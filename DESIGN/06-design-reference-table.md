# Design Reference — Tables (latest design)

Role key: **BRAIN** = LLM plans/generates · **JUDGE** = LLM evaluates · **det** = deterministic, no LLM (free)

## A. Components — agents, sub-agents, workers

| # | Component | Role | Skills | Tools | Resources | Memory | Model | Calls / called-by |
|---|-----------|------|--------|-------|-----------|--------|-------|-------------------|
| — | Trigger | det | schedule/fire | cron · CLI · webhook | — | — | — | → Orchestrator |
| 0 | **Orchestrator Agent** | BRAIN | plan · delegate · enforce budget · decide done | filesystem · manifest · cost-ledger · provider-selector | config.yaml | manifest.json · cost_ledger.jsonl · checkpoint | Sonnet (Opus in V4) | calls 1–5; called by Trigger |
| 1 | Ingest + Spine | det | pull list · normalize | channel adapters | input dir / keys | — | none | called by Orch |
| 1 | Extractors | det | extract content | youtube-transcript · markitdown · context7 · mermaid | kb/full | — | none | called by Orch |
| 1 | Dedupe gate | det | seen/new check | manifest | manifest.json | done-set | none | gate before extract |
| 2 | **Sub-agent · Router** | BRAIN | classify ambiguous links | — | synth/router.md | — | Haiku | called by Orch (ambiguous only) |
| 3 | **Sub-agent · Synthesis** | BRAIN | outline→write→polish · level · cross-link | read full · write highlights | synth/synthesize.md | existing highlights | Sonnet / Opus(deep) | calls Judge |
| 4 | **Sub-agent · Judge** | JUDGE | coverage · fidelity · links | read source+draft | synth/judge.md | — | Sonnet | loops to Synthesis |
| 5 | Sub-agent · Deep-research (V4) | BRAIN | breadth-first · spawn parallel subagents | search · subagent dispatch | — | shared scratch | Sonnet/Opus | gated by --deep |
| 5 | Sub-agent · Skill-curator (V5) | BRAIN | propose/rank skills · update org CLAUDE.md | filesystem | research corpus | — | Sonnet | called on schedule |
| — | Publish | det | write KB + ledger | filesystem | kb/* | manifest.json | none | terminal |

## B. Orchestration, loops, exits

| Loop / mechanism | Where | Definition of Done (DoD) | Loop breaker | Cost behavior |
|------------------|-------|--------------------------|--------------|---------------|
| Evaluator-optimizer | Synthesis ↔ Judge | coverage + fidelity + links pass | max 2 retries → publish `needs-review` | ≤3× synth tokens; exit-on-cost publishes best + stops |
| Deep recursion (V4) | Deep-research subagents | coverage threshold or depth cap | max depth + max subagents + token ceiling | won't spawn an unaffordable subagent |
| Ingest / schedule | Trigger → spine | manifest shows all sources extracted | **dedupe gate** (never re-process) | zero LLM cost; idempotent |
| Cost ceiling | every LLM call | n/a (guard) | budget exceeded → checkpoint + stop | the universal exit-on-cost |

Pattern: **orchestrator-worker**. V1–V3 = workflow (code is the caller, LLM the callee). V4 `--deep` = the LLM may drive, fenced by flag + ceiling.

## C. Evals

| Eval | When | Checks | Introduced |
|------|------|--------|------------|
| Per-item judge | every synthesized entry | coverage · fidelity · links | V2 |
| Pre-merge regression | before merging a synthesis-prompt PR | fixed source→expected pairs don't regress | V2 |
| Routing eval | when adding source types | ambiguous link → expected kind | V3 |

## D. Cost & model routing (verify rates at claude.com/pricing — they drift)

| Model | ~Input/Output per MTok | Use for | Why |
|-------|------------------------|---------|-----|
| Haiku | ~$1 / ~$5 | Router (ambiguous links), cheap checks | cheapest |
| Sonnet | ~$3 / ~$15 | default synthesis + judge | best quality/$ |
| Opus | ~$5 / ~$25 | "deep" level + hard V4 integration | highest capability, used sparingly |

Levers: output = 5× input (control output length) · cache reads ≈ 0.1× input (keep CLAUDE.md lean).

## E. Execution modes (the swappable Model Provider)

| | provider: subscription | provider: api |
|---|------------------------|----------------|
| For | your testing / internal (one beneficiary) | dev of agents / serving others |
| Auth | Claude MAX OAuth; headless via `CLAUDE_CODE_OAUTH_TOKEN` | `ANTHROPIC_API_KEY` (Commercial Terms) |
| Invocation | `claude -p` | Anthropic API / SDK |
| Billing | Max pool / non-interactive credit pool | per-token, full $ |
| Multi-tenant | NOT allowed | allowed |
| Startup guard | `ANTHROPIC_API_KEY` must be UNSET | key must be SET; `deployment: product` forces this |

## F. Versions & gating

| Ver | Scope | Agentic complexity | Cost |
|-----|-------|--------------------|------|
| V1 | 1 channel → YouTube → KB highlights; dedupe+throttle+ledger | det pipeline + 1 synth pass | near-zero |
| V2 | + documents; + evaluator-optimizer loop; leveled output | + judge + bounded loop | low |
| V3 | + Drive, GitHub-repo understanding; + Router | + routing brain | low–med |
| V4 | breadth-first deep research (parallel subagents); cross-linked reading | full orchestrator-worker (~15×) | HIGH — cost-gated |
| V5 | Telegram (+WhatsApp paid); scheduling; skill-curator; org CLAUDE.md | + curator + schedulers | med |

## G. Acronyms
LLM Large Language Model · DoD Definition of Done · KB Knowledge Base · PR Pull Request ·
API Application Programming Interface · MTok Million Tokens · MCP Model Context Protocol ·
det deterministic · BYOK Bring Your Own Key.
