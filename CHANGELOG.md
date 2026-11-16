# Changelog

## 0.2.0

- New skill: `/harness-xray`, a read-only look at a project spread over several folders. It says what each
  folder is, which copies have drifted apart, whether it is one project or several, where it should live,
  and which skill to run next. It changes nothing.
- New ledger command: `survey <folders...>`, which the x-ray uses. It reads file names, sizes and dates,
  and reads the content of same-named databases and status-like files to tell identical copies from
  drifted ones. It needs no project, writes nothing, and does not open files whose names suggest secrets.
- Triage and surgery now handle a scattered project: they start from the x-ray's report and gather the
  folders into one home by copying, never moving (`skills/harness-triage/references/gathering.md`).
- The surgery plan and record gain a section for the folders and what happened to each.
- Two fixes from a first run on Windows: `snapshot` now closes the ledger so a later `restore` can replace
  it, and write rules are compared without regard to letter case there, so a worker is no longer refused
  its own task folder. macOS and Linux behave as before.

## 0.1.0 (first public version)

- Three skills: `/harness-triage` (assess a starting project and set up none, lite or full),
  `/harness-doctor` (independent check-up that changes nothing) and `/harness-surgery` (reconfigure an
  arrangement that is wrong).
- Three role commands: `/coordinator`, `/worker`, `/reviewer`.
- The kit: the ledger command (`kit/harness.py`), one hook script for every Claude Code hook event
  (`kit/hook.py`), and the hook installer (`kit/hooks_install.py`), which installs into one project's
  settings by default.
- `install.py`, which copies the kit and skills into place and changes no settings. Its edit to a skills
  folder's `.git/info/exclude` is opt-in with `--git-exclude`.
- `--uninstall` removes the lines `--git-exclude` added, and nothing else in that file.
- Documentation in `docs/`, including a security page, and `SECURITY.md` for reporting problems privately.
- Scripted tests for the ledger, the hooks and the documents.
- Tested with Claude Code 2.1.325 on macOS. Not yet run on Windows.
