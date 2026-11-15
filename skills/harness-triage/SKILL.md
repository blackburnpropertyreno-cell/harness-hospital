---
name: harness-triage
description: Assess a project that is starting and may need several Claude sessions or agents working over hours or days, decide how much working environment (a "harness") it needs - none, lite or full - and set it up: a shared ledger, hooks, a coordinator, workers, a reviewer, and a handoff routine between computers. Use this whenever the user wants to start or organise a new multi-session, multi-agent or multi-day project, asks for a coordinator and workers, asks "does this need a harness", wants to add a second computer to an existing harness project, or says "harness triage" or "harness setup". Also use it to decide that a job does NOT need a harness. For a project that already has an arrangement which is wrong, use harness-surgery instead.
argument-hint: "[project name or folder]"
---

# Harness triage

A harness is everything around the model: what each session sees, what it can touch, where results get
written down, and who checks them. The model does the thinking. This skill sets up the rest for one project,
sized to that project, and tells the owner when the right size is "none".

`H` below stands for the ledger command on this computer. It is shorthand for this document, not a shell
variable: type the full command each time.

    {{HARNESS}}

## What is fixed and what is yours to judge

**Fixed, and shipped as code.** The ledger and its command, the hooks, the status views and the handoff
routine. They are the parts that failed when they were improvised, so do not redesign them per project.
Run them; do not rewrite them.

**Yours to judge.** Whether the project needs a harness at all, which tier, which roles, how results get
checked, what the known-answer cases are, which rules deserve enforcement, and what a worker needs to be
told. These differ for every project, and this is where your judgement matters. Nothing below is a script to
follow line by line.

You may depart from any default here when the project calls for it. When you do, tell the owner what you
changed and why, in one or two sentences.

## The six principles

Every decision you make should trace back to one of these. The one-line versions below are enough to start.
Read `references/principles.md` when a decision is not obvious, or when the work is subjective.

- **C - Context is all it knows.** A session knows only what it is given. Give it the right information and a few sharp tools.
- **L - Ledger, not memory.** Project state lives in one place outside any session, is changed through one command, and every view is generated from it.
- **A - The author never grades its own work.** Scripts check facts. An independent reviewer, told to find faults, checks judgements.
- **M - Measure before believing.** Test the setup on cases with known answers, change one thing at a time, and count the failures you can see.
- **P - Put the rules in code.** A rule that matters is enforced by a hook or a permission, because a rule in a prompt will eventually be broken.
- **S - Small wins.** Add a part only when something shows it is needed. More thinking effort usually beats more agents.

## How to run a setup

1. **Scope it.** Read what the conversation and the project folder already tell you, then ask only for what
   is missing. Four questions decide the tier: Does the work need more than one session at once? Will it
   outlive one session's context? Can the owner tell a good result from a bad one by looking? How costly is
   an unnoticed mistake? Answer them from what the work needs. If the owner has asked for a particular
   structure ("a coordinator and two workers"), treat that as a proposal to weigh, not as the answer.
   Choose None, Lite or Full using `references/tiers.md`, and tell the owner which and why. If the answer
   is None, say so, suggest what to do instead, and end the setup there. You can then offer to do the job
   itself in this session.

2. **Look at what exists.** The project folder may already hold data, checker scripts or source rules.
   Keep what works. The harness lives in a `.harness/` folder beside the project's own files and does not
   move or rewrite them. If the project is already running several sessions under an arrangement of its
   own (status files edited by hand, a chat acting as coordinator), this is the wrong skill: tell the owner
   that changing an existing arrangement is what `/harness-surgery` is for, and stop.

3. **Create it.** `H init <name> --path <project folder> --tier lite` or `--tier full`. Lite creates one
   state file and a checker stub. Full creates the ledger, rules file, role files and views. Write the
   project's goal, in a sentence or two, into the `goal` field of the rules file: the coordinator needs it
   to say no to side work, and a later review needs it to see whether the project has drifted.

4. **Decide the checking, then the measuring, then the context,** in that order, because each depends on
   the one before. `references/checking.md` covers splitting facts from judgements, what a reviewer is told,
   building three to five known-answer cases, and how all of it changes when the work is subjective.

5. **Put the rules that matter into the rules file** (`.harness/config.json`): data that must not be
   overwritten, sites that must not be fetched, shell commands that must not run. `references/ledger.md`
   lists every field. Checker and promotion scripts you write go in `.harness/tools/`, which workers
   cannot change.

6. **Install the hooks, with the owner's yes.** By default they go into the project's own local settings and
   apply to sessions started inside the project folder. The alternative is the user's settings, where they
   run for every session on the computer and let a session join from any folder. Explain the choice first,
   then follow `references/hooks.md`, which also says plainly what the hooks cannot catch. Whether they
   really fire can only be seen from a new session, so that check goes in the handover.

7. **Shape the roles.** Edit the role files in `.harness/roles/` for this project, add a specialist only if
   the work has a real one, and choose a model and effort level per role. See `references/roles.md`.

8. **Plan saving and handoff** if the project runs for days or moves between computers:
   `references/handoff.md`. Confirm the durable copy really exists (for example, that the folder is a git
   repository with a remote), agree with the owner what may travel to it, and run the save command once.

9. **Prove it before handing over.** Queue one small real task and take it through the whole path: taken,
   done, checked, verified. You cannot play every part yourself, because the ledger will not let an author
   verify its own task, and you wrote the known-answer cases so you already know their answers. Use fresh
   subagents: one told to join as a worker and do the task, one told to join as a reviewer, and one per
   case, on the model that will do the real work. Subagents share your session, so have each set the
   environment variable `HARNESS_SESSION_ID` to its own made-up value on every ledger command. If you
   cannot start subagents, give these runs to the owner as the first lines of the handover. Record each case
   with `H case record <name> pass` or `fail`, with the model and effort in `--note`. Run `H check-install`.
   Then clear the trial from the ledger with `H --project <name> reset --yes`. A setup that has not
   completed one task end to end is not finished; if part of it could not be proven, say which part.

10. **Hand over.** Give the owner the exact lines to type, where the dashboard is, how to answer a decision,
    and when to run `/harness-doctor`. Lead with anything they must do before work starts, and anything you
    could not prove. Put questions only they can answer into their decision queue with
    `H --project <name> ask "<question>"`, so they are not lost in this conversation. Then end this session:
    the coordinator should be a fresh session, because the design depends on a new session being able to run
    the project from the ledger alone.

## Constraints, and why

- **Ask before installing hooks, and prefer the project's settings to the user's.** User-wide hooks touch every session on the computer; that is the owner's decision.
- **Do not move, rename or delete the project's existing files.** A setup that damages the project has failed before it started.
- **Flag a project folder that sits inside iCloud, Dropbox or OneDrive.** Sync services corrupt databases that are being written to and create conflicting copies. Recommend moving it; do not move it yourself.
- **Keep secrets out of the rules file and the ledger,** and agree what else may travel. Snapshots and handoffs copy the ledger; a save command copies whatever it is told to, which can include task folders full of downloads or licensed material.
- **When torn between two tiers, start with the lower one.** Adding a part later is easy; an oversized harness costs effort on every task.
- **Keep setup under about a tenth of the project's expected length.** If it is taking longer, the tier is too high.

## Three examples, to show the range

These are illustrations, not templates. Most projects will match none of them exactly.

**A two-hour job.** "Summarise these twelve PDFs into one briefing." One session, the owner can judge the
result by reading it. Tier: None. Say so, suggest raising the thinking effort and listing the PDFs in the
prompt, and stop. Setting up a ledger here would cost more than the job.

**A two-day job, one or two sessions.** "Migrate forty report templates to the new format." The work
outlives one context window, and a script can check each output. Tier: Lite. One state file listing the
forty templates, a checker that validates a converted template, three templates converted by hand as
known-answer cases. No coordinator, no hooks.

**A two-week research project, six sessions, unfamiliar subject.** The owner cannot judge the findings
unaided, sessions run in parallel, and work moves between two computers. Tier: Full. Ledger, hooks,
coordinator on a timer, one reviewer, facts checked by script and conclusions by the reviewer, five
known-answer cases, and the handoff routine. Whether the one scarce resource gets its own specialist session
or is simply routed to one named worker is a judgement about cost: a specialist is a whole session.
