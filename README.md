# Skills

Agent skills for Claude Code, Cursor, and other agents that read
`SKILL.md`, focused on multi-model orchestration in
[T3 Code](https://github.com/pingdotgg/t3code).

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Skills: 7](https://img.shields.io/badge/skills-7-brightgreen.svg)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)

- [About](#about)
- [Skills](#skills)
- [Quick start](#quick-start)
- [How skills are laid out](#how-skills-are-laid-out)
- [The conductor skill](#the-conductor-skill)
- [Requirements](#requirements)
- [Privacy and security](#privacy-and-security)
- [Contributing](#contributing)
- [License](#license)

## About

Coding agents keep getting more capable, but every model draws on a usage
pool, and the strong models run out first. These skills set out how an
agent should split up work, which model does each part, and when to stop.

A skill is a folder holding a `SKILL.md`: YAML frontmatter (`name`,
`description`) followed by Markdown instructions. An agent loads it when a
request matches its description. Skills can carry reference docs and
helper scripts, which the agent reads or runs only when needed.

Everything here is plain Markdown and Python from the standard library.
There is nothing to build and no dependencies to install. `install.sh`
symlinks each skill into the folders where agents look for skills, so a
`git pull` updates every agent at once.

## Skills

| Skill | Trigger phrases | What it does |
| --- | --- | --- |
| [conductor](skills/conductor/SKILL.md) | "orchestrate", "conduct", "conductor", "save my usage limits" | Turns a cheap Cursor Auto thread in T3 Code into an orchestrator. It splits a task into plan, implement, review, CI, PR, and merge phases, and sends each phase to the cheapest model that can do it well. It tracks live Claude Code and Cursor usage, uses Claude sparingly by default, and stays on the PR until checks pass and it merges. |
| [ship](skills/ship/SKILL.md) | "ship it", "create a PR and merge it", "merge and deploy", "push the migration" | Opens the PR, gets checks green, merges, then runs the repo's post-merge steps from `.ship.md`: deploy, migration on the right database, local container update, upstream PR sync, app build. It verifies each one. `scripts/detect.py` proposes a ship file. |
| [pr-triage](skills/pr-triage/SKILL.md) | any PR watcher wake-up | Sorts each PR event into noise (deploy-preview bot comments, stale or duplicate events), CI failure, rebase, review finding, green or done, and acts on it. Noise gets no tokens and no message. |
| [council](skills/council/SKILL.md) | "council", "council review" | Several models from different families review the same work in parallel and score it out of 10. Later rounds review only what changed. It stops when the target is met, only nits remain, scores plateau, or the round cap is reached. |
| [design-pass](skills/design-pass/SKILL.md) | "improve the design", "use the taste skill", "polish the UI", "taste council" | Picks one or two installed design skills for the surface, audits with screenshots, builds within the project's components and tokens, checks the result with responsive-qa, and can run a multi-model taste review. |
| [responsive-qa](skills/responsive-qa/SKILL.md) | "overflowing", "not fully visible", "broken on mobile", "still showing on Safari" | Measures overflow, clipped content, oversized dialogs, tap targets and sticky-bar gaps at phone, tablet and desktop widths with `scripts/layout-check.js`. Checks WebKit and confirms the project's own components were reused. |
| [feature-audit](skills/feature-audit/SKILL.md) | "make sure each feature works", "audit the app", "what's broken" | Builds a feature inventory from routes, APIs, jobs and tables (`scripts/inventory.py`), tests each feature with evidence, fixes small breaks, and reports a pass/broken/partial table. |

## Quick start

```bash
git clone https://github.com/dxbh0517/skills.git
cd skills
./install.sh              # link every skill
./install.sh ship council # or only the ones you name
```

`install.sh` creates symlinks in:

| Agent | Skills folder |
| --- | --- |
| Generic (`.agents` convention) | `~/.agents/skills/<name>` |
| Claude Code | `~/.claude/skills/<name>` |
| Cursor | `~/.cursor/skills/<name>` |

It is safe to run more than once. Symlinks it made before are refreshed.
If a real folder with the same name already exists, the script leaves it
alone and prints `skip`, so it never overwrites a skill you installed
another way.

**Update:** `git pull`. The symlinks point into this checkout, so the
change shows up right away.

**Uninstall:** remove the symlinks, for example:

```bash
rm ~/.agents/skills/conductor ~/.claude/skills/conductor ~/.cursor/skills/conductor
```

**Use:** start a new agent session and ask for what the skill does
("conduct this: add rate limiting to the API"), or call it by name if your
agent supports slash commands (`/conductor`).

## How skills are laid out

```
skills/
└── <name>/
    ├── SKILL.md          # required: frontmatter + instructions
    ├── references/       # optional: docs the skill reads on demand
    └── scripts/          # optional: helpers the skill runs
```

`SKILL.md` frontmatter:

```yaml
---
name: my-skill            # matches the folder name
description: What it does and when to use it, including trigger phrases.
---
```

The `description` decides when the agent picks the skill, so put the
phrases users will actually type into it. Keep `SKILL.md` to the steps the
agent always needs, and move tables and templates into `references/` so
they load only when needed.

## The conductor skill

The main thread runs on **Cursor Auto**, a cheap model, and acts as the
orchestrator. It sizes the task, writes self-contained briefs, and hands
each phase to a child agent through T3 Code's `delegate_task`:

```
triage ──► plan ──► implement ──► review ──► PR ──► CI ──► merge
 (Auto)   (varies)  (Composer)   (another     (Auto, stays on the PR
                                  model family) until green and merged)
```

Highlights:

- **Size-based phases.** XS fixes skip planning and review. L tasks are
  split into parallel slices in separate worktrees.
- **Routing ladders.** Each phase has a ranked list of models. A failure, a
  usage-limit error, or two failed check runs moves the task one step up.
  See [`references/routing.md`](skills/conductor/references/routing.md).
- **Usage-aware budget modes.** [`scripts/usage.py`](skills/conductor/scripts/usage.py)
  reads Claude Code's 5-hour and 7-day windows and Cursor's Auto and
  named-model pools, then recommends a mode: `claude-frugal` (default),
  `claude-off`, `cursor-frugal`, `survival`, or `balanced`.
- **Review by another model family.** A model never reviews code from its
  own family.
- **Owns the PR until it merges.** The orchestrator fixes failing checks,
  conflicts, and review findings, and watches the PR until it merges. Say
  "full stop" to have it stop at the merge gate without merging.
- **Ledger and report.** Each phase is logged with its model, pool, and
  result. The final report includes the usage the task consumed.

### `usage.py`

```bash
python3 skills/conductor/scripts/usage.py              # summary + recommended mode
python3 skills/conductor/scripts/usage.py --json       # JSON only
python3 skills/conductor/scripts/usage.py --save task  # snapshot before a task
python3 skills/conductor/scripts/usage.py --diff task  # usage consumed since the snapshot
python3 skills/conductor/scripts/usage.py --fresh      # skip the 5-minute cache
```

Change which model handles which phase by editing
[`references/routing.md`](skills/conductor/references/routing.md). The
brief templates the orchestrator fills in are in
[`references/briefs.md`](skills/conductor/references/briefs.md).

## Requirements

- **Any skill:** an agent that loads `SKILL.md` skills (Claude Code,
  Cursor, or another agent that follows the `~/.agents/skills` convention),
  plus `bash` for `install.sh`.
- **conductor:**
  - [T3 Code](https://github.com/pingdotgg/t3code) with its orchestration tools
    (`delegate_task`, `orchestrator_capabilities`, PR tools).
  - Logged-in Claude Code and/or Cursor providers. Free OpenCode or local
    models are optional.
  - Python 3.8+ (standard library only) for `usage.py`.
  - The GitHub CLI (`gh`), authenticated, for PR and CI work.

- **ship:** `git`, the GitHub CLI (`gh`), and the CLIs for your deploy
  host and migration tool. `detect.py` needs Python 3.8+ (standard library
  only). It prints database **provider and host** only, never credentials.
- **council, design-pass, feature-audit:** multi-model parts use T3 Code's
  `delegate_task`. They also run with any harness that has subagents.
- **responsive-qa:** a browser the agent can drive (T3 Code preview tools or
  Playwright). WebKit checks use `npx playwright` when it is available.
- **design-pass** routes to third-party design skills such as
  `impeccable`, `apple-design`, `emil-design-eng`, and
  `design-taste-frontend`. It uses whichever ones you have installed.

`usage.py` reads Cursor's login from Linux paths
(`~/.config/Cursor/...`, `~/.config/cursor/auth.json`). On other systems
the Cursor reading may show `unknown`. The skill still works and treats
the pool as `tight`.

## Privacy and security

`usage.py` reads the login tokens Claude Code
(`~/.claude/.credentials.json`) and Cursor already keep on your machine.
It sends them only to each vendor's own usage endpoint
(`api.anthropic.com` and `cursor.com`). Tokens are never printed, logged,
or written to disk. Cached readings and snapshots in
`~/.cache/conductor/` hold only usage percentages, reset times, and the
Cursor plan type.

To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Contributing

Issues and pull requests are welcome. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for how to add a skill and what a good
`SKILL.md` looks like.

## License

[MIT](LICENSE) © dxbh0517

Not affiliated with Anthropic, Cursor, or T3 Code. Product names belong to
their owners.
