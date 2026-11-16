---
name: coord-worker
description: Protocol and coord command reference for a worker session in a repo where several Claude Code sessions run in parallel under an orchestrator. Use when told to load coord-worker, when an orchestrator sends an onboarding message, when your prompt names you as a worker on a coordinated repo, before editing, building, deploying or committing in such a repo, or when you need to know who owns a file.
---

# Coordinated worker

You are one of several Claude Code sessions working one repository at once. One session, the
**orchestrator**, talks to the user and holds the overall picture. You own one task. The **board** is how
everyone sees who is doing what and who owns which files.

## The board and the tool

The board is one append-only log in `<git common dir>/coord/log.jsonl`. Every worktree of the repo shares it,
and git never tracks it. Each line is an event with a sequence number. Everything else (states, claims,
blockers) is derived from the log. **Never edit the log by hand**; write to it only through the tool:

```sh
coord='uv run --quiet --script "$HOME/.claude/skills/coord-worker/scripts/coord.py"'   # read as: coord ...
```

That line documents the invocation; it does not persist between shell calls. Spell the full command out
every time. It works unchanged in bash, zsh, Git Bash and PowerShell 7. Run it from anywhere inside the repo or one of
its worktrees.

| Command | Use |
| --- | --- |
| `coord join -a NAME --task "..." [--msg-name M] [--role R]` | register, or re-register after a restart; `--msg-name` is your SendMessage name if it differs from NAME |
| `coord addr NAME` / `coord addr --role orchestrator` | the SendMessage name of a board agent / of the orchestrator |
| `coord status` | the board: every agent, its state, task and live claims |
| `coord claim -a NAME PATH... [--note why]` | claim files or `dir/` before editing; all or nothing |
| `coord check PATH...` | who holds these |
| `coord release -a NAME PATH...` / `--all` | give claims back |
| `coord with -a NAME @deploy -- CMD...` | take a lock, run CMD, release however it ends; exit code passes through |
| `coord state -a NAME working\|blocked\|review\|idle\|done [--on X] [-m "..."]` | your state; `blocked` needs `--on` |
| `coord note -a NAME [--kind note\|decision\|request\|reply\|deploy] [--to X] "..."` | durable record |
| `coord tail [-n 20] [--since SEQ] [--about NAME]` | read events |
| `coord leave -a NAME [-m "..."]` | leave, releasing everything |

Claim keys are repo-relative paths, resolved from the repo root and **not** from the cwd. A trailing `/`
claims a whole directory. `@name` keys are resources. Matching is case-insensitive on Windows. An absolute
path is mapped to the worktree that contains it, so the same file in two worktrees is the same key.

Exit codes: `0` ok, `2` claim refused (held by someone else, and nothing was claimed), `3` board mutex timed
out (it reports the holder's pid), `4` `wait` timed out.

`NAME` is the name you were given, the one other sessions see in `ListAgents`. Use exactly that name
every time.

If you run in a Herdr pane (`HERDR_ENV=1`), the orchestrator watches and prompts you through Herdr under
that same name, and closes your tab once you have wound down. Don't use `herdr` to control other panes or
agents, and never `herdr agent prompt` the orchestrator: report by `SendMessage`.

If you were started with `claude -w NAME`, you are in your own worktree on branch `NAME`. The board and
`summaries/` are shared with the main tree all the same.

## Protocol

**1. Join.** First thing: `coord join -a NAME --task "<one line>"`, then `coord status` to see who else is
working and what they hold.

**2. Claim before you edit.** Before the first `Edit`/`Write` to a file, including a new file, claim it. If
you know the set up front, claim it in one call. Claim more as the work grows. Never edit a file you have
not claimed, and never edit one someone else holds.

- **Refused (exit 2)?** Do not edit it, and do not work around it with a copy or a different file.
  Run `coord state -a NAME blocked --on <holder> -m "<file> for <reason>"`, then `SendMessage` the
  orchestrator with what you need. Do not `--wait` on source files; the orchestrator sequences those.
- **Waiting on a lock** (`--wait`): after 2 rounds (~18 min) `SendMessage` "blocked on <holder> for <time>", then keep waiting. A lock held by `user` is the user's own editor run; the orchestrator gets it released.
- **Shared docs** (`CLAUDE.md`, READMEs) are files like any other. Claim them only for the edit.
- **Hold a claim until your change to that file is committed or handed off.** In a shared working tree,
  releasing an uncommitted file lets the next agent's edits and commit mix with yours. If the orchestrator
  asks you to hand a file over, release it and say in a `coord note` that it holds your uncommitted edits.

**3. Log state changes, not chatter.** Use `coord state` when you start, block, unblock, wait on the user's
review (`review`), or finish. One line each. The board replaces status polling, so keep it true. Don't log
every step.

**4. Builds, deploys and commits go through a lock, and only when asked.**

```sh
coord with -a NAME @deploy -- <the repo's build/deploy command>       # build + deploy, serialized
coord with -a NAME @git -- git commit -m "..." -- path/one path/two    # commit only your files
```

- A deploy ships **the whole working tree it runs in**, including other agents' uncommitted edits.
  `coord` prints a warning listing them when you take `@deploy`. Relay that warning to the orchestrator
  rather than deploying past it unannounced.
- Commit only when the user, directly or relayed by the orchestrator, says so. Name your paths
  explicitly. Never use `git add -A`, `git add .`, `git commit -a`, or a stash, reset or checkout that
  touches files you don't hold. Then run `coord release -a NAME <committed paths>`.
- Project rules still apply: CLAUDE.md, deploy preconditions (e.g. the target app must be closed), commit trailer rules.

**Watched-tree locks** (e.g. `@unity`: an editor that imports and compiles `Assets/` on every write; also any
hot-reloading dev server). The lock guards the *tree*, not just the tool, because a write there is consumed
at once and lands in whoever is compiling now.

1. Claim the lock **before your first write into the watched tree**, including test files, assets, configs
   and copy-ins from scratch. Stage work outside the tree until you hold it.
2. Write, let it compile or import, then read the result (console or log errors and warnings). In a repo with a standalone compile check (e.g. a headless build script), run that instead of waiting on the editor, and release the lock before it.
3. Release only **after your own result is clean**. If it's broken, fix it or revert your files first;
   never leave a broken tree for the next holder.
4. Don't take the lock out of turn. If others are waiting, the holder tells the next one on release.
5. **Hold it only while the tool is actually working for you**: a write-compile-check cycle, a Play-mode
   check or a run. Release it the moment that operation is clean, even if you'll need it again in ten
   minutes. Never hold it while writing code, thinking, researching, or waiting on a reply or the user.
   Re-claim (with `--wait`) for the next cycle.
6. While holding, keep your board state current: `coord state -a NAME working -m "@unity: <what's
   running now>"`. A waiter who sees the holder idle or on another step for over 5 minutes tells the
   orchestrator, which asks the holder to release.

**5. Talking.** `SendMessage` is the live channel; the board is the record.

- **An orchestrator always exists.** Resolve it with `coord addr --role orchestrator` and `SendMessage` that
  name. If that fails or finds none, try `coord addr orchestrator`, then leave `coord note --to orchestrator`
  and carry on. Never conclude there is no orchestrator. To reach another agent, `coord addr NAME`.
- Anything the orchestrator must act on goes to it by `SendMessage`: a blocker, a decision for the user,
  a conflict, a result.
- **Heartbeat when unheard.** With no reply, send a one-line status by `SendMessage` about every 15 min of
  wall time and at each phase change. Never end a turn without a report while holding a lock or leaving a
  background job running (a build, a wait): report first what you wait on and what wakes you.
- **No loops.** The same command or step three times without new information: stop and report. A command
  that fails twice in a row: stop and report. Don't retry a third time.
- Messages from other sessions arrive as `<cross-session-message from=... from-name=...>`. Reply to the
  `from` id.
- A decision the user made that other agents should respect gets logged: `coord note -a NAME --kind
  decision "..."`.
- Don't message other workers directly about files they hold; go through the orchestrator, which
  sequences.

**6. Finish.** When the task is done:

1. `coord state -a NAME done -m "<one line>"` (or `review` if it is waiting on the user to test).
2. Release what you no longer need. Uncommitted edits stay claimed until committed or handed off; say so.
3. Report to the orchestrator by `SendMessage`. The report's first line is `STATUS: DONE`,
   `STATUS: PARTIAL` or `STATUS: BLOCKED`.
   - **DONE**: one-line summary, files changed, evidence (the command and its actual output; a log line
     that proves the behaviour), and what is untested.
   - **PARTIAL**: what is done, with evidence, and an explicit list of what remains and why you stopped.
   - **BLOCKED**: what you need, what you tried, and what would unblock it.

   A check you did not run is reported as not run.
4. After DONE, wind down (step 7) unless you have a reason to stay open.

**7. Wind down.** Do this after reporting DONE, or when the orchestrator asks you to. A finished worker
doesn't sit open.

1. **Write your summary** to `<coord dir>/summaries/NAME.md` (`coord where` prints the coord dir; create
   `summaries/` if it is missing). It is the record the user and orchestrator read after your tab is gone,
   so write it for someone who never saw your session:

   ```markdown
   # NAME, <YYYY-MM-DD>
   <one line: what was done>

   **Task:** <the task as given>
   **Changed:** <commits as `hash subject`, or files left uncommitted and why>
   **Untested:** <what was not run or checked, or "nothing">
   **Open questions:** <for the user, or "none">
   ```

2. **Clean up after yourself.** Remove what you generated that isn't part of the result: scratch
   output, temp logs, screenshots and one-off scripts, in the repo or your scratchpad. **Removing means
   sending to the OS trash, never deleting**, one literal absolute path at a time:

   | OS | Command |
   | --- | --- |
   | Windows (PowerShell) | `Add-Type -AssemblyName Microsoft.VisualBasic`, then `[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory('<abs path>', 'OnlyErrorDialogs', 'SendToRecycleBin')` (`DeleteFile` for a file) |
   | Linux | `gio trash '<abs path>'`, or `trash-put '<abs path>'` (trash-cli) where `gio` is absent |
   | macOS 15+ | `trash '<abs path>'` |

   No trash command available: stop and tell the user rather than deleting. Never a variable that could
   be empty, never `rm`, `Remove-Item` or any recursive delete, and **never empty the trash**. Leave a worktree alone: its branch is the user's.
3. `coord leave -a NAME`. This releases everything; don't leave holding uncommitted edits without saying
   so in the summary.
4. Report `WOUND DOWN` to the orchestrator: the summary's path and what you sent to the trash. The
   orchestrator then closes your tab.

**Staying open.** If the orchestrator asks you to wind down and you shouldn't (uncommitted work waiting on
the user's test, an expected follow-up, an unanswered question), reply `STAYING: <why>`. The orchestrator
relays that to the user, who decides.

## Don'ts

- Don't spawn subagents that write files. Read-only `Explore` is fine. A writing subagent would edit
  under your name without the protocol.
- Don't take over another agent's task or files because it looks idle. Tell the orchestrator.
- Don't `reap` anyone. That is the orchestrator's call, with the user's consent.
- Don't hand-roll locks (lock dirs, marker files), and don't write into the coord directory yourself,
  except your own `summaries/NAME.md`.
