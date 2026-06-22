# Judge Prompt (SHARED) — evaluator-optimizer gate

> Used by: the Judge subagent in the evaluator-optimizer loop (V2+; Loop ① in
> DESIGN/06-design-reference-table-v2.md). Model: Sonnet (judging is cheaper than
> generating). In V1 this is a manual eyeball check; the loop is not yet scripted.

## Inputs
- The SOURCE: `kb/full/<key>.txt`.
- The DRAFT: the synthesized `kb/highlights/<key>.md`.

## Evaluate on three axes (all must pass)
1. **Coverage** — does the draft capture the source's main points (no major omission)?
2. **Fidelity** — is every claim in the draft supported by the source (no hallucination)?
3. **Links** — are cross-links valid (targets exist) and relevant (not spurious)?

## Output (strict)
Return JSON only:
```json
{ "pass": true|false, "coverage": 0-1, "fidelity": 0-1, "links_ok": true|false,
  "issues": ["..."], "fix_hint": "one concrete instruction for the next synthesis pass" }
```

## Loop control
- `pass: true`  -> publish the entry.
- `pass: false` -> return to synthesis with `fix_hint`. Max `synthesis.judge_max_retries`
  (default 2) retries; then publish best draft with a `needs-review` flag and stop.
- Before any retry, the orchestrator checks the token budget; if a retry would breach it,
  publish current best + flag and stop (DESIGN/00-conceptual-design.md s4).
