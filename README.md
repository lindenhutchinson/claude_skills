# linden — Claude Code working standards

A Claude Code **plugin marketplace** holding the conventions I reuse across every repo
in `../`. One source of truth, installed rather than copied.

Everything here is **stack- and domain-agnostic** — how I want work done, not what any
particular project is. Project-specific instructions stay in that project's own
`CLAUDE.md`.

## Install

```powershell
# once per machine
claude
/plugin marketplace add <path to this repo>
/plugin install linden@linden
```

Machine-wide config that plugins cannot ship (`~/.claude/CLAUDE.md`, and skills that
must keep a fixed `~/.claude/skills/<name>` path) lives in `home/` and is linked into
place:

```powershell
pwsh scripts/sync-home.ps1        # add -Force to replace existing files
```

## Layout

| Path | Purpose |
|---|---|
| `.claude-plugin/marketplace.json` | Marketplace manifest. |
| `plugins/linden/` | The plugin: `skills/`, `commands/`, `agents/`. |
| `home/` | Canonical copies of `~/.claude` files, linked by `scripts/sync-home.ps1`. |
| `home/skills/` | User-level skills, not plugin-namespaced (`orchestrator`, `coord-worker`). Each is junctioned to `~/.claude/skills/<name>`; edit them here or there, it is the same directory. |
| `scripts/` | Install and maintenance tooling. |
| `docs/` | Why each convention exists, and how new ones get sourced. |

## Adding to it

Conventions are derived from evidence, not invented — invented best practices get
ignored, codified corrections stick. [`docs/sourcing.md`](docs/sourcing.md) covers how
to mine session transcripts for recurring corrections;
[`docs/conventions.md`](docs/conventions.md) is the registry of what is encoded, what
is queued, and what was deliberately left out.

The bar for landing here is: **it recurred, across more than one project, and it is
true regardless of stack.** Everything else goes in the project.
