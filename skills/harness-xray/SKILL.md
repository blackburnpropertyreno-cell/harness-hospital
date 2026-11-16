---
name: harness-xray
description: Read-only look at a project that is spread across several folders - old copies, half-finished versions, a second computer's folder, things in iCloud or Dropbox - before anything is set up or changed. Says what each folder is, which copies have drifted apart, whether it is one project or several, which folder should be the home, and which skill to run next. Changes nothing. Use this whenever the user says "harness xray" or "x-ray", says a project is a mess or all over the place, names several folders for one project, does not know which copy is current, or wants to use harness-triage or harness-surgery on work that is not yet in one folder. Run it first when in doubt; it cannot do harm.
argument-hint: "[folders]"
---

# Harness x-ray

The owner has a project they cannot see whole. It lives in several folders, some of them copies of each
other, and nobody is sure which is current. The other harness skills all assume one project folder, so none
of them can start yet. Your job is to produce the picture: what is where, what is a copy of what, and where
the project should live. You look and report. You do not move, copy, fix or set up anything.

| Situation | Skill | Stance |
|---|---|---|
| The project is scattered and nobody can see it whole | this one | Look; change nothing |
| A project that is starting | harness-triage | Build |
| A running project that may need adjusting | harness-doctor | Review; change nothing |
| An existing arrangement that is wrong | harness-surgery | Change it, with the owner's consent |

`H` below stands for the ledger command on this computer. It is shorthand for this document, not a shell
variable: type the full command each time.

    {{HARNESS}}

## How to run it

1. **Get the list of folders from the owner.** Ask for every folder they think holds part of this work. Do
   not go searching the disk for more: you would find things that are not theirs to show you, and you cannot
   tell their project from someone else's by name. You may prompt their memory with questions: an older
   copy? a folder on another computer or an external drive? anything in Downloads or a cloud drive? notes
   kept in an app? Folders that cannot be reached from this computer go in the report as not seen. A
   folder that sits inside another one they named is part of its parent, not a separate place.

2. **Survey them.** `H survey <folder> <folder> ...` needs no project and writes nothing. For each folder
   it prints the size, when it last changed, whether it is a git repository (and whether that has any
   commits), whether it has a harness, whether it appears to be in a sync service, its databases, the
   files that look like status, notes or instructions, and the names of files that may hold secrets.
   Across folders it prints probable copies (same name and size), folders nested in each other, and
   databases and status-like files that share a name, with a letter per version: the same letter means
   identical content, a different letter means they have drifted or only share a name, and `?` means the
   file was too large to compare.
   If a folder stops at the file limit, raise `--limit` and run it again, or the comparison is incomplete.
   Run this and every other command on the named folders themselves, never on their parent or the home
   folder.

3. **Read what the survey points at.** In each folder, open the newest few status-like files and any
   instructions file (`CLAUDE.md`, a README). You are looking for what the folder was for, when real work
   last happened there, and what it says about the other folders. You may look at the start of any other
   file to tell what it is. For two databases that have drifted, you may compare their tables and row
   counts, opening them read-only; do not read through the rows. Do not open the files the survey lists
   as possible secrets, or anything else that looks as if it holds credentials (a token, a key, a client
   secret, a saved login): the survey's list goes by name and is not complete. Never print their contents.

   Dates written inside notes are better evidence than file dates. When the two disagree, or the notes
   claim work that the files do not show (a status file says 180 items are done and the database holds
   156), do not pick a side: that disagreement is a finding of its own, often the most important one,
   because it means work is landing somewhere other than where the owner thinks.

4. **Ask the owner what files cannot show.** Which folder do you open when you sit down to work? Which one
   do sessions get pointed at? Is anything running right now? Is any of these someone else's, or a different
   project? Their answers outrank your reading of the dates.

   If the owner cannot answer now, do not guess for them. Put the questions in the report, and make every
   label and recommendation that hangs on an answer conditional, saying which answer changes it.

5. **Give every folder one label.**
   - **Live:** work happens here and it is current.
   - **Reference:** read by the work, not changed by it (source material, a dataset, an export).
   - **Copy:** the same as another folder, or an older state of it. Say of which.
   - **Dead:** abandoned; nothing in it is needed.
   - **Arrangement:** not project material but the coordination itself: a status file, a claims list,
     handoff notes, a coordinator's scratch folder. These are the places for state that surgery replaces.
   - **Other project:** belongs to different work.
   - **Unknown:** you could not tell. Say what would settle it.

   A folder can be two things: live for its notes and a copy for its database. Say which part is which
   instead of forcing one label.

6. **Say whether this is one project or several.** Signs that folders belong together: the same repository
   address, shared files, notes that name each other, one goal. Signs they do not: different goals, no
   shared files, different people. Two projects sharing a pile of folders is common, and it is the most
   useful thing you can tell the owner, because each project then gets its own home and its own setup.

7. **Recommend a home for each project.** One folder that everything else will be brought into or pointed at
   from. Prefer the folder where live work happens, that sessions already use, that has git history, and
   that is not in a sync service. If every candidate is in a sync service, recommend a new folder outside
   it and say why (a database written inside a sync folder can be corrupted); do not create it.

8. **Settle the drifted copies as far as you can.** For each pair with the same name and different content,
   say which looks like the master, how you know, and how sure you are. Newer is not always the master: an
   old copy can be opened by accident and saved. Where you are not sure, make it a question for the owner.
   A wrong guess here is how work gets lost later.

9. **Recommend what to run next,** with the exact line to type. If something has to be settled before any
   skill runs (sessions still working, or signs that work is being written into the wrong copy), put that
   first and say the next skill waits on it.
   - Nothing needs several sessions, or the mess is only clutter: no harness. Say what to do instead.
   - No arrangement for several sessions exists yet, the material just needs gathering: `/harness-triage` in
     the home folder. It brings the folders together as part of setting up.
   - An arrangement exists and is wrong (status files in several places, sessions pointed at different
     folders, more than one harness): `/harness-surgery` in the home folder.
   - One folder is a sound project with the kit and the rest are copies or dead: nothing to rebuild.
     `/harness-doctor` if the owner wants it checked.

10. **Report.** Use the shape below, in your reply. Then offer to save it as `.harness/xray/<date>.md` in
    the recommended home, so the next skill starts from it. Save only on the owner's yes. That file is the
    only thing this skill ever writes.

## The report

    # X-ray: <what the owner calls the work>, <date>

    Looked at <n> folders on <computer>. Nothing was changed.

    ## In short
    Three or four sentences: one project or several, where it should live, the one thing to settle first.

    ## The folders
    | Folder | What it is | Label | Last real work | Notes |
    (Last real work: the date the notes give. Add the file date when it disagrees.)

    ## Things that do not add up
    Where the notes and the files disagree. Leave the section out if there are none.

    ## Copies and conflicts
    For each: the two files, which looks like the master, how sure, what would settle it.

    ## One project or several
    ## Recommended home
    ## Not seen
    Folders on another computer or drive, and anything the owner mentioned that was not found.

    ## Questions for the owner
    Numbered. Only the ones whose answer changes what happens next.

    ## What to run next
    The exact line, and the folder to start the session in.

Write it for someone who has not looked at these folders in months. Full paths, plain words.

## Constraints, and why

- **Change nothing.** No moving, copying, renaming, deleting or tidying, and no `init` or hooks. The owner
  ran this because they do not yet know what they have; acting on a picture they have not seen is how the
  wrong copy gets kept.
- **Only the folders the owner names.** Their disk holds more than this project.
- **Dates are a hint.** Copying, syncing and a git checkout all reset them. A folder that looks fresh may be
  last month's copy.
- **No sync warning is not proof.** The survey catches the common cases. If a folder is under Desktop,
  Documents or a company drive, ask.
- **Two harnesses is a finding, not a detail.** A project has one ledger. Name it and send it to surgery.
- **Do not judge the harness itself.** Whether a setup is any good is the doctor's question. Yours is where
  things are.
- **Keep secrets out of the report,** including file contents you happened to see.

Saving the report is the one write this skill makes. If the home already has a harness with hooks, this
session may have been registered there as a worker and the save will be refused; run
`H join <project> --role guest` and save again.
