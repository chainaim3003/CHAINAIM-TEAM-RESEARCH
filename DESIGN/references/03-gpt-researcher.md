# Reference: GPT Researcher (assafelovic/gpt-researcher)

- **Author / org:** Assaf Elovic (Head of AI at Monday.com; founder context around Tavily). Widely adopted OSS.
- **Type:** Open-source deep-research agent. Python.
- **GitHub stars:** ~**27k** (verified 2026-06-21; sources reported 25k–27.8k across the
  repo activity page, PR #1250, and skill indexes — star counts drift, treat as "~27k").
- **Primary URL:** https://github.com/assafelovic/gpt-researcher
- **License:** confirm on the repo before reuse (commonly Apache-2.0 for this project — verify).

## The pattern
**Planner → Executor → Publisher**, parallelized:
- **Planner** generates the research sub-questions.
- **Executor** agents (crawlers) gather + summarize + source-track per question, in parallel.
- **Publisher** aggregates into a cited report (PDF / DOCX / Markdown).
- **Deep Research mode:** a recursive **tree-like exploration** with configurable
  **depth and breadth**, concurrent branches, and automatic context aggregation.
- Supports **web + local** sources (PDF, CSV, Excel, Markdown, PowerPoint, Word), and
  **MCP** retrievers (GitHub repos, databases) alongside web search.
- Notably ships **per-step cost tracking** (a feature we mirror in `cost_ledger.py`).

## How it maps to ChainAIM
Closest open-source parallel to our requirements. We adopt: per-step cost tracking (V1),
local + multi-format document research (V2), and the depth/breadth-bounded recursive tree
as the concrete shape of our **V4** deep loop (with our own hard token ceiling on top).
The planner/executor/publisher split mirrors our Orchestrator / Extraction+Synthesis / Publish.
