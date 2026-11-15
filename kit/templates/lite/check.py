#!/usr/bin/env python3
"""check.py - the project's checker. Replace the body of check() with real tests.

A result counts as verified only when this script exits 0 for it, or when someone
other than its author has reviewed it. Run:  python .harness/check.py <result file>
"""
import sys
from pathlib import Path


def check(path):
    """Return a list of problems; an empty list means the result passes."""
    problems = []
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        problems.append("the result file is empty")
    # Add the facts a script can test here: required sections, sources that must be cited,
    # numbers that must add up, files that must exist.
    return problems


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: check.py <result file>")
    found = check(sys.argv[1])
    for p in found:
        print("FAIL: " + p)
    print("passed" if not found else "%d problem(s)" % len(found))
    sys.exit(1 if found else 0)
