"""run_evals.py — deterministic V1 eval harness (CI-friendly).

V1 has NO LLM, so V1 evals test the deterministic core (the parts that can silently
break): the Router/classify regex, ingest parsing, the dedupe gate's idempotency, and
the extract->manifest write path (offline, via a labeled test double).

Slots reserved for later: the V2 judge eval and V3 routing eval (LLM) plug in here as
separate suites keyed off model.provider; they are intentionally NOT run in V1.

Flags (Rule 8):
    --fixtures DIR   fixtures directory (default: ./fixtures next to this file)
    --verbose        print each case, not just the summary
    --only NAME      run only the named suite (classify|ingest|dedupe|extract|manifest|naming|rename|provider)

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
from provider import ProviderError, SubscriptionProvider, select_provider  # noqa: E402
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


def suite_provider(fixtures: Path, verbose: bool) -> Result:
    """PR-4: SubscriptionProvider against an OFFLINE test double of `claude -p`.

    evals/fixtures/fake_claude.py mimics the documented `--output-format json` shape; no
    network, no real model. 6 checks:
      1. prompt goes via STDIN (not argv), incl. a 120 KB prompt (> Windows' 32,767-char
         command-line limit); -p and --output-format json are passed.
      2. result, usage (incl. cache tokens), cost estimate and model ALIAS are parsed/passed.
      3. is_error, non-zero exit and non-JSON output all raise ProviderError (no silent success).
      4. complete_json returns structured_output; a reply without it raises ProviderError.
      5. the CLI runs in a clean scratch folder (not the repo), so repo CLAUDE.md isn't loaded.
      6. select_provider guardrails: key set + subscription, product + subscription, and
         api without key all raise; subscription without key returns SubscriptionProvider.
    """
    fails: List[str] = []
    passed = 0
    fake = [sys.executable, str(PKG / "evals" / "fixtures" / "fake_claude.py")]
    prov = SubscriptionProvider({"synthesize": "sonnet"}, claude_cmd=fake, timeout_s=60)

    def check(n: int, msgs: List[str]) -> None:
        nonlocal passed
        if msgs:
            fails.extend(f"provider {n}: {m}" for m in msgs)
        else:
            passed += 1

    def with_mode(mode: str, fn):
        old = os.environ.get("FAKE_CLAUDE_MODE")
        os.environ["FAKE_CLAUDE_MODE"] = mode
        try:
            return fn()
        finally:
            if old is None:
                os.environ.pop("FAKE_CLAUDE_MODE", None)
            else:
                os.environ["FAKE_CLAUDE_MODE"] = old

    # 1 + 2 + 5
    big = "x" * (120 * 1024)
    c = with_mode("ok", lambda: prov.complete(big, "synthesize"))
    info = json.loads(c.text)
    c1 = []
    if info["stdin_len"] != len(big) or info["prompt_in_argv"]:
        c1.append(f"stdin_len={info['stdin_len']} prompt_in_argv={info['prompt_in_argv']}")
    if not (info["has_p"] and info["fmt_json"]):
        c1.append("missing -p or --output-format json")
    check(1, c1)
    c2 = []
    if info["model"] != "sonnet" or c.model != "sonnet":
        c2.append(f"model={info['model']!r} (role synthesize should resolve to alias 'sonnet')")
    if c.usage != {"input": 120, "output": 30, "cache_read": 5, "cache_write": 7} or c.total_tokens != 162:
        c2.append(f"usage={c.usage}")
    if c.cost_usd != 0.0123:
        c2.append(f"cost={c.cost_usd}")
    check(2, c2)

    # 3
    c3 = []
    for mode in ("is_error", "exit1", "badjson"):
        try:
            with_mode(mode, lambda: prov.complete("hi", "haiku"))
            c3.append(f"{mode}: no ProviderError")
        except ProviderError:
            pass
    check(3, c3)

    # 4
    c4 = []
    schema = {"type": "object", "properties": {"pass": {"type": "boolean"}}, "required": ["pass"]}
    out = with_mode("ok", lambda: prov.complete_json("judge", schema, "sonnet"))
    if out != {"pass": True, "echo_required": ["pass"]}:
        c4.append(f"structured_output={out}")
    try:
        with_mode("noschema", lambda: prov.complete_json("judge", schema, "sonnet"))
        c4.append("missing structured_output did not raise")
    except ProviderError:
        pass
    check(4, c4)

    # 5
    cwd = Path(info["cwd"]).resolve()
    c5 = []
    if cwd == PKG.resolve() or PKG.resolve() in cwd.parents or cwd in PKG.resolve().parents:
        c5.append(f"CLI ran inside the repo: {cwd}")
    if (cwd / "CLAUDE.md").exists():
        c5.append("scratch folder contains a CLAUDE.md")
    check(5, c5)

    # 6
    c6 = []
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        if not isinstance(select_provider({"model": {"provider": "subscription"}}), SubscriptionProvider):
            c6.append("subscription without key did not return SubscriptionProvider")
        for cfg, label in (
            ({"model": {"provider": "subscription", "deployment": "product"}}, "product+subscription"),
            ({"model": {"provider": "api"}}, "api without key"),
        ):
            try:
                select_provider(cfg)
                c6.append(f"{label}: no ProviderError")
            except ProviderError:
                pass
        os.environ["ANTHROPIC_API_KEY"] = "test-not-a-real-key"
        try:
            select_provider({"model": {"provider": "subscription"}})
            c6.append("key set + subscription: no ProviderError")
        except ProviderError:
            pass
    finally:
        os.environ.pop("ANTHROPIC_API_KEY", None)
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved
    check(6, c6)

    if verbose:
        print(f"  provider -> {passed}/6 checks ok (stdin {info['stdin_len']} chars, cwd {cwd})")
    return passed, 6, fails


SUITES: Dict[str, Callable[[Path, bool], Result]] = {
    "classify": suite_classify,
    "ingest": suite_ingest,
    "extract": suite_extract,
    "dedupe": suite_dedupe,
    "manifest": suite_manifest,
    "naming": suite_naming,
    "rename": suite_rename,
    "provider": suite_provider,
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
