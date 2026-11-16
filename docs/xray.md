# Harness x-ray

**Command:** `/harness-xray`
**Use it when:** a project is spread over several folders (old copies, half-finished versions, a folder on
another computer, things in iCloud or Dropbox) and nobody can see it whole. Run it before triage or surgery.
When in doubt, run it first: it cannot do harm.

## What it does

The other skills all assume the project lives in one folder. A real mess does not. The x-ray produces the
picture that has to exist before anything can be set up or fixed: what is where, what is a copy of what, and
where the project should live. It looks and reports. It changes nothing.

It:

1. Asks you for every folder you think holds part of the work. It does not search your disk for more.
2. Runs the kit's read-only `survey` command on them. For each folder that gives the size, when it last
   changed, whether it is a git repository or already has a harness, whether it appears to be inside a sync
   service, its databases, the files that look like status, notes or instructions, and the names of files
   that may hold secrets. Across folders it lists probable copies (same name and size), folders nested
   inside each other, and databases and status files that share a name, marked with a letter per version
   so you can see which are identical and which have drifted apart.
3. Reads the notes and instructions files the survey points at, to find out what each folder was for.
4. Asks you what files cannot show (below).
5. Labels every folder: **live**, **reference**, **copy**, **dead**, **arrangement** (the coordination
   itself: status files, claims lists, handoff notes), **other project** or **unknown**. It also points
   out where the notes and the files disagree, which usually means work is landing somewhere other than
   where you think.
6. Says whether this is one project or several. Two projects sharing a pile of folders is common.
7. Recommends one home folder for each project.
8. For each pair of drifted copies, says which looks like the master and how sure it is.
9. Tells you which skill to run next, and the exact line to type.

## What it will ask you

- Which folder do you open when you sit down to work?
- Which one do your sessions get pointed at?
- Is anything running right now?
- Is any of these someone else's, or a different project?

Your answers outrank its reading of the dates. File dates are a weak hint: copying, syncing and a git
checkout all reset them, so a folder that looks fresh may be last month's copy.

## What the report contains

- A few sentences at the top: one project or several, where it should live, the one thing to settle first.
- A table of the folders with a label for each.
- Copies and conflicts: which file looks like the master, how sure, and what would settle it.
- A recommended home.
- What it could not see (folders on another computer or drive).
- Numbered questions for you.
- What to run next.

## What happens next

The x-ray does not gather anything. The next skill does, as part of its own plan, and only by copying:

- No arrangement for several sessions exists yet: [triage](triage.md), started in the home folder.
- An arrangement exists and is wrong (status files in several places, sessions pointed at different folders,
  more than one harness): [surgery](surgery.md), started in the home folder.
- One folder is a sound project and the rest are copies or dead: nothing to rebuild.

Either way the rule is the same: **copy in, never move, and leave every original as it is until you retire
it yourself.**

## What it changes

Nothing, unless you say yes to saving the report. Then it writes one file, `.harness/xray/<date>.md`, in the
recommended home folder, so the next skill starts from it.

## What it will never do

- Move, copy, rename, delete or tidy anything.
- Set up a harness or install hooks.
- Look in folders you did not name.
- Open files that hold secrets, or put their contents in the report.

## Limits

- **Whole-folder copies are matched by file name and size, not content.** Two different files with the
  same name and size are reported as probable copies. Only databases and status-like files that share a
  name have their content compared. Treat the lists as leads to check.
- **Files over 256 MB are not compared.** They are marked `?` instead of being called identical.
- **Same name does not mean same project.** A `notes.md` in two unrelated folders will be listed together.
- **It sees only this computer.** Folders on another computer or an unplugged drive are listed as not seen.
- **The sync warning is a best effort.** It catches iCloud Drive, a Mac's synced Desktop and Documents
  folders, Dropbox, OneDrive and Google Drive by their usual paths. No warning does not prove a folder is
  not synced.
