---
name: reviewer
description: Join a harness project as a reviewer of other sessions' results. Typed by the owner as /reviewer <project>.
argument-hint: "<project>"
disable-model-invocation: true
---

The owner wants this session to review results in a harness project.

Arguments given: `$ARGUMENTS`. The first word is the project name.

Run this, with the project name in place of `<project>`:

    {{HARNESS}} join <project> --role reviewer

It prints your session name, your ledger command and your role instructions. Follow those instructions; they
are the project's own and take precedence over anything general. Then take your first review with the `next`
subcommand of your ledger command.

If no project name was given, run `{{HARNESS}} projects` and ask which one.
