# Security

## Read a project's rules file before you trust it

A project set up with this kit has a rules file, `.harness/config.json`. **Some of its settings are shell
commands, and the kit runs them on your computer, in the project folder, with your permissions.** They are:

| Setting in `config.json` | When it runs |
|---|---|
| `checks.<kind>.script` | every time a worker marks a task of that kind finished (`done`), and when `check` is run |
| `promote.cmd` | when a verified result is promoted into the project's files (`promote`) |
| `handoff.push_cmd` | when the project is handed off (`stamp`) |
| `handoff.pull_cmd` | when the project is taken over on another computer (`resume`) |
| `autosave.cmd` | **automatically**, every few minutes, by the hook after a tool call, in any session working in the project |

The last one matters most: once a project is registered on your computer and its hooks are installed, the
autosave command runs without anyone typing anything.

So treat a project folder that you did not set up yourself (one you cloned, downloaded or were sent) the way
you would treat a script from a stranger. **Before you run the ledger command in it, register it on your
computer (`init` or `register-path`), or install the hooks for it, open `.harness/config.json` and read
every one of those settings.** If you do not understand a command, remove it or ask someone who does.

A folder that has not been registered on your computer is inert: the hook ignores sessions started in it.

The same caution applies to a project's own `.claude/` settings folder, which Claude Code itself reads.

## The hooks are guard rails, not a security boundary

The hooks keep a well-meaning session inside the lines: they refuse a write to a protected file, a fetch
from a blocked site, a worker peeking at the answers to the known-answer cases. They are **not** designed to
stop a session that is deliberately trying to get around them, and they will not protect you from a
malicious project or a malicious prompt.

## Shell commands are checked by pattern only

When a session writes a file with Claude Code's file tools, the tool names the file, so the hook checks it
exactly. A shell command can write anywhere, including from inside a script, and the hook sees only the
command text. It catches the obvious cases (redirecting into a protected file, deleting it, opening a
protected database for writing, commands that look like downloads from a blocked site). It will not catch a
script that writes somewhere it should not.

The backstops are the ledger copies taken every few minutes, the promotion step (only verified results
reach the project's own files), and the `scan` command, which lists project files changed outside the
`.harness/` folder.

## The hooks fail open

If the hook itself breaks, the tool call or the stop goes ahead as if the hook were not there, and one line
is written to `~/.harness/hook-errors.log`. This is deliberate: a broken harness should not freeze every
session on the computer. It also means a rule can silently stop being enforced. If you rely on a rule,
check that log now and then, and run the ledger command's `check-install`
(`python3 ~/.harness/bin/harness.py check-install`).

The hooks also run only between tool calls. A single command that runs for thirty minutes is not
interrupted.

## What installing changes

**`install.py`** (with no options):

- Deletes and recopies `~/.harness/bin/` (the kit).
- Copies six skill folders into `~/.claude/skills/`, each with a `.harness-kit` marker file. Skips any
  folder of the same name that it did not install.
- Changes no Claude Code settings and no git repository.
- `--git-exclude` additionally appends the six skill folder names to `~/.claude/skills/.git/info/exclude`,
  if that folder is a git repository. Off by default. `--uninstall` takes those lines out again.
- `--hooks` additionally installs the hooks in your user settings (see below).

**Installing the hooks** (`hooks_install.py --add`, which the triage and surgery skills run only with your
yes):

- With `--project <folder>`: writes five hook entries to that folder's `.claude/settings.local.json`. If
  the folder is a git repository, adds `.claude/settings.local.json` to its `.git/info/exclude`, because the
  file holds paths for this computer only.
- Without `--project`: writes the same five entries to your user settings (`~/.claude/settings.json`), so
  the hook runs on every tool call of every session on this computer. For sessions not in a project it exits
  at once.
- Either way: backs the settings file up first (as `settings...json.harness-backup-<date>`), leaves your
  other hooks exactly as they were, and is safe to run twice. `--remove` takes them out again.

**Setting up a project** creates `.harness/` in the project folder and records the project's name and path
in `~/.harness/`. It never moves, renames or deletes the project's own files.

## Keep secrets out

Do not put passwords, API keys or tokens in the rules file, the ledger or task notes. Snapshots copy the
ledger, handoffs carry it to another computer, and a save command copies whatever it is told to.

## Reporting a security problem

Please do not post details of a security problem in a public issue. See [SECURITY.md](../SECURITY.md)
for how to report it privately.
