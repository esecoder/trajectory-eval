#!/usr/bin/env python3
"""
provider.py — the Promptfoo provider: a JUDGE, not a prompt target.

Promptfoo normally calls a model with a prompt. Here there is no prompt to call: the
agent has already run and the transcript is the input. So this provider *is* the judge —
it receives the transcript Promptfoo passes in and returns the rubric's verdict as the
"completion", which the assertions then check.

⚠️ ONE DEFINITION OF "GOOD". This shells out to `src/judge.py` and `src/rubric.py` rather
than re-implementing the rubric in JavaScript. Two definitions of the same rubric in two
languages drift apart, and a gate that measures a different standard from the one you
report is worse than no gate.

Contract expected by Promptfoo's `exec` provider: JSON on stdout of the form
    {"output": "<string>", "metadata": {...}}
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(os.path.dirname(HERE))          # .../13-g2i-ai-evals/src
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import rubric  # noqa: E402
from judge import RuleBasedJudge  # noqa: E402


def read_prompt() -> str:
    """Get the transcript, from argv or stdin, WITHOUT EVER BLOCKING FOREVER.

    ⚠️ THE UNCONDITIONAL `sys.stdin.read()` WAS A REAL BUG AND IT HUNG THE RUN.
    If the caller spawns this process with a pipe on stdin and does not close it,
    `read()` waits for EOF that never comes — so the eval sat at "Running 20 test cases"
    and produced nothing. A provider that can hang is worse than one that fails, because
    a hang looks like slowness and gets waited on.

    So: prefer argv, and if stdin is a pipe only read it when data is actually ready.
    `select` on a pipe is portable enough here (macOS and Linux both support it), and a
    short timeout converts "hangs indefinitely" into "fails in one second with a reason".
    """
    # 1. argv — promptfoo passes the prompt as an argument in most configurations.
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        return args[0]

    # 2. stdin, but only if it is ready. A TTY means a human ran it interactively and
    #    reading would block on a keyboard, which is never what a test harness wants.
    if not sys.stdin.isatty():
        try:
            import select
            ready, _, _ = select.select([sys.stdin], [], [], 1.0)
        except (ImportError, OSError):                    # pragma: no cover
            ready = []
        if ready:
            raw = sys.stdin.read()
            try:
                payload = json.loads(raw) if raw.strip().startswith("{") else {"prompt": raw}
            except json.JSONDecodeError:
                payload = {"prompt": raw}
            return (payload.get("prompt")
                    or payload.get("vars", {}).get("transcript", ""))

    raise SystemExit(
        "provider.py: no prompt on argv and nothing ready on stdin after 1s. "
        "Promptfoo's `exec:` provider should pass the prompt as an argument.")


def main() -> int:
    transcript = read_prompt()

    # ⚠️ min_score=0, NOT the lenient default. A floor of 2 makes the safety veto
    # unrepresentable, which deletes the only signal that decides whether a judge is
    # safe. This is the bug reproduced in deepeval_eval.py, and it is not repeated here.
    min_score = int(os.environ.get("JUDGE_MIN_SCORE", "0"))
    judge = RuleBasedJudge(min_score=min_score)
    scores = judge.score(transcript)
    result = rubric.evaluate_composite(scores)

    weak = rubric.weakest(scores, 3)
    output = (
        f"{result['verdict']} | composite {result['composite']:.2f}/{rubric.SCALE_MAX}"
        + (" | VETO" if result["vetoed"] else "")
        + " | weakest: " + ", ".join(f"{d}={v:.0f}" for d, v in weak)
    )

    print(json.dumps({
        "output": output,
        "metadata": {
            "scores": scores,
            "verdict": result["verdict"],
            "vetoed": result["vetoed"],
            "composite": result["composite"],
        },
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
