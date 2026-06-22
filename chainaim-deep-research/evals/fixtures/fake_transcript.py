#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""OFFLINE TEST DOUBLE for the youtube-transcript skill.

LABELLED EXPLICITLY AS A TEST FIXTURE (Rule 8), not a real extractor. It mimics the
real skill's CLI contract exactly — `<id_or_url> [--timestamps]`, transcript to stdout,
`Error: ...` + exit 1 on failure — so evals can exercise the real extract -> manifest ->
dedupe path WITHOUT hitting YouTube. The production run uses the real skill in
config.yaml (youtube.transcript_script). This file is NEVER referenced by config.yaml.
"""
import sys

if len(sys.argv) < 2:
    print("Error: missing video id", file=sys.stderr)
    sys.exit(1)

vid = sys.argv[1]
if vid == "FAILTHIS123":  # lets the eval test the failure path deterministically
    print("Error: simulated extraction failure", file=sys.stderr)
    sys.exit(1)

ts = "--timestamps" in sys.argv or "-t" in sys.argv
if ts:
    print(f"[00:00] fake transcript for {vid}")
    print(f"[00:03] second line for {vid}")
else:
    print(f"fake transcript for {vid}")
    print(f"second line for {vid}")
