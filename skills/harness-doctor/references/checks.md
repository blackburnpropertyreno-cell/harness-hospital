# The checks

Organised by the six principles, then checks that cut across them. For each: where to look, what a bad sign
looks like, what it usually means, and the usual remedy. Thresholds are rules of thumb. A dotted name such
as `flow.long_running_tasks` is a field in the output of the `metrics` command, whose `field_notes` entry
defines the less obvious ones. Where a check needs something the ledger does not record (models, cost, the
number of open sessions), ask the owner.

Contents: C Context · L Ledger · A Author never grades · M Measure · P Rules in code · S Small wins ·
Flow and the coordinator · The owner · Fit and drift · Saving and handoff · Hygiene

---

## C - Context is all it knows

**C1. Tasks that do not say enough.**
Look at: task details in three or four task folders; counts of `asked` and `blocked` events in the log.
Bad sign: workers ask the owner things the coordinator knew, block for missing information, or return work
that answers a different question. Details that are one line long.
Usually means: the coordinator writes tasks as reminders to itself.
Remedy: require every task to state what is wanted, what is known, and what done looks like; add that to the
coordinator's role file with one good example.

**C2. Role files that have grown.**
Look at: `role_prompt_words`; compare with the shipped templates (roughly 300 words each).
Bad sign: a role file several times its original length, with rules added after each incident.
Usually means: prose is being used where a hook rule or a checker belongs, and the parts that matter are
being diluted.
Remedy: move hard limits into the rules file, delete instructions for situations that no longer occur, keep
the reasons.

**C3. Instructions that have drifted from reality.**
Look at: paths, file names, tool names and counts mentioned in role files, project instructions and task
details; check each exists.
Bad sign: a folder that was renamed, a script that moved, a rule about a tool nobody uses.
Usually means: the project changed and the instructions were not updated, so sessions work from a false map.
Remedy: fix them, and note which instructions go stale fastest; those should be generated or checked.

**C4. Tasks the wrong size.**
Look at: `flow.long_running_tasks`, `flow.in_progress_without_checkpoint`, `minutes_median.started_to_done`.
Bad sign: tasks in progress for many hours with no checkpoint (too big, and lost if the session dies), or
many tasks that take two minutes each (the coordination costs more than the work).
Remedy: split large tasks at natural review points; batch trivial ones into one task with a list.

**C5. Work lost at a compaction or restart.**
Look at: `flow.in_progress_without_checkpoint`, `flow.checkpoints`; requeued tasks that restarted from nothing.
Bad sign: a second session redoing what the first had half finished.
Remedy: make checkpoints a habit in the worker role file; shorten tasks.

**C6. Too many tools or too little.**
Look at: whether several workers wrote near-identical helper scripts in their task folders; whether role
files list tools nobody calls.
Remedy: write the shared helper once and name it; remove what is unused.

---

## L - Ledger, not memory

**L1. State in more than one place.**
Look at: every file a session or the owner reads to learn status. Count them.
Bad sign: a notes file, a spreadsheet, a page in a notes app or a chat message that is treated as the
record and can disagree with the ledger. Duplicate rows for one item with different statuses.
Usually means: a view is being edited by hand, or a habit from before the ledger survived.
Remedy: one source. Regenerate every other view from it and stop editing them.

**L2. Views that are only partly refreshed.**
Look at: any script that pushes status elsewhere. Does it update existing items or only add new ones?
Bad sign: an item whose status changed in the ledger but not in the place the owner reads.
Remedy: full refresh every time, with a "last synced" time shown.

**L3. The coordinator as the record.**
Look at: ask what a brand-new coordinator session would not know. Read `.harness/notes/`.
Bad sign: priorities, promises or the owner's decisions that exist only in the coordinator's conversation.
Usually means: the role is drifting from deciding to remembering.
Remedy: decisions into the ledger with the `answer` command, plans into task rows, then replace the
coordinator with a fresh session as a test.

**L4. Work that bypassed the ledger.**
Look at: the `scan` command's list of project files changed outside `.harness/`, against the count of
promotions; ask the owner how many sessions they have open and compare with the board.
Bad sign: project files changing with no task behind them; sessions working without having joined.
Usually means: sessions started outside the project folder and never joined, sessions that joined from
another folder while the hooks cover only the project folder, or the owner doing side work in unregistered
sessions.
Remedy: start workers in the project folder, or make joining the first line of every session.

**L5. Finished things that are not finished.**
Look at: `checking.done_unverified`, tasks whose result path is missing or empty, results with a confident
summary and a thin file.
Bad sign: done treated as verified downstream: tasks that depend on unverified work, promotions that skip
review.
Remedy: set `deps_need_verified` if later work must rest on checked results.

**L6. Unknown recorded as a footnote.**
Look at: result files and summaries for phrases like "not checked", "could not access", "assumed".
Bad sign: a result marked done or verified whose own text says a key part was not confirmed.
Remedy: blocked or needs-owner is a state; a result with an unchecked core should be in it.

**L7. Decisions that are not data.**
Look at: the decision queue on the board and `answered` events in the log, against what the owner remembers
deciding.
Bad sign: the same question asked twice by different sessions; answers given in chat and never recorded.
Remedy: every answer goes through the `answer` command.

---

## A - The author never grades its own work

**A1. Self-certified confidence.**
Look at: result files that state their own confidence or verdict; who verified each (the `show` command
prints it).
Bad sign: verdicts and confidence levels decided by the session that did the work, with nothing after.
Remedy: the reviewer sets the verdict; the author states evidence and what it did not check.

**A2. A reviewer that never fails anything.**
Look at: `checking.passes` against `checking.failures`; review notes.
Bad sign: a pass rate near 100% over more than about fifteen reviews, or notes that say only "looks fine".
Usually means: the reviewer is reading for plausibility, or its role file gives it nothing to look for.
Remedy: name this project's typical errors in the reviewer's role file; plant one known error and see
whether it is caught. If results really are that good, the reviewer may be unnecessary for that kind of task.

**A3. A reviewer that repairs.**
Look at: file changes in task folders made by the reviewer session.
Bad sign: the reviewer editing results. Nobody has checked its edits.
Remedy: fail with a note; the author fixes.

**A4. A checker that covers facts but not arguments,** or the reverse.
Look at: which kinds of task have a script, which have a reviewer, which have neither.
Bad sign: the data is rigorously checked while the conclusions built on it are checked by nobody; or
everything goes to an expensive reviewer although a script could test half of it.
Remedy: split kinds of task; scripts for facts, reviewer for reasoning.

**A5. A checker that cannot fail.**
Look at: the checker script and its history of `check_fail` events.
Bad sign: it tests only that a file exists or is non-empty; it has never failed.
Remedy: make it test something a wrong result would get wrong, and prove it by feeding it one.

**A6. A review backlog.**
Look at: `checking.done_unverified` over time, `minutes_median.done_to_verified`.
Bad sign: unverified results piling up faster than they are reviewed.
Usually means: too many workers for one reviewer, or too much sent to review that a script could handle.
Remedy: move checkable kinds to scripts first; only then add reviewer capacity or reduce workers.

**A7. Rework loops.**
Look at: `checking.tasks_failed_more_than_once`.
Bad sign: the same task bouncing between author and reviewer.
Usually means: the task is underspecified, the review note does not say how to fix it, or the task is beyond
the worker's model.
Remedy: read one loop in full to see which; fix the task detail, the note, or the model.

**A8. Reviewer independence.**
Look at: whether the reviewer shares a session, a prompt or context with the authors; ask the owner which
model it runs.
Bad sign: the coordinator or a worker doing reviews "to save time"; a reviewer weaker than the workers.
Remedy: a separate session at least as capable as the workers.

**A9. Corrections that do not travel.**
Look at: a fact that was corrected after other work relied on it.
Bad sign: later results still resting on the old value.
Remedy: record dependencies between tasks so a correction shows what must be rechecked.

**A10. Nothing asks whether the answer is already known.**
Look at: results that turned out to be known, published, or already done elsewhere in the project.
Bad sign: effort spent rediscovering. Duplicate tasks.
Remedy: a first step before effort is spent, as its own task or a specialist's job.

---

## M - Measure before believing

**M1. No known-answer cases, or stale ones.**
Look at: `known_answer_cases`.
Bad sign: none defined; or none rerun since the role files, models or rules last changed.
Remedy: three to five cases; rerun after every change.

**M2. Cases that no longer resemble the work.**
Look at: the cases against the last twenty tasks.
Bad sign: the project has moved to a different kind of task and the cases test the old kind.
Remedy: add cases drawn from recent work, including one the owner settled by hand.

**M3. Several changes at once.**
Look at: the log around the last adjustment to the setup.
Bad sign: prompts, models and rules changed together, so nobody knows which helped.
Remedy: one change, rerun the cases, then the next.

**M4. Visible failures that nobody counts.**
Look at: `flow` (requeues, reassignments, stop refusals, dead dependencies), `checking.failures`.
Bad sign: the owner feels the project is stalling and no one has looked at the counts.
Remedy: include three or four of these numbers in the coordinator's regular report.

**M5. Measuring activity instead of outcomes.**
Look at: what the coordinator's reports count.
Bad sign: tasks completed and sessions active, with no mention of how many results were verified, sent back,
or used.
Remedy: report verified results and what they changed.

**M6. No baseline.**
Look at: whether anyone knows what one session working alone would have produced.
Bad sign: no way to say the harness is earning its cost.
Remedy: rerun two or three finished tasks with a single session at high effort and compare.

**M7. For subjective work: an uncalibrated judge.**
Look at: whether a rubric exists, whether the reviewer has been compared with the owner's own past choices.
Bad sign: the reviewer's taste has replaced the owner's without anyone checking that they agree; longer or
more polished results winning by default.
Remedy: twenty past decisions as a test set; blind pairwise comparison with the order swapped.

---

## P - Put the rules in code

**P1. Important rules that exist only as sentences.**
Look at: role files and project instructions for words like "never", "always", "do not"; compare with the
rules file.
Bad sign: a rule whose breach would be costly, enforced only by asking.
Remedy: a `protected_paths`, `blocked_hosts` or `bash_deny` entry, or a shared helper that applies it.

**P2. Rules that fire constantly.**
Look at: `hook_denials.by_rule`.
Bad sign: one rule responsible for most denials.
Usually means: the rule is wrong for the work as it now is, or sessions are not told where they should write
instead. Each denial costs a turn.
Remedy: read `hook_denials.recent`, which lists what each refused call was aimed at. Fix the rule or the
role file, whichever is at fault.

**P3. Rules that never fire.**
Look at: rules in the rules file with no denial against them.
Bad sign: could be a rule nobody would break (harmless) or hooks that are not running at all.
Remedy: confirm the hooks are attached on this computer with the `check-install` command. Recent activity
times on the board and a recent `saving.last_snapshot` also show they are running. If in doubt, ask the owner
to open a new session in the project folder and see whether it appears on the board.

**P4. The shell route around the rules.**
Look at: the `scan` output for changed files that file-tool rules would have refused.
Bad sign: protected or shared files modified with no promotion recorded.
Usually means: a script or shell command wrote them. Shell commands are checked by pattern only.
Remedy: add a `bash_deny` pattern for the specific route; restore from a copy if needed; make promotion the
only writer in practice.

**P5. Sessions holding the wrong role.**
Look at: `sessions.open_by_role`; guests that hold tasks; several coordinators.
Bad sign: project work done by guest sessions, which carry few limits.
Remedy: guests are for the owner's own maintenance; work is done as a worker.

**P6. Messaging used as a side channel.**
Look at: denials under the `message` rule; a role's `messaging` set to `open` in the rules file.
Bad sign: sessions arranging work in messages the ledger never sees.
Remedy: requests as task rows; return messaging to `none` or `nudge`.

---

## S - Small wins

**S1. Parts nobody uses.**
Look at: roles with no sessions, specialists with no requests, kinds of check never run, cases never rerun,
a dashboard the owner does not open.
Remedy: remove them. Each unused part still costs attention and makes the setup harder to reason about.

**S2. More sessions than the owner can check.**
Look at: `decisions.oldest_open_minutes`, the unverified backlog, how many sessions are open, and what the
owner says about keeping up.
Bad sign: decisions waiting for hours, results nobody has read, a growing queue of proposals.
Usually means: output exceeds the owner's attention, so the extra sessions are producing unread work.
Remedy: fewer sessions at higher effort.

**S3. Coordination that costs more than it saves.**
Look at: `flow.coordinator_wakes` against tasks handed out and decisions made; ask the owner what share of
their usage the coordinator takes.
Bad sign: a coordinator waking every few minutes over two workers who rarely need anything.
Remedy: lengthen the timer, or drop the coordinator and let the owner read the board.

**S4. Agents where effort would do.**
Look at: whether quality problems were answered by adding sessions or roles.
Bad sign: a new role added after each disappointing result.
Remedy: raise the thinking effort or the model for the role that is failing, and measure on the cases.

**S5. The wrong tier.**
Bad signs of too heavy: one or two sessions, an empty decision queue, a reviewer that passes everything,
hooks whose denials are all false alarms.
Bad signs of too light: a state file with conflicting edits, the owner relaying messages between sessions,
nobody able to say what is verified.
Remedy: say so plainly and name the tier that fits: None, Lite or Full.

---

## Flow and the coordinator

**F1. Sessions stopping with work available.**
Look at: `flow.stopped` against `flow.handed_out_at_stop`; the board for idle sessions beside queued tasks.
Bad sign: workers idle while unassigned tasks wait.
Usually means: tasks are addressed to a role or a session that is not there, or dependencies are not met.
Remedy: check the `role` and `--to` fields of the waiting tasks.

**F2. An empty queue.**
Look at: `flow.stopped_with_empty_queue`; how many tasks are queued ahead of each worker on the board.
Bad sign: workers regularly finishing into an empty queue.
Usually means: the coordinator wakes too rarely, or is not keeping a task ahead of each worker.
Remedy: shorten its timer; restate the one-ahead target in its role file.

**F3. The coordinator is not being woken.**
Look at: gaps between `board` events (`log --kind board`).
Bad sign: long gaps while workers were active. The stall has moved up a level.
Remedy: restart its timer; note that the timer dies with the session.

**F4. The coordinator is cooking.**
Look at: file writes by the coordinator outside `.harness/notes/`; denials against the coordinator.
Bad sign: it is doing tasks itself.
Remedy: it assigns; it does not do.

**F5. Proposals pile up, or all get accepted.**
Look at: `followups`.
Bad sign: dozens waiting (the coordinator is not deciding) or nearly every one accepted (the project is
wandering wherever the workers' curiosity leads).
Remedy: the coordinator's role file should state the project's goal sharply enough to say no.

**F6. Dead ends.**
Look at: `flow.dead_dependencies`; tasks blocked for more than a day; blocked tasks grouped by reason.
Bad sign: tasks waiting on something cancelled; many tasks blocked by the same missing thing.
Remedy: cancel or re-point the dead ones. Group blockers by cause: if seven tasks wait on one resource,
getting it is worth more than it looks from any single task.

**F7. A starved or swamped specialist.**
Look at: queue length and waiting time for each specialty.
Bad sign: a specialist with a long queue blocking everyone, or one that has had no requests.
Remedy: a second session for the first; remove the second.

**F8. Long single commands hiding sessions.**
Look at: sessions shown as inside one call for a long time.
Bad sign: hooks and handoff notices delayed by thirty-minute commands.
Remedy: run long jobs in the background or have them write progress as they go.

---

## The owner

**O1. The owner is the bottleneck.**
Look at: `minutes_median.decision_wait`, `decisions.oldest_open_minutes`.
Bad sign: tasks waiting on answers for most of a day.
Remedy: a standing rule recorded in the coordinator's role file for the kinds of decision the owner always
answers the same way; a daily time to clear the queue.

**O2. The owner is still nudging by hand.**
Ask the owner directly. If they are prompting sessions to continue, asking sessions for status, or carrying
information between sessions, the harness is missing a part. Find which: the stop hook, the coordinator's
timer, or a view they can actually read.

**O3. The owner cannot read the state.**
Ask where they look to see how things stand, and whether it answers their question.
Bad sign: they do not open the dashboard, or they open it and still ask a session.
Remedy: change the view to lead with what they ask about most.

**O4. Access problems treated as design problems.**
Look at: blocked and needs-owner tasks, and findings marked unconfirmed.
Bad sign: effort going into redesign when the real obstacle is a book, a licence or a login.
Remedy: list exactly what is needed from the owner and what each item would unblock.

---

## Fit and drift

**D1. The goal has moved.**
Compare the goal written at setup (the `goal` field of the rules file and of `metrics`) with the last twenty
tasks. If no goal was recorded, ask the owner what it was and recommend writing it down.
Bad sign: the queue, the roles and the cases still serve the original goal.
Remedy: restate the goal; cancel what no longer serves it; update cases and role files.

**D2. The kind of work has changed.**
Bad sign: the project began as gathering (checkable by script) and is now interpretation (needs a reviewer
and a rubric), or the reverse, and the checking has not followed.
Remedy: revisit how each kind of task is checked.

**D3. The scale has changed.**
Bad sign: twice the sessions on the same coordinator timer and one reviewer; or a wind-down still running
the full apparatus.
Remedy: resize, in either direction.

**D4. The model has changed.**
Bad sign: role files written for one model now run on another, with the cases not rerun.
Remedy: rerun the cases; trim instructions a stronger model no longer needs.

---

## Saving and handoff

**H1. Copies that are not being made.**
Look at: `saving.last_snapshot`; files in `.harness/snapshots/`.
Bad sign: the last copy is hours old while sessions were working. The hooks may not be running.

**H2. A handoff routine that has never been run.**
Look at: `saving.stamps` and `saving.resumes` on a project meant to move between computers.
Bad sign: zero. The first real handoff will be the first test.
Remedy: do one now, while nothing depends on it.

**H3. A restore that has never been tried.**
Ask whether anyone has opened a snapshot. An untested copy is a hope.

**H4. No save or fetch command.**
Look at: `rules.handoff_push_set`.
Bad sign: handoff depends on the owner copying a folder by hand.

**H5. Raw files that exist on one computer only.**
Ask where large files live and whether both computers can reach them; check for a list with checksums.

**H6. The project sits in a synced folder.**
Look at: the project path for iCloud Drive, Dropbox or OneDrive.
Bad sign: a live database inside one. Expect corruption or conflicting copies.

---

## Hygiene

**G1. Secrets in the wrong place.** Search the rules file, role files and task details for keys and
passwords. They travel in every copy and handoff.

**G2. Fetched content treated as instructions.** Look in task folders for a session that followed
directions found in a downloaded page or document. Sources are data.

**G3. Disk growth.** Check the size of `.harness/work/` and the project's raw data against free space.
Downloads accumulate quietly.

**G4. Hook errors.** Read `hook-errors.log` in the harness home folder. Repeated errors mean a part of the
harness is silently not working.

**G5. The kit is out of date or differs between computers.** Compare what the ledger command prints for
`--version` on each.
