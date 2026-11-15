# The hooks

A hook is a script that Claude Code runs by itself at fixed moments: when a session starts, before and after
every tool call, and when a session tries to end its turn. The session does not choose whether it runs. That
is what makes it suitable for rules: a message can be missed, a hook cannot.

## Installing them

There are two places they can go. Explain the choice to the owner and get a yes before installing either.

| | For this project only (the default) | For every session on the computer |
|---|---|---|
| Command | `{{HOOKS}} --add --project <project folder>` | `{{HOOKS}} --add` |
| Written to | the project's `.claude/settings.local.json` | the user's Claude Code settings |
| Sessions started in the project folder | hooks apply | hooks apply |
| Sessions that join from another folder | in the ledger, but no rules apply to them | hooks apply |
| The owner's other sessions | untouched | the hook runs on each tool call and exits at once |

Choose project-only unless the owner wants sessions to join from folders outside the project, for example
one that reads across several projects. Project-only means every working session must be started in the
project folder; say that in the handover. A session that joins from elsewhere is told that the rules do not
apply to it.

Either command backs up the settings file if it exists, adds five hook groups, and leaves every other hook
untouched. It is safe to run twice. `--check` reports whether they are present and `--remove` takes them
out, each with the same `--project` option. Sessions already open pick the hooks up only after they are
restarted.

The project's local settings file holds paths for this computer only, so it is kept out of git and each
computer installs its own.

`H check-install` confirms they are in the settings file. Whether they really fire can only be seen from a
new session, so put this in the handover for the owner: open a new session in the project folder and run
`H board`. The new session should be listed. If it is not, the hooks are not running; check
`~/.harness/hook-errors.log`.

Each computer needs its own install, and with project-only hooks each project does too.

## What each one does

| Moment | What the hook does |
|---|---|
| Session starts | In a registered project folder: registers the session and tells it its name and ledger command. After a resume or a compaction: reminds it who it is and which task it holds |
| Before a tool call | Records activity. Refuses a file write outside the session's allowed places, a shell command that matches a rule, a fetch from a blocked site, a worker reading the known-answer cases, or a message to another session |
| After a tool call | Records activity, copies the ledger every few minutes, refreshes the views, and delivers a handoff notice to a busy session |
| Session tries to stop | Refuses once if its task is unfinished and unrecorded; hands it the next queued task if there is one; otherwise lets it stop and records why |
| Session closes | Records it, so the board shows a session that closed while holding a task |

**The stop rule never loops.** If a session is refused and tries to stop again without doing anything, it is
let go and that is recorded. This guard is the hook's own and does not depend on other stop hooks the user
has.

**The coordinator's stop** is refused once while the board shows a session with nothing to do, an undecided
follow-up, or a result with no reviewer.

## What a session started in the project folder becomes

By default it is registered as a worker, so the write rules apply from its first tool call. It is handed
tasks only after it takes its first one, so a session opened to ask a question is never given work. The owner
can run `H join <project> --role guest` in a session meant for something else (maintenance, the doctor) to
lift the worker limits; a guest still cannot overwrite protected data or the ledger. Set `auto_join` to
`guest` or `off` in the rules file to change the default.

A session started anywhere else joins when the owner types `/worker <project>`, `/coordinator <project>` or
`/reviewer <project>`. The rules reach such a session only when the hooks are installed for every session
on the computer.

## How the path and site rules match

- A protected path matches as a whole name, so protecting `sources/**` does not affect a file called
  `water-resources.pdf`. Reading a protected file is always allowed, and copying one out into a task folder
  counts as reading.
- A blocked site stops fetching: a tool given that address, or a shell command that both names the site and
  looks like a download. Naming the site in a search, a note or a question to the owner is allowed.

## What the hooks cannot do

Be honest with the owner about these.

- **Shell commands are checked by pattern only.** A file tool names the file it will write, so those writes
  are checked exactly. A shell command can write anywhere, including from inside a script, and the hook sees
  only the command text. It catches the obvious cases (redirecting into a protected file, deleting it, opening
  a protected database for writing). It will not catch a script that writes somewhere it should not. The
  backstops are the ledger copies, the promotion step, and `H scan`, which lists project files changed
  outside the `.harness/` folder.
- **They are guard rails, not security.** They keep a well-meaning session inside the lines. They are not
  designed to stop a session that is deliberately trying to get around them.
- **They run between tool calls.** A single command that runs for thirty minutes delays everything the hook
  would have told that session. Have long jobs run in the background or write progress to disk as they go.
- **They fail open.** If the hook itself breaks, the tool call goes ahead and the error is logged. A broken
  harness should not freeze every session on the computer.
- **A session that never joined is outside all of this,** and so is one that joined from another folder
  while the hooks are project-only. Starting workers inside the project folder is what makes joining
  automatic and the rules certain.

## Choosing what to enforce

Enforce a rule in the rules file when breaking it is costly or hard to undo: overwriting source data,
fetching from a site that forbids it, pushing or publishing, deleting. Leave matters of style and method in
the role files. A rule that fires constantly is either wrong or badly explained, and the doctor skill looks
for exactly that.
