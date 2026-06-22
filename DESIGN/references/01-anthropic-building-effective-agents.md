# Reference: Anthropic — "Building Effective Agents"

- **Author / org:** Anthropic (Erik Schluntz, Barry Zhang). Reputable: model vendor's own engineering guidance.
- **Type:** Canonical pattern essay (not a repo — so no star count; it is the most-cited
  primer in the field; accompanied by official cookbook code).
- **Primary URL:** https://www.anthropic.com/research/building-effective-agents
- **Verified:** 2026-06-21 via web search; corroborated by Simon Willison, Spring AI docs, multiple practitioners.
- **License:** essay (read freely); cookbook code under Anthropic's repo license — confirm on the repo.

## The patterns (the vocabulary our design uses)
1. **Augmented LLM** — an LLM with retrieval, tools, and memory. Our base unit.
2. **Prompt chaining** — output of one call feeds the next. (Our extract → synthesize → judge.)
3. **Routing** — an initial call sends easy work to a small model (Haiku), hard work to a
   bigger one (Sonnet/Opus). (Our Router + model-by-difficulty cost rule.)
4. **Parallelization** — split a task across concurrent calls, or vote. (V4 only.)
5. **Orchestrator-workers** — a central LLM decomposes a task, delegates to workers,
   synthesizes results; subtasks are decided dynamically, not pre-defined. (Our
   Orchestrator Agent; full form in V4.)
6. **Evaluator-optimizer** — one model generates, another evaluates in a loop until the
   evaluator is satisfied. (Our Synthesis ↔ Judge loop, capped at 2 retries.)

## Why it anchors our design
Its core thesis is our philosophy: start simple, measure, and "add complexity only when
it demonstrably improves outcomes." That is exactly why V1–V3 stay single-agent/
deterministic and the expensive orchestrator-worker pattern is deferred to a cost-gated V4.
