#!/usr/bin/env python3
"""Check that every ledger subcommand named in a skill or role file really exists.

Run:  python tests/test_docs.py
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "kit"))
import harness  # noqa: E402
import hooks_install  # noqa: E402,F401


def subcommands():
    parser = harness.build_parser()
    for action in parser._actions:
        if action.dest == "cmd":
            return dict(action.choices)
    raise SystemExit("no subcommands found")


def main():
    subs = subcommands()
    problems, seen = [], set()
    files = list((REPO / "skills").rglob("*.md")) + list((REPO / "kit" / "templates").rglob("*.md")) + [REPO / "README.md"] + list((REPO / "docs").glob("*.md"))
    # `H next`, `L done --result ...`, `H --project <name> board`, and "{{HARNESS}} join ..."
    pat = re.compile(r"(?:`|\s|^)(?:[HL]|\{\{HARNESS\}\})((?:\s+--(?:project|as)\s+\S+)*)\s+([a-z][a-z-]+)((?:\s+[^`\n]*)?)", re.M)
    for f in files:
        text = f.read_text(encoding="utf-8")
        for m in pat.finditer(text):
            sub, rest = m.group(2), m.group(3) or ""
            if sub in ("means", "stands", "below", "is", "and", "or"):
                continue
            seen.add(sub)
            if sub not in subs:
                problems.append("%s: unknown subcommand '%s'" % (f.relative_to(REPO), sub))
                continue
            known = set()
            for a in subs[sub]._actions:
                known.update(a.option_strings)
            for opt in re.findall(r"(?<![\w-])--[a-z][a-z-]+", rest.split("`")[0]):
                if opt not in known and opt not in ("--project", "--as", "--help"):
                    problems.append("%s: '%s %s' is not an option of that subcommand" % (f.relative_to(REPO), sub, opt))
        for leftover in re.findall(r"\{\{[A-Z_]+\}\}", text):
            if leftover not in ("{{HARNESS}}", "{{HOOKS}}", "{{SKILLS}}"):
                problems.append("%s: unknown placeholder %s" % (f.relative_to(REPO), leftover))
        for flag in re.findall(r"\{\{HOOKS\}\}\s+(--[a-z]+)", text):
            if flag not in ("--add", "--remove", "--check", "--project"):
                problems.append("%s: hooks installer has no %s" % (f.relative_to(REPO), flag))
    # the doctor's checks name metrics fields; make sure they exist in the code
    src = (REPO / "kit" / "harness.py").read_text(encoding="utf-8")
    checks = (REPO / "skills" / "harness-doctor" / "references" / "checks.md").read_text(encoding="utf-8")
    for field in set(re.findall(r"`([a-z_]+(?:\.[a-z_*]+)+)`", checks)):
        last = field.split(".")[-1]
        if last != "*" and ('"%s"' % last) not in src:
            problems.append("checks.md names metrics field '%s' which the metrics command does not produce" % field)
    for p in problems:
        print("PROBLEM: " + p)
    print("docs check: %d subcommands referenced (%s), %d problem(s)" % (len(seen), ", ".join(sorted(seen)), len(problems)))
    never = sorted(set(subs) - seen)
    if never:
        print("subcommands never mentioned in any document: %s" % ", ".join(never))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
