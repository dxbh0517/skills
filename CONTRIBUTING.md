# Contributing

Thanks for helping. Bug reports, fixes to existing skills, and new skills
are all welcome.

## Reporting a problem

Open an issue with:

- the skill and the agent you used it with (Claude Code, Cursor, T3 Code
  and version),
- what you asked for, what the agent did, and what you expected,
- relevant output, with tokens, emails, and private paths removed.

## Adding a skill

1. Create `skills/<name>/SKILL.md`. Use lowercase kebab-case for `<name>`.
2. Start it with frontmatter:

   ```yaml
   ---
   name: <name>
   description: What it does and when to use it. Include the phrases users type.
   ---
   ```

3. Put the instructions below the frontmatter. Put long tables, templates,
   and examples in `references/`, and helper scripts in `scripts/`.
4. Run `./install.sh <name>` and try the skill in a real session.
5. Add a row to the **Skills** table in [README.md](README.md).

### What makes a good skill

- **The description triggers the skill.** Name the task and the words a
  user would say. Vague descriptions never fire, and broad ones fire when
  they shouldn't.
- **Write steps the agent can follow:** numbered phases, clear exit
  conditions, and defaults for every decision so the agent asks the user
  only when it has to.
- **Keep `SKILL.md` short.** Everything in it is loaded every time the
  skill runs. Move rarely needed material into `references/` and link to it.
- **Scripts use the standard library only.** They must not print, log, or
  store secrets, and must fail cleanly (report `unknown`, don't crash) when
  a login or file is missing.
- **No personal data:** no real emails, tokens, machine names, or private
  repo paths in skills or examples.

## Pull requests

- Branch from `main` and keep each PR to one skill or one change.
- Explain what changed and how you tested it (which agent, what prompt).
- Before opening, check that scripts still run:

  ```bash
  python3 -m py_compile skills/*/scripts/*.py
  bash -n install.sh
  ```

By contributing, you agree that your work is released under the
[MIT License](LICENSE).
