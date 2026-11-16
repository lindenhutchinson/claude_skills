---
name: docs-staleness-sweep
description: Audit a repo's documentation against what actually shipped — retire plans that are implemented or abandoned, fix docs that describe code that no longer exists, and keep the README outward-facing. Use when asked to clean up the docs, when planning docs have piled up, or before making a repo public.
---

# docs-staleness-sweep

Documentation is a maintained artefact. Plan docs that describe finished work, and
READMEs that point at documents nobody kept up, are worse than no documentation — they
send the next reader (including the next agent) confidently in the wrong direction.

## Procedure

### 1. Inventory

Every markdown file outside `node_modules` and vendored trees. For each, record its
last-modified date and its apparent kind:

| Kind | What it is |
|---|---|
| **Outward-facing** | `README` — for someone who does not know the project |
| **Working agreement** | `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING` — how work is done here |
| **Plan** | A proposal for work: `*_PLAN.md`, `PLANS/`, `docs/design-*` |
| **Reference** | Durable explanation of how something works |
| **Log** | Changelog, decision record, review history — append-only, never stale |

The kind determines the test. A plan can be finished; a reference can only be wrong.

### 2. Reconcile plans against the code

For each plan document, determine which it is:

- **Shipped** — the code exists and matches. Delete the plan; the code is now the
  truth. If it carries rationale worth keeping, move that into a reference doc or the
  relevant `CLAUDE.md` first.
- **Partly shipped** — trim it to only the unshipped remainder, and say plainly at the
  top what already landed.
- **Superseded** — the work happened differently. Delete it. A plan that contradicts
  shipped code is actively harmful; it is the single worst artefact in a docs tree.
- **Abandoned** — never started, no longer wanted. Delete it.
- **Live** — still the intent. Leave it, but check its claims about the current state.

Verify by reading the code, not by trusting a checklist inside the plan. Boxes go
unticked routinely.

### 3. Check reference docs against reality

For each reference doc, spot-check its concrete claims: named files and directories
still exist, commands still run, described flows match the code, config keys are real.
Fix what is wrong. Delete what documents something that no longer exists.

### 4. Fix the README

The README is for someone outside the project. It should cover what this is, what it
does, how to run it, and how to develop it — and little else.

- Move internal detail out into reference docs.
- **Remove links to documents that are stale or gone.** A README pointing at a rotten
  doc endorses it.
- Check the setup instructions against the actual tooling; setup sections are the
  fastest-rotting text in any repo.

### 5. Check what shouldn't be public

Especially before a repo goes public: hostnames, internal IPs, personal paths, tokens
and keys in examples, screenshots with real data, real account identifiers. Machine-
specific instructions belong in an untracked local file, not the shared docs.

### 6. Report

```
Deleted    <file> — shipped in <where>
           <file> — superseded by <what actually happened>
Trimmed    <file> — removed <n> shipped sections, <what> remains
Fixed      <file> — <claim> was wrong, now <correct>
README     <what moved out, what links were removed>
Flagged    <anything sensitive found>
Left       <live docs, unchanged>
```

## Notes

- **Delete rather than archive.** Git holds the history. An `old/` directory is just
  the same rot with a different path.
- **Don't rewrite while sweeping.** This retires what is false; improving what is true
  is separate work. Say if you spot the need.
- **Logs are never stale.** Changelogs and decision records are historical by design —
  don't "correct" them.
- **When you can't tell whether a plan shipped, say so.** A wrong deletion costs more
  than an open question.
