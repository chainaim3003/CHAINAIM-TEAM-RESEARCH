"""orchestrate.py — V1 pipeline driver.

Data-flow contract (DESIGN/01-architecture-contract.md s1), V1 subset:
    ingest -> route(classify) -> dedupe gate -> extract(youtube) -> publish(manifest+ledger)

V1 spends ZERO LLM tokens. synthesize/judge are a MANUAL Claude Code/Max session in V1
(guided by synth/*.md + CLAUDE.md); they are NOT run here. The ModelProvider exists
(scripts/provider.py) and its guardrails are runnable via --provider-check, but the V1
pipeline never calls .complete().

Path resolution: relative paths in config (input.source_*, output.kb_dir, etc.) are
anchored to the PACKAGE dir (where config.yaml lives), not the current working directory,
so a run resolves to the same place no matter where you invoke it from. Absolute paths
are used as-is. See _anchor().

CLI flags (Rule 8 — all behavior configurable, defaults sensible):
    --config PATH            config file (default: ../config.yaml next to scripts/)
    --dry-run               plan only: classify + dedupe, NO extraction, NO writes
    --max-videos N          cap sources processed this run (default: all)
    --naming title_id|id    file names '<Title> [<id>]' (default) or '<id>' (no title lookup)
    --timestamps            include timestamps in transcripts (overrides config)
    --no-timestamps         exclude timestamps (overrides config)
    --force                 ignore dedupe gate; re-extract even if already seen
    --provider-check        print model-provider guardrail report and exit
    --kb-dir PATH           override output.kb_dir (default: from config)
    --source-list PATH      override input.source_list (default: from config)
    --source-dir PATH       override input.source_dir (default: from config)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

# make sibling scripts/ modules importable, and the package root for ingest/ extract/
HERE = Path(__file__).resolve().parent          # .../chainaim-deep-research/scripts
ROOT = HERE.parent                               # .../chainaim-deep-research
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from manifest import Manifest                     # noqa: E402
from throttle import Throttle                     # noqa: E402
from cost_ledger import CostLedger                # noqa: E402
import provider as provider_mod                   # noqa: E402
from ingest.local_dir import collect_sources      # noqa: E402
from extract import youtube as yt                 # noqa: E402
from extract.metadata import fetch_youtube_title  # noqa: E402
from naming import DEFAULT_MAX_LEN, safe_stem     # noqa: E402
from envfile import load_env_file                 # noqa: E402
from extract import github as gh                  # noqa: E402
from extract import arxiv as ax                   # noqa: E402
from extract import web as wb                     # noqa: E402
from manifest import content_hash                 # noqa: E402


# ----- Router / classify (contract s4: classify(line) -> (kind, key)) -----
# Regex-only: known types are free to route. The LLM Router (Haiku) for AMBIGUOUS
# links is a V3 addition (DESIGN/06-design-reference-table-v2.md, row Router).
_YT_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})"),
    re.compile(r"^([a-zA-Z0-9_-]{11})$"),
]


# GitHub (PR-5). "github.com/<owner>/<repo>[/anything]" -> repo; "github.com/<owner>" -> account.
# The look-behind skips gist.github.com and other subdomains. Manifest keys "gh:<owner>[/<repo>]"
# classify too, so tools that re-derive URLs from keys (migrate_manifest.py) keep working.
_GH_URL = re.compile(r"(?<![\w.])(?:www\.)?github\.com/([A-Za-z0-9-]+)(?:/([A-Za-z0-9._-]+))?", re.I)
_GH_KEY = re.compile(r"^gh:([A-Za-z0-9-]+)(?:/([A-Za-z0-9._-]+))?$")
_GH_RESERVED = {"orgs", "settings", "topics", "marketplace", "features", "about", "pricing", "login",
                "explore", "sponsors", "collections", "notifications", "issues", "pulls", "search",
                "apps", "enterprise", "trending", "site", "security", "customer-stories"}


# arXiv (PR-7): arxiv.org/abs|pdf|html/<id>[vN][.pdf], "arXiv:<id>" and manifest keys "arxiv:<id>".
# The version suffix is dropped so every version of a paper dedupes to one entry.
_ARXIV = re.compile(rf"(?:arxiv\.org/(?:abs|pdf|html)/|\barxiv:\s*)({ax.NEW_ID}|{ax.OLD_ID})(?:v\d+)?", re.I)


def classify(line: str) -> Tuple[str, Optional[str]]:
    """Classify a raw source line. Returns (kind, key).

    Kinds: "youtube" (key = 11-char video id), "github_repo" (key = "gh:<owner>/<repo>"),
    "github_account" (key = "gh:<owner>"), "arxiv" (key = "arxiv:<id>"), "web" (any other
    http(s) URL; key = "web:<10-hex hash of the normalized URL>"). Lines without a URL ->
    ("unknown", None), skipped with a note.
    """
    s = line.strip()
    for pat in _YT_PATTERNS:
        m = pat.search(s)
        if m:
            return "youtube", m.group(1)
    m = _GH_KEY.match(s) or _GH_URL.search(s)
    if m and m.group(1).lower() not in _GH_RESERVED:
        owner, repo = m.group(1), m.group(2)
        if repo:
            repo = repo[:-4] if repo.lower().endswith(".git") else repo
            if repo:
                return "github_repo", f"gh:{owner}/{repo}"
        return "github_account", f"gh:{owner}"
    m = _ARXIV.search(s)
    if m:
        return "arxiv", f"arxiv:{m.group(1)}"
    url = wb.first_url(s)
    if url:
        return "web", wb.web_key(url)
    return "unknown", None


def canonical_url(kind: str, key: str) -> str:
    """Return the clean, canonical URL for a classified source.

    The manifest stores THIS (not the raw input line) as `source_url`, so every entry has a
    usable link no matter how the line was written (youtu.be/..., ?si= tracking params,
    notes after the link, or a pasted table row). The raw line is kept separately as
    `source_line`. Raises ValueError for kinds that have no canonical form yet, so a new
    kind can never silently store a wrong URL.
    """
    if kind == "youtube":
        return f"https://www.youtube.com/watch?v={key}"
    if kind in ("github_repo", "github_account"):
        return f"https://github.com/{key[3:]}"
    if kind == "arxiv":
        return f"https://arxiv.org/abs/{key[6:]}"
    # "web" keys are hashes; the URL itself comes from the source line (see plan_url()).
    raise ValueError(f"no canonical URL rule for kind '{kind}'")


# ----- config + path resolution -----
def load_config(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"config not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _anchor(path_str: str, base: Path) -> Path:
    """Resolve a config path to a clean absolute path. Absolute -> used as-is. Relative ->
    anchored under `base` (the PACKAGE dir where config.yaml lives), NOT the current working
    directory, so a run resolves to the same place regardless of where you invoke it from.
    `(base / p)` returns `p` unchanged when `p` is absolute, so this handles both. `.resolve()`
    collapses any `..` so the manifest stores clean paths."""
    return (base / Path(path_str)).resolve()


def resolve_paths(cfg: dict, kb_dir_override: Optional[str]) -> Dict[str, Path]:
    out = cfg.get("output", {})
    kb_dir = _anchor(kb_dir_override or out.get("kb_dir", "."), ROOT)
    full_dir = kb_dir / out.get("full_dir", "kb/full")
    manifest = kb_dir / out.get("manifest", "manifest.json")
    ledger = kb_dir / cfg.get("cost", {}).get("ledger", "cost_ledger.jsonl")
    return {"kb_dir": kb_dir, "full_dir": full_dir, "manifest": manifest, "ledger": ledger}


def build_throttle(cfg: dict) -> Throttle:
    t = cfg.get("youtube", {}).get("throttle", {})
    return Throttle(
        min_delay_s=float(t.get("min_delay_s", 2.0)),
        jitter_s=float(t.get("jitter_s", 1.0)),
        backoff_factor=float(t.get("backoff_factor", 2.0)),
        max_retries=int(t.get("max_retries", 3)),
    )


# ----- main pipeline -----
def run(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    paths = resolve_paths(cfg, args.kb_dir)

    # --provider-check: run guardrails report and exit (no pipeline)
    if args.provider_check:
        report = provider_mod.provider_env_report(cfg)
        print("Provider guardrail report:")
        for k, v in report.items():
            print(f"  {k}: {v}")
        try:
            provider_mod.select_provider(cfg)
            print("  guardrails: PASS")
            return 0
        except provider_mod.ProviderError as exc:
            print(f"  guardrails: FAIL -> {exc}")
            return 2

    yt_cfg = cfg.get("youtube", {})
    # transcript_script gets the SAME package-dir anchoring as every other config path
    # (see _anchor): a RELATIVE value resolves against ROOT (the package dir), not the shell
    # cwd, so the vendored in-repo skill works no matter where `uv run` is invoked. An
    # ABSOLUTE value passes through unchanged. Empty/unset stays "" so the failure is explicit.
    _ts_raw = yt_cfg.get("transcript_script", "")
    transcript_script = str(_anchor(_ts_raw, ROOT)) if _ts_raw else ""
    if args.timestamps is not None:
        timestamps = args.timestamps
    else:
        timestamps = bool(yt_cfg.get("timestamps", False))
    formats = cfg.get("output", {}).get("formats", ["txt"])

    # PR-2 naming: "title_id" -> "<Title> [<key>]" (title via oEmbed), "id" -> "<key>" (pre-PR-2).
    # CLI --naming wins over config output.naming.
    naming = args.naming or cfg.get("output", {}).get("naming", "title_id")
    if naming not in ("title_id", "id"):
        sys.exit(f"invalid output.naming '{naming}' (expected 'title_id' or 'id')")
    max_stem_len = int(cfg.get("output", {}).get("max_stem_len", DEFAULT_MAX_LEN))
    tl_cfg = yt_cfg.get("title_lookup", {})

    # ingest — CLI flags override config (config supplies the defaults)
    items = collect_sources(
        source_list=args.source_list if args.source_list is not None else cfg.get("input", {}).get("source_list"),
        source_dir=args.source_dir if args.source_dir is not None else cfg.get("input", {}).get("source_dir"),
        base_dir=ROOT,
    )

    manifest = Manifest(paths["manifest"])
    ledger = CostLedger(paths["ledger"], token_budget_per_run=int(cfg.get("cost", {}).get("token_budget_per_run", 0)))
    throttle = build_throttle(cfg)

    # Secrets (e.g. GITHUB_TOKEN) come from the environment or the git-ignored repo-root .env.
    # Existing environment variables always win; values are never printed.
    load_env_file(ROOT.parent / ".env")
    gh_cfg = cfg.get("github", {})

    planned: List[Dict] = []
    skipped_unknown: List[str] = []
    skipped_dedupe = 0
    extracted = 0
    failed: List[Tuple[str, str]] = []

    for item in items:
        kind, key = classify(item["url"])
        if kind not in ("youtube", "github_repo", "github_account", "arxiv", "web") or not key:
            skipped_unknown.append(item["url"])
            continue
        refresh = False
        if kind != "github_account" and manifest.seen(key) and not args.force:
            if kind == "github_repo" and args.refresh_github:
                refresh = True  # re-check: re-extract only if the repo's commit changed
            else:
                skipped_dedupe += 1
                continue
        # url  = canonical link (stored as manifest source_url and passed to the extractor)
        # line = the original input line, kept verbatim as manifest source_line (audit trail)
        url = wb.normalize_url(wb.first_url(item["url"]) or "") if kind == "web" else canonical_url(kind, key)
        planned.append({"kind": kind, "key": key, "url": url, "line": item["url"], "refresh": refresh})
        if args.max_videos is not None and len(planned) >= args.max_videos:
            break

    n_yt = sum(1 for p in planned if p["kind"] == "youtube")
    n_gh = sum(1 for p in planned if p["kind"].startswith("github"))
    n_ax = sum(1 for p in planned if p["kind"] == "arxiv")
    n_web = sum(1 for p in planned if p["kind"] == "web")
    print(f"== ChainAIM ==  ingest={len(items)}  youtube_new={n_yt}  github_new={n_gh}  "
          f"arxiv_new={n_ax}  web_new={n_web}  "
          f"dedupe_skipped={skipped_dedupe}  unknown_skipped={len(skipped_unknown)}  naming={naming}")
    if skipped_unknown:
        print("  unknown (no URL found; skipped):")
        for u in skipped_unknown[:10]:
            print(f"    - {u}")

    if args.dry_run:
        print("\n-- DRY RUN: would extract --")
        for p in planned:
            note = " (repos listed at extract time)" if p["kind"] == "github_account" else (
                " (refresh: re-extract only if changed)" if p["refresh"] else "")
            print(f"    {p['key']}  <-  {p['line']}{note}")
        if naming == "title_id":
            print("(titles are looked up at extract time, not in a dry run)")
        print("(no files written, no manifest/ledger changes)")
        return 0

    gh_client: Optional[gh.GitHubClient] = None
    gh_stopped = False
    ax_client: Optional[ax.ArxivClient] = None
    for p in planned:
        if p["kind"] in ("arxiv", "web"):
            if p["kind"] == "arxiv" and ax_client is None:
                ax_cfg = cfg.get("arxiv", {})
                ax_client = ax.ArxivClient(timeout_s=float(ax_cfg.get("timeout_s", 30)),
                                           min_delay_s=float(ax_cfg.get("min_delay_s", 3.0)))
            ok = _run_doc_item(p, ax_client, cfg, manifest, paths, max_stem_len)
            ledger.add(free_tool_calls=1)
            if ok is True:
                extracted += 1
                ledger.add(items_processed=1)
            else:
                failed.append((p["key"], ok))
            continue
        if p["kind"] != "youtube":
            if gh_stopped:
                failed.append((p["key"], "skipped: GitHub rate limit reached earlier in this run"))
                continue
            if gh_client is None:
                gh_client = gh.GitHubClient(
                    token=os.environ.get(gh_cfg.get("token_env", "GITHUB_TOKEN")) or None,
                    timeout_s=float(gh_cfg.get("timeout_s", 20)),
                    min_delay_s=float(gh_cfg.get("min_delay_s", 0.5)),
                    min_remaining=int(gh_cfg.get("min_remaining", 5)),
                )
            ok_n, gh_failed, gh_stopped = _run_github_item(p, gh_client, gh_cfg, manifest, paths,
                                                           max_stem_len, args)
            extracted += ok_n
            ledger.add(items_processed=ok_n)
            failed.extend(gh_failed)
            continue
        # Title lookup (PR-2). Failure never invents a title: fall back to the key-only name.
        title: Optional[str] = None
        if naming == "title_id":
            title, why = fetch_youtube_title(
                p["key"],
                timeout_s=float(tl_cfg.get("timeout_s", 10.0)),
                retries=int(tl_cfg.get("retries", 2)),
                backoff_s=float(tl_cfg.get("backoff_s", 1.0)),
            )
            if title is None:
                print(f"  [warn] {p['key']}: title unavailable ({why}); file named by ID")
        stem = safe_stem(title, p["key"], max_len=max_stem_len) if title else None
        ok, file_paths, info = yt.extract(
            key=p["key"],
            source=p["url"],
            transcript_script=transcript_script,
            full_dir=paths["full_dir"],
            kb_dir=paths["kb_dir"],
            formats=formats,
            throttle=throttle,
            timestamps=timestamps,
            stem=stem,
        )
        ledger.add(free_tool_calls=1)
        if ok:
            manifest.record(p["key"], p["url"], info, file_paths, status="extracted",
                            source_line=p["line"], title=title, stem=stem)
            ledger.add(items_processed=1)
            extracted += 1
            print(f"  [ok] {p['key']} -> {file_paths.get('txt', next(iter(file_paths.values()), '?'))}")
        else:
            failed.append((p["key"], info))
            print(f"  [FAIL] {p['key']}: {info}")

    if gh_client is not None:
        ledger.add(free_tool_calls=gh_client.calls)
    ledger.add(items_skipped_dedupe=skipped_dedupe)
    # cumulative() must run BEFORE flush(): flush writes this run to disk, and cumulative
    # reads disk + in-memory — calling it after flush would double-count the current run.
    cum = ledger.cumulative()
    run_line = ledger.flush()

    print("\n== run report ==")
    print(f"  extracted={extracted}  failed={len(failed)}  dedupe_skipped={skipped_dedupe}")
    print(f"  this run : free_tool_calls={run_line['free_tool_calls']}  llm_tokens={run_line['llm_tokens']}")
    print(f"  cumulative: runs={cum['runs']}  items_processed={cum['items_processed']}  "
          f"llm_tokens={cum['llm_tokens']}")
    if failed:
        print("  NOTE: failures above are usually missing captions or throttling — safe to re-run (dedupe protects successes).")
    print("\n  next: run scripts/build_kb_pack.py, then paste a kb/prompts/*.prompt.md file into any AI "
          "and save its answer in kb/highlights/ (the agent itself uses no AI)")
    return 0 if not failed else 1


def _run_github_item(p: Dict, client: "gh.GitHubClient", gh_cfg: dict, manifest: Manifest,
                     paths: Dict[str, Path], max_stem_len: int, args: argparse.Namespace):
    """Extract one planned GitHub repo or account. Returns (extracted_count, failures, rate_limited).

    An account expands into its repos (most recently pushed first, forks/archived excluded unless
    configured); each repo becomes its own manifest entry and file, deduped like everything else.
    """
    failures: List[Tuple[str, str]] = []
    try:
        if p["kind"] == "github_account":
            owner = p["key"][3:]
            names = gh.list_account_repos(
                client, owner, max_repos=int(gh_cfg.get("max_repos", 20)),
                include_forks=bool(gh_cfg.get("include_forks", False)),
                include_archived=bool(gh_cfg.get("include_archived", False)))
            print(f"  [github] account {owner}: {len(names)} repo(s)")
            todo = []
            for full in names:
                k = f"gh:{full}"
                if manifest.seen(k) and not args.force and not args.refresh_github:
                    print(f"    - {k}: already extracted (dedupe)")
                    continue
                todo.append({"kind": "github_repo", "key": k, "url": canonical_url("github_repo", k),
                             "line": p["line"], "refresh": manifest.seen(k)})
        else:
            todo = [p]
    except gh.GitHubRateLimit as exc:
        print(f"  [FAIL] {p['key']}: {exc}")
        return 0, [(p["key"], str(exc))], True
    except gh.GitHubError as exc:
        print(f"  [FAIL] {p['key']}: {exc}")
        return 0, [(p["key"], str(exc))], False

    done = 0
    for item in todo:
        full = item["key"][3:]
        try:
            md, meta = gh.extract_repo(
                client, full,
                max_tree_entries=int(gh_cfg.get("max_tree_entries", 400)),
                max_files=int(gh_cfg.get("max_files", 15)),
                max_file_bytes=int(gh_cfg.get("max_file_bytes", 50_000)),
                max_total_bytes=int(gh_cfg.get("max_total_bytes", 300_000)),
                key_files=gh_cfg.get("key_files") or None)
        except gh.GitHubRateLimit as exc:
            print(f"  [FAIL] {item['key']}: {exc}")
            failures.append((item["key"], str(exc)))
            return done, failures, True
        except gh.GitHubError as exc:
            print(f"  [FAIL] {item['key']}: {exc}")
            failures.append((item["key"], str(exc)))
            continue
        hash_value = f"git-{meta['sha'][:16]}"
        prev = manifest.get(item["key"]) or {}
        if item.get("refresh") and prev.get("content_hash") == hash_value:
            print(f"  [unchanged] {item['key']} (commit {meta['sha'][:12]})")
            continue
        stem = safe_stem(full.replace("/", "__"), "github", max_len=max_stem_len)
        paths["full_dir"].mkdir(parents=True, exist_ok=True)
        target = paths["full_dir"] / f"{stem}.md"
        target.write_text(md, encoding="utf-8")
        try:
            rel = target.relative_to(paths["kb_dir"]).as_posix()
        except ValueError:
            rel = target.as_posix()
        manifest.record(item["key"], item["url"], hash_value, {"md": rel}, status="extracted",
                        source_line=item["line"], title=meta["title"], stem=stem, kind="github_repo")
        done += 1
        print(f"  [ok] {item['key']} -> {rel}")
    return done, failures, False


def _run_doc_item(p: Dict, client: Optional["ax.ArxivClient"], cfg: dict, manifest: Manifest,
                  paths: Dict[str, Path], max_stem_len: int):
    """Extract one arXiv paper or web article (PR-7, no AI). Returns True or an error string."""
    try:
        if p["kind"] == "arxiv":
            ax_cfg = cfg.get("arxiv", {})
            arxiv_id = p["key"][6:]
            md, meta = ax.extract_paper(client, arxiv_id,
                                        max_chars=int(ax_cfg.get("max_chars", 400_000)),
                                        min_fulltext_chars=int(ax_cfg.get("min_fulltext_chars", 2_000)))
            stem = safe_stem(meta["title"], f"arxiv-{ax.file_id(arxiv_id)}", max_len=max_stem_len)
            kind = "arxiv_paper"
            extra = f" (full text: {meta['fulltext_source']})"
        else:
            w_cfg = cfg.get("web", {})
            md, meta = wb.extract_article(p["url"], min_chars=int(w_cfg.get("min_chars", 300)),
                                          max_chars=int(w_cfg.get("max_chars", 300_000)))
            stem = safe_stem(meta["title"], "web-" + p["key"][4:], max_len=max_stem_len)
            kind = "web_article"
            extra = ""
    except (ax.ArxivError, wb.WebError) as exc:
        print(f"  [FAIL] {p['key']}: {exc}")
        return str(exc)
    paths["full_dir"].mkdir(parents=True, exist_ok=True)
    target = paths["full_dir"] / f"{stem}.md"
    target.write_text(md, encoding="utf-8")
    try:
        rel = target.relative_to(paths["kb_dir"]).as_posix()
    except ValueError:
        rel = target.as_posix()
    manifest.record(p["key"], p["url"], content_hash(md), {"md": rel}, status="extracted",
                    source_line=p["line"], title=meta["title"], stem=stem, kind=kind)
    print(f"  [ok] {p['key']} -> {rel}{extra}")
    return True


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="orchestrate", description="ChainAIM Deep Research Agent — V1 pipeline")
    p.add_argument("--config", default=str(ROOT / "config.yaml"), help="path to config.yaml")
    p.add_argument("--dry-run", action="store_true", help="plan only; no extraction or writes")
    p.add_argument("--max-videos", type=int, default=None, help="cap sources processed this run")
    p.add_argument("--force", action="store_true", help="ignore dedupe gate; re-extract seen keys")
    p.add_argument("--refresh-github", action="store_true",
                   help="re-check already-extracted GitHub repos; re-extract only those whose commit changed")
    p.add_argument("--provider-check", action="store_true", help="print provider guardrail report and exit")
    p.add_argument("--kb-dir", default=None, help="override output.kb_dir")
    p.add_argument("--naming", choices=["title_id", "id"], default=None,
                   help="file naming: 'title_id' = '<Title> [<id>]' (title via oEmbed), "
                        "'id' = '<id>' (no title lookup). Default: output.naming in config")
    p.add_argument("--source-list", default=None,
                   help="override input.source_list (path to a newline-delimited source file)")
    p.add_argument("--source-dir", default=None,
                   help="override input.source_dir (directory scanned for *.txt/*.md source files)")
    ts = p.add_mutually_exclusive_group()
    ts.add_argument("--timestamps", dest="timestamps", action="store_true", default=None,
                    help="include timestamps in transcripts")
    ts.add_argument("--no-timestamps", dest="timestamps", action="store_false",
                    help="exclude timestamps in transcripts")
    return p


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
