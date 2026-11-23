# ChainAIM Deep Research Agent — Build Plan (Phases 1–3)

> Target location in repo: `DESIGN/07-build-plan.md`
> Status: PLAN ONLY — nothing below is built yet. Today only the V1 collector works
> (YouTube link → transcript, dedupe, cost ledger).
> Rule for every item: real implementation, no mocks presented as working code. The only
> test doubles allowed are the OFFLINE fixtures used by `evals/` (clearly labelled), exactly
> like the existing `evals/fixtures/fake_transcript.py`.

---

## 0. Ground truth this plan is built on

### 0.1 Read from your code (verified)
| Fact | Source |
|---|---|
| Pipeline: ingest → classify (regex) → dedupe → extract → publish | `scripts/orchestrate.py` |
| Files named by video ID: `kb/full/<id>.txt` | `extract/youtube.py::write_full` |
| Manifest keyed by ID; `record(key, url, hash, paths, status)` | `scripts/manifest.py` |
| `source_url` stores the whole input line (bug) | `GENERAL-RESEARCH/output/manifest.json` |
| Budget gate `over_budget(projected)` already implemented | `scripts/cost_ledger.py` |
| `SubscriptionProvider` passes the prompt as a command-line argument | `scripts/provider.py` line ~102 |
| Hard-coded model IDs `claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-8` | `scripts/provider.py` lines 47–49 |
| Writer / checker prompts exist but are never called | `synth/synthesize.md`, `synth/judge.md` |
| 15 transcripts, 0 summaries, `llm_tokens: 0` on every run | `output/manifest.json`, `cost_ledger.jsonl` |

### 0.2 Verified from official docs (2026-11-23)
| Fact | Source |
|---|---|
| `claude -p --output-format json` returns the text in `result`, plus `session_id`, usage and `total_cost_usd` (client-side estimate) | code.claude.com/docs/en/headless |
| `claude -p` reads stdin (cap 10 MB); exit code 0 = success | same |
| `--bare` does NOT use your subscription login (needs `ANTHROPIC_API_KEY`) → we must NOT use `--bare` in subscription mode | same |
| Without `--bare`, `-p` loads the CLAUDE.md / hooks of the working directory → run it from a clean scratch dir | same |
| `--json-schema` returns validated output in `structured_output` | same |
| YouTube oEmbed `https://www.youtube.com/oembed?url=...&format=json` returns `title` with no API key | oEmbed spec / Wikipedia oEmbed example |
| YouTube Data API: search has its own default bucket (~100 `search.list` calls/day) + 10,000 units/day for other endpoints | developers.google.com/youtube/v3 (quota pages) |
| arXiv API: free, no key, max 1 request / 3 s, single connection | info.arxiv.org/help/api/tou.html |
| Tavily: free 1,000 credits/month; basic search = 1 credit | docs.tavily.com/documentation/api-credits |
| GitHub REST: 60 req/h without token, 5,000 req/h with a token | docs.github.com rate-limits page |

### 0.3 Resolved in Step 0.1 (read from the repo on 2026-11-23)
| Item | Finding |
|---|---|
| Does `get_transcript.py` print the video title? | **No** — it prints transcript text only. Title comes from YouTube oEmbed (PR-2). |
| `run_evals.py` structure | Suites registered in a `SUITES` dict (`classify`, `ingest`, `extract`, `dedupe`); `--only` choices come from it. New suites are added there. |
| `.gitignore` | Has `.venv/`, `__pycache__/`, `*.py[cod]`, `*.egg-info/`, OS cruft. **No `.env` rule** → added in PR-0. `GENERAL-RESEARCH/output/` is tracked (17 files). |
| Git remote / default branch | `origin` = `https://github.com/chainaim3003/CHAINAIM-TEAM-RESEARCH.git`, default `main` |

### 0.4 Already in the repo (the plan builds on these, does not duplicate them)
| Item | What it does |
|---|---|
| `.github/workflows/ci.yml` | On every PR to `main`: `uv run evals/run_evals.py` + `--provider-check` |
| `.github/workflows/tag-release-summary.md` (+ `.lock.yml`) | On every pushed `v*` tag: Copilot agent writes a release-summary issue (uses AI credits per run — the file notes ~13 credits per report) |
| Branch protection (per the workflow comment) | `main` needs a PR + passing evals + 1 approval |
| `ship.ps1` | Your commit/push/tag helper (`-Message -Paths -Branch -Tag -DryRun`) |
| `.gitattributes` | LF line endings; `*.ps1` CRLF |
| Existing tags | `v1.0.1` – `v1.0.4` → next tag starts at **`v1.0.5`** |

### 0.5 Still to verify (Step 0.2+, manual checks)
| Item | Why it matters |
|---|---|
| `claude --model sonnet` alias works on your Claude Code version | Avoids hard-coding model IDs that go stale |
| `gh` CLI installed + logged in | `gh pr create` |
| SQLite FTS5 available in your Python | Phase 3 "Ask your library" |
| `streamlit.testing.v1.AppTest` available in the installed Streamlit | Phase 2 UI tests |

---

## 1. Architecture after all three phases

```
                 ┌──────────── Streamlit app (localhost) ────────────┐
                 │ Add links │ Library │ Suggestions │ Ask │ Research │
                 └─────┬─────────┬──────────┬─────────┬───────┬──────┘
                       │ files only (app never holds state itself)
 sources/*.txt ──► ingest ──► classify ──► dedupe ──► extract ──► kb/full/
 (manual + approved)            │                       │  youtube | github | arxiv | web
                                │                       ▼
                         candidates.json ◄── discover ◄─ profile/topic_profile.json
                                                        ▲
 kb/highlights/ ◄── synthesize ◄─► judge  (ModelProvider: claude -p | API)
       │
       ├──► index (SQLite FTS5) ──► ask.py  /  deep_research.py ──► reports/
       └──► digest.py (weekly) ──► kb/digests/
 Every LLM call: CostLedger.over_budget(projected) checked FIRST → checkpoint + stop if breached.
```

Design rules kept from `DESIGN/00-conceptual-design.md`:
1. Free deterministic tools first; LLM only as writer, checker, planner.
2. Every behaviour is a config key AND a CLI flag (flag wins).
3. `kb/full/` is never edited by synthesis.
4. Every LLM loop has a hard stop (retries cap + token budget).
5. Files are the interface — UI, scheduler and CLI all read/write the same files.

---

## 2. Git workflow (used by every PR)

### 2.1 Branch / tag conventions
- **Branch workflow (changed 2026-11-23, from PR-4 on):** all work happens on ONE long-lived
  branch `dev`. One PR per numbered item, `dev` → `main`, merged with a **merge commit**
  (not squash — squash would make `dev` diverge from `main`). One PR open at a time.
  After each merge: `git pull origin main` on `dev`, then tag `main`.
  Repo settings (owner): "Allow merge commits" on, "Allow auto-merge" on,
  "Automatically delete head branches" off. PR-0..PR-3 used per-PR branches + squash.
- Tags: annotated, semver. Current latest tag is `v1.0.4`. Each merged PR bumps the
  version shown in its section. End of Phase 1 = `v2.0.0`, Phase 2 = `v3.0.0`, Phase 3 = `v4.0.0`.
- Every tag push triggers `tag-release-summary` (AI credits). Tagging per PR = one summary per PR.
- Every step starts by checking the current branch (`git branch --show-current` → `dev`).
- Auto-merge: every PR command ends with `gh pr merge --auto --merge`; the code owner
  (`chainaim3003`) approves and GitHub merges once CI passes.
- Branch protection needs 1 approval. GitHub does not let a PR author approve their own PR, so
  if you are the only collaborator you will need an admin bypass or another reviewer (check your
  repo's ruleset settings — not verified from here).
- Commit messages: Conventional Commits. **No Claude attribution trailer** (your rule).
- Secrets: `.env` only, never committed, never pasted in chat.

### 2.2 One-line commands (Windows PowerShell 5.1 — verified on your machine)
5.1 has no `&&`, so each step is nested in `if ($?) { ... }`: a step runs only if the one
before it succeeded. Replace `<...>` placeholders.

**Set the repo path (once per PowerShell window):**
```powershell
$R="C:\SATHYA\CHAINAIM3003\mcp-servers\FINAGENTS\FINAGENTS1\Transcript_agent\CHAINAIM-TEAM-RESEARCH"
```

**Sync `dev` with `main` (start of every PR, after the previous merge):**
```powershell
cd $R; git checkout dev; if ($?) { git pull origin main; if ($?) { git push origin dev; git branch --show-current } }
```

**Check branch + what will be committed (run before every commit):**
```powershell
cd $R; git branch --show-current; git status --short
```

**Commit + push + open PR** (explicit paths — never `git add -A`, so outputs/.env can't slip in;
PR bodies live in the git-ignored `.pr/` folder):
```powershell
cd $R; git add -- <paths...>; if ($?) { git commit -m "<subject>" -m "<body>"; if ($?) { git push origin dev; if ($?) { gh pr create --base main --head dev --title "<title>" --body-file .pr/<PR-ID>.md; if ($?) { gh pr merge --auto --merge } } } }
```

**After the PR is merged — tag the latest main:**
```powershell
cd $R; git checkout main; if ($?) { git pull origin main; if ($?) { git tag -a <vX.Y.Z> -m "<PR-ID>: <title>"; if ($?) { git push origin <vX.Y.Z>; if ($?) { git checkout dev; if ($?) { git pull origin main; if ($?) { git push origin dev; git branch --show-current } } } } } }
```
(Tags `main`, then brings the merge commit back into `dev` so the next PR shows only new work.)

**Release note for phase tags (v2.0.0 / v3.0.0 / v4.0.0):**
```powershell
cd $R; gh release create <vX.0.0> --title "<Phase N complete>" --notes-file .pr/<vX.0.0>-release.md
```

### 2.3 PR body template (every `.pr/<PR-ID>.md` follows this)
```markdown
## What
One paragraph: what this PR adds/fixes.
## Why
The problem it solves; link to DESIGN/07-build-plan.md section.
## How
- Files added/changed and the role of each.
- Key design decisions + trade-offs.
- New config keys and CLI flags (name · default · effect).
## Tests
- Offline evals: command + expected output.
- Live smoke test: command + expected output (what was actually observed).
## Risks / limits
Known limits, external quotas, failure modes and how they surface.
## Rollback
How to revert (git revert <sha> / restore backup file / flag to disable).
## Checklist
- [ ] `uv run evals/run_evals.py` → ALL PASS
- [ ] Live smoke test run and output pasted above
- [ ] No secrets in diff (`git diff --cached | Select-String -Pattern "KEY|TOKEN|SECRET"` empty)
- [ ] README/config docs updated
```

### 2.4 Code comment standard (every file)
- Module docstring: purpose, contract it implements (cite DESIGN section), inputs/outputs,
  network/LLM usage (yes/no), failure behaviour.
- Every public function: docstring with Args / Returns / Raises.
- Inline comments only for **why** (non-obvious decisions, external limits, Windows quirks).
- Every config key documented in `config.yaml` beside the key.

---

## 3. Step 0 — Verification gate (before any code)

| # | Check | Who | Command / action | Pass condition |
|---|---|---|---|---|
| 0.1 | Read `get_transcript.py`, `run_evals.py`, `.gitignore`, `.git/config` | AI can do this (when your computer is online) | — | Facts in §0.3 confirmed or plan adjusted |
| 0.2 | Tool versions | Manual — you do this | `uv --version; python --version; claude --version; gh --version; $PSVersionTable.PSVersion` | All print a version |
| 0.3 | `claude -p` JSON shape + model alias | Manual — you do this | `cd $env:TEMP; "Reply with the word OK" \| claude -p --output-format json --model sonnet` | JSON with `"result"` containing OK, exit 0 |
| 0.4 | Key hygiene | Manual — you do this | `cd $R\chainaim-deep-research; uv run scripts/orchestrate.py --provider-check` | `guardrails: PASS` |
| 0.5 | gh login | Manual — you do this | `gh auth status` | Logged in to github.com |
| 0.6 | FTS5 | Manual — you do this | `uv run python -c "import sqlite3;sqlite3.connect(':memory:').execute('create virtual table t using fts5(x)');print('FTS5 OK')"` | `FTS5 OK` |

Manual steps are walked one at a time when we start.

---

## 4. PHASE 1 — Core: transcript → named files → checked summary (+ GitHub)

### PR-0 · `chore/build-plan` · tag `v1.0.5`
**What:** commit this plan; harden `.gitignore` for secrets; document future keys.
(CI already exists in `ci.yml` — not duplicated.)
- `DESIGN/07-build-plan.md` (this file).
- `.gitignore`: add `.env`, `.env.*` with `!.env.example` kept, `logs/`, `pipeline.lock`,
  `kb_backup_*/`, `.pr/` (local PR-body drafts). (`uv.lock` stays tracked — no blanket `*.lock` rule.)
- `.env.example`: every future key with empty values + comments (no real values).

**Tests**
```powershell
cd $R\chainaim-deep-research; uv run evals/run_evals.py; uv run scripts/orchestrate.py --provider-check; cd $R; git check-ignore -v .env .pr/x.md; git branch --show-current; git status --short
```
Expect: `ALL PASS`, `guardrails: PASS`, `.env` and `.pr/x.md` reported as ignored by `.gitignore`,
branch `chore/build-plan`, and only the 3 PR-0 files listed as changed/new.

**Commit:** `chore: add Phase 1-3 build plan and ignore local secrets`

---

### PR-1 · `fix/manifest-source-url` · tag `v1.0.6`
**What:** manifest stores a clean canonical URL; one-time migration of the 15 existing entries.
- `scripts/orchestrate.py`: pass `canonical_url = https://www.youtube.com/watch?v=<key>` to
  `manifest.record`; keep the original line in a new `source_line` field (audit trail).
- `scripts/manifest.py`: schema gains `source_line` (optional, backward compatible).
- `scripts/migrate_manifest.py` — flags: `--kb-dir`, `--dry-run` (default ON), `--apply`,
  `--backup-dir` (default `kb_backup_<ts>/`). Writes a backup before any change.
- `evals/run_evals.py`: new suite `manifest` (temp dir; old-format entry → migrated entry).

**Tests**
```powershell
uv run evals/run_evals.py --only manifest --verbose
uv run scripts/migrate_manifest.py --dry-run
uv run scripts/migrate_manifest.py --apply
uv run scripts/orchestrate.py --config config.yaml --dry-run
```
Expect: dry-run lists 15 planned fixes; apply writes backup + fixes; dry-run of pipeline still
shows `youtube_new=0 dedupe_skipped=15` (dedupe unaffected).

**Rollback:** copy `kb_backup_<ts>/manifest.json` back.

---

### PR-2 · `feat/title-file-naming` · tag `v1.1.0`
**What:** files named `Title [ID].txt` / `Title [ID].md`.
- `extract/metadata.py` (new): `fetch_youtube_title(key, *, timeout_s, retries)` via oEmbed
  (stdlib `urllib`, no key). Step 0.1 confirmed `get_transcript.py` does not return a title.
- `scripts/naming.py` (new): `safe_stem(title, key, *, max_len=120)`:
  removes `<>:"/\|?*` and control chars, collapses spaces, strips trailing dots/spaces,
  avoids Windows reserved names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`), always
  appends ` [<key>]` so names are unique.
- `extract/youtube.py`: writes `<stem>.<fmt>`; manifest records `title`, `stem`.
- Title fetch failure → falls back to `<key>` stem, logs `[warn] title unavailable`, run still
  succeeds (no fake title is ever invented).
- Config `output.naming: "title_id" | "id"` + flag `--naming`.

**Tests**
```powershell
uv run evals/run_evals.py --only naming --verbose
uv run scripts/orchestrate.py --config config.yaml --max-videos 1 --force --naming title_id
```
Offline suite cases: reserved names, emoji, 300-char titles, duplicate titles, empty title.
Live: one re-extracted file appears as `kb/full/<Title> [<ID>].txt`.

---

### PR-3 · `feat/rename-existing-kb` · tag `v1.2.0`
**What:** rename the 15 existing ID-named files to the new style, reversibly.
- `scripts/rename_kb.py` — flags: `--kb-dir`, `--dry-run` (default ON), `--apply`,
  `--undo <log.json>`, `--throttle-s` (oEmbed pacing, default 2.0).
- Writes `rename_log_<ts>.json` (old → new) before touching files; updates manifest paths.

**Tests**
```powershell
uv run evals/run_evals.py --only rename --verbose
uv run scripts/rename_kb.py --dry-run
uv run scripts/rename_kb.py --apply
uv run scripts/rename_kb.py --undo <rename_log_ts.json> --dry-run
```
Expect: 15 planned renames; after apply `kb/full` shows titles; undo dry-run lists 15 reversals.

---

### PR-4 · branch `dev` · tag `v1.2.1`
**What:** make `SubscriptionProvider` safe for real transcripts on Windows.
- Prompt sent via **stdin**, not argv (Windows command lines cap at 32,767 chars; your largest
  transcript is ~100 KB).
- Resolve the binary with `shutil.which("claude")`; clear error if missing.
- Run from a clean scratch working dir (so the repo's CLAUDE.md/hooks don't load into every call).
- Model routing by **alias** (`haiku`/`sonnet`/`opus`) from config; explicit IDs optional via
  `model.tier_models` override. Removes stale hard-coded IDs.
- Parse `result`, `is_error`, usage and `total_cost_usd`; `is_error` or non-zero exit → `ProviderError`.
- New: `--json-schema` support (`complete_json(prompt, schema, tier)`) returning `structured_output`.
- `ApiProvider`: same interface; model IDs from config.
- `evals/fixtures/fake_claude.py`: OFFLINE test double that mimics the documented JSON output
  (labelled as a test double; used only by evals).
- `scripts/provider_smoke.py` — flags `--tier`, `--prompt`: one real call, prints result + tokens.

**Tests**
```powershell
uv run evals/run_evals.py --only provider --verbose
uv run scripts/provider_smoke.py --tier haiku --prompt "Reply with OK"
```
Expect: offline suite passes; live smoke prints `OK` and token counts.

---

### PR-5 · `feat/synthesize-judge` · tag `v1.3.0`
**What:** automatic summaries + checker → `kb/highlights/<stem>.md`, plus `kb/INDEX.md` for Claude Code.
- `scripts/synthesize.py` — flags: `--config`, `--max-items`, `--key`, `--level tldr|highlights|deep`
  (default `highlights`), `--force`, `--dry-run`, `--no-judge` (off by default; logged when used),
  `--budget` (overrides `cost.token_budget_per_run`).
- Flow per item:
  1. Skip if highlight exists and `--force` not set (dedupe via manifest `synth_status`).
  2. Projected tokens = estimate from input chars → `over_budget(projected)`? → checkpoint + stop.
  3. Writer: `synth/synthesize.md` + transcript → draft.
  4. Checker: `synth/judge.md` via `complete_json` with a JSON schema
     (`pass, coverage, fidelity, links_ok, issues, fix_hint`).
  5. Fail → rewrite with `fix_hint`, max `synthesis.judge_max_retries` (2).
     Still failing → publish best draft with `status: needs-review`.
  6. Write highlight with front-matter: `title, key, source_url, kind, model, created,
     judge: {coverage, fidelity, pass}, status`.
  7. Ledger records real tokens; manifest records `synth_status`, `highlight_path`.
- Guard: `synthesis.max_input_chars` (default 400,000). Larger input → clear error, never silent truncation.
- `scripts/build_index.py`: regenerates `kb/INDEX.md` (table: title · kind · TL;DR · links to
  full + highlight · status). Run automatically at the end of synthesize.
- `synth/synthesize.md` / `judge.md`: tightened output format (no behaviour change in rules).

**Tests**
```powershell
uv run evals/run_evals.py --only synthesize --verbose
uv run scripts/synthesize.py --dry-run
uv run scripts/synthesize.py --max-items 1
uv run scripts/synthesize.py --max-items 1
uv run scripts/synthesize.py
```
Expect: offline suite covers pass, retry→pass, retry-exhausted→needs-review, budget stop,
oversize input. Live: first run writes 1 highlight with judge scores; second run skips it
(dedupe); full run writes the rest; `kb/INDEX.md` lists all 15.

---

### PR-6 · `feat/github-summaries` · tag `v1.4.0`
**What:** GitHub repo or account links → extracted content → same summary flow.
- `scripts/orchestrate.py::classify`: new kinds `github_repo` (`github.com/<owner>/<repo>`),
  `github_account` (`github.com/<owner>`). Keys `gh:<owner>/<repo>`.
- `extract/github.py` (REST via stdlib `urllib`; `GITHUB_TOKEN` from `.env` optional):
  - repo: metadata, README, top-level tree, recursive tree (bounded), key files
    (`package.json`, `pyproject.toml`, `requirements*.txt`, `Cargo.toml`, `go.mod`, `Dockerfile`,
    `*.md` in `docs/`, `CLAUDE.md`, `llms.txt`, `SKILL.md`) up to `github.max_files` /
    `github.max_bytes`.
  - account: paginate repos; flags `--gh-max-repos` (20), `--gh-include-forks`, `--gh-include-archived`.
  - Reads `X-RateLimit-Remaining`; stops cleanly with a checkpoint before exhausting it.
  - Writes `kb/full/<owner>__<repo> [github].md`; content hash = default-branch commit SHA,
    so `--refresh` re-extracts only repos that changed.
- `synth/synthesize_repo.md`: repo-specific sections (purpose, architecture, stack, how to run,
  entry points, notable files).
- Private repos need a token with repo read scope — stored in `.env`, never in chat.

**Tests**
```powershell
uv run evals/run_evals.py --only github --verbose
uv run scripts/orchestrate.py --config config.yaml --dry-run
uv run scripts/orchestrate.py --config config.yaml --max-items 1
uv run scripts/synthesize.py --key "gh:<owner>/<repo>"
```
Offline suite uses recorded API JSON fixtures (labelled). Live: add one public repo link to
`sources.txt` → `kb/full/<owner>__<repo> [github].md` + its highlight.

### Phase 1 done → tag `v2.0.0`
**Manual — you do this:** open `GENERAL-RESEARCH\output\kb` in Claude Code; start from `INDEX.md`.

---

## 5. PHASE 2 — Automation, taste, discovery, one local app

### PR-7 · `feat/automation-digest` · tag `v2.1.0`
- `scripts/run_pipeline.py` — flags `--stages extract,synthesize,index,digest`, `--max-items`,
  `--budget`. Single entry point. File lock (`pipeline.lock`) prevents overlapping runs;
  stale lock (> `--lock-timeout-min`, default 120) is reported, not silently deleted.
- `scripts/digest.py` — flags `--since 7d`, `--out kb/digests/`: weekly digest from highlights
  (themes, top takeaways, links).
- `ops/run_nightly.ps1`, `ops/run_weekly.ps1`: activate env, run pipeline, log to `logs/<date>.log`,
  non-zero exit on failure.
- `ops/register_tasks.ps1`: registers two Windows Scheduled Tasks (`Register-ScheduledTask`,
  current user, run only when logged on, "wake to run" optional flag). `-Unregister` switch.

**Tests**
```powershell
uv run evals/run_evals.py --only pipeline --verbose
uv run scripts/run_pipeline.py --stages extract,synthesize,index --max-items 1
uv run scripts/digest.py --since 30d
pwsh ops/run_nightly.ps1
pwsh ops/register_tasks.ps1 -WhatIf
```
**Manual — you do this:** run `ops/register_tasks.ps1` and confirm both tasks in Task Scheduler.

---

### PR-8 · `feat/topic-profile` · tag `v2.2.0`
- `scripts/profile.py` — flags `--rebuild`, `--min-sources`, `--out profile/topic_profile.json`.
  Claude reads highlights (not full transcripts — cheaper) and returns, via JSON schema,
  `topics[{name, weight, keywords, example_sources}]`, `exclusions[]`.
- Profile is versioned (`profile/history/`), human-editable; your edits are preserved on rebuild
  (`locked: true` topics never change).
- Feedback hook: `profile/feedback.jsonl` (approve/reject events from PR-10) shifts weights.

**Tests**
```powershell
uv run evals/run_evals.py --only profile --verbose
uv run scripts/profile.py --rebuild
```
Expect: `topic_profile.json` with topics whose `example_sources` exist in `kb/highlights`.

---

### PR-9 · `feat/discovery` · tag `v2.3.0`
- `discover/youtube_search.py` — YouTube Data API v3 `search.list` (`YOUTUBE_API_KEY`);
  local quota counter; stops at `discovery.youtube.max_calls_per_day` (default 80, below the ~100 default).
- `discover/arxiv_search.py` — arXiv export API, 3 s spacing, single connection, descriptive User-Agent.
- `discover/web_search.py` — Tavily search (`TAVILY_API_KEY`), credit counter vs monthly cap.
- `scripts/discover.py` — flags `--sources youtube,arxiv,web`, `--per-topic 5`, `--min-score 0.6`,
  `--dry-run`. Builds queries from the profile, dedupes against manifest + `rejected.json`,
  scores candidates with Claude (Haiku, batched, JSON schema: `score, reason, topic`), writes
  `candidates.json` (`url, kind, title, source, topic, score, reason, found_at, status: pending`).
- New extractors so approved papers/articles become `kb/full` files:
  - `extract/arxiv.py`: abstract + PDF text (PDF → text via `markitdown`, already named in design).
  - `extract/web.py`: Tavily Extract (clean article text); falls back to `markitdown` on the HTML.

**Tests**
```powershell
uv run evals/run_evals.py --only discover --verbose
uv run scripts/discover.py --sources arxiv --per-topic 2 --dry-run
uv run scripts/discover.py --sources youtube,arxiv,web --per-topic 3
```
**Manual — you do this:** create YouTube Data API key + Tavily key, put them in `.env`.
⚠️ Don't paste keys into the chat.

---

### PR-10 · `feat/local-app` · tag `v2.4.0`
- `app/services.py`: all logic (add links, list library, approve/reject, trigger pipeline run,
  read logs) — plain functions, unit-tested.
- `app/streamlit_app.py`: thin UI only. Tabs:
  1. **Add links** — paste links (YouTube / GitHub / arXiv / article) → validated by `classify`
     → appended to `sources/manual.txt` → optional "Run now".
  2. **Library** — search/filter by title, kind, topic, status; read highlight; download
     transcript and summary (`st.download_button`).
  3. **Suggestions** — `candidates.json` cards: Approve (→ `sources/approved.txt`), Reject
     (→ `rejected.json` + feedback), Later.
  4. **Runs** — last runs from `cost_ledger.jsonl`, current lock state, log tail.
- Binds to `localhost` only (`--server.address 127.0.0.1`). All data stays local.
- `ops/run_app.ps1` launcher.

**Tests**
```powershell
uv run evals/run_evals.py --only app --verbose
uv run streamlit run app/streamlit_app.py --server.address 127.0.0.1
```
Offline: `services.py` unit tests + Streamlit `AppTest` smoke (if available per Step 0).
Manual: add a link in the UI → run → see it in Library → download both files.

### Phase 2 done → tag `v3.0.0`

---

## 6. PHASE 3 — Ask your library, deep research

### PR-11 · `feat/library-qa` · tag `v3.1.0`
- `scripts/index_kb.py` — SQLite FTS5 index over `kb/full` + `kb/highlights`, chunked
  (`--chunk-chars 1500`, `--overlap 200`), incremental by content hash.
- `scripts/ask.py "<question>"` — flags `--top-k 8`, `--tier sonnet`, `--kinds`. BM25 retrieval →
  Claude answers **only from retrieved chunks** with citations `[Title, chunk n]`; returns
  "not found in your library" when evidence is missing (no outside knowledge).
- App: new **Ask** tab.

**Tests**
```powershell
uv run evals/run_evals.py --only qa --verbose
uv run scripts/index_kb.py
uv run scripts/ask.py "What do my videos say about git worktree?"
```
Expect: answer with citations pointing to real files; nonsense question → "not found".

---

### PR-12 · `feat/deep-research` · tag `v3.2.0`
- `scripts/deep_research.py "<question>"` — flags `--breadth 4`, `--depth 2`, `--max-workers 2`,
  `--budget 300000`, `--web/--no-web`, `--resume <checkpoint>`.
- Flow (STORM + Anthropic orchestrator-worker, cost-gated per `DESIGN/00` §6):
  1. Planner (Sonnet, JSON schema) → sub-questions.
  2. Workers (parallel, `--max-workers`) → library retrieval (PR-11) + optional Tavily web →
     cited notes.
  3. Writer: outline → sections → polish (Opus only for final polish if `--deep-polish`).
  4. Checker: every claim has a citation that exists; failures flagged in report.
  5. Budget checked before every call; checkpoint file after every step → `--resume`.
- Output `reports/<date>-<slug>.md` with sources list. App: **Research** tab.

**Tests**
```powershell
uv run evals/run_evals.py --only research --verbose
uv run scripts/deep_research.py "Best agent architecture patterns in my library" --breadth 2 --depth 1 --no-web --budget 80000
uv run scripts/deep_research.py --resume reports/.checkpoints/<id>.json
```
Expect: report with cited sections; ledger shows tokens; budget stop produces a checkpoint
that resumes.

### Phase 3 done → tag `v4.0.0`

---

## 7. Summary table

| PR | Branch | Phase | Item | Tag | Who |
|---|---|---|---|---|---|
| 0 | chore/build-plan | 1 | Plan, .gitignore, .env.example | v1.0.5 | AI build · you push |
| 1 | fix/manifest-source-url | 1 | Clean URLs + migration | v1.0.6 | AI build · you push |
| 2 | feat/title-file-naming | 1 | `Title [ID]` file names | v1.1.0 | AI build · you push |
| 3 | feat/rename-existing-kb | 1 | Rename 15 existing files | v1.2.0 | AI build · you run + push |
| 4 | fix/provider-hardening | 1 | Safe Claude calls (stdin, aliases) | v1.2.1 | AI build · you run smoke |
| 5 | feat/synthesize-judge | 1 | Summaries + checker + INDEX | v1.3.0 | AI build · you run |
| 6 | feat/github-summaries | 1 | GitHub repo/account | v1.4.0 → **v2.0.0** | AI build · you push |
| 7 | feat/automation-digest | 2 | Nightly/weekly + digest | v2.1.0 | AI build · you register tasks |
| 8 | feat/topic-profile | 2 | Taste profile | v2.2.0 | AI build · you review profile |
| 9 | feat/discovery | 2 | YouTube/arXiv/web discovery + extractors | v2.3.0 | AI build · you add keys |
| 10 | feat/local-app | 2 | Streamlit app | v2.4.0 → **v3.0.0** | AI build · you test UI |
| 11 | feat/library-qa | 3 | Ask your library | v3.1.0 | AI build · you test |
| 12 | feat/deep-research | 3 | Deep research reports | v3.2.0 → **v4.0.0** | AI build · you test |

Order is strict: each PR depends on the ones above it.
