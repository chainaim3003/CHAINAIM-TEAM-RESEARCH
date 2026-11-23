"""run_evals.py — deterministic V1 eval harness (CI-friendly).

V1 has NO LLM, so V1 evals test the deterministic core (the parts that can silently
break): the Router/classify regex, ingest parsing, the dedupe gate's idempotency, and
the extract->manifest write path (offline, via a labeled test double).

Slots reserved for later: the V2 judge eval and V3 routing eval (LLM) plug in here as
separate suites keyed off model.provider; they are intentionally NOT run in V1.

Flags (Rule 8):
    --fixtures DIR   fixtures directory (default: ./fixtures next to this file)
    --verbose        print each case, not just the summary
    --only NAME      run only the named suite (classify|ingest|dedupe|extract|manifest)

Exit code: 0 if all pass, 1 otherwise (so CI can gate on it).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Tuple

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG / "scripts"))
sys.path.insert(0, str(PKG))

from orchestrate import classify, canonical_url  # noqa: E402
from migrate_manifest import (                  # noqa: E402
    apply_migration, backup_manifest, plan_migration,
)
from manifest import Manifest                # noqa: E402
from throttle import Throttle                # noqa: E402
from ingest.local_dir import collect_sources  # noqa: E402
from extract import youtube as yt            # noqa: E402

Result = Tuple[int, int, List[str]]  # (passed, total, failures)


def suite_classify(fixtures: Path, verbose: bool) -> Result:
    cases = json.loads((fixtures / "classify_cases.json").read_text(encoding="utf-8"))
    passed, fails = 0, []
    for c in cases:
        kind, key = classify(c["input"])
        ok = (kind == c["kind"]) and (key == c["key"])
        if ok:
            passed += 1
        else:
            fails.append(f"classify({c['input']!r}) -> ({kind},{key}) expected ({c['kind']},{c['key']})")
        if verbose:
            print(f"  [{'ok' if ok else 'XX'}] {c['input']!r} -> ({kind}, {key})")
    return passed, len(cases), fails


def suite_ingest(fixtures: Path, verbose: bool) -> Result:
    """Comments/blanks ignored; intra-run dedupe; order preserved."""
    fails: List[str] = []
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "sources.txt").write_text(
            "# a comment\n\nhttps://youtu.be/dQw4w9WgXcQ\n   \n"
            "https://youtu.be/dQw4w9WgXcQ\nplainID12345\n",
            encoding="utf-8",
        )
        items = collect_sources(source_list="sources.txt", source_dir=None, base_dir=d)
        urls = [i["url"] for i in items]
        expected = ["https://youtu.be/dQw4w9WgXcQ", "plainID12345"]
        if urls != expected:
            fails.append(f"ingest urls={urls} expected={expected}")
        if verbose:
            print(f"  ingest -> {urls}")
    total = 1
    return (1 if not fails else 0), total, fails


def _extract_one(td: Path, key: str, source: str) -> Tuple[bool, Manifest]:
    fake = PKG / "evals" / "fixtures" / "fake_transcript.py"
    m = Manifest(td / "manifest.json")
    throttle = Throttle(min_delay_s=0.0, jitter_s=0.0, backoff_factor=1.0, max_retries=1)
    ok, paths, info = yt.extract(
        key=key, source=source, transcript_script=str(fake),
        full_dir=td / "kb" / "full", kb_dir=td, formats=["txt", "json"], throttle=throttle, timestamps=False,
    )
    if ok:
        m.record(key, source, info, paths, status="extracted")
    return ok, m


def suite_extract(fixtures: Path, verbose: bool) -> Result:
    """Real extract path against the offline double: success writes files+manifest;
    failure path returns ok=False; re-extract is gated by manifest.seen (dedupe)."""
    fails: List[str] = []
    with tempfile.TemporaryDirectory() as tds:
        td = Path(tds)
        # success
        ok, m = _extract_one(td, "dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ")
        if not ok:
            fails.append("extract success-case returned ok=False")
        if not (td / "kb" / "full" / "dQw4w9WgXcQ.txt").exists():
            fails.append("extract did not write kb/full/<key>.txt")
        if not m.seen("dQw4w9WgXcQ"):
            fails.append("manifest.seen False after successful extract (dedupe would not trigger)")
        # failure path
        ok2, _, info = yt.extract(
            key="FAILTHIS123", source="FAILTHIS123",
            transcript_script=str(PKG / "evals" / "fixtures" / "fake_transcript.py"),
            full_dir=td / "kb" / "full", kb_dir=td, formats=["txt"],
            throttle=Throttle(min_delay_s=0.0, jitter_s=0.0, max_retries=1), timestamps=False,
        )
        if ok2:
            fails.append("extract failure-case returned ok=True (should be False)")
        if verbose:
            print(f"  extract ok={ok} seen={m.seen('dQw4w9WgXcQ')} fail_ok={ok2} fail_info={info!r}")
    return (1 if not fails else 0), 1, fails


def suite_dedupe(fixtures: Path, verbose: bool) -> Result:
    """Second extract of a seen key must be skipped by the gate (manifest.seen)."""
    fails: List[str] = []
    with tempfile.TemporaryDirectory() as tds:
        td = Path(tds)
        ok, m = _extract_one(td, "dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ")
        # reload manifest from disk (simulates a fresh run) and check the gate
        m2 = Manifest(td / "manifest.json")
        if not m2.seen("dQw4w9WgXcQ"):
            fails.append("dedupe: reloaded manifest does not report key as seen")
        # the gate logic in orchestrate is: seen and not force -> skip
        would_skip = m2.seen("dQw4w9WgXcQ")
        if not would_skip:
            fails.append("dedupe gate would NOT skip an already-extracted key")
        if verbose:
            print(f"  dedupe -> reloaded seen={m2.seen('dQw4w9WgXcQ')} would_skip={would_skip}")
    return (1 if not fails else 0), 1, fails


def suite_manifest(fixtures: Path, verbose: bool) -> Result:
    """PR-1: canonical source_url, source_line audit trail, and the one-time migration.

    Offline: temp directory only, no network, no real KB touched. 4 checks:
      1. canonical_url() gives the clean watch?v= link; unknown kinds raise.
      2. record(source_line=...) stores both fields; record() without it keeps the old
         schema (backward compatible) and the dedupe gate still works.
      3. plan/apply migration: a pre-PR-1 table-row entry is fixed, the original text is
         kept in source_line, a clean entry is left alone, input is not mutated, and a
         second plan finds nothing (idempotent).
      4. backup_manifest() copies the file and refuses to overwrite an existing backup.
    """
    fails: List[str] = []
    passed = 0
    vid = "wEpw20UIfzI"
    clean = f"https://www.youtube.com/watch?v={vid}"
    row = f"| 96 | 6/22/26 | 10:15 AM | https://www.youtube.com/watch?v={vid} | co-work |"

    # 1. canonical_url
    c1 = []
    kind, key = classify(row)
    if (kind, key) != ("youtube", vid):
        c1.append(f"classify(table row) -> ({kind},{key})")
    if canonical_url("youtube", vid) != clean:
        c1.append(f"canonical_url -> {canonical_url('youtube', vid)!r}")
    try:
        canonical_url("unknown", "x")
        c1.append("canonical_url('unknown') did not raise")
    except ValueError:
        pass
    passed += 0 if c1 else 1
    fails += [f"canonical: {m}" for m in c1]

    with tempfile.TemporaryDirectory() as tds:
        td = Path(tds)

        # 2. record with / without source_line
        c2 = []
        m = Manifest(td / "m2.json")
        m.record(vid, clean, "sha256-x", {"txt": f"kb/full/{vid}.txt"}, source_line=row)
        m.record("dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "sha256-y", {})
        reloaded = Manifest(td / "m2.json")
        e1, e2 = reloaded.get(vid) or {}, reloaded.get("dQw4w9WgXcQ") or {}
        if e1.get("source_url") != clean or e1.get("source_line") != row:
            c2.append(f"with source_line -> {e1}")
        if "source_line" in e2:
            c2.append("record() without source_line wrote a source_line field")
        if not (reloaded.seen(vid) and reloaded.seen("dQw4w9WgXcQ")):
            c2.append("dedupe gate: seen() False after record")
        passed += 0 if c2 else 1
        fails += [f"record: {m_}" for m_ in c2]

        # 3. migration plan / apply / idempotency
        c3 = []
        old_data = {
            vid: {"source_url": row, "content_hash": "h1", "full_paths": {"txt": "a"},
                  "status": "extracted", "ts": "t1"},
            "dQw4w9WgXcQ": {"source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                            "content_hash": "h2", "full_paths": {}, "status": "extracted", "ts": "t2"},
        }
        snapshot = json.dumps(old_data, sort_keys=True)
        plan = plan_migration(old_data)
        if [c["key"] for c in plan["changes"]] != [vid] or plan["unchanged"] != ["dQw4w9WgXcQ"]:
            c3.append(f"plan -> {plan}")
        new_data = apply_migration(old_data, plan["changes"])
        fixed = new_data[vid]
        if fixed.get("source_url") != clean or fixed.get("source_line") != row:
            c3.append(f"apply -> {fixed}")
        if fixed.get("content_hash") != "h1" or fixed.get("ts") != "t1" or fixed.get("full_paths") != {"txt": "a"}:
            c3.append("apply changed fields other than source_url/source_line")
        if json.dumps(old_data, sort_keys=True) != snapshot:
            c3.append("apply_migration mutated its input")
        if plan_migration(new_data)["changes"]:
            c3.append("second plan still finds changes (not idempotent)")
        passed += 0 if c3 else 1
        fails += [f"migrate: {m_}" for m_ in c3]

        # 4. backup
        c4 = []
        mp = td / "manifest.json"
        mp.write_text(json.dumps(old_data), encoding="utf-8")
        b = backup_manifest(mp, td / "kb_backup_test")
        if not b.exists() or b.read_text(encoding="utf-8") != mp.read_text(encoding="utf-8"):
            c4.append("backup missing or differs from source")
        try:
            backup_manifest(mp, td / "kb_backup_test")
            c4.append("second backup into same folder did not refuse")
        except FileExistsError:
            pass
        passed += 0 if c4 else 1
        fails += [f"backup: {m_}" for m_ in c4]

    if verbose:
        print(f"  manifest -> {passed}/4 checks ok")
    return passed, 4, fails


SUITES: Dict[str, Callable[[Path, bool], Result]] = {
    "classify": suite_classify,
    "ingest": suite_ingest,
    "extract": suite_extract,
    "dedupe": suite_dedupe,
    "manifest": suite_manifest,
}


def main() -> int:
    ap = argparse.ArgumentParser(prog="run_evals", description="ChainAIM V1 deterministic evals")
    ap.add_argument("--fixtures", default=str(HERE / "fixtures"))
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--only", choices=list(SUITES), default=None)
    args = ap.parse_args()

    fixtures = Path(args.fixtures)
    suites = {args.only: SUITES[args.only]} if args.only else SUITES

    total_pass, total_all, all_fail = 0, 0, []
    for name, fn in suites.items():
        print(f"[suite] {name}")
        p, t, fails = fn(fixtures, args.verbose)
        total_pass += p
        total_all += t
        all_fail += [f"({name}) {f}" for f in fails]
        print(f"  -> {p}/{t} passed")

    print(f"\n== EVAL SUMMARY ==  {total_pass}/{total_all} checks passed")
    if all_fail:
        print("FAILURES:")
        for f in all_fail:
            print(f"  - {f}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
