# Harness surgery

**Command:** `/harness-surgery`
**Use it when:** a project already runs several sessions and the arrangement is wrong, and needs
reconfiguring rather than reviewing.

That can be a **hand-built arrangement**: status files edited by hand, a chat session acting as
coordinator, rules that live only in prompts, the project's state written in several places. Or it can be a
**set-up made with this kit** that no longer fits the work.

If the project is spread over several folders, run [x-ray](xray.md) first. Surgery then plans from its
report: each folder gets a fate in the plan, and folders are gathered into one home by copying, never moving.

## What it does

The two ways this kind of change goes wrong are losing work during the change, and leaving the old
arrangement half in place so the new ledger becomes one more place where state lives. Every step is there
to prevent those two outcomes.

1. **Diagnose.** Starts from a recent doctor report if there is one. Otherwise finds every place the
   project's state is written down, who checks results, which rules exist only as sentences, and what you
   end up doing by hand. Also lists what works and should be kept.
2. **Check that surgery is the right tool.** If a few changes would do, it says so and points you to the
   [doctor](doctor.md). If the project needs no harness at all, it says that.
3. **Decide the target:** which tier, which roles, how results are checked, which rules are enforced.
4. **Write a plan and wait for your yes.** You may strike items.
5. **Make it undoable,** and tell you how to undo it.
6. **Stop the running sessions,** so old and new instructions do not run side by side.
7. **Operate:** protect the project's data, rebuild, prove the rebuilt set-up on a trial task, bring the
   open work across, retire the old arrangement, and install the hooks last.
8. **Account for everything:** every open item from the old arrangement is now a task in the ledger, or is
   listed with the reason it was left out.
9. **Write a record** to `.harness/surgery/<date>.md` and hand over.

Afterwards, run the [doctor](doctor.md) in a fresh session once the project has worked for a day or so
under the new arrangement. Surgery changes many things at once, so if something goes wrong later it cannot
be traced to one change; the plan says this.

## What it will ask you

- Where the project's state is written down, and which copy you actually trust.
- Who or what checks results.
- How you find out what each session is doing.
- What it may change: you approve the whole plan, and each edit to an existing project file individually.
- Whether the hooks may be installed, and where.
- For sessions that cannot be stopped cleanly: whether they are really closed.

## What it changes

Only what the plan you agreed lists. Typically: a `.harness/` folder, the rules and role files inside it,
tasks in the ledger, the hooks (with your yes), and specific existing project files you approved one by one.
The originals of those files are copied into `.harness/surgery/before/` first.

## What it will never do without asking

- Change anything before you agree to the plan.
- Edit an existing project file you did not approve individually.
- Install hooks.
- Carry on when it finds something the plan did not expect. It stops and tells you.

And it never does these at all:

- Delete. Old files are frozen, archived or left in place.
- Touch the project's data. The harness lives in `.harness/`.
- Mark earlier results as checked when nothing checked them.
- Put secrets, or the answers to the known-answer cases, in the plan or the record.
