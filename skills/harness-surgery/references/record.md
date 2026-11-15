# The plan and the record

Two documents, both for the owner, both in plain words with a file or a number behind every claim.

## The plan, shown before anything changes

Give it in your reply. Save it as `.harness/surgery/<YYYY-MM-DD>-plan.md` after it is approved and
`.harness/` exists. Name the known-answer cases but do not describe their answers: workers can read this.

```markdown
# Surgery plan: <project>, <date>

## What is wrong
<Three to six findings, most costly first. Each with its evidence: a file, a count, something the owner said.>

## What stays
<The parts that work and will be kept as they are.>

## Where it ends up
<Tier, roles, how each kind of result will be checked, where state will live. A few lines.>

## Changes
<Every change, numbered, in the order they will be made. For each: what, and why in a line.>

## Existing files I would edit
<Each one, what the edit is, and that the original is copied first. The owner can strike any of these.>

## New files outside .harness/
<Usually only the project's hooks file, `.claude/settings.local.json`.>

## Before I start
<What the running sessions must do, and anything only the owner can do. If sessions are already closed,
what existed only in their conversations and is already lost.>

## How this is undone
<The undo point, and until when undoing is sensible.>

## How I will show it works
<The trial task, the known-answer cases, and the count of open items carried across.>

## What you give up
<After this many changes at once, a later problem cannot be traced to one of them.>

## Questions for you
<Only what you cannot decide from the project.>
```

## The record, written when the work is done

Save it as `.harness/surgery/<YYYY-MM-DD>.md`.

```markdown
# Surgery record: <project>, <date>

## Outcome
<One or two sentences: what the project runs on now, and whether everything in the plan was done.>

## Before you start working again
<Anything the owner must do first, including opening one new session in the project folder and checking
it appears on the board, which is the only test that the hooks fire. Then the exact lines to start the
coordinator and its timer, the reviewer, the workers and any specialist, and where each must be started.>

## What changed
<The changes actually made, against the plan's numbering. Mark any that were skipped or done differently, and why.>

## What was kept

## Carried across
<A table: each old item and what it became. Then what was left out, with reasons.>

## Old arrangement
<Each old place for state: frozen, repointed, switched off, or kept, and where to look now.>

## Not verified
<Earlier results that predate the checking. Parts of the proof that could not be run. That the trial ran
before the hooks were installed. Anything untested. Also note that the `scan` command will list this
surgery's own edits to project files, so a later review does not mistake them for work that bypassed the
ledger.>

## How to undo
<In order: remove the hooks, copy edited files back, restore the kit's files. The undo points' names and
which is which. Until when undoing is sensible.>

## Next
<Run /harness-doctor in a fresh session after a day of work under the new arrangement.>
```

In your reply, give the outcome, what the owner must do before starting, the counts carried across, what is
not verified, and the path to the record. Do not paste the whole record.
