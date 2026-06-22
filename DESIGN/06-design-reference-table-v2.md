# Design Reference — Tables v2 (loops made explicit)

Role key: `BRAIN` LLM generates · `JUDGE` LLM evaluates · `det` deterministic (free).

## ★ LOOPS & EXITS (read this first)

Each loop is drawn as `from ─▶ … ─▶ back-to`. The breaker is what stops it.

| | Loop / exit | Flow (the cycle) | Repeats until (DoD) | Breaker | On break |
|---|-------------|------------------|---------------------|---------|----------|
| ↺ | **Loop ① evaluator-optimizer** | `SYNTHESIZE ─▶ JUDGE ─fail─▶ SYNTHESIZE` | judge passes coverage + fidelity + links | **retry ≤ 2** | publish with `needs-review` |
| ↺ | **Loop ② deep research** (V4) | `ORCHESTRATOR ─▶ ‖subagents‖ ─▶ ORCHESTRATOR` | coverage / depth target met | depth + subagent + **token** caps (`--deep`) | stop, return partial |
| ⟳ | **Re-run** schedule/event | `TRIGGER ─▶ pipeline ─▶ next TRIGGER` | (continuous) | **dedupe gate** (idempotent) | only new items processed |
| ✗ | **Exit ① dedupe** | gate before EXTRACT | — | source already extracted | skip before any token |
| ✗ | **Exit ② cost ceiling** | before every LLM call | — | projected tokens > budget | checkpoint + stop |

Only **Loop ①** spends tokens in V1–V3. **Loop ②** is the expensive one and is cost-gated.

## A. Components (with loop membership)

| Component | Role | In loop? | Model | Key skills/tools |
|-----------|------|----------|-------|------------------|
| Orchestrator | BRAIN | drives Loop ② (V4) | Sonnet/Opus | plan · delegate · budget · provider-select |
| Ingest + Spine | det | feeds Re-run | none | adapters; dedupe gate (Exit ①) |
| Extractors | det | — | none | youtube-transcript · markitdown · context7 · mermaid |
| Router | BRAIN | — | Haiku | classify ambiguous links only |
| **Synthesize** | BRAIN | **Loop ① (start)** | Sonnet/Opus | outline→write→polish · cross-link |
| **Judge** | JUDGE | **Loop ① (gate)** | Sonnet | coverage · fidelity · links |
| Deep-research (V4) | BRAIN | **Loop ② (start)** | Sonnet/Opus | spawn parallel subagents |
| Skill-curator (V5) | BRAIN | — | Sonnet | propose/rank skills · update org CLAUDE.md |
| Publish | det | — | none | write KB + ledger |

## B. Cost & model routing (verify rates at claude.com/pricing)

| Model | ~In/Out per MTok | Use for |
|-------|------------------|---------|
| Haiku | ~$1 / ~$5 | Router (ambiguous links) |
| Sonnet | ~$3 / ~$15 | default Synthesize + Judge |
| Opus | ~$5 / ~$25 | "deep" level + V4 integration |

Output = 5× input · cache reads ≈ 0.1× input (keep CLAUDE.md lean).

## C. Execution modes (swappable Model Provider — wraps every BRAIN/JUDGE call)

| | subscription | api |
|---|--------------|-----|
| For | your testing / internal | dev / serving others |
| Auth | Claude MAX (`claude -p`) | `ANTHROPIC_API_KEY` |
| Multi-tenant | no | yes |
| Startup guard | key must be UNSET | key must be SET (`product` forces this) |

## D. Evals

| Eval | When | Tied to |
|------|------|---------|
| Per-item judge | every entry | Loop ① |
| Pre-merge regression | synthesis-prompt PRs | Synthesize |
| Routing eval (V3) | new source types | Router |

## E. Versions

| Ver | Adds | Loops active | Cost |
|-----|------|--------------|------|
| V1 | YouTube → KB; dedupe+throttle+ledger | Exit ①, Re-run | near-zero |
| V2 | documents; **Loop ①**; leveled output | + Loop ①, Exit ② | low |
| V3 | Drive, GitHub-repo; Router | same | low–med |
| V4 | deep research; cross-linked reading | + **Loop ②** | HIGH (gated) |
| V5 | Telegram/WhatsApp; scheduler; curator | same | med |
