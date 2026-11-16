"""Merge the repo's settings into a machine's settings.json without owning the whole file.

Claude Code writes machine state (`/model`, `/config` choices, enabled plugins) back into settings.json, so the
file cannot be linked. Instead the repo's settings are merged in, and the settings applied last time are kept, so
something removed from the repo is removed from the machine on the next run:

- objects merge key by key;
- arrays gain the repo's entries and keep the machine's own;
- any other value is set to the repo's.

What the repo applied and no longer has is retracted first: its array entries are removed, and its other values
are removed if the machine has not changed them since.
"""

from __future__ import annotations

import copy
from typing import Any

JSON = dict[str, Any]
_MISSING = object()


def merge(current: JSON, fragment: JSON, previous: JSON | None = None) -> JSON:
    result = copy.deepcopy(current)
    if previous:
        _retract(result, previous, fragment)
    _apply(result, fragment)
    return result


def _retract(target: JSON, previous: JSON, fragment: JSON) -> None:
    for key, old in previous.items():
        if key not in target:
            continue
        new = fragment.get(key, _MISSING)
        current = target[key]
        if isinstance(old, dict) and isinstance(current, dict):
            _retract(current, old, new if isinstance(new, dict) else {})
            if not current and new is _MISSING:
                del target[key]
        elif isinstance(old, list) and isinstance(current, list):
            keep = new if isinstance(new, list) else []
            target[key] = [x for x in current if x not in old or x in keep]
            if not target[key] and new is _MISSING:
                del target[key]
        elif new is _MISSING and current == old:
            del target[key]


def _apply(target: JSON, fragment: JSON) -> None:
    for key, value in fragment.items():
        current = target.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            _apply(current, value)
        elif isinstance(value, list) and isinstance(current, list):
            current.extend(copy.deepcopy(x) for x in value if x not in current)
        else:
            target[key] = copy.deepcopy(value)
