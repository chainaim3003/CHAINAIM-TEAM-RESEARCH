"""extract/github.py — free, AI-free GitHub repo -> text extractor (PR-5).

Why (DESIGN/07-build-plan.md, PR-5; decision 2026-11-23: the agent stays AI-free):
    A GitHub repo or account link in the source list becomes one Markdown file per repo in
    kb/full/ ("<owner>__<repo> [github].md") containing the repo's facts, folder structure,
    README and key files, plus (via build_kb_pack.py) a ready-to-paste prompt so the user can
    summarise the repo in any AI.

Source: GitHub REST API (https://api.github.com), standard library only.
    - Public repos work without a token (GitHub allows 60 requests/hour unauthenticated).
    - With GITHUB_TOKEN (read from the environment or the repo-root .env, see envfile.py) the
      limit is 5,000 requests/hour and private repos you can read are included. The token is
      sent only as an Authorization header and is never printed or written to disk.

Requests per repo (typical): 1 repo metadata + 1 tree + 1 README + up to `max_files` key files.
Before each request the remaining rate limit (X-RateLimit-Remaining) is checked; when it drops
below `min_remaining` the extractor stops with GitHubRateLimit instead of failing half-way.

Bounded output (all configurable, config `github.*`): at most `max_tree_entries` paths in the
folder listing, `max_files` key files, `max_file_bytes` per file and `max_total_bytes` overall.
Every cut is stated explicitly in the output — nothing is silently dropped.

`http_get` and `sleep` are injectable so the offline eval suite can test every path.
"""

from __future__ import annotations

import fnmatch
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

API = "https://api.github.com"
USER_AGENT = "chainaim-deep-research/0.1 (+https://github.com/chainaim3003/CHAINAIM-TEAM-RESEARCH)"

# Files worth including, in priority order (glob patterns on the repo path).
DEFAULT_KEY_FILES = [
    "package.json", "pyproject.toml", "requirements*.txt", "setup.py", "setup.cfg",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle*", "Dockerfile", "docker-compose*.y*ml",
    "Makefile", "CLAUDE.md", "AGENTS.md", "llms.txt", "**/SKILL.md", "CONTRIBUTING.md",
    "docs/*.md", "doc/*.md",
    # Nested projects (code in a subfolder, e.g. monorepos): same files one or more levels down.
    "*/README.md", "*/pyproject.toml", "*/package.json", "*/CLAUDE.md", "*/requirements*.txt",
    "*/Cargo.toml", "*/go.mod", "*/Dockerfile",
]


class GitHubError(Exception):
    """Any GitHub API failure (status kept for decisions)."""

    def __init__(self, msg: str, status: int = 0) -> None:
        super().__init__(msg)
        self.status = status


class GitHubRateLimit(GitHubError):
    """Raised before a request when the remaining rate limit is too low."""


# http_get(url, headers, timeout_s) -> (status, response_headers, body_bytes)
HttpGet = Callable[[str, Dict[str, str], float], Tuple[int, Dict[str, str], bytes]]


def default_http_get(url: str, headers: Dict[str, str], timeout_s: float) -> Tuple[int, Dict[str, str], bytes]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 (fixed https host)
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, exc.read() or b""


@dataclass
class GitHubClient:
    """Minimal REST client with rate-limit awareness and polite pacing."""
    token: Optional[str] = None
    timeout_s: float = 20.0
    min_delay_s: float = 0.5
    min_remaining: int = 5
    http_get: HttpGet = default_http_get
    sleep: Callable[[float], None] = time.sleep
    remaining: Optional[int] = None
    calls: int = 0
    _last: float = field(default=0.0, repr=False)

    def _headers(self, raw: bool) -> Dict[str, str]:
        h = {"User-Agent": USER_AGENT, "X-GitHub-Api-Version": "2022-11-28",
             "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def get(self, path: str, *, raw: bool = False) -> Tuple[int, Dict[str, str], bytes]:
        if self.remaining is not None and self.remaining < self.min_remaining:
            raise GitHubRateLimit(
                f"GitHub rate limit nearly used up ({self.remaining} left). "
                f"Wait for the hourly reset or add GITHUB_TOKEN to .env (5,000/h).", 403)
        if self.calls and self.min_delay_s > 0:
            self.sleep(self.min_delay_s)
        self.calls += 1
        try:
            status, headers, body = self.http_get(f"{API}{path}", self._headers(raw), self.timeout_s)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GitHubError(f"network error calling GitHub: {exc}") from exc
        if "x-ratelimit-remaining" in headers:
            try:
                self.remaining = int(headers["x-ratelimit-remaining"])
            except ValueError:
                pass
        if status == 403 and self.remaining == 0:
            raise GitHubRateLimit("GitHub rate limit exceeded. Add GITHUB_TOKEN to .env or wait for the reset.", 403)
        return status, headers, body

    def get_json(self, path: str):
        status, headers, body = self.get(path)
        if status == 404:
            raise GitHubError(f"not found: {path} (does not exist, or is private and needs GITHUB_TOKEN)", 404)
        if status >= 400:
            raise GitHubError(f"GitHub API {status} for {path}: {body[:200]!r}", status)
        return json.loads(body.decode("utf-8")), headers


def list_account_repos(client: GitHubClient, owner: str, *, max_repos: int = 20,
                       include_forks: bool = False, include_archived: bool = False) -> List[str]:
    """Return up to max_repos "owner/repo" names for a user or organisation, most recently
    pushed first. Works for both users and orgs via /users/{owner}/repos."""
    names: List[str] = []
    page = 1
    while len(names) < max_repos:
        data, _ = client.get_json(f"/users/{owner}/repos?per_page=100&sort=pushed&type=owner&page={page}")
        if not data:
            break
        for r in data:
            if r.get("fork") and not include_forks:
                continue
            if r.get("archived") and not include_archived:
                continue
            names.append(r["full_name"])
            if len(names) >= max_repos:
                break
        if len(data) < 100:
            break
        page += 1
    return names


def _fence_for(text: str) -> str:
    """A backtick fence longer than any backtick run in `text`, so file content that contains
    its own ``` code blocks (e.g. a README) cannot break out of the block it is wrapped in."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def _pick_key_files(tree: List[dict], patterns: List[str], max_files: int, max_file_bytes: int) -> Tuple[List[str], List[str]]:
    """Choose key files by pattern priority. Returns (chosen_paths, skipped_notes)."""
    blobs = {t["path"]: t for t in tree if t.get("type") == "blob"}
    chosen: List[str] = []
    notes: List[str] = []
    for pat in patterns:
        for path in sorted(blobs):
            if path in chosen or not fnmatch.fnmatch(path, pat):
                continue
            if "/" in path and "/" not in pat.replace("**/", ""):
                if not pat.startswith("**/"):
                    continue  # root-level patterns match root files only
            size = blobs[path].get("size") or 0
            if size > max_file_bytes:
                notes.append(f"{path} skipped ({size:,} bytes > max_file_bytes {max_file_bytes:,})")
                continue
            chosen.append(path)
            if len(chosen) >= max_files:
                return chosen, notes
    return chosen, notes


def extract_repo(
    client: GitHubClient,
    full_name: str,
    *,
    max_tree_entries: int = 400,
    max_files: int = 15,
    max_file_bytes: int = 50_000,
    max_total_bytes: int = 300_000,
    key_files: Optional[List[str]] = None,
) -> Tuple[str, Dict[str, str]]:
    """Fetch one repo and render it as Markdown.

    Returns (markdown, meta) where meta has: full_name, title, sha, default_branch, html_url.
    Raises GitHubError / GitHubRateLimit.
    """
    repo, _ = client.get_json(f"/repos/{full_name}")
    branch = repo.get("default_branch") or "main"
    tree_data, _ = client.get_json(f"/repos/{full_name}/git/trees/{branch}?recursive=1")
    sha = tree_data.get("sha", "")
    tree = tree_data.get("tree") or []

    status, _, readme = client.get(f"/repos/{full_name}/readme", raw=True)
    readme_text = readme.decode("utf-8", errors="replace") if status == 200 else ""

    chosen, notes = _pick_key_files(tree, key_files or DEFAULT_KEY_FILES, max_files, max_file_bytes)
    files: List[Tuple[str, str]] = []
    total = len(readme_text.encode("utf-8"))
    for path in chosen:
        st, _, body = client.get(f"/repos/{full_name}/contents/{path}?ref={sha}", raw=True)
        if st != 200:
            notes.append(f"{path} could not be fetched (HTTP {st})")
            continue
        text = body.decode("utf-8", errors="replace")
        if total + len(body) > max_total_bytes:
            notes.append(f"{path} and later files skipped (max_total_bytes {max_total_bytes:,} reached)")
            break
        total += len(body)
        files.append((path, text))

    paths = [t["path"] + ("/" if t.get("type") == "tree" else "") for t in tree]
    shown = paths[:max_tree_entries]
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lic = (repo.get("license") or {}).get("spdx_id") or "none"
    out: List[str] = [
        f"# {full_name}",
        "",
        f"- URL: {repo.get('html_url', f'https://github.com/{full_name}')}",
        f"- Description: {repo.get('description') or '(none)'}",
        f"- Language: {repo.get('language') or 'n/a'} · Stars: {repo.get('stargazers_count', 0)} · "
        f"Forks: {repo.get('forks_count', 0)} · License: {lic}",
        f"- Topics: {', '.join(repo.get('topics') or []) or '(none)'}",
        f"- Default branch: {branch} · Commit: {sha[:12]} · Last push: {repo.get('pushed_at', 'n/a')}",
        f"- Extracted: {fetched} by chainaim-deep-research (no AI)",
        "",
        f"## Folder structure ({len(paths)} entries)",
        "```",
        *shown,
    ]
    if len(paths) > len(shown):
        out.append(f"... {len(paths) - len(shown)} more entries not shown (max_tree_entries={max_tree_entries})")
    if tree_data.get("truncated"):
        out.append("... GitHub truncated this tree listing (very large repo)")
    out += ["```", "", "## README", "", readme_text.strip() or "(no README)", "", "## Key files", ""]
    if not files:
        out.append("(none matched)")
    for path, text in files:
        lang = path.rsplit(".", 1)[-1] if "." in path else ""
        fence = _fence_for(text)
        out += [f"### {path}", f"{fence}{lang}", text.rstrip(), fence, ""]
    if notes:
        out += ["## Not included", "", *[f"- {n}" for n in notes], ""]
    meta = {"full_name": full_name, "title": full_name, "sha": sha, "default_branch": branch,
            "html_url": repo.get("html_url", f"https://github.com/{full_name}")}
    return "\n".join(out) + "\n", meta
