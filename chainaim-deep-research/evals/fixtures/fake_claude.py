"""fake_claude.py — OFFLINE TEST DOUBLE for `claude -p --output-format json`.

Used ONLY by evals/run_evals.py (suite `provider`). It is NOT a Claude implementation and makes
no network calls. It mimics the documented output shape of `claude -p --output-format json`
(https://code.claude.com/docs/en/headless): a JSON object with `result`, `is_error`,
`session_id`, `usage` (Anthropic API token field names) and `total_cost_usd`; plus
`structured_output` when `--json-schema` is passed.

Behaviour is chosen with env var FAKE_CLAUDE_MODE:
    ok        (default) echo facts about the call so the eval can assert on them
    is_error  JSON with is_error: true
    exit1     non-zero exit with an error result on stdout
    badjson   non-JSON stdout
    noschema  --json-schema given but no structured_output in the reply
"""
import json
import os
import sys

mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
args = sys.argv[1:]
stdin_text = sys.stdin.read()
model = args[args.index("--model") + 1] if "--model" in args else None
schema = json.loads(args[args.index("--json-schema") + 1]) if "--json-schema" in args else None

if mode == "badjson":
    print("this is not json")
    sys.exit(0)
if mode == "exit1":
    print(json.dumps({"type": "result", "is_error": True, "result": "Not logged in"}))
    sys.exit(1)

payload = {
    "type": "result",
    "is_error": mode == "is_error",
    "result": "boom" if mode == "is_error" else json.dumps({
        "stdin_len": len(stdin_text),
        "prompt_in_argv": any(stdin_text[:50] in a for a in args) if stdin_text else False,
        "model": model,
        "cwd": os.getcwd(),
        "has_p": "-p" in args,
        "fmt_json": "--output-format" in args and args[args.index("--output-format") + 1] == "json",
    }),
    "session_id": "fake-session",
    "usage": {"input_tokens": 120, "output_tokens": 30,
              "cache_read_input_tokens": 5, "cache_creation_input_tokens": 7},
    "total_cost_usd": 0.0123,
}
if schema is not None and mode != "noschema":
    payload["structured_output"] = {"pass": True, "echo_required": schema.get("required", [])}
print(json.dumps(payload))
