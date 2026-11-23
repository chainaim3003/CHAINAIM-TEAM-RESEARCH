"""rename_kb.py — rename existing KB files from "<id>.<ext>" to "<Title> [<id>].<ext>", reversibly.

Why (DESIGN/07-build-plan.md, PR-3):
    PR-2 names NEW extractions "<Title> [<id>]". Files extracted before PR-2 still have ID-only
    names. This script renames them with the SAME naming rule (scripts/naming.safe_stem), so old
    and new files look identical, and records the title/stem in the manifest.

What it does, per manifest entry with status "extracted":
    1. Title: uses the manifest's `title` if present; otherwise looks it up via YouTube oEmbed
       (extract/metadata.fetch_youtube_title), paced by --throttle-s. --no-lookup uses only
       titles already in the manifest. A failed lookup SKIPS the entry (keeps its ID name) —
       a title is never invented.
    2. New stem = safe_stem(title, key, max_len=output.max_stem_len).
    3. Each file in the entry's `full_paths` is planned "<old>.<ext>" -> "<stem>.<ext>" in the
       same folder. Skipped (reported) when: the old file is missing, the target already exists
       (never overwrites), or the file already has the target name.

Safety:
    - DRY RUN BY DEFAULT: prints the plan, changes nothing. `--apply` is required.
    - With --apply, BEFORE touching any file it:
        * backs up manifest.json to <kb_dir>/kb_backup_<UTC ts>/ (git-ignored), and
        * writes the rename log <kb_dir>/rename_log_<UTC ts>.json (old/new paths and the old
          manifest values for every entry) — this log is what --undo uses.
    - If any rename fails part-way, every rename already done in this run is reversed, the
      manifest is NOT written, and the exit code is 1.
    - The manifest is written once, atomically, after all renames succeed.
    - Idempotent: a second run finds nothing to rename.
    - `--undo <log>` reverses a previous --apply (also dry-run unless --apply is given).

No LLM. Network only for oEmbed title lookups (skipped with --no-lookup).
Transcript CONTENT is never read or changed — files are only renamed.

Usage (run from chainaim-deep-research/):
    uv run scripts/rename_kb.py                              # dry run: show the plan
    uv run scripts/rename_kb.py --apply                      # back up + log, then rename
    uv run scripts/rename_kb.py                              # re-run: "nothing to rename."
    uv run scripts/rename_kb.py --undo ../GENERAL-RESEARCH/output/rename_log_<ts>.json          # undo plan
    uv run scripts/rename_kb.py --undo ../GENERAL-RESEARCH/output/rename_log_<ts>.json --apply  # undo

Flags (Rule 8):
    --config PATH       config.yaml (default: next to scripts/)
    --kb-dir PATH       override output.kb_dir
    --dry-run           show the plan only (default)
    --apply             perform the renames (or the undo)
    --undo LOG          reverse the renames recorded in a rename log
    --throttle-s SEC    pause between oEmbed lookups (default 2.0; polite pacing)
    --no-lookup         never call oEmbed; rename only entries whose title is already known
    --backup-dir PATH   manifest backup folder (default: <kb_dir>/kb_backup_<UTC ts>)

Exit codes: 0 success / nothing to do; 1 error (missing manifest, failed rename, bad log).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent          # .../chainaim-deep-research/scripts
ROOT = HERE.parent                               # .../chainaim-deep-research
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from orchestrate import load_config, resolve_paths              # noqa: E402
from naming import DEFAULT_MAX_LEN, safe_stem                    # noqa: E402
from migrate_manifest import backup_manifest, write_manifest     # noqa: E402
from extract.metadata import fetch_youtube_title                 # noqa: E402

# get_title(key) -> (title or None, reason-if-None). Injectable for offline evals.
GetTitle = Callable[[str], Tuple[Optional[str], Optional[str]]]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def plan_renames(
    data: Dict[str, Dict[str, Any]],
    kb_dir: Path,
    *,
    get_title: Optional[GetTitle],
    max_len: int = DEFAULT_MAX_LEN,
) -> Dict[str, List[Dict[str, Any]]]:
    """Work out which files to rename, without changing anything.

    Args:
        data:      manifest {key: entry}.
        kb_dir:    folder that manifest `full_paths` are relative to.
        get_title: title lookup for entries without a manifest title; None = no lookups.
        max_len:   max stem length (output.max_stem_len).

    Returns:
        {"entries": [...], "skipped": [...]}
        entries: {"key","title","old_stem","new_stem","moves":[{"fmt","old","new"}],
                  "old_entry": {"full_paths","title"?,"stem"?}}   (paths relative to kb_dir)
        skipped: {"key","reason"}
    """
    entries: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    for key, entry in data.items():
        if entry.get("status") != "extracted":
            skipped.append({"key": key, "reason": f"status={entry.get('status')!r}"})
            continue
        full_paths: Dict[str, str] = entry.get("full_paths") or {}
        if not full_paths:
            skipped.append({"key": key, "reason": "no files recorded"})
            continue

        title = entry.get("title")
        if not title:
            if get_title is None:
                skipped.append({"key": key, "reason": "no title in manifest (--no-lookup)"})
                continue
            title, why = get_title(key)
            if not title:
                skipped.append({"key": key, "reason": f"title unavailable: {why}"})
                continue

        new_stem = safe_stem(title, key, max_len=max_len)
        moves: List[Dict[str, str]] = []
        problem: Optional[str] = None
        for fmt, rel in full_paths.items():
            old = Path(rel)
            new = old.with_name(f"{new_stem}{old.suffix}")
            if old.as_posix() == new.as_posix():
                continue  # already named correctly
            if not (kb_dir / old).exists():
                problem = f"file missing: {old.as_posix()}"
                break
            if (kb_dir / new).exists():
                problem = f"target already exists (not overwriting): {new.as_posix()}"
                break
            moves.append({"fmt": fmt, "old": old.as_posix(), "new": new.as_posix()})
        if problem:
            skipped.append({"key": key, "reason": problem})
            continue
        if not moves:
            continue  # nothing to do for this entry (already renamed)

        old_entry = {k: entry[k] for k in ("full_paths", "title", "stem") if k in entry}
        entries.append({
            "key": key, "title": title,
            "old_stem": Path(next(iter(full_paths.values()))).stem,
            "new_stem": new_stem, "moves": moves, "old_entry": old_entry,
        })
    return {"entries": entries, "skipped": skipped}


def _do_moves(kb_dir: Path, moves: List[Tuple[str, str]]) -> None:
    """Rename (src -> dst) pairs relative to kb_dir. On failure, reverse what was done and re-raise."""
    done: List[Tuple[Path, Path]] = []
    try:
        for src, dst in moves:
            s, d = kb_dir / src, kb_dir / dst
            if d.exists():
                raise FileExistsError(f"refusing to overwrite {d}")
            s.rename(d)
            done.append((s, d))
    except Exception:
        for s, d in reversed(done):
            try:
                d.rename(s)
            except OSError as exc:  # report, keep rolling back the rest
                print(f"  [ROLLBACK ERROR] could not move {d} back to {s}: {exc}")
        raise


def apply_renames(
    plan: Dict[str, List[Dict[str, Any]]],
    data: Dict[str, Dict[str, Any]],
    *,
    kb_dir: Path,
    manifest_path: Path,
    log_path: Path,
    backup_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    """Back up the manifest, write the rename log, rename files, then write the manifest.

    Returns the new manifest dict. Raises on failure (files already rolled back, manifest
    untouched; the log and backup remain for inspection).
    """
    backup_manifest(manifest_path, backup_dir)
    log = {
        "created": datetime.now(timezone.utc).isoformat(),
        "kb_dir": kb_dir.as_posix(),
        "manifest": manifest_path.name,
        "backup_dir": backup_dir.as_posix(),
        "entries": plan["entries"],
    }
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    pairs = [(m["old"], m["new"]) for e in plan["entries"] for m in e["moves"]]
    _do_moves(kb_dir, pairs)

    new_data = json.loads(json.dumps(data))
    for e in plan["entries"]:
        entry = new_data[e["key"]]
        fp = dict(entry.get("full_paths") or {})
        for m in e["moves"]:
            fp[m["fmt"]] = m["new"]
        entry["full_paths"] = fp
        entry["title"] = e["title"]
        entry["stem"] = e["new_stem"]
    write_manifest(manifest_path, new_data)
    return new_data


def plan_undo(log: Dict[str, Any], data: Dict[str, Dict[str, Any]], kb_dir: Path) -> Dict[str, List[Any]]:
    """From a rename log, plan the reverse moves. Entries whose files are not where the log says
    (already undone, moved again, or deleted) are skipped and reported."""
    entries, skipped = [], []
    for e in log.get("entries", []):
        bad = None
        for m in e["moves"]:
            if not (kb_dir / m["new"]).exists():
                bad = f"not found (already undone?): {m['new']}"
                break
            if (kb_dir / m["old"]).exists():
                bad = f"original name already in use: {m['old']}"
                break
        if bad or e["key"] not in data:
            skipped.append({"key": e["key"], "reason": bad or "key no longer in manifest"})
        else:
            entries.append(e)
    return {"entries": entries, "skipped": skipped}


def apply_undo(
    undo_plan: Dict[str, List[Any]],
    data: Dict[str, Dict[str, Any]],
    *,
    kb_dir: Path,
    manifest_path: Path,
    backup_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    """Reverse the renames and restore the old manifest values (full_paths, title, stem)."""
    backup_manifest(manifest_path, backup_dir)
    pairs = [(m["new"], m["old"]) for e in undo_plan["entries"] for m in e["moves"]]
    _do_moves(kb_dir, pairs)
    new_data = json.loads(json.dumps(data))
    for e in undo_plan["entries"]:
        entry = new_data[e["key"]]
        for k in ("full_paths", "title", "stem"):
            if k in e["old_entry"]:
                entry[k] = e["old_entry"][k]
            else:
                entry.pop(k, None)
    write_manifest(manifest_path, new_data)
    return new_data


def _print_skipped(skipped: List[Dict[str, str]]) -> None:
    for s in skipped:
        print(f"  ? {s['key']}: skipped — {s['reason']}")


def run(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    paths = resolve_paths(cfg, args.kb_dir)
    kb_dir: Path = paths["kb_dir"]
    manifest_path: Path = paths["manifest"]
    if not manifest_path.exists():
        print(f"manifest not found: {manifest_path}")
        return 1
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    stamp = utc_stamp()
    backup_dir = Path(args.backup_dir) if args.backup_dir else kb_dir / f"kb_backup_{stamp}"
    mode = "APPLY" if args.apply else "DRY RUN"

    # ---------------- undo ----------------
    if args.undo:
        log_path = Path(args.undo)
        try:
            log = json.loads(log_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"cannot read rename log {log_path}: {exc}")
            return 1
        up = plan_undo(log, data, kb_dir)
        print(f"== rename_kb UNDO ({mode}) ==  log={log_path}")
        print(f"  to_restore={len(up['entries'])}  skipped={len(up['skipped'])}")
        for e in up["entries"]:
            for m in e["moves"]:
                print(f"  - {e['key']}: {Path(m['new']).name}  ->  {Path(m['old']).name}")
        _print_skipped(up["skipped"])
        if not up["entries"]:
            print("nothing to undo.")
            return 0
        if not args.apply:
            print("\n(dry run: nothing changed. Add --apply to undo.)")
            return 0
        try:
            apply_undo(up, data, kb_dir=kb_dir, manifest_path=manifest_path, backup_dir=backup_dir)
        except Exception as exc:  # noqa: BLE001 — report any failure, files already rolled back
            print(f"\nUNDO FAILED: {exc}\n  files rolled back; manifest unchanged.")
            return 1
        print(f"\n  manifest backup: {backup_dir / manifest_path.name}")
        print(f"  restored {len(up['entries'])} entr{'y' if len(up['entries']) == 1 else 'ies'}")
        return 0

    # ---------------- rename ----------------
    get_title: Optional[GetTitle] = None
    if not args.no_lookup:
        tl = cfg.get("youtube", {}).get("title_lookup", {})
        state = {"calls": 0}

        def get_title(key: str) -> Tuple[Optional[str], Optional[str]]:  # noqa: F811
            if state["calls"]:
                time.sleep(max(0.0, args.throttle_s))  # polite pacing between oEmbed calls
            state["calls"] += 1
            return fetch_youtube_title(
                key,
                timeout_s=float(tl.get("timeout_s", 10.0)),
                retries=int(tl.get("retries", 2)),
                backoff_s=float(tl.get("backoff_s", 1.0)),
            )

    max_len = int(cfg.get("output", {}).get("max_stem_len", DEFAULT_MAX_LEN))
    print(f"== rename_kb ({mode}) ==  kb_dir={kb_dir}")
    plan = plan_renames(data, kb_dir, get_title=get_title, max_len=max_len)
    n_files = sum(len(e["moves"]) for e in plan["entries"])
    print(f"  entries={len(data)}  to_rename={len(plan['entries'])} ({n_files} files)  "
          f"skipped={len(plan['skipped'])}")
    for e in plan["entries"]:
        for m in e["moves"]:
            print(f"  - {Path(m['old']).name}  ->  {Path(m['new']).name}")
    _print_skipped(plan["skipped"])

    if not plan["entries"]:
        print("nothing to rename.")
        return 0
    if not args.apply:
        print("\n(dry run: nothing changed. Re-run with --apply to back up, log and rename.)")
        return 0

    log_path = kb_dir / f"rename_log_{stamp}.json"
    try:
        apply_renames(plan, data, kb_dir=kb_dir, manifest_path=manifest_path,
                      log_path=log_path, backup_dir=backup_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"\nRENAME FAILED: {exc}\n  renames rolled back; manifest unchanged. Log kept: {log_path}")
        return 1
    print(f"\n  manifest backup: {backup_dir / manifest_path.name}")
    print(f"  rename log     : {log_path}")
    print(f"  renamed {n_files} file(s) in {len(plan['entries'])} entr{'y' if len(plan['entries']) == 1 else 'ies'}")
    print(f"  undo: uv run scripts/rename_kb.py --undo \"{log_path}\" --apply")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rename_kb",
                                description="Rename '<id>' KB files to '<Title> [<id>]' (reversible).")
    p.add_argument("--config", default=str(ROOT / "config.yaml"), help="path to config.yaml")
    p.add_argument("--kb-dir", default=None, help="override output.kb_dir")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="show the plan only (default)")
    mode.add_argument("--apply", action="store_true", help="perform the renames (or the undo)")
    p.add_argument("--undo", default=None, metavar="LOG", help="reverse the renames in a rename log")
    p.add_argument("--throttle-s", type=float, default=2.0, help="pause between oEmbed lookups (default 2.0)")
    p.add_argument("--no-lookup", action="store_true", help="do not call oEmbed; use manifest titles only")
    p.add_argument("--backup-dir", default=None, help="manifest backup folder (default: <kb_dir>/kb_backup_<ts>)")
    return p


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
