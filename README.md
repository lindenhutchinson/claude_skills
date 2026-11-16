# linden — Claude Code working standards

My Claude Code setup: how I want work done, kept in one place and installed rather than
copied between projects. Windows, Linux and macOS.

Everything here is **stack- and domain-agnostic**. Project-specific instructions stay in
that project's own `CLAUDE.md`.

It comes in two halves, because a plugin cannot ship everything:

| Half | What | Installed by |
|---|---|---|
| `plugins/linden/` | Skills and commands: `verify-live`, `quality-gate`, `checkpoint-review`, `committee-review`, `docs-staleness-sweep`, `repo-orientation`, `write-claude-md`, `/wrap-up`. | Claude Code's plugin system |
| `home/` | The global `CLAUDE.md`, and user-level skills that must keep a fixed `~/.claude/skills/<name>` path (`orchestrator`, `coord-worker`). Plugin skills are namespaced (`linden:<skill>`), which would break the scripts these two call by path. | `scripts/sync_home.py` |

## Install

Needs [Claude Code](https://code.claude.com) and [uv](https://docs.astral.sh/uv/) (or
any Python 3.12+).

```sh
git clone https://github.com/lindenhutchinson/claude_skills
cd claude_skills
uv run scripts/sync_home.py          # link home/ into ~/.claude
```

Then, inside Claude Code:

```
/plugin marketplace add lindenhutchinson/claude_skills
/plugin install linden@linden
```

### What `sync_home.py` does

It links, never copies, so editing a file in the repo or in `~/.claude` edits the same
file, and a `git pull` updates what Claude loads.

- Each directory in `home/skills/` becomes `~/.claude/skills/<name>`: a symlink on
  Linux and macOS, a junction on Windows (no privileges needed).
- Every other file in `home/` is symlinked at the same path under `~/.claude`. On
  Windows a file symlink needs Developer Mode or an elevated shell; without either the
  file is copied and the script warns that the copy will drift.
- It is safe to re-run. Anything already in the way is skipped; `--force` moves it into
  `~/.claude/backups/sync-home/<timestamp>/` and links. Nothing is deleted.
- `--dry-run` shows what it would do. `$CLAUDE_CONFIG_DIR` overrides `~/.claude`.

## Layout

| Path | Purpose |
|---|---|
| `.claude-plugin/marketplace.json` | Marketplace manifest. |
| `plugins/linden/` | The plugin: `skills/`, `commands/`. |
| `home/` | Canonical copies of `~/.claude` files. |
| `home/skills/` | User-level skills, linked into `~/.claude/skills/`. |
| `scripts/sync_home.py` | Links `home/` into place. |
| `docs/` | Why each convention exists, and how new ones get sourced. |

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
