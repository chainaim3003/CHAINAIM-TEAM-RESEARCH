# Architecture Contract (language-independent)

> This is the stable core. Python, TypeScript, and any future runtime implement THIS.
> If something here changes, it changes for every language. See `language-portability-audit.md`.

## 1. Data-flow contract (identical in every language)
```
ingest → route → dedupe gate → extract → synthesize → judge → publish
```
- `ingest` emits items: `{ kind, url, raw }`
- `route` adds `skill` (which extractor handles it)
- `dedupe gate` drops any item whose key is already `extracted` (manifest) or seen this run
- `extract` writes raw content to `kb/full/<key>.{txt,md,json}`
- `synthesize` writes `kb/highlights/<key>.md` (TL;DR / highlights / deep)
- `judge` approves, or loops back to `synthesize` (max 2 retries)
- `publish` updates `manifest.json` + `cost_ledger.jsonl`

## 2. Module responsibilities (by capability, not filename)
| Capability | Inputs | Outputs | LLM? |
|------------|--------|---------|------|
| Orchestrator | config, manifest, ledger | dispatch + budget decisions | brain |
| Ingest adapter (per channel) | channel handle/keys | `{kind,url,raw}[]` | none |
| Router | item | item + `skill` | none (LLM only for ambiguous) |
| Dedupe | item key | seen / new | none |
| Extractor (per skill) | `{url}` | files in `kb/full/` | none |
| Synthesis | full content | `kb/highlights/<key>.md` | brain |
| Judge | source + draft | pass / revise | judge |
| Cost ledger | per-call usage | `cost_ledger.jsonl`, budget gate | none |

## 3. Shared schemas (JSON/YAML — consumed identically by any runtime)

### manifest entry (`manifest.json`, keyed by source key e.g. youtube id)
```json
{
  "<key>": {
    "source_url": "https://youtu.be/<id>",
    "content_hash": "sha256-16",
    "full_paths": { "txt": "...", "md": "...", "json": "..." },
    "status": "extracted",
    "ts": "ISO-8601"
  }
}
```

### cost ledger line (`cost_ledger.jsonl`, one JSON object per run)
```json
{ "ts": "ISO-8601", "items_processed": 0, "items_skipped_dedupe": 0,
  "free_tool_calls": 0, "llm_tokens": 0, "tool_cost_usd": 0.0 }
```

### config (`config.yaml`) — shared by both runtimes; keys are the public interface
`input.source_dir`, `input.source_list`, `output.kb_dir/full_dir/highlights_dir/manifest/formats`,
`youtube.transcript_script/timestamps/throttle.*`, `cost.token_budget_per_run/ledger`,
`synthesis.levels/judge_max_retries`.

## 4. Stable interfaces (same signatures, any language)
- `manifest.seen(key) -> bool` · `manifest.record(key, url, hash, paths, status)`
- `throttle.run_with_retry(cmd) -> (ok, output)` with min_delay, jitter, backoff, max_retries
- `costLedger.over_budget() -> bool` · `costLedger.add(...)` · `costLedger.flush() -> run`
- `classify(line) -> (kind, key)` (regex; YouTube in V1)
- `ModelProvider.complete(prompt, modelTier, maxTokens) -> { text, usage{input,output} }`
  - `SubscriptionProvider` (Claude MAX via `claude -p`) and `ApiProvider` (`ANTHROPIC_API_KEY`)
    both implement this; `selectProvider(config)` validates env guardrails and returns one.
  - This is the ONLY layer that differs between "run on Max" and "run via API key." Everything
    else in the pipeline is provider-agnostic. See `04-execution-modes.md`.

## 5. PR plan by capability (extension-agnostic)
PR-1 core (manifest+throttle+ledger+config) · PR-2 youtube-extract+ingest · PR-3 synthesize ·
PR-4 documents · PR-5 evaluator-optimizer · PR-6 evals · PR-7 gdrive · PR-8 github-repo ·
PR-9 router · PR-10 deep(cost-gated) · PR-11 cross-linking · PR-12 telegram ·
PR-13 whatsapp(paid) · PR-14 scheduler · PR-15 skill-curator.

Each PR is defined by *capability + Definition of Done*, so the same PR ships in whichever
language the runtime is built in. The language-specific file layout lives in
`01-detailed-design-python.md` / `01-detailed-design-typescript.md`.
