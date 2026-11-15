# Deciding how results get checked

Decide this before anything else that is project-specific. The order is checking, then measuring, then
context, because what you measure depends on what "correct" means, and what you tell workers depends on what
will be checked.

## 1. Checking

Ask the owner, or work out from the project: when a session says a task is finished, how would anyone know it
is right?

**Sort the outputs into facts and judgements.**

- A **fact** can be compared with something: a source document, a schema, a total, a test suite, a file that
  must exist. Facts get a script. Put the command in the rules file under `checks` for that kind of task.
  A passing script can verify a task with no reviewer (`"review": false`).
- A **judgement** is a conclusion, a ranking, a piece of writing, a recommendation. No script settles it.
  It gets a reviewer session: one that did not do the work and is told to look for what is wrong.

Most real tasks contain both. A finding like "these two documents share an author" rests on facts (the
documents exist, the quoted passages are accurate) and a judgement (the similarity means common authorship).
Check the facts by script, then have the reviewer judge only the reasoning. If the project is large enough,
make them separate kinds of task.

**Things to settle:**

- What does the checker script test, concretely? If the project already has one, use it.
- What is the reviewer told to look for? Edit `.harness/roles/reviewer.md` to name the two or three ways
  results in this project typically go wrong.
- Is there a question that should be answered before effort is spent, such as "is this already known?" or
  "is this in scope?" If so, make it a task that comes first (`--after`), or a specialist's job.
- What is unknown or unobtainable? If results depend on a resource only the owner can get, record that as a
  blocked state rather than letting results through with a footnote.
- When a checked fact is later corrected, what rests on it? Use `--after` and `--parent` so the dependency is
  on record.

**If the owner cannot judge the subject themselves,** the reviewer and the known-answer cases are the only
protection, so do not skip either. The reviewer should be at least as capable a model as the workers. This
does not mean every result needs a reviewer. `"review": false` is right for a kind of task where a script
fully decides correctness. Where producing the result involved choosing or interpreting, keep the reviewer.

**When there are many results of one kind,** one reviewer becomes the bottleneck. Let the script check all
of them and send a sample to the reviewer with `"review": "sample"`. Review everything that involves
judgement, and tell the owner what share of the routine results is being reviewed.

## 2. Measuring

Build three to five **known-answer cases**: tasks where the correct result is already known, representative
of the real work, including one hard one and one where the right answer is "nothing here" or "cannot tell".

- Good sources: work the owner has already done by hand, published answers hidden from the session, past
  decisions, or an error planted on purpose to see whether the reviewer catches it.
- Create each with `H case add <name>` and fill in its `case.md`: the input, the known answer, how to tell.
  Workers cannot read the cases folder, so the answers stay hidden. To run a case, give a fresh session only
  the input, as an ordinary task.
- Run them before the project starts, on the model and effort level that will do the work, and record each
  with `H case record <name> pass` or `fail`, putting the model and effort in `--note`. Whoever wrote a case
  knows its answer, so someone else runs it: a fresh subagent or a new session. Rerun them after any change
  to prompts, roles, models or rules, and change one thing at a time so a difference can be attributed.
- If the owner has no worked examples and you have to invent the cases, say so. Invented cases test only the
  traps you thought of. Replace them with real ones as soon as the owner has settled a few results by hand.

If the setup cannot pass cases whose answers you know, it will not be reliable on ones you don't. Fix it
before starting.

Also tell the owner what the harness counts by itself: tasks sent back by review, stalls, requeues, how long
decisions wait. These show harness problems without anyone needing to know the right answers.

## 3. Context

Now decide what a worker is told, knowing what will be checked.

- Each task's detail should state what is wanted, what is already known, where the inputs are, and what done
  looks like in terms the checker or reviewer will use.
- The worker role file should carry only what applies to every task in this project: where things are, the
  two or three rules specific to the subject, the format of a result. Keep it short. Rules that must not be
  broken belong in the rules file, where a hook enforces them.
- Give workers the few tools the work needs. If every worker would otherwise write the same helper script,
  write it once and name it in the role file.

## When the work is subjective

See the last section of `principles.md`. In short: check embedded facts by script, write a rubric with a
passing and a failing example for each criterion, prefer blind pairwise comparison with the order swapped
over scores, calibrate the reviewer against decisions the owner has already made, and record each new
decision by the owner so the test set grows. Where there is only one draft and no history to compare with,
the rubric and the owner's read are the check; say that plainly.
