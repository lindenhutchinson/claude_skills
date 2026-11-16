"""Guards over the shell commands an agent is about to run.

Every public module in this package is a guard: it defines `check(command, cwd) -> Decision | None`. Adding a
guard is adding a file; nothing here lists them. When several guards object, the most severe verdict wins.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

from ._decision import SEVERITY, Decision
from ._shell import decoded_payloads, normalise

__all__ = ["Decision", "evaluate", "guards"]

MAX_DECODE_DEPTH = 3


def guards() -> list[ModuleType]:
    return [
        importlib.import_module(f"{__name__}.{info.name}")
        for info in sorted(pkgutil.iter_modules(__path__), key=lambda i: i.name)
        if not info.name.startswith("_")
    ]


def evaluate(command: str, cwd: str | None = None, _depth: int = 0) -> Decision | None:
    text = normalise(command)
    decisions = [d for guard in guards() if (d := guard.check(text, cwd))]
    if _depth < MAX_DECODE_DEPTH:
        for inner in decoded_payloads(text):
            if d := evaluate(inner, cwd, _depth + 1):
                decisions.append(Decision(d.verdict, f"{d.reason} (inside -EncodedCommand)"))
    return max(decisions, key=lambda d: SEVERITY[d.verdict], default=None)
