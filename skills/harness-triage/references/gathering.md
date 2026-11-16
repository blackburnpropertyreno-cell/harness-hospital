# Bringing a scattered project into one folder

The kit assumes one project folder: the home. This file is for a project whose material sits in several
folders, and it is used by a new setup and by surgery alike. The rule throughout is **copy in, never move,
and leave every original as it is until the owner retires it.**

## Start from the picture

If there is an x-ray report (`.harness/xray/` in the home, or one the owner gives you), start from it and
check it still holds. If there is none and more than two or three folders are involved, recommend
`/harness-xray` first: it is read-only, and it settles which folder is the home and which copy is the
master before anything is touched. For two or three folders you can run `H survey <folders...>` yourself
and ask the owner the same questions.

Do not start gathering while any of these is open:

- which folder is the home
- which of two drifted copies is the master
- whether this is one project or two

## What happens to each folder

Every folder gets one fate, agreed with the owner before anything is copied. In surgery it is a line in the
plan; in a new setup, list them in your reply and get a yes.

| The folder is | What to do |
|---|---|
| The home | Nothing. Everything else comes to it. |
| Live work outside the home | Copy it in, to a place agreed with the owner. Check the copy. The original stays. |
| A copy of something already in the home | Bring nothing. Name it in the record as a copy. |
| A drifted copy that lost to the master | Bring in only what the master lacks, as its own clearly named folder. Never merge by hand. |
| Reference material | Small: copy it in. Large: leave it where it is and name its full path in a note under `.harness/notes/`. |
| Dead | Leave it alone. List it in the record. |
| Another project | Leave it alone. Say so. |

## Copying safely

- **Keep each source recognisable.** Copy a folder in under its own name, or one the owner picks. Do not
  reorganise the files inside it; restructuring is a separate job and hides where things came from.
- **Check every copy.** Every file in the original is in the copy with a matching checksum. Nothing less
  counts: the survey's "same name and size" figure is a lead for finding copies, not proof that one is
  complete. Say in the record how each copy was checked.
- **Databases.** Copy one only when nothing is writing to it, and take any `-wal` and `-shm` files beside
  it in the same copy. Two drifted copies of a database are never merged by hand: keep the master, keep the
  other under a clear name, and queue a task to compare them if the other may hold rows the master lacks.
- **Repositories.** A folder that is its own git repository should not be dropped inside another without
  asking: the owner chooses between keeping it as a separate repository beside the home, or bringing in
  its files without its history.
- **Secrets.** Ask before copying `.env` files, keys or anything holding credentials. They never go into
  the rules file, the ledger or the record.
- **Size.** Check there is room before a large copy. Large data that only gets read is reference: leave it.
- **Sync services.** If the home is inside iCloud, Dropbox, OneDrive or a similar folder, say so and
  recommend the owner move it out first. Do not move it yourself.

## What "one home" means afterwards

- Sessions are started in the home, and the hooks limit their writes to it. A session can still read a
  reference folder outside; it cannot write there.
- The originals are now copies. Until they are retired, someone will open one by habit and work in it.
  With the owner's yes, the least destructive way to retire one is to leave it in place and add a single
  file at its top saying it was brought into the home on this date and is no longer the working copy.
  Deleting is the owner's call, later, by hand.
- Paths inside the home are stored relative to it, so the home can move or be cloned to another computer.
  A reference folder left outside has to exist on each computer that needs it; say so in the handover.

## What you cannot see

Folders on another computer or drive are not gathered from here. List them as not seen, and have the owner
run `/harness-xray` there, or bring them over first.

## In the record

Every folder the owner named, its fate, where its copy now is, how the copy was checked, and whether the
original has been retired. Show it folder by folder.
