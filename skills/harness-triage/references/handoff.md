# Saving, and moving between computers

## Where the project lives

Keep the working copy in an ordinary local folder, not inside iCloud Drive, Dropbox or OneDrive. Sync
services can corrupt a database that is being written to, offload files that sessions need, and create
conflicting copies. If the project is in such a folder now, tell the owner and recommend moving it.

There are three layers, and each piece of data is edited in exactly one of them:

1. **The working copy,** local and unsynced, where sessions write.
2. **The durable copy,** which both computers can reach: a private git remote for text and code, object
   storage or an external drive for large raw files.
3. **Views,** generated for reading: the dashboard, the status file, anything pushed to a notes app. Views are
   never edited.

## Saving while working

The hooks copy the ledger into `.harness/snapshots/` every few minutes (`autosave.minutes`) and keep the most
recent copies. Set `autosave.cmd` in the rules file if the project should also be saved somewhere else on the
same timer, for example a git commit.

Each automatic copy also refreshes `.harness/handoff/autosave.sqlite`, which is inside the folder that
travels. So whatever saves the project off this computer carries a ledger at most a few minutes old, even
between handoffs. Without a save command, the ledger exists only on the computer in use until the next
`stamp`; tell the owner that, and let them choose.

Git handles text well: it merges changes or flags a conflict. It cannot merge a database, which is why the
ledger has one home at a time and moves by handoff.

## Handoff: finishing on one computer and continuing on another

The routine is planned, not automatic. It takes a few minutes and guarantees the other computer starts from
the latest state.

**On the computer you are leaving:**

1. `H --project <name> drain`. No new tasks are handed out. Each busy session is told, after its next tool
   call, to save its files, record where it is, and stop. Nobody has to message them.
2. Run `drain` again until it reports that every session has finished or recorded a checkpoint.
3. `H --project <name> stamp`. This seals a copy of the ledger with the computer's name, the time and a
   checksum, runs the save command if one is set, and **parks** this computer: its hooks and ledger command
   refuse writes to the project from then on. If the save command fails, nothing is parked and it says so.

**On the computer you are moving to:**

4. The first time only: `H register-path <name> <folder>` to say where the project lives on this computer,
   and install the hooks here too (they are per computer, and by default per project).
5. `H --project <name> resume`. This runs the fetch command if one is set, checks the sealed ledger against
   its checksum, and reports the stamp it is resuming from (which computer, when). Tasks that were mid-flight
   return to the queue with their checkpoints. If the copy is incomplete it refuses and changes nothing.
6. Start fresh sessions and have each one join. They read the ledger; nothing depends on the old sessions.

One computer works on a project at a time. A parked computer stays parked until `resume` is run on it.

## Setting the save and fetch commands

Put them in the rules file under `handoff`. They run in the project folder. For a git-based project, for
example:

    "push_cmd": "git add -A && git commit -m handoff --allow-empty && git push"
    "pull_cmd": "git pull --ff-only"

`git add -A` saves everything in the folder, including task folders with downloaded files and anything
licensed or private. Agree with the owner what may go to the remote, and keep the rest out with the
project's `.gitignore` before the first save. Then run the save command once to see that it works.

The sealed ledger and its stamp are in `.harness/handoff/`, which is meant to travel. The live ledger, the
snapshots and the parked marker are local and are listed in `.harness/.gitignore`.

If no commands are set, `stamp` says the owner must carry the project folder across themselves.

## Large raw files

Files too big for git need their own durable home that both computers can reach, such as an object storage
bucket synced with a tool like `rclone`. Decide with the owner:

- Whether the second computer mirrors everything or fetches files on demand. Mirroring costs disk space;
  fetching on demand costs time when a file is first needed.
- That the save command uploads them, so a handoff is not sealed while files exist only on one computer.
- That the project keeps a list of the files with sizes and checksums, so either computer can tell whether
  it has them all.

This kit runs the commands you configure; it does not manage the storage itself. Check current prices and
terms with the owner before recommending a service.

## If something goes wrong

- **Sessions were not drained** (a crash, a closed laptop): on the same computer, just continue; the ledger
  is intact and stuck tasks show on the board. To move anyway, `stamp --force` seals what is recorded, and
  unrecorded work in those sessions is lost.
- **Both computers have new work:** `resume` refuses and explains. The owner chooses which copy to keep;
  `resume --force` replaces the local ledger and keeps the old one in `.harness/snapshots/`.
- **The computer is lost or will not start:** on the other computer, fetch the project, copy
  `.harness/handoff/autosave.sqlite` over `.harness/ledger.sqlite`, and continue. This skips `resume`
  because no stamp was made. Work since the last save is lost.
- **The ledger is damaged:** stop sessions, copy the most recent file from `.harness/snapshots/` over
  `.harness/ledger.sqlite`, and continue. At most a few minutes of state changes are lost; files in task
  folders are unaffected.
