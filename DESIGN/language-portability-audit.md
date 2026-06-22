# Language Portability Audit

> Purpose: state exactly how much of this design is language-independent, and what gets a
> `-python` / `-typescript` variant. Naming convention: language-independent docs have no
> suffix; language-specific docs end in `-python` or `-typescript`.

## Verdict: the architecture is language-independent; only the implementation binds to a language.

The design is split so that ~80% (everything conceptual) is portable across Python,
TypeScript, and future stacks, and the language-specific ~20% is isolated into clearly
suffixed docs and the code itself.

## Classification of every artifact

| Artifact | Independent / Dependent | Action |
|----------|-------------------------|--------|
| `00-conceptual-design.md` (agent map, versions, loops, evals, DoD) | **Independent** | keep as-is |
| `02-cost-model.md` (Claude Max metering, model routing, KEY costs) | **Independent** (about Claude billing, not impl language) | keep as-is |
| `references/*.md` (the 4 reference architectures) | **Independent** patterns (note: GPT-Researcher & STORM are themselves Python, but the *patterns* we borrow are language-agnostic) | keep; note impl language inside |
| Data-flow contract + module responsibilities + PR plan | **Independent** | extracted into `01-architecture-contract.md` |
| Project file tree + file→module mapping + deps + build/run | **Dependent** | split into `01-detailed-design-python.md` and `-typescript.md` |
| V1 runnable code (orchestrate / manifest / throttle / cost_ledger) | **Dependent** (currently Python reference impl) | a TypeScript port follows the same contract |
| `config.yaml` | **Independent** (YAML config consumed by either runtime) | shared by both |
| `CLAUDE.md` engineering guardrails | **Mostly independent**; the TS/JS no-drift rule is **TypeScript-specific** | guardrails section added; TS rule flagged TS-only |
| `synth/*.md`, `evals/fixtures` (prompts + expected outputs) | **Independent** (prompts and fixtures are plain text/data) | shared by both |

## What stays identical across languages (the stable core)
- The **data-flow contract**: `ingest → route → dedupe → extract → synthesize → judge → publish`.
- The **module responsibilities** (what each component does, its inputs/outputs).
- The **manifest schema**, **cost-ledger schema**, and **config schema** (JSON/YAML — language-neutral).
- The **prompts** (`synthesize.md`, `judge.md`, `router.md`) and **eval fixtures**.
- The **PR plan** by capability (PR-1…PR-15) — the *what*, not the file extensions.

## What is language-specific (isolated)
- File/folder names and extensions (`.py` vs `.ts`).
- Dependency manager and build step (uv/pyproject vs npm/tsc).
- Runtime invocation (`uv run …` vs `node dist/…` / `tsx …`).
- The TS/JS no-drift rule (only meaningful where a compile step produces `.js`).

## Extensibility to other stacks (Google / NVIDIA / AWS / blockchain)
Because the contract is expressed as data schemas + prompts + capability boundaries (not
code), a new runtime only has to: (1) read the same `config.yaml`, (2) read/write the same
`manifest.json` + `cost_ledger.jsonl`, (3) shell out to the same free extraction skills,
(4) call the model with the same prompts. That means a future Go (e.g. some cloud/agent
runtimes), Rust (some blockchain tooling), or JVM implementation is a port of the
*adapters*, not a redesign. Any new language gets its own `01-detailed-design-<lang>.md`;
nothing in the independent docs changes.

**Rule going forward:** if a future framework forces a change to the *contract* (schemas,
prompts, capability boundaries), that change is made in the independent docs and propagates
to all language variants — never the reverse.
