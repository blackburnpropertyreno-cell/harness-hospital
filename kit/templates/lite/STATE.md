# Project state

This file is the single record of where the project stands. Every session reads it first and updates it
before stopping. If something is not written here, it did not happen.

Last updated: <date and time> by <session>

## Goal

<One or two sentences. What done looks like.>

## Tasks

| # | Task | State | Who | Result (path) | Note |
|---|---|---|---|---|---|
| 1 |  | queued |  |  |  |

States: queued, in progress, blocked, needs owner, done, verified.
A task is **done** when its result is on disk. It is **verified** only after `check.py` passes or someone
other than its author has checked it.

## Decisions waiting for the owner

- (none)

## Decisions made

- <date>: <decision and reason>

## Known-answer cases

Cases with a known correct result, rerun after any change to how the work is done:

| Case | Expected | Last run | Result |
|---|---|---|---|
|  |  |  |  |
