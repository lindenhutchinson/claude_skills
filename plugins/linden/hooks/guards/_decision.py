from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["deny", "ask"]
SEVERITY: dict[Verdict, int] = {"ask": 1, "deny": 2}


@dataclass(frozen=True)
class Decision:
    """What a guard wants done with a command. `deny` blocks it; `ask` puts it to the user."""

    verdict: Verdict
    reason: str

    def hook_output(self) -> dict:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": self.verdict,
                "permissionDecisionReason": self.reason,
            }
        }
