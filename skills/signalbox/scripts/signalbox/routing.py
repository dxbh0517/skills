"""Pool status and route selection from routing.toml."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .hosts import hosts
from .pools import Reading, home

DEFAULT_CONFIG = Path(__file__).with_name("routing.toml")
PHASES = ("plan-m", "plan-l", "implement", "review-s", "review-m", "review-risk", "ci-fix")
STATUSES = ("ok", "tight", "out", "unknown", "missing")


def user_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or home() / ".config"
    return Path(os.environ.get("SIGNALBOX_CONFIG") or Path(base) / "signalbox" / "routing.toml")


def load_config(path: Path | None = None) -> dict:
    """Default config with the user's tables laid over it (one level deep)."""
    cfg = tomllib.loads(DEFAULT_CONFIG.read_text())
    user = path or user_config_path()
    if user.exists():
        over = tomllib.loads(user.read_text())
        for key, value in over.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key] = {**cfg[key], **value}
            else:
                cfg[key] = value
    return cfg


# ------------------------------------------------------------------ status
def pool_status(pool: str, reading: Reading | None, cfg: dict, marked_until: float | None = None) -> tuple[str, str]:
    """(status, reason) for one pool."""
    rules = cfg.get("pools", {}).get(pool, {})
    if marked_until:
        return "out", "marked out after a usage-limit error"
    if reading is None or not reading.ok:
        return rules.get("unknown", "tight"), (reading.error if reading else "no reading") or "unknown"
    if reading.unlimited or not reading.windows:
        return "ok", "unlimited" if reading.unlimited else "no limits reported"
    out_at, tight_at, pace_at = rules.get("out", 100), rules.get("tight", 85), rules.get("pace")
    worst, why = "ok", ""
    for w in reading.windows:
        if w.used_pct is None:
            continue
        if w.used_pct >= out_at:
            if reading.overage:
                worst, why = "tight", f"{w.label} {w.used_pct:.0f}% used, paying overage"
            else:
                return "out", f"{w.label} {w.used_pct:.0f}% used"
        elif w.used_pct >= tight_at or (pace_at is not None and (w.ahead_of_pace or 0) > pace_at):
            if worst == "ok":
                pace_note = f", {w.ahead_of_pace:+.0f} vs pace" if w.ahead_of_pace is not None else ""
                worst, why = "tight", f"{w.label} {w.used_pct:.0f}% used{pace_note}"
    return worst, why or "within limits"


def pool_hosts(cfg: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for r in cfg.get("routes", {}).values():
        out.setdefault(r["pool"], set()).add(r["host"])
    return out


def statuses(readings: dict[str, Reading], cfg: dict, marks: dict[str, float],
             check_hosts: bool = True) -> dict[str, tuple[str, str]]:
    """Status per pool. With check_hosts, a pool none of whose CLIs is installed is `missing`."""
    installed = {name for name, h in hosts().items() if h.binary()}
    out = {}
    for pool, pool_host_names in pool_hosts(cfg).items():
        if check_hosts and not (pool_host_names & installed):
            out[pool] = ("missing", f"no {'/'.join(sorted(pool_host_names))} CLI on PATH")
        else:
            out[pool] = pool_status(pool, readings.get(pool), cfg, marks.get(pool))
    return out


# ------------------------------------------------------------------ modes
def _matches(want: str | list[str], have: str) -> bool:
    return have in ([want] if isinstance(want, str) else want)


def auto_mode(st: dict[str, tuple[str, str]], cfg: dict) -> str:
    for rule in cfg.get("auto", []):
        if all(_matches(want, st.get(pool, ("unknown", ""))[0]) for pool, want in rule.get("when", {}).items()):
            return rule["mode"]
    return "claude-frugal"


# ------------------------------------------------------------------ routes
@dataclass
class Step:
    ref: str
    route: str
    effort: str | None
    status: str
    reason: str
    host: str | None = None
    model: str | None = None
    pool: str | None = None
    family: str | None = None


@dataclass
class Choice:
    phase: str
    mode: str
    pick: Step | None
    ladder: list[Step] = field(default_factory=list)

    def to_dict(self) -> dict:
        def s(x: Step | None):
            return None if x is None else {k: v for k, v in x.__dict__.items() if v is not None}
        return {"phase": self.phase, "mode": self.mode, "pick": s(self.pick), "ladder": [s(x) for x in self.ladder]}


def parse_ref(ref: str) -> tuple[str, str | None]:
    route, _, effort = ref.partition("@")
    return route, effort or None


def choose(phase: str, mode: str, st: dict[str, tuple[str, str]], cfg: dict, *,
           not_family: set[str] = frozenset(), skip: set[str] = frozenset(),
           not_pool: set[str] = frozenset()) -> Choice:
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase!r}; one of {', '.join(PHASES)}")
    modes = cfg.get("modes", {})
    if mode not in modes:
        raise ValueError(f"unknown mode {mode!r}; one of {', '.join(modes)}")
    ladder: list[Step] = []
    for ref in modes[mode].get(phase, []):
        name, effort = parse_ref(ref)
        if name == "self":
            ladder.append(Step(ref, "self", effort, "ok", "orchestrator does it"))
            continue
        r = cfg.get("routes", {}).get(name)
        if r is None:
            ladder.append(Step(ref, name, effort, "missing", "no such route in routing.toml"))
            continue
        step = Step(ref, name, effort, *st.get(r["pool"], ("unknown", "no status")),
                    host=r["host"], model=r.get("model", ""), pool=r["pool"], family=r.get("family"))
        if name in skip:
            step.status, step.reason = "skipped", "--skip"
        elif r["pool"] in not_pool:
            step.status, step.reason = "skipped", f"--not-pool {r['pool']}"
        elif step.family in not_family:
            step.status, step.reason = "skipped", f"same family as the author ({step.family})"
        ladder.append(step)
    pick = next((s for s in ladder if s.status == "ok"), None) or next((s for s in ladder if s.status == "tight"), None)
    return Choice(phase, mode, pick, ladder)
