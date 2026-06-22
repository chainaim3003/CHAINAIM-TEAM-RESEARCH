# Skill Invocation Model — Way 1 vs Way 2 (language-independent)

> How the agent uses "skills" (the on-disk, free extraction tools). There are two distinct
> invocation mechanisms. The design uses **BOTH, permanently** — but at different layers and
> different versions. Language-independent (applies to the Python and TypeScript runtimes).
> Pairs with `01-architecture-contract.md` and `02-cost-model.md`.
>
> This doc closes a gap: the "do both" decision was recorded in the session log but was not
> previously written into the design proper. The version mapping below is grounded in the
> actual V1 code (`chainaim-deep-research/`), not just intent — see "grounded in code".

## The two ways

| | **Way 2 — deterministic dispatch** | **Way 1 — installed plugin (auto-select)** |
|---|---|---|
| What | Orchestrator **code is the CALLER**; it shells out to a skill's script directly (`uv run <script> <args>`) | Skill is installed as a Claude Code **plugin** (via `marketplace.json`); Claude, in a session, **auto-selects** it by its `SKILL.md` description |
| Who picks the skill | code — regex `classify` → `{kind → skill}` dispatch table | the LLM — matches the request to a `SKILL.md` description |
| Cost | **free** (no tokens to select or to run the skill) | tokens to read `SKILL.md` + decide (selection is itself an LLM act) |
| Determinism | deterministic, repeatable, **schedulable** | non-deterministic (selection can vary run to run) |
| Role | the **permanent engine** of the pipeline | **conversational** use + skill **curation** |
| Versions | **ALL** versions (V1 → V5) — the backbone | **mainly V5** (conversational + skill-curator) |

## Boundary rule (which way, when)
- **Way 2 is the permanent engine.** Every scheduled / headless / pipeline run uses Way 2,
  because those runs must be deterministic and free to *select and invoke* skills. Way 2 is
  what the `extract/*` modules do, driven by the `{kind → skill}` dispatch table (a single
  hard-wired extractor in V1; generalized in V3).
- **Way 1 is for conversational + curation only.** A human — or the V5 skill-curator — in a
  Claude Code / Max session lets Claude pick an installed skill by description. Way 1 is
  **never** placed on the scheduled/headless path: auto-selection isn't repeatable, so it
  cannot be the engine.
- The **V3 LLM Router is NOT Way 1.** It classifies only *ambiguous* links, but the code
  calls the router and then dispatches deterministically — selection stays in the pipeline's
  control. Known types never reach the LLM at all (regex resolves them, free).

## What each version actually uses (grounded in code)

| Ver | Way 2 (dispatch) | Way 1 (plugin auto-select) | Basis |
|-----|------------------|----------------------------|-------|
| **V1** | **YES — sole mechanism** | **NO** (not used, not required) | code path below |
| V2 | YES (+ documents extractor) | NO | same dispatch; adds doc→markdown extractor |
| V3 | YES (+ generalized `{kind→skill}` table + LLM Router for ambiguous) | NO | Router is code-called, then deterministic dispatch |
| V4 | YES | NO | deep research spawns subagents; extraction still dispatch-driven |
| V5 | YES (engine unchanged) | **YES** — conversational + skill-curator | curator installs/proposes skills via `marketplace.json`; Claude auto-selects in chat |

### V1 — the answer, verified against the official codebase
**V1 needs only Way 2.** Evidence from `chainaim-deep-research/`:
- The pipeline's only skill call is `extract/youtube.py::build_cmd` → `["uv", "run",
  <transcript_script>, source]`, executed via `throttle.run_with_retry` (subprocess). Pure
  Way 2: the code is the caller.
- `scripts/orchestrate.py` never calls `provider.complete()`; the V1 pipeline spends **zero
  LLM tokens**, so nothing in it can be auto-selecting a skill.
- `config.yaml` wires the skill purely by script path (`youtube.transcript_script`). There is
  **no** plugin / marketplace install in V1.
- V1's manual synthesis (`CLAUDE.md`) uses Claude as a **brain** over already-extracted
  `kb/full/*.txt`; it does **not** auto-select any extraction skill, so it is not Way 1 either.

Caveat (precision): V1's dispatch is a single hard-wired `if kind == "youtube"` branch — the
Way-2 *mechanism* for one skill. The full `{kind → skill}` table arrives in V3. Either way it
is Way 2, never Way 1.

## Why keep BOTH (permanently)
- **Way 2** gives a free, deterministic, schedulable engine — the thing you can cron and trust.
- **Way 1** gives ergonomic, conversational reach and is the natural surface for the V5
  skill-curator to install/propose skills and have Claude use them ad hoc.
- They share the **same** skills on disk (one `SKILL.md` + script per skill): Way 2 calls the
  script; Way 1 installs the same folder as a plugin. No skill is duplicated — the difference
  is purely *who selects and how it is invoked*.

## Cross-references
- Dispatch mechanics + `classify` contract: `01-architecture-contract.md` (s1, s4).
- Free-skill cost rationale (why selection must be free on the engine path): `02-cost-model.md`.
- Skill packaging that enables Way 1: the skills repo's `marketplace.json` / `plugin.json`.
- Skill-curator (the main Way-1 consumer): `00-conceptual-design.md` (s3),
  `06-design-reference-table.md` (Component row 5, V5).
