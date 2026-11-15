# The six principles

One sentence holds all of it: the model does the thinking, and the harness decides what it sees, what it can
touch, where results get written down, and who checks them.

Each principle below gives the failure it prevents, because the failure is how you recognise that it is
missing.

## C - Context is all it knows

**The failure:** a session does the wrong thing confidently, or asks questions whose answers exist somewhere
it was never shown.

A session starts with nothing but its prompt, its tools and what it reads. It does not know what another
session found yesterday. So each task must carry what is wanted, what is already known, and what done looks
like. More is not better: a long prompt and a large toolbox dilute the parts that matter. Give the right
information and a few sharp tools.

## L - Ledger, not memory

**The failure:** nobody can say where the project stands without asking a session, and the answer depends on
which session you ask.

If project state lives in a chat, it is lost when that chat closes or its context is compacted. If it lives
in two or three files, they drift apart and none is the master copy. Keep state in one place outside any
session, change it through one command so the rules are applied every time, and generate every view from it
so no view can be edited into disagreement. Anything unknown, blocked or unchecked is a recorded state, never
a footnote.

## A - The author never grades its own work

**The failure:** results are marked "high confidence" by the session that produced them, and errors are found
later by accident or not at all.

A session that did the work is the worst-placed to check it: it will re-read its own reasoning and find it
convincing. Split what can be checked by rule from what needs judgement. A script checks facts against their
sources. A separate reviewer, told to look for what is wrong, checks reasoning. The session that planned the
work does not grade it either.

## M - Measure before believing

**The failure:** the setup feels as if it is working, and there is no way to tell whether a change made it
better or worse.

Before trusting a setup on questions with unknown answers, run it on a few with known answers. Change one
thing at a time and rerun the same cases. Count the failures you can see without knowing the truth: stalls,
duplicated work, rework, results sent back, findings that turned out to be already known. Those belong to the
harness, not the model.

## P - Put the rules in code

**The failure:** a rule everyone was told gets broken anyway, and is noticed after the damage.

A sentence in a prompt is a request. Sessions forget it after compaction, weigh it against the task, or
never read it. A rule that matters is enforced where it cannot be skipped: a hook that refuses the tool call,
a permission that was never granted, one shared helper that applies the rule for everyone. Keep prose for
guidance and code for limits.

## S - Small wins

**The failure:** a large apparatus of roles, skills and agents that costs several times as much and performs
no better, or worse.

Every part of a harness costs tokens, attention and upkeep on every task. Add a part when a measurement or a
repeated failure shows it is needed, and remove one when it stops earning its place. Before adding agents,
raise the thinking effort of the ones you have. Size the number of sessions to what the owner can actually
check.

## What changes for subjective work

When there is no checkable right answer (writing, design, strategy, choosing among leads), C, L, P and S stay
as they are. The ledger also records the reason for each decision. A and M change:

- **Split facts from taste.** Most subjective work still contains facts (a quote, a number, a deadline).
  Check those by script as usual and reserve judgement for the rest.
- **Write the rubric down, with examples.** Three to six criteria, each with one example that passes and one
  that fails. A reviewer without a rubric judges by its own taste.
- **Compare, don't score.** Asking "which of these two is better, and why" is more reliable than asking for a
  mark out of ten. Show the pair blind, then swap the order and ask again; keep only verdicts that survive
  the swap.
- **Use several reviewers with different lenses** when the stakes justify it: one for accuracy, one for the
  reader's point of view, one arguing against.
- **The test set is the owner's own past decisions.** Collect twenty to fifty cases where the owner already
  chose, and measure how often the reviewer agrees. Also check that the reviewer agrees with itself when
  asked twice.
- **Watch for judge bias.** Model reviewers favour longer answers, polished prose and writing that resembles
  their own. Control for length and check a sample by hand.
- **The owner is the final referee,** and each of their decisions goes into the ledger so it becomes part of
  the test set.
- **Judge the argument, not the conclusion.** A reviewer should fail a result whose reasoning does not
  support it, even when the conclusion happens to be agreeable.

## Which parts vary

Context, checking and measuring are decided fresh for every project. Rules in code vary only in their
details: the mechanism is the same and the rules are settings. The ledger almost never varies, and "small
wins" never does. Over time, as models improve, context and size shift (less needs spelling out,
fewer parts are needed). Checking and measuring do not loosen.
