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
# 1) EVALS — tests the code only (no config, no network). Expect: "45/45 checks passed / ALL PASS", exit 0.
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
| `--refresh-github` | off | re-check extracted GitHub repos; re-extract only changed ones |
| `--naming title_id\|id` | `output.naming` (`title_id`) | `title_id`: files named `<Title> [<id>]` (title via YouTube oEmbed); `id`: `<id>` with no title lookup |

### Flags (run_evals.py)
| Flag | Default | Effect |
|------|---------|--------|
| `--fixtures DIR` | `evals/fixtures` | fixtures directory (classify cases live here) |
| `--only NAME` | all | run one suite: `classify` \| `ingest` \| `extract` \| `dedupe` \| `manifest` \| `naming` \| `rename` \| `pack` \| `github` |
| `--verbose` | off | print each case, not just the summary |

> The evals are self-contained: the `ingest`/`extract`/`dedupe` suites build their own
> temporary data and use an OFFLINE test double (`evals/fixtures/fake_transcript.py`), so they
> do NOT read `sources.txt` / `input.source_dir` and make ZERO YouTube calls. Only `--fixtures`
> configures their input.

## File naming (PR-2)
New extractions are named `<Title> [<id>]`, e.g. `kb/full/Design Claude Code Like a Senior Engineer [YtRIj_KU9d4].txt`.
- The title comes from YouTube's public oEmbed endpoint (free, no API key, one request per video).
- Characters Windows forbids (`< > : " / \ | ? *`) are removed, the name is capped at
  `output.max_stem_len` (default 100) so full paths stay under Windows' 260-character limit,
  and ` [<id>]` is always kept so names never collide.
- If the title lookup fails (offline, private/removed video) the file is named `<id>` and the run
  prints `[warn] <id>: title unavailable (...)`. A title is never invented.
- The manifest records `title` and `stem` for each new entry.
- Settings: `output.naming` (`title_id` | `id`), `output.max_stem_len`,
  `youtube.title_lookup.{timeout_s, retries, backoff_s}`; per run: `--naming`.
- Files extracted before PR-2 are renamed with `scripts/rename_kb.py` (below).

## Renaming existing files (PR-3, reversible)
```bash
uv run scripts/rename_kb.py                 # DRY RUN (default): show "<id>.txt -> <Title> [<id>].txt"
uv run scripts/rename_kb.py --apply         # back up manifest + write rename log, then rename
uv run scripts/rename_kb.py                 # re-run: expect "nothing to rename."
uv run scripts/rename_kb.py --undo ../GENERAL-RESEARCH/output/rename_log_<ts>.json --apply   # undo
```
- Same naming rule as new extractions (`safe_stem`), so old and new files match.
- Titles come from the manifest if known, otherwise YouTube oEmbed (paced by `--throttle-s`).
  A video whose title can't be fetched (private/removed → HTTP 401/404) keeps its `<id>` name.
- Never overwrites a file; if any rename fails, the ones already done in that run are reversed
  and the manifest is left unchanged. File contents are never changed.
- `--apply` writes `<kb_dir>/rename_log_<ts>.json` (used by `--undo`, kept as an audit record)
  and backs up the manifest to `<kb_dir>/kb_backup_<ts>/` (git-ignored).

### Flags (rename_kb.py)
| Flag | Default | Effect |
|------|---------|--------|
| `--config PATH` | `config.yaml` | config file |
| `--kb-dir PATH` | from config | override `output.kb_dir` |
| `--dry-run` | on | show the plan only |
| `--apply` | off | perform the renames (or the undo) |
| `--undo LOG` | — | reverse the renames recorded in a rename log |
| `--throttle-s SEC` | `2.0` | pause between oEmbed lookups |
| `--no-lookup` | off | never call oEmbed; rename only entries whose title is already in the manifest |
| `--backup-dir PATH` | `<kb_dir>/kb_backup_<ts>` | manifest backup folder |

## GitHub repos and accounts (PR-5, no AI)
Put GitHub links in the same source list as YouTube links:
```
https://github.com/<owner>/<repo>          # one repo (also .git URLs and /tree/... links)
https://github.com/<owner>                 # an account: its repos (most recently pushed first)
```
Each repo becomes `kb/full/<owner>__<repo> [github].md` with: repo facts (description, language,
stars, license, topics, branch, commit), folder structure, README, and key files
(package.json, pyproject.toml, requirements, Dockerfile, CLAUDE.md, docs/*.md, and the same files in
subfolders). Every cut (too many paths, oversized file, size cap) is stated in the file.
`build_kb_pack.py` then writes a repo-specific prompt (`synth/manual_prompt_repo.md`).

- Free GitHub REST API. Public repos need no token (60 requests/hour). For 5,000/hour and private
  repos you can read, put `GITHUB_TOKEN=...` in the repo-root `.env` (git-ignored; never paste it in chat).
- Already-extracted repos are skipped (dedupe). `--refresh-github` re-checks them and re-extracts
  only repos whose latest commit changed.
- Limits in `config.yaml` → `github:` (`max_repos`, `max_files`, `max_file_bytes`, `max_total_bytes`,
  `max_tree_entries`, `include_forks`, `include_archived`, `min_delay_s`, `min_remaining`, `timeout_s`).

## Summaries with ANY AI, by hand (no AI inside the agent)
The agent never calls an AI. To summarise, it prepares one ready-to-paste prompt per transcript:
```bash
uv run scripts/build_kb_pack.py --dry-run    # show what would be written
uv run scripts/build_kb_pack.py              # write kb/prompts/<Title> [<id>].prompt.md + kb/INDEX.md
```
1. Open `kb/INDEX.md` (lists every video, its transcript, its prompt, and whether a summary exists).
2. Open a **prompt** file, copy ALL of it, paste it into Claude Desktop / Claude Code / Gemini / GPT.
3. Save the AI's answer as `kb/highlights/<Title> [<id>].md` (the exact name is in the prompt).
4. Re-run `build_kb_pack.py` — INDEX.md then shows ✅ for that summary.

- The full transcript is copied into the prompt verbatim; nothing is shortened or edited.
- Re-runs only rewrite a prompt when its transcript changed (`--force` rewrites all).
- Template: `synth/manual_prompt.md` (edit it to change the instructions). Config:
  `output.prompts_dir`, `output.prompt_template`.

| Flag (build_kb_pack.py) | Default | Effect |
|------|---------|--------|
| `--dry-run` | off | report only, write nothing |
| `--force` | off | rewrite prompts even if unchanged |
| `--key KEY` | all | only this video (INDEX.md still lists all) |
| `--template PATH` | `output.prompt_template` | use another prompt template |
| `--no-index` | off | don't rebuild `kb/INDEX.md` |
| `--kb-dir PATH` / `--config PATH` | from config | as in orchestrate.py |

## Manifest `source_url` fix (PR-1, one-time)
Runs before PR-1 stored the whole input line as `source_url` (e.g. a pasted table row
`| 96 | 6/22/26 | ... | https://www.youtube.com/watch?v=<id> | note |`). New runs now store:
- `source_url`  — the canonical link `https://www.youtube.com/watch?v=<id>`
- `source_line` — the original input line, kept verbatim as an audit trail

Fix entries written before PR-1 (no LLM, no network, transcripts untouched):
```bash
uv run scripts/migrate_manifest.py            # DRY RUN (default): show what would change
uv run scripts/migrate_manifest.py --apply    # back up manifest.json, then fix it
uv run scripts/migrate_manifest.py            # re-run: expect "nothing to change."
```
The backup goes to `<kb_dir>/kb_backup_<UTC timestamp>/manifest.json` (git-ignored). Undo by
copying it back over `manifest.json`.

### Flags (migrate_manifest.py)
| Flag | Default | Effect |
|------|---------|--------|
| `--config PATH` | `config.yaml` | config file (reads `output.kb_dir`, `output.manifest`) |
| `--kb-dir PATH` | from config | override `output.kb_dir` |
| `--dry-run` | on | show the plan only; writes nothing |
| `--apply` | off | back up, then write the fixed manifest |
| `--backup-dir PATH` | `<kb_dir>/kb_backup_<ts>` | where the backup is written (never overwrites an existing backup) |

## After extraction (manual synthesis — V1, superseded by build_kb_pack.py above)
For each new `kb/full/<key>.txt`, open a Claude Code session on Max and follow
`synth/synthesize.md` to write `kb/highlights/<key>.md`, self-checking against
`synth/judge.md`. Synthesis never edits `kb/full/`. (Synthesis becomes scripted in V2.)

## Output layout (under `output.kb_dir`)
```
kb/full/<Title> [<key>].txt  # extracted transcript (raw; never edited by synthesis); <key>.txt if no title
kb/highlights/<key>.md     # synthesized entry (manual in V1)
manifest.json              # dedupe ledger (idempotent re-runs); source_url + source_line per entry
cost_ledger.jsonl          # one line per run (items, free tool calls, tokens)
```

## What it does NOT do (by design)
- No LLM tokens spent by the pipeline (synthesis is manual on Max).
- Non-YouTube links are skipped (Drive/GitHub = V3; documents = V2; deep research = V4).

## Skill invocation (Way 1 vs Way 2)
V1 uses **Way 2 only** — code shells out to the skill script deterministically. The installed-
plugin / auto-select path (Way 1) is not used until V5. See `../DESIGN/skill-invocation-model.md`.
