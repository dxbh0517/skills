#!/usr/bin/env python3
"""Report Claude Code and Cursor usage and recommend an orchestrator budget mode.

Reads the local logins that Claude Code and Cursor already store, asks each
vendor's own usage endpoint, and prints a short summary plus a JSON line.
Tokens are never printed or written anywhere.

Usage:
  usage.py                 summary + recommendation
  usage.py --json          JSON only
  usage.py --save NAME     also save a snapshot (for per-task cost)
  usage.py --diff NAME     show usage consumed since snapshot NAME
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
STATE_DIR = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "conductor"
TIMEOUT = 15


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


def _pace(utilization: float | None, resets_at: str | None, window_h: float) -> float | None:
    """Utilization minus the share of the window already elapsed (positive = ahead of pace)."""
    if utilization is None or not resets_at:
        return None
    try:
        reset = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    left_h = (reset - datetime.now(timezone.utc)).total_seconds() / 3600
    elapsed = max(0.0, min(1.0, 1 - left_h / window_h))
    return round(utilization - elapsed * 100, 1)


# ---------------------------------------------------------------- Claude Code
def claude_usage() -> dict:
    cred = HOME / ".claude" / ".credentials.json"
    if not cred.exists():
        return {"ok": False, "error": "no Claude Code login (~/.claude/.credentials.json)"}
    try:
        oauth = json.loads(cred.read_text()).get("claudeAiOauth", {})
        tok = oauth["accessToken"]
    except Exception:
        return {"ok": False, "error": "unreadable Claude Code credentials"}
    exp = oauth.get("expiresAt")
    if exp and exp / 1000 < time.time():
        return {"ok": False, "error": "Claude Code token expired; it refreshes on the next Claude run"}
    try:
        d = _get(
            "https://api.anthropic.com/api/oauth/usage",
            {
                "Authorization": f"Bearer {tok}",
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": "conductor-usage",
            },
        )
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"Claude usage endpoint HTTP {e.code}"}
    except Exception as e:  # network etc.
        return {"ok": False, "error": f"Claude usage endpoint failed: {e.__class__.__name__}"}

    def win(key: str, hours: float) -> dict | None:
        w = d.get(key)
        if not w:
            return None
        u = w.get("utilization")
        return {
            "used_pct": u,
            "resets_at": w.get("resets_at"),
            "ahead_of_pace": _pace(u, w.get("resets_at"), hours),
        }

    out = {"ok": True, "five_hour": win("five_hour", 5), "seven_day": win("seven_day", 168)}
    for k in ("seven_day_opus", "seven_day_sonnet"):
        if d.get(k):
            out[k] = win(k, 168)
    extra = d.get("extra_usage") or {}
    out["extra_usage_enabled"] = bool(extra.get("is_enabled"))
    return out


# --------------------------------------------------------------------- Cursor
def _cursor_token() -> str | None:
    db = HOME / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    cands: list[str] = []
    if db.exists():
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
            row = con.execute(
                "select value from ItemTable where key='cursorAuth/accessToken'"
            ).fetchone()
            con.close()
            if row and row[0]:
                cands.append(row[0])
        except Exception:
            pass
    cli = HOME / ".config" / "cursor" / "auth.json"
    if cli.exists():
        try:
            cands.append(json.loads(cli.read_text())["accessToken"])
        except Exception:
            pass
    now = time.time()
    fresh = [t for t in cands if _jwt_payload(t).get("exp", 0) > now]
    return fresh[0] if fresh else None


def cursor_usage() -> dict:
    tok = _cursor_token()
    if not tok:
        return {"ok": False, "error": "no fresh Cursor login (open Cursor or run `cursor-agent login`)"}
    uid = _jwt_payload(tok).get("sub", "").split("|")[-1]
    try:
        d = _get(
            "https://cursor.com/api/usage-summary",
            {
                "Cookie": f"WorkosCursorSessionToken={uid}%3A%3A{tok}",
                "User-Agent": "Mozilla/5.0 conductor-usage",
                "Origin": "https://cursor.com",
            },
        )
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"Cursor usage endpoint HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": f"Cursor usage endpoint failed: {e.__class__.__name__}"}

    plan = (d.get("individualUsage") or {}).get("plan") or {}
    od = (d.get("individualUsage") or {}).get("onDemand") or {}
    return {
        "ok": True,
        "membership": d.get("membershipType"),
        "unlimited": bool(d.get("isUnlimited")),
        "cycle_end": d.get("billingCycleEnd"),
        "auto_used_pct": plan.get("autoPercentUsed"),
        "api_used_pct": plan.get("apiPercentUsed"),
        "total_used_pct": plan.get("totalPercentUsed"),
        "on_demand_enabled": bool(od.get("enabled")),
        "ahead_of_pace": _pace(
            plan.get("totalPercentUsed"), d.get("billingCycleEnd"), 24 * 30
        ),
    }


# ---------------------------------------------------------------------- cache
CACHE_TTL = 300  # seconds; the Claude endpoint rate-limits frequent reads


def cached(name: str, fetch, fresh: bool) -> dict:
    """Return a cached reading younger than CACHE_TTL, else fetch.

    On a failed fetch, fall back to the last good reading marked stale.
    """
    path = STATE_DIR / f"cache-{name}.json"
    old = None
    if path.exists():
        try:
            old = json.loads(path.read_text())
        except Exception:
            old = None
    if old and not fresh and time.time() - old.get("_at", 0) < CACHE_TTL:
        return old
    new = fetch()
    if new.get("ok"):
        new["_at"] = time.time()
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(new))
        return new
    if old:
        age = int((time.time() - old.get("_at", 0)) / 60)
        old["stale"] = f"{new.get('error')}; showing reading from {age} min ago"
        return old
    return new


# ------------------------------------------------------------- recommendation
def recommend(c: dict, k: dict) -> dict:
    """Pool status + budget mode. Default bias: spare Claude."""
    pools = {"claude": "unknown", "cursor-auto": "unknown", "cursor-api": "unknown", "free": "ok"}
    reasons: list[str] = []

    if c.get("ok"):
        h5 = (c.get("five_hour") or {}).get("used_pct") or 0
        d7 = (c.get("seven_day") or {}).get("used_pct") or 0
        pace7 = (c.get("seven_day") or {}).get("ahead_of_pace") or 0
        if h5 >= 90 or d7 >= 92:
            pools["claude"] = "out"
            reasons.append(f"Claude near cap (5h {h5:.0f}%, 7d {d7:.0f}%)")
        elif h5 >= 70 or d7 >= 75 or pace7 > 10:
            pools["claude"] = "tight"
            reasons.append(f"Claude tight (5h {h5:.0f}%, 7d {d7:.0f}%, {pace7:+.0f} vs pace)")
        else:
            pools["claude"] = "ok"
    else:
        reasons.append("Claude usage unknown: treat as tight")
        pools["claude"] = "tight"

    if k.get("ok"):
        if k.get("unlimited"):
            pools["cursor-auto"] = pools["cursor-api"] = "ok"
        else:
            auto = k.get("auto_used_pct") or 0
            api = k.get("api_used_pct") or 0
            od = k.get("on_demand_enabled")
            pools["cursor-auto"] = "out" if auto >= 100 and not od else "tight" if auto >= 85 else "ok"
            pools["cursor-api"] = "out" if api >= 100 and not od else "tight" if api >= 85 else "ok"
            if pools["cursor-api"] == "out":
                reasons.append(f"Cursor API pool used up ({api:.0f}%): no Grok/Gemini/Claude via Cursor")
            if pools["cursor-auto"] != "ok":
                reasons.append(f"Cursor Auto/Composer pool {auto:.0f}% used")
    else:
        reasons.append("Cursor usage unknown: assume Auto/Composer ok, named models tight")
        pools["cursor-auto"], pools["cursor-api"] = "ok", "tight"

    if pools["claude"] == "out":
        mode = "claude-off"
    elif pools["cursor-auto"] == "out" and pools["claude"] == "ok":
        mode = "cursor-frugal"
    elif pools["cursor-auto"] == "out":
        mode = "survival"
    else:
        mode = "claude-frugal"
    return {"mode": mode, "pools": pools, "reasons": reasons}


# ------------------------------------------------------------------ snapshots
def _flat(c: dict, k: dict) -> dict:
    return {
        "claude_5h": (c.get("five_hour") or {}).get("used_pct"),
        "claude_7d": (c.get("seven_day") or {}).get("used_pct"),
        "cursor_auto": k.get("auto_used_pct"),
        "cursor_api": k.get("api_used_pct"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--save")
    ap.add_argument("--diff")
    ap.add_argument("--fresh", action="store_true", help="ignore the 5 min cache")
    a = ap.parse_args()

    c = cached("claude", claude_usage, a.fresh)
    k = cached("cursor", cursor_usage, a.fresh)
    rec = recommend(c, k)
    flat = _flat(c, k)
    result = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "claude": c, "cursor": k, "recommendation": rec, "flat": flat}

    if a.diff:
        p = STATE_DIR / f"{a.diff}.json"
        if p.exists():
            old = json.loads(p.read_text())
            result["since_snapshot"] = {
                key: (round(flat[key] - old[key], 1)
                      if flat.get(key) is not None and old.get(key) is not None else None)
                for key in flat
            }
        else:
            result["since_snapshot"] = f"no snapshot named {a.diff}"
    if a.save:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / f"{a.save}.json").write_text(json.dumps(flat))

    if a.json:
        print(json.dumps(result))
        return 0

    def f(v):
        return "?" if v is None else f"{v:.0f}%"

    def note(x):
        if not x.get("ok"):
            return f"  ({x.get('error')})"
        return f"  (stale: {x['stale']})" if x.get("stale") else ""

    print(f"Claude Code  5h {f(flat['claude_5h'])}  7d {f(flat['claude_7d'])}{note(c)}")
    print(f"Cursor       auto/composer {f(flat['cursor_auto'])}  "
          f"api(named) {f(flat['cursor_api'])}{note(k)}")
    print("Pools        " + "  ".join(f"{p}={s}" for p, s in rec["pools"].items()))
    print(f"Mode         {rec['mode']}")
    for r in rec["reasons"]:
        print(f"  - {r}")
    if "since_snapshot" in result:
        print(f"Since {a.diff}: {result['since_snapshot']}")
    print(json.dumps({"mode": rec["mode"], "pools": rec["pools"], "flat": flat}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
