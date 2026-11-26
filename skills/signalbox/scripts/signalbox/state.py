"""Cache, snapshots, and manual pool marks under $XDG_CACHE_HOME/signalbox."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .pools import POOL_SOURCE, READERS, Reading, home

CACHE_TTL = 300  # seconds; the Claude endpoint rate-limits frequent reads
FAIL_BACKOFF = 60  # seconds before retrying a source whose read failed


def state_dir() -> Path:
    if os.environ.get("SIGNALBOX_STATE_DIR"):
        return Path(os.environ["SIGNALBOX_STATE_DIR"])
    return Path(os.environ.get("XDG_CACHE_HOME") or home() / ".cache") / "signalbox"


def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default


def _write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(p)


def _as_tuple(r: Reading | tuple[Reading, ...]) -> tuple[Reading, ...]:
    return r if isinstance(r, tuple) else (r,)


def read_source(source: str, fresh: bool = False) -> tuple[Reading, ...]:
    """Readings for one source, from a cache younger than CACHE_TTL when possible.
    A failed fetch falls back to the last good reading, marked stale."""
    path = state_dir() / f"cache-v2-{source}.json"
    old = _read_json(path, None)
    if not isinstance(old, dict) or not isinstance(old.get("readings"), list):
        old = None  # missing, corrupt, or another tool's format
    now = time.time()
    if old and not fresh:
        if old.get("_failed") and now < old.get("_retry_after", 0):
            return tuple(Reading.from_dict(d) for d in old["readings"])  # recent failure: don't hammer
        if not old.get("_failed") and now - old.get("_at", 0) < CACHE_TTL:
            return tuple(Reading.from_dict(d) for d in old["readings"])
    new = _as_tuple(READERS[source]())
    if all(r.ok for r in new):
        _write_json(path, {"_at": now, "readings": [r.to_dict() for r in new]})
        return new
    good = old if old and not old.get("_failed") else (old.get("_last_good") if old else None)
    if good:
        age = int((now - good.get("_at", 0)) / 60)
        result = tuple(Reading.from_dict(d) for d in good["readings"])
        for r in result:
            r.stale = f"{new[0].error}; showing reading from {age} min ago"
    else:
        result = new
    _write_json(path, {"_at": now, "_failed": True, "_retry_after": now + FAIL_BACKOFF,
                       "readings": [r.to_dict() for r in result], "_last_good": good})
    return result


def read_all(fresh: bool = False, sources: list[str] | None = None) -> dict[str, Reading]:
    out: dict[str, Reading] = {}
    for source in sources or list(READERS):
        for r in read_source(source, fresh):
            out[r.pool] = r
    out["free"] = Reading("free", True)
    return out


# ---------------------------------------------------------------- marks
def marks() -> dict[str, float]:
    """Pools marked out by hand or after a usage-limit error: {pool: until_ts}."""
    data = _read_json(state_dir() / "marks.json", {})
    now = time.time()
    return {k: v for k, v in data.items() if v > now}


def mark_out(pool: str, hours: float) -> float:
    data = marks()
    until = time.time() + hours * 3600
    data[pool] = until
    _write_json(state_dir() / "marks.json", data)
    return until


def clear_mark(pool: str) -> None:
    data = marks()
    data.pop(pool, None)
    _write_json(state_dir() / "marks.json", data)


# ---------------------------------------------------------------- snapshots
def flat(readings: dict[str, Reading]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for pool, r in readings.items():
        for w in r.windows:
            out[f"{pool}:{w.label}"] = w.used_pct
    return out


def save_snapshot(name: str, readings: dict[str, Reading]) -> None:
    _write_json(state_dir() / "snapshots" / f"{name}.json", flat(readings))


def diff_snapshot(name: str, readings: dict[str, Reading]) -> dict[str, float | None] | None:
    old = _read_json(state_dir() / "snapshots" / f"{name}.json", None)
    if old is None:
        return None
    now = flat(readings)
    return {k: (round(v - old[k], 1) if v is not None and old.get(k) is not None else None) for k, v in now.items()}


__all__ = ["POOL_SOURCE", "read_all", "read_source", "marks", "mark_out", "clear_mark", "save_snapshot", "diff_snapshot", "flat"]
