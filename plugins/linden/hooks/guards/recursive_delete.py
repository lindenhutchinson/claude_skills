"""Deny any command that deletes recursively, or empties the trash every removal is redirected to."""

from __future__ import annotations

import re

from ._decision import Decision
from ._shell import ARGS, CMD_START, I, git_invocations, tokens

HINT = (
    "Recursive deletes, and emptying the trash, are blocked. Send the item to the OS trash instead, one literal "
    "absolute path at a time. Windows (PowerShell): Add-Type -AssemblyName Microsoft.VisualBasic; "
    "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory('<abs path>', 'OnlyErrorDialogs', "
    "'SendToRecycleBin') (DeleteFile for a file). Linux: gio trash '<abs path>'. macOS 15+: trash '<abs path>'. "
    "For tracked files, `git rm -r --cached` first. If it really must be a permanent delete, stop and ask the "
    "user to run it themselves."
)

S = re.IGNORECASE | re.DOTALL

DELETE_CMDS = re.compile(CMD_START + r"(rm|rmdir|rd|del|erase|ri|Remove-Item)(?=$|[\s\"'`,\]])" + ARGS, I)
UNIX_RECURSIVE = re.compile(r"^-[fidrv]*r[fidrv]*$", I)
LONG_RECURSIVE = re.compile(r"^--recursive$", I)
PS_RECURSE = re.compile(r"^-r(?:e(?:c(?:u(?:r(?:s(?:e)?)?)?)?)?)?(?::(.*))?$", I)
CMD_SLASH = re.compile(r"^(?:/[a-z])+$", I)
DELETE_DIRECTORY = re.compile(r"\bDeleteDirectory\s*\(", I)

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("find -delete", re.compile(CMD_START + r"find\b[^;&|\n]*\s-delete\b", I)),
    (
        "find -exec rm",
        re.compile(CMD_START + r"find\b[^\n]*\s-(?:exec|execdir|ok|okdir)\s+\S*?(?:rm|rmdir|unlink|Remove-Item)\b", I),
    ),
    ("find | xargs rm", re.compile(CMD_START + r"find\b[^\n]*\|\s*xargs\b[^;&|\n]*\b(?:rm|rmdir|unlink)\b", I)),
    ("fd -x rm", re.compile(CMD_START + r"fd\b[^;&|\n]*\s(?:-x|-X|--exec|--exec-batch)\s+\S*?rm\b", I)),
    (
        "recursive listing piped into a delete",
        re.compile(
            r"\b(?:Get-ChildItem|gci|ls|dir)\b[^|;\n]*\s(?:-r(?:e(?:c\w*)?)?|-Recurse|/s)\b[^;\n]*\|\s*"
            r"(?:(?:ForEach-Object|foreach|%)\s*\{[^}]*)?(?:Remove-Item|ri|rm|del|erase|\$_\.Delete\s*\()",
            I,
        ),
    ),
    (
        "Remove-Item splatted with Recurse",
        re.compile(r"\bRecurse\s*=\s*\$true\b[\s\S]*\b(?:Remove-Item|ri|rm|del)\b\s*@", I),
    ),
    ("shutil.rmtree", re.compile(r"\brmtree\s*\(|\bshutil\s*\.\s*rmtree\b|\bimport\s+rmtree\b", I)),
    ("os.removedirs", re.compile(r"\bremovedirs\b", I)),
    (
        "recursive fs remove",
        re.compile(
            r"\b(?:rm|rmdir|remove|rmSync|rmdirSync|removeSync)\s*\([^;]{0,400}?\brecursive\s*:\s*(?:true|!0|1)\b", S
        ),
    ),
    ("fs-extra remove/emptyDir", re.compile(r"\bfse?\s*\.\s*(?:remove|removeSync|emptyDir|emptyDirSync)\s*\(", I)),
    ("rimraf", re.compile(CMD_START + r"rimraf\b", I)),
    (
        "Directory.Delete(..., true)",
        re.compile(r"Directory\]?\s*(?:\.|::)\s*Delete\s*\([^;]{0,400}?,\s*(?:recursive\s*:\s*)?\$?true\s*\)", S),
    ),
    ("DirectoryInfo.Delete(true)", re.compile(r"\.\s*Delete\s*\(\s*(?:recursive\s*:\s*)?\$?true\s*\)", I)),
    ("robocopy /MIR or /PURGE", re.compile(CMD_START + r"robocopy\b[^;&|\n]*\s/(?:MIR|PURGE)\b", I)),
    ("rsync --delete", re.compile(CMD_START + r"rsync\b[^;&|\n]*\s--del(?:ete[\w-]*)?\b", I)),
    # The trash is the safety net every removal above is redirected to, so emptying it is blocked too.
    ("Clear-RecycleBin", re.compile(r"\bClear-RecycleBin\b", I)),
    ("SHEmptyRecycleBin", re.compile(r"\bSHEmptyRecycleBin\w*\b", I)),
    ("nircmd emptybin", re.compile(r"\bemptybin\b", I)),
    ("gio trash --empty", re.compile(CMD_START + r"gio\s+trash\b[^;&|\n]*\s--empty\b", I)),
    ("trash-empty", re.compile(CMD_START + r"trash-empty\b", I)),
    (
        "deleting inside the trash",
        re.compile(
            r"\b(?:rm|rmdir|rd|del|erase|ri|Remove-Item|unlink|Delete\w*|rmtree)\b[^;&|\n]*"
            r"(?:\$?Recycle\.Bin|\.local/share/Trash|\.Trash\b)"
            r"|(?:\$?Recycle\.Bin|\.local/share/Trash)[^;&|\n]*\b(?:Remove-Item|ri|rm|del|erase|Delete\w*)\b",
            I,
        ),
    ),
    (
        "emptying the Recycle Bin via Shell.Application",
        re.compile(
            r"\bNameSpace\s*\(\s*(?:10|0x0*a|'shell:RecycleBinFolder'|\"shell:RecycleBinFolder\")\s*\)"
            r"[\s\S]*\b(?:InvokeVerb|Remove-Item|ri|rm|del|Delete\w*)\b",
            I,
        ),
    ),
]


def check(command: str, cwd: str | None = None) -> Decision | None:
    hit = _delete_cmds(command) or _git(command) or _delete_directory(command)
    if not hit:
        hit = next((name for name, pattern in PATTERNS if pattern.search(command)), None)
    return Decision("deny", f"Blocked ({hit}). {HINT}") if hit else None


def _ps_recurse_on(tok: str) -> bool:
    m = PS_RECURSE.match(tok)
    return bool(m) and (m.group(1) or "").lower() not in ("$false", "false", "0")


def _delete_cmds(text: str) -> str | None:
    git_rm_starts = {m.start(2) for sub, _, m in git_invocations(text) if sub == "rm"}
    for m in DELETE_CMDS.finditer(text):
        word, args = m.group(1).lower(), m.group(2)
        if word == "rm" and m.start(1) in git_rm_starts:
            continue  # `git rm` is judged by _git, which allows --cached.
        for tok in tokens(args):
            if UNIX_RECURSIVE.match(tok) or LONG_RECURSIVE.match(tok) or _ps_recurse_on(tok):
                return f"{m.group(1)} with {tok}"
            # cmd's /s, alone or clustered (`/s/q`).
            if word in ("rd", "rmdir", "del", "erase") and CMD_SLASH.match(tok) and "s" in tok.lower().split("/"):
                return f"{m.group(1)} with {tok}"
    return None


def _git(text: str) -> str | None:
    for sub, toks, _ in git_invocations(text):
        if sub == "clean":
            flags = [t for t in toks if t.startswith("-")]
            if any(t in ("-n", "--dry-run") or (re.match(r"^-[a-z]+$", t, I) and "n" in t[1:]) for t in flags):
                continue
            for t in flags:
                if re.match(r"^-[a-z]+$", t, I) and re.search(r"[dxX]", t[1:]):
                    return f"git clean {t}"
        elif sub == "rm" and "--cached" not in toks:
            for t in toks:
                if t == "--":
                    break
                if re.match(r"^-[a-z]*r[a-z]*$", t, I) or t == "--recursive":
                    return f"git rm {t} without --cached"
    return None


def _call_args(text: str, open_paren: int) -> str:
    depth = 0
    for i in range(open_paren, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1 : i]
    return text[open_paren + 1 :]


def _delete_directory(text: str) -> str | None:
    """FileSystem.DeleteDirectory is recursive unless it recycles or refuses a non-empty directory."""
    for m in DELETE_DIRECTORY.finditer(text):
        args = _call_args(text, m.end() - 1)
        if re.search(r"SendToRecycleBin|ThrowIfDirectoryNonEmpty", args, I) and not re.search(
            r"DeletePermanently|DeleteAllContents", args, I
        ):
            continue
        return "FileSystem.DeleteDirectory without SendToRecycleBin"
    return None
