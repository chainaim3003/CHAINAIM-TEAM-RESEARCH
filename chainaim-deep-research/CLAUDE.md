# CLAUDE.md — ChainAIM Deep Research Agent operating guardrails

> Loaded by Claude Code in your Max session. Keep this LEAN — it sits in the cached
> prefix on every call, and bloated overhead wastes the non-interactive credit pool
> (DESIGN/02-cost-model.md). Add nothing here that doesn't change behavior.

## What this agent is (V1)
A deterministic pipeline that turns a list of YouTube links into a knowledge base.
Extraction is FREE (the on-disk youtube-transcript skill). The LLM is used only as a
**brain** (synthesis) and a **judge** (quality) — and in V1, synthesis is YOU, here, in
this session. The pipeline spends **zero** LLM tokens.

## Cost-conscious rules (non-negotiable)
1. Never feed a whole video through the model — `scripts/orchestrate.py` extracts the
   transcript for free first. Synthesize from `kb/full/<key>.txt`, not from the video.
2. Output costs 5x input. Prefer TL;DR + Highlights; reserve the "deep" level (Opus) for
   sources that justify it.
3. Respect the per-run token budget (`cost.token_budget_per_run` in config.yaml).
4. Evaluator-optimizer loop (V2+) is capped at `synthesis.judge_max_retries` (default 2).

## Execution-mode guardrails (key hygiene — prevents silent API billing)
- This project runs on your **Claude MAX subscription** (`model.provider: subscription`,
  `model.deployment: internal` — one human, one beneficiary).
- **`ANTHROPIC_API_KEY` must be UNSET** in this environment. If it is set, Claude Code
  silently bills the API instead of your Max seat. Verify before a scripted run:
  `uv run scripts/orchestrate.py --provider-check` (it FAILs loudly if the key is set).
- Headless/scheduled runs (V2+) need `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`).

## How to run V1
```bash
uv run scripts/orchestrate.py --config config.yaml --dry-run        # plan only
uv run scripts/orchestrate.py --config config.yaml --max-videos 5   # extract up to 5
uv run scripts/orchestrate.py --provider-check                      # check key hygiene
uv run evals/run_evals.py                                           # deterministic evals
```

## Manual synthesis (V1)
After extraction, for each new `kb/full/<key>.txt`:
1. Read the transcript.
2. Follow `synth/synthesize.md` to write `kb/highlights/<key>.md` (TL;DR + Highlights).
3. Self-check against `synth/judge.md` (coverage, fidelity, links) before saving.
Do NOT modify files under `kb/full/` — synthesis only writes to `kb/highlights/`.

## Files
- `scripts/orchestrate.py` — pipeline driver (ingest -> classify -> dedupe -> extract -> publish)
- `scripts/{manifest,throttle,cost_ledger,provider}.py` — contract implementations
- `ingest/local_dir.py`, `extract/youtube.py` — V1 channel + extractor
- `synth/{synthesize,judge,router}.md` — shared prompts
- `evals/run_evals.py` — deterministic V1 evals
- `config.yaml` — the public interface; absolute paths fixed for this machine
