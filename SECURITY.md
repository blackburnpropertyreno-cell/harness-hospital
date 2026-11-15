# Security policy

## Reporting a problem

Please report a suspected security problem privately, through GitHub's private vulnerability reporting:
the **Security** tab of this repository, then **Report a vulnerability**. Only the maintainer sees the report
until a fix is out.

Please do not open a public issue for it.

Include:

- The file affected (for example `kit/hook.py` or `kit/harness.py`) and the version (`CHANGELOG.md`).
- What untrusted input reaches what it should not, and how to reproduce it.
- A suggested fix, if you have one.

Remove passwords, keys, personal paths and private project data from anything you paste.

## What is in scope

- The hook script, which Claude Code runs automatically on every tool call in a project where it is
  installed.
- The ledger command, and the shell commands it runs from a project's `.harness/config.json` (the checking
  script, the promotion command, the handoff save and fetch commands, and the autosave command).
- The installers, `install.py` and `kit/hooks_install.py`, which write to your Claude Code skills folder and
  settings files.

Problems in Claude Code itself are out of scope; report those to Anthropic.

## Before you use it

Read [docs/security.md](docs/security.md). In short: a project's `.harness/config.json` can run shell
commands on your computer, so read it before you use a project you did not set up; and the hooks are guard
rails for well-meaning sessions, not a security boundary.

## Supported versions

Only the latest version is supported. This project is early (see the README), so please update before
reporting.
