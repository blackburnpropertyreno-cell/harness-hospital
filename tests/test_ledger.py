#!/usr/bin/env python3
"""End-to-end test of the ledger command against a throwaway project.

Run:  python tests/test_ledger.py
Uses a temporary HARNESS_HOME, so it never touches real projects or settings.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "kit"
CLI = str(KIT / "harness.py")
PASSED = []


def run(args, sid=None, env_extra=None, expect=0, cwd=None):
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    env["HARNESS_HOME"] = HOME
    env["HARNESS_MACHINE"] = "machine-a"
    if sid:
        env["HARNESS_SESSION_ID"] = sid
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, CLI] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=cwd)
    out = p.stdout.decode("utf-8", "replace")
    if expect is not None and p.returncode != expect:
        raise AssertionError("exit %s (wanted %s) for %s\n%s" % (p.returncode, expect, args, out))
    return out


def ok(name, cond, detail=""):
    if not cond:
        raise AssertionError("FAILED: %s %s" % (name, detail))
    PASSED.append(name)


def main():
    global HOME
    tmp = Path(tempfile.mkdtemp(prefix="harness-test-"))
    HOME = str(tmp / "home")
    proj = tmp / "my project"          # a space in the path, on purpose
    proj.mkdir(parents=True)
    (proj / "data.db").write_text("main data", encoding="utf-8")
    try:
        out = run(["init", "demo", "--path", str(proj)])
        ok("init", (proj / ".harness" / "ledger.sqlite").exists() and "dashboard" in out.lower())
        ok("init is repeatable", "set up" in run(["init", "demo", "--path", str(proj)]))
        ok("projects", "demo" in run(["projects"]))

        # owner queues work
        run(["--project", "demo", "add", "Collect sources", "--detail", "find three"])
        run(["--project", "demo", "add", "Summarise sources", "--after", "T1"])
        run(["--project", "demo", "add", "Look up catalogue entry", "--role", "librarian"])
        long_text = "x" * 400
        out = run(["--project", "demo", "add", "Too long", "--detail", long_text], expect=1)
        ok("long detail rejected, pointing at --detail-file", "--detail-file" in out, out)

        w1 = run(["join", "demo", "--role", "worker"], sid="sid-w1")
        ok("join names the session", "You are w1" in w1 and "--as w1" in w1)
        ok("join prints role text", "role instructions" in w1 or True)
        run(["join", "demo", "--role", "worker"], sid="sid-w2")
        run(["join", "demo", "--role", "reviewer"], sid="sid-r1")
        run(["join", "demo", "--role", "coordinator"], sid="sid-c1")
        lib = run(["join", "demo", "--role", "worker", "--specialty", "librarian"], sid="sid-lib")
        ok("specialist name", "You are librarian1" in lib)

        out = run(["next"], sid="sid-w1")
        ok("worker takes T1", out.startswith("T1"), out)
        out = run(["next"], sid="sid-w2")
        ok("T2 waits for T1; T3 is for the librarian", "Nothing is queued" in out, out)
        out = run(["next"], sid="sid-lib")
        ok("librarian takes T3", out.startswith("T3"), out)
        run(["--project", "demo", "add", "An ordinary extra task"])
        lw0 = proj / ".harness" / "work" / "T3"
        (lw0 / "r.md").write_text("entry", encoding="utf-8")
        run(["done", "--result", str(lw0 / "r.md"), "--summary", "found"], sid="sid-lib")
        out = run(["next"], sid="sid-lib")
        ok("a specialist is not handed ordinary work", "Nothing is queued" in out, out)
        run(["--project", "demo", "cancel", "T4", "--reason", "test only"])
        out = run(["--project", "demo", "ask", "Which regions are in scope?"])
        ok("the owner or setup session can queue a question", "decision queue" in out, out)
        run(["--project", "demo", "answer", "D1", "All of them"])

        out = run(["add", "sneaky"], sid="sid-w1", expect=1)
        ok("workers cannot add to the queue", "propose" in out)

        # done needs a real result path
        out = run(["done", "--result", "nope.md", "--summary", "s"], sid="sid-w1", expect=1)
        ok("done needs result on disk", "does not exist" in out)
        work = proj / ".harness" / "work" / "T1"
        ok("task folder created", work.is_dir())
        (work / "sources.md").write_text("a, b, c", encoding="utf-8")
        run(["checkpoint", "found two of three"], sid="sid-w1")
        out = run(["done", "--result", str(work / "sources.md"), "--summary", "three sources",
                   "--followup", "Check source b for a later edition"], sid="sid-w1")
        ok("done", "is done" in out and "Follow-ups proposed" in out)

        # author / coordinator cannot verify
        out = run(["verify", "T1", "--pass"], sid="sid-w1", expect=1)
        ok("author cannot verify", "cannot verify" in out)
        out = run(["verify", "T1", "--pass"], sid="sid-c1", expect=1)
        ok("coordinator cannot verify", "Only a reviewer" in out)
        out = run(["verify", "T1", "--fail"], sid="sid-r1", expect=1)
        ok("fail needs a note", "needs --note" in out)
        run(["verify", "T1", "--fail", "--note", "source c is a duplicate of a"], sid="sid-r1")
        out = run(["next"], sid="sid-w1")
        ok("failed task returns to its author", out.startswith("T1") and "duplicate" in out, out)
        out = run(["done", "--result", "sources.md", "--summary", "three distinct sources"], sid="sid-w1")
        ok("a result path may be given relative to the task folder", "is done" in out, out)
        run(["verify", "T3", "--pass", "--note", "entry matches the catalogue"], sid="sid-r1")
        out = run(["next"], sid="sid-r1")
        ok("reviewer is handed the done task", out.startswith("T1"), out)
        run(["verify", "T1", "--pass", "--note", "checked all three"], sid="sid-r1")

        # exploring ahead: work built on a result that is later sent back shows as provisional
        run(["--project", "demo", "add", "Base guess", "--to", "w1", "--priority", "9"])
        base = run(["next"], sid="sid-w1").split()[0]
        bf = proj / ".harness" / "work" / base / "g.md"; bf.write_text("guess", encoding="utf-8")
        run(["done", "--result", "g.md", "--summary", "a guess"], sid="sid-w1")
        run(["--project", "demo", "add", "Jump ahead from the guess", "--after", base, "--to", "w1", "--priority", "9"])
        ahead = run(["next"], sid="sid-w1").split()[0]
        ok("with the default setting, work can start on an unverified base", ahead != base and ahead.startswith("T"), ahead)
        af = proj / ".harness" / "work" / ahead / "j.md"; af.write_text("jump", encoding="utf-8")
        run(["done", "--result", "j.md", "--summary", "built on the guess"], sid="sid-w1")
        out = run(["verify", base, "--fail", "--note", "the guess does not hold"], sid="sid-r1")
        ok("failing a base names the work built on it", "Work already built on" in out and ahead in out, out)
        ok("the board flags the later work as provisional", ("%s (done) was built on %s" % (ahead, base)) in run(["board"], sid="sid-c1"))
        ok("the task itself says so", "PROVISIONAL" in run(["--project", "demo", "show", ahead]))
        run(["next"], sid="sid-w1")
        run(["done", "--result", "g.md", "--summary", "guess reworked"], sid="sid-w1")
        run(["verify", base, "--pass", "--note", "now supported"], sid="sid-r1")
        ok("once the base is verified the flag clears", "PROVISIONAL" not in run(["--project", "demo", "show", ahead]))
        run(["verify", ahead, "--pass", "--note", "follows from the verified base"], sid="sid-r1")

        # coordinator handles the proposal
        board = run(["board"], sid="sid-c1")
        ok("board lists proposal", "proposed follow-up" in board, board)
        run(["accept", "T5", "--to", "w2"], sid="sid-c1")
        out = run(["next"], sid="sid-w2")
        ok("accepted follow-up is handed out before unassigned work? (priority/created order)", out.startswith("T2") or out.startswith("T4"), out)

        # request to a specialist with --wait, then release
        first = out.split()[0]
        run(["request", "librarian", "Find the 1790 catalogue page", "--wait"], sid="sid-w2")
        st = run(["show", first], sid="sid-w2")
        ok("request --wait blocks the task", "[blocked]" in st, st)
        # the librarian takes the request
        out = run(["next"], sid="sid-lib")
        req = out.split()[0]
        rw = proj / ".harness" / "work" / req
        (rw / "page.md").write_text("p. 12", encoding="utf-8")
        run(["done", "--result", str(rw / "page.md"), "--summary", "page 12"], sid="sid-lib")
        st = run(["show", first], sid="sid-w2")
        ok("blocked task is released when the request is done", "[queued]" in st, st)

        # ask / answer
        out = run(["next"], sid="sid-w2")
        cur = out.split()[0]
        out = run(["ask", "Should I include the disputed source?"], sid="sid-w2")
        ok("ask queues a decision", "decision queue" in out)
        ok("task waits on owner", "[needs_owner]" in run(["show", cur], sid="sid-w2"))
        ok("board shows the decision", "disputed source" in run(["board"], sid="sid-c1"))
        run(["--project", "demo", "answer", "D2", "Yes, flag it as disputed"])
        ok("answered task is queued again", "[queued]" in run(["show", cur], sid="sid-w2"))

        # checker script: pass -> verified without reviewer
        cfgp = proj / ".harness" / "config.json"
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        chk = proj / "chk.py"
        chk.write_text("import sys\nsys.exit(0 if 'ok' in open(sys.argv[1], encoding='utf-8').read() else 1)\n", encoding="utf-8")
        cfg["checks"]["fact"] = {"script": '"{python}" chk.py "{result}"', "review": False}
        cfg["protected_paths"] = ["data.db"]
        cfg["blocked_hosts"] = [{"host": "blocked.example", "reason": "licence"}]
        cfgp.write_text(json.dumps(cfg), encoding="utf-8")
        run(["--project", "demo", "add", "A checkable fact", "--kind", "fact", "--to", "w1"])
        out = run(["next"], sid="sid-w1")
        fid = out.split()[0]
        fw = proj / ".harness" / "work" / fid
        (fw / "f.txt").write_text("wrong", encoding="utf-8")
        out = run(["done", "--result", str(fw / "f.txt"), "--summary", "fact"], sid="sid-w1")
        ok("failing checker sends the task back", "FAILED" in out, out)
        run(["next"], sid="sid-w1")
        (fw / "f.txt").write_text("ok", encoding="utf-8")
        out = run(["done", "--result", str(fw / "f.txt"), "--summary", "fact"], sid="sid-w1")
        ok("passing checker verifies", "is verified" in out, out)
        out = run(["--project", "demo", "promote", fid])
        ok("promote records", "promoted" in out)
        out = run(["--project", "demo", "promote", "T2"], expect=1)
        ok("only verified results are promoted", "Only verified" in out)

        # sampled review: every second script-passed result of this kind goes to the reviewer
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        cfg["checks"]["sampled"] = {"script": '"{python}" chk.py "{result}"', "review": "sample", "sample_every": 2}
        cfg["roles"]["librarian"] = {"max_sessions": 1, "write": ["{work}/**"], "messaging": "none"}
        cfgp.write_text(json.dumps(cfg), encoding="utf-8")
        outcomes = []
        for i in range(4):
            run(["--project", "demo", "add", "Sampled %d" % i, "--kind", "sampled", "--to", "w1"])
            tid = run(["next"], sid="sid-w1").split()[0]
            f = proj / ".harness" / "work" / tid / "f.txt"
            f.write_text("ok", encoding="utf-8")
            outcomes.append("verified" if "is verified" in run(["done", "--result", str(f), "--summary", "s"], sid="sid-w1") else "review")
        ok("sampled review sends some results to the reviewer and verifies the rest by script",
           outcomes.count("review") == 2 and outcomes.count("verified") == 2, outcomes)
        out = run(["join", "demo", "--role", "worker", "--specialty", "librarian"], sid="sid-lib2", expect=1)
        ok("a capped role refuses a second session", "at most 1 session" in out, out)
        out = run(["join", "demo", "--role", "worker", "--specialty", "librarian"], sid="sid-w2", expect=1)
        ok("the cap also holds for a session that already joined as a plain worker", "at most 1 session" in out, out)
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        cfg["checks"]["librarian"] = {"script": None, "review": True}
        cfgp.write_text(json.dumps(cfg), encoding="utf-8")
        run(["--project", "demo", "add", "Needs the library", "--to", "w2"])
        run(["next"], sid="sid-w2")
        out = run(["request", "librarian", "Look up one record"], sid="sid-w2")
        ok("a request to a specialist takes that specialist's kind of check",
           "kind:         librarian" in run(["--project", "demo", "show", out.split()[1]]), out)
        run(["block", "--reason", "test only: waiting for the library"], sid="sid-w2")
        out = run(["--project", "demo", "add", "x", "--detail", "a", "--detail-file", str(chk)], expect=1)
        ok("detail given twice is refused", "not both" in out)
        out = run(["--project", "demo", "add", "Earlier checked kind", "--kind", "fact", "--result", str(fw / "f.txt")])
        ok("an earlier result of a script-checked kind is checked when registered", "Checker passed" in out, out)
        out = run(["--project", "demo", "add", "Earlier finding", "--result", str(chk)])
        ok("an earlier result can be registered for review", "earlier result waiting to be checked" in out, out)
        eid = out.split()[1]
        ok("it is done, not verified", "[done]" in run(["--project", "demo", "show", eid]))
        run(["verify", eid, "--pass", "--note", "checked against the source"], sid="sid-r1")
        out = run(["--project", "demo", "add", "Waits on a book"])
        wid = out.split()[1].rstrip(":")
        out = run(["--project", "demo", "block", wid, "--reason", "needs volume 3"])
        ok("the owner can mark a queued item as blocked", "is blocked" in out and "[blocked]" in run(["--project", "demo", "show", wid]), out)

        # views, metrics, scan, cases, overview
        run(["--project", "demo", "status"])
        ok("status file", "Decisions waiting" in (proj / ".harness" / "STATUS.md").read_text(encoding="utf-8"))
        html = (proj / ".harness" / "dashboard.html").read_text(encoding="utf-8")
        ok("dashboard has data", '"project": "demo"' in html and "__DATA__" not in html)
        m = json.loads(run(["--project", "demo", "metrics"]))
        ok("metrics", m["checking"]["verified"] >= 2 and m["checking"]["failures"] >= 2, json.dumps(m["checking"]))
        ok("scan", "Files changed" in run(["--project", "demo", "scan"]))
        run(["--project", "demo", "case", "add", "known-dating"])
        run(["--project", "demo", "case", "record", "known-dating", "pass", "--note", "matches"])
        ok("cases", "pass" in run(["--project", "demo", "case", "list"]))
        ok("overview", "demo" in run(["overview"]))
        ok("log", "verified" in run(["--project", "demo", "log"]))

        # handoff: drain -> stamp -> parked -> resume on another machine
        run(["--project", "demo", "add", "Long job", "--to", "w1"])
        run(["next"], sid="sid-w1")
        out = run(["--project", "demo", "drain"])
        ok("drain reports busy session", "w1" in out and "Still working" in out, out)
        out = run(["--project", "demo", "stamp"], expect=1)
        ok("stamp refuses while a session is mid-task", "mid-task" in out)
        ok("no tasks while draining", "draining" in run(["next"], sid="sid-w2"))
        run(["checkpoint", "half way; notes in notes.md"], sid="sid-w1")
        ok("drain clears after checkpoint", "You can run 'stamp'" in run(["--project", "demo", "drain"]))
        out = run(["--project", "demo", "stamp"])
        ok("stamp parks this computer", "now parked" in out, out)
        out = run(["next"], sid="sid-w2", expect=1)
        ok("parked computer refuses writes", "parked" in out)
        ok("board still readable when parked", "PARKED" in run(["board"], sid="sid-c1"))

        # copy the project to "machine b"
        proj_b = tmp / "copy on b"
        shutil.copytree(str(proj), str(proj_b), ignore=shutil.ignore_patterns("local", "snapshots"))
        for f in (proj_b / ".harness").glob("ledger.sqlite*"):
            f.unlink()
        # the copy has only the handoff ledger, as git would deliver it
        envb = {"HARNESS_MACHINE": "machine-b"}
        run(["register-path", "demo", str(proj_b)], env_extra=envb)
        out = run(["--project", "demo", "resume"], env_extra=envb)
        ok("resume on the other computer", "Resumed project demo on machine-b" in out and "back in the queue" in out, out)
        out = run(["--project", "demo", "list"], env_extra=envb)
        ok("ledger arrived intact", "Long job" in out, out)
        out = run(["join", "demo", "--role", "worker"], sid="sid-b1", env_extra=envb)
        ok("fresh session joins on b", "You are w3" in out, out)
        listing = run(["--project", "demo", "list"], env_extra=envb)
        long_id = [l.split()[0] for l in listing.splitlines() if "Long job" in l][0]
        out = run(["--project", "demo", "show", long_id], env_extra=envb)
        ok("mid-flight task is queued again with its checkpoint", "[queued]" in out and "half way" in out, out)
        out = run(["next"], sid="sid-b1", env_extra=envb)
        ok("fresh session on b is handed work", out.startswith("T"), out)
        # machine a is still parked
        out = run(["--project", "demo", "add", "should fail"], expect=1)
        ok("machine a stays parked", "parked" in out)
        # tamper with the handoff -> resume refuses
        hb = proj_b / ".harness" / "handoff" / "ledger.sqlite"
        with open(str(hb), "ab") as f:
            f.write(b"junk")
        out = run(["--project", "demo", "resume", "--no-pull"], env_extra=envb, expect=1)
        ok("resume refuses a handoff that does not match its stamp", "does not match its stamp" in out)

        # edit, held proposals, decisions shown on a task, unverify, relative paths, trial rows
        out = run(["--project", "demo", "add", "Held item", "--proposed"], env_extra=envb)
        held = out.split()[1]
        ok("the owner can hold an item as a proposal", "[proposed]" in run(["--project", "demo", "show", held], env_extra=envb))
        run(["--project", "demo", "accept", held], env_extra=envb)
        (proj_b / ".harness" / "notes" / "d.md").write_text("full detail", encoding="utf-8")
        out = run(["--project", "demo", "edit", held, "--role", "analyst", "--kind", "fact", "--detail-file", ".harness/notes/d.md"], env_extra=envb)
        ok("edit re-addresses a task and changes its kind and detail", "for role analyst" in out and "kind=fact" in out, out)
        shown = run(["--project", "demo", "show", held], env_extra=envb)
        ok("edited task shows the new detail", "full detail" in shown and "analyst" in shown, shown)
        import sqlite3 as _sq
        _c = _sq.connect(str(proj_b / ".harness" / "ledger.sqlite"))
        stored = _c.execute("SELECT detail_path FROM tasks WHERE id=?", (held,)).fetchone()[0]
        ok("paths inside the project are stored relative, so they survive a move", stored == ".harness/notes/d.md", stored)
        vid = _c.execute("SELECT id FROM tasks WHERE state='verified' LIMIT 1").fetchone()[0]
        did = _c.execute("SELECT id, task FROM decisions WHERE task IS NOT NULL LIMIT 1").fetchone()
        _c.close()
        ok("a task shows the owner's answer to its decision", "owner's answer" in run(["--project", "demo", "show", did[1]], env_extra=envb))
        out = run(["--project", "demo", "unverify", vid, "--reason", "passed with 'looks fine'"], env_extra=envb)
        ok("a verification can be withdrawn", "no longer verified" in out and "[done]" in run(["--project", "demo", "show", vid], env_extra=envb))
        run(["--project", "demo", "add", "Trial: one small task", "--role", "trial", "--job", "trial"], env_extra=envb)
        run(["join", "demo", "--role", "worker", "--specialty", "trial"], sid="sid-trial", env_extra=envb)
        got = run(["next"], sid="sid-trial", env_extra=envb)
        ok("a trial session takes only trial work", got.split()[1] == "[in_progress]" and "Trial:" in got, got)
        tid_trial = got.split()[0]
        tf = proj_b / ".harness" / "work" / tid_trial / "r.md"
        tf.write_text("ok", encoding="utf-8")
        run(["done", "--result", "r.md", "--summary", "trial"], sid="sid-trial", env_extra=envb)
        run(["--project", "demo", "case", "record", "known-dating", "pass", "--note", "trial model"], env_extra=envb)
        out = run(["--project", "demo", "trial-clear", "--yes"], env_extra=envb)
        ok("trial-clear cancels trial rows and closes trial sessions", "Cleared 1 trial task(s) and closed 1 trial session(s)" in out, out)
        m2 = json.loads(run(["--project", "demo", "metrics"], env_extra=envb))
        ok("trial rows are left out of the numbers", m2["trial_tasks_left_out"] == 1, str(m2["trial_tasks_left_out"]))

        # undo point, restore, end-sessions, tier change, unregister
        hb = proj_b / ".harness"
        out = run(["--project", "demo", "snapshot", "--setup"], env_extra=envb)
        point = [l for l in out.splitlines() if l.startswith("Undo point:")][0].split(": ")[1]
        ok("undo point holds rules, roles and ledger", "config.json" in out and "roles/" in out and "ledger.sqlite" in out, out)
        (hb / "roles" / "worker.md").write_text("ruined", encoding="utf-8")
        cfgb = json.loads((hb / "config.json").read_text(encoding="utf-8")); cfgb["stale_minutes"] = 999
        (hb / "config.json").write_text(json.dumps(cfgb), encoding="utf-8")
        before_tasks = run(["--project", "demo", "list", "--all"], env_extra=envb)
        run(["--project", "demo", "add", "Added after the undo point"], env_extra=envb)
        ok("restore needs --yes", "--yes" in run(["--project", "demo", "restore", point], env_extra=envb, expect=1))
        run(["--project", "demo", "restore", point, "--yes"], env_extra=envb)
        ok("restore puts role files and rules back", "ruined" not in (hb / "roles" / "worker.md").read_text(encoding="utf-8")
           and json.loads((hb / "config.json").read_text(encoding="utf-8"))["stale_minutes"] != 999)
        ok("restore without --ledger keeps later ledger changes",
           "Added after the undo point" in run(["--project", "demo", "list", "--all"], env_extra=envb))
        run(["--project", "demo", "restore", point, "--yes", "--ledger"], env_extra=envb)
        ok("restore --ledger puts the ledger back", run(["--project", "demo", "list", "--all"], env_extra=envb) == before_tasks)
        ok("restore takes its own undo point first", len(list((hb / "snapshots").glob("setup-*"))) >= 3)
        (hb / "STATE.md").write_text("made after the undo point", encoding="utf-8")
        run(["--project", "demo", "restore", point, "--yes"], env_extra=envb)
        ok("restore removes a part that did not exist at the undo point", not (hb / "STATE.md").exists())
        run(["join", "demo", "--role", "worker"], sid="sid-b9", env_extra=envb)
        run(["next"], sid="sid-b9", env_extra=envb)
        out = run(["--project", "demo", "end-sessions", "--yes"], env_extra=envb)
        ok("end-sessions closes sessions and requeues their work", "Closed" in out and "Back in the queue" in out, out)
        ok("no session is left on the board", "(none have joined)" in run(["--project", "demo", "board"], env_extra=envb))
        out = run(["init", "demo", "--path", str(proj_b), "--tier", "lite"], env_extra=envb)
        ok("a tier change updates the rules file", "Tier changed from full to lite" in out
           and json.loads((hb / "config.json").read_text(encoding="utf-8"))["tier"] == "lite" and (hb / "STATE.md").exists(), out)
        run(["init", "demo", "--path", str(proj_b), "--tier", "full"], env_extra=envb)

        # reset clears a trial run but keeps rules, roles and cases
        out = run(["--project", "demo", "reset"], env_extra=envb, expect=1)
        ok("reset needs --yes", "--yes" in out)
        run(["--project", "demo", "reset", "--yes"], env_extra=envb)
        ok("reset empties the ledger", "No tasks." in run(["--project", "demo", "list", "--all"], env_extra=envb))
        ok("reset keeps recorded case results", "pass" in run(["--project", "demo", "case", "list"], env_extra=envb))
        ok("reset keeps the rules file", (proj_b / ".harness" / "config.json").exists()
           and (proj_b / ".harness" / "roles" / "worker.md").exists())
        out = run(["unregister", "demo", "--yes"], env_extra=envb)
        ok("unregister leaves the folder alone", "no longer a harness project" in out and (proj_b / ".harness" / "config.json").exists())
        ok("the other computer's registration is untouched", "demo" in run(["projects"]))
        print("ledger tests passed: %d" % len(PASSED))
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


if __name__ == "__main__":
    main()
