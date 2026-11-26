"""signalbox: usage-aware model routing for coding agents.

  signalbox usage [--json] [--fresh] [--save NAME] [--diff NAME]
  signalbox route PHASE [--mode auto|NAME] [--not-family F] [--skip ROUTE] [--json]
  signalbox delegate (--phase PHASE | --route ROUTE) --brief FILE [--cwd DIR] [--read-only] [--dry-run]
  signalbox mark POOL [--hours H | --clear]
  signalbox install [--host claude,codex,cursor,agents | all] [--link]
  signalbox doctor
  signalbox config (path | show | init)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, state
from .hosts import USAGE_LIMIT, build_command, hosts
from .routing import PHASES, DEFAULT_CONFIG, auto_mode, choose, load_config, parse_ref, statuses, user_config_path

EX_USAGE_LIMIT = 75  # EX_TEMPFAIL: the child hit a usage or rate limit
SKILL_DIR = Path(__file__).resolve().parents[2]  # skills/signalbox


def _pct(v: float | None) -> str:
    return "?" if v is None else f"{v:.0f}%"


def _context(args) -> tuple[dict, dict, dict[str, tuple[str, str]], str]:
    cfg = load_config()
    readings = state.read_all(fresh=getattr(args, "fresh", False))
    st = statuses(readings, cfg, state.marks(), check_hosts=not getattr(args, "no_host_check", False))
    mode = getattr(args, "mode", "auto") or "auto"
    if mode == "auto":
        mode = auto_mode(st, cfg)
    return cfg, readings, st, mode


# ------------------------------------------------------------------ usage
def cmd_usage(args) -> int:
    cfg, readings, st, mode = _context(args)
    result = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "pools": {p: {"status": s, "reason": why} for p, (s, why) in st.items()},
        "readings": {p: r.to_dict() for p, r in readings.items()},
    }
    if args.diff:
        result["since"] = state.diff_snapshot(args.diff, readings) or f"no snapshot named {args.diff}"
    if args.save:
        state.save_snapshot(args.save, readings)
    if args.json:
        print(json.dumps(result))
        return 0
    for pool, (status, why) in st.items():
        r = readings.get(pool)
        wins = "  ".join(f"{w.label} {_pct(w.used_pct)}" for w in (r.windows if r and r.ok else []))
        stale = f"  (stale: {r.stale})" if r and r.stale else ""
        print(f"{pool:<12} {status:<8} {wins or '-':<22} {why}{stale}")
    print(f"mode         {mode}")
    if "since" in result:
        print(f"since {args.diff}: {json.dumps(result['since'])}")
    return 0


# ------------------------------------------------------------------ route
def _choose(args, cfg, st, mode):
    return choose(args.phase, mode, st, cfg, not_family=set(args.not_family or []),
                  skip=set(args.skip or []), not_pool=set(args.not_pool or []))


def cmd_route(args) -> int:
    cfg, _, st, mode = _context(args)
    c = _choose(args, cfg, st, mode)
    if args.json:
        print(json.dumps(c.to_dict()))
        return 0 if c.pick else 1
    for s in c.ladder:
        mark = "→" if s is c.pick else " "
        target = f"{s.host} {s.model or '(default model)'}" if s.host else ""
        print(f"{mark} {s.ref:<14} {s.status:<8} {target:<34} {s.reason}")
    if not c.pick:
        print(f"no usable route for {args.phase} in mode {mode}", file=sys.stderr)
        return 1
    return 0


# --------------------------------------------------------------- delegate
def cmd_delegate(args) -> int:
    cfg, readings, st, mode = _context(args)
    if args.route:
        name, effort = parse_ref(args.route)
        r = cfg["routes"].get(name)
        if not r:
            print(f"no route {name!r} in routing.toml", file=sys.stderr)
            return 2
        status = st.get(r["pool"], ("unknown", ""))[0]
        if status in ("out", "missing") and not args.force:
            print(f"route {name} is {status} ({st[r['pool']][1]}); pass --force to use it anyway", file=sys.stderr)
            return EX_USAGE_LIMIT
        host, model, pool, eff = r["host"], r.get("model", ""), r["pool"], args.effort or effort
    else:
        c = _choose(args, cfg, st, mode)
        if not c.pick or c.pick.route == "self":
            why = "the ladder says the orchestrator does this itself" if c.pick else "no usable route"
            print(json.dumps({"delegated": False, "reason": why, **c.to_dict()}))
            return 0 if c.pick else 1
        name, host, model, pool, eff = c.pick.route, c.pick.host, c.pick.model, c.pick.pool, args.effort or c.pick.effort

    brief = sys.stdin.read() if args.brief == "-" else Path(args.brief).read_text()
    cwd = str(Path(args.cwd or os.getcwd()).resolve())
    argv, stdin_text, notes = build_command(host, model, eff, cwd, args.read_only, brief)
    shown = [a if a != brief else "<brief>" for a in argv]
    for n in notes:
        print(f"[signalbox] {n}", file=sys.stderr)
    if args.dry_run:
        print(json.dumps({"route": name, "host": host, "model": model, "effort": eff, "pool": pool,
                          "cwd": cwd, "argv": shown, "brief_on_stdin": stdin_text is not None}))
        return 0

    log_dir = state.state_dir() / "runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}.log"
    print(f"[signalbox] {name}: {host} {model or '(default)'} effort={eff or '-'} → {log}", file=sys.stderr)
    tail: list[str] = []
    with log.open("w") as fh:
        proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if stdin_text is not None:
            assert proc.stdin
            proc.stdin.write(stdin_text)
            proc.stdin.close()
        assert proc.stdout
        for line in proc.stdout:
            sys.stdout.write(line)
            fh.write(line)
            tail = (tail + [line])[-60:]
        code = proc.wait()

    limited = code != 0 and bool(USAGE_LIMIT.search("".join(tail)))
    if limited:
        until = state.mark_out(pool, args.mark_hours)
        print(f"[signalbox] usage limit detected; {pool} marked out until "
              f"{datetime.fromtimestamp(until).strftime('%H:%M')}", file=sys.stderr)
    print(json.dumps({"route": name, "host": host, "model": model, "pool": pool, "exit": code,
                      "usage_limit": limited, "log": str(log)}))
    return EX_USAGE_LIMIT if limited else code


# ------------------------------------------------------------------- mark
def cmd_mark(args) -> int:
    if args.clear:
        state.clear_mark(args.pool)
        print(f"{args.pool}: mark cleared")
    else:
        until = state.mark_out(args.pool, args.hours)
        print(f"{args.pool}: out until {datetime.fromtimestamp(until).isoformat(timespec='minutes')}")
    return 0


# ---------------------------------------------------------------- install
def cmd_install(args) -> int:
    all_hosts = hosts()
    wanted = [h for h in all_hosts if all_hosts[h].skill_dir] if args.host == "all" else args.host.split(",")
    for name in wanted:
        h = all_hosts.get(name)
        if not h or not h.skill_dir:
            print(f"skip {name}: no skill directory known")
            continue
        if args.host == "all" and name != "agents" and not h.skill_dir.parent.exists():
            continue  # host not set up on this machine
        dest = h.skill_dir / "signalbox"
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        elif dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if args.link:
            dest.symlink_to(SKILL_DIR, target_is_directory=True)
        else:
            shutil.copytree(SKILL_DIR, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        print(f"{'linked' if args.link else 'copied'} → {dest}")
    return 0


# ----------------------------------------------------------------- doctor
def cmd_doctor(args) -> int:
    print(f"signalbox {__version__}  python {sys.version.split()[0]}")
    print(f"config       {user_config_path()} ({'found' if user_config_path().exists() else 'using defaults'})")
    print(f"state        {state.state_dir()}")
    for name, h in hosts().items():
        if not h.binaries:
            continue
        b = h.binary()
        installed = "installed" if h.skill_dir and (h.skill_dir / "signalbox").exists() else "not installed"
        print(f"{name:<12} {b or 'not on PATH':<40} skill {installed if h.skill_dir else 'n/a'}")
    args.fresh, args.json, args.save, args.diff = False, False, None, None
    print()
    return cmd_usage(args)


# ----------------------------------------------------------------- config
def cmd_config(args) -> int:
    p = user_config_path()
    if args.action == "path":
        print(p)
    elif args.action == "show":
        print(json.dumps(load_config(), indent=2))
    elif args.action == "init":
        if p.exists() and not args.force:
            print(f"{p} exists; pass --force to overwrite", file=sys.stderr)
            return 1
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(DEFAULT_CONFIG, p)
        print(f"wrote {p}")
    return 0


# ------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="signalbox", description="Usage-aware model routing for coding agents.")
    ap.add_argument("--version", action="version", version=f"signalbox {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def routing_flags(p):
        p.add_argument("--mode", default="auto", help="auto or a mode from routing.toml")
        p.add_argument("--not-family", action="append", metavar="FAMILY", help="skip routes of this family (review rule)")
        p.add_argument("--not-pool", action="append", metavar="POOL", help="skip routes draining this pool")
        p.add_argument("--skip", action="append", metavar="ROUTE", help="skip this route (it already failed)")
        p.add_argument("--no-host-check", action="store_true",
                       help="don't require the route's CLI on PATH (the host delegates natively, e.g. T3 Code)")
        p.add_argument("--fresh", action="store_true", help="ignore the 5-minute usage cache")

    p = sub.add_parser("usage", help="usage per pool and the recommended mode")
    p.add_argument("--json", action="store_true")
    p.add_argument("--fresh", action="store_true")
    p.add_argument("--save", metavar="NAME", help="save a snapshot for --diff")
    p.add_argument("--diff", metavar="NAME", help="usage consumed since snapshot NAME")
    p.add_argument("--no-host-check", action="store_true")
    p.add_argument("--mode", default="auto")
    p.set_defaults(func=cmd_usage)

    p = sub.add_parser("route", help="pick the model for a phase")
    p.add_argument("phase", choices=PHASES)
    routing_flags(p)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_route)

    p = sub.add_parser("delegate", help="run a brief on the routed model's CLI")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--phase", choices=PHASES)
    g.add_argument("--route", help="ROUTE or ROUTE@effort, bypassing the ladder")
    p.add_argument("--brief", required=True, help="file with the brief, or - for stdin")
    p.add_argument("--cwd", help="repo to work in (default: current directory)")
    p.add_argument("--effort", help="override the ladder's effort")
    p.add_argument("--read-only", action="store_true", help="plan and review: no edits")
    p.add_argument("--dry-run", action="store_true", help="print the command instead of running it")
    p.add_argument("--force", action="store_true", help="use a route even if its pool is out")
    p.add_argument("--mark-hours", type=float, default=1.0, help="how long a usage-limit hit marks the pool out")
    routing_flags(p)
    p.set_defaults(func=cmd_delegate)

    p = sub.add_parser("mark", help="mark a pool out (or clear the mark)")
    p.add_argument("pool")
    p.add_argument("--hours", type=float, default=1.0)
    p.add_argument("--clear", action="store_true")
    p.set_defaults(func=cmd_mark)

    p = sub.add_parser("install", help="install the signalbox skill into agent skill folders")
    p.add_argument("--host", default="all", help="comma list of claude,codex,cursor,agents, or all")
    p.add_argument("--link", action="store_true", help="symlink instead of copy (for development)")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("doctor", help="CLIs, skill installs, and usage at a glance")
    p.add_argument("--no-host-check", action="store_true")
    p.add_argument("--mode", default="auto")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("config", help="where the routing config lives")
    p.add_argument("action", choices=["path", "show", "init"])
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_config)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as e:
        print(f"signalbox: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
