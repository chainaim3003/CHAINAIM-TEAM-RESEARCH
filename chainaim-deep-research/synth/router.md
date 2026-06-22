# Router Prompt (SHARED) — ambiguous-link classification only

> Used by: the LLM Router in V3 (DESIGN/06-design-reference-table-v2.md, row Router).
> Model: Haiku (cheapest; high volume). This is ONLY invoked for links that the regex
> classifier in `scripts/orchestrate.py::classify` could NOT resolve. Known types
> (YouTube, GitHub, known extensions) are routed for FREE by regex — never sent here.

## Input
A single bare/ambiguous URL or string.

## Task
Classify it into exactly one known `kind`, choosing the extractor that should handle it.

Known kinds (V3 set): `youtube`, `github_repo`, `document` (pdf/docx/pptx), `gdrive`,
`webpage`, `unknown`.

## Output (strict)
Return JSON only:
```json
{ "kind": "<one of the known kinds>", "confidence": 0-1, "reason": "short" }
```
- If confidence < 0.5, return `kind: "unknown"` so the orchestrator can skip + flag rather
  than mis-route. Mis-routing wastes a free extractor call and pollutes the KB; skipping is
  cheaper and safe (dedupe will pick it up once correctly typed).
