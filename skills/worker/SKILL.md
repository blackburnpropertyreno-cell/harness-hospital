---
name: worker
description: Join a harness project as a worker, optionally as a named specialist. Typed by the owner as /worker <project> [specialty].
argument-hint: "<project> [specialty]"
disable-model-invocation: true
---

The owner wants this session to work in a harness project.

Arguments given: `$ARGUMENTS`. The first word is the project name. A second word, if present, is a
specialty.

Run this, with the project name in place of `<project>`:

    {{HARNESS}} join <project> --role worker

If a specialty was given, add `--specialty <specialty>` to that command.

It prints your session name, your ledger command and your role instructions. Follow those instructions; they
are the project's own and take precedence over anything general. Then take your first task with the `next`
subcommand of your ledger command and begin.

If no project name was given, run `{{HARNESS}} projects` and ask which one.
