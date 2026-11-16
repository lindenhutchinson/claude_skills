#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""coord: the coordination board for several Claude Code sessions working one repository.

One append-only log, ``log.jsonl``, is the only source of truth. Every line is one event carrying a sequence
number. Who is working on what, which files each agent has claimed and what each is blocked on are all derived
by folding the log; nothing else holds state, so nothing can disagree with it.

Every write happens under one mutex: an OS byte-range lock on ``.mutex`` (``msvcrt.locking`` on Windows,
``fcntl.flock`` elsewhere). The kernel drops it when the holding process exits, however it exits, so a crashed
writer can never leave the board locked. The sequence number is read and the line appended inside that one
critical section, which is what makes the log gap-free and strictly ordered.

Claims are the logical locks agents take on repository files (``src/Foo.cs``, ``src/Dir/``) and on named
resources (``@deploy``, ``@git``). They outlive any process by design, so they never expire on their own unless
taken with ``--ttl``; a dead agent's claims are freed with ``reap``, which is logged like everything else.

The board lives in ``<git common dir>/coord`` so every worktree of one repository shares it and git never
tracks it. ``COORD_DIR`` overrides that.

Exit codes: 0 ok, 1 error, 2 claim refused (held by another agent), 3 board mutex timed out, 4 wait timed out.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import posixpath
import random
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

EXIT_OK, EXIT_ERROR, EXIT_CONFLICT, EXIT_MUTEX, EXIT_WAIT = 0, 1, 2, 3, 4

LOG_NAME = "log.jsonl"
MUTEX_NAME = ".mutex"
HOLDER_NAME = ".mutex.holder"

STATES = ("working", "blocked", "review", "idle", "done")
NOTE_KINDS = ("note", "decision", "request", "reply", "deploy")
DEFAULT_WITH_TTL = 30 * 60
CASE_INSENSITIVE = os.name == "nt"


class CoordError(Exception):
    def __init__(self, message: str, code: int = EXIT_ERROR) -> None:
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------------------------- location


def _git(args: list[str], cwd: Path | None = None) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        detail = str(getattr(e, "stderr", e)).strip()
        raise CoordError(f"git {' '.join(args)} failed in {cwd or Path.cwd()}: {detail}") from e
    return out.stdout.strip()


def resolve_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    if env := os.environ.get("COORD_DIR"):
        return Path(env).resolve()
    common = _git(["rev-parse", "--path-format=absolute", "--git-common-dir"])
    return Path(common) / "coord"


def worktree_root(cwd: Path | None = None) -> Path:
    return Path(_git(["rev-parse", "--show-toplevel"], cwd))


# --------------------------------------------------------------------------------------------- mutex


class Mutex:
    """Exclusive OS lock on one byte of ``.mutex``. Released by the kernel if the process dies."""

    def __init__(self, directory: Path, timeout: float, holder: str) -> None:
        self.path = directory / MUTEX_NAME
        self.holder_path = directory / HOLDER_NAME
        self.timeout = timeout
        self.holder = holder
        self.fd: int | None = None

    def __enter__(self) -> Mutex:
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
        deadline = time.monotonic() + self.timeout
        delay = 0.005
        while True:
            try:
                _lock(fd)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    raise CoordError(
                        f"board mutex busy for {self.timeout:.0f}s; last holder: {self._last_holder()}", EXIT_MUTEX
                    ) from None
                time.sleep(delay * (0.5 + random.random()))
                delay = min(delay * 2, 0.2)
        self.fd = fd
        with contextlib.suppress(OSError):
            self.holder_path.write_text(f"{self.holder} pid={os.getpid()} at={_now_iso()}\n", encoding="utf-8")
        return self

    def __exit__(self, *_: object) -> None:
        assert self.fd is not None
        try:
            _unlock(self.fd)
        finally:
            os.close(self.fd)
            self.fd = None

    def _last_holder(self) -> str:
        try:
            return self.holder_path.read_text(encoding="utf-8").strip() or "unknown"
        except OSError:
            return "unknown"


if os.name == "nt":
    import msvcrt

    def _lock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


# --------------------------------------------------------------------------------------------- log


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_iso(ts: str) -> float:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def read_events(directory: Path, since: int = 0) -> list[dict]:
    """Every complete, valid event with seq > since, in file order.

    A final line without its newline is a write in progress (or one that died mid-write and was never
    acknowledged) and is skipped. So is any line that does not parse.
    """
    try:
        raw = (directory / LOG_NAME).read_bytes()
    except FileNotFoundError:
        return []
    lines = raw.split(b"\n")
    lines.pop()  # whatever follows the last newline is incomplete, or empty
    events = []
    for line in lines:
        try:
            event = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(event, dict) and isinstance(event.get("seq"), int) and event["seq"] > since:
            events.append(event)
    return events


def _append_locked(directory: Path, events: list[dict], body: dict) -> dict:
    """Append one event. The caller holds the mutex and has just read ``events`` under it."""
    path = directory / LOG_NAME
    seq = max((e["seq"] for e in events), default=0) + 1
    event = {"seq": seq, "ts": _now_iso(), **body}
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
    try:
        size = os.fstat(fd).st_size
        if size:
            # A writer that died mid-line left no newline. Terminate its fragment rather than rewrite it, so
            # history stays append-only and the fragment reads as one skipped, invalid line.
            with open(path, "rb") as f:
                f.seek(size - 1)
                if f.read(1) != b"\n":
                    data = b"\n" + data
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    return event


# --------------------------------------------------------------------------------------------- keys


def normalize_key(raw: str, root: Path) -> str:
    """A claim key: ``@resource``, a repo-relative file path, or a repo-relative directory ending in ``/``.

    Relative paths are relative to the repository root, never the shell's cwd. An absolute path is made
    relative to the root of whichever worktree contains it, so the same file in two worktrees is one key.
    """
    raw = raw.strip()
    if not raw:
        raise CoordError("empty claim key")
    if raw.startswith("@"):
        if not re.fullmatch(r"@[A-Za-z0-9_.-]+", raw):
            raise CoordError(f"bad resource name {raw!r}")
        return raw.lower()
    is_dir = raw.endswith(("/", "\\"))
    text = raw.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", text) or text.startswith("/"):
        path = Path(raw)
        probe = path if path.is_dir() else path.parent
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        tree = worktree_root(probe)
        try:
            text = path.resolve().relative_to(tree.resolve()).as_posix()
        except ValueError:
            raise CoordError(f"{raw} is not inside the worktree {tree}") from None
        is_dir = is_dir or path.is_dir()
    else:
        is_dir = is_dir or (root / text).is_dir()
    text = posixpath.normpath(text)
    if text in (".", "") or text.startswith("../") or text == "..":
        raise CoordError(f"{raw!r} does not name something inside the repository")
    return text + "/" if is_dir else text


def _fold(key: str) -> str:
    return key.casefold() if CASE_INSENSITIVE else key


def keys_overlap(a: str, b: str) -> bool:
    a, b = _fold(a), _fold(b)
    if a.startswith("@") or b.startswith("@"):
        return a == b
    return a == b or (a.endswith("/") and b.startswith(a)) or (b.endswith("/") and a.startswith(b))


# --------------------------------------------------------------------------------------------- board


@dataclass
class Claim:
    key: str
    agent: str
    seq: int
    ts: str
    expires: float | None
    note: str | None

    def active(self, now: float) -> bool:
        return self.expires is None or self.expires > now


@dataclass
class Agent:
    name: str
    task: str | None = None
    worktree: str | None = None
    msg_name: str | None = None  # the SendMessage/ListAgents name, when it differs from the board name
    role: str | None = None
    state: str = "working"
    on: str | None = None
    note: str | None = None
    last_seq: int = 0
    last_ts: str = ""
    claims: dict[str, Claim] = field(default_factory=dict)  # folded key -> claim


@dataclass
class Board:
    agents: dict[str, Agent] = field(default_factory=dict)  # folded name -> agent
    seq: int = 0

    def agent(self, name: str) -> Agent | None:
        return self.agents.get(name.casefold())

    def active_claims(self, now: float) -> list[Claim]:
        return [c for a in self.agents.values() for c in a.claims.values() if c.active(now)]

    def conflicts(self, agent: str, keys: list[str], now: float) -> list[tuple[str, Claim]]:
        me = agent.casefold()
        return [
            (k, c) for k in keys for c in self.active_claims(now) if c.agent.casefold() != me and keys_overlap(k, c.key)
        ]


def fold(events: list[dict]) -> Board:
    board = Board()
    for e in events:
        board.seq = e["seq"]
        name = e.get("agent")
        if not isinstance(name, str):
            continue
        agent = board.agents.setdefault(name.casefold(), Agent(name))
        agent.last_seq, agent.last_ts = e["seq"], e.get("ts", "")
        match e.get("type"):
            case "join":
                agent.name = name
                agent.task = e.get("task") or agent.task
                agent.worktree = e.get("worktree") or agent.worktree
                agent.msg_name = e.get("msg_name") or agent.msg_name
                agent.role = e.get("role") or agent.role
                agent.state, agent.on, agent.note = "working", None, None
            case "state":
                agent.state, agent.on, agent.note = e.get("state", agent.state), e.get("on"), e.get("note")
            case "claim":
                for key in e.get("keys", []):
                    agent.claims[_fold(key)] = Claim(
                        key, agent.name, e["seq"], e.get("ts", ""), e.get("expires"), e.get("note")
                    )
            case "release":
                keys = e.get("keys")
                if keys is None:
                    agent.claims.clear()
                else:
                    for key in keys:
                        agent.claims.pop(_fold(key), None)
            case "leave":
                agent.claims.clear()
                agent.state, agent.on, agent.note = "left", None, e.get("note")
            case "reap":
                target = board.agents.get(str(e.get("target", "")).casefold())
                if target is not None:
                    target.claims.clear()
                    target.state, target.on, target.note = "reaped", None, e.get("reason")
    return board


# --------------------------------------------------------------------------------------------- commands


@dataclass
class Ctx:
    dir: Path
    agent: str | None
    mutex_timeout: float

    def need_agent(self) -> str:
        if not self.agent:
            raise CoordError("this command needs -a/--agent NAME (or COORD_AGENT)")
        return self.agent

    @contextlib.contextmanager
    def locked(self) -> Iterator[list[dict]]:
        if not (self.dir / LOG_NAME).exists():
            raise CoordError(f"no board at {self.dir}; run `coord init` first")
        with Mutex(self.dir, self.mutex_timeout, self.agent or "?"):
            yield read_events(self.dir)

    def append(self, body: dict) -> dict:
        with self.locked() as events:
            return _append_locked(self.dir, events, body)


def _require_joined(board: Board, name: str) -> Agent:
    agent = board.agent(name)
    if agent is None or agent.state in ("left", "reaped"):
        raise CoordError(f"{name!r} has not joined the board; run `coord join -a {name!r} --task ...` first")
    return agent


def cmd_init(ctx: Ctx, _: argparse.Namespace) -> int:
    ctx.dir.mkdir(parents=True, exist_ok=True)
    (ctx.dir / LOG_NAME).touch(exist_ok=True)
    (ctx.dir / MUTEX_NAME).touch(exist_ok=True)
    readme = ctx.dir / "README.txt"
    if not readme.exists():
        readme.write_text(
            "Coordination board for parallel Claude Code sessions. Managed by coord.py from the coord-worker\n"
            "skill. log.jsonl is append-only and the only state; never edit it by hand. .mutex is the OS\n"
            "lock every writer takes; .mutex.holder only names the last process that held it.\n",
            encoding="utf-8",
        )
    print(ctx.dir.as_posix())
    return EXIT_OK


def cmd_where(ctx: Ctx, _: argparse.Namespace) -> int:
    print(ctx.dir.as_posix())
    return EXIT_OK


def cmd_join(ctx: Ctx, args: argparse.Namespace) -> int:
    name = ctx.need_agent()
    tree = Path(args.worktree).resolve() if args.worktree else worktree_root()
    body = {"agent": name, "type": "join", "task": args.task, "worktree": tree.as_posix()}
    if args.msg_name:
        body["msg_name"] = args.msg_name
    if args.role:
        body["role"] = args.role
    event = ctx.append(body)
    print(f"#{event['seq']} joined as {name!r} in {tree.as_posix()}")
    return EXIT_OK


def cmd_addr(ctx: Ctx, args: argparse.Namespace) -> int:
    """Print the SendMessage name for a board agent, or for whoever joined with --role."""
    board = fold(read_events(ctx.dir))
    live = [a for a in board.agents.values() if a.state not in ("left", "reaped")]
    if args.role:
        found = [a for a in live if (a.role or "").casefold() == args.role.casefold()]
        found += [a for a in live if a not in found and not a.role and a.name.casefold() == args.role.casefold()]
        found.sort(key=lambda a: a.last_seq, reverse=True)
        target = found[0] if found else None
        what = f"role {args.role!r}"
    elif args.name:
        target = next((a for a in live if a.name.casefold() == args.name.casefold()), None)
        what = repr(args.name)
    else:
        raise CoordError("give NAME or --role ROLE")
    if target is None:
        raise CoordError(f"no live agent for {what} on the board; leave a note instead: coord note --to {args.role or args.name} ...")
    print(target.msg_name or target.name)
    if not target.msg_name:
        print(f"coord: {target.name!r} joined without --msg-name; assuming its board name is its SendMessage name", file=sys.stderr)
    return EXIT_OK


def cmd_state(ctx: Ctx, args: argparse.Namespace) -> int:
    name = ctx.need_agent()
    if args.state == "blocked" and not args.on:
        raise CoordError("blocked needs --on WHAT (an agent, a decision, the user)")
    with ctx.locked() as events:
        _require_joined(fold(events), name)
        event = _append_locked(
            ctx.dir, events, {"agent": name, "type": "state", "state": args.state, "on": args.on, "note": args.note}
        )
    print(f"#{event['seq']} {name}: {args.state}" + (f" on {args.on}" if args.on else ""))
    return EXIT_OK


def _try_claim(
    ctx: Ctx, name: str, keys: list[str], ttl: float | None, note: str | None
) -> tuple[dict | None, list[str], list]:
    """One attempt under the mutex. Returns (event, newly taken keys, conflicts).

    Keys already held are left alone, except that a held claim which itself has an expiry is refreshed when a
    ttl is given. A permanent claim never acquires an expiry by being claimed again.
    """
    now = time.time()
    with ctx.locked() as events:
        board = fold(events)
        agent = _require_joined(board, name)
        conflicts = board.conflicts(name, keys, now)
        if conflicts:
            return None, [], conflicts
        held = {k: c for k, c in agent.claims.items() if c.active(now)}
        fresh = [k for k in keys if _fold(k) not in held]
        refresh = [k for k in keys if ttl is not None and (c := held.get(_fold(k))) and c.expires is not None]
        if not fresh and not refresh:
            return {"seq": board.seq, "keys": [], "already": True}, [], []
        body = {
            "agent": name,
            "type": "claim",
            "keys": fresh + refresh,
            "expires": now + ttl if ttl is not None else None,
            "note": note,
        }
        return _append_locked(ctx.dir, events, body), fresh, []


def claim(
    ctx: Ctx, name: str, raw: list[str], ttl: float | None, wait: float, note: str | None
) -> tuple[dict, list[str]]:
    root = worktree_root()
    keys = list(dict.fromkeys(normalize_key(r, root) for r in raw))
    deadline = time.monotonic() + wait
    delay = 0.5
    while True:
        event, fresh, conflicts = _try_claim(ctx, name, keys, ttl, note)
        if event is not None:
            return event, fresh
        if time.monotonic() >= deadline:
            lines = [
                f"  {k} held by {c.agent} since #{c.seq}" + (f" ({c.note})" if c.note else "") for k, c in conflicts
            ]
            raise CoordError("claim refused, nothing claimed:\n" + "\n".join(lines), EXIT_CONFLICT)
        time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
        delay = min(delay * 1.5, 5.0)


def _warn_shared_tree(ctx: Ctx, name: str, keys: list[str]) -> None:
    """A build or deploy in a shared worktree ships every other agent's uncommitted edits too. Say so."""
    if "@deploy" not in keys:
        return
    board = fold(read_events(ctx.dir))
    me = board.agent(name)
    if me is None or not me.worktree:
        return
    now = time.time()
    others = [
        c
        for c in board.active_claims(now)
        if not c.key.startswith("@")
        and c.agent.casefold() != name.casefold()
        and (o := board.agent(c.agent)) is not None
        and o.worktree == me.worktree
    ]
    if others:
        print(
            "warning: this worktree also holds other agents' claimed files; a deploy ships their uncommitted "
            "edits too:",
            file=sys.stderr,
        )
        for c in others:
            print(f"  {c.key} ({c.agent})", file=sys.stderr)


def cmd_claim(ctx: Ctx, args: argparse.Namespace) -> int:
    name = ctx.need_agent()
    event, _ = claim(ctx, name, args.keys, args.ttl, args.wait, args.note)
    if event.get("already"):
        print("already held: " + ", ".join(args.keys))
    else:
        print(
            f"#{event['seq']} {name} claimed {', '.join(event['keys'])}"
            + (f" until {_fmt_clock(event['expires'])}" if event.get("expires") else "")
        )
        _warn_shared_tree(ctx, name, event["keys"])
    return EXIT_OK


def release(ctx: Ctx, name: str, raw: list[str] | None) -> dict | None:
    keys = None if raw is None else [normalize_key(r, worktree_root()) for r in raw]
    with ctx.locked() as events:
        agent = fold(events).agent(name)
        held = agent.claims if agent else {}
        if keys is None:
            if not held:
                return None
        else:
            keys = [k for k in keys if _fold(k) in held]
            if not keys:
                return None
        return _append_locked(ctx.dir, events, {"agent": name, "type": "release", "keys": keys})


def cmd_release(ctx: Ctx, args: argparse.Namespace) -> int:
    name = ctx.need_agent()
    if bool(args.keys) == args.all:
        raise CoordError("give the keys to release, or --all")
    event = release(ctx, name, None if args.all else args.keys)
    print(
        "nothing held to release"
        if event is None
        else f"#{event['seq']} {name} released {'everything' if event['keys'] is None else ', '.join(event['keys'])}"
    )
    return EXIT_OK


def cmd_with(ctx: Ctx, args: argparse.Namespace) -> int:
    name = ctx.need_agent()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise CoordError("usage: coord with -a NAME KEY... -- COMMAND ARGS...")
    note = args.note or " ".join(command)
    _, keys = claim(ctx, name, args.keys, args.ttl, args.wait, note)
    _warn_shared_tree(ctx, name, keys)
    print(f"[coord] holding {', '.join(args.keys)}; running: {' '.join(command)}", file=sys.stderr, flush=True)
    try:
        code = subprocess.run(command).returncode
    except OSError as e:
        print(f"[coord] could not run {command[0]}: {e}", file=sys.stderr)
        code = 127
    finally:
        if keys:  # release only what this call took; a key held beforehand stays held
            with ctx.locked() as events:
                _append_locked(ctx.dir, events, {"agent": name, "type": "release", "keys": keys})
    print(f"[coord] released; command exited {code}", file=sys.stderr)
    return code


def cmd_check(ctx: Ctx, args: argparse.Namespace) -> int:
    root = worktree_root()
    board = fold(read_events(ctx.dir))
    now = time.time()
    for raw in args.keys:
        key = normalize_key(raw, root)
        holders = [c for c in board.active_claims(now) if keys_overlap(key, c.key)]
        print(f"{key}: " + (", ".join(f"{c.agent} via {c.key} (#{c.seq})" for c in holders) or "free"))
    return EXIT_OK


def cmd_note(ctx: Ctx, args: argparse.Namespace) -> int:
    name = ctx.need_agent()
    event = ctx.append({"agent": name, "type": "note", "kind": args.kind, "to": args.to, "text": " ".join(args.text)})
    print(f"#{event['seq']} logged")
    return EXIT_OK


def cmd_leave(ctx: Ctx, args: argparse.Namespace) -> int:
    name = ctx.need_agent()
    event = ctx.append({"agent": name, "type": "leave", "note": args.note})
    print(f"#{event['seq']} {name} left; all its claims released")
    return EXIT_OK


def cmd_reap(ctx: Ctx, args: argparse.Namespace) -> int:
    name = ctx.need_agent()
    with ctx.locked() as events:
        target = fold(events).agent(args.target)
        if target is None:
            raise CoordError(f"no agent {args.target!r} on the board")
        event = _append_locked(
            ctx.dir, events, {"agent": name, "type": "reap", "target": target.name, "reason": args.reason}
        )
    print(f"#{event['seq']} reaped {target.name}; freed {len(target.claims)} claim(s)")
    return EXIT_OK


def _age(ts: str, now: float) -> str:
    if not ts:
        return "-"
    s = max(0, int(now - _parse_iso(ts)))
    return f"{s}s" if s < 90 else f"{s // 60}m" if s < 5400 else f"{s // 3600}h" if s < 172800 else f"{s // 86400}d"


def _fmt_clock(epoch: float) -> str:
    return datetime.fromtimestamp(epoch).strftime("%H:%M")


def cmd_status(ctx: Ctx, args: argparse.Namespace) -> int:
    board = fold(read_events(ctx.dir))
    now = time.time()
    agents = sorted(board.agents.values(), key=lambda a: a.last_seq, reverse=True)
    if not args.all:
        agents = [a for a in agents if a.state not in ("left", "reaped")]
    if args.json:
        print(
            json.dumps(
                {
                    "dir": ctx.dir.as_posix(),
                    "seq": board.seq,
                    "agents": [
                        {
                            "name": a.name,
                            "task": a.task,
                            "worktree": a.worktree,
                            "msg_name": a.msg_name,
                            "role": a.role,
                            "state": a.state,
                            "on": a.on,
                            "note": a.note,
                            "last_seq": a.last_seq,
                            "last_ts": a.last_ts,
                            "claims": [
                                {"key": c.key, "seq": c.seq, "expires": c.expires, "note": c.note}
                                for c in a.claims.values()
                                if c.active(now)
                            ],
                        }
                        for a in agents
                    ],
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        return EXIT_OK
    print(f"board {ctx.dir.as_posix()}  at #{board.seq}")
    trees = {a.worktree for a in agents if a.worktree}
    for a in agents:
        tree = f"  [{Path(a.worktree).name}]" if a.worktree and len(trees) > 1 else ""
        on = f" on {a.on}" if a.on else ""
        msg = f" [msg: {a.msg_name}]" if a.msg_name and a.msg_name != a.name else ""
        print(f"- {a.name}{msg}: {a.state}{on}  (seen {_age(a.last_ts, now)} ago, #{a.last_seq}){tree}")
        if a.task:
            print(f"    task: {a.task}")
        if a.note:
            print(f"    note: {a.note}")
        live = [c for c in a.claims.values() if c.active(now)]
        if live:
            print(
                "    claims: "
                + ", ".join(c.key + (f" (until {_fmt_clock(c.expires)})" if c.expires else "") for c in live)
            )
    return EXIT_OK


def _fmt_event(e: dict) -> str:
    t = e.get("type")
    head = f"#{e['seq']} {e.get('ts', '')[11:19]} {e.get('agent', '?')}"
    match t:
        case "join":
            body = f"joined: {e.get('task')}"
        case "state":
            body = (
                f"{e.get('state')}"
                + (f" on {e['on']}" if e.get("on") else "")
                + (f": {e['note']}" if e.get("note") else "")
            )
        case "claim":
            body = "claim " + ", ".join(e.get("keys", [])) + (f"  ({e['note']})" if e.get("note") else "")
        case "release":
            body = "release " + ("everything" if e.get("keys") is None else ", ".join(e["keys"]))
        case "note":
            to = f" -> {e['to']}" if e.get("to") else ""
            body = f"{e.get('kind', 'note')}{to}: {e.get('text')}"
        case "leave":
            body = "left" + (f": {e['note']}" if e.get("note") else "")
        case "reap":
            body = f"reaped {e.get('target')}: {e.get('reason')}"
        case _:
            body = json.dumps(e, ensure_ascii=False)
    return f"{head}  {body}"


def _matches(e: dict, args: argparse.Namespace) -> bool:
    if args.types and e.get("type") not in args.types:
        return False
    if args.about:
        who = {str(e.get(k, "")).casefold() for k in ("agent", "to", "target", "on")}
        if args.about.casefold() not in who:
            return False
    return True


def cmd_tail(ctx: Ctx, args: argparse.Namespace) -> int:
    events = [e for e in read_events(ctx.dir, args.since) if _matches(e, args)]
    if args.since == 0:
        events = events[-args.n :]
    for e in events:
        print(json.dumps(e, ensure_ascii=False) if args.json else _fmt_event(e))
    return EXIT_OK


def cmd_wait(ctx: Ctx, args: argparse.Namespace) -> int:
    """Block, in-process, until an event after --since matches. Meant for run_in_background."""
    log = ctx.dir / LOG_NAME
    deadline = time.monotonic() + args.timeout
    last_size = -1
    while True:
        size = log.stat().st_size if log.exists() else 0
        if size != last_size:
            last_size = size
            hits = [
                e
                for e in read_events(ctx.dir, args.since)
                if _matches(e, args) and (not ctx.agent or str(e.get("agent", "")).casefold() != ctx.agent.casefold())
            ]
            if hits:
                for e in hits:
                    print(_fmt_event(e))
                return EXIT_OK
        if time.monotonic() >= deadline:
            print(f"nothing new after #{args.since} within {args.timeout:.0f}s")
            return EXIT_WAIT
        time.sleep(1.0)


# --------------------------------------------------------------------------------------------- cli


def duration(text: str) -> float:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([smhd]?)", text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"bad duration {text!r}; use 90, 90s, 15m, 2h")
    return float(m[1]) * {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[m[2]]


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-a",
        "--agent",
        default=os.environ.get("COORD_AGENT"),
        help="your agent name, as other sessions know you (default: $COORD_AGENT)",
    )
    common.add_argument("--dir", help="board directory (default: $COORD_DIR, else <git common dir>/coord)")
    common.add_argument("--mutex-timeout", type=duration, default=duration("15s"), help=argparse.SUPPRESS)

    p = argparse.ArgumentParser(
        prog="coord", description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    def add(name: str, fn, help: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, parents=[common], help=help, description=help)
        sp.set_defaults(fn=fn)
        return sp

    add("init", cmd_init, "create the board if missing and print its path")
    add("where", cmd_where, "print the board path")

    sp = add("join", cmd_join, "register (or re-register) yourself with your task")
    sp.add_argument("--task", required=True)
    sp.add_argument("--worktree", help="defaults to the worktree containing the cwd")
    sp.add_argument("--msg-name", help="your SendMessage/ListAgents name, if it differs from -a (kept across re-joins)")
    sp.add_argument("--role", help="e.g. orchestrator; lets `coord addr --role` find you (default for -a orchestrator)")

    sp = add("addr", cmd_addr, "print the SendMessage name of a board agent, or of the one holding --role")
    sp.add_argument("name", nargs="?")
    sp.add_argument("--role", help="e.g. orchestrator")

    sp = add("state", cmd_state, "set your state: " + ", ".join(STATES))
    sp.add_argument("state", choices=STATES)
    sp.add_argument("-m", "--note", help="one line: what you are doing, or why you are blocked")
    sp.add_argument("--on", help="what you are blocked on (required for blocked)")

    sp = add("claim", cmd_claim, "claim files, directories (trailing /) or @resources; all or nothing")
    sp.add_argument("keys", nargs="+")
    sp.add_argument("--ttl", type=duration, help="claim lapses after this long (default: never)")
    sp.add_argument("--wait", type=duration, default=0.0, help="wait this long for holders to release")
    sp.add_argument("--note")

    sp = add("release", cmd_release, "release some of your claims, or --all")
    sp.add_argument("keys", nargs="*")
    sp.add_argument("--all", action="store_true")

    sp = add("with", cmd_with, "claim KEYS, run COMMAND, release KEYS however it ends")
    sp.add_argument("keys", nargs="+", help="keys, then -- and the command")
    sp.add_argument("--ttl", type=duration, default=DEFAULT_WITH_TTL)
    sp.add_argument("--wait", type=duration, default=duration("10m"))
    sp.add_argument("--note")
    sp.add_argument("command", nargs=argparse.REMAINDER)

    sp = add("check", cmd_check, "who holds these keys")
    sp.add_argument("keys", nargs="+")

    sp = add("note", cmd_note, "log a note, decision, request or reply")
    sp.add_argument("text", nargs="+")
    sp.add_argument("--kind", choices=NOTE_KINDS, default="note")
    sp.add_argument("--to", help="the agent (or 'user') it is addressed to")

    sp = add("leave", cmd_leave, "leave the board, releasing every claim")
    sp.add_argument("-m", "--note")

    sp = add("reap", cmd_reap, "free a dead agent's claims (orchestrator, after confirming it is gone)")
    sp.add_argument("target")
    sp.add_argument("--reason", required=True)

    sp = add("status", cmd_status, "the board: every agent, its state, task and live claims")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--all", action="store_true", help="include agents that left or were reaped")

    for name, fn, help in (
        ("tail", cmd_tail, "print events"),
        ("wait", cmd_wait, "block until a new matching event by someone else, then print it"),
    ):
        sp = add(name, fn, help)
        sp.add_argument("--since", type=int, default=0, help="only events after this seq")
        sp.add_argument("--type", dest="types", action="append", help="only this event type (repeatable)")
        sp.add_argument("--about", help="only events by, to, or about this agent")
        if name == "tail":
            sp.add_argument("-n", type=int, default=20, help="last N events when --since is not given")
            sp.add_argument("--json", action="store_true")
        else:
            sp.add_argument("--timeout", type=duration, default=duration("30m"))
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError):
            stream.reconfigure(encoding="utf-8", errors="replace")
    argv = sys.argv[1:] if argv is None else argv
    # `with KEYS -- CMD`: argparse cannot split positional keys from a REMAINDER on its own.
    if argv[:1] == ["with"] and "--" in argv:
        i = argv.index("--")
        head, command = argv[:i], argv[i + 1 :]
        args = build_parser().parse_args([*head])
        args.command = command
    else:
        args = build_parser().parse_args(argv)
        if args.cmd == "with":
            raise SystemExit("coord with: separate the command with --")
    try:
        ctx = Ctx(resolve_dir(args.dir), args.agent, args.mutex_timeout)
        return args.fn(ctx, args)
    except CoordError as e:
        print(f"coord: {e}", file=sys.stderr)
        return e.code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
