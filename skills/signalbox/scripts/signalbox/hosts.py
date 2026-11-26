"""Agent CLIs signalbox can delegate to, and where each one reads skills from."""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .pools import home

READ_ONLY_PREFIX = "Read only: do not edit, create, or delete files, and do not commit.\n\n"

# Output that means the child hit a usage or rate limit, not a task failure.
USAGE_LIMIT = re.compile(
    r"usage limit|rate[ _-]?limit|quota|limit reached|limit exceeded|exceeded your|out of (credits|usage)"
    r"|too many requests|\b429\b|overloaded|try again (in|after|later)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Host:
    name: str
    binaries: tuple[str, ...]
    skill_dir: Path | None  # where this host loads user skills from
    efforts: tuple[str, ...] = ()  # accepted effort values; empty = no effort flag

    def binary(self) -> str | None:
        for b in self.binaries:
            path = shutil.which(b)
            if path:
                return path
        return None


def hosts() -> dict[str, Host]:
    h = home()
    return {
        "claude": Host("claude", ("claude",), h / ".claude" / "skills", ("low", "medium", "high", "xhigh", "max")),
        "codex": Host("codex", ("codex",), h / ".codex" / "skills", ("minimal", "low", "medium", "high", "xhigh")),
        "cursor": Host("cursor", ("cursor-agent", "agent"), h / ".cursor" / "skills"),
        "opencode": Host("opencode", ("opencode",), None),
        # The cross-agent location from the Agent Skills standard.
        "agents": Host("agents", (), h / ".agents" / "skills"),
    }


def clamp_effort(host: Host, effort: str | None) -> str | None:
    if not effort or not host.efforts:
        return None
    if effort in host.efforts:
        return effort
    # max → xhigh on Codex, minimal → low on Claude, and so on.
    order = ["minimal", "low", "medium", "high", "xhigh", "max"]
    want = order.index(effort) if effort in order else order.index("medium")
    return min(host.efforts, key=lambda e: abs(order.index(e) - want))


def build_command(host_name: str, model: str, effort: str | None, cwd: str, read_only: bool,
                  prompt: str) -> tuple[list[str], str | None, list[str]]:
    """argv, stdin text, and notes about anything that could not be honored."""
    host = hosts()[host_name]
    exe = host.binary() or host.binaries[0]
    eff = clamp_effort(host, effort)
    notes: list[str] = []
    if effort and not eff:
        notes.append(f"{host_name} has no effort setting; ignored {effort}")
    elif effort and eff != effort:
        notes.append(f"effort {effort} → {eff} for {host_name}")

    if host_name == "claude":
        argv = [exe, "-p", "--output-format", "text", "--permission-mode", "plan" if read_only else "acceptEdits"]
        if model:
            argv += ["--model", model]
        if eff:
            argv += ["--effort", eff]
        return argv, prompt, notes

    if host_name == "codex":
        argv = [exe, "exec", "--skip-git-repo-check", "-C", cwd, "-s", "read-only" if read_only else "workspace-write"]
        if model:
            argv += ["-m", model]
        if eff:
            argv += ["-c", f'model_reasoning_effort="{eff}"']
        return argv, prompt, notes

    if host_name == "cursor":
        argv = [exe, "-p", "--output-format", "text", "--trust", "--workspace", cwd]
        argv += ["--plan"] if read_only else ["--force"]
        if model:
            argv += ["--model", model]
        return argv + [prompt], None, notes

    if host_name == "opencode":
        if read_only:
            notes.append("opencode has no read-only sandbox; the brief asks it not to edit")
            prompt = READ_ONLY_PREFIX + prompt
        argv = [exe, "run"] + (["-m", model] if model else [])
        return argv + [prompt], None, notes

    raise ValueError(f"no command builder for host {host_name!r}")
