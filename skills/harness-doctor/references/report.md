# The report

Write for an owner who will read it once and act on the first page. Plain words, short sentences, and a
number or a file behind every claim. Save it as `.harness/doctor/<YYYY-MM-DD>.md`.

Use this structure:

```markdown
# Harness review: <project>, <date>

## Verdict

<One or two sentences. Is the harness still right for the work: about right, too heavy, too light, or
right in shape but failing in one place? Lead with this.>

## If you only do three

<The three changes that matter most, one line each, pointing at their entries below.>

## Changes

Write each change so that another session could carry it out without asking: the instruction, the exact
setting, file or command, and how to tell it worked.

### Safe to apply together

<Mechanical fixes that do not alter how work is done or checked. A numbered list.>
1. **<The change, as an instruction.>** How: <exact setting, file or command>. Why: <finding, in a line>.

### Apply one at a time, rerunning the known-answer cases after each

<Changes to role files, models, checking rules or the number of sessions, in the order to apply them.>
1. **<The change, as an instruction.>**
   Why: <the finding and its evidence, in one or two sentences>.
   How: <the exact setting, file or command>.
   You will know it worked when: <something observable>.

### Needs the owner

<Decisions and access problems. What is needed and what each would unblock.>

## What I found

<Findings ranked by how much they cost the project. For each:>
### <Finding, as a plain statement>
- Evidence: <numbers, events, files>
- Cause: <what produces it>
- Kind: <harness | access | model limit>
- Check: <the code of the check it falls under, for example A2 or F3, or "not on the list">
- Remedy: <smallest change that would work, and which group above it is in>

## Also noticed

<Smaller findings, one line each.>

## Keep

<What is working and should not be touched, with one line of evidence each.>

## Consider removing

<Parts that are not earning their cost.>

## Since the last review

<If an earlier report exists: which of its changes were made, and what the numbers show since.>

## What I could not check

<Limits of this review.>

## Numbers

<The handful of figures the findings rest on, so the next review can compare.>
```

In your reply to the owner, give the verdict, the three that matter most, how many changes are in each
group, and the path to the full report. Do not paste the whole report into the conversation. Say that a
separate session should apply the changes, and that the review can be run again afterwards.

If the honest verdict is that the harness is fine, say so in two lines and list what you checked. A review
that finds nothing wrong is a valid result; do not manufacture findings to fill the page.
