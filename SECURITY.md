# Security policy

## Scope

Some skills include scripts that run on your machine. For example,
`skills/conductor/scripts/usage.py` reads the Claude Code and Cursor login
tokens stored locally so it can query each vendor's usage endpoint.
Security problems include, among others:

- a script that prints, logs, caches, or sends a token anywhere other than
  the vendor's own endpoint,
- `install.sh` overwriting or deleting files it didn't create,
- skill instructions that lead an agent to leak secrets, bypass branch
  protection, or take destructive actions without the user's approval.

## Reporting a vulnerability

Do not open a public issue. Use GitHub's
[private vulnerability reporting](https://github.com/dxbh0517/skills/security/advisories/new)
and include the steps to reproduce and the impact.

You should hear back within 7 days. Fixes go to `main`; there are no
versioned releases to backport to.
