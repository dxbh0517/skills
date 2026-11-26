"""Usage readers for each model pool.

Each reader uses the login the vendor's own CLI already stored and returns a
`Reading`. Tokens are never printed, logged, or written anywhere.

Pools:
  claude        Claude Code subscription: 5-hour and 7-day windows
  cursor-auto   Cursor Auto / Composer allowance
  cursor-api    Cursor named-model (API-priced) allowance
  codex         Codex CLI (ChatGPT plan): 5-hour and weekly windows, from session logs
  free          free or local models: always ok
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

TIMEOUT = 15


def home() -> Path:
    return Path(os.environ.get("SIGNALBOX_HOME") or Path.home())


@dataclass
class Window:
    label: str  # "5h", "7d", "cycle", ...
    used_pct: float | None
    resets_at: str | None = None  # ISO 8601, UTC
    hours: float | None = None  # window length, for pace
    ahead_of_pace: float | None = None  # used % minus elapsed %; positive = burning fast

    def __post_init__(self) -> None:
        if self.ahead_of_pace is None and self.hours:
            self.ahead_of_pace = pace(self.used_pct, self.resets_at, self.hours)


@dataclass
class Reading:
    pool: str
    ok: bool
    windows: list[Window] = field(default_factory=list)
    error: str | None = None
    unlimited: bool = False
    overage: bool = False  # pay-as-you-go beyond the allowance is on
    stale: str | None = None
    at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Reading":
        d = dict(d)
        d["windows"] = [Window(**w) for w in d.get("windows", [])]
        return Reading(**d)


def pace(used: float | None, resets_at: str | None, window_h: float) -> float | None:
    if used is None or not resets_at:
        return None
    try:
        reset = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    left_h = (reset - datetime.now(timezone.utc)).total_seconds() / 3600
    elapsed = max(0.0, min(1.0, 1 - left_h / window_h))
    return round(used - elapsed * 100, 1)


def _get(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())


def _jwt_payload(tok: str) -> dict:
    try:
        part = tok.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except Exception:
        return {}


def _http_error(pool: str, what: str, e: Exception) -> Reading:
    if isinstance(e, urllib.error.HTTPError):
        return Reading(pool, False, error=f"{what} HTTP {e.code}")
    return Reading(pool, False, error=f"{what} failed: {e.__class__.__name__}")


# ---------------------------------------------------------------- Claude Code
def read_claude() -> Reading:
    cred = home() / ".claude" / ".credentials.json"
    if not cred.exists():
        return Reading("claude", False, error="no Claude Code login (~/.claude/.credentials.json)")
    try:
        oauth = json.loads(cred.read_text()).get("claudeAiOauth", {})
        tok = oauth["accessToken"]
    except Exception:
        return Reading("claude", False, error="unreadable Claude Code credentials")
    exp = oauth.get("expiresAt")
    if exp and exp / 1000 < time.time():
        return Reading("claude", False, error="Claude Code token expired; it refreshes on the next Claude run")
    try:
        d = _get(
            "https://api.anthropic.com/api/oauth/usage",
            {"Authorization": f"Bearer {tok}", "anthropic-beta": "oauth-2025-04-20", "User-Agent": "signalbox-usage"},
        )
    except Exception as e:
        return _http_error("claude", "Claude usage endpoint", e)
    return parse_claude(d)


def parse_claude(d: dict) -> Reading:
    windows = []
    for key, label, hours in (("five_hour", "5h", 5), ("seven_day", "7d", 168),
                              ("seven_day_opus", "7d-opus", 168), ("seven_day_sonnet", "7d-sonnet", 168)):
        w = d.get(key)
        if w:
            windows.append(Window(label, w.get("utilization"), w.get("resets_at"), hours))
    extra = d.get("extra_usage") or {}
    return Reading("claude", True, windows, overage=bool(extra.get("is_enabled")))


# --------------------------------------------------------------------- Cursor
def _cursor_token() -> str | None:
    cands: list[str] = []
    db = home() / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    if db.exists():
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
            row = con.execute("select value from ItemTable where key='cursorAuth/accessToken'").fetchone()
            con.close()
            if row and row[0]:
                cands.append(row[0])
        except Exception:
            pass
    cli = home() / ".config" / "cursor" / "auth.json"
    if cli.exists():
        try:
            cands.append(json.loads(cli.read_text())["accessToken"])
        except Exception:
            pass
    now = time.time()
    fresh = [t for t in cands if _jwt_payload(t).get("exp", 0) > now]
    return fresh[0] if fresh else None


def read_cursor() -> tuple[Reading, Reading]:
    tok = _cursor_token()
    if not tok:
        err = "no fresh Cursor login (open Cursor or run `cursor-agent login`)"
        return Reading("cursor-auto", False, error=err), Reading("cursor-api", False, error=err)
    uid = _jwt_payload(tok).get("sub", "").split("|")[-1]
    try:
        d = _get(
            "https://cursor.com/api/usage-summary",
            {"Cookie": f"WorkosCursorSessionToken={uid}%3A%3A{tok}", "User-Agent": "Mozilla/5.0 signalbox-usage",
             "Origin": "https://cursor.com"},
        )
    except Exception as e:
        r = _http_error("cursor-auto", "Cursor usage endpoint", e)
        return r, Reading("cursor-api", False, error=r.error)
    return parse_cursor(d)


def parse_cursor(d: dict) -> tuple[Reading, Reading]:
    usage = d.get("individualUsage") or {}
    plan = usage.get("plan") or {}
    od = bool((usage.get("onDemand") or {}).get("enabled"))
    unlimited = bool(d.get("isUnlimited"))
    end = d.get("billingCycleEnd")
    auto = Reading("cursor-auto", True, [Window("cycle", plan.get("autoPercentUsed"), end, 24 * 30)],
                   unlimited=unlimited, overage=od)
    api = Reading("cursor-api", True, [Window("cycle", plan.get("apiPercentUsed"), end, 24 * 30)],
                  unlimited=unlimited, overage=od)
    return auto, api


# ---------------------------------------------------------------------- Codex
def _codex_session_files(limit: int = 20) -> list[Path]:
    root = Path(os.environ.get("CODEX_HOME") or home() / ".codex") / "sessions"
    if not root.is_dir():
        return []
    files = sorted(root.rglob("rollout-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def _codex_window(label: str, w: dict, observed_at: float) -> Window:
    minutes = w.get("window_minutes")
    resets_at = None
    if w.get("resets_at"):
        resets_at = datetime.fromtimestamp(float(w["resets_at"]), timezone.utc).isoformat()
    elif w.get("resets_in_seconds") is not None:
        resets_at = datetime.fromtimestamp(observed_at + float(w["resets_in_seconds"]), timezone.utc).isoformat()
    return Window(label, w.get("used_percent"), resets_at, minutes / 60 if minutes else None)


def parse_codex_line(line: str, observed_at: float) -> Reading | None:
    """One rollout line → Reading, if it is a token_count event with rate limits."""
    try:
        ev = json.loads(line)
    except ValueError:
        return None
    payload = ev.get("payload") if isinstance(ev, dict) else None
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None
    rl = payload.get("rate_limits")
    if not isinstance(rl, dict):
        return None
    windows = []
    for key, default in (("primary", "5h"), ("secondary", "7d")):
        w = rl.get(key)
        if isinstance(w, dict) and w.get("used_percent") is not None:
            minutes = w.get("window_minutes")
            label = default if not minutes else ("5h" if minutes <= 300 else "7d" if minutes >= 10080 else f"{minutes}m")
            windows.append(_codex_window(label, w, observed_at))
    return Reading("codex", True, windows) if windows else None


def read_codex() -> Reading:
    """Latest rate-limit snapshot Codex wrote to its session logs. Experimental:
    the log format is not a public API. Codex only writes it during a session,
    so the reading is as old as your last Codex run (see `stale`)."""
    files = _codex_session_files()
    if not files:
        return Reading("codex", False, error="no Codex session logs (~/.codex/sessions); run Codex once")
    for f in files:
        mtime = f.stat().st_mtime
        try:
            lines = f.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            r = parse_codex_line(line, mtime)
            if r:
                r.at = mtime
                age_min = int((time.time() - mtime) / 60)
                if age_min > 30:
                    r.stale = f"last Codex session {age_min} min ago"
                return r
    return Reading("codex", False, error="Codex session logs have no rate-limit data")


READERS: dict[str, Callable[[], Reading | tuple[Reading, ...]]] = {
    "claude": read_claude,
    "cursor": read_cursor,
    "codex": read_codex,
}
POOL_SOURCE = {"claude": "claude", "cursor-auto": "cursor", "cursor-api": "cursor", "codex": "codex"}
