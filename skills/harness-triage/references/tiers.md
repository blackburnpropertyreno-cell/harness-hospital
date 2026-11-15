# Choosing a tier

Project length is a rough guide. The four questions decide.

1. **Does the work need more than one session at once?** Parallel sessions need somewhere shared to record
   who is doing what. Judge this from the work, not from the structure the owner proposed.
2. **Longer than one context window?** If the work will be compacted or resumed, state must live outside the
   session.
3. **Can the owner tell good from bad by looking?** If not, something other than the author has to check.
4. **How costly is an unnoticed mistake?** Cheap mistakes can be caught late; expensive ones need a gate.

## None

One session, finishes within its own context, the owner can judge the result, mistakes are cheap. Typically
under about two hours. Do not set anything up. What helps instead: a clear prompt with what done looks like,
a higher thinking effort, and the owner reading the result.

A single-session job gains nothing from coordination machinery. Say this plainly; it is a correct outcome of
running this skill.

Owners often ask for a harness because they want the job done faster. For a job this size it does the
opposite: setting up and coordinating several sessions takes longer than one session doing the work. Say
that, since it answers the reason they asked.

## Lite

The work outlives one context window, or two sessions take turns, but there is little true parallel work.
Typically half a day to a couple of days. Setup takes fifteen to thirty minutes.

`init --tier lite` creates:

- `.harness/STATE.md`: goal, a task table with fixed states, the owner's pending decisions, decisions made,
  and the known-answer cases. Every session reads it first and updates it before stopping.
- `.harness/check.py`: a checker stub. Replace its body with the facts a script can test for this project.

You add three to five known-answer cases and one line in the project's instructions telling sessions to read
and update `STATE.md`. There is no ledger database, no coordinator, no hooks and no dashboard. Two or three
sessions editing one state file is tolerable; seven is not.

## Full

Several sessions in parallel for days, or work the owner cannot judge unaided, or expensive mistakes.
Setup takes one to three hours.

`init --tier full` creates the ledger, the rules file, role files and the status views. You then install the
hooks, shape the roles, define the checking, build the cases, and set up saving and handoff.

A coordinator is part of Full by default. Past about three working sessions, and sooner when the owner is
outside their own expertise, one person cannot track assignments, stalls and follow-ups by hand.

## Moving between tiers

Start one tier lower when unsure. Signs that Lite has been outgrown: the state file has conflicting edits,
the owner is relaying messages between sessions, or nobody can say which tasks are verified. Signs that Full
is too much: one or two sessions, an empty decision queue, a reviewer that never fails anything, the
coordinator's reports being ignored. The doctor skill checks for both.

## Sizing the number of sessions

Open only as many working sessions as the owner can check the output of. The coordinator, the reviewer and
any specialist count toward the owner's total. The limits are the owner's attention
and budget. Prefer fewer sessions at a higher thinking effort. Use a cheaper model for rote, read-only
preparation and keep the strongest model for judgement.
