"""Textual helpers shared by the guards. These scan text; they do not parse a shell.

Every guard errs towards matching: a command that merely mentions a dangerous operation in an argument (a commit
message, an echo) is caught too.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Iterator

I = re.IGNORECASE

# Where a command word may start: start of text, whitespace, a shell separator, a quote, or a path slash.
CMD_START = r"(?:^|(?<=[\s;&|(){}`\"'=\\/\[,]))"
# Where a simple command's arguments end. Quotes are not separators: `Remove-Item "x" -Recurse`.
ARGS = r"([^;&|\n\r)]*)"

GIT = re.compile(
    CMD_START + r"git(?:\.exe)?((?:\s+(?:-[Cc]\s+\S+|--?[\w-]+(?:=\S+)?))*)\s+([a-z][\w-]*)(?=$|\s)" + ARGS, I
)

TOKEN_STRIP = "\"'`\\[](),"

ENCODED = re.compile(r"(?:^|\s)-(?:e|ec|en|enc|enco\w*|encodedcommand)\s+([A-Za-z0-9+/=]{8,})", I)


def tokens(args: str) -> list[str]:
    return [t.strip(TOKEN_STRIP) for t in re.split(r"[\s,]+", args) if t.strip(TOKEN_STRIP)]


def git_invocations(text: str) -> Iterator[tuple[str, list[str], re.Match[str]]]:
    """Each `git <sub> <args>` in the text: the subcommand, its argument tokens, and the match."""
    for m in GIT.finditer(text):
        yield m.group(2).lower(), tokens(m.group(3)), m


def flag_cluster_has(token: str, letter: str) -> bool:
    """`-fdx` has `f`; `--force` is not a cluster."""
    return bool(re.fullmatch(r"-[a-zA-Z]+", token)) and letter in token[1:]


def normalise(text: str) -> str:
    """Join continued lines (bash `\\`, PowerShell backtick) so flags on the next line stay with their command."""
    return re.sub(r"[\\`]\r?\n", " ", text)


def decoded_payloads(text: str) -> list[str]:
    """`pwsh -EncodedCommand <base64 UTF-16LE>` hides its script from a textual scan; unwrap it."""
    out = []
    for m in ENCODED.finditer(text):
        try:
            out.append(base64.b64decode(m.group(1), validate=True).decode("utf-16-le"))
        except (ValueError, UnicodeDecodeError):
            pass
    return out
