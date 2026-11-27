"""migrate_manifest.py — one-time, reversible fix of `source_url` in an existing manifest.

Why (DESIGN/07-build-plan.md, PR-1):
    Before PR-1, orchestrate.py stored the WHOLE input line as `source_url`, e.g.
    "| 96 | 6/22/26 | 10:15 AM | https://www.youtube.com/watch?v=wEpw20UIfzI | co-work |".
    PR-1 makes new runs store a canonical URL. This script fixes entries written earlier.

What it does, per manifest entry:
    - Re-derives the canonical URL from the entry KEY with the same rule the pipeline uses
      (orchestrate.classify + orchestrate.canonical_url), so old and new entries match.
    - If `source_url` differs from the canonical URL:
        * sets `source_line` to the old `source_url` (only if `source_line` is not already
          present — the original text is never lost or overwritten), and
        * sets `source_url` to the canonical URL.
    - Leaves everything else untouched: content_hash, full_paths, status, ts.
    - Entries whose key is not a recognised source kind are reported and left unchanged.

Safety:
    - DRY RUN BY DEFAULT: prints the plan, writes nothing. `--apply` is required to change files.
    - Before writing, copies manifest.json into a timestamped backup folder
      (default: <kb_dir>/kb_backup_<UTC timestamp>/manifest.json, git-ignored).
    - Writes atomically (temp file + replace), same as Manifest.save().
    - Idempotent: a second run finds nothing to change.

No LLM. No network. Transcripts in kb/full/ are not touched.

Usage (run from chainaim-deep-research/):
    uv run scripts/migrate_manifest.py                      # dry run: show the plan
    uv run scripts/migrate_manifest.py --apply              # back up, then fix
    uv run scripts/migrate_manifest.py --apply --backup-dir D:/backups/kb1
    uv run scripts/migrate_manifest.py --kb-dir ../OTHER/output --apply

Flags (Rule 8 — all behaviour configurable, defaults sensible):
    --config PATH       config.yaml to read output.kb_dir / output.manifest from
                        (default: config.yaml next to scripts/)
    --kb-dir PATH       override output.kb_dir (same meaning as orchestrate.py --kb-dir)
    --dry-run           show the plan only (default behaviour; explicit flag for scripts)
    --apply             back up, then write the fixed manifest
    --backup-dir PATH   where to put the backup (default: <kb_dir>/kb_backup_<UTC ts>)

Exit codes: 0 success (including "nothing to change"), 1 manifest missing/unreadable.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent          # .../chainaim-deep-research/scripts
ROOT = HERE.parent                               # .../chainaim-deep-research
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

# Reuse the pipeline's own rules so the migration can never disagree with new runs.
from orchestrate import canonical_url, classify, load_config, resolve_paths  # noqa: E402

Change = Dict[str, str]  # {"key", "old_url", "new_url", "keep_line"}


def plan_migration(data: Dict[str, Dict[str, Any]]) -> Dict[str, List[Any]]:
    """Work out what would change, without changing anything.

    Args:
        data: the manifest's {key: entry} dict.

    Returns:
        {"changes": [Change...], "unchanged": [key...], "unknown": [key...]}
        - changes:   entries whose source_url is not canonical (to be fixed)
        - unchanged: entries already canonical (nothing to do)
        - unknown:   keys that classify() does not recognise (left as they are)
    """
    changes: List[Change] = []
    unchanged: List[str] = []
    unknown: List[str] = []
    for key, entry in data.items():
        kind, parsed_key = classify(key)
        if kind == "unknown" or parsed_key != key:
            unknown.append(key)
            continue
        new_url = canonical_url(kind, key)
        old_url = str(entry.get("source_url", ""))
        if old_url == new_url:
            unchanged.append(key)
            continue
        changes.append({
            "key": key,
            "old_url": old_url,
            "new_url": new_url,
            # Preserve the original text only if no source_line exists yet.
            "keep_line": "no" if "source_line" in entry else "yes",
        })
    return {"changes": changes, "unchanged": unchanged, "unknown": unknown}


def apply_migration(data: Dict[str, Dict[str, Any]], changes: List[Change]) -> Dict[str, Dict[str, Any]]:
    """Return a NEW manifest dict with the planned changes applied (input not mutated)."""
    out = json.loads(json.dumps(data))  # deep copy; manifest is plain JSON
    for ch in changes:
        entry = out[ch["key"]]
        if ch["keep_line"] == "yes":
            entry["source_line"] = ch["old_url"]
        entry["source_url"] = ch["new_url"]
    return out


def backup_manifest(manifest_path: Path, backup_dir: Path) -> Path:
    """Copy manifest.json into backup_dir (created if needed). Returns the backup path.

    Refuses to overwrite an existing backup file, so an earlier backup is never lost.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / manifest_path.name
    if target.exists():
        raise FileExistsError(f"backup already exists, refusing to overwrite: {target}")
    shutil.copy2(manifest_path, target)
    return target


def write_manifest(manifest_path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    """Atomic write (temp file + replace), identical format to Manifest.save()."""
    tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(manifest_path)


def default_backup_dir(kb_dir: Path, now: Optional[datetime] = None) -> Path:
    """<kb_dir>/kb_backup_<YYYYmmddTHHMMSSZ> — matches the `kb_backup_*/` .gitignore rule."""
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return kb_dir / f"kb_backup_{ts}"


def run(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    paths = resolve_paths(cfg, args.kb_dir)
    manifest_path: Path = paths["manifest"]

    if not manifest_path.exists():
        print(f"manifest not found: {manifest_path}")
        return 1
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"manifest unreadable: {manifest_path}: {exc}")
        return 1

    plan = plan_migration(data)
    changes = plan["changes"]
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"== migrate_manifest ({mode}) ==  manifest={manifest_path}")
    print(f"  entries={len(data)}  to_fix={len(changes)}  already_ok={len(plan['unchanged'])}  "
          f"unknown_kind={len(plan['unknown'])}")
    for ch in changes:
        print(f"  - {ch['key']}")
        print(f"      old source_url: {ch['old_url']}")
        print(f"      new source_url: {ch['new_url']}")
        print(f"      source_line   : {'set to old value' if ch['keep_line'] == 'yes' else 'already present, kept'}")
    for key in plan["unknown"]:
        print(f"  ? {key}: kind not recognised — left unchanged")

    if not changes:
        print("nothing to change.")
        return 0
    if not args.apply:
        print("\n(dry run: nothing written. Re-run with --apply to back up and fix.)")
        return 0

    backup_dir = Path(args.backup_dir) if args.backup_dir else default_backup_dir(paths["kb_dir"])
    backup = backup_manifest(manifest_path, backup_dir)
    print(f"\n  backup written: {backup}")
    write_manifest(manifest_path, apply_migration(data, changes))
    print(f"  manifest updated: {len(changes)} entr{'y' if len(changes) == 1 else 'ies'} fixed")
    print(f"  undo: copy {backup} back to {manifest_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="migrate_manifest",
        description="Fix pre-PR-1 manifest entries whose source_url holds the raw input line.",
    )
    p.add_argument("--config", default=str(ROOT / "config.yaml"), help="path to config.yaml")
    p.add_argument("--kb-dir", default=None, help="override output.kb_dir")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="show the plan only (default)")
    mode.add_argument("--apply", action="store_true", help="back up, then write the fixed manifest")
    p.add_argument("--backup-dir", default=None,
                   help="backup folder (default: <kb_dir>/kb_backup_<UTC timestamp>)")
    return p


if __name__ == "__main__":
    from console import utf8_console  # PR-13: UTF-8 output on any Windows code page
    utf8_console()
    raise SystemExit(run(build_parser().parse_args()))
