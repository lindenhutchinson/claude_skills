---
description: Close out a session — secret and gitignore sweep, docs sync, commit, push, deploy, verify live, then report the ledger of what landed.
---

Close out the current session's work. Do the whole sequence; don't stop to ask
permission for steps already implied by the work being finished.

## 1. Account for everything uncommitted

`git status --short` and `git diff --stat`. For each change, decide: keep, or was it
scratch that should be reverted? Name anything you are discarding before discarding it.

## 2. Secret and gitignore sweep

Before staging, check that nothing sensitive is about to be committed:

- New `.env`, credential, token, key or dump files — confirm each is gitignored, and
  that a `.env.example` exists with the keys but not the values.
- Grep the staged diff for obvious secret shapes: API keys, bearer tokens,
  connection strings with passwords, private key headers.
- New build output, caches, virtualenvs, or large binaries that should be ignored.

Fix `.gitignore` as part of this commit rather than in a follow-up.

## 3. Sync the docs to reality

- Does the `README` still describe what the project now does, for someone outside it?
- Do the planning docs still match? Mark shipped work as shipped; delete plans that
  the implementation superseded rather than leaving them to rot.
- Does `CLAUDE.md` state anything the code no longer does?

Only touch what this session actually changed. This is not a full docs rewrite.

## 4. Commit

Group into coherent commits — one logical change each, not one giant blob and not a
commit per file. Follow the repo's existing message convention (read the last twenty
commits if unsure). No `Co-Authored-By` trailers.

## 5. Push, and integrate

Push the branch. If the work is complete and the repo's convention is trunk-based,
merge to the main branch. If a PR is the convention here, open it.

## 6. Deploy and verify

If this project deploys, deploy it, then **verify it landed on the running system** —
rebuild rather than restart, confirm the running artefact is the new one, and exercise
the actual behaviour. Use the `verify-live` skill for the full procedure.

## 7. Report the ledger

End with a compact statement of what landed. Not a narrative — a ledger:

```
Landed this session
  <one line per logical change>

Committed   <short-sha> … <short-sha> on <branch>
Pushed      <remote>/<branch>  (merged to <main>, if applicable)
Deployed    <where> — <how verified>
Not done    <anything deliberately left, and why>
```

The `Not done` line is required whenever something was skipped, blocked, or held back.
Silently omitting it is the failure this whole command exists to prevent.
