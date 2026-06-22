# Reference: Anthropic — "How we built our multi-agent research system"

- **Author / org:** Anthropic engineering. Reputable: the canonical production deep-research write-up.
- **Type:** Engineering blog post (architecture + lessons). No repo/stars; it is the
  reference the open-source community re-implements (e.g. The-Swarm-Corporation/AdvancedResearch).
- **Primary URL:** https://www.anthropic.com/engineering/multi-agent-research-system
- **Verified:** 2026-06-21 via web search; corroborated by ZenML LLMOps DB, a Deep Research survey (arXiv 2512.02038), and multiple analyses.
- **License:** blog (read freely).

## The pattern
**Orchestrator-worker for breadth-first research.** A **lead agent** plans, saves the plan
to memory (to survive context-window limits), then spawns **3–5 parallel subagents**, each
with its **own context window and tool access**. Subagents return condensed findings; a
**separate citation/synthesis pass** assembles the final answer. Workers never talk to each
other — every decision lives in the orchestrator (constrained topology, easy to reason about).

## The numbers that govern when to use it
- ~**90.2%** improvement over single-agent Claude Opus on Anthropic's internal research eval.
- Costs ~**15×** the tokens of a normal chat. Token usage alone explained ~**80%** of
  performance variance in their browsing eval.

## How it maps to ChainAIM
This is the **V4** target, and *only* V4 — for genuinely breadth-first questions whose
material exceeds one context window. The 15× cost is why it sits behind a `--deep` flag and
a hard token ceiling. For everyday ingest→extract→summarize, a single agent is far cheaper
and sufficient. We borrow two ideas earlier than V4: plan-to-memory (our manifest/checkpoint)
and the separate quality pass (our Judge subagent).
