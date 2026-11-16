---
name: quality-gate
description: Discover and run the repo's own full check loop — format, lint, typecheck, test, build — instead of guessing commands. Use before committing, before reporting work complete, and after any refactor that touched more than one file.
---

# quality-gate

Run the checks this repo actually defines, in the order it defines them. The point is to
find the project's own gate rather than inventing one, because a guessed command that
silently doesn't exist reads as a pass.

## 1. Discover the gate

Look in this order and stop at the first that gives a real answer:

1. **A task runner target** — `Makefile` (`make check`), `justfile`, `Taskfile.yml`,
   or a `scripts` block in `package.json` / `[project.scripts]`. A repo-defined
   aggregate target is the gate; use it verbatim.
2. **CI config** — `.github/workflows/*.yml`. Whatever CI runs on a pull request *is*
   the contract. Extract the actual commands, including flags.
3. **Tool config present in the repo** — `[tool.ruff]`, `[tool.mypy]`,
   `[tool.pytest.ini_options]`, `eslint.config.*`, `biome.json`, `tsconfig.json`,
   `vitest.config.*`, `playwright.config.*`.

Run each tool through the project's own runner (`uv run`, `pnpm`, `npm run`, `dotnet`)
rather than a bare global binary — a global tool picks up the wrong version and the
wrong config.

**If no gate exists at all**, say so. That is a finding: propose adding one rather than
improvising a private sequence that only you know about.

## 2. Run it

Standard order, skipping any stage the repo doesn't define:

1. **Install / sync** — only if the lockfile changed.
2. **Format** — write mode, so formatting isn't reported as a lint failure.
3. **Lint**.
4. **Typecheck**.
5. **Unit tests**.
6. **Build** — if the project produces an artefact.
7. **Integration / e2e** — only when they can run here without external services; say
   so explicitly if you skipped them.

Run to completion rather than stopping at the first failure — one run that reports five
problems beats five runs that report one each.

## 3. Fix, and re-run

Fix what the gate reports. Then **run the full gate again from the top** — formatters
and autofixes routinely introduce new lint or type failures.

If a check fails for a reason unrelated to this session's work, say so and leave it
alone; don't quietly widen the scope, and don't quietly narrow the gate to make it pass.

## 4. Report

State the commands run and their real results:

```
uv run ruff format .     28 files reformatted
uv run ruff check .      clean
uv run mypy src          clean
uv run pytest            412 passed, 3 skipped, 18.4s
pnpm --dir web build     clean
e2e                      skipped — needs a live database
```

## Notes

- **Never claim a check passed without its output.** If you didn't run it, say you
  didn't.
- **Never weaken the gate to get green.** Adding an ignore, lowering strictness, or
  deleting an assertion to pass is a change to the contract — propose it explicitly,
  don't slip it in.
- **A skipped stage is a reported stage.** Silent omission is the failure mode here.
- **Don't add a new tool mid-run.** If the repo lacks a typechecker, that's a proposal
  for its own conversation, not something to bolt on inside a verification pass.
