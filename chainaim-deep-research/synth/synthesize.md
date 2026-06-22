# Synthesis Prompt (SHARED)

> Used by: the human in a Claude Code / Max session in V1 (manual synthesis), and by the
> scripted SubscriptionProvider in V2+. Maps to STORM's outline -> write -> polish
> (DESIGN/references/04-stanford-storm.md). Model: Sonnet by default; Opus only for the
> "deep" level (DESIGN/02-cost-model.md).

## Inputs
- The extracted raw content at `kb/full/<key>.txt` (a YouTube transcript in V1).
- The source URL and key.
- Existing entries in `kb/highlights/` (for cross-linking).

## Task
Produce a leveled, hyperlinked KB entry at `kb/highlights/<key>.md` with these sections,
in this order. Introduce concepts before relying on them; follow the source's chronology
where it has one.

1. **TL;DR** (≤ 3 sentences) — the single most useful takeaway.
2. **Highlights** (bulleted) — the key claims/insights, each faithful to the source.
3. **Deep** (only when requested / "deep" level) — a cohesive narrative that orders ideas
   for a first-time reader; cross-link related existing KB entries with relative links.

## Hard rules
- Fidelity over fluency: every claim must be supported by the transcript. Do NOT add facts
  the source doesn't contain. If the transcript is ambiguous, say so rather than inventing.
- Keep output short: output tokens cost 5x input (DESIGN/02-cost-model.md). Prefer the
  TL;DR + Highlights levels; reserve "deep" for sources that justify it.
- Cross-link by relative path to other `kb/highlights/*.md` entries where genuinely related.
- Never modify the raw transcript in `kb/full/` — synthesis only writes to `kb/highlights/`.
