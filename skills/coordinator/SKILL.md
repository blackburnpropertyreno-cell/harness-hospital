---
name: coordinator
description: Join a harness project as its coordinator. Typed by the owner as /coordinator <project>.
argument-hint: "<project>"
disable-model-invocation: true
---

The owner wants this session to be the coordinator of a harness project.

Arguments given: `$ARGUMENTS`. The first word is the project name.

Run this, with the project name in place of `<project>`:

    {{HARNESS}} join <project> --role coordinator

It prints your session name, your ledger command and your role instructions. Follow those instructions; they
are the project's own and take precedence over anything general.

Then do your first wake as the instructions describe, and finish your reply by telling the owner the one
line to type in this session so that you are woken on a timer:

    /loop 5m Coordinator wake: run the board and act on it.

If no project name was given, run `{{HARNESS}} projects` and ask which one.
