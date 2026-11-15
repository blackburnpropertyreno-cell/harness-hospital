#!/usr/bin/env python3
"""Test the hook script by feeding it the JSON Claude Code would send.

Run:  python tests/test_hooks.py
Uses a temporary HARNESS_HOME; never touches real projects or settings.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "kit"
CLI, HOOK = str(KIT / "harness.py"), str(KIT / "hook.py")
PASSED = []


def env_for(sid=None):
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    env["HARNESS_HOME"] = HOME
    env["HARNESS_MACHINE"] = "machine-a"
    if sid:
        env["HARNESS_SESSION_ID"] = sid
    return env


def cli(args, sid=None, expect=0):
    p = subprocess.run([sys.executable, CLI] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env_for(sid))
    out = p.stdout.decode("utf-8", "replace")
    if expect is not None and p.returncode != expect:
        raise AssertionError("exit %s for %s\n%s" % (p.returncode, args, out))
    return out


def hook(event, sid, raw=None, **fields):
    payload = dict(hook_event_name=event, session_id=sid, cwd=fields.pop("cwd", str(PROJ)), **fields)
    data = raw if raw is not None else json.dumps(payload)
    env = env_for()
    env["PYTHONIOENCODING"] = "cp1252"      # mimic a Windows console code page
    payload_bytes = json.dumps(json.loads(data), ensure_ascii=False).encode("utf-8") if raw is None else data.encode("utf-8")
    p = subprocess.run([sys.executable, HOOK], input=payload_bytes, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env)
    if p.returncode != 0:
        raise AssertionError("hook exited %s: %s" % (p.returncode, p.stderr.decode()))
    out = p.stdout.decode("utf-8").strip()
    return json.loads(out) if out else None


def pre(sid, tool, **tool_input):
    r = hook("PreToolUse", sid, tool_name=tool, tool_input=tool_input)
    if r and r["hookSpecificOutput"].get("permissionDecision") == "deny":
        return r["hookSpecificOutput"]["permissionDecisionReason"]
    return None


def ok(name, cond, detail=""):
    if not cond:
        raise AssertionError("FAILED: %s\n%s" % (name, detail))
    PASSED.append(name)


def main():
    global HOME, PROJ
    tmp = Path(tempfile.mkdtemp(prefix="harness-hook-test-"))
    HOME = str(tmp / "home")
    PROJ = tmp / "proj dir"
    PROJ.mkdir(parents=True)
    (PROJ / "data.db").write_text("x", encoding="utf-8")
    try:
        cli(["init", "demo", "--path", str(PROJ)])
        cfgp = PROJ / ".harness" / "config.json"
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        cfg["protected_paths"] = ["data.db", "shared/**"]
        cfg["blocked_hosts"] = [{"host": "blocked.example", "reason": "The site forbids automated fetching."}]
        cfg["bash_deny"] = [{"pattern": r"\bgit\s+push\b", "reason": "Workers do not push."}]
        cfgp.write_text(json.dumps(cfg), encoding="utf-8")

        # sessions that never joined are untouched
        ok("unregistered session: no output", hook("PreToolUse", "nobody", tool_name="Write",
                                                 tool_input={"file_path": str(PROJ / "data.db")}) is None)
        ok("unregistered stop: no output", hook("Stop", "nobody") is None)
        ok("malformed input: silent", hook("Stop", "x", raw="not json {") is None)
        ok("empty input: silent", hook("Stop", "x", raw="") is None)
        ok("session start elsewhere: silent", hook("SessionStart", "elsewhere", cwd=str(tmp), source="startup") is None)

        # auto-join when a session starts inside the project folder
        r = hook("SessionStart", "sid-a", source="startup", cwd=str(PROJ / ".harness"))
        text = r["hookSpecificOutput"]["additionalContext"]
        ok("auto-join as worker", "registered automatically as w1 (worker)" in text, text)
        ok("auto-join explains guest", "--role guest" in text)

        # provisional worker (never held a task)
        cli(["--project", "demo", "add", "First task"])
        cli(["--project", "demo", "add", "Second task"])
        ok("provisional worker is not handed a task at stop", hook("Stop", "sid-a") is None)
        d = pre("sid-a", "Write", file_path=str(PROJ / "notes.md"), content="x")
        ok("worker without a task cannot write in the project", d and "run 'next' first" in d and "--role guest" in d, d)
        ok("temp files are allowed", pre("sid-a", "Write", file_path=os.path.join(tempfile.gettempdir(), "x.txt")) is None)

        # a working worker
        out = cli(["next"], sid="sid-a")
        ok("worker takes T1", out.startswith("T1"), out)
        ok("write in own task folder", pre("sid-a", "Write", file_path=str(PROJ / ".harness/work/T1/a.md")) is None)
        ok("relative path resolves against the session folder",
           pre("sid-a", "Edit", file_path="work/T1/b.md") is None)
        d = pre("sid-a", "Write", file_path=str(PROJ / ".harness/work/T2/a.md"))
        ok("not in another task's folder", d and "may write only in" in d, d)
        d = pre("sid-a", "Edit", file_path=str(PROJ / "data.db"))
        ok("protected data", d and "protected project data" in d, d)
        d = pre("sid-a", "Write", file_path=str(PROJ / "shared" / "x" / "y.md"))
        ok("protected folder", d and "protected project data" in d, d)
        d = pre("sid-a", "Edit", file_path=str(PROJ / ".harness/config.json"))
        ok("rules file", d and "belongs to the harness" in d, d)
        d = pre("sid-a", "Write", file_path=str(PROJ / ".harness/STATUS.md"))
        ok("status file", d and "regenerated" in d, d)
        d = pre("sid-a", "Write", file_path=str(Path.home() / "somewhere-else.txt"))
        ok("outside the project", d and "outside project" in d, d)

        # shell patterns
        d = pre("sid-a", "Bash", command='sqlite3 ".harness/ledger.sqlite" "select 1"')
        ok("ledger not touched directly", d and "only through the ledger command" in d, d)
        ok("ledger command itself is fine", pre("sid-a", "Bash", command='"py" "/x/.harness/bin/harness.py" --as w1 board') is None)
        d = pre("sid-a", "Bash", command='sqlite3 data.db "update t set a=1"')
        ok("sqlite write to protected data", d and "protected project data" in d, d)
        ok("sqlite read-only is fine", pre("sid-a", "Bash", command='sqlite3 -readonly data.db "select 1"') is None)
        ok("reading is fine", pre("sid-a", "Bash", command="cat data.db | head") is None)
        ok("python reading is fine", pre("sid-a", "Bash", command="python3 analyse.py data.db") is None)
        d = pre("sid-a", "Bash", command="echo x > data.db")
        ok("redirect into protected data", d and "protected" in d, d)
        d = pre("sid-a", "Bash", command="rm -f data.db")
        ok("rm protected data", d and "protected" in d, d)
        d = pre("sid-a", "Bash", command="curl -s https://blocked.example/img/1.jpg -o x.jpg")
        ok("blocked host in shell", d and "blocked.example" in d and "forbids" in d, d)
        ok("naming a blocked site in a search or a note is fine",
           pre("sid-a", "Bash", command="grep -n blocked.example .harness/work/T1/notes.md") is None
           and pre("sid-a", "WebSearch", query="blocked.example annual report") is None
           and pre("sid-a", "Bash", command='py /x/.harness/bin/harness.py --as w1 ask "may I use blocked.example?"') is None)
        ok("a longer word that contains a protected name is not protected",
           pre("sid-a", "Bash", command="mv a.pdf .harness/work/T1/unshared-plan.pdf") is None
           and pre("sid-a", "Bash", command="rm /tmp/my-data.db.bak2") is None)
        ok("copying out of a protected folder is reading",
           pre("sid-a", "Bash", command="cp shared/a.txt .harness/work/T1/") is None)
        d = pre("sid-a", "Bash", command="cp .harness/work/T1/a.txt shared/")
        ok("copying into a protected folder is refused", d and "protected" in d, d)
        d = pre("sid-a", "Bash", command="cd /tmp && mv x shared/y")
        ok("protected check looks at each part of a chained command", d and "protected" in d, d)
        d = pre("sid-a", "Read", file_path=str(PROJ / ".harness/cases/secret/case.md"))
        ok("workers cannot read known-answer cases", d and "held back" in d, d)
        d = pre("sid-a", "Bash", command="cat .harness/cases/secret/case.md")
        ok("nor through the shell", d and "held back" in d, d)
        d = pre("sid-a", "Bash", command='py /x/.harness/bin/harness.py --as w1 checkpoint "x" && cp a.txt shared/')
        ok("chaining after the ledger command does not skip the checks", d and "protected" in d, d)
        d = pre("sid-a", "Write", file_path=str(PROJ / "data.db"), content="He said \u201cno\u201d \u2014 caf\u00e9")
        ok("non-ASCII content does not defeat the hook", d and "protected" in d, d)
        d = pre("sid-a", "Bash", command="git push origin main")
        ok("project shell rule", d == "Workers do not push.", d)
        d = pre("sid-a", "WebFetch", url="https://blocked.example/page", prompt="x")
        ok("blocked host in fetch", d and "blocked.example" in d, d)
        ok("other hosts fine", pre("sid-a", "WebFetch", url="https://ok.example/page", prompt="x") is None)
        d = pre("sid-a", "mcp__browser__navigate", url="https://sub.blocked.example/")
        ok("blocked host in browser tool", d and "blocked.example" in d, d)
        ok("reading tools untouched", pre("sid-a", "Read", file_path=str(PROJ / "data.db")) is None)

        # messaging
        d = pre("sid-a", "SendMessage", to="w2", message="what is your status?")
        ok("workers do not message", d and "request ROLE" in d, d)
        cli(["join", "demo", "--role", "coordinator"], sid="sid-c")
        ok("coordinator wake-up allowed", pre("sid-c", "mcp__x__send_message", message="New assignment: run next.") is None)
        d = pre("sid-c", "SendMessage", message="Please do the following long thing " * 20)
        ok("coordinator content message refused", d and "wake-ups only" in d, d)
        d = pre("sid-c", "Write", file_path=str(PROJ / ".harness/work/T1/a.md"))
        ok("coordinator does not cook", d and "may write only" in d, d)
        ok("coordinator notes allowed", pre("sid-c", "Write", file_path=str(PROJ / ".harness/notes/plan.md")) is None)

        # stop rules
        r = hook("Stop", "sid-a")
        ok("stop refused while task unfinished", r and r["decision"] == "block" and "T1" in r["reason"], r)
        ok("second stop in a row is allowed", hook("Stop", "sid-a") is None)
        hook("PostToolUse", "sid-a", tool_name="Bash", tool_input={})
        r = hook("Stop", "sid-a", stop_hook_active=True)
        ok("after more work, stop is refused again even if another hook already continued the turn",
           r and r["decision"] == "block", r)
        hook("PostToolUse", "sid-a", tool_name="Bash", tool_input={})
        (PROJ / ".harness/work/T1/a.md").write_text("r", encoding="utf-8")
        cli(["done", "--result", ".harness/work/T1/a.md", "--summary", "did it"], sid="sid-a")
        r = hook("Stop", "sid-a")
        ok("finished worker is handed the next task at stop", r and "T2" in r["reason"] and "show T2" in r["reason"], r)
        ok("handed-out task is claimed", "[in_progress]" in cli(["show", "T2"], sid="sid-a"))
        hook("PostToolUse", "sid-a", tool_name="Bash", tool_input={})
        cli(["block", "--reason", "source offline"], sid="sid-a")
        ok("blocked worker with empty queue may stop", hook("Stop", "sid-a") is None)

        # coordinator stop: an idle worker and nothing queued -> gap
        r = hook("Stop", "sid-c")
        ok("coordinator stop refused while a worker sits idle", r and r["decision"] == "block" and "w1" in r["reason"], r)
        ok("coordinator second stop allowed", hook("Stop", "sid-c") is None)

        # reviewer
        cli(["join", "demo", "--role", "reviewer"], sid="sid-r")
        r = hook("Stop", "sid-r")
        ok("reviewer is handed the unverified result", r and "T1" in r["reason"] and "review" in r["reason"], r)
        hook("PostToolUse", "sid-r", tool_name="Read", tool_input={})
        r = hook("Stop", "sid-r")
        ok("reviewer cannot stop mid-review", r and "verify T1" in r["reason"], r)
        ok("reviewer writes review notes", pre("sid-r", "Write", file_path=str(PROJ / ".harness/work/T1/review/n.md")) is None)
        d = pre("sid-r", "Edit", file_path=str(PROJ / ".harness/work/T1/a.md"))
        ok("reviewer cannot edit the result", d and "may write only" in d, d)
        cli(["verify", "T1", "--pass", "--note", "fine"], sid="sid-r")

        # a specialty entry that sets only a cap must not take away the worker's task folder
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        cfg["roles"]["librarian"] = {"max_sessions": 1}
        cfgp.write_text(json.dumps(cfg), encoding="utf-8")
        hook("SessionStart", "sid-lib", source="startup")
        cli(["join", "demo", "--role", "worker", "--specialty", "librarian"], sid="sid-lib")
        cli(["--project", "demo", "add", "Look something up", "--role", "librarian"])
        lt = cli(["next"], sid="sid-lib").split()[0]
        ok("a specialist keeps the worker's write limits when its entry sets only a cap",
           pre("sid-lib", "Write", file_path=str(PROJ / (".harness/work/%s/answer.md" % lt))) is None)
        hook("SessionStart", "sid-lib2", source="startup")
        out = cli(["join", "demo", "--role", "worker", "--specialty", "librarian"], sid="sid-lib2", expect=1)
        ok("the cap holds for a session that was auto-registered in the project folder", "at most 1 session" in out, out)
        cli(["leave"], sid="sid-lib"); cli(["leave"], sid="sid-lib2")
        cli(["--project", "demo", "cancel", lt, "--reason", "test only"])

        # guest = the owner's own session
        hook("SessionStart", "sid-g", source="startup")
        cli(["join", "demo", "--role", "guest"], sid="sid-g")
        ok("guest writes project files", pre("sid-g", "Write", file_path=str(PROJ / "README.md")) is None)
        ok("guest edits rules", pre("sid-g", "Edit", file_path=str(PROJ / ".harness/config.json")) is None)
        d = pre("sid-g", "Edit", file_path=str(PROJ / "data.db"))
        ok("guest still cannot overwrite protected data", d and "protected" in d, d)
        d = pre("sid-g", "Write", file_path=str(PROJ / ".harness/ledger.sqlite"))
        ok("nobody edits the ledger file", d and "belongs to the harness" in d, d)

        # session close and resume
        cli(["requeue", "T2", "--reason", "retry"], sid="sid-c")
        cli(["next"], sid="sid-a")
        hook("SessionEnd", "sid-a", reason="other")
        ok("closed session with a task shows as stuck", "STALE" in cli(["board"], sid="sid-c"), cli(["board"], sid="sid-c"))
        r = hook("SessionStart", "sid-a", source="resume")
        ok("resumed session is told who it is", "You are w1" in r["hookSpecificOutput"]["additionalContext"]
           and "show T2" in r["hookSpecificOutput"]["additionalContext"], r)
        r = hook("SessionStart", "sid-a", source="compact")
        ok("identity survives compaction", "You are w1" in r["hookSpecificOutput"]["additionalContext"])
        hook("SessionEnd", "sid-a", reason="clear")
        ok("cleared session's task returns to the queue", "[queued]" in cli(["--project", "demo", "show", "T2"]))

        # drain
        hook("SessionStart", "sid-d", source="startup")
        cli(["next"], sid="sid-d")
        cli(["--project", "demo", "drain"])
        r = hook("PostToolUse", "sid-d", tool_name="Bash", tool_input={})
        ok("busy session is told about the handoff after its next tool call",
           r and "another computer" in r["hookSpecificOutput"]["additionalContext"], r)
        ok("told only once", hook("PostToolUse", "sid-d", tool_name="Bash", tool_input={}) is None)
        r = hook("Stop", "sid-d")
        ok("draining: stop refused until a checkpoint exists", r and "checkpoint" in r["reason"], r)
        hook("PostToolUse", "sid-d", tool_name="Bash", tool_input={})
        cli(["checkpoint", "half done; see notes.md"], sid="sid-d")
        ok("draining: stop allowed after checkpoint", hook("Stop", "sid-d") is None)
        cli(["--project", "demo", "stamp"])
        d = pre("sid-d", "Write", file_path=str(PROJ / ".harness/work/T2/late.md"))
        ok("parked: writes refused", d and "parked" in d, d)
        r = hook("SessionStart", "sid-new", source="startup")
        ok("parked: a new session is told", "PARKED" in r["hookSpecificOutput"]["additionalContext"], r)
        cli(["--project", "demo", "resume", "--no-pull"])

        m = json.loads(cli(["--project", "demo", "metrics"]))
        ok("denials are counted by rule", m["hook_denials"]["total"] >= 15 and "write:protected" in m["hook_denials"]["by_rule"],
           json.dumps(m["hook_denials"]))
        ok("denials record what was refused", any("data.db" in r for r in m["hook_denials"]["recent"])
           or any("write:protected |" in l for l in cli(["--project", "demo", "log", "--kind", "deny", "-n", "60"]).splitlines()),
           json.dumps(m["hook_denials"]["recent"]))
        ok("no hook errors were logged", not (Path(HOME) / "hook-errors.log").exists(),
           (Path(HOME) / "hook-errors.log").read_text() if (Path(HOME) / "hook-errors.log").exists() else "")

        # eight sessions at once: each must get a different task, none lost
        for i in range(8):
            cli(["--project", "demo", "add", "Parallel %d" % i])
        sids = ["par-%d" % i for i in range(8)]
        for s in sids:
            hook("SessionStart", s, source="startup")
        with ThreadPoolExecutor(8) as ex:
            outs = list(ex.map(lambda s: cli(["next"], sid=s), sids))
        got = sorted(o.split()[0] for o in outs)
        ok("eight sessions claim eight different tasks", len(set(got)) == 8 and all(g.startswith("T") for g in got), got)

        def burst(s):
            for _ in range(5):
                hook("PreToolUse", s, tool_name="Bash", tool_input={"command": "ls"})
                hook("PostToolUse", s, tool_name="Bash", tool_input={})
            return True
        with ThreadPoolExecutor(8) as ex:
            ok("eighty hook calls from eight sessions at once", all(ex.map(burst, sids)))
        ok("still no hook errors", not (Path(HOME) / "hook-errors.log").exists(),
           (Path(HOME) / "hook-errors.log").read_text() if (Path(HOME) / "hook-errors.log").exists() else "")
        ok("snapshots are being taken", len(list((PROJ / ".harness/snapshots").glob("*.sqlite"))) >= 1)

        # fail open: a broken ledger must not block anything
        (PROJ / ".harness/ledger.sqlite").write_bytes(b"this is not a database")
        for side in ("-wal", "-shm"):
            sp = Path(str(PROJ / ".harness/ledger.sqlite") + side)
            if sp.exists():
                sp.unlink()
        ok("broken ledger: tool call still allowed", pre("par-0", "Write", file_path=str(PROJ / "data.db")) is None)
        ok("broken ledger: stop still allowed", hook("Stop", "par-0") is None)
        ok("the failure was logged", (Path(HOME) / "hook-errors.log").exists())

        print("hook tests passed: %d" % len(PASSED))
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


if __name__ == "__main__":
    main()
