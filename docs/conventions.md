# Convention registry

What is encoded, where it lives, and what motivated it. Nothing gets added without
evidence — see [`sourcing.md`](sourcing.md).

Everything here must hold for **any** repo. A rule that only makes sense for one
stack, one host, or one domain belongs in that repo's own `CLAUDE.md`, not here.

Status: **live** = written and installed · **drafted** = written, not yet promoted ·
**queued** = evidence gathered, not yet written.

## Global — `home/CLAUDE.md`

| Convention | Status | Evidence |
|---|---|---|
| Prove a change landed on the running system, not in the diff | live | Surfaced independently in two repos; ~15 verification challenges in one alone ("did that name change actually land?", "is it actually loaded?"). A defect recurring across sessions means the previous fix was never verified. |
| Run the whole loop autonomously: build → test → deploy → verify | live | Repeated requests to take a task end to end — build, review, test, verify, deploy — without checking in at each step. |
| Default to parallel subagents for independent workstreams; don't ask | live | Requested unprompted across 5+ sessions in two repos: fan independent work out to agents and parallelise it. |
| No process ceremony — investigate directly, report findings not phases | live | Five interrupts of announced skill workflows across four projects, each asking to skip the ritual and just look. Distinct from wanting rigour: root-cause analysis is wanted, narrated methodology is not. |
| Ask inline and recommend; don't use the question tool | live | Three hard rejections of `AskUserQuestion`; prose questions answered readily. |
| After design is agreed, implement — no spec doc, no implementation plan | live | Seven instances of asking to skip the implementation plan and implement. Research and design *dialogue* at kickoff is still wanted; the written artifacts are not. |
| Fix root causes; never work around a problem | live | Repeated pushback on workarounds where the direct fix was simple. |
| Context and token budget is a real constraint | live | Concern about exhausting usage limits before the work ships. |
| Extensibility test: adding a tool or route should be a single-file drop-in | live | Extends the existing *Clean architecture* section. Requests to break up god files so new capabilities are easy to add. |
| A repeated or shouted instruction means a step was skipped — do it before replying | live | Every all-caps message in the corpus restates an earlier instruction that never landed. |
| Close out with a ledger: changed, committed, pushed, deployed, verified | live | Six-plus unprompted status checks (is it deployed, is it fixed, what landed this session). |

## Plugin assets — `plugins/linden/`

| Asset | Kind | Status | Purpose |
|---|---|---|---|
| `wrap-up` | command | live | Close-out ritual: secret and gitignore sweep → README sync → commit → push → deploy → verify live → report what landed. |
| `verify-live` | skill | live | Prove a change is actually running: rebuild rather than restart, then read the live behaviour — logs, health, or browser. Never report from the diff. |
| `quality-gate` | skill | live | Discover and run the repo's own full check loop — format, lint, typecheck, test — rather than guessing commands. |
| `repo-orientation` | skill | live | Kickoff shape for an unfamiliar or stale repo: what still works, what's likely broken, a candid quality verdict. |
| `docs-staleness-sweep` | skill | live | Map plan docs to shipped code, flag implemented and stale, keep READMEs outward-facing. Requested four times in different words. |
| `committee-review` | skill | live | Parallel multi-perspective review of a design surface by a panel of subagents with distinct lenses. |
| `checkpoint-review` | skill | live | Hoisted from an existing project, where it was already written stack-agnostically. Diff-since-baseline review at natural seams, with a stored baseline SHA and an audit trail. The strongest existing artifact; use it as the template for every other skill here. |
| `write-claude-md` | skill | live | House style for a project `CLAUDE.md`: the five-part skeleton those files already converge on, rules stated with the failure they prevent, and no in-flight work log — that belongs in `TODO.md`. |

## Shared settings — `home/`

| Item | Status | Evidence |
|---|---|---|
| A read-only Bash allowlist in global `settings.json` | queued | The same core (`ls`, `grep`, `find`, `wc`, `git status/log/diff`) is re-derived by hand in four repos' `settings.local.json`, with drift and accidental entries. Global settings currently has no `permissions` block at all. Needs a **merge** strategy, not a file copy — `sync-home.ps1` links whole files and must not clobber machine-local settings. |
| Line-ending and commit-format guards as hooks | queued | No hooks exist anywhere, despite two repos carrying hook-shaped rules enforced by prose alone. |


## Deliberately not encoded

Real recurring patterns that are nonetheless **project-scoped**. They belong in the
relevant repo's `CLAUDE.md` or `.claude/skills/`, and are listed here only so the
decision isn't relitigated:

- Host-specific deploy mechanics (ssh targets, compose overlay selection).
- Service-specific triage runbooks and known-bug notes.
- LLM-application hygiene: prompt-cache safety under dynamic injection, strict JSON
  with lenient repair, tool-loop limits for weak models.
- UI laws tied to one app's design language.
- Game-modding toolchains.

And genuinely non-recurring: one-off scraping work, hardware troubleshooting
sessions that happened to be recorded inside a project directory.
