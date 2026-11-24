"""run_evals.py — deterministic V1 eval harness (CI-friendly).

V1 has NO LLM, so V1 evals test the deterministic core (the parts that can silently
break): the Router/classify regex, ingest parsing, the dedupe gate's idempotency, and
the extract->manifest write path (offline, via a labeled test double).

Slots reserved for later: the V2 judge eval and V3 routing eval (LLM) plug in here as
separate suites keyed off model.provider; they are intentionally NOT run in V1.

Flags (Rule 8):
    --fixtures DIR   fixtures directory (default: ./fixtures next to this file)
    --verbose        print each case, not just the summary
    --only NAME      run only the named suite (classify|ingest|dedupe|extract|manifest|naming|rename|pack|github|digest|papers)

Exit code: 0 if all pass, 1 otherwise (so CI can gate on it).
"""

from __future__ import annotations

import argparse
import json
import os
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
from extract.metadata import HttpStatusError, fetch_youtube_title, oembed_url  # noqa: E402
from naming import safe_stem                 # noqa: E402
from build_kb_pack import build_pack          # noqa: E402
from envfile import load_env_file             # noqa: E402
from digest import build_digest               # noqa: E402
from extract import arxiv as axx              # noqa: E402
from extract import web as wbx                # noqa: E402
from extract import github as ghx             # noqa: E402
from rename_kb import apply_renames, apply_undo, plan_renames, plan_undo  # noqa: E402

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


def suite_naming(fixtures: Path, verbose: bool) -> Result:
    """PR-2: "<Title> [<key>]" file names and the oEmbed title lookup.

    Offline: the title lookup uses an injected fake http_get (labelled test double) — no
    network. 6 checks:
      1. forbidden Windows characters removed, spaces collapsed, key suffix added.
      2. missing / empty / all-invalid title -> key-only stem (pre-PR-2 name).
      3. long title cut to max_len, never ending in a space or dot before " [key]".
      4. unicode/emoji kept (NFC), control chars removed, trailing dots stripped.
      5. title lookup: success -> title; HTTP 404 -> None with NO retry; network error ->
         None after 1 + retries attempts; oembed_url is well-formed.
      6. extract() writes kb/full/<stem>.txt and the manifest path points to it.
    """
    fails: List[str] = []
    passed = 0
    key = "8D8ewFBJfFM"

    def check(n: int, cond_msgs: List[str]) -> None:
        nonlocal passed
        if cond_msgs:
            fails.extend(f"naming {n}: {m}" for m in cond_msgs)
        else:
            passed += 1

    # 1
    got = safe_stem('Agents: How/Why <Now>?  "Really" | 2026*', key)
    check(1, [] if got == f"Agents How Why Now Really 2026 [{key}]" else [f"got {got!r}"])
    # 2
    c2 = [f"{t!r} -> {safe_stem(t, key)!r}" for t in (None, "", "   ", '<>:"/\\|?*', "...")
          if safe_stem(t, key) != key]
    check(2, c2)
    # 3
    long_t = ("Word " * 80) + "end."
    st = safe_stem(long_t, key, max_len=60)
    c3 = []
    if len(st) > 60:
        c3.append(f"len {len(st)} > 60")
    if not st.endswith(f" [{key}]"):
        c3.append(f"missing key suffix: {st!r}")
    if st[: -len(f" [{key}]")].endswith((" ", ".")):
        c3.append(f"title part ends with space/dot: {st!r}")
    try:
        safe_stem("x", key, max_len=5)
        c3.append("max_len too small did not raise")
    except ValueError:
        pass
    check(3, c3)
    # 4
    st4 = safe_stem("Cafe\u0301 \U0001F680 launch\x07 notes...", key)
    check(4, [] if st4 == f"Caf\u00e9 \U0001F680 launch notes [{key}]" else [f"got {st4!r}"])

    # 5 — fake http_get (test double)
    c5 = []
    calls = {"n": 0}

    def ok_get(url: str, timeout: float) -> bytes:
        return b'{"title": "  Building Multi-Agent Systems  ", "author_name": "x"}'

    def nf_get(url: str, timeout: float) -> bytes:
        calls["n"] += 1
        raise HttpStatusError(404, "Not Found")

    def net_get(url: str, timeout: float) -> bytes:
        calls["n"] += 1
        raise OSError("connection reset")

    noop = lambda _s: None  # noqa: E731
    t, why = fetch_youtube_title(key, http_get=ok_get, sleep=noop)
    if t != "Building Multi-Agent Systems" or why is not None:
        c5.append(f"success -> {(t, why)}")
    calls["n"] = 0
    t, why = fetch_youtube_title(key, retries=3, http_get=nf_get, sleep=noop)
    if t is not None or calls["n"] != 1:
        c5.append(f"404 -> title={t!r} calls={calls['n']} (expected None, 1 call)")
    calls["n"] = 0
    t, why = fetch_youtube_title(key, retries=2, http_get=net_get, sleep=noop)
    if t is not None or calls["n"] != 3 or "after 3 attempts" not in (why or ""):
        c5.append(f"network -> title={t!r} calls={calls['n']} why={why!r}")
    if oembed_url(key) != ("https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com"
                           f"%2Fwatch%3Fv%3D{key}&format=json"):
        c5.append(f"oembed_url -> {oembed_url(key)}")
    check(5, c5)

    # 6 — real extract path with a stem, offline transcript double
    c6 = []
    with tempfile.TemporaryDirectory() as tds:
        td = Path(tds)
        stem = safe_stem("Building Multi-Agent Systems", "dQw4w9WgXcQ")
        ok, paths, info = yt.extract(
            key="dQw4w9WgXcQ", source="https://youtu.be/dQw4w9WgXcQ",
            transcript_script=str(PKG / "evals" / "fixtures" / "fake_transcript.py"),
            full_dir=td / "kb" / "full", kb_dir=td, formats=["txt"],
            throttle=Throttle(min_delay_s=0.0, jitter_s=0.0, max_retries=1), timestamps=False,
            stem=stem,
        )
        expect = td / "kb" / "full" / f"{stem}.txt"
        if not ok or not expect.exists():
            c6.append(f"file not written at {expect.name} (ok={ok})")
        if paths.get("txt") != f"kb/full/{stem}.txt":
            c6.append(f"manifest path -> {paths.get('txt')!r}")
    check(6, c6)

    if verbose:
        print(f"  naming -> {passed}/6 checks ok; example stem: {safe_stem('Agents: How/Why?', key)!r}")
    return passed, 6, fails


def suite_rename(fixtures: Path, verbose: bool) -> Result:
    """PR-3: rename "<id>.txt" -> "<Title> [<id>].txt" with log, idempotency and undo.

    Offline: temp KB, injected fake title lookup (labelled test double), no network. 5 checks:
      1. plan: renames the entry whose title resolves; skips a failed lookup, a missing file,
         and an existing target (never overwrites); uses a manifest title without lookup.
      2. apply: files moved, content unchanged, manifest full_paths/title/stem updated,
         backup + rename log written.
      3. idempotent: a second plan finds nothing to rename.
      4. undo: files back to original names, manifest restored exactly (title/stem removed).
      5. rollback: a failing rename part-way reverses earlier renames, manifest untouched.
    """
    fails: List[str] = []
    passed = 0

    def check(n: int, msgs: List[str]) -> None:
        nonlocal passed
        if msgs:
            fails.extend(f"rename {n}: {m}" for m in msgs)
        else:
            passed += 1

    titles = {"AAAAAAAAAAA": "Agents: Part 1", "BBBBBBBBBBB": None, "CCCCCCCCCCC": "Clash",
              "DDDDDDDDDDD": "Ghost"}
    lookups: List[str] = []

    def fake_get_title(key: str):  # test double for fetch_youtube_title
        lookups.append(key)
        t = titles.get(key)
        return (t, None) if t else (None, "HTTP 404")

    with tempfile.TemporaryDirectory() as tds:
        kb = Path(tds)
        full = kb / "kb" / "full"
        full.mkdir(parents=True)
        for k in ("AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC", "EEEEEEEEEEE"):
            (full / f"{k}.txt").write_text(f"transcript {k}", encoding="utf-8")
        (full / "Clash [CCCCCCCCCCC].txt").write_text("someone else's file", encoding="utf-8")

        def ent(k, **extra):
            e = {"source_url": f"https://www.youtube.com/watch?v={k}", "content_hash": "h",
                 "full_paths": {"txt": f"kb/full/{k}.txt"}, "status": "extracted", "ts": "t"}
            e.update(extra)
            return e
        data = {k: ent(k) for k in ("AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC", "DDDDDDDDDDD")}
        data["EEEEEEEEEEE"] = ent("EEEEEEEEEEE", title="Known Title")
        mp = kb / "manifest.json"
        mp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        original = json.loads(json.dumps(data))

        # 1. plan
        plan = plan_renames(data, kb, get_title=fake_get_title, max_len=100)
        keys = sorted(e["key"] for e in plan["entries"])
        reasons = {x["key"]: x["reason"] for x in plan["skipped"]}
        c1 = []
        if keys != ["AAAAAAAAAAA", "EEEEEEEEEEE"]:
            c1.append(f"to_rename={keys}")
        if "unavailable" not in reasons.get("BBBBBBBBBBB", ""):
            c1.append(f"B reason={reasons.get('BBBBBBBBBBB')}")
        if "already exists" not in reasons.get("CCCCCCCCCCC", ""):
            c1.append(f"C reason={reasons.get('CCCCCCCCCCC')}")
        if "missing" not in reasons.get("DDDDDDDDDDD", ""):
            c1.append(f"D reason={reasons.get('DDDDDDDDDDD')}")
        if "EEEEEEEEEEE" in lookups:
            c1.append("looked up a title already in the manifest")
        check(1, c1)

        # 2. apply
        c2 = []
        log_path = kb / "rename_log_test.json"
        new_data = apply_renames(plan, data, kb_dir=kb, manifest_path=mp, log_path=log_path,
                                 backup_dir=kb / "kb_backup_test")
        a_new = full / "Agents Part 1 [AAAAAAAAAAA].txt"
        if not a_new.exists() or (full / "AAAAAAAAAAA.txt").exists():
            c2.append("A not moved")
        elif a_new.read_text(encoding="utf-8") != "transcript AAAAAAAAAAA":
            c2.append("A content changed")
        on_disk = json.loads(mp.read_text(encoding="utf-8"))
        a = on_disk["AAAAAAAAAAA"]
        if a.get("full_paths") != {"txt": "kb/full/Agents Part 1 [AAAAAAAAAAA].txt"} \
                or a.get("title") != "Agents: Part 1" or a.get("stem") != "Agents Part 1 [AAAAAAAAAAA]":
            c2.append(f"manifest A -> {a}")
        if on_disk["BBBBBBBBBBB"] != original["BBBBBBBBBBB"]:
            c2.append("skipped entry B was modified")
        if not log_path.exists() or not (kb / "kb_backup_test" / "manifest.json").exists():
            c2.append("rename log or backup missing")
        if (full / "Clash [CCCCCCCCCCC].txt").read_text(encoding="utf-8") != "someone else's file":
            c2.append("existing target was overwritten")
        check(2, c2)

        # 3. idempotent
        again = plan_renames(new_data, kb, get_title=fake_get_title, max_len=100)
        check(3, [] if not again["entries"] else [f"second plan -> {[e['key'] for e in again['entries']]}"])

        # 4. undo
        c4 = []
        log = json.loads(log_path.read_text(encoding="utf-8"))
        up = plan_undo(log, new_data, kb)
        restored = apply_undo(up, new_data, kb_dir=kb, manifest_path=mp, backup_dir=kb / "kb_backup_undo")
        if not (full / "AAAAAAAAAAA.txt").exists() or a_new.exists():
            c4.append("A not moved back")
        if restored != original or json.loads(mp.read_text(encoding="utf-8")) != original:
            c4.append("manifest not restored exactly")
        if plan_undo(log, restored, kb)["entries"]:
            c4.append("second undo still finds work")
        check(4, c4)

        # 5. rollback on failure part-way
        c5 = []
        plan2 = plan_renames(original, kb, get_title=fake_get_title, max_len=100)
        # sabotage: make the 2nd target appear after planning
        second = plan2["entries"][1]["moves"][0]["new"]
        (kb / second).write_text("appeared later", encoding="utf-8")
        before = mp.read_text(encoding="utf-8")
        try:
            apply_renames(plan2, original, kb_dir=kb, manifest_path=mp,
                          log_path=kb / "rename_log_fail.json", backup_dir=kb / "kb_backup_fail")
            c5.append("apply did not raise on conflict")
        except FileExistsError:
            pass
        if not (full / "AAAAAAAAAAA.txt").exists():
            c5.append("first rename not rolled back")
        if mp.read_text(encoding="utf-8") != before:
            c5.append("manifest changed after failed apply")
        check(5, c5)

    if verbose:
        print(f"  rename -> {passed}/5 checks ok")
    return passed, 5, fails


def suite_pack(fixtures: Path, verbose: bool) -> Result:
    """Way 1 (manual AI): ready-to-paste prompt per transcript + kb/INDEX.md. No AI, offline.

    4 checks:
      1. prompt contains the transcript VERBATIM (incl. braces/unicode), title, source URL and
         the save-as path; uses the real synth/manual_prompt.md template.
      2. INDEX.md lists every entry, marks a saved summary, uses <...> links for names with spaces.
      3. idempotent: re-run writes nothing; a changed transcript is rewritten; --force rewrites all.
      4. an entry whose transcript file is missing is reported, not fatal; dry run writes nothing.
    """
    fails: List[str] = []
    passed = 0
    template = (PKG / "synth" / "manual_prompt.md").read_text(encoding="utf-8")

    def check(n: int, msgs: List[str]) -> None:
        nonlocal passed
        if msgs:
            fails.extend(f"pack {n}: {m}" for m in msgs)
        else:
            passed += 1

    with tempfile.TemporaryDirectory() as tds:
        kb = Path(tds)
        full = kb / "kb" / "full"
        full.mkdir(parents=True)
        s1 = "Design Claude Code [AAAAAAAAAAA]"
        t1 = "Let's design {an} agent \u2014 caf\u00e9 [music]\n>> next speaker"
        (full / f"{s1}.txt").write_text(t1, encoding="utf-8")
        (full / "BBBBBBBBBBB.txt").write_text("plain transcript", encoding="utf-8")
        (kb / "kb" / "highlights").mkdir(parents=True)
        (kb / "kb" / "highlights" / "BBBBBBBBBBB.md").write_text("# my summary", encoding="utf-8")
        data = {
            "AAAAAAAAAAA": {"source_url": "https://www.youtube.com/watch?v=AAAAAAAAAAA", "status": "extracted",
                            "full_paths": {"txt": f"kb/full/{s1}.txt"}, "title": "Design: Claude Code", "stem": s1},
            "BBBBBBBBBBB": {"source_url": "https://www.youtube.com/watch?v=BBBBBBBBBBB", "status": "extracted",
                            "full_paths": {"txt": "kb/full/BBBBBBBBBBB.txt"}},
            "CCCCCCCCCCC": {"source_url": "x", "status": "extracted", "full_paths": {"txt": "kb/full/gone.txt"}},
        }

        # 4 (dry run first: must write nothing)
        c4 = []
        r0 = build_pack(data, kb_dir=kb, template=template, dry_run=True)
        if (kb / "kb" / "prompts").exists() or (kb / "kb" / "INDEX.md").exists():
            c4.append("dry run wrote files")
        if r0["missing"] != ["CCCCCCCCCCC"]:
            c4.append(f"missing={r0['missing']}")

        r1 = build_pack(data, kb_dir=kb, template=template)
        # 1
        c1 = []
        pf = kb / "kb" / "prompts" / f"{s1}.prompt.md"
        txt = pf.read_text(encoding="utf-8") if pf.exists() else ""
        for needle in (t1, "Design: Claude Code", "https://www.youtube.com/watch?v=AAAAAAAAAAA",
                       f"kb/highlights/{s1}.md", "--- TRANSCRIPT START ---"):
            if needle not in txt:
                c1.append(f"prompt missing {needle[:40]!r}")
        if "{{" in txt.split("--- TRANSCRIPT START ---")[0]:
            c1.append("unfilled placeholder in prompt header")
        check(1, c1)
        # 2
        c2 = []
        idx = (kb / "kb" / "INDEX.md").read_text(encoding="utf-8")
        if "2 transcripts \u00b7 1 summaries saved." not in idx:
            c2.append("counts line wrong")
        if f"[prompt](<prompts/{s1}.prompt.md>)" not in idx or "[\u2705 summary](<highlights/BBBBBBBBBBB.md>)" not in idx:
            c2.append("links wrong")
        if "Design: Claude Code" not in idx:
            c2.append("title missing")
        check(2, c2)
        # 3
        c3 = []
        r2 = build_pack(data, kb_dir=kb, template=template)
        if r2["written"]:
            c3.append(f"re-run wrote {r2['written']}")
        (full / "BBBBBBBBBBB.txt").write_text("plain transcript v2", encoding="utf-8")
        r3 = build_pack(data, kb_dir=kb, template=template)
        if r3["written"] != ["BBBBBBBBBBB"]:
            c3.append(f"changed transcript -> written={r3['written']}")
        r4 = build_pack(data, kb_dir=kb, template=template, force=True)
        if sorted(r4["written"]) != ["AAAAAAAAAAA", "BBBBBBBBBBB"]:
            c3.append(f"--force -> written={r4['written']}")
        check(3, c3)
        if r1["missing"] != ["CCCCCCCCCCC"]:
            c4.append("missing entry not reported on write run")
        check(4, c4)

    if verbose:
        print(f"  pack -> {passed}/4 checks ok")
    return passed, 4, fails


def suite_github(fixtures: Path, verbose: bool) -> Result:
    """PR-5: GitHub repo/account -> text, with a labelled OFFLINE fake GitHub API (no network).

    6 checks:
      1. extract_repo renders facts, folder tree, README and key files; states every cut
         (tree cap, oversized file, total-bytes cap).
      2. errors: missing repo -> GitHubError(404); low rate limit -> GitHubRateLimit raised
         BEFORE the next request is sent.
      3. account listing: forks/archived excluded by default, pagination, max_repos cap.
      4. token goes only in the Authorization header (never in the URL); none sent without it.
      5. build_kb_pack uses the repo template for kind "github_repo".
      6. .env loader: sets missing vars, never overrides existing ones, skips empty values.
    """
    fails: List[str] = []
    passed = 0

    def check(n: int, msgs: List[str]) -> None:
        nonlocal passed
        if msgs:
            fails.extend(f"github {n}: {m}" for m in msgs)
        else:
            passed += 1

    seen_requests: List[Tuple[str, Dict[str, str]]] = []
    tree = [{"path": "README.md", "type": "blob", "size": 50},
            {"path": "src", "type": "tree"},
            {"path": "src/app.py", "type": "blob", "size": 10},
            {"path": "pyproject.toml", "type": "blob", "size": 30},
            {"path": "package.json", "type": "blob", "size": 999999},
            {"path": "docs/guide.md", "type": "blob", "size": 40}]

    def fake_get(url, headers, timeout):  # TEST DOUBLE of api.github.com
        seen_requests.append((url, headers))
        h = {"x-ratelimit-remaining": "4999"}
        path = url.replace(ghx.API, "")
        if path == "/repos/o/r":
            return 200, h, json.dumps({"default_branch": "main", "html_url": "https://github.com/o/r",
                                       "description": "Demo repo", "language": "Python",
                                       "stargazers_count": 7, "topics": ["agents"],
                                       "license": {"spdx_id": "MIT"}}).encode()
        if path.startswith("/repos/o/r/git/trees/main"):
            return 200, h, json.dumps({"sha": "abc123def4567890", "tree": tree, "truncated": False}).encode()
        if path == "/repos/o/r/readme":
            return 200, h, b"# Demo\nRun: uv run app"
        if path.startswith("/repos/o/r/contents/pyproject.toml"):
            return 200, h, b"[project]\nname='demo'"
        if path.startswith("/repos/o/r/contents/docs/guide.md"):
            return 200, h, b"Guide\n```bash\nuv run x\n```\n## Inner heading"
        if path.startswith("/users/acct/repos"):
            page = int(path.split("&page=")[1])
            if page == 1:
                data = [{"full_name": f"acct/r{i}", "fork": i % 10 == 0, "archived": i % 15 == 0} for i in range(100)]
            else:
                data = [{"full_name": "acct/last", "fork": False, "archived": False}]
            return 200, h, json.dumps(data).encode()
        return 404, h, b'{"message":"Not Found"}'

    noop = lambda _s: None  # noqa: E731
    client = ghx.GitHubClient(token=None, http_get=fake_get, sleep=noop, min_delay_s=0)

    # 1
    c1 = []
    md, meta = ghx.extract_repo(client, "o/r", max_tree_entries=3, max_files=5, max_file_bytes=1000,
                                max_total_bytes=10_000)
    for needle in ("# o/r", "Demo repo", "License: MIT", "Topics: agents", "Commit: abc123def456",
                   "## Folder structure (6 entries)", "3 more entries not shown", "# Demo",
                   "### pyproject.toml", "[project]", "### docs/guide.md",
                   "package.json skipped (999,999 bytes"):
        if needle not in md:
            c1.append(f"missing {needle!r}")
    if meta.get("sha") != "abc123def4567890":
        c1.append(f"meta={meta}")
    if "````md\nGuide" not in md:
        c1.append("nested ``` in a key file not protected by a longer fence")
    md2, _ = ghx.extract_repo(client, "o/r", max_total_bytes=30)
    if "max_total_bytes 30 reached" not in md2:
        c1.append("total-bytes cut not stated")
    check(1, c1)

    # 2
    c2 = []
    try:
        ghx.extract_repo(client, "o/missing")
        c2.append("missing repo did not raise")
    except ghx.GitHubError as exc:
        if exc.status != 404:
            c2.append(f"status={exc.status}")
    low = ghx.GitHubClient(http_get=fake_get, sleep=noop, min_delay_s=0, min_remaining=5)
    low.remaining = 3
    before = len(seen_requests)
    try:
        low.get("/repos/o/r")
        c2.append("low rate limit did not raise")
    except ghx.GitHubRateLimit:
        if len(seen_requests) != before:
            c2.append("request was sent despite low rate limit")
    check(2, c2)

    # 3
    names = ghx.list_account_repos(client, "acct", max_repos=200)
    c3 = []
    if any(n in names for n in ("acct/r0", "acct/r10", "acct/r15")):
        c3.append("fork/archived not excluded")
    if names[-1] != "acct/last":
        c3.append("second page not fetched")
    if len(ghx.list_account_repos(client, "acct", max_repos=5)) != 5:
        c3.append("max_repos cap not applied")
    check(3, c3)

    # 4
    c4 = []
    if any("Authorization" in h for _u, h in seen_requests):
        c4.append("Authorization header sent without a token")
    tok = ghx.GitHubClient(token="test-token-not-real", http_get=fake_get, sleep=noop, min_delay_s=0)
    tok.get("/repos/o/r")
    url, hdr = seen_requests[-1]
    if hdr.get("Authorization") != "Bearer test-token-not-real" or "test-token" in url:
        c4.append("token not in header only")
    check(4, c4)

    # 5
    c5 = []
    with tempfile.TemporaryDirectory() as tds:
        kb = Path(tds)
        (kb / "kb" / "full").mkdir(parents=True)
        (kb / "kb" / "full" / "o__r [github].md").write_text(md, encoding="utf-8")
        data = {"gh:o/r": {"source_url": "https://github.com/o/r", "status": "extracted", "kind": "github_repo",
                           "title": "o/r", "stem": "o__r [github]", "full_paths": {"md": "kb/full/o__r [github].md"}}}
        res = build_pack(data, kb_dir=kb, template="VIDEO {{TRANSCRIPT}}",
                         repo_template=(PKG / "synth" / "manual_prompt_repo.md").read_text(encoding="utf-8"))
        pr = (kb / "kb" / "prompts" / "o__r [github].prompt.md").read_text(encoding="utf-8")
        if "Summarise this GitHub repository" not in pr or "VIDEO" in pr or "### pyproject.toml" not in pr:
            c5.append("repo template not used or extract missing")
        if res["written"] != ["gh:o/r"]:
            c5.append(f"written={res['written']}")
    check(5, c5)

    # 6
    c6 = []
    with tempfile.TemporaryDirectory() as tds:
        envp = Path(tds) / ".env"
        envp.write_text("# c\nCDR_T1='abc'\nCDR_T2=\nCDR_T3=new\n", encoding="utf-8")
        os.environ["CDR_T3"] = "old"
        try:
            names_set = load_env_file(envp)
            if os.environ.get("CDR_T1") != "abc" or "CDR_T2" in os.environ or os.environ.get("CDR_T3") != "old":
                c6.append(f"env state wrong, set={names_set}")
        finally:
            for k in ("CDR_T1", "CDR_T2", "CDR_T3"):
                os.environ.pop(k, None)
    check(6, c6)

    if verbose:
        print(f"  github -> {passed}/6 checks ok")
    return passed, 6, fails


def suite_digest(fixtures: Path, verbose: bool) -> Result:
    """PR-6: weekly digest (no AI). 3 checks:
      1. only entries extracted inside the window are listed (old and future ones excluded).
      2. summary status and GitHub/YouTube type are correct; links use <...> targets.
      3. an empty window says "Nothing new" and still has the week heading.
    """
    from datetime import datetime, timezone
    fails: List[str] = []
    passed = 0
    now = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tds:
        kb = Path(tds)
        (kb / "kb" / "highlights").mkdir(parents=True)
        (kb / "kb" / "highlights" / "New Video [AAAAAAAAAAA].md").write_text("sum", encoding="utf-8")
        data = {
            "AAAAAAAAAAA": {"status": "extracted", "ts": "2026-11-22T10:00:00+00:00", "title": "New Video",
                            "stem": "New Video [AAAAAAAAAAA]", "source_url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
                            "full_paths": {"txt": "kb/full/New Video [AAAAAAAAAAA].txt"}},
            "gh:o/r": {"status": "extracted", "ts": "2026-11-20T10:00:00+00:00", "title": "o/r", "kind": "github_repo",
                       "stem": "o__r [github]", "source_url": "https://github.com/o/r",
                       "full_paths": {"md": "kb/full/o__r [github].md"}},
            "OLDOLDOLDOL": {"status": "extracted", "ts": "2026-10-01T10:00:00+00:00", "title": "Old",
                            "full_paths": {"txt": "kb/full/OLDOLDOLDOL.txt"}},
        }
        md = build_digest(data, kb, days=7, now=now)
        c1 = [] if ("New Video" in md and "o/r" in md and "Old" not in md) else ["window filter wrong"]
        c2 = []
        if "| 2026-11-22 | YouTube | New Video |" not in md or "| GitHub | o/r |" not in md:
            c2.append("type/title row wrong")
        if "2 item(s), 1 with a saved summary, 1 still to summarise" not in md:
            c2.append("counts wrong")
        if "[file](<full/New Video [AAAAAAAAAAA].txt>)" not in md:
            c2.append("link format wrong")
        empty = build_digest(data, kb, days=1, now=datetime(2026, 12, 30, tzinfo=timezone.utc))
        c3 = [] if ("Nothing new in this period." in empty and "# Weekly digest 2026-W53" in empty) else ["empty digest wrong"]
        for n, c in ((1, c1), (2, c2), (3, c3)):
            if c:
                fails.extend(f"digest {n}: {m}" for m in c)
            else:
                passed += 1
    if verbose:
        print(f"  digest -> {passed}/3 checks ok")
    return passed, 3, fails


_ATOM_OK = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
 <entry><id>http://arxiv.org/abs/1706.03762v7</id><updated>2023-08-02T00:41:18Z</updated>
  <published>2017-06-12T17:57:34Z</published><title>Attention Is
   All You Need</title><summary> The dominant sequence transduction models ... </summary>
  <author><name>Ashish Vaswani</name></author><author><name>Noam Shazeer</name></author>
  <arxiv:primary_category term="cs.CL"/><category term="cs.CL"/><category term="cs.LG"/>
 </entry></feed>"""
_ATOM_EMPTY = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
_ARTICLE_HTML = """<html><head><title>Agents in production | Example Blog</title>
<meta name="author" content="Jane Doe"><meta property="og:site_name" content="Example Blog"></head>
<body><nav>Home | About | Login | Subscribe</nav><article><h1>Agents in production</h1>
<p>""" + ("Running agents in production needs evaluation, observability and guardrails. " * 12) + """</p>
<p>The second paragraph explains context layers and why retrieval quality matters for agents.</p>
</article><footer>Copyright 2026 Example. Cookie settings.</footer></body></html>"""


def suite_papers(fixtures: Path, verbose: bool) -> Result:
    """PR-7: arXiv papers + web articles -> text (no AI). Offline: injected network functions
    (labelled test doubles); web extraction uses the REAL trafilatura on a static HTML string.
    5 checks:
      1. arXiv Atom parsing (title whitespace, authors, dates, categories, version); empty -> error.
      2. full text: HTML used when long enough; PDF fallback when no HTML; abstract-only with an
         explicit note when both fail; 3-second pacing between arXiv requests.
      3. web: main text kept, nav/footer dropped, title/site/author captured; too-short -> WebError.
      4. build_kb_pack picks the paper / article template by manifest kind.
      5. digest labels arXiv and Web items.
    """
    from datetime import datetime, timezone
    fails: List[str] = []
    passed = 0

    def check(n: int, msgs: List[str]) -> None:
        nonlocal passed
        if msgs:
            fails.extend(f"papers {n}: {m}" for m in msgs)
        else:
            passed += 1

    # 1
    c1 = []
    m = axx.parse_atom(_ATOM_OK)
    if m["title"] != "Attention Is All You Need" or m["authors"] != ["Ashish Vaswani", "Noam Shazeer"]:
        c1.append(f"title/authors={m['title']!r} {m['authors']}")
    if (m["published"], m["updated"], m["versioned_id"], m["primary_category"]) != ("2017-06-12", "2023-08-02", "1706.03762v7", "cs.CL"):
        c1.append(f"dates/ids={m}")
    try:
        axx.parse_atom(_ATOM_EMPTY)
        c1.append("empty feed did not raise")
    except axx.ArxivError:
        pass
    check(1, c1)

    # 2
    c2 = []
    sleeps: List[float] = []

    def make_get(html_status: int, pdf_status: int):
        def get(url, timeout):  # TEST DOUBLE of export.arxiv.org / arxiv.org
            if url.startswith(axx.API):
                return 200, _ATOM_OK
            if "/html/" in url:
                return html_status, b"<html>paper html</html>"
            return pdf_status, b"%PDF-fake"
        return get

    long_md = "Full paper text. " * 200
    cl = axx.ArxivClient(http_get=make_get(200, 200), sleep=sleeps.append)
    md, meta = axx.extract_paper(cl, "1706.03762", html_to_markdown=lambda h, u: long_md,
                                 pdf_to_text=lambda b: "PDF TEXT")
    if meta["fulltext_source"] != "html" or "Full paper text." not in md or "PDF TEXT" in md:
        c2.append("HTML path not used")
    if sleeps != [3.0]:
        c2.append(f"pacing sleeps={sleeps} (expected one 3.0 s pause between 2 requests)")
    cl = axx.ArxivClient(http_get=make_get(404, 200), sleep=lambda _s: None)
    md, meta = axx.extract_paper(cl, "1706.03762", html_to_markdown=lambda h, u: long_md,
                                 pdf_to_text=lambda b: "PDF TEXT " * 50)
    if meta["fulltext_source"] != "pdf" or "no HTML version (HTTP 404)" not in md or "formulas and tables may be garbled" not in md:
        c2.append("PDF fallback not used or not stated")
    cl = axx.ArxivClient(http_get=make_get(404, 404), sleep=lambda _s: None)
    md, meta = axx.extract_paper(cl, "1706.03762", html_to_markdown=lambda h, u: "", pdf_to_text=lambda b: "")
    if meta["fulltext_source"] != "none" or "FULL TEXT NOT EXTRACTED" not in md or "dominant sequence transduction" not in md:
        c2.append("abstract-only case not stated")
    check(2, c2)

    # 3 (real trafilatura)
    c3 = []
    md, meta = wbx.extract_article("https://blog.example.com/agents", fetch=lambda u: _ARTICLE_HTML)
    if "Running agents in production needs evaluation" not in md or "context layers" not in md:
        c3.append("main text missing")
    if "Cookie settings" in md or "Subscribe" in md:
        c3.append("nav/footer not removed")
    if "Agents in production" not in meta["title"] or "Jane Doe" not in md:
        c3.append(f"metadata title={meta['title']!r}")
    try:
        wbx.extract_article("https://x.example/", fetch=lambda u: "<html><body><p>tiny</p></body></html>")
        c3.append("too-short page did not raise")
    except wbx.WebError:
        pass
    check(3, c3)

    # 4 + 5
    c4, c5 = [], []
    with tempfile.TemporaryDirectory() as tds:
        kb = Path(tds)
        (kb / "kb" / "full").mkdir(parents=True)
        for st in ("Paper [arxiv-1706.03762]", "Post [web-33e31ed646]"):
            (kb / "kb" / "full" / f"{st}.md").write_text("body", encoding="utf-8")
        ts = "2026-11-23T10:00:00+00:00"
        data = {"arxiv:1706.03762": {"status": "extracted", "kind": "arxiv_paper", "title": "Paper", "ts": ts,
                                     "stem": "Paper [arxiv-1706.03762]", "source_url": "u",
                                     "full_paths": {"md": "kb/full/Paper [arxiv-1706.03762].md"}},
                "web:33e31ed646": {"status": "extracted", "kind": "web_article", "title": "Post", "ts": ts,
                                   "stem": "Post [web-33e31ed646]", "source_url": "u",
                                   "full_paths": {"md": "kb/full/Post [web-33e31ed646].md"}}}
        kt = {"arxiv_paper": (PKG / "synth" / "manual_prompt_paper.md").read_text(encoding="utf-8"),
              "web_article": (PKG / "synth" / "manual_prompt_article.md").read_text(encoding="utf-8")}
        build_pack(data, kb_dir=kb, template="VIDEO {{TRANSCRIPT}}", kind_templates=kt)
        pp = (kb / "kb" / "prompts" / "Paper [arxiv-1706.03762].prompt.md").read_text(encoding="utf-8")
        ap = (kb / "kb" / "prompts" / "Post [web-33e31ed646].prompt.md").read_text(encoding="utf-8")
        if "Summarise this research paper" not in pp or "Summarise this article" not in ap or "VIDEO" in pp + ap:
            c4.append("kind templates not applied")
        dg = build_digest(data, kb, days=7, now=datetime(2026, 11, 24, tzinfo=timezone.utc))
        if "| arXiv | Paper |" not in dg or "| Web | Post |" not in dg:
            c5.append("digest kind labels wrong")
    check(4, c4)
    check(5, c5)

    if verbose:
        print(f"  papers -> {passed}/5 checks ok")
    return passed, 5, fails


SUITES: Dict[str, Callable[[Path, bool], Result]] = {
    "classify": suite_classify,
    "ingest": suite_ingest,
    "extract": suite_extract,
    "dedupe": suite_dedupe,
    "manifest": suite_manifest,
    "naming": suite_naming,
    "rename": suite_rename,
    "pack": suite_pack,
    "github": suite_github,
    "digest": suite_digest,
    "papers": suite_papers,
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
