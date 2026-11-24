"""build_kb_pack.py — make the KB ready to hand to ANY AI by hand (no AI used here).

Why (DESIGN/07-build-plan.md, decision 2026-11-23 "Way 1 — manual AI"):
    The agent stays a free, AI-free transcript tool. Summaries are made by the user in the AI
    of their choice (Claude Desktop, Claude Code, Gemini, GPT, ...). To make that a single
    copy-paste, this script writes, for every extracted transcript:

      kb/prompts/<stem>.prompt.md   instructions + title + source + the FULL transcript,
                                    ready to paste into any AI (template: synth/manual_prompt.md)
    and one overview file:
      kb/INDEX.md                   every entry: title, source link, transcript, prompt, and
                                    whether a summary has been saved in kb/highlights/ yet

    <stem> is the same "<Title> [<id>]" name as the transcript, so transcript, prompt and the
    summary you save (kb/highlights/<stem>.md) always match.

Behaviour:
    - Transcripts are copied into the prompt VERBATIM (never edited, never truncated).
    - Idempotent: a prompt is rewritten only when its transcript changed (content hash recorded
      in the prompt's first line) or with --force. INDEX.md is rebuilt every run.
    - Entries whose transcript file is missing are reported and skipped.
    - Template placeholders: {{TITLE}} {{SOURCE_URL}} {{STEM}} {{TRANSCRIPT}} (plain string
      replacement, so braces inside a transcript are safe).

No LLM. No network. Reads the manifest and kb/full/; writes only kb/prompts/ and kb/INDEX.md.

Usage (run from chainaim-deep-research/):
    uv run scripts/build_kb_pack.py --dry-run     # show what would be written
    uv run scripts/build_kb_pack.py               # write prompts + INDEX.md
    uv run scripts/build_kb_pack.py --key YtRIj_KU9d4 --force

Flags (Rule 8):
    --config PATH     config.yaml (default: next to scripts/)
    --kb-dir PATH     override output.kb_dir
    --dry-run         report only; write nothing
    --force           rewrite prompts even if unchanged
    --key KEY         only this manifest key (INDEX.md still lists everything)
    --template PATH   prompt template (default: output.prompt_template)
    --no-index        do not rebuild kb/INDEX.md

Exit codes: 0 success, 1 manifest/template missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from orchestrate import _anchor, load_config, resolve_paths  # noqa: E402
from manifest import content_hash                              # noqa: E402

HASH_MARK = "<!-- transcript_hash: "

# PR-8: a saved summary only counts when it looks like a real answer. Short files or files that
# start like a pasted shell command (a clipboard mix-up) are flagged "check" instead of "ok".
DEFAULT_MIN_SUMMARY_CHARS = 200
_COMMAND_START = ("$", "PS ", "cd ", "uv run", "git ", "Get-", "Set-", "[IO.File]")


def summary_status(path: Path, *, min_chars: int = DEFAULT_MIN_SUMMARY_CHARS) -> str:
    """Return "ok", "check" (exists but too short / looks like a pasted command) or "missing"."""
    if not path.exists():
        return "missing"
    text = path.read_text(encoding="utf-8-sig", errors="replace").strip()
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if len(text) < min_chars or first.startswith(_COMMAND_START):
        return "check"
    return "ok"


def render_prompt(template: str, *, title: str, source_url: str, stem: str, transcript: str) -> str:
    """Fill the template with plain replacements and prepend the transcript-hash marker line."""
    body = (template.replace("{{TITLE}}", title)
                    .replace("{{SOURCE_URL}}", source_url)
                    .replace("{{STEM}}", stem)
                    .replace("{{TRANSCRIPT}}", transcript))
    return f"{HASH_MARK}{content_hash(transcript)} -->\n{body}"


def _existing_hash(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    first = path.read_text(encoding="utf-8").split("\n", 1)[0]
    return first[len(HASH_MARK):-4].strip() if first.startswith(HASH_MARK) else None


def _link(rel: str) -> str:
    """Markdown link target that tolerates spaces/brackets in file names (CommonMark <...>)."""
    return f"<{rel}>"


def build_pack(
    data: Dict[str, Dict[str, Any]],
    *,
    kb_dir: Path,
    template: str,
    repo_template: Optional[str] = None,
    kind_templates: Optional[Dict[str, str]] = None,
    prompts_rel: str = "kb/prompts",
    highlights_rel: str = "kb/highlights",
    only_key: Optional[str] = None,
    min_summary_chars: int = DEFAULT_MIN_SUMMARY_CHARS,
    force: bool = False,
    dry_run: bool = False,
    write_index: bool = True,
) -> Dict[str, List[Any]]:
    """Write prompt files (+ INDEX.md). Returns {"written","unchanged","missing","rows"}.

    GitHub entries (manifest kind "github_repo", PR-5) use `repo_template` when given.
    """
    written: List[str] = []
    unchanged: List[str] = []
    missing: List[str] = []
    rows: List[Dict[str, str]] = []
    prompts_dir = kb_dir / prompts_rel
    for key, entry in data.items():
        if entry.get("status") != "extracted":
            continue
        rel_full = (entry.get("full_paths") or {}).get("txt") or next(iter((entry.get("full_paths") or {}).values()), None)
        if not rel_full or not (kb_dir / rel_full).exists():
            missing.append(key)
            continue
        stem = entry.get("stem") or Path(rel_full).stem
        title = entry.get("title") or stem
        url = entry.get("source_url", "")
        prompt_path = prompts_dir / f"{stem}.prompt.md"
        summary_rel = f"{highlights_rel}/{stem}.md"
        rows.append({"title": title, "url": url,
                     "full": rel_full, "prompt": f"{prompts_rel}/{stem}.prompt.md",
                     "summary": summary_rel,
                     "status": summary_status(kb_dir / summary_rel, min_chars=min_summary_chars)})
        if only_key and key != only_key:
            continue
        transcript = (kb_dir / rel_full).read_text(encoding="utf-8")
        kind = entry.get("kind")
        tpl = ((kind_templates or {}).get(kind)
               or (repo_template if (repo_template and kind == "github_repo") else None)
               or template)
        if not force and _existing_hash(prompt_path) == content_hash(transcript):
            unchanged.append(key)
            continue
        if not dry_run:
            prompts_dir.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(render_prompt(tpl, title=title, source_url=url,
                                                 stem=stem, transcript=transcript), encoding="utf-8")
        written.append(key)

    if write_index and not dry_run:
        write_index_md(kb_dir, rows)
    return {"written": written, "unchanged": unchanged, "missing": missing, "rows": rows}


def write_index_md(kb_dir: Path, rows: List[Dict[str, str]]) -> Path:
    """Write kb/INDEX.md. Links are relative to the kb/ folder."""
    def rel_to_kb(p: str) -> str:
        return p[3:] if p.startswith("kb/") else p
    done = sum(1 for r in rows if r["status"] == "ok")
    check = sum(1 for r in rows if r["status"] == "check")
    lines = [
        "# Knowledge base index",
        "",
        f"_Generated by `scripts/build_kb_pack.py` on "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. Do not edit by hand._",
        "",
        f"{len(rows)} sources - {done} summaries OK - {check} to check - {len(rows) - done - check} missing.",
        "",
        "How to use: open a **Prompt** file, paste all of it into your AI (Claude, Gemini, GPT, ...),",
        "then save the AI's answer as the file named in the prompt (`kb/highlights/<name>.md`).",
        "Summary column: OK = saved; CHECK = file exists but is very short or looks like a pasted",
        "command (open it and replace it with the AI's answer); - = not saved yet.",
        "",
        "| # | Title | Source | Transcript | Prompt | Summary |",
        "|---|-------|--------|------------|--------|---------|",
    ]
    for i, r in enumerate(sorted(rows, key=lambda r: r["title"].lower()), 1):
        title = r["title"].replace("|", "\\|")
        if r["status"] == "ok":
            summ = f"[OK]({_link(rel_to_kb(r['summary']))})"
        elif r["status"] == "check":
            summ = f"[CHECK]({_link(rel_to_kb(r['summary']))})"
        else:
            summ = "-"
        lines.append(f"| {i} | {title} | [link]({r['url']}) | [txt]({_link(rel_to_kb(r['full']))}) | "
                     f"[prompt]({_link(rel_to_kb(r['prompt']))}) | {summ} |")
    path = kb_dir / "kb" / "INDEX.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    paths = resolve_paths(cfg, args.kb_dir)
    kb_dir: Path = paths["kb_dir"]
    out = cfg.get("output", {})
    tpl_path = _anchor(args.template or out.get("prompt_template", "synth/manual_prompt.md"), ROOT)
    if not paths["manifest"].exists():
        print(f"manifest not found: {paths['manifest']}")
        return 1
    if not tpl_path.exists():
        print(f"prompt template not found: {tpl_path}")
        return 1
    data = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    repo_tpl_path = _anchor(out.get("prompt_template_repo", "synth/manual_prompt_repo.md"), ROOT)
    repo_template = repo_tpl_path.read_text(encoding="utf-8") if repo_tpl_path.exists() else None
    kind_templates = {}
    for kind, rel in (out.get("prompt_templates_by_kind") or {}).items():
        pth = _anchor(rel, ROOT)
        if pth.exists():
            kind_templates[kind] = pth.read_text(encoding="utf-8")
    res = build_pack(
        data, kb_dir=kb_dir, template=tpl_path.read_text(encoding="utf-8"), repo_template=repo_template, kind_templates=kind_templates,
        prompts_rel=out.get("prompts_dir", "kb/prompts"),
        highlights_rel=out.get("highlights_dir", "kb/highlights"),
        only_key=args.key, force=args.force,
        min_summary_chars=int(out.get("min_summary_chars", DEFAULT_MIN_SUMMARY_CHARS)), dry_run=args.dry_run, write_index=not args.no_index,
    )
    mode = "DRY RUN" if args.dry_run else "WRITE"
    print(f"== build_kb_pack ({mode}) ==  kb_dir={kb_dir}")
    print(f"  prompts written={len(res['written'])}  unchanged={len(res['unchanged'])}  "
          f"missing_transcript={len(res['missing'])}  summaries_saved="
          f"{sum(1 for r in res['rows'] if r['status'] == 'ok')}/{len(res['rows'])}  "
          f"to_check={sum(1 for r in res['rows'] if r['status'] == 'check')}")
    for r in res["rows"]:
        if r["status"] == "check":
            print(f"  ! CHECK summary: {r['summary']} (very short or looks like a pasted command)")
    for k in res["missing"]:
        print(f"  ? {k}: transcript file missing - skipped")
    if args.dry_run:
        print("(dry run: nothing written)")
    elif not args.no_index:
        print(f"  index: {kb_dir / 'kb' / 'INDEX.md'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="build_kb_pack",
                                description="Write ready-to-paste AI prompts per transcript + kb/INDEX.md (no AI used).")
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--kb-dir", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--key", default=None)
    p.add_argument("--template", default=None)
    p.add_argument("--no-index", action="store_true")
    return p


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
