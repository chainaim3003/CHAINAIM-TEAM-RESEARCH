"""provider_smoke.py — one REAL model call through the configured provider (live check).

Why (DESIGN/07-build-plan.md, PR-4): the offline evals prove the parsing/guardrail logic with a
labelled test double; this script proves the real `claude -p` path on YOUR machine (login,
model alias, stdin prompt, JSON output) before summaries (PR-5) depend on it.

Costs: one small call on your Claude Max plan (or API if provider: api). Nothing is written.

Usage (run from chainaim-deep-research/):
    uv run scripts/provider_smoke.py                          # haiku, "Reply with OK"
    uv run scripts/provider_smoke.py --tier sonnet
    uv run scripts/provider_smoke.py --json                   # also test --json-schema output
    uv run scripts/provider_smoke.py --big-kb 120             # 120 KB prompt via stdin (Windows limit test)

Flags (Rule 8):
    --config PATH   config.yaml (default: next to scripts/)
    --tier NAME     tier or role to call (default: haiku)
    --prompt TEXT   prompt text (default: "Reply with exactly: OK")
    --json          additionally run a structured-output call with a tiny JSON schema
    --big-kb N      prepend N KB of filler to the prompt to prove long prompts work (default 0)

Exit codes: 0 success, 2 guardrail failure, 1 provider/call failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from orchestrate import load_config                              # noqa: E402
from provider import ProviderError, select_provider              # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(prog="provider_smoke", description="One live call through the model provider.")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--tier", default="haiku")
    ap.add_argument("--prompt", default="Reply with exactly: OK")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--big-kb", type=int, default=0)
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    try:
        prov = select_provider(cfg)
    except ProviderError as exc:
        print(f"guardrails: FAIL -> {exc}")
        return 2
    prompt = args.prompt
    if args.big_kb > 0:
        filler = ("lorem ipsum dolor sit amet " * 40 + "\n")
        body = (filler * (args.big_kb * 1024 // len(filler) + 1))[: args.big_kb * 1024]
        prompt = f"Ignore the filler text below and {args.prompt[0].lower()}{args.prompt[1:]}\n\n{body}"
    print(f"provider={type(prov).__name__}  tier={args.tier} -> model={prov.model_for(args.tier)}  "
          f"prompt_chars={len(prompt)}")
    try:
        c = prov.complete(prompt, args.tier)
    except ProviderError as exc:
        print(f"CALL FAILED: {exc}")
        return 1
    print(f"result      : {c.text.strip()[:200]!r}")
    print(f"usage       : {c.usage}  total={c.total_tokens}")
    print(f"cost_usd    : {c.cost_usd} (client-side estimate)")

    if args.json:
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}
        try:
            out = prov.complete_json("Return answer = OK", schema, args.tier)
        except ProviderError as exc:
            print(f"JSON CALL FAILED: {exc}")
            return 1
        print(f"structured  : {out}")
    print("smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
