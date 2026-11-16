---
name: repo-orientation
description: Get oriented in an unfamiliar, inherited, or stale repo and deliver a candid verdict on what it is, what still works, what is likely broken, and whether the code is any good. Use when opening a project for the first time, returning to one after months, or when asked "understand this repo" or "how is the quality of this code".
---

# repo-orientation

Two questions, answered honestly: **what is this, and can it be trusted?**

Stale repos are the common case — dependencies have moved, APIs it scrapes or calls have
changed, and the README describes an intention rather than the current state. Assume
drift and go looking for it.

## Procedure

### 1. Establish what it claims to be

Read the `README`, `CLAUDE.md`, and any planning docs. Note the claims — they are
hypotheses to check, not facts. Then `git log --oneline -20` and
`git log -1 --format=%ci` for the real last-touched date; a two-year gap changes what
"working" plausibly means.

### 2. Map the actual shape

Manifests and layout before source. What language and framework, what package manager
and lockfile, what test runner, what linting, is it containerised, does it have CI.
Then the directory tree — is the structure coherent, or has it accreted?

Read entry points and the core domain module. Do not read the whole codebase; sample
enough to judge.

### 3. Find the rot

This is the part that earns the exercise. Look specifically for:

- **Dependency staleness** — pinned versions years behind; a lockfile that no longer
  resolves; deprecated or abandoned packages.
- **Broken external contracts** — hardcoded selectors for a site that has since been
  redesigned, API endpoints and payload shapes, auth flows, model names, anything
  pointing at a third party that moves without telling you.
- **Environmental assumptions** — a language version no longer installed, paths that
  only existed on one machine, credentials expected in a file that isn't there.
- **Docs that lie** — a README describing a feature the code doesn't have, or plan docs
  for work that shipped or was abandoned.
- **Dead code** — modules nothing imports, commented-out blocks, an abandoned rewrite
  sitting beside the original.

### 4. Try to run it

Attempt install and the test suite. This converts speculation into fact fast. Record
exactly where it fails; a failure at install is a very different verdict from a failure
in three tests.

Don't fix anything yet. Orientation and repair are separate.

### 5. Judge the quality

A real verdict, not a hedge. Assess: is the architecture coherent or is it one god-file;
are the boundaries real; do tests exist and do they test anything meaningful; is error
handling present or is everything a bare catch; are there secrets in the repo; would
extending this be pleasant or miserable.

Say plainly whether it is worth building on, worth salvaging in part, or worth
replacing. That judgement is the deliverable — an inventory without a verdict is not an
orientation.

## Output format

```markdown
## What it is
<Two or three sentences. What it does, for whom, what state it's in.>

## Stack
<Language, framework, package manager, tests, lint, container, CI — one line each.>

## Structure
<Brief tree of what matters, with a note per entry. Not exhaustive.>

## Does it run?
<What you tried, what happened, exactly where it broke.>

## What's likely broken
<Ranked. Each item: what, why you think so, how much work to confirm.>

## Quality verdict
<Candid. Architecture, tests, error handling, security. Then: build on it,
salvage part of it, or replace it — and why.>

## If we continue, start here
<Three to five concrete first moves.>
```

## Notes

- **Be candid about quality.** A hedged verdict is worthless; the whole point is finding
  out whether this is worth the effort.
- **Distinguish "old" from "bad."** Code untouched for three years can be perfectly
  sound. Age is a reason to check, not a finding on its own.
- **Don't fix while orienting.** Note it and move on; repairs come after the verdict.
- **Bound the effort.** This is an assessment, not an audit. Sample widely, read deeply
  only where something looks wrong.
