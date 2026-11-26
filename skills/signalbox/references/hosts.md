# Delegating from each host

`signalbox route` picks a route: a host CLI, a model, an effort and a pool.
How you hand the brief to that model depends on where you are running.

## T3 Code

T3 Code's `delegate_task` reaches every provider, so use it, not
`signalbox delegate`.

1. `signalbox route <phase> --no-host-check --json`. `--no-host-check` keeps
   routes whose CLI isn't installed on this machine.
2. Map the pick to `orchestrator_capabilities`: `host` claude → the Claude
   provider, codex → Codex, cursor → Cursor, opencode → OpenCode. Use the
   pick's `model`; when it's empty, use that provider's default.
3. Pass the effort in `target.options` (`effort` for Claude,
   `reasoning_effort` for Cursor and Codex).
4. `mode: "async"`, then end your turn. T3 wakes you when the child finishes.

## Claude Code

- Pick is Claude and the model you are on: use your `Agent` tool.
- Anything else: `signalbox delegate --phase <phase> --brief <file> --cwd <repo>`
  in Bash. It runs `codex exec`, `cursor-agent -p`, `opencode run` or
  `claude -p --model ...` and streams the output. Use `run_in_background`
  for long children and wait for the notification instead of polling.

## Codex

- Pick is Codex: use your own subagent or do it in a fresh `codex exec`.
- Anything else: `signalbox delegate ...` in the shell. The sandbox must
  allow running the other CLIs and their network access.

## Cursor (agent or `cursor-agent`)

- Pick is a Cursor model: use your own subagent with that model.
- Anything else: `signalbox delegate ...` in the terminal.

## What `delegate` runs

| Host | Command | Read-only (`--read-only`) | Effort |
| --- | --- | --- | --- |
| claude | `claude -p --model M --effort E`, brief on stdin | `--permission-mode plan` (else `acceptEdits`) | low…max |
| codex | `codex exec -C DIR -m M -c model_reasoning_effort=E`, brief on stdin | `-s read-only` (else `workspace-write`) | minimal…xhigh (max → xhigh) |
| cursor | `cursor-agent -p --workspace DIR --model M "<brief>"` | `--plan` (else `--force`) | none |
| opencode | `opencode run -m M "<brief>"` | brief says not to edit (no sandbox) | none |

Each run's output is logged under `~/.cache/signalbox/runs/`. The last line
is JSON: `{"route", "exit", "usage_limit", "log", ...}`. Exit code 75 means
a usage or rate limit hit, and the pool is now marked out.
