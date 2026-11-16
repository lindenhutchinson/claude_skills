# linden — Claude Code working standards

My Claude Code setup: how I want work done, kept in one place and installed rather than
copied between projects. Windows, Linux and macOS.

Everything here is **stack- and domain-agnostic**. Project-specific instructions stay in
that project's own `CLAUDE.md`.

It comes in two halves, because a plugin cannot ship everything:

| Half | What | Installed by |
|---|---|---|
| `plugins/linden/` | Skills (`verify-live`, `quality-gate`, `checkpoint-review`, `committee-review`, `docs-staleness-sweep`, `repo-orientation`, `write-claude-md`, and `/wrap-up`, which only runs when invoked), and guard hooks over every shell command. | Claude Code's plugin system |
| `home/` | The global `CLAUDE.md`; settings a plugin cannot set (`attribution`, permissions); and user-level skills that must keep a fixed `~/.claude/skills/<name>` path (`orchestrator`, `coord-worker`). Plugin skills are namespaced (`linden:<skill>`), which would break the scripts these two call by path. | `scripts/sync_home.py` |

## Install

Needs [Claude Code](https://code.claude.com) and [uv](https://docs.astral.sh/uv/). The
guard hooks run through `uv`, so it must be on the `PATH` Claude Code starts with.

```sh
git clone https://github.com/lindenhutchinson/claude_skills
cd claude_skills
uv run scripts/sync_home.py
claude plugin marketplace add lindenhutchinson/claude_skills
claude plugin install linden@linden
```

Third-party marketplaces do not auto-update by default. Turn it on in `/plugin`, or run
`claude plugin update linden@linden`. A marketplace added from a local path is copied
into the plugin cache too, keyed by commit: commit, then update, to pick up a change.

### What `sync_home.py` does

- Each directory in `home/skills/` becomes `~/.claude/skills/<name>`: a symlink on
  Linux and macOS, a junction on Windows (no privileges needed).
- `home/settings.json` is **merged** into `~/.claude/settings.json`, never linked:
  Claude Code writes `/model` and `/config` choices into that file. Objects merge,
  arrays gain the repo's entries, other values take the repo's. What the repo applied
  last time is recorded in `~/.claude/sync-home/`, so an entry removed from the repo is
  removed from the machine on the next run.
- Every other file in `home/` is symlinked at the same path under `~/.claude`, so
  editing either side edits the same file. On Windows a file symlink needs Developer
  Mode or an elevated shell; without either the file is copied and the script warns
  that the copy will drift.
- It is safe to re-run. Anything already in the way is skipped; `--force` moves it into
  `~/.claude/sync-home/backups/<timestamp>/` and links. `settings.json` is backed up
  there before any merge that changes it. Nothing is deleted.
- `--dry-run` shows what it would do. `$CLAUDE_CONFIG_DIR` overrides `~/.claude`.

Claude Code ignores a symlinked `~/.claude/CLAUDE.md` in Cowork desktop sessions.

### The guards

A PreToolUse hook (`plugins/linden/hooks/`) runs over every Bash, PowerShell and
Monitor command:

- **Denied:** recursive deletes in any shell or language, emptying the trash, and
  `Co-Authored-By` trailers on commits and pull requests.
- **Asked:** `git reset --hard`, forced or deleting pushes, `git clean -f`, whole-tree
  `checkout`/`restore`, `branch -D`, `stash clear`/`drop`, SQL `DROP`/`TRUNCATE`.

It is a textual scan, not a sandbox, and errs towards matching: a commit message that
mentions `rm -rf` is blocked too. Each rule is a module in `hooks/guards/`; adding a
file adds a guard.

## Layout

| Path | Purpose |
|---|---|
| `.claude-plugin/marketplace.json` | Marketplace manifest. |
| `plugins/linden/` | The plugin: `skills/`, `hooks/`. |
| `home/` | Canonical copies of `~/.claude` files, and `settings.json` to merge. |
| `home/skills/` | User-level skills, linked into `~/.claude/skills/`. |
| `scripts/` | `sync_home.py` and the settings merge it uses. |
| `tests/` | Guard and merge tests. |
| `docs/` | Why each convention exists, and how new ones get sourced. |

## Developing

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
claude plugin validate . && claude plugin validate plugins/linden
```

CI runs the same on Linux, Windows and macOS.

## Adding to it

Conventions are derived from evidence, not invented: invented best practices get
ignored, codified corrections stick. [`docs/sourcing.md`](docs/sourcing.md) covers how
to mine session transcripts for recurring corrections;
[`docs/conventions.md`](docs/conventions.md) is the registry of what is encoded, what
is queued, and what was deliberately left out.

The bar for landing here: **it recurred, across more than one project, and it is true
regardless of stack.** Everything else goes in the project.

A new user-level skill goes in `home/skills/<name>/`; run `sync_home.py` again to link it.

## License

[MIT](LICENSE)
