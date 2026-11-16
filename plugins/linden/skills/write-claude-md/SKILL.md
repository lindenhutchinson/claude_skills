---
name: write-claude-md
description: Write or clean up a project's CLAUDE.md in the house style — the standard skeleton, rules stated with the failure they prevent, no in-flight work log, nothing that duplicates global preferences. Use when creating a CLAUDE.md, when an existing one has drifted or bloated, or when a repo has been worked in without one.
---

# write-claude-md

A project `CLAUDE.md` answers one question: **what would someone competent still get
wrong here?** Everything else is noise that costs context on every single turn.

## What belongs, and what doesn't

**Belongs** — the non-obvious and project-specific:

- What this project is, in two or three sentences.
- The stack, and the commands to run it — the exact invocations, not the general idea.
- The layout, where it isn't self-evident.
- Deliberate architectural inversions, especially ones that look like mistakes. These
  are the highest-value lines in the file: without them, the next change "fixes" them.
- Gotchas that have already cost real time.
- Domain constraints that aren't derivable from the code — legal, editorial, safety.

**Doesn't belong**:

- Anything already in the global `CLAUDE.md`. Restating a global preference locally
  invites the two to drift apart.
- Tutorial content — how to create a virtualenv, what a migration is.
- **In-flight task state.** "Phase 16 complete", "A1 in progress". That is `TODO.md`'s
  job. Work logs in `CLAUDE.md` go stale within days and then actively mislead.
- Anything true of every project in the language.
- Copies of another repo's document. Link instead; copies fork and then contradict.

## The skeleton

Sections in this order, omitting any that has nothing real to say:

```markdown
# <Project name>
<Two or three sentences: what it is, who it's for, what state it's in.>

## Stack
- **Language:** … / **Framework:** … / **Package manager:** … / **Tests:** …

## Layout
<Fenced tree, one inline comment per entry that isn't obvious.>

## Commands
<Fenced block or a table. Exact invocations, with a comment each.>

## Conventions
<The rules. Each with the reason or the failure it prevents.>

## Gotchas
<Things that have already cost time. Symptom first, then cause, then fix.>
```

Use `## Conventions` and `## Gotchas` as the headings — those names, consistently,
across repos.

Two length modes, both fine: a pointer file of roughly 50–100 lines for a small or
self-evident project, and an exhaustive one for a large or surprising codebase. What is
not fine is length made of filler.

## How to write a rule

**Attach the failure to the rule.** A rule with its reason gets followed and survives
refactors; a bare imperative gets rationalised away the first time it is inconvenient.

- Weak: "Don't duplicate the slug helper."
- Strong: "Slug generation lives only in `core/slug`. Four copies had already drifted
  before it was consolidated."

- Weak: "Templates should be simple."
- Strong: "**No logic in templates.** Hardcode paths rather than reversing URLs — the
  templates are deliberately dumb so the render path stays debuggable from the view
  alone."

Use bold lead-ins, em-dash definitions, and tables for anything that is a lookup. Be
terse. State the rule, state the cost, move on.

## Procedure

**Writing a new one:** run `repo-orientation` first if the project is unfamiliar. Draft
the skeleton, then fill only the sections with something non-obvious to say. Verify
every command by running it. Confirm the layout matches reality.

**Cleaning up an existing one:** read it against the code and cut in this order — work
log and phase history out to `TODO.md`; duplicated global preferences deleted; tutorial
filler deleted; stale claims corrected or removed; drifted section headings renamed to
the standard set; content copied from another repo replaced with a link. Then check what
is *missing* — every gotcha that cost time this month should be in here.

Report what you cut and what you added, with line counts.

## Notes

- **`CLAUDE.md` is loaded on every turn.** Every line is rent. If a line wouldn't change
  what someone does, delete it.
- **Machine-specific detail goes in `CLAUDE.local.md`**, untracked — hostnames, personal
  paths, local credentials. Especially before a repo goes public.
- **If `AGENTS.md` is present, keep it a one-line pointer** to `CLAUDE.md`. Two
  documents of substance guarantees two versions of the truth.
