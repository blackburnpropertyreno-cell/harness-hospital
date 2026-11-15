# Bringing the work across

This file is for a hand-built arrangement, where the new ledger starts empty. It covers how the project's
existing work gets into the ledger and how the old arrangement is retired, which together are what make the
change real. A project that already has the kit keeps its ledger; see `operations.md` for repairing it in
place.

## Before changing anything

- **Find every place the project's state is written down:** status files, notes, a spreadsheet, a page in a
  notes app, a coordinator's conversation. This list is in the plan, and each item on it needs a fate.
- **Find what already works and keep it.** An existing checker script becomes the `script` for a kind of
  task. Existing rules about sources or sites become entries in the rules file. Existing specialist roles
  become role files. Do not rebuild something that is doing its job.
- **Ask the owner what the old sessions are doing now.** Work held only in a running session's conversation
  is lost if that session is closed first.

## Bringing the work across

1. **Stop the old sessions cleanly.** Have each one write down where it is, in the project's existing notes,
   before it is closed. A handoff between arrangements is like a handoff between computers: nothing should
   be mid-flight.
2. **Open items become tasks.** One `H add` per open item, with its existing identifier in the title and
   `--kind` to match how it will be checked. For the detail, write a short file under `.harness/notes/`
   saying what is wanted, what is known and what done looks like, and pointing at the existing file for the
   content, so nothing is retyped. An old status note of two lines is not a task detail by itself, and
   some items will have no file at all: say in the detail that the earlier work left nothing on disk.
3. **Finished items stay where they are.** Do not import history. The ledger starts from now; say in the
   `goal` field or a note where the earlier record lives.
4. **Past decisions the owner made** that sessions keep needing go into the coordinator's role file or the
   rules file, not into the ledger as old decisions.
5. **Results that were never independently checked** are the judgement call. For the ones that matter,
   `H add "<title>" --result <existing file>` registers the result as done but unverified, and the reviewer
   is handed it. If the old result is too thin to review, queue a task to restate it with its evidence.
   For the rest, tell the owner plainly that they predate the checking. Do not import anything as verified.
6. **Retire the old status files, with the owner's yes.** A hand-edited status file that keeps being updated
   will drift from the ledger within a day. The least destructive way is to leave the file in place and add
   one line at the top saying it is frozen as of this date and that the current state is in
   `.harness/STATUS.md`. That edits a project file, so ask first.
7. **Anything that pushed status elsewhere** (a script that copies it to a notes app, for example) should
   now read from the ledger and refresh everything each time, not only add new items. If you cannot change
   it now, turn it off and say so, because a view that is half up to date is worse than none.

## Protecting what is already there

An established project has data worth more than a new one's. Put the main data files and folders under
`protected_paths` before any session starts, and check with the owner that the list is complete.

## Counting

"Open items before" and "tasks now" rarely match one for one. An item listed twice with different statuses
is one item. Two requests waiting on the same missing thing can be one task. A result marked done that was
never checked may become a task. Show the mapping row by row.

## What to tell the owner

- Which of the old places for state are retired, which are kept, and where to look now.
- What was brought across as tasks, and what was left as history.
- Which earlier results are unverified.
- That the first day on the new arrangement is the test: run the doctor after it.

All of this goes in the record.
