# Architecture — Textual Visual v2 (diagrammatic)

Roles:  `[BRAIN]` LLM generates · `[JUDGE]` LLM evaluates · `det` deterministic, free.
Detail (skills/tools/memory) lives in `06-design-reference-table.md` — this is FLOW + LOOPS only.

```
                 TRIGGER  (det)
                      │
                      ▼
              ┌───────────────┐
              │ INGEST · ROUTE│   det · free
              └───────┬───────┘
                      ▼
              ┌───────────────┐   seen
              │  DEDUPE GATE  ├── before ─▶  ✗ SKIP
              └───────┬───────┘     ?         └─ EXIT ① re-work breaker
                      │ new                       (skips before any token)
                      ▼
              ┌───────────────┐
              │    EXTRACT    │   det · free skills
              └───────┬───────┘
                      ▼
              ┌───────────────┐ ◀───────────────╮
              │   SYNTHESIZE  │   [BRAIN]        │
              └───────┬───────┘                  │   ↺ LOOP ①
                      ▼                           │   evaluator-optimizer
              ┌───────────────┐                  │   fail ▶ revise
              │     JUDGE     │   [JUDGE] ──fail──╯   retry ≤ 2, then
              └───────┬───────┘                      publish ⚠ needs-review
                      │ pass   (DoD: coverage + fidelity + links)
                      ▼
              ┌───────────────┐
              │    PUBLISH    │   det
              └───────────────┘

   every [BRAIN]/[JUDGE] call ─▶ MODEL PROVIDER { subscription | api }
                                        └─▶ COST TRACKER ─ over budget? ─▶ EXIT ② stop+checkpoint
```

## Loops & exits at a glance

```
  ↺ LOOP ①  evaluator-optimizer   SYNTHESIZE ─▶ JUDGE ─fail─▶ SYNTHESIZE
                                  breaker: retry ≤ 2  →  publish needs-review

  ↺ LOOP ②  deep research (V4)    ORCHESTRATOR ─▶ ‖ parallel subagents ‖ ─▶ ORCHESTRATOR
                                  breaker: depth + subagent + token caps (gated by --deep)

  ⟳ RE-RUN  schedule/event        TRIGGER ─▶ pipeline ─▶ (next TRIGGER)
                                  breaker: dedupe gate makes repeats free (idempotent)

  ✗ EXIT ①  dedupe               source already extracted ─▶ skip (no token spent)
  ✗ EXIT ②  cost ceiling         projected tokens > budget ─▶ checkpoint + stop
```

## One-line mental model
`det` code is the **caller**; the **LLM is a callee** invoked only at SYNTHESIZE / JUDGE
(and Router for ambiguous links). The single token-spending loop is LOOP ①, bounded to 2
retries. Everything else is gated by dedupe (EXIT ①) and the cost ceiling (EXIT ②).
