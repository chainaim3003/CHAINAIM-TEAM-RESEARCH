# Detailed Design — Python (`-python`)

> Language-specific. Implements `01-architecture-contract.md`. Pair file: `01-detailed-design-typescript.md`.
> This is the current V1 reference implementation.

## Project structure (Python)
```
chainaim-deep-research/
├── pyproject.toml             # uv-managed deps
├── config.yaml                # SHARED (language-independent)
├── CLAUDE.md                  # SHARED guardrails + agent ops
├── scripts/
│   ├── orchestrate.py         # pipeline driver
│   ├── manifest.py            # dedupe ledger
│   ├── throttle.py            # pacing/backoff
│   ├── cost_ledger.py         # token + budget gate
│   └── provider.py            # ModelProvider: SubscriptionProvider | ApiProvider (+ guardrails)
├── ingest/  local_dir.py · github_dir.py · gdrive.py(V3) · telegram.py(V5) · whatsapp_twilio.py(V5)
├── extract/ youtube.py · document.py(V2) · github_repo.py(V3) · mermaid.py(V3)
├── synth/   synthesize.md · judge.md · router.md      # SHARED prompts
├── evals/   fixtures/ · run_evals.py
└── deep/    deep_research.py(V4)
```

## Tooling
- **Runtime:** Python ≥ 3.10, managed by **uv** (matches the existing youtube-transcript skill).
- **Deps:** declared inline (`# /// script`) for single-file scripts, or in `pyproject.toml`.
- **Run:**
  ```bash
  uv run scripts/orchestrate.py --config config.yaml --dry-run
  uv run scripts/orchestrate.py --config config.yaml --max-videos 5
  ```

## File → contract mapping
| Contract interface | Python file |
|--------------------|-------------|
| `manifest.seen/record` | `scripts/manifest.py` (class `Manifest`) |
| `throttle.run_with_retry` | `scripts/throttle.py` (class `Throttle`) |
| `costLedger.over_budget/add/flush` | `scripts/cost_ledger.py` (class `CostLedger`) |
| `classify` | `scripts/orchestrate.py` |

## Notes
- No build step → no generated artifacts → **no TS/JS-style drift risk** in Python.
- The V1 Python files already exist and pass a dedupe + dry-run smoke test.
