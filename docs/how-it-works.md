# How it works

This page explains the four moving parts of a full set-up: the ledger, the hooks, the roles, and the
handoff between computers. A lite set-up uses none of them: just one shared state file and a checking
script.

Everything the kit adds to a project lives in one folder, `.harness/`, beside the project's own files.

## The ledger

The **ledger** is the project's single record of what is going on: every task, every session, every
question waiting for you, and a history of everything that happened. It is one small database file,
`.harness/ledger.sqlite`.

Sessions never open that file directly. They change it only through one command, the **ledger command**
(`kit/harness.py`, installed at `~/.harness/bin/harness.py`). In the skills and on this page it is
abbreviated as `H`. Because there is only one way in, the rules live in one place:

- A task cannot be marked **done** without a result on disk.
- The session that did a task cannot mark it **verified**. A script or another session has to.
- Entries stay short. Longer text goes in a file, and the ledger holds the path.

A task moves through these states: proposed, queued, in progress, blocked, waiting for the owner, done,
verified. It can also be rejected or cancelled.

Work happens in three zones:

| Zone | Holds | Who writes it |
|---|---|---|
| The ledger | state, one-line summaries, file paths | any session, through the ledger command |
| A task folder, `.harness/work/<task>/` | notes, drafts, downloads, the result | the session doing that task |
| The project's own files | only results that have been verified | the promotion step |

Two folders belong to you and cannot be changed by workers: `.harness/tools/` (checking and promotion
scripts) and `.harness/cases/` (the known-answer cases, which workers cannot read either).

Status pages are generated from the ledger, never edited by hand: `.harness/STATUS.md` and
`.harness/dashboard.html`. The command `H board` prints where everything stands and what needs action.

The rules for a project live in `.harness/config.json`: which roles may write where, which files are
protected, which sites are blocked, which shell commands are refused, how each kind of task is checked, and
the save commands. **Some of those settings are shell commands that the kit runs.** See
[security](security.md).

## The hooks

A **hook** is a script that Claude Code runs by itself at fixed moments. The session does not choose
whether it runs. That is what makes hooks the right place for rules: a message in a prompt can be missed, a
hook cannot.

One script, `kit/hook.py`, handles every moment:

| Moment | What it does |
|---|---|
| A session starts | In a registered project folder, registers the session (as a worker by default) and tells it its name and the ledger command. After a resume or compaction, reminds it who it is and which task it holds. |
| Before each tool call | Refuses a file write outside the session's allowed places, a shell command matching a refused pattern, a fetch from a blocked site, a worker reading the known-answer cases, or a message from a worker or reviewer to another session. |
| After each tool call | Records activity, copies the ledger every few minutes (and runs the autosave command if one is set), refreshes the status pages, and passes on a handoff notice. |
| A session tries to stop | Refuses once if its task is unfinished and unrecorded; hands it the next queued task if there is one; otherwise lets it stop and records why. It never refuses twice in a row, so it cannot trap a session in a loop. |
| A session closes | Records it, so the board shows a session that closed while holding a task. |

For a session that is not part of a project, the hook exits at once and does nothing.

**Where they are installed.** By default, in one project's `.claude/settings.local.json`, so they apply
only to sessions started in that project's folder. The alternative is your user settings, where they run
for every session on the computer, and a session started in another folder can join a project. The
installer for the hooks is `kit/hooks_install.py`:

```
hooks_install.py --add --project <project folder>     add them for one project
hooks_install.py --check --project <project folder>   are they there?
hooks_install.py --remove --project <project folder>  take them out
```

Leave out `--project` to act on your user settings instead. Each computer installs its own hooks.

What the hooks cannot do is set out in [security](security.md).

## The roles

A **role** is a short instruction file in `.harness/roles/` plus limits in the rules file. A session gets
its role when it joins a project.

- **Coordinator.** Keeps sessions moving and reports to you. Reads the board, assigns work, decides on
  proposed follow-ups, puts stuck tasks back in the queue, promotes verified results into the project's
  files, and passes your decisions into the ledger. It does no worker's tasks and judges no results. It keeps
  nothing in its own memory, so a fresh coordinator can take over at any time. It usually runs on a timer,
  for example `/loop 10m` in its session.
- **Worker.** Takes one task at a time, writes only in that task's folder, records the result, takes the
  next. It may propose follow-ups but does not decide to pursue them.
- **Reviewer.** Checks finished results it did not produce, looking for what is wrong. Passes or fails each
  with a note. Does not repair anything.
- **Specialist** (optional). A worker with different access or instructions, for work that needs a scarce
  resource such as a licensed database. Other sessions ask it for things through the ledger.
- **Guest.** A session opened for something else, such as a question or a doctor review. It has fewer
  limits, but still cannot overwrite protected data or the ledger.

To put a session in a project with a role, type `/coordinator <project>`, `/worker <project>` or
`/reviewer <project>` in it. A session started inside the project folder joins as a worker automatically
when the hooks are installed there.

Workers and reviewers cannot message other sessions; the coordinator may send only a short wake-up
("you have a new task"). The content of the work always goes through the ledger, so nothing depends on a
session still being open.

## Moving between computers (the handoff)

Only one computer works on a project at a time. Moving it is a planned routine that takes a few minutes.

**On the computer you are leaving:**

1. `H --project <name> drain`. No new tasks are handed out, and each busy session is told, after its next
   tool call, to save its files, record where it is, and stop.
2. Run `drain` again until it reports that every session has finished or recorded where it is.
3. `H --project <name> stamp`. This seals a copy of the ledger with the computer's name, the time and a
   checksum, runs the save command if one is set, and **parks** this computer: from then on its hooks and
   the ledger command refuse changes to the project.

**On the computer you are moving to:**

4. The first time only: `H register-path <name> <folder>` to say where the project lives there, and install
   the hooks there too.
5. `H --project <name> resume`. This runs the fetch command if one is set, checks the sealed ledger against
   its checksum, and puts any half-finished tasks back in the queue with their notes. If the copy is
   incomplete it refuses and changes nothing.
6. Start fresh sessions and have each one join.

How the project's files get from one computer to the other is up to you: usually a private git remote for
text and code. The save and fetch commands in the rules file (`handoff.push_cmd` and `handoff.pull_cmd`) can
do it for you. Keep the working folder out of iCloud Drive, Dropbox and OneDrive; they can corrupt a
database that is being written to.

While you work, the hooks copy the ledger into `.harness/snapshots/` every few minutes and keep the latest
copy in `.harness/handoff/`, so whatever saves the project carries a recent ledger even between handoffs.
