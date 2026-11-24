# Skills

Personal agent skills. Each skill lives in `skills/<name>/SKILL.md`, with
optional `references/` and `scripts/`.

## Install

```bash
./install.sh            # link all skills
./install.sh conductor
```

This symlinks each skill into `~/.agents/skills`, `~/.claude/skills`, and
`~/.cursor/skills`, so edits here are live everywhere. Existing non-symlink
folders with the same name are left alone.

## Skills

| Skill | What it does |
| --- | --- |
| [conductor](skills/conductor/SKILL.md) | Makes a Cursor Auto thread in T3 Code an orchestrator that routes planning, coding, review, CI, PR and merge to the cheapest model that can do each well. Tracks live Claude Code and Cursor usage (`scripts/usage.py`) and spares Claude by default. |
