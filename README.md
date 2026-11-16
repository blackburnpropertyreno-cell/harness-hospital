# harness hospital

Skills and a small kit for running one project across several Claude Code sessions, over hours or days,
without losing track of what has been done, who did it, and whether anyone checked it.

> **Status: early.** Read [Honest status](#honest-status) before relying on it.

## The problem

One Claude Code session is good at one job. A bigger project, say a two-week research task or a migration
of hundreds of files, soon needs more than one session. Then things go wrong in familiar ways:

- Each session forgets what the others did, and what it did itself before its memory was compacted.
- Progress is written in several notes files, and they disagree.
- A session marks its own work as finished and correct, and nobody checks.
- Rules written in a prompt ("don't touch the source data") are broken sooner or later.
- Moving the work to another computer loses state.

The word for everything around the model that prevents this is a **harness**: what each session sees, what
it is allowed to touch, where results are written down, and who checks them. The model does the thinking.
The harness decides the rest.

## Who it is for

People who use Claude Code and have a project that is too big or too long for one session. You do not need
to be a programmer to use the skills: they ask you questions in plain language and tell you what to type.
You do need to be comfortable installing a Python script and running a few commands in a terminal.

It is not for a job one session can finish in an afternoon. The first skill will tell you so.

## The four skills

Think of a hospital. You arrive, someone decides how much care you need, you get a check-up later, and if
something is badly wrong you go into surgery. And when nobody can tell what is wrong, they take a picture
first.

| Skill | Reach for it when | What it does |
|---|---|---|
| **`/harness-xray`** | The project is a **mess spread over several folders** and you cannot see it whole | Looks at every folder you name and changes nothing. Says what each one is, which copies have drifted apart, whether it is one project or several, where it should live, and which of the other three to run next. |
| **`/harness-triage`** | A project is **starting** | Asks about the work and decides how much harness it needs: **none**, **lite** (one shared state file and a checking script) or **full** (a shared record, hooks, a coordinator, workers and a reviewer). Then sets that up and proves it on one small task. |
| **`/harness-doctor`** | A project is **running** and you want a check-up, or a few tweaks | An independent review in a fresh session. Changes nothing. Writes a report that says what is working, what is not, and groups the recommended changes by how safely they can be applied. |
| **`/harness-surgery`** | The current arrangement is **wrong** and needs reconfiguring | Works on a hand-built arrangement (notes files edited by hand, a chat acting as coordinator) or a kit set-up that no longer fits. Diagnoses, writes a plan, waits for your yes, takes an undo point, rebuilds, brings the open work across, retires the old arrangement and writes a record. |

There are also three short commands that put a session into a project with a role:
**`/coordinator`**, **`/worker`** and **`/reviewer`**.

Each skill has its own page: [x-ray](docs/xray.md), [triage](docs/triage.md), [doctor](docs/doctor.md),
[surgery](docs/surgery.md). How the parts fit together is in [how it works](docs/how-it-works.md).

## The six principles

Every part of the kit traces back to one of these.

| | Principle | In practice |
|---|---|---|
| C | **Context is all it knows** | A session knows only what it is given. Each task says what is wanted, what is known, and what done looks like. |
| L | **Ledger, not memory** | The project's state lives in one record (the *ledger*) outside any session, changed through one command. Every status page is generated from it. |
| A | **The author never grades its own work** | Scripts check facts. A separate reviewer session checks judgements. |
| M | **Measure before believing** | Test the set-up on a few cases whose answers you already know. Change one thing at a time. Count the failures you can see. |
| P | **Put the rules in code** | Rules that matter are enforced by *hooks* (scripts Claude Code runs by itself), not just written in a prompt. |
| S | **Small wins** | Add a part only when something shows it is needed. |

## Before you install: one security warning

A project set up with this kit has a rules file, `.harness/config.json`. That file can hold **shell commands
that the kit runs on your computer**: a checking script, a promotion command, save and fetch commands for
moving between computers, and an autosave command that the hooks run every few minutes.

So treat a project folder you did not set up yourself the way you would treat a script from a stranger.
**Read its `.harness/config.json` before you run the ledger command in it, register it on your computer, or
install the hooks for it.** More in [security](docs/security.md). To report a security problem, see [SECURITY.md](SECURITY.md).

## Install

You need **Python 3.8 or newer** and **Claude Code**. Nothing else: the kit uses only Python's standard
library.

**macOS or Linux** (in Terminal):

```bash
git clone https://github.com/ethan-blackburn/harness-hospital.git ~/harness-hospital
python3 ~/harness-hospital/install.py
```

**Windows** (in PowerShell):

```powershell
git clone https://github.com/ethan-blackburn/harness-hospital.git $env:USERPROFILE\harness-hospital
py $env:USERPROFILE\harness-hospital\install.py
```

You can put the folder anywhere you like. To update later: `git pull` in that folder, then run `install.py` again. Edit files in this folder,
not the installed copies; the installed copies are overwritten on each install.

Other installer options:

```
python3 install.py --status        show what is installed
python3 install.py --uninstall     remove the kit, the skills, hooks in your user settings, and any lines
                                   --git-exclude added; projects (and hooks added to a project's own
                                   settings) are left alone
python3 install.py --hooks         also add the hooks for EVERY session on this computer (see below)
python3 install.py --git-exclude   if your skills folder is a git repository, tell git to ignore the
                                   installed skills (writes to that repository's .git/info/exclude)
python3 install.py --claude-dir DIR --harness-home DIR
                                   install somewhere other than ~/.claude and ~/.harness (used by the tests)
```

### What installing changes on your computer

- **Copies the kit** to `~/.harness/bin/`. If that folder already exists it is deleted and copied fresh.
- **Copies seven skills** to `~/.claude/skills/`: `harness-xray`, `harness-triage`, `harness-doctor`,
  `harness-surgery`, `coordinator`, `worker` and `reviewer`. Each gets a small marker file, `.harness-kit`, so the installer
  knows it put it there. Paths and commands for your computer are filled into the skill files as they are
  copied.
- **Skips any skill folder it did not install.** If you already have a skill called `worker`, it is left
  alone and the installer tells you.
- Honours the `CLAUDE_CONFIG_DIR` and `HARNESS_HOME` environment variables if you have set them.

### What installing does not change

- **No Claude Code settings.** The hooks are not installed by default. The triage skill asks you before it
  adds them, and by default adds them to one project only.
- **No git repository,** unless you pass `--git-exclude`.
- **No project.** Nothing is set up until you run `/harness-triage`.
- Nothing is sent anywhere. The kit makes no network connections of its own. (Commands you or someone
  else put in a project's rules file can, which is why the warning above matters.)

### The hooks

A *hook* is a script Claude Code runs by itself at fixed moments: when a session starts, before and after
every tool call, and when a session tries to stop. The session does not choose whether it runs, which is
what makes hooks suitable for rules.

This kit's hook registers sessions in the project, refuses file writes outside a session's allowed places,
refuses fetches from blocked sites, stops a session from ending its turn with its task unfinished and
unrecorded, and keeps the ledger copied and the status pages fresh.

**By default the hooks go into one project's own settings,** the file `.claude/settings.local.json` inside
that project's folder, so they apply only to sessions started in that folder. Your other sessions are not
affected. The other choice, `install.py --hooks`, puts them in your user settings so they run for every
session on the computer; for any session not in a project they exit at once and do nothing. Either way the
settings file is backed up first and your other hooks are left exactly as they were. When the hooks go
into a project that is a git repository, `.claude/settings.local.json` is also added to that repository's
`.git/info/exclude`, because it holds paths for this computer only.

## A first use

0. If the project's files are spread over several folders, start with `/harness-xray` and name the
   folders. It tells you where the project should live and what to run next.
1. Open a new Claude Code session and type `/harness-triage`. Describe the project: what it is for, how
   long you expect it to take, whether you can judge the results yourself.
2. Answer its questions. It will say which tier the project needs, and why. If the answer is **none**, it
   says so and can simply do the job with you.
3. For lite or full, it creates a `.harness/` folder beside your project's own files (it never moves or
   rewrites your files), writes the rules, asks before installing the hooks, and proves the set-up on one
   small task.
4. It ends with a handover: the exact lines to type next. For a full set-up that usually means opening a
   fresh session and typing `/coordinator <project>`, then opening worker sessions in the project folder.
5. Watch progress in `.harness/dashboard.html`. When the coordinator needs a decision from you, it asks.
6. Part-way through, open a fresh session and type `/harness-doctor <project>` for a check-up.

## Limits

- **The hooks are guard rails, not a security boundary.** They keep a well-meaning session inside the
  lines. They are not built to stop one that is trying to get around them.
- **Shell commands are checked by pattern only.** File writes made with Claude Code's file tools are checked
  exactly. A shell command can write anywhere, including from inside a script; the hook sees only the
  command text. Ledger copies, the promotion step and the `scan` command (which lists project files changed
  outside `.harness/`) are the backstops.
- **The hooks fail open.** If the hook itself breaks, the tool call goes ahead and the error is written to
  `~/.harness/hook-errors.log`.
- **One computer at a time.** A project can move between computers with a planned handoff, but two computers
  cannot work on the same project at once.
- **Keep projects out of iCloud Drive, Dropbox and OneDrive.** Sync services can corrupt a database that is
  being written to.

## If something goes wrong

- **The hooks do not seem to run.** Sessions that were already open pick up the hooks only after a restart,
  so open a new session in the project folder. Then run the ledger command's `check-install`
  (`python3 ~/.harness/bin/harness.py check-install`) and read `~/.harness/hook-errors.log`. The hooks fail
  open, so a broken hook shows up there rather than as an error in your session.
- **The installer says it skipped a skill.** A folder of that name already exists in your skills folder and
  was not installed by this kit. Rename or remove yours, then run `install.py` again.
- **A session says the project is parked.** The project was handed off to another computer with `stamp`.
  Nothing may change here until you take it back with `resume` (see [how it works](docs/how-it-works.md)).

## Honest status

- **Early.** Version 0.2.0.
- Trialled by Claude agents on throwaway test projects, and by the scripted tests in `tests/`.
- Three live runs on macOS confirmed that the hooks fire in real Claude Code sessions.
- **Used once on a real project:** `/harness-surgery` reconfigured an existing project, and that run
  finished. No sessions have worked under the new set-up yet, so whether it helps is not yet known.
- **`/harness-xray` is new in 0.2.0.** A Claude agent trialled it once on a made-up mess of thirteen
  folders; its findings were then applied, and the corrected version has not been trialled again. It has
  not been used on a real mess. The step that follows it, gathering the folders into one home during
  triage or surgery, has not been trialled at all. Reports from real messes are the most useful thing you
  can send.
- **Never run on Windows.** It is written to be portable (standard library only, no shell-specific
  commands), but check `install.py --status` and your first session carefully before relying on it there.
- Tested with **Claude Code 2.1.325** on macOS. Hooks depend on Claude Code's hook format, which may change.

Reports of what works and what breaks are very welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

## What is where

```
install.py              copies the kit and skills into place
kit/harness.py          the ledger command: the only way to change a project's ledger
kit/hook.py             one script for every Claude Code hook event; does nothing outside a project
kit/hooks_install.py    adds or removes the hooks in a settings file (one project's, or the user's)
kit/templates/          role prompts and lite-tier files copied into a new project
skills/                 the seven skills
docs/                   one page per skill, how it works, and security
tests/                  scripted tests
```

Inside a project, everything the kit adds lives in one folder, `.harness/`: the ledger, the rules file,
role prompts, task folders, status pages, snapshots, and the sealed copy used for a handoff.

## Running the tests

From this folder:

```bash
python3 tests/test_ledger.py
python3 tests/test_hooks.py
python3 tests/test_docs.py
```

They use temporary folders and never touch real projects or settings. On Windows use `py` in place of
`python3`.

## Licence

MIT. See [LICENSE](LICENSE).
