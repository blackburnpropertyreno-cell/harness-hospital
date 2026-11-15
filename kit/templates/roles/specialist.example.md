# Specialist: <name>

Copy this file to `<specialty>.md` in the project's `roles/` folder and rewrite it. A session joins with
`join <project> --role worker --specialty <specialty>` and then receives only tasks addressed to that role.

`L` means your ledger command, shown when you joined.

## What you do

<One paragraph: the one kind of request this role answers, and what it never does.>

## Your loop

1. `L next` gives you a request. It names who asked and holds their detail file.
2. Answer exactly what was asked. Put the answer in the task folder.
3. `L done --result <file> --summary "<one line>"`, then `L next`.

The requester's task was waiting on yours and returns to the queue by itself when you finish.

## Limits of this role

<What this role may access, what it must cite, and what it must refuse or pass to the owner with `L ask`.>
