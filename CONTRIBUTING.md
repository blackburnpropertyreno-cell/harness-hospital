# Contributing

Thank you for trying harness hospital. It is early, so reports of what happened when you used it are the
most useful contribution of all.

## Reporting a problem

Open an issue on GitHub and include:

- What you were doing, and which skill or command you used.
- What you expected, and what happened instead. Paste the exact error text if there was one.
- Your operating system, your Python version (`python3 --version`), and your Claude Code version
  (`claude --version`).
- The output of `python3 install.py --status`.
- If the hooks seemed not to work: the last few entries of `~/.harness/hook-errors.log`.

Before pasting anything, remove passwords, keys, personal paths and anything from your project you would
not want public.

For a security problem, please do not open a public issue. See [SECURITY.md](SECURITY.md).

## Running the tests

From the repository folder:

```bash
python3 tests/test_ledger.py
python3 tests/test_hooks.py
python3 tests/test_docs.py
```

Each prints its checks and ends with a count. They use temporary folders and never touch your real projects
or settings. `test_docs.py` checks that every ledger command and option named in the skills and docs really
exists, so run it after editing any document.

## Making a change

- Keep the kit to Python's standard library, so it installs anywhere with nothing else.
- Keep it working on macOS, Linux and Windows: use `pathlib`, avoid shell-specific commands.
- Write documents in plain English: short sentences, and define a term the first time it is used.
- Add or update a test for any change in behaviour, and make sure all three test scripts pass.
- Prefer a small change with a clear reason. The project's own principle applies: add a part only when
  something shows it is needed.
