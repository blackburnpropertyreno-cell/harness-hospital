#!/usr/bin/env python3
"""install.py - install or update harness hospital (the harness kit and its skills) on this computer.

  python install.py              install or update the kit and skills (changes no settings)
  python install.py --hooks      also add the hooks to Claude Code's user settings
  python install.py --git-exclude  if your skills folder is a git repository, list the installed
                                 skills in its .git/info/exclude so git ignores them (off by default)
  python install.py --status     show what is installed
  python install.py --uninstall  remove the kit, the skills, the hooks in user settings and any lines
                                 --git-exclude added (projects are left alone)

Standard library only. The same script works on macOS, Linux and Windows.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
MARKER = ".harness-kit"


def python_path():
    exe = os.environ.get("HARNESS_PYTHON") or sys.executable
    if ("Xcode.app" in exe or "CommandLineTools" in exe) and os.path.exists("/usr/bin/python3"):
        exe = "/usr/bin/python3"
    return Path(exe).as_posix()


def q(part):
    return '"%s"' % part if " " in part else part


EXCLUDE_MARK = "# installed by the harness kit"


def remove_exclude_lines(exclude, names):
    """Take out only the block that --git-exclude added: the marker line and the skill lines right under it."""
    if not exclude.is_file():
        return
    ours = set("/%s/" % n for n in names)
    kept, in_block, changed = [], False, False
    for line in exclude.read_text(encoding="utf-8").splitlines():
        if line.strip() == EXCLUDE_MARK:
            in_block, changed = True, True
            continue
        if in_block and line.strip() in ours:
            continue
        in_block = False
        kept.append(line)
    if changed:
        with open(str(exclude), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(kept) + ("\n" if kept else ""))
        print("Removed the harness kit's lines from %s" % exclude)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hooks", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--git-exclude", action="store_true",
                    help="if the skills folder is a git repository, add the installed skills to its "
                         ".git/info/exclude (off by default)")
    ap.add_argument("--claude-dir", help="Claude Code config folder (default: ~/.claude)")
    ap.add_argument("--harness-home", help="where the kit lives (default: ~/.harness)")
    args = ap.parse_args()
    if sys.version_info < (3, 8):
        sys.exit("Python 3.8 or newer is needed; this is %s." % sys.version.split()[0])

    cdir = Path(args.claude_dir or os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    home = Path(args.harness_home or os.environ.get("HARNESS_HOME") or (Path.home() / ".harness"))
    bindir = home / "bin"
    skills_dst = cdir / "skills"
    names = sorted(p.name for p in (REPO / "skills").iterdir() if p.is_dir())
    harness_cmd = "%s %s" % (q(python_path()), q((bindir / "harness.py").as_posix()))
    hooks_cmd = "%s %s" % (q(python_path()), q((bindir / "hooks_install.py").as_posix()))
    settings = ["--settings", str(cdir / "settings.json")] if args.claude_dir else []

    if args.status:
        print("Kit:    %s  (%s)" % (bindir, "installed" if (bindir / "harness.py").exists() else "not installed"))
        for n in names:
            d = skills_dst / n
            state = "installed" if (d / MARKER).exists() else ("present but not ours" if d.exists() else "not installed")
            print("Skill:  %-16s %s" % (n, state))
        if (bindir / "hooks_install.py").exists():
            subprocess.call([sys.executable, str(bindir / "hooks_install.py"), "--check"] + settings)
        return 0

    if args.uninstall:
        if (bindir / "hooks_install.py").exists():
            subprocess.call([sys.executable, str(bindir / "hooks_install.py"), "--remove"] + settings)
        for n in names:
            d = skills_dst / n
            if (d / MARKER).exists():
                shutil.rmtree(str(d))
                print("Removed skill %s" % n)
        if bindir.exists():
            shutil.rmtree(str(bindir))
            print("Removed %s" % bindir)
        remove_exclude_lines(skills_dst / ".git" / "info" / "exclude", names)
        print("Projects and their .harness folders were left alone. The registry is still at %s." % home)
        return 0

    # 1. the kit
    home.mkdir(parents=True, exist_ok=True)
    if bindir.exists():
        shutil.rmtree(str(bindir))
    shutil.copytree(str(REPO / "kit"), str(bindir), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print("Kit installed at %s" % bindir)

    # 2. the skills, with this computer's commands filled in
    skills_dst.mkdir(parents=True, exist_ok=True)
    for n in names:
        dst = skills_dst / n
        if dst.exists() and not (dst / MARKER).exists():
            print("SKIPPED skill '%s': %s already exists and was not installed by this kit. "
                  "Rename or remove it, then run this again." % (n, dst))
            continue
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(str(REPO / "skills" / n), str(dst), ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
        (dst / MARKER).write_text("Installed by the harness kit from %s\nEdit the copy in that folder, then run "
                                  "install.py again; changes made here are overwritten.\n" % REPO, encoding="utf-8")
        for md in dst.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            new = (text.replace("{{HARNESS}}", harness_cmd).replace("{{HOOKS}}", hooks_cmd)
                   .replace("{{SKILLS}}", skills_dst.as_posix()))
            if new != text:
                with open(str(md), "w", encoding="utf-8", newline="\n") as f:
                    f.write(new)
        print("Skill installed: /%s" % n)

    # 3. only when asked: keep the installed copies out of a personal skills repository
    exclude = skills_dst / ".git" / "info" / "exclude"
    if args.git_exclude and exclude.parent.is_dir():
        have = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        add = [("/%s/" % n) for n in names if ("/%s/" % n) not in have]
        if add:
            with open(str(exclude), "a", encoding="utf-8") as f:
                f.write(("" if have.endswith("\n") or not have else "\n") + EXCLUDE_MARK + "\n" + "\n".join(add) + "\n")
            print("Your skills folder is a git repository, so these folders were added to its local exclude list "
                  "(%s) to keep them out of it: %s" % (exclude, " ".join(add)))
    elif exclude.parent.is_dir():
        print("Your skills folder is a git repository. Its exclude list was NOT changed, so git will see the "
              "installed skills as new files. Run again with --git-exclude to have git ignore them.")

    # 4. the hooks, only when asked
    if args.hooks:
        rc = subprocess.call([sys.executable, str(bindir / "hooks_install.py"), "--add"] + settings)
        if rc != 0:
            return rc
    else:
        print("\nHooks were NOT changed. The triage skill (/harness-triage) adds them, with your OK, the first time a project "
              "needs them. To add them yourself, for one project:  %s --add --project <project folder>" % hooks_cmd)
    print("\nLedger command on this computer:\n  %s" % harness_cmd)
    print("Harness hospital is installed. Start a new Claude Code session and type /harness-triage to set up a project.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
