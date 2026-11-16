---
name: checkpoint-review
description: Review files changed since the last review checkpoint for bugs, test gaps, anti-patterns, scaling concerns, and architectural drift. Use at natural seams in multi-commit implementation work — end of a layer, after 5-10 commits, before crossing into a new subsystem. Advances a tracked baseline so consecutive invocations review only new work.
---

# checkpoint-review

Review the code changed since the last review checkpoint. Produce a structured report covering contract cleanliness, test thoroughness, bugs, scaling concerns, anti-patterns, and architectural drift relative to the project's own planning docs.

**Not a CI tool.** Don't invoke on every commit. This is for natural seams in implementation work.

## Procedure

### 1. Establish the baseline

Look for `.claude/review-baseline` in the project root. It holds the commit SHA of the last review.

- **Present**: `BASELINE=$(cat .claude/review-baseline)`.
- **Absent**: ask what to use — typically the first commit (`git rev-list --max-parents=0 HEAD`), `HEAD~10`, or a named tag. Do not silently default to `HEAD~1`; that makes the review trivially empty.

### 2. Compute the diff set

```bash
git diff --name-only $BASELINE..HEAD
git log --oneline $BASELINE..HEAD
git diff --shortstat $BASELINE..HEAD
```

Filter to source and tests. Ignore lockfiles, caches, build artefacts, and docs-only changes unless docs review was asked for.

- **Empty diff**: say so, stop.
- **Large diff** (>30 files or >2000 changed lines): report the counts and ask whether to scope by directory, layer, or commit range before proceeding.

### 3. Per-file review

For each changed source file:

1. **Read the current file.** Don't rely on prior-turn context — things drift.
2. **Find its tests.** Learn the project's convention from existing pairs rather than assuming one. Absence of a test file is itself a finding.
3. **Read the tests**, if present.
4. **Review along the six dimensions** below.
5. **Assign a severity**: `blocking` (fix before moving on) / `flag` (worth discussing; the choice is legitimate but non-obvious) / `polish` (optional cleanup).

For test files with no source counterpart, focus on coverage breadth, fixture hygiene, clock and network mocking, determinism, and naming.

### 4. Cross-cutting pass

Then consider the diff as a whole:

- **Architectural drift.** Read the project's planning docs — `CLAUDE.md`, `TODO.md`, `PLANS/`, whatever this repo uses. Do the changes honour the stated architecture? Were decisions made ad-hoc in code that should have been surfaced?
- **Emerging duplication.** The same helper appearing in two modules → propose extracting it.
- **Dependency creep.** Diff the manifest (`pyproject.toml`, `package.json`, `*.csproj`, `go.mod`). Flag every new dependency and what it bought.
- **Commit hygiene.** Clear messages? Anything that should have been squashed or split?

### 5. Produce the report

Use the output format below. Write it to `.claude/reviews/<YYYY-MM-DD>-<short-sha>.md` for the audit trail, and print it in the reply.

### 6. Offer to advance the baseline

Ask once: advance the baseline to the current HEAD short-sha?

On yes: write HEAD's full SHA to `.claude/review-baseline`, stage it alongside the new report, and commit as `chore: review checkpoint <short-sha>`.

On no: leave the baseline alone — the next invocation re-reviews the same range plus new commits. Save the report either way.

## Review dimensions

Think through each. Don't force a finding per dimension; skip silently when there is nothing specific to say.

### 1. Contract and naming
- Is the public surface minimal and coherent?
- Do names reveal intent without the docstring?
- Are types accurate? Does the escape-hatch type (`Any`, `any`, `object`) appear only at true boundaries?
- Does the module's stated purpose still match what it does?
- Any dead exports?

### 2. Tests — thoroughness, not presence
**Every claim about coverage must name a specific case.** "Tests are shallow" is useless; "no test covers the empty-input branch at line 42" is useful. Per non-trivial function:

- **Happy path** — covered?
- **Empty, zero, null inputs** — covered?
- **Error paths** — does it raise, and does a test assert both the failure and a message fragment?
- **Domain edge cases** — derive these from this codebase: threshold boundaries, pagination, retry exhaustion, encoding, timezones, concurrent access, filesystem races.
- **Determinism** — injected clocks and mocked I/O, or real wall-clock, real sleeps, real network?
- **Scale** — is a path tested only at N=1 when production runs it at N=1M?

### 3. Bugs

Language-independent: off-by-one, empty-collection handling, null coalescence, swallowed exceptions, exceptions used for normal control flow, shared mutable state across threads, silent I/O failures where a status is never checked, equality vs identity confusion, timezone-aware vs naive comparisons.

Per language, add the local hazards — mutable default arguments and bare `except` in Python, `==` coercion and unhandled promise rejection in JS/TS, nullable references and `async void` in C#, unchecked errors in Go.

### 4. Scaling
- Unbounded in-memory accumulation where a stream would do.
- Quadratic loops over collections that grow.
- Uncached repeated work inside a loop.
- Transaction boundaries — is a 100K-row insert one transaction? Should it batch?
- String concatenation in loops where a join applies.
- Serial I/O where a batch or concurrent pattern cuts runtime by an order of magnitude.

### 5. Anti-patterns
- Module-level mutable globals; hidden singletons; class-level mutable defaults.
- Side effects in constructors — writing files, opening sockets, hitting the network.
- Printing instead of logging.
- God-functions: over ~60 lines, or more than a handful of responsibilities.
- **Premature abstraction**: a base class with one subclass, an interface with one implementer. Flag it, but don't always "fix" it — some are deliberate and justified.
- **Leaky abstractions**: an interface that forces callers to know the implementation.

### 6. Architectural drift
- Does this honour the architecture the planning docs state?
- Does the file still belong where it is, or has it outgrown that directory's remit?
- Any new pattern that contradicts or duplicates an existing one?
- Decisions made in code that should have been surfaced as a plan update?

## Output format

```markdown
# Review checkpoint: <head-short-sha> (<N> commits since <baseline-short-sha>)

## Scope
- Files changed: <count>
- Commits: <count>
- Period: <first-commit-date> → <head-date>

<commit list — short SHAs and titles>

## Blocking
<Fix before moving on. Each: file:line — what, why, suggested action. Omit if empty.>

## Flag
<Worth discussing. Each: file:line — observation and tradeoff. Omit if empty.>

## Polish
<Minor cleanups. Omit if empty or trivial.>

## Tests

| File | Test file | Happy | Empty | Error | Domain edges | Determinism | Notes |
|---|---|---|---|---|---|---|---|
| ... | ... | ✓ | ✗ (line 42) | ✓ | ✗ (threshold boundary) | ✓ | ... |

## Architectural drift
<"None observed" is a valid and common answer.>

## Recommended next
<Specific and actionable, with paths.>
```

## Notes for the reviewer

- **Be specific.** File:line references are non-negotiable. "Consider improving error handling" is useless; "`fetch/http.py:48` — status never checked, so a 500 silently becomes a null URL" is useful.
- **Be honest.** Don't pad. Fewer real findings beat a long list of polish items.
- **Skip non-findings.** Nothing to say in a dimension for a file? Leave it out.
- **Don't refactor as you go.** This is review, not rewrite. Present findings and let the user decide.
- **Respect the budget.** A 10-file review is 5–15 minutes of tool use, not an hour. If one file needs deep inspection, say so in the report rather than burning the budget solo.
- **Defer to the plan.** Where planning docs exist, drift is measured against them, not against your aesthetic.
