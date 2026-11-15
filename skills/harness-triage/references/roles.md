# Roles

A role is a short instruction file in `.harness/roles/` plus limits in the rules file. A session gets its
role when it joins, and the ledger command prints the role file to it then.

## The standard three

**Coordinator.** Keeps sessions moving and reports to the owner. It reads the board, assigns work, decides on
proposed follow-ups, requeues stuck tasks, runs the promotion step on verified results and relays the
owner's decisions into the ledger. It does not do
workers' tasks and does not judge results. It keeps nothing in its own memory, so a fresh coordinator can
take over at any time. There is one per project; a new one joining replaces the old.

**Worker.** Takes one task at a time, writes only in that task's folder, records the outcome, takes the next.
It proposes follow-ups but does not decide to pursue them.

**Reviewer.** Checks finished results it did not produce, looking for what is wrong. It passes or fails each
with a note and does not repair anything.

A coordinator is needed once there are more than about three working sessions, and earlier when the owner is
working outside their own expertise. Below that, the owner can run `H board` themselves.

The coordinator, the reviewer and any specialist each take one of the owner's sessions. If the owner wants
six sessions in all, say how many of them will actually be doing the work.

## Specialists

Add a specialist only when the project has work that needs different access, different instructions, or a
single scarce resource that should be queued for: a licensed database, an expert method, a slow external
service. Copy `.harness/roles/specialist.example.md` to `.harness/roles/<specialty>.md` and rewrite it. A
session joins with `H join <project> --role worker --specialty <specialty>` and receives only tasks addressed
to that specialty, never ordinary work. Other sessions ask it for things with `H request <specialty> "..."`,
which is a task row, not a message.

If only one session at a time may use the resource, say so in the rules file: under `roles`, add an entry
named after the specialty with `"max_sessions": 1`, and a second session trying to join is refused. The
entry adds to the worker's limits; it does not replace them. This keeps a second specialist from starting. It does not stop an ordinary worker reaching the resource by
itself, so say in the worker role file that such requests go through the specialist.

Do not add a role because it sounds useful. Each role is a session to pay for and a queue to watch. A
cheaper alternative for a light load is a convention: the coordinator addresses every such task to one named
worker with `--to`.

## Editing the role files

The shipped files are starting points written to be general. For each project:

- Add the two or three things specific to this subject that every session in that role needs.
- Name the usual ways results go wrong here, in the reviewer's file.
- Remove anything that does not apply.
- Keep each file to about a page. Explain why a rule exists so the session can handle a case you did not
  foresee. Put hard limits in the rules file, where a hook enforces them.

Then test each role file you changed substantially on the model that will run it. A prompt that a stronger
model follows well may be read differently by a weaker one. The known-answer cases test the worker and
reviewer files. For the coordinator, the first real wake is the test: read its first report with the owner
and check it acted on every line the board listed.

## Models and effort

Mistakes in judgement roles cost the most and are the hardest for the owner to spot, so spend there.

| Role | Suggested |
|---|---|
| Triage and setup (this skill) | The strongest model available. It runs once, and its decisions shape everything after |
| Coordinator, reviewer | The strongest model, or the next one down at high effort |
| Workers on well-specified tasks with a script checking them | A mid-tier model at medium effort |
| Workers making judgement calls in a subject the owner does not know | Higher effort than medium |
| Rote, read-only preparation | A cheaper model |

This is reasoning from where mistakes cost most, not a measured result. The known-answer cases settle it for
a given project: run them at two effort levels and keep the lower one if the results match.

## Starting sessions

The owner types one of these as the first message of a new session:

    /coordinator <project>
    /worker <project>
    /worker <project> <specialty>
    /reviewer <project>

A session started inside the project folder is already registered as a worker and only needs to be told to
begin. When the hooks are installed for the project only, which is the default, start every working session
inside the project folder: the commands above still work from elsewhere, but the rules do not reach a
session started outside it.

**The coordinator needs something to wake it.** It is a session too, so it stops when its turn ends. In the
coordinator session the owner runs:

    /loop 5m Coordinator wake: run the board and act on it.

Choose the interval from how fast the work moves; five to fifteen minutes suits most projects.

## Messages between sessions

By default workers and reviewers cannot message other sessions, and the coordinator can send only a short
wake-up. Everything else goes through the ledger, where the owner and the coordinator can see it and where a
busy session will find it when it next looks. Loosen this per role in the rules file only if the project has
a real need.
