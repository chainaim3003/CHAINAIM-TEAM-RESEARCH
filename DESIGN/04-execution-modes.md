# Execution Modes — run on Claude MAX now, switch to API key later

> Answers: "run from Max for my own testing now; run via Anthropic key when I develop/serve
> others." Verified against Anthropic terms 2026-06-21 — confirm at anthropic.com/legal before relying.

## The whole difference is ONE layer: the Model Provider

Everything in the pipeline (ingest, route, dedupe, extract, judge logic, publish) is
identical in both modes. The only thing that changes is **how the LLM call is made**. So the
design isolates that into a single swappable component selected by `config.model.provider`.

```
... → synthesize → [ Model Provider ] → ... → judge → [ Model Provider ] → ...
                         ▲
        subscription  ───┴───  api
   (Claude MAX, claude -p)   (ANTHROPIC_API_KEY, Commercial Terms)
```

| | `provider: subscription` | `provider: api` |
|---|---|---|
| Who it's for | **You, testing / internal** (one beneficiary) | **Dev of products / serving others** |
| Auth | Claude Code OAuth (your Max seat); headless via `CLAUDE_CODE_OAUTH_TOKEN` | `ANTHROPIC_API_KEY` (Console, Commercial Terms) |
| Invocation | `claude -p` (the sanctioned automation path) | Anthropic API / SDK call |
| Billing | Max pool (interactive) or non-interactive credit pool (headless) | Per-token, full $ visibility, no seat cap |
| Multi-tenant / customers | **Not allowed** ("one human, one subscription, one beneficiary") | **Allowed** (the path for products) |
| Cost ledger field | token estimate | real `est_cost_usd` from usage |

## The two guardrails the runner MUST enforce (cheap, prevents real damage)

1. **Key hygiene / no silent API billing.** If `ANTHROPIC_API_KEY` is set, Claude Code and the
   SDK **prefer it and silently bill the API** even when you meant to use your subscription.
   So on startup:
   - `provider == subscription` → assert `ANTHROPIC_API_KEY` is **unset**; else FAIL loudly
     ("would bill API, not your Max seat — unset it or switch provider").
   - `provider == api` → assert the key **is** set; else FAIL.
2. **One-beneficiary guard.** If `deployment == product`, refuse `provider == subscription`
   (serving others on a personal seat violates terms). Force `api` for any multi-tenant run.

## What this means for V1
V1's core spends **zero** LLM tokens (extraction only). The synthesis step in V1 is you, in a
Claude Code session on Max, following `CLAUDE.md` — i.e. `provider: subscription`, no provider
code needed yet. The Model Provider becomes actual code the moment synthesis is **scripted**
(V2+, or any headless/scheduled run). Designing it now means that switch is a config flag, not
a refactor.

## Interface (language-independent — see 01-architecture-contract.md)
```
ModelProvider.complete(prompt, modelTier, maxTokens) -> { text, usage{input,output} }
  SubscriptionProvider  -> shells to `claude -p` with subscription/OAuth auth
  ApiProvider           -> calls Anthropic API with ANTHROPIC_API_KEY
selectProvider(config) -> validates guardrails above, returns the right impl
```
Both implementations satisfy the same signature, so `synthesize` and `judge` never know which
mode they're in. Adding a future provider (e.g. AWS Bedrock / Google Vertex, which Anthropic
supports for Claude) is a third class implementing the same interface — no pipeline changes.
