#!/usr/bin/env python3
"""hook.py - one entry point for every Claude Code hook event.

Installed by hooks_install.py, usually in one project's .claude/settings.local.json
(so it runs only for sessions started in that folder), or in the user settings (so it
runs for every session on this computer). For a session that has not joined a harness
it exits at once and changes nothing.
It fails open: on any error it lets the tool call or the stop go ahead and
writes one line to ~/.harness/hook-errors.log.
"""
import json
import os
import re
import sys
import traceback
from pathlib import Path

WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
READ_TOOLS = ("Read", "Grep", "Glob")
MESSAGE_RE = re.compile(r"(?i)send_?message")
URL_TOOL_RE = re.compile(r"(?i)(fetch|navigate|browser|web|download|open_url|preview_start)")


def harness_home():
    return Path(os.environ.get("HARNESS_HOME") or (Path.home() / ".harness"))


def emit(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def context(event, text):
    emit({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def deny(reason):
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": reason}})


def log_error(exc_text):
    try:
        path = harness_home() / "hook-errors.log"
        if path.exists() and path.stat().st_size > 200000:
            path.unlink()
        with open(str(path), "a", encoding="utf-8") as f:
            f.write(exc_text.rstrip() + "\n---\n")
    except OSError:
        pass


def run(data):
    event = data.get("hook_event_name") or ""
    sid = data.get("session_id") or ""
    if not sid or os.environ.get("HARNESS_HOOKS_OFF"):
        return
    try:
        with open(str(harness_home() / "sessions.json"), "r", encoding="utf-8-sig") as f:
            index = json.load(f)
    except (OSError, ValueError):
        index = {}
    entry = index.get(sid)
    if not entry and event != "SessionStart":
        return                                            # not a harness session: do nothing

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import harness as H

    if not entry:                                         # SessionStart of an unregistered session
        cwd = data.get("cwd") or os.getcwd()
        project = H.project_by_cwd(cwd)
        if not project:
            return
        root = H.project_root(project)
        if not H.ledger_path(root).exists():
            return
        cfg = H.load_config(root)
        mode = cfg.get("auto_join", "worker")
        cmd = H.this_command()
        if H.parked_info(root):
            context(event, "This folder is project '%s', which runs under a harness and is PARKED on this computer "
                           "(it was handed off to another one). Nothing here may be changed until the owner runs: "
                           "%s --project %s resume" % (project, cmd, project))
            return
        if mode not in ("worker", "guest"):
            return
        con = H.connect(root)
        sess = H.do_join(root, con, cfg, sid, mode, cwd=cwd)
        H.render(root, con, cfg, min_interval=5)
        text = ("This folder is project '%s', which runs under a multi-session harness. This session was registered "
                "automatically as %s (%s). Ledger command: %s --as %s\n" % (project, sess["name"], mode, cmd, sess["name"]))
        if mode == "worker":
            text += ("If you are here to do project work, run the ledger command with 'whoami --full' to read your "
                     "role, then 'next' for a task. If the owner opened this session to coordinate or review, run "
                     "'join %s --role coordinator' or '--role reviewer'. If it is for something else (a question, "
                     "maintenance, a review of the harness), run 'join %s --role guest': until then, file writes "
                     "outside a task folder are refused." % (project, project))
        else:
            text += ("To work in the harness run 'join %s --role worker' (or coordinator, reviewer). Protected project "
                     "data cannot be changed directly from any session." % project)
        context(event, text)
        return

    root = Path(entry.get("root") or "")
    if not H.ledger_path(root).exists():
        return
    cfg = H.load_config(root)
    con = H.connect(root)
    sess = H.get_session(con, entry.get("name"))
    if sess is None or sess["state"] == "ended":
        return
    name = sess["name"]
    parked = H.parked_info(root)
    cmd = "%s --as %s" % (H.this_command(), name)

    if event == "SessionStart":
        if not parked:
            con.execute("UPDATE sessions SET state='active', last_heartbeat=? WHERE name=?", (H.now(), name))
        cur = sess["current_task"]
        context(event, "You are %s (%s) in harness project '%s'. Ledger command: %s\nRun 'whoami --full' to re-read "
                       "your role instructions%s. Do not rely on memory of earlier assignments: the ledger is the record."
                % (name, sess["specialty"] or sess["role"], cfg.get("project"), cmd,
                   ", and 'show %s' for your current task and its checkpoints" % cur if cur else ""))
        return

    if event == "PreToolUse":
        tool = data.get("tool_name") or ""
        tin = data.get("tool_input") or {}
        ok, reason, rule, target = True, "", "", ""
        if tool in WRITE_TOOLS:
            target = tin.get("file_path") or tin.get("notebook_path") or tin.get("path") or ""
            if target:
                if parked and H.is_inside(H.resolve_path(sess["cwd"] or root, target), root):
                    ok, reason, rule = False, ("Project '%s' is parked on this computer after a handoff. Nothing here "
                                               "may be changed until the owner runs 'resume'." % cfg.get("project")), "parked"
                else:
                    ok, reason, rule = H.write_allowed(root, cfg, sess, target)
        elif tool in READ_TOOLS and sess["role"] == "worker":
            target = str(tin.get("file_path") or tin.get("path") or "")
            if target and H.is_inside(H.resolve_path(sess["cwd"] or root, target), H.hdir(root) / "cases"):
                ok, rule = False, "read:cases"
                reason = ("Known-answer cases are held back from workers so that they stay a fair test. "
                          "Work from your task's detail.")
        elif tool in SHELL_TOOLS:
            target = tin.get("command") or ""
            ok, reason, rule = H.bash_allowed(root, cfg, sess, target)
        elif MESSAGE_RE.search(tool):
            ok, reason = H.message_allowed(cfg, sess, tin)
            rule = "message"
        elif URL_TOOL_RE.search(tool) or "url" in tin:
            target = str(tin.get("url") or "")
            ok, reason = H.url_allowed(cfg, tin)
            rule = "blocked-host"
        if not ok:
            if not parked:
                with H.tx(con):
                    H.event(con, "deny", name, sess["current_task"],
                            rule + (" | " + " ".join(str(target).split())[:200] if target else ""))
            deny(reason)
            return
        if not parked:
            H.heartbeat(root, con, cfg, name, "pre", tool)
        return

    if event == "PostToolUse":
        if parked:
            return
        H.heartbeat(root, con, cfg, name, "post")
        drain = H.meta_get(con, "drain")
        if drain and sess["current_task"] and sess["role"] != "coordinator":
            task = con.execute("SELECT state FROM tasks WHERE id=?", (sess["current_task"],)).fetchone()
            told = con.execute("SELECT 1 FROM events WHERE kind='drain_notice' AND session=? AND ts>=? LIMIT 1",
                               (name, drain)).fetchone()
            if task and task["state"] == "in_progress" and not told:
                with H.tx(con):
                    H.event(con, "drain_notice", name, sess["current_task"], "")
                context(event, "NOTICE FROM THE HARNESS: the owner is moving this project to another computer. Finish "
                               "the step you are on, save your files in your task folder, then record exactly where "
                               "you are and stop:\n  %s checkpoint \"what is finished, what is next, where the files "
                               "are\"\nDo not start anything new." % cmd)
        return

    if event == "Stop":
        allow, message = H.stop_decision(root, con, cfg, sess)
        if not allow:
            emit({"decision": "block", "reason": message})
        try:
            H.render(root, con, cfg, min_interval=5)
        except Exception:
            pass
        return

    if event == "SessionEnd":
        if parked:
            return
        reason = data.get("reason") or ""
        with H.tx(con):
            if reason == "clear":
                cur = sess["current_task"]
                if cur:
                    t = con.execute("SELECT state FROM tasks WHERE id=?", (cur,)).fetchone()
                    if t and t["state"] == "in_progress":
                        H.set_task(con, cur, state="queued")
                        H.event(con, "requeued", name, cur, "session was cleared")
                H.set_session(con, name, state="ended", current_task=None, stop_reason="cleared")
            else:
                H.set_session(con, name, state="closed", stop_reason=sess["stop_reason"] or "window closed")
            H.event(con, "session_end", name, None, reason)
        return


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")     # Windows consoles default to a legacy code page
        try:
            data = json.loads(raw) if raw.strip() else {}
        except ValueError:
            return 0
        if isinstance(data, dict):
            run(data)
    except BaseException as exc:                          # fail open, always
        if isinstance(exc, SystemExit):
            return 0
        log_error(traceback.format_exc())
    return 0


if __name__ == "__main__":
    sys.exit(main())
