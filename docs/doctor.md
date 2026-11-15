# Harness doctor

**Command:** `/harness-doctor <project>`
**Use it when:** a project is running and you want to know whether its set-up still fits the work, or it
needs a few tweaks.

## What it does

It is an outside review. It answers one narrow question: is this project's harness still the right one for
the work as it is now? It does not judge the project's results.

Run it in a **fresh session**. A session that has worked inside the project, or set it up, will find its own
arrangements reasonable, in the same way an author is a poor judge of their own work.

It:

1. Reads the rules file, the role prompts and the board (the current state of every task and session).
2. Asks you three questions (below).
3. Gathers evidence: counts and timings from the ledger, recent history, files changed outside the
   `.harness/` folder, the known-answer cases, and three to five tasks read in full.
4. Works through a list of checks organised by the six principles, and looks for problems not on the list.
5. Judges whether the harness is too heavy, too light or about right.
6. Writes a report to `.harness/doctor/<date>.md` and gives you the short version.

It also works on a project that coordinates sessions by hand, with no kit installed. Then it gathers the
evidence by reading, and gives the report in its reply.

## What it will ask you

- What has changed since the set-up?
- What do you find yourself doing by hand?
- What have you stopped trusting?

And, because the ledger cannot tell it: which model and effort level each role uses, how many sessions you
have open, and roughly what the project is costing.

## What the report contains

- The three findings that matter most, at the top.
- At most eight findings in full, each with evidence (a number, an event, a file), its cause, and the
  smallest remedy that would work. Smaller points go under "Also noticed".
- The recommended changes grouped by how they can be applied:
  - **Safe to batch:** mechanical fixes that do not change how work is done or checked.
  - **One at a time:** anything that changes behaviour. Apply one, rerun the known-answer cases, then the
    next, so you can see which change helped.
  - **Needs the owner:** access problems (a login, a licence) and decisions about scope.
- What is working and should be kept.
- What it could not check.

If the arrangement is wrong at the root, the report says so and recommends [surgery](surgery.md).

## What it changes

Nothing, apart from writing its report. If the session was started inside the project folder and was
registered as a worker automatically, it may first join as a guest (an entry in the ledger) so that it is
allowed to write the report. It does not apply its own recommendations: a separate session does,
so the reviewer stays a reviewer.

## What it will never do without asking

- Change any file in the project other than its report.
- Install anything, in a project without the kit.
- Carry on in a session that has already done project work. It tells you and recommends a fresh one.
- Save its report in a project with no `.harness/` folder. It asks you where.
