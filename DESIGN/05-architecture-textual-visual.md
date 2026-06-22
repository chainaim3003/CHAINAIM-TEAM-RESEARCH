# Architecture — Textual Visual (latest design)

Legend:  [BRAIN] = LLM plans/generates  ·  [JUDGE] = LLM evaluates  ·  (det) = deterministic, no LLM, free

```
TRIGGER  (det) ─ cron schedule · manual CLI · event/webhook · channel message
   │  fires the run (idempotent — safe to re-run; dedupe makes repeats cheap)
   ▼
█ ORCHESTRATOR AGENT ───────────────────────────────────────────── [BRAIN]
│   pattern  : orchestrator-worker.  V1–V3 run as a WORKFLOW (code drives,
│              LLM is CALLED at fixed points).  Only V4 --deep lets the LLM drive.
│   skills   : plan run · delegate to sub-agents · enforce budget · decide done/continue
│   tools    : filesystem · manifest · cost-ledger · model-provider selector
│   resources: config.yaml (all behavior as flags)
│   memory   : manifest.json (the "done set") · cost_ledger.jsonl · run checkpoint
│
├─▶ (1) DETERMINISTIC SPINE — workers, NO LLM, FREE
│        ingest ─▶ route ─▶ dedupe gate ─▶ extract
│        adapters : local-dir · github-dir · gdrive(gog-cli) · telegram · whatsapp(twilio,paid)
│        skills   : youtube-transcript · markitdown · context7 · beautiful-mermaid
│        ▸ dedupe gate = LOOP/RE-WORK BREAKER: a source seen before (manifest
│          or earlier this run) EXITS here before any token is spent.
│        │  only NEW items continue ▼
│
├─▶ (2) SUB-AGENT · Router ───────────────────────────────── [BRAIN · Haiku]
│        role     : classify ambiguous links to the right skill
│        note     : known types (YouTube, GitHub, known extensions) resolved by
│                   regex (free) — the LLM is invoked ONLY when ambiguous.
│
├─▶ (3) SUB-AGENT · Synthesis ──────────────────────── [BRAIN · Sonnet / Opus]
│        skills   : outline → write → polish (STORM pattern); leveled output
│                   = TL;DR / highlights / deep, ordered for cohesive reading
│        tools    : read kb/full · write kb/highlights · cross-link entries
│        resources: synth/synthesize.md (prompt)
│        memory   : existing highlights (for hyperlinking + "movie-order" reading)
│        model    : Sonnet for TL;DR+highlights · Opus ONLY for the "deep" level
│        │
│        ▼   ╭───────────────── EVALUATOR-OPTIMIZER LOOP ─────────────────╮
├─▶ (4) SUB-AGENT · Judge ────────────────────────────────── [JUDGE · Sonnet]
│        checks   : coverage · fidelity (no hallucinated claim) · link validity
│        DoD      : all 3 pass  ─▶ publish
│        on FAIL  : send back to (3) Synthesis to revise  ──▲
│        ▸ LOOP BREAKER : max 2 retries → publish with "⚠ needs-review" banner
│            ╰──────────────────────────────────────────────────────────────╯
│
└─▶ (5) SUB-AGENT · Deep-research  (V4 ONLY) ──────── [orchestrator-worker, BRAIN]
         role     : breadth-first; spawns parallel subagents; recursion by
                    depth/breadth (Anthropic's ~15× pattern, STORM/GPT-Researcher tree)
         ▸ COST GATE : behind --deep flag + a HARD token ceiling; the orchestrator
           refuses to spawn a subagent it cannot afford (loop/cost breaker)

  ── crosscutting (apply to every LLM call above) ───────────────────────────
  MODEL PROVIDER (swappable) :  subscription = Claude MAX via `claude -p`
                                api          = ANTHROPIC_API_KEY (Commercial Terms)
                                ▸ the ONLY layer that differs between "run on Max"
                                  and "run via API key"; pipeline is provider-agnostic
  COST TRACKER  :  before EVERY LLM call → check projected tokens vs run budget
                   ▸ EXIT-ON-COST: if over budget, write checkpoint + STOP cleanly
                   ▸ report tokens (this run + cumulative) and free-tier status
  EVALS         :  per-item judge (above) · pre-merge regression eval on prompts ·
                   routing eval (V3) for the Router

   │  approved entries
   ▼
PUBLISH  (det) ─ NO LLM
   kb/full/        raw extractions (transcripts, converted docs)
   kb/highlights/  leveled, hyperlinked entries
   manifest.json   the done-set (dedupe source of truth)
   cost_ledger.jsonl  tokens + $ per run
```

## How to read the orchestration pattern
- The Orchestrator is the single point of control (orchestrator-worker). Workers/sub-agents
  never talk to each other — every decision routes back through the orchestrator.
- V1–V3 are **workflows**: deterministic code is the caller; the LLM is a callee invoked at
  the Router, Synthesis, and Judge steps only. Everything else spends zero tokens.
- The only **loop** that consumes tokens is the evaluator-optimizer loop (Synthesis↔Judge),
  bounded to 2 retries. The dedupe gate and the cost ceiling are the two non-LLM breakers.
- V4 is the one place the LLM is allowed to **drive** (spawn subagents), and it is fenced by
  the `--deep` flag and a hard token ceiling.
