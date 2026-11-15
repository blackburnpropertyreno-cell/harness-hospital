#!/usr/bin/env python3
"""hooks_install.py - add or remove the harness hooks in a Claude Code settings file.

  --add      add the hook groups (backs the file up first; safe to run twice)
  --remove   take them out again
  --check    say whether they are present

  --project FOLDER   use that project's local settings (FOLDER/.claude/settings.local.json), so the
                     hooks run only for sessions started inside the project folder. This is the
                     usual choice.
  (neither)          use the user settings, so the hooks run for every session on this computer and
                     a session can join a project from any folder.

Other hooks already in the file are left exactly as they are.
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

EVENTS = [("SessionStart", 20), ("PreToolUse", 15), ("PostToolUse", 30), ("Stop", 20), ("SessionEnd", 5)]


def python_path():
    exe = os.environ.get("HARNESS_PYTHON") or sys.executable
    if ("Xcode.app" in exe or "CommandLineTools" in exe) and os.path.exists("/usr/bin/python3"):
        exe = "/usr/bin/python3"
    return Path(exe).as_posix()


def hook_path():
    return (Path(__file__).resolve().parent / "hook.py").as_posix()


def is_ours(hook):
    blob = json.dumps(hook).replace("\\\\", "/")
    return hook_path() in blob or "/.harness/bin/hook.py" in blob


def make_hook(timeout, form):
    if form == "exec":
        return {"type": "command", "command": python_path(), "args": [hook_path()], "timeout": timeout}
    return {"type": "command", "command": '"%s" "%s"' % (python_path(), hook_path()), "timeout": timeout}


def strip_ours(settings):
    changed = False
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept = []
        for g in groups:
            inner = g.get("hooks") if isinstance(g, dict) else None
            if isinstance(inner, list) and any(is_ours(h) for h in inner):
                rest = [h for h in inner if not is_ours(h)]
                changed = True
                if rest:
                    g = dict(g, hooks=rest)
                    kept.append(g)
            else:
                kept.append(g)
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
            changed = True
    if not hooks:
        del settings["hooks"]
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--add", action="store_true")
    g.add_argument("--remove", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--project", metavar="FOLDER", help="install for this project folder only")
    ap.add_argument("--settings", help="a settings file to change, given exactly (mainly for testing)")
    ap.add_argument("--form", choices=["auto", "shell", "exec"], default="auto",
                    help="how the hook is launched; auto = exec on Windows, shell elsewhere")
    args = ap.parse_args()
    cdir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    if args.settings:
        path = Path(args.settings)
    elif args.project:
        proj = Path(args.project).expanduser().resolve()
        if not proj.is_dir():
            print("Project folder not found: %s. Nothing was changed." % proj)
            return 1
        path = proj / ".claude" / "settings.local.json"
    else:
        path = cdir / "settings.json"
    form = args.form if args.form != "auto" else ("exec" if os.name == "nt" else "shell")

    original = ""
    settings = {}
    if path.exists():
        original = path.read_text(encoding="utf-8-sig")
        try:
            settings = json.loads(original) if original.strip() else {}
        except ValueError as exc:
            print("Cannot read %s as JSON (%s). Nothing was changed; fix the file first." % (path, exc))
            return 1
        if not isinstance(settings, dict):
            print("%s is not a JSON object. Nothing was changed." % path)
            return 1

    present = []
    for event, groups in (settings.get("hooks") or {}).items():
        for grp in groups if isinstance(groups, list) else []:
            if isinstance(grp, dict) and any(is_ours(h) for h in grp.get("hooks") or []):
                present.append(event)
    if args.check:
        missing = [e for e, _ in EVENTS if e not in present]
        print("Settings file: %s" % path)
        print("Harness hooks present for: %s" % (", ".join(present) or "none"))
        if missing:
            print("Missing: %s" % ", ".join(missing))
        return 0 if not missing else 1

    strip_ours(settings)
    if args.add:
        if not Path(hook_path()).exists():
            print("hook.py not found next to this script (%s). Nothing was changed." % hook_path())
            return 1
        hooks = settings.setdefault("hooks", {})
        for event, timeout in EVENTS:
            hooks.setdefault(event, []).append({"hooks": [make_hook(timeout, form)]})
    new_text = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
    if original and json.loads(original) == settings:
        print("No change needed: %s already %s the harness hooks." % (path, "has" if args.add else "lacks"))
        return 0
    if path.exists():
        backup = path.with_name(path.name + ".harness-backup-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        shutil.copyfile(str(path), str(backup))
        print("Backup of the previous settings: %s" % backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    os.replace(str(tmp), str(path))
    if args.add:
        print("Added harness hooks (%s form) for: %s" % (form, ", ".join(e for e, _ in EVENTS)))
        print("Settings file: %s" % path)
        if args.project:
            print("They run only for sessions started inside %s." % Path(args.project).expanduser().resolve())
            print("A session started elsewhere can join the project's ledger, but none of the rules apply to it.")
            exclude = Path(args.project).expanduser().resolve() / ".git" / "info" / "exclude"
            if exclude.parent.is_dir():
                have = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
                if ".claude/settings.local.json" not in have:
                    with open(str(exclude), "a", encoding="utf-8") as f:
                        f.write(("" if have.endswith("\n") or not have else "\n") + ".claude/settings.local.json\n")
                    print("This file holds paths for this computer only, so it was added to the repository's local "
                          "exclude list (%s). Each computer installs its own." % exclude)
        else:
            print("They run for every session on this computer and do nothing for sessions outside a harness.")
        print("Sessions that are already open pick them up only after a restart.")
    else:
        print("Removed the harness hooks from %s." % path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
