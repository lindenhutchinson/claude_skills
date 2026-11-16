"""Put destructive git and database operations to the user instead of running them.

These are legitimate often enough that blocking them outright would only push agents to work around the guard;
the rule is "ask first", so the verdict is `ask`. Recursive deletes, which are never fine, are in
recursive_delete and denied.
"""

from __future__ import annotations

import re

from ._decision import Decision
from ._shell import I, flag_cluster_has, git_invocations

# Path arguments that sweep a whole tree rather than naming files.
SWEEPING_PATHS = {".", "*", ":/", ":/*", "./", "./*"}

# Keyword then a name, so a search for the phrase itself (`grep 'drop table'`) is not caught.
SQL = re.compile(r"\b(?:DROP\s+(?:TABLE|DATABASE|SCHEMA)(?:\s+IF\s+EXISTS)?|TRUNCATE(?:\s+TABLE)?)\s+[\w.\"`\[]+", I)


def check(command: str, cwd: str | None = None) -> Decision | None:
    hit = _git(command) or (f"SQL `{m.group(0)}`" if (m := SQL.search(command)) else None)
    if not hit:
        return None
    return Decision("ask", f"Destructive operation ({hit}). Confirm with the user before it runs.")


def _paths(toks: list[str]) -> list[str]:
    after = toks[toks.index("--") + 1 :] if "--" in toks else toks
    return [t for t in after if not t.startswith("-")]


def _git(text: str) -> str | None:
    for sub, toks, _ in git_invocations(text):
        flags = [t for t in toks if t.startswith("-")]
        if sub == "reset" and "--hard" in flags:
            return "git reset --hard"
        if sub == "push":
            forced = [t for t in flags if t.startswith("--force") or flag_cluster_has(t, "f")]
            if forced:
                return f"git push {forced[0]}"
            if any(t.startswith("+") for t in toks):
                return "git push with a +refspec"
            if any(t in ("--delete", "-d") for t in flags) or any(t.startswith(":") for t in toks):
                return "git push --delete"
        dry_run = any(t in ("-n", "--dry-run") or flag_cluster_has(t, "n") for t in flags)
        if sub == "clean" and not dry_run and any(t == "--force" or flag_cluster_has(t, "f") for t in flags):
            return "git clean -f"
        if sub in ("checkout", "restore"):
            if sub == "checkout" and any(t in ("-f", "--force") for t in flags):
                return "git checkout --force"
            staged_only = sub == "restore" and any(t in ("--staged", "-S") for t in flags) and "--worktree" not in flags
            if not staged_only and SWEEPING_PATHS.intersection(_paths(toks)):
                return f"git {sub} of the whole tree"
        if sub == "branch":
            deleting = any(t == "--delete" or flag_cluster_has(t, "d") for t in flags)
            if any(flag_cluster_has(t, "D") for t in flags) or (
                deleting and any(t in ("-f", "--force") for t in flags)
            ):
                return "git branch -D"
        if sub == "stash" and toks[:1] in (["clear"], ["drop"]):
            return f"git stash {toks[0]}"
    return None
