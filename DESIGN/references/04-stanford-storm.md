# Reference: STORM / Co-STORM (stanford-oval/storm)

- **Author / org:** Stanford OVAL (Open Virtual Assistant Lab). Reputable: academic, EMNLP-published (Co-STORM, EMNLP 2024).
- **Type:** LLM-powered knowledge-curation system that writes Wikipedia-style, cited
  articles from scratch. Python, built on **DSPy** (Declarative Self-improving Python).
- **GitHub stars:** ~**14k+** (verified 2026-06-21; one analysis reported "over 14,000
  stars / 1,300 forks". Treat as "~14k", counts drift).
- **Primary URL:** https://github.com/stanford-oval/storm
- **License:** confirm on the repo before reuse (commonly MIT for this project — verify).

## The pattern (why it matters for "organize like a movie / levels of understanding")
STORM splits long-form generation into a **pre-writing** stage and a **writing** stage,
via four modules:
1. **Knowledge Curation** — gather broad coverage on the topic.
2. **Outline Generation** — build a hierarchical outline (the reading order / structure).
3. **Article Generation** — populate the outline from gathered sources.
4. **Article Polishing** — refine for presentation.

**Co-STORM** adds a `KnowledgeBase` data class that structures retrieved info into a
**concept-oriented hierarchy** (shown as a **mind map**) — i.e. exactly the "different
levels of understanding" and ordered concept introduction you asked for.

## How it maps to ChainAIM
This is the model for our **Synthesis subagent** and the V4 "cohesive reading" goal:
outline → write → polish gives the movie-like ordering; Co-STORM's concept hierarchy gives
the TL;DR / highlights / deep levels and the cross-linked mind-map. We do not need STORM's
web-research front (we already have extraction skills) — we reuse its *curation/structuring*
ideas on top of content we extracted for free.
