# ChainAIM Deep Research Agent — V1

Turns a list of YouTube links into a knowledge base. **Deterministic, zero-LLM core:**
extraction uses the free on-disk `youtube-transcript` skill; synthesis (V1) is a manual
Claude Code / Max session. See `../DESIGN/` for the full design.

## Pipeline (V1)
```
ingest -> route(classify regex) -> dedupe gate -> extract(youtube) -> publish(manifest + ledger)
```

## Requirements
- Python >= 3.10 and **uv** (https://docs.astral.sh/uv/). `uv --version` to confirm.
- The youtube-transcript skill present at the path in `config.yaml`
  (`youtube.transcript_script`). It self-installs its own deps via `uv run`.

## Configure
Edit `config.yaml` (the shared, language-independent public interface):
- `input.source_list` -> a single list file (or `null`).
- `input.source_dir` -> directory scanned for `*.txt`/`*.md` source files (current default:
  `../GENERAL-RESEARCH/input`).
- `output.kb_dir` -> where the KB, manifest, and ledger are written (current default:
  `../GENERAL-RESEARCH/output`).
- `youtube.transcript_script` -> path to the skill's `get_transcript.py`, relative to this
  package dir (vendored in-repo default: `../agent-skills/skills/youtube-transcript/scripts/get_transcript.py`). An absolute path also works.
- `youtube.throttle.*`, `cost.token_budget_per_run`, `output.formats` -> tune as needed.

Relative paths are anchored to THIS package dir (the folder holding `config.yaml`), not your
shell's current directory, so a run resolves to the same place from any cwd. Any input/output
path can also be overridden per-run on the CLI (config supplies defaults; the flag wins).

## Test sequence (step by step)

Run everything from the package folder:
```bash
cd chainaim-deep-research   # from the root of your cloned repo
```

Steps 1–3 are **safe — no network, no YouTube calls, nothing persists/changes**. Step 4 onward
makes **live** YouTube calls.

```bash
# 1) EVALS — tests the code only (no config, no network). Expect: "13/13 checks passed / ALL PASS", exit 0.
uv run evals/run_evals.py

# 2) KEY HYGIENE — confirms ANTHROPIC_API_KEY is unset (subscription mode). Expect: "guardrails: PASS".
uv run scripts/orchestrate.py --provider-check

# 3) DRY-RUN — reads your real input dir, classifies + dedupes, writes NOTHING, calls NOTHING.
#    Expect: "ingest=N  youtube_new=N  dedupe_skipped=0  unknown_skipped=0" + the list it would extract.
uv run scripts/orchestrate.py --config config.yaml --dry-run

# ---- everything below is LIVE (calls YouTube) ----

# 4) FIRST LIVE EXTRACTION, capped to one video (de-risk: confirms the network path + one-time
#    uv install of youtube-transcript-api). Expect one "[ok] <id> -> ...\output\kb\full\<id>.txt".
uv run scripts/orchestrate.py --config config.yaml --max-videos 1

# 5) FULL RUN — extract everything not already done. Already-extracted videos are dedupe-skipped.
#    Expect: youtube_new = (remaining), dedupe_skipped = (already done), one [ok] per new video.
uv run scripts/orchestrate.py --config config.yaml

# 6) RE-RUN (idempotency check) — should do nothing new.
#    Expect: "youtube_new=0  dedupe_skipped=N", extracted=0.
uv run scripts/orchestrate.py --config config.yaml
```

Notes:
- **First live call only** pauses briefly while `uv` installs the skill's `youtube-transcript-api`
  (one-time, needs internet). Subsequent calls are fast.
- Calls are paced ~2 s apart (throttle) with exponential backoff on failure; a failing video
  retries up to `youtube.throttle.max_retries` (default 3).
- If a video lacks captions it reports `[FAIL] <id>: ...` while the others succeed. Safe to
  re-run — the dedupe gate skips successes and retries only the failures.
- `--max-videos N` caps how many *new* videos a run attempts; drop it to process all.
- Every run appends one line to `cost_ledger.jsonl` and prints `this run` + `cumulative` counters.

## Run (command reference)
```bash
# dry run — classify + dedupe plan only, nothing written:
uv run scripts/orchestrate.py --config config.yaml --dry-run

# key hygiene — confirm ANTHROPIC_API_KEY is unset (subscription mode):
uv run scripts/orchestrate.py --provider-check

# real extraction (cap optional):
uv run scripts/orchestrate.py --config config.yaml --max-videos 5

# point at a different source list for one run (no config edit):
uv run scripts/orchestrate.py --source-list path/to/other-list.txt --dry-run

# deterministic evals (CI-friendly; exit 1 on failure):
uv run evals/run_evals.py            # or: --only classify --verbose
```

### Flags (orchestrate.py)
| Flag | Default | Effect |
|------|---------|--------|
| `--config PATH` | `config.yaml` | config file |
| `--dry-run` | off | plan only; no extraction or writes |
| `--max-videos N` | all | cap sources processed this run |
| `--timestamps` / `--no-timestamps` | from config | transcript timestamps |
| `--force` | off | ignore dedupe; re-extract seen keys |
| `--provider-check` | off | print provider guardrail report and exit |
| `--kb-dir PATH` | from config | override `output.kb_dir` |
| `--source-list PATH` | from config | override `input.source_list` |
| `--source-dir PATH` | from config | override `input.source_dir` |

### Flags (run_evals.py)
| Flag | Default | Effect |
|------|---------|--------|
| `--fixtures DIR` | `evals/fixtures` | fixtures directory (classify cases live here) |
| `--only NAME` | all | run one suite: `classify` \| `ingest` \| `extract` \| `dedupe` |
| `--verbose` | off | print each case, not just the summary |

> The evals are self-contained: the `ingest`/`extract`/`dedupe` suites build their own
> temporary data and use an OFFLINE test double (`evals/fixtures/fake_transcript.py`), so they
> do NOT read `sources.txt` / `input.source_dir` and make ZERO YouTube calls. Only `--fixtures`
> configures their input.

## After extraction (manual synthesis — V1)
For each new `kb/full/<key>.txt`, open a Claude Code session on Max and follow
`synth/synthesize.md` to write `kb/highlights/<key>.md`, self-checking against
`synth/judge.md`. Synthesis never edits `kb/full/`. (Synthesis becomes scripted in V2.)

## Output layout (under `output.kb_dir`)
```
kb/full/<key>.txt          # extracted transcript (raw; never edited by synthesis)
kb/highlights/<key>.md     # synthesized entry (manual in V1)
manifest.json              # dedupe ledger (idempotent re-runs)
cost_ledger.jsonl          # one line per run (items, free tool calls, tokens)
```

## What V1 does NOT do (by design)
- No LLM tokens spent by the pipeline (synthesis is manual on Max).
- Non-YouTube links are skipped (Drive/GitHub = V3; documents = V2; deep research = V4).

## Skill invocation (Way 1 vs Way 2)
V1 uses **Way 2 only** — code shells out to the skill script deterministically. The installed-
plugin / auto-select path (Way 1) is not used until V5. See `../DESIGN/skill-invocation-model.md`.
