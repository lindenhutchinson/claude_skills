"""Deny a commit or pull request that would carry a Co-Authored-By trailer.

The cause is Claude Code's own attribution, turned off by `"attribution": false` in settings; this is the backstop
for when that setting is missing or something adds a trailer by hand.
"""

from __future__ import annotations

import re
from pathlib import Path

from ._decision import Decision
from ._shell import CMD_START, I, git_invocations

TRAILER = re.compile(r"co-authored-by\s*[:=]", I)
GH_WRITE = re.compile(CMD_START + r"gh(?:\.exe)?\s+(?:pr\s+(?:create|edit|merge)|api\b)", I)
MESSAGE_FILE = re.compile(r"(?:^|\s)(?:-F|--file)(?:\s+|=)(\"[^\"]+\"|'[^']+'|\S+)")

REASON = (
    "Blocked: commits and pull requests carry no Co-Authored-By trailer; they are authored by the user alone. "
    "Remove the trailer and run it again."
)


def check(command: str, cwd: str | None = None) -> Decision | None:
    commits = [toks for sub, toks, _ in git_invocations(command) if sub in ("commit", "merge", "tag")]
    if not commits and not GH_WRITE.search(command):
        return None
    if TRAILER.search(command) or any(_file_has_trailer(m.group(1), cwd) for m in MESSAGE_FILE.finditer(command)):
        return Decision("deny", REASON)
    return None


def _file_has_trailer(raw: str, cwd: str | None) -> bool:
    path = Path(raw.strip("\"'"))
    if not path.is_absolute() and cwd:
        path = Path(cwd) / path
    try:
        return bool(TRAILER.search(path.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False
