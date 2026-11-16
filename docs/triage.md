# Harness triage

**Command:** `/harness-triage`
**Use it when:** a project is starting and may need several Claude sessions, or will run for more than a
day.

If the project's files are spread over several folders, run [x-ray](xray.md) first. Triage then starts from
its report and gathers the folders into one home by copying, never moving.

## What it does

It assesses the project and decides how much harness it needs, then sets that up. There are three sizes,
called *tiers*:

| Tier | For | What you get |
|---|---|---|
| **None** | One session that can finish the job, where you can judge the result yourself. Usually under about two hours. | Nothing. It tells you so, suggests how to do the job well in one session, and can do the job with you there and then. |
| **Lite** | Work that outlives one session, or two sessions taking turns. Half a day to a couple of days. | A shared state file (`.harness/STATE.md`) and a checking script (`.harness/check.py`). No hooks, no coordinator. Takes fifteen to thirty minutes to set up. |
| **Full** | Several sessions in parallel for days, work you cannot judge unaided, or mistakes that would be expensive. | The ledger (a small database), a rules file, role prompts, hooks, a coordinator, workers, usually a reviewer, a dashboard and a routine for moving between computers. Takes one to three hours to set up. |

"None" is a correct answer, not a failure. A harness makes a small job slower, not faster.

For a full set-up it then:

1. Creates a `.harness/` folder beside your project's own files.
2. Decides how results are checked (facts by script, judgements by a separate reviewer), and builds three to
   five *known-answer cases*: small tasks whose right answer you already know, used to test the set-up.
3. Writes the rules that matter into `.harness/config.json`: files that must not be overwritten, sites
   that must not be fetched, shell commands that must not run.
4. Shapes the role prompts for this project.
5. Plans saving and moving between computers, if the project needs it.
6. Proves the whole thing on one small real task, from start to checked result, using separate helper
   sessions so that no one checks their own work.
7. Hands over: the exact lines for you to type next.

## What it will ask you

Four questions decide the tier:

- Does the work need more than one session at the same time?
- Will it last longer than one session's memory?
- Can you tell a good result from a bad one by looking?
- How costly would an unnoticed mistake be?

It may also ask what the project is for in a sentence or two (written down as the project's goal), which
files must never be overwritten, which sites must not be fetched from, whether the project is in a git
repository with a remote copy, and what may be copied off this computer when saving.

If you ask for a particular structure ("a coordinator and two workers"), it treats that as a suggestion to
weigh, not as the answer.

## What it changes

- Creates `.harness/` inside the project folder, and registers the project on this computer (in
  `~/.harness/`).
- With your yes: adds the hooks, by default to the project's own `.claude/settings.local.json`.
- With your agreement: a save command in the rules file, and one line in the project's instructions for a
  lite set-up.

## What it will never do without asking

- Install hooks. It also prefers the project's own settings over your user settings.
- Move, rename or delete your project's existing files. It never does this.
- Move a project out of iCloud Drive, Dropbox or OneDrive. It tells you to, and why, but leaves the move
  to you.
- Decide what may be copied off your computer by a save command.

It keeps secrets out of the rules file and the ledger.

## When to use something else

- A project that already runs several sessions under its own arrangement: use
  [surgery](surgery.md). Triage stops and says so.
- A running project that needs a check-up: use [doctor](doctor.md).
