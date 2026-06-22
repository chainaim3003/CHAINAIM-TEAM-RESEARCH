# ChainAIM Deep Research Agent — Conceptual Design

> Scope: **language-independent.** Applies to every runtime (Python, TypeScript, future stacks). See `language-portability-audit.md`.

> Status: DRAFT for confirmation. Nothing here is on the production filesystem yet.
> Acronyms expanded at first use; full glossary at the end.

## 1. Design philosophy (the one rule everything follows)

Do as little with the LLM (Large Language Model) as possible. Extraction is done by
**free deterministic tools** (the skills already on disk). The LLM is used only as a
**brain** (planning, synthesis) and as a **judge** (quality gate). We never pay for what
a free script can do, and we never spawn parallel LLM subagents until cost demonstrably
justifies it.

This is a direct application of Anthropic's *Building Effective Agents* guidance:
"add complexity only when it demonstrably improves outcomes." See
`references/01-anthropic-building-effective-agents.md`.

## 2. Version roadmap (cost-conscious first, expensive patterns deferred)

| Ver | Scope | Agentic complexity | Cost profile |
|-----|-------|--------------------|--------------|
| **V1** | One channel (local / GitHub input dir) → YouTube transcript → KB highlights. Dedupe + throttle + cost ledger. | Deterministic pipeline + 1 LLM synthesis step | Near-zero. Extraction free; one synthesis pass on Max. |
| **V2** | Add documents (PDF/DOCX/PPTX via markdown-converter). Add the **evaluator-optimizer loop** (LLM-as-judge). Leveled output: TL;DR / highlights / deep. | + LLM judge + bounded loop | Low. Judge is cheap; loop capped at 2 retries. |
| **V3** | Multi-channel ingest: Google Drive (gog-cli), GitHub-repo understanding (READMEs, llms.txt, SKILL.md → agent-friendly artifacts). | + routing brain for ambiguous items | Low–medium. Routing uses Haiku. |
| **V4** | Breadth-first deep research: STORM-style outline→write→polish; cross-linked "movie-order" reading; optional **orchestrator-worker parallel subagents**. | Full orchestrator-worker (the Anthropic 15x pattern) | **High — cost-gated.** Only runs when budget allows; hard token ceiling. |
| **V5** | Chat-channel triggers (Telegram; WhatsApp via Twilio — paid, approval-gated). Scheduling / event triggers. Skill-curation agent: generate skills from research by licensing/usage/cost; fold best practices into org CLAUDE.md. | + curator agent + schedulers | Medium. Twilio is the only hard paid dependency. |

We ship value at V1 in 1–2 days. V4 (the expensive multi-agent pattern) is opt-in and
guarded by a token budget — you turn it on only when a run's value justifies the spend.

## 3. The agent map (who is an agent, what they hold, who they call)

LLM-as-brain = ✅brain.  LLM-as-judge = ⚖️judge.  No LLM = ⚙️deterministic.

### Orchestrator Agent  ✅brain  (the only always-on LLM)
- **Role:** plan the run, route items, enforce the budget, integrate worker outputs,
  decide done/continue. (Maps to Anthropic "lead researcher" / orchestrator-workers.)
- **Skills/Tools:** filesystem read/write; dedupe manifest; cost ledger; dispatch to workers.
- **Resources:** `config.yaml`, `manifest.json`, `cost_ledger.jsonl`, `CLAUDE.md`.
- **Calls:** Ingest workers → Router → Extraction skills → Synthesis subagent → Judge subagent.
- **Cost:** main token consumer (planning + integration). Runs on Claude Max via Claude Code.
- **Model:** Sonnet by default; Opus only for hard integration in V4.

### Ingest Workers  ⚙️deterministic  (no LLM)
- **Role:** pull the source list from a channel, normalize to `{kind, url, raw}` items.
- **Adapters / Tools:** local-dir, github-checkout-dir (V1); `gog-cli` for Drive (V3);
  Telegram Bot API, Twilio WhatsApp API (V5).
- **Resources / variable cost:** API keys per channel. gog-cli/Telegram free; **Twilio paid**.

### Router  ⚙️deterministic for known types · ✅brain only for ambiguous
- Regex resolves YouTube / GitHub / known file extensions → **free**.
- LLM classifies only bare/ambiguous links. **Model: Haiku** (cheapest, high volume).

### Extraction Skills  ⚙️deterministic  (free)
- `youtube-transcript` (free, throttled), `markdown-converter`/markitdown (free),
  `context7` (free tier), `beautiful-mermaid` (free), `tavily` web search (free tier).
- **Variable cost / expiry risk:** tavily & context7 keys have free tiers that can
  change or expire → the agent must warn before they lapse.

### Synthesis Subagent  ✅brain
- **Role:** raw content → leveled, hyperlinked KB entry, ordered for cohesive reading
  (introduce concepts in order; chronological where the source is). Maps to STORM's
  outline → write → polish. See `references/04-stanford-storm.md`.
- **Tools:** read extracted full content; write `kb/highlights/*.md`; cross-link existing entries.
- **Model:** Sonnet for TL;DR + highlights; Opus only for the "deep" narrative level.

### Judge Subagent  ⚖️judge  (evaluator-optimizer)
- **Role:** check the synthesized entry against the source: (1) coverage, (2) fidelity
  (no hallucinated claim), (3) link validity. Maps to Anthropic's evaluator-optimizer
  pattern and Anthropic Research's separate citation pass.
- **Model:** Sonnet (judging is cheaper than generating).

### Skill-Curator Agent  ✅brain  (V5)
- **Role:** from accumulated research, propose new reusable skills; rank by licensing,
  usage frequency, and cost; merge best practices into the organizational `CLAUDE.md`.

## 4. Loops — where they make sense, and what stops them

| Loop | Where | Definition of Done (DoD) | Loop breaker | Loop cost / exit-on-cost |
|------|-------|--------------------------|--------------|--------------------------|
| **Evaluator-optimizer** | Synthesis ↔ Judge | Judge passes coverage + fidelity + links | Max 2 retries → publish with `needs-review` | Up to 3× synthesis tokens. If run budget would be exceeded mid-loop, publish current best + flag, stop. |
| **Deep-research recursion** (V4) | Orchestrator spawns sub-questions, recurses by depth/breadth (STORM / GPT-Researcher tree) | Coverage threshold met OR depth cap reached | Max depth + max subagents + token budget | The expensive loop. Hard token ceiling; orchestrator refuses to spawn a subagent it can't afford. |
| **Ingest / schedule** | Cron or event trigger | Manifest shows all sources extracted | Dedupe gate — never re-process a seen source | No LLM cost; idempotent. |

**Cost tracker + exit-on-cost (applies to every LLM loop):** before each LLM call the
orchestrator checks projected tokens against the remaining run budget
(`cost.token_budget_per_run`). If the call would exceed it, the orchestrator writes a
checkpoint listing unfinished items and stops cleanly. Every run reports tokens spent
(this run) and cumulative, plus items processed vs. skipped-by-dedupe.

## 5. Where evals (evaluations) are required

- **Judge as eval (per item):** the evaluator-optimizer check above is a lightweight,
  per-entry eval. Required from V2 on.
- **Regression eval (per release):** a small fixed set of source→expected-highlights
  pairs, run before merging a PR (Pull Request) that touches synthesis prompts, so a
  prompt change can't silently degrade quality. Required from V2.
- **Routing eval (V3+):** a labeled set of ambiguous links → expected kind, to keep the
  Haiku router honest as new source types are added.

## 6. When to pay for the Anthropic multi-agent (15x) pattern

Anthropic's multi-agent research system beats a single agent by ~90% on their internal
research eval but costs ~15× the tokens of a normal chat (see
`references/02-anthropic-multi-agent-research.md`). For ChainAIM that tradeoff is only
worth it in **V4**, for genuinely breadth-first questions where one context window can't
hold the material. Default stays single-agent. The orchestrator-worker code path is
behind a `--deep` flag and a token ceiling.

## Glossary
LLM Large Language Model · RAG Retrieval-Augmented Generation · DoD Definition of Done ·
PR Pull Request · KB Knowledge Base · MCP Model Context Protocol · API Application
Programming Interface · CLI Command-Line Interface · SDK Software Development Kit ·
DSPy Declarative Self-improving Python (the framework STORM is built on) · MTok Million
Tokens · TTL Time To Live · CI Continuous Integration · SLA Service Level Agreement.
