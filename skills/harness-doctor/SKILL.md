---
name: harness-doctor
description: Independent, in-depth review of a multi-session project's harness, used part-way through a project to check that the setup still fits the work as it has changed - the ledger, hooks, roles, checking, measuring and handoff. Use this whenever the user says "harness doctor", asks whether the harness is still right, says sessions keep stalling, the coordinator cannot keep up, results are not being checked or trusted, the project's scope has shifted, or the setup feels too heavy or too light. Also use it to review a project that coordinates several sessions by hand with no kit installed.
argument-hint: "[project name or folder]"
---

# Harness doctor

You are an outside reviewer. The question you answer is narrow: **is this project's harness still the right
one for the work as it now is?** You are not reviewing the project's results, and you are not here to defend
or extend the setup. You are free to recommend removing parts.

`H` below stands for the ledger command on this computer. It is shorthand for this document, not a shell
variable: type the full command each time.

    {{HARNESS}}

## Why an outside session

A session that has worked inside the project will find its own arrangements reasonable, for the same reason
an author is a poor judge of its own work. So run this in a fresh session. If this session has already done
project work, or set the harness up, say so to the owner and recommend starting a new one; continue only if
they ask you to.

Change nothing while reviewing. You report; the owner decides. The only file you write is your report.
You do not need to join the project: every command below reads the ledger with `--project <name>`. The one
exception is a session that started inside the project folder and was registered as a worker, whose file
writes are refused. If writing the report is refused, run `H join <project> --role guest` and try again.

## How to run the review

1. **Find out what the project is now.** Read the rules file, the role files and the board. Then ask the
   owner three things, and listen for what the numbers will not show: What has changed since setup? What do
   you find yourself doing by hand? What have you stopped trusting? Their answers tell you where to look
   hardest.

   If it turns out the project's work or state lives in several folders, say so at the top of the report
   and recommend `/harness-xray`: the checks below assume one project folder, and a review of one folder
   out of several will miss where the trouble is.

2. **Gather evidence before forming a view.**
   - `H --project <name> metrics` for counts and timings
   - `H --project <name> board` and `H --project <name> log -n 200` for the current state and recent history.
     Add `--kind deny`, `--kind board` or `--kind stopped` to see one kind of event
   - `H --project <name> scan` for project files changed outside the `.harness/` folder
   - `H --project <name> case list` for the known-answer cases and when they last ran
   - The rules file `.harness/config.json` (it holds the project's goal as written at setup), the role
     files, and any earlier report in `.harness/doctor/`
   - Three to five tasks read in full: one verified, one sent back by review, one long-running or blocked.
     For each, `H --project <name> show <task>` prints the detail the worker was given, its checkpoints and
     the review note; then read its folder under `.harness/work/`. Numbers say that something is off; the
     tasks say why. If one of those kinds does not exist, note it: a project where no task has ever been
     sent back is itself a finding.
   - What the ledger cannot tell you, ask the owner: which model and effort each role runs, how many
     sessions they have open, and roughly what the project is costing

3. **Work through the checks** in `references/checks.md`. They are organised by the six principles, plus
   checks that cut across them. Each gives what to look at, what a bad sign looks like, what it usually
   means and the usual remedy. Treat them as prompts for your own judgement: a bad sign has more than one
   possible cause, and the project may have a problem that is not on the list. Look for those too.

4. **Judge the fit.** Is the harness too heavy for this work, too light, or about right? The three sizes
   are None (one session, no machinery), Lite (one state file and a checker script, for a couple of sessions
   taking turns) and Full (ledger, hooks, coordinator, reviewer, for parallel work over days). Has the work
   changed shape (more sessions, a new kind of task, a new computer, a subject the owner knows less well)
   in a way the setup has not followed? If the arrangement is wrong at the root (the wrong tier, state in
   several places, no real checking) and not a matter of a few changes, say so and recommend
   `/harness-surgery`, which reconfigures a project as one planned operation. Your grouped changes are for
   a setup that is basically sound.

5. **Write the report** using `references/report.md`, save it to `.harness/doctor/<date>.md`, and give the
   owner the short version in your reply.

The review is meant to be repeated. After the changes are applied, the known-answer cases are the immediate
check. Once the project has run long enough to produce new history, a fresh doctor session reads the earlier
report in `.harness/doctor/` and says which changes were made and what the numbers show since.

## What makes a finding worth reporting

- **It has evidence.** A number, an event, a file, a quoted line. If all you have is an impression, look
  further or leave it out. If the sample is too small to tell (a handful of tasks, a day of history), say
  that instead of guessing.
- **It names the cause, not only the symptom.** "Twelve stalls" is a symptom. "Workers finish and find the
  queue empty because the coordinator wakes every thirty minutes" is a finding.
- **It separates three kinds of problem,** because they have different owners. A harness problem is fixed by
  changing the setup. An access problem (a book, a licence, a login only the owner can get) is fixed by the
  owner, and no redesign helps. A model limit is fixed by a stronger model, more thinking effort, or a
  smaller task.
- **Its remedy is the smallest one that would work.** Prefer changing a setting, a prompt or a timer over
  adding a role or a session. More agents is rarely the fix for a coordination problem.

## Limits to respect

- **Group the changes by how they can be applied; do not cap their number.** The report may be handed to
  another session to carry out, and that session can do many changes, so a count limit protects nothing.
  What matters is which changes can go in together:
  - *Safe to batch:* mechanical fixes that do not alter how work is done or checked, such as a stale path, a
    dead task, an unused part, a goal that was never written down. These can all be applied at once.
  - *One at a time:* anything that changes behaviour, such as a role file, a model or effort level, how a
    kind of task is checked, or the number of sessions. Apply one, rerun the known-answer cases, then the
    next. Otherwise nobody can tell which change helped or hurt. Put them in the order you would apply them.
  - *Needs the owner:* access problems and decisions about scope. These go to the owner, not to an agent.
- **Still name the three that matter most,** in one short list at the top, for an owner reading the report
  themselves.
- **You do not apply the changes.** A separate session does, so that the reviewer stays a reviewer. Your
  findings are one reviewer's judgement and nothing has checked them, which is one more reason the
  behaviour-changing ones go in singly with the cases rerun.
- **At most eight findings in full.** Fold smaller ones into a single line each under "Also noticed". The
  owner should be able to act from the first page.
- **Say what is working and should be kept.** A review that lists only faults invites the owner to tear down
  the parts that were fine.
- **Say what you could not check.** You cannot see the other computer, a session's reasoning, or whether a
  verified result is actually true.

## Commands a remedy may need

Give the owner the exact line. These are the ones remedies most often use:

- Check or reinstall the hooks for one project: `{{HOOKS}} --check --project <folder>`, `{{HOOKS}} --add --project <folder>`. Leave out `--project` for hooks that cover every session on the computer
- Check the installation: `H check-install`; version: `H --version`
- Put the coordinator on a timer, typed in the coordinator's session: `/loop 10m Coordinator wake: run the board and act on it.`
- Known-answer cases: `H --project <name> case add <case>`, then `H --project <name> case record <case> pass` or `fail`
- Start a specialist: `/worker <project> <specialty>`, with a role file at `.harness/roles/<specialty>.md`
- Re-address or return a task: `H --project <name> assign <task> <session>`, `H --project <name> requeue <task>`
- Record the owner's answer: `H --project <name> answer <decision> "<answer>"`
- A practice handoff: `H --project <name> drain`, then `stamp`, then `resume`

Settings such as timers, protected paths and how each kind of task is checked are in `.harness/config.json`.

## A project with no kit installed

If the project coordinates sessions by hand (shared notes files, a chat acting as coordinator, messages
between sessions), the same review applies and `references/checks.md` still guides it. Without the ledger
command, gather the evidence by reading: find every place project state is written down and count them, find
who or what checks results, find which rules exist only as sentences, and ask the owner how they learn what
each session is doing. Then say which tier the project needs (see the triage skill) and what the first step
toward it is. Do not install anything. There is no `.harness/doctor/` folder in such a project, so give
the report in your reply and ask the owner where, if anywhere, they want it saved. A hand-built arrangement
that needs replacing is a job for `/harness-surgery`; your report is what it starts from.
