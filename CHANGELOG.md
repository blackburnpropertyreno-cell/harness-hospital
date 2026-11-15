# Changelog

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
