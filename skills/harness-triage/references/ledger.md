# The ledger

The default ledger is one SQLite file per project, `.harness/ledger.sqlite`, reached only through the ledger
command. Sessions never write SQL and never open the file. `H` stands for the ledger command.

## Why this is the default

- Several sessions and their hooks write at the same moment. A database handles that; a shared text file
  gets overwritten.
- It is separate from the project's own data, so it stays small, can be copied every few minutes, and travels
  in a handoff.
- One command is the only door, so the rules live in one place: a task cannot be marked done without a result
  on disk, an author cannot verify its own task, and rows stay short.

Depart from the default only for a stated reason. The one common reason is agents on more than one computer
writing at the same time, which needs a hosted database and is outside this kit. Tell the owner if a project
needs that.

## What it holds

| Table | One row per | Main fields |
|---|---|---|
| `tasks` | piece of work | state, who has it, what it waits for, result path, one-line summary, who verified it |
| `sessions` | agent session | role, current task, last activity, why it last stopped |
| `decisions` | question for the owner | who asked, about which task, the answer, when |
| `events` | anything that happened | time, session, kind, task. Never edited or deleted |

Task states: `proposed`, `queued`, `in_progress`, `blocked`, `needs_owner`, `done`, `verified`, plus
`rejected` and `cancelled`. `done` means the result is on disk. `verified` means a script or someone other
than the author checked it. Keeping the two apart is how the ledger enforces that the author does not grade.

## Three zones

| Zone | Holds | Who writes |
|---|---|---|
| Ledger | state, short summaries, paths | any session, through the command |
| Task folder `.harness/work/<task>/` | notes, drafts, downloads, results, request details | the session doing that task |
| Project data (the project's own files) | verified results only | the promotion step |

Two more folders in `.harness/` belong to the owner and cannot be changed by workers: `tools/` for checker
and promotion scripts, and `cases/` for known-answer cases, which workers cannot read either.

The ledger holds pointers, not content. The command rejects long text and asks for a file path, which keeps
the central record readable.

## Commands

Setup and sessions: `H init`, `H register-path`, `H projects`, `H join`, `H whoami`, `H leave`,
`H check-install`.

Queueing work (coordinator or owner): `H add`, `H assign`, `H edit`, `H accept`, `H reject`, `H requeue`,
`H cancel`, and `H answer` to record the owner's reply to a decision. `H add --proposed` holds an item until
it is accepted, and `H add --result <file>` registers earlier work as done but unverified.

Doing work (workers): `H next`, `H show`, `H checkpoint`, `H done`, `H block`, `H ask`, `H propose`,
`H request`.

Checking: `H check` runs the configured script, `H verify` records a reviewer's pass or fail, `H unverify`
withdraws a verification that was not a real check, `H promote` moves a verified result into project data,
`H case` manages known-answer cases. Check and promote scripts run from the project folder.

Seeing: `H board`, `H list`, `H log`, `H status`, `H overview`, `H metrics`, `H scan`.

Saving and handoff: `H snapshot`, `H drain`, `H stamp`, `H resume`. `H reset` archives the ledger and task
folders and starts an empty one, keeping recorded case results; it is for clearing a trial run when a new
project is set up, never for a project with real work in it.

Reconfiguring: `H snapshot --setup` makes an undo point of the rules, roles, tools, cases and ledger,
`H restore` goes back to one, `H end-sessions` closes every session before roles or rules change,
`H trial-clear` removes a labelled trial from a ledger that holds real work, and `H unregister` stops this
computer treating a folder as a harness project.

Run any of them with `--help` for its options. A command run by a session that has joined knows who is
calling, from the session ID that Claude Code puts in the environment. The owner, or a session that has not
joined, passes `--project <name>`. For testing, the environment variable `HARNESS_SESSION_ID` overrides the
session ID, which lets one session act as several.

Paths inside the project are stored relative to it, so tasks keep working when the folder moves or is
opened on another computer.

## The views

`STATUS.md` and `dashboard.html` in `.harness/` are rewritten from the ledger after every change. Nobody
edits them. The dashboard is one page that reloads itself: decisions waiting for the owner at the top, a card
per session coloured by how recent its activity is, then tasks in columns by state. `H overview` writes one
page covering every project on this computer.

## The rules file: `.harness/config.json`

This is what you customise per project. The owner's own sessions can edit it; workers cannot.

| Field | Meaning |
|---|---|
| `goal` | The project's goal in a sentence or two, written at setup |
| `stale_minutes` | A session with a task and no activity for this long is shown as stuck. Set it above the longest normal quiet stretch. Default 20 |
| `auto_join` | What a session started inside the project folder becomes: `worker` (default), `guest`, or `off` |
| `protected_paths` | Project files and folders no session may overwrite directly, as patterns relative to the project folder, for example `data/main.sqlite` or `published/**` |
| `extra_write_paths` | Extra places every worker may write, beyond its task folder |
| `outside_writes` | `deny` (default) or `allow` for file writes outside the project folder |
| `blocked_hosts` | Sites that must not be fetched, each `{"host": "...", "reason": "..."}` |
| `bash_deny` | Shell commands to refuse, each `{"pattern": "<regular expression>", "reason": "..."}` |
| `roles` | Per role: `write` (where it may write; `{work}` means its current task folder), `messaging` (`none`, `nudge` or `open`) and optionally `max_sessions`. Add an entry named after a specialty to give that specialist its own limits |
| `checks` | Per kind of task: `script` (a command; `{result}`, `{task}`, `{workdir}`, `{python}` are filled in), `timeout` in seconds, and `review`: `true` if a reviewer must also pass it, `false` if the script alone decides, or `"sample"` to send every Nth script-passed result to the reviewer (`sample_every`, default 5; anything that failed once is always reviewed). `default` applies to kinds not listed |
| `deps_need_verified` | `true` if a task that follows another must wait until that one is verified, not merely done |
| `promote.cmd` | The command that adds a verified result to project data |
| `handoff.push_cmd`, `handoff.pull_cmd` | Commands that send the project to, and fetch it from, wherever both computers can reach |
| `autosave.minutes`, `autosave.keep`, `autosave.cmd` | How often the ledger is copied, how many copies to keep, and an optional extra save command |

## Tasks carry a kind

Give tasks a `--kind` when different work needs different checking, for example `fact` checked by a script
alone and `finding` that also needs a reviewer. Each kind gets its own entry under `checks`.
