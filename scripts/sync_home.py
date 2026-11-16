#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Link the canonical config in home/ into the Claude config directory.

home/ is the source of truth for machine-wide Claude config that a plugin cannot ship. Everything is linked,
never copied, so editing either side edits the same thing:

- each directory in home/skills/ is a user-level skill, linked as a directory at <config>/skills/<name>;
- every other file in home/ is linked as a file at the same relative path.

On Linux and macOS links are symlinks. On Windows a directory is linked as a junction, which needs no
privileges, and a file as a symlink, which needs Developer Mode or an elevated shell; without either the file
is copied, with a warning that the copy will drift.

The config directory is $CLAUDE_CONFIG_DIR if set, else ~/.claude. Re-running is safe: correct links are left
alone. An existing target that is not the right link is skipped unless --force is given, in which case it is
moved, never deleted, into <config>/backups/sync-home/<timestamp>/.

Exit codes: 0 everything linked, 1 something was skipped or copied, 2 usage or environment error.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WINDOWS = os.name == "nt"
REPO_HOME = Path(__file__).resolve().parent.parent / "home"
SKILLS = "skills"


def config_dir() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override).expanduser() if override else Path.home() / ".claude"


def is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def links_to(dest: Path, source: Path) -> bool:
    return is_link(dest) and dest.resolve() == source.resolve()


def link_dir(dest: Path, source: Path) -> None:
    if WINDOWS:
        # A junction needs no privilege. mklink is the documented way to make one.
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dest), str(source)],
            check=True,
            capture_output=True,
            text=True,
        )
    else:
        dest.symlink_to(source, target_is_directory=True)


class Syncer:
    def __init__(self, target: Path, force: bool, dry_run: bool) -> None:
        self.target = target
        self.force = force
        self.dry_run = dry_run
        self.backup_root = target / "backups" / "sync-home" / datetime.now().strftime("%Y%m%d-%H%M%S")
        self.incomplete = False

    def report(self, action: str, label: str, detail: str = "") -> None:
        prefix = "[dry run] " if self.dry_run else ""
        print(f"{prefix}{action:<7}{label}{f'  ({detail})' if detail else ''}")

    def make_room(self, dest: Path, source: Path, label: str) -> bool:
        """True when dest is free to be linked."""
        if not (dest.exists() or is_link(dest)):
            return True
        if links_to(dest, source):
            self.report("ok", label, "already linked")
            return False
        if not self.force and source.is_file() and dest.is_file() and filecmp.cmp(source, dest, shallow=False):
            self.report("copy", label, "identical copy, not a link; it will drift. --force replaces it with a link")
            self.incomplete = True
            return False
        if not self.force:
            self.report("skip", label, "exists; re-run with --force to move it to backups/ and link")
            self.incomplete = True
            return False
        backup = self.backup_root / dest.relative_to(self.target)
        self.report("backup", label, f"moved to {backup}")
        if not self.dry_run:
            backup.parent.mkdir(parents=True, exist_ok=True)
            # Renaming a link moves the link itself, never what it points at.
            dest.rename(backup)
        return True

    def sync_skill(self, source: Path) -> None:
        dest = self.target / SKILLS / source.name
        label = f"{SKILLS}/{source.name}/"
        if not self.make_room(dest, source, label):
            return
        if not self.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            link_dir(dest, source)
        self.report("link", label)

    def sync_file(self, source: Path) -> None:
        relative = source.relative_to(REPO_HOME)
        dest = self.target / relative
        label = relative.as_posix()
        if not self.make_room(dest, source, label):
            return
        if self.dry_run:
            self.report("link", label)
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.symlink_to(source)
            self.report("link", label)
        except OSError as error:
            shutil.copy2(source, dest)
            self.incomplete = True
            self.report(
                "copy",
                label,
                f"symlink failed: {error.strerror}; this copy will drift. On Windows, "
                "enable Developer Mode or run once from an elevated shell with --force",
            )

    def run(self) -> None:
        skills = REPO_HOME / SKILLS
        if skills.is_dir():
            for source in sorted(p for p in skills.iterdir() if p.is_dir()):
                self.sync_skill(source)
        for source in sorted(p for p in REPO_HOME.rglob("*") if p.is_file()):
            if skills not in source.parents:
                self.sync_file(source)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--force",
        action="store_true",
        help="move an existing target that is not the right link into backups/, then link",
    )
    parser.add_argument("--dry-run", action="store_true", help="print what would happen; change nothing")
    args = parser.parse_args()

    target = config_dir()
    if not target.is_dir():
        print(f"No Claude config directory at {target}. Run Claude Code once first.", file=sys.stderr)
        return 2

    syncer = Syncer(target, force=args.force, dry_run=args.dry_run)
    syncer.run()
    return 1 if syncer.incomplete else 0


if __name__ == "__main__":
    sys.exit(main())
