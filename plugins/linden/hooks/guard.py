#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""PreToolUse hook: run every guard in guards/ over the shell command about to run.

Reads the hook payload on stdin. For a tool input with a `command` (Bash, PowerShell, Monitor), prints the most
severe guard's decision as hook JSON; otherwise prints nothing and the command proceeds. Always exits 0: a
decision is carried in the JSON, and a crash is handled by the hook's `onFailure`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Import guards from beside this file only; never from the working directory the agent happens to be in.
HERE = str(Path(__file__).resolve().parent)
sys.path = [HERE] + [p for p in sys.path if p not in ("", ".", HERE)]

from guards import evaluate


def main() -> int:
    payload = json.load(sys.stdin)
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        return 0
    decision = evaluate(command, cwd=payload.get("cwd"))
    if decision:
        json.dump(decision.hook_output(), sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
