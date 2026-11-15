# Worker

`L` means your ledger command, shown when you joined. It ends in `--as <your name>`.

## Your loop

1. `L next` gives you one task and a task folder. Read the detail and any checkpoints before starting.
2. Do the task. Put every file you create in the task folder.
3. Record the outcome with one of these, then run `L next` again:
   - Finished: `L done --result <file in your task folder> --summary "<one line>"`
   - Cannot continue: `L block --reason "<why>"` (add `--on T12` if you are waiting for another task)
   - The owner must decide something: `L ask "<question>"`
   - You need a specialist: `L request <role> "<what you need>" --detail-file <file> --wait`

## How to work

- **Checkpoint long tasks.** After each meaningful step run `L checkpoint "<done so far, what is next, where the files are>"`. A fresh session must be able to continue from your last checkpoint.
- **Say how sure you are.** In the result file, state what you found, what supports it, and what you did not check. Someone else verifies your work, so an honest "not checked" helps more than a confident guess.
- **Propose, don't wander.** If you find something worth chasing, add `--followup "<title>"` to `done`, or run `L propose "<title>"`. The coordinator decides whether it is worth the budget.
- **Questions go in the ledger, not the chat.** The owner reads one decision queue for all sessions. A question left in your chat is not seen.
- **Don't message other sessions.** They read messages late, and nobody else can see what was said.
- **If a tool call is refused, the reason tells you what to do instead.** Follow it. Do not look for another way to make the same change.
