---
name: harness-surgery
description: Reconfigure a multi-session project whose existing harness is wrong - a hand-built arrangement (status files edited by hand, a chat session acting as coordinator, rules that live only in prompts, several places holding the project's state) or an installed harness kit that no longer fits the work. Diagnoses it, writes a plan for the owner to approve, takes an undo point, rebuilds the setup, brings the open work across, retires the old arrangement, proves the result and records what was done. Use this when the user says "harness surgery", or wants an existing setup fixed, rebuilt, overhauled, migrated or reconfigured rather than reviewed, or wants a doctor's report carried out in full. For a project that is just starting use harness-triage; for a review that changes nothing, or a setup that only needs tweaks, use harness-doctor; for a mess spread over many folders that nobody can see whole yet, run harness-xray first.
argument-hint: "[project name or folder]"
---

# Harness surgery

The owner has chosen this skill because they believe the project's current arrangement is wrong and want it
changed, not reviewed. Take that as the starting point. Your job is to find out exactly what is wrong, agree
a plan, and then carry out the whole reconfiguration while the project's work and data stay safe.

Four skills cover four situations, and the choice of skill is the owner telling you which one this is:

| Situation | Skill | Stance |
|---|---|---|
| The project is scattered and nobody can see it whole | harness-xray | Look; change nothing |
| A project that is starting | harness-triage | Build |
| A running project that may need adjusting | harness-doctor | Review; change nothing |
| An existing arrangement that is wrong | this one | Change it, with the owner's consent |

`H` below stands for the ledger command on this computer. It is shorthand for this document, not a shell
variable: type the full command each time.

    {{HARNESS}}

You will lean on the other two skills' reference files rather than repeat them:

- What to look for: `{{SKILLS}}/harness-doctor/references/checks.md`
- How to build each part: the files in `{{SKILLS}}/harness-triage/references/` (`principles.md`, `tiers.md`,
  `ledger.md`, `checking.md`, `hooks.md`, `roles.md`, `handoff.md`, `gathering.md`)

## Why this is riskier than a new setup

A new setup has nothing to lose. Here there is work in progress, data that took effort to gather, sessions
that may still be running, and an owner who has been burned by the current arrangement. The two ways this
goes wrong are losing work during the change, and leaving the old arrangement half in place, so that the new
ledger becomes one more place where state lives instead of the only one. Everything below exists to prevent
those two outcomes.

## How to run it

1. **Diagnose, far enough to plan.** If there is a recent doctor report (in `.harness/doctor/`, or one the
   owner gives you), start from it and check that it still holds. Otherwise gather the evidence yourself,
   using the doctor's checks as a guide. For a hand-built arrangement, establish four things by reading and
   by asking the owner:
   - every place the project's state is written down, and which one people actually trust
   - who or what checks results, and whether the author is grading its own work
   - which rules exist only as sentences in a prompt or a document
   - how the owner finds out what each session is doing, and what they end up doing by hand

   If the project is spread over several folders, establish the whole picture before planning: which
   folder is the home, what each other folder is, and which of any drifted copies is the master. Start
   from an x-ray report if there is one (`.harness/xray/` in the home, or one the owner gives you). With
   more than two or three folders and no report, recommend `/harness-xray` first, in its own session; it
   is read-only and its report is what you plan from. Surgery run from one folder, blind to the other
   twelve, rebuilds a corner of the project and leaves the mess standing. Two folders that each hold a
   harness are two ledgers for one project: one becomes the home, and the other's open work is brought
   across like a hand-built arrangement's.

   Also establish what works. A project that has been running has parts worth keeping: a checker script,
   careful source rules, specialist roles, a habit of logging disagreements. List them. Surgery that
   replaces a sound part with a default is a loss.

2. **Check that surgery is the right tool.** If the arrangement is basically sound and needs a handful of
   changes, say so and point the owner to `/harness-doctor`: a review with a few targeted changes is cheaper
   and keeps the ability to see which change helped. If the project turns out to need no harness at all,
   say that instead; removing one is a valid operation (see `references/operations.md`).

3. **Decide the target.** Which tier, which roles, how each kind of result is checked, which rules are
   enforced, where state lives. Use the triage skill's reference files. Decide the checking first, then the
   measuring, then the context, as a new setup would.

4. **Write the plan and get a yes.** Use the plan template in `references/record.md`. It says what is wrong
   and how you know, what will be kept, every change you intend to make, each existing project file you
   would edit, each new file outside `.harness/`, what the running sessions must do first, how to undo it,
   and how the result will be proven. Give it to the owner in your reply. **Change nothing until they
   agree.** They may strike items; the plan is theirs. Once work starts, save the plan in
   `.harness/surgery/`.

5. **Make it undoable.** What that takes depends on where you start:
   - *A project with the kit:* run `H init <name> --path <folder> --tier <its tier>` once more, which adds
     folders and template files a newer kit ships and overwrites nothing. Then
     `H --project <name> snapshot --setup` copies the rules file, role files, tools, cases and ledger and
     prints a name to restore from. That is the undo point.
   - *A hand-built project:* `H init` creates `.harness/` and touches no existing file. Then copy every
     existing project file you are going to edit into `.harness/surgery/before/`, keeping its path. Those
     copies, plus removing the hooks and unregistering, are the undo. Confirm with checksums that `init`
     changed nothing.

   Tell the owner how it is undone before going on.

6. **Stop the running sessions.** A change to roles or rules reaches a session only when it rejoins, so
   operating on live sessions leaves old and new instructions running side by side.
   - *With a kit:* `H --project <name> drain`, wait until it reports everyone has stopped or checkpointed,
     then `H --project <name> end-sessions --yes`. A session that is gone for good will never clear; once
     the owner confirms it is closed, go on, and say in the record that its unrecorded work is lost.
   - *Hand-built:* ask the owner to have each session write down where it is, in the project's existing
     notes, and stop. If the sessions are already closed, list what existed only in their conversations
     and is therefore already gone; the owner should hear that from the plan, not discover it later. If
     the owner can reopen a closed session, such as the old coordinator, it can be asked once, read-only,
     what it knew beyond its notes. Should the hooks register it when it reopens, have it run `leave`
     afterwards so it is handed no work.

7. **Operate.** Make all the planned changes, in this order, because each step protects the next:
   1. Protect the project's data in the rules file, or confirm it already is.
   2. Build or repair the structure: tier, rules, checking, known-answer cases, role files. Put rules that
      must hold into the rules file; role files that absorb every old rule end up twice the length they
      should be.
   3. Prove the rebuilt setup on a trial task and the cases, as the triage skill's proof step describes,
      with one difference: **never use `reset` here.** Label the trial so it stays apart from real work:
      add trial tasks with `--role trial --job trial`, and have the trial worker join with
      `--specialty trial`, so it takes only trial tasks and real workers never take them. When the proof is
      done, `H --project <name> trial-clear --yes` cancels the trial rows and closes the trial sessions,
      and recorded case results stay.
   4. Bring the work into the new arrangement. If folders are being gathered into the home, do that
      first, as `{{SKILLS}}/harness-triage/references/gathering.md` describes: copy in, check each copy,
      leave the originals. Hand-built: `references/bringing-work-across.md`. With a
      kit, the work is already in the ledger and stays there; repair it in place as
      `references/operations.md` describes.
   5. Retire the old arrangement, as agreed in the plan. This step is what makes it surgery. Hand-built:
      until the old status files are frozen and anything that copied state elsewhere is repointed or
      switched off, the project has gained a place for state, not lost several. With a kit: the old
      arrangement is the roles, rules and checks being replaced, and results that were marked verified
      without a real check.
   6. Install the hooks, with the owner's yes, as `hooks.md` in the triage skill describes. They come last
      because they would refuse your own edits to protected files. This means the proof ran without them:
      trial agents were told the rules, not held to them. Say so in the record. Whether the hooks fire can
      only be seen from a new session, so that check goes in the handover.
   7. For a kit project, take a second undo point now, so the delivered setup can be returned to.

   If you find something the plan did not expect (state in a place nobody mentioned, a session still
   running, a file that is not what it was thought to be), stop and tell the owner before continuing.

8. **Account for everything.** Every item that was open in the old arrangement is now a task in the ledger,
   or is listed in the record with the reason it was left out. Every old place for state is frozen,
   repointed, switched off, or deliberately kept and named. Show the mapping item by item, not only two
   totals: one old item can become two tasks, two can become one, and a "done" item that was never checked
   becomes a task too.

9. **Write the record and hand over.** Use the record template in `references/record.md`, saved to
   `.harness/surgery/<date>.md`: what was wrong, what changed, what was kept, what is unverified, how to
   undo it, and the exact lines to start working again. Then end this session. The coordinator starts fresh.

## The trade you are making

The doctor recommends changing behaviour one step at a time, rerunning the known-answer cases in between, so
that each change's effect can be seen. Surgery changes many things at once and gives that up. That is
acceptable here because the old arrangement is being replaced, not tuned: the question is no longer which
change helped, but whether the rebuilt setup works, and the trial task and the cases answer that for the
setup as a whole. Say this to the owner in the plan, so they know that after surgery a problem cannot be
traced to one change.

## You are the operator, not the reviewer

You designed and made these changes, so you are the wrong one to judge them. The check is a
`/harness-doctor` run in a fresh session after the project has worked under the new arrangement for a day
or so. Put that in the handover.

## Constraints, and why

- **Nothing changes before the owner agrees to the plan.** This is their running project.
- **Never delete, and never move.** Freeze, archive, copy or leave in place. Disk space is cheap and a deleted record is not recoverable.
- **Do not touch the project's data.** The harness lives in `.harness/`. Protect the data in the rules file before any session starts.
- **Each edit to an existing project file is agreed individually** in the plan, and the original is copied first.
- **Ask before installing hooks,** and prefer the project's settings to the user's.
- **Earlier results are unverified until something checks them.** Do not import them as verified. Where the ledger already marks them verified after a check that was not one, withdraw it with `H unverify`.
- **Keep secrets out** of the rules file, the ledger and the record. Keep the answers to the known-answer cases out of the plan and the record too, and give trial files neutral names: workers can read those.
- **Use the kit's commands for the kit's files.** Do not edit the ledger or the status files directly.

If this session started inside a project that already has hooks, it was registered as a worker and its file
writes are refused. Run `H join <project> --role guest` first.
