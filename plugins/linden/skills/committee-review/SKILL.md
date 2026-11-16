---
name: committee-review
description: Review one surface with a panel of parallel subagents holding deliberately different lenses, then synthesise their findings into one ranked list. Use for design sweeps, prompt and tool-description reviews, architecture assessments, and anywhere a single pass would only catch one class of problem.
---

# committee-review

One reviewer finds one kind of problem. A panel with genuinely different lenses finds
several, and disagreement between them is itself information — it marks where the
decision is real rather than obvious.

Use it when the surface is broad and the failure modes are varied. For a narrow,
well-specified check, one pass is cheaper and just as good.

## Procedure

### 1. Define the surface precisely

Name exactly what is under review — files, directories, a diff range, a set of prompts,
a rendered UI. Every reviewer must see the same surface, or their findings can't be
compared.

### 2. Choose lenses that genuinely differ

Three to five. Each lens gets its own criteria and its own blind spot; running the same
generalist five times buys nothing but cost.

Pick from the axes that actually apply — for example:

| Surface | Lenses that differ |
|---|---|
| Architecture | Extensibility · failure modes · testability · the newcomer reading it cold |
| UI / UX | First-time user · mobile · accessibility · visual and typographic craft |
| Prompts / tool descriptions | Ambiguity and misreading · redundancy and token cost · failure and edge cases · does it actually elicit the intended behaviour |
| Data model | Query patterns · migration and evolution · integrity constraints · scale |

Each reviewer is told its lens is the whole job, and to report only within it.

### 3. Dispatch in parallel

All reviewers at once, each with: the surface, its lens and criteria, the required
output format, and an instruction to give file:line or quoted-excerpt evidence for every
finding, with a severity.

Reviewers do **not** see each other's work — independence is the entire mechanism.
Don't tell them what the others are looking at, and don't let one summarise for another.

### 4. Synthesise

The synthesis is your job, not another agent's. Merge into one ranked list:

- **Deduplicate**, but record how many lenses independently raised each item. Something
  three lenses found separately is more real than something one found.
- **Surface disagreement explicitly** rather than averaging it away. When the
  extensibility lens wants an abstraction and the simplicity lens wants it deleted, that
  tension is the finding — present both cases and make a call.
- **Rank by severity and confidence**, not by which lens produced it.
- **Discard the padding.** A reviewer told to find problems will find some. Anything
  without concrete evidence doesn't survive.

### 5. Report

```markdown
## Panel
<Lens — one line on what it was asked to look for.>

## Findings
<Ranked. Each: severity, what, evidence (file:line or quote), which lenses raised it,
recommended action.>

## Disagreements
<Where lenses conflicted. Both cases, then your call and why.>

## Not worth acting on
<Raised but rejected, with the reason. Keeps it from being re-raised next sweep.>
```

## Notes

- **Lenses must be adversarial to each other**, at least partly. If every reviewer would
  agree on every point, the panel is redundant.
- **Watch the budget.** Five reviewers over a large surface is expensive; scope the
  surface before adding lenses, and prefer fewer, sharper lenses to more.
- **Panels review; they don't rewrite.** Findings come back to be decided on.
- **Don't launder a weak finding through consensus.** Three vague agreements are still
  vague.
