# Architecture — Visual v3 (layered / business-architecture style)

Read it as three tiers, top to bottom: **what comes in → what the agent does → what comes out.**
(A rendered color version of this diagram was produced in chat; this is the portable copy.)

```
━━ TIER 1 · INPUT CHANNELS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   [ GitHub dir ]   [ Google Drive ]   [ Telegram ]   [ WhatsApp ]   [ Local folder ]

   Each channel supplies a LIST FILE of sources, e.g.:
        YouTube URLs · documents (pdf/docx/pptx) · GitHub links · mermaid diagrams · (extensible)

                         │   all channels feed ONE queue
                         ▼
━━ TIER 2 · RESEARCH AGENT  ·  runs on Claude MAX (you)  OR  API key (product) ━━━

      De-duplicate ──▶ Extract ──▶ Summarize ⇄ Check quality ──▶ (approved)
        det · skip      det · free   [AI BRAIN]    [AI JUDGE]
                                         ▲              │
                                         └── fail ↺ retry ≤ 2 ──┘ → publish ⚠ needs-review

   • Free skills do extraction:  youtube-transcript · doc→markdown (markitdown) · repo/llms.txt reader
   • The AI is used ONLY at "Summarize" and "Check" — everything else costs nothing.
   • Early EXITS that stop a run:   de-duplicate (already done)   ·   cost ceiling (over budget)
   • The ONE repeating loop:        Summarize ⇄ Check  (the quality loop, max 2 retries)

                         │   approved entries
                         ▼
━━ TIER 3 · KNOWLEDGE BASE (output) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   [ Full content ]   [ Highlights · 3 levels ]   [ Index / manifest ]   [ Cost ledger ]
```

## How to read it (one paragraph)
Sources arrive from any channel (Tier 1) and land in one queue. The agent (Tier 2) first
**throws away anything already done** (de-duplicate), then **extracts the content for free**,
then **summarizes it with the AI brain** and **has the AI judge check the summary**. If the
check fails, it loops back and tries again — at most twice. Approved results are written to the
**knowledge base** (Tier 3). The AI is only ever used in the two purple/amber steps; the loop
between them is the only thing that repeats, and two safety exits (duplicate, or over budget)
can stop a run early.

## Why this shape (conceptual-diagram best practices used)
- **Tiers/bands** (input → process → output) — the standard layered architecture layout.
- **Channels grouped** in one band so adding a channel doesn't change the rest.
- **Color/role tags** kept to four meanings only: free/deterministic, AI brain, AI judge, data.
- **One loop drawn, not described** — the `⇄ … ↺ retry ≤ 2` is the single repeat; exits are labeled.
- Detail (skills, tools, memory, models, cost) lives in the table doc, not the picture.
