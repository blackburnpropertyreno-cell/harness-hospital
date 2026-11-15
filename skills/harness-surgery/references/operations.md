# Operations

Procedures for the situations surgery meets. `H` is the ledger command. The building blocks themselves
(tiers, the rules file, checking, roles, hooks, handoff) are described in the triage skill's reference files;
this file covers what is specific to changing an arrangement that already exists.

Contents: A hand-built arrangement · A kit on the wrong tier · A kit with the wrong parts · Removing a
harness · Undoing

---

## A hand-built arrangement

This is the usual case: the project coordinates several sessions through files and habits that grew as it
went. Typical parts, and what each becomes:

| What exists | What is wrong with it | What it becomes |
|---|---|---|
| A status or claims file that sessions edit by hand | Sessions overwrite each other; rows are duplicated with different statuses; nobody is sure it is current | Tasks in the ledger. The file is frozen with a line pointing to `.harness/STATUS.md` |
| A chat session acting as coordinator, which others must ask before taking work | The project's state lives in one conversation and is lost when it closes or compacts | A coordinator role that reads the board and keeps nothing in memory |
| Status copied into a notes app or sheet by a script | Often adds new items and never updates old ones, so the copy drifts | Regenerated in full from the ledger each time, or switched off |
| Sessions messaging each other for status and requests | Read late; invisible to the owner | Requests as task rows; messaging limited by the hooks |
| Rules in a contract or instructions document ("never fetch from X", "write only in your folder") | Broken sooner or later, and noticed afterwards | Entries in the rules file, enforced by hooks. The document stays as explanation |
| Results that carry their author's own confidence rating | The author is grading its own work | A reviewer role and a `checks` entry per kind of task |
| A checker for the data but none for conclusions | Arguments built on checked facts are checked by nobody | Facts by script, conclusions by the reviewer |
| Specialist sessions reached by message | Their queue stalls when the session closes | Specialist role files; requests through the ledger; a session cap if the resource is scarce |
| Standing approvals the owner gave in chat | Rediscovered or forgotten by each new session | Written into the coordinator's role file |
| "Unchecked" or "could not access" noted in a footnote | Reads as finished | A blocked or needs-owner state, grouped by what is missing |

Steps:

1. `H init <name> --path <folder> --tier full` (or `lite`). This creates `.harness/`, records the project
   in this computer's registry, and touches no existing file.
2. Copy the files you will edit into `.harness/surgery/before/`, as the main file describes.
3. Fill in the rules file, starting with `protected_paths` for the project's data and `goal`.
4. Carry existing rules into the rules file one at a time. For each, decide whether breaking it would be
   costly: if so it becomes `protected_paths`, `blocked_hosts` or `bash_deny`; if not it stays as guidance
   in a role file.
5. Turn what already checks results into `checks` entries. An existing checker often tests the project's
   data as a whole and not one task's result, so it may need a small wrapper; keep the original unchanged
   and call it. Put scripts you write in `.harness/tools/`. Check scripts run from the project folder.
   Ask how verified results are meant to reach the project's data, and set `promote.cmd` or record that
   it is undecided. If the project's existing data already breaks the rules a new checker enforces, the
   checker should fail a task only for breaks that task adds, measured against a baseline taken now, and
   the size of the existing problem goes in the record and becomes a task of its own.
6. Write the role files. Start from what the project's existing role descriptions got right.
7. Prove it, reset, bring the work across, retire the old arrangement, install hooks: the order in the main
   file.

Reuse the project's own identifiers in task titles (a lead number, a ticket number), so that the owner and
the existing files still line up.

Group what waits on the owner by what is missing, not by which item is waiting. Twenty items that all need
the same loan request or the same shelf visit are one decision with a list, and the tasks behind it are
blocked with that decision named. The owner then sees one request worth making instead of twenty small ones.

Decide the workers' write zone with care, and say what you chose in the plan. The default is the task folder
only, with verified results reaching the project through the promotion step. A project whose own layout has
sessions writing straight into shared data folders can widen it with `write` entries for the worker role,
but every folder added is one the "only checked results reach the project" rule no longer covers. Prefer
widening for folders a checker script then tests, and keep `deps_need_verified` on when the owner cannot
judge results themselves.

Things the ledger command gives you for this:

- `H add "<title>" --result <existing file>` registers earlier work as done but unverified, so that a
  reviewer is handed it. Use it for results that matter and were only ever rated by their author.
- `H block <task> --reason "<what is missing>"` marks an item that cannot proceed, and
  `H add ... --after <task>` makes one item wait for another. `H list` shows what each queued task waits for.
- `H add ... --proposed` holds an item until the coordinator or owner decides it is worth doing.
- A specialist limited to one session: an entry under `roles` named after the specialty with
  `"max_sessions": 1`. Requests to it are checked as its own kind when `checks` has an entry of that name.

---

## A kit on the wrong tier

**Lite to Full.** `H init <name> --path <folder> --tier full` adds the ledger, role files and views beside
the existing state file and updates the rules file's tier. Then turn each open row of `STATE.md` into a
task, record decisions that sessions still need in the coordinator's role file, and freeze `STATE.md` with a
line pointing to `.harness/STATUS.md`. Install hooks.

**Full to Lite.** Drain and end the sessions. Write the open tasks into a `STATE.md` (run
`H init <name> --path <folder> --tier lite` to create the template and switch the tier; `H list` gives you
the open tasks). Remove the hooks for the project. Leave the ledger file where it is as history. Tell the
owner that the dashboard and the board no longer update.

---

## A kit with the wrong parts

The tier is right and something in it is not. Take the undo point, end the sessions, then:

- **Roles.** Rewrite the role files. Remove a role that has no work by deleting its file's content down to a
  note saying it is retired; do not leave a queue addressed to it (`H list --state queued`, then
  `H assign` or `H cancel`).
- **Checking.** Change the `checks` entries. Results verified under the old checking stay verified in the
  ledger; if the old checking was not really checking, say in the record that they should be treated as
  unverified, and queue review tasks for the ones that matter.
- **Known-answer cases.** Replace cases that no longer resemble the work. Rerun all of them after the
  changes.
- **Rules.** A rule that fired constantly was wrong or badly explained: read what it refused in
  `hook_denials.recent` from `H metrics` before changing it.
- **The ledger's contents.** The ledger is kept; repair it in place. Cancel tasks waiting on cancelled work.
  Re-address a task sent to a role nobody holds, or change its kind or detail, with `H edit`. Requeue tasks
  held by sessions that are gone. Withdraw verifications that were not real checks with `H unverify`, which
  puts the result back in front of the reviewer. Proposed follow-ups are normally the coordinator's to
  decide; reject or accept them here only where the plan says so.
- **Role files against the current kit.** The project's role files were copied from the kit when it was set
  up and the kit may have moved on. Compare them with the files in the `templates/roles` folder beside the
  ledger command, and carry across lines the project's copies lack.
- **Where hooks are installed.** To move them between the user's settings and the project's:
  `{{HOOKS}} --remove` from one, `{{HOOKS}} --add --project <folder>` to the other, or the reverse.

---

## Removing a harness

Sometimes the finding is that the project no longer needs one: it has shrunk to one session, or the work has
become something the owner can judge by reading.

1. Drain and end the sessions.
2. Write the open tasks and unanswered decisions into a plain notes file the owner chooses.
3. Remove the project's hooks: `{{HOOKS}} --remove --project <folder>`.
4. `H unregister <name> --yes` stops this computer treating the folder as a harness project.
5. Leave `.harness/` in place as a record. Say so in the handover.

---

## Undoing

Do these in order. The hooks come off first, because while they are on they refuse writes to protected
files, including the ones you are putting back.

- **Hooks:** `{{HOOKS}} --remove --project <folder>`.
- **Project files you edited:** copy each back from `.harness/surgery/before/`.
- **The kit's own files:** `H --project <name> restore <undo point> --yes` puts the rules file, role files,
  tools and cases back as they were, removing any of those that did not exist then. Add `--ledger` to put
  the ledger back too, which discards every task change made since. A restore first takes a copy of the
  present state and prints its name, so the restore can itself be undone. Give the owner the name of the
  point taken before the surgery and the one taken at the end, and say which is which.
- **A hand-built project that should return to how it was:** unfreeze the status files from the copies,
  remove the hooks, and `H unregister <name> --yes`. The `.harness/` folder can stay; nothing reads it.

Undo is for the first day or two. After sessions have done real work under the new arrangement, going back
means losing that work's records, so the record should say until when undoing is still sensible.
