#!/usr/bin/env python3
"""harness.py - the ledger command.

One small command is the only way to change a project's ledger. Agents never
write SQL or edit the status files; they run a subcommand and the command
enforces the rules (who may verify, short rows, one writer per machine).

Standard library only. Python 3.8+. Works on macOS, Linux and Windows.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.1.0"
SCHEMA_VERSION = 1
SUMMARY_MAX = 300
NOTE_MAX = 500

OPEN_STATES = ("proposed", "queued", "in_progress", "blocked", "needs_owner", "done")
ALL_STATES = OPEN_STATES + ("verified", "rejected", "cancelled")

DEFAULT_CONFIG = {
    "project": "",
    "goal": "",
    "tier": "full",
    "stale_minutes": 20,
    "auto_join": "worker",
    "deps_need_verified": False,
    "outside_writes": "deny",
    "nudge_max_chars": 200,
    "roles": {
        "worker": {"write": ["{work}/**"], "messaging": "none"},
        "reviewer": {"write": ["{work}/review/**", ".harness/reviews/**"], "messaging": "none"},
        "coordinator": {"write": [".harness/notes/**"], "messaging": "nudge"},
        "guest": {"write": ["**"], "messaging": "open"},
    },
    "extra_write_paths": [],
    "protected_paths": [],
    "blocked_hosts": [],
    "bash_deny": [],
    "checks": {"default": {"script": None, "review": True}},
    "promote": {"cmd": None},
    "handoff": {"push_cmd": None, "pull_cmd": None},
    "autosave": {"minutes": 5, "keep": 20, "cmd": None},
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, detail_path TEXT, kind TEXT DEFAULT 'default',
  role TEXT, assigned_to TEXT, state TEXT NOT NULL, priority INTEGER DEFAULT 0,
  depends_on TEXT DEFAULT '[]', block_on TEXT, block_reason TEXT, job TEXT, parent TEXT,
  requested_by TEXT, result_path TEXT, summary TEXT, done_by TEXT, reviewer TEXT,
  check_passed INTEGER, verified_by TEXT, verify_note TEXT, fail_count INTEGER DEFAULT 0,
  promoted_at TEXT, created_at TEXT, updated_at TEXT, started_at TEXT, done_at TEXT, verified_at TEXT);
CREATE TABLE IF NOT EXISTS sessions (
  name TEXT PRIMARY KEY, session_id TEXT, role TEXT, specialty TEXT, machine TEXT,
  state TEXT, current_task TEXT, held_task INTEGER DEFAULT 0, last_heartbeat TEXT,
  in_tool TEXT, in_tool_since TEXT, stop_reason TEXT, stop_blocks INTEGER DEFAULT 0,
  joined_at TEXT, cwd TEXT);
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY, task TEXT, asked_by TEXT, question TEXT, answer TEXT,
  state TEXT, asked_at TEXT, answered_at TEXT);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, session TEXT, kind TEXT, task TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS ix_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS ix_events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS ix_sessions_sid ON sessions(session_id);
"""


class HarnessError(Exception):
    pass


# ---------------------------------------------------------------- basics

def home():
    return Path(os.environ.get("HARNESS_HOME") or (Path.home() / ".harness"))


def machine():
    return (os.environ.get("HARNESS_MACHINE") or socket.gethostname().split(".")[0]).lower()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_ts(s):
    try:
        return datetime.fromisoformat(s) if s else None
    except ValueError:
        return None


def age_minutes(ts):
    t = parse_ts(ts)
    if not t:
        return None
    return (datetime.now(timezone.utc) - t).total_seconds() / 60.0


def fmt_age(ts):
    m = age_minutes(ts)
    if m is None:
        return "never"
    if m < 1:
        return "just now"
    if m < 90:
        return "%dm ago" % m
    if m < 60 * 48:
        return "%dh ago" % (m / 60)
    return "%dd ago" % (m / 1440)


def read_json(path, default):
    try:
        with open(str(path), "r", encoding="utf-8-sig") as f:     # tolerate a byte-order mark from Windows editors
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp%d" % os.getpid())
    with open(str(tmp), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    replace_file(tmp, path)


def replace_file(src, dst):
    for attempt in range(8):
        try:
            os.replace(str(src), str(dst))
            return
        except PermissionError:
            time.sleep(0.05 * (attempt + 1))
    os.replace(str(src), str(dst))


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp%d" % os.getpid())
    with open(str(tmp), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    replace_file(tmp, path)


def norm(p):
    return os.path.normcase(os.path.realpath(str(p)))


def is_inside(child, parent):
    c, p = norm(child), norm(parent)
    return c == p or c.startswith(p.rstrip("\\/") + os.sep)


def python_path():
    """The interpreter to name in commands we print. Stable across tool updates where we can manage it."""
    exe = os.environ.get("HARNESS_PYTHON") or sys.executable
    if ("Xcode.app" in exe or "CommandLineTools" in exe) and os.path.exists("/usr/bin/python3"):
        exe = "/usr/bin/python3"       # the system shim outlives Xcode updates
    return Path(exe).as_posix()


def shell_quote(part):
    """Quote only when needed, so the same text works in bash and in PowerShell when paths have no spaces."""
    return '"%s"' % part if (" " in part or not part) else part


def this_command():
    return "%s %s" % (shell_quote(python_path()), shell_quote(Path(__file__).resolve().as_posix()))


# ---------------------------------------------------------------- registry

def registry():
    reg = read_json(home() / "registry.json", {})
    reg.setdefault("projects", {})
    return reg


def save_registry(reg):
    write_json(home() / "registry.json", reg)


def project_root(name):
    entry = registry()["projects"].get(name)
    if not entry:
        raise HarnessError("No project named '%s' in the registry. Known: %s"
                           % (name, ", ".join(sorted(registry()["projects"])) or "none"))
    path = entry.get("paths", {}).get(machine())
    if not path:
        raise HarnessError(
            "Project '%s' has no folder recorded for this computer (%s). "
            "Run: register-path %s <folder>" % (name, machine(), name))
    return Path(path)


def project_by_cwd(cwd):
    best = None
    for name, entry in registry()["projects"].items():
        path = entry.get("paths", {}).get(machine())
        if path and is_inside(cwd, path):
            if best is None or len(path) > len(best[1]):
                best = (name, path)
    return best[0] if best else None


def session_index():
    return read_json(home() / "sessions.json", {})


def save_session_index(idx):
    write_json(home() / "sessions.json", idx)


# ---------------------------------------------------------------- database

def hdir(root):
    return Path(root) / ".harness"


def ledger_path(root):
    return hdir(root) / "ledger.sqlite"


def connect(root, readonly=False):
    p = ledger_path(root)
    if not p.exists():
        raise HarnessError("No ledger at %s. This project may be on the Lite tier "
                           "(see .harness/STATE.md) or not set up yet." % p)
    if readonly:
        con = sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
    else:
        con = sqlite3.connect(str(p), timeout=30, isolation_level=None)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def tx(con):
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


def load_config(root):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    user = read_json(hdir(root) / "config.json", {})
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict) and k != "roles":
            cfg[k].update(v)
        elif k == "roles" and isinstance(v, dict):
            for rn, rv in v.items():
                cfg["roles"].setdefault(rn, {}).update(rv)
        else:
            cfg[k] = v
    return cfg


def meta_get(con, key, default=None):
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def meta_set(con, key, value):
    con.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value))


def event(con, kind, session=None, task=None, detail=None):
    con.execute("INSERT INTO events(ts,session,kind,task,detail) VALUES(?,?,?,?,?)",
                (now(), session, kind, task, (detail or "")[:1000]))


def parked_info(root):
    return read_json(hdir(root) / "local" / "PARKED.json", None)


def require_writable(root):
    info = parked_info(root)
    if info:
        raise HarnessError(
            "This project is parked on this computer: it was handed off at %s. "
            "Nothing may be written here until you run 'resume'." % info.get("stamped_at"))


def get_task(con, tid):
    row = con.execute("SELECT * FROM tasks WHERE id=?", (tid.upper() if tid else tid,)).fetchone()
    if not row:
        raise HarnessError("No task %s." % tid)
    return row


def get_session(con, name):
    return con.execute("SELECT * FROM sessions WHERE name=?", (name,)).fetchone()


def next_id(con, prefix):
    n = int(meta_get(con, "seq_" + prefix, "0")) + 1
    meta_set(con, "seq_" + prefix, str(n))
    return "%s%d" % (prefix, n)


def check_short(text, limit, what):
    if text and len(text) > limit:
        raise HarnessError(
            "%s is %d characters; the ledger holds short rows only (max %d). "
            "Put the content in a file in your task folder and give the path."
            % (what, len(text), limit))


def set_task(con, tid, **fields):
    fields["updated_at"] = now()
    cols = ", ".join("%s=?" % k for k in fields)
    con.execute("UPDATE tasks SET %s WHERE id=?" % cols, list(fields.values()) + [tid])


def set_session(con, name, **fields):
    cols = ", ".join("%s=?" % k for k in fields)
    con.execute("UPDATE sessions SET %s WHERE name=?" % cols, list(fields.values()) + [name])


def deps_ready(con, cfg, task):
    deps = json.loads(task["depends_on"] or "[]")
    ok = ("verified",) if cfg.get("deps_need_verified") else ("done", "verified")
    for d in deps:
        row = con.execute("SELECT state FROM tasks WHERE id=?", (d,)).fetchone()
        if not row or row["state"] not in ok:
            return False
    return True


def release_dependents(con, tid):
    for row in con.execute("SELECT id FROM tasks WHERE state='blocked' AND block_on=?", (tid,)).fetchall():
        set_task(con, row["id"], state="queued", block_on=None, block_reason=None)
        event(con, "unblocked", None, row["id"], "blocker %s finished" % tid)


def shaky_bases(con, task):
    """Tasks this one was built on that were sent back, or had their verification withdrawn, and are not verified now."""
    ids = list(json.loads(task["depends_on"] or "[]"))
    if task["parent"]:
        ids.append(task["parent"])
    out = []
    for i in ids:
        b = con.execute("SELECT id,state,fail_count,verify_note FROM tasks WHERE id=?", (i,)).fetchone()
        if b is None or b["state"] in ("verified", "cancelled", "rejected"):
            continue
        if (b["fail_count"] or 0) > 0 or (b["verify_note"] or "").startswith("verification withdrawn"):
            out.append(b["id"])
    return out


def built_on(con, tid):
    """Tasks that follow from this one and have work in them."""
    rows = con.execute("SELECT * FROM tasks WHERE state IN ('in_progress','done','verified')").fetchall()
    return [r["id"] for r in rows if tid in json.loads(r["depends_on"] or "[]") or r["parent"] == tid]


def work_dir(root, tid):
    return hdir(root) / "work" / tid


def resolve_path(root, p):
    path = Path(p).expanduser()
    return path if path.is_absolute() else Path(root) / path


def stored_path(root, p):
    """How a path is kept in the ledger: relative to the project when inside it, so it survives a move."""
    p = Path(os.path.abspath(str(p)))
    if is_inside(p, root):
        return os.path.relpath(norm(p), norm(root)).replace("\\", "/")
    return str(p)


# ---------------------------------------------------------------- picking work

def pick_next(con, cfg, sess):
    """Next task this session should take, or None. Call inside a transaction."""
    if sess["role"] == "reviewer":
        rows = con.execute(
            "SELECT * FROM tasks WHERE state='done' AND (reviewer IS NULL OR reviewer=?) "
            "AND (done_by IS NULL OR done_by<>?) ORDER BY priority DESC, done_at", (sess["name"], sess["name"])
        ).fetchall()
        for t in rows:
            chk = check_for(cfg, t["kind"])
            if chk.get("review", True) and not (chk.get("script") and t["check_passed"] is None):
                return t
        return None
    rows = con.execute(
        "SELECT * FROM tasks WHERE state='queued' ORDER BY priority DESC, created_at, id").fetchall()
    gone = set(r["name"] for r in con.execute("SELECT name FROM sessions WHERE state='ended'").fetchall())
    for t in rows:
        owner = t["assigned_to"] if t["assigned_to"] not in gone else None   # work of a departed session is up for grabs
        if owner and owner != sess["name"]:
            continue
        if not owner:
            wanted = t["role"] or "worker"
            if wanted != (sess["specialty"] or sess["role"]):   # a specialist takes only its own kind of request
                continue
        if deps_ready(con, cfg, t):
            return t
    return None


def claim(con, root, sess, task):
    if sess["role"] == "reviewer":
        set_task(con, task["id"], reviewer=sess["name"])
        event(con, "review_started", sess["name"], task["id"])
    else:
        set_task(con, task["id"], state="in_progress", assigned_to=sess["name"], started_at=now())
        event(con, "started", sess["name"], task["id"])
        work_dir(root, task["id"]).mkdir(parents=True, exist_ok=True)
    set_session(con, sess["name"], current_task=task["id"], held_task=1, stop_reason=None)


def check_for(cfg, kind):
    checks = cfg.get("checks") or {}
    base = dict(checks.get("default") or {"script": None, "review": True})
    base.update(checks.get(kind or "default") or {})
    return base


# ---------------------------------------------------------------- identity

class Ctx(object):
    def __init__(self, args, need_session=False, need_project=True, write=True):
        self.args = args
        sid = os.environ.get("HARNESS_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID")
        idx = session_index()
        entry = idx.get(sid) if sid else None
        self.sid = sid
        pname = getattr(args, "project", None) or (entry or {}).get("project")
        if not pname:
            pname = project_by_cwd(os.getcwd())
        if not pname and need_project:
            raise HarnessError("Which project? Pass --project NAME (see 'projects'), "
                               "or run this from inside a registered project folder.")
        self.project = pname
        self.root = project_root(pname) if pname else None
        self.cfg = load_config(self.root) if self.root else None
        self.con = None
        self.me = None
        if self.root and ledger_path(self.root).exists():
            if write:
                require_writable(self.root)
            self.con = connect(self.root)
            name = getattr(args, "as_name", None) or os.environ.get("HARNESS_SESSION_NAME")
            if not name and entry and entry.get("project") == pname:
                name = entry.get("name")
            if name:
                self.me = get_session(self.con, name)
                if not self.me:
                    raise HarnessError("No session named '%s' in project %s." % (name, pname))
        elif need_project and self.root is not None and getattr(args, "cmd", "") not in ("init",):
            raise HarnessError("No ledger at %s. This project may be on the Lite tier "
                               "(see .harness/STATE.md)." % ledger_path(self.root))
        if need_session and not self.me:
            raise HarnessError(
                "This session has not joined project %s. Run: join %s --role worker "
                "(or pass --as NAME if you already joined)." % (pname, pname))

    @property
    def who(self):
        return self.me["name"] if self.me else "owner"

    def refresh(self):
        if self.me:
            self.me = get_session(self.con, self.me["name"])


def after_change(ctx):
    try:
        render(ctx.root, ctx.con, ctx.cfg)
    except Exception as exc:  # the views are a convenience; never fail a write because of them
        sys.stderr.write("(could not refresh status views: %s)\n" % exc)


# ---------------------------------------------------------------- commands: setup

def cmd_init(args):
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        raise HarnessError("Folder does not exist: %s" % root)
    h = hdir(root)
    for sub in ("work", "roles", "snapshots", "handoff", "local", "cases", "notes", "reviews", "doctor", "tools", "surgery"):
        (h / sub).mkdir(parents=True, exist_ok=True)
    tdir = Path(__file__).resolve().parent / "templates"
    gi = h / ".gitignore"
    if not gi.exists():
        write_text(gi, "/local/\n/snapshots/\n/ledger.sqlite\n/ledger.sqlite-wal\n/ledger.sqlite-shm\n/dashboard.html\n*.tmp*\n*.new\n")
    if args.tier == "lite":
        for fname in ("STATE.md", "check.py"):
            dst = h / fname
            src = tdir / "lite" / fname
            if not dst.exists() and src.exists():
                shutil.copyfile(str(src), str(dst))
    else:
        con = sqlite3.connect(str(ledger_path(root)), timeout=30, isolation_level=None)
        con.executescript(SCHEMA)
        con.execute("PRAGMA journal_mode=WAL")
        con.row_factory = sqlite3.Row
        if meta_get(con, "schema_version") is None:
            meta_set(con, "schema_version", str(SCHEMA_VERSION))
            meta_set(con, "created_at", now())
            meta_set(con, "active_machine", machine())
            event(con, "init", None, None, "tier=full machine=%s" % machine())
        con.close()
        rdir = tdir / "roles"
        if rdir.is_dir():
            for src in sorted(rdir.glob("*.md")):
                dst = h / "roles" / src.name
                if not dst.exists():
                    shutil.copyfile(str(src), str(dst))
    cfgp = h / "config.json"
    if not cfgp.exists():
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        cfg["project"] = args.name
        cfg["tier"] = args.tier
        write_json(cfgp, cfg)
    else:
        existing = read_json(cfgp, {})
        if existing and existing.get("tier") != args.tier:
            print("Tier changed from %s to %s; the rest of the rules file is unchanged." % (existing.get("tier"), args.tier))
            existing["tier"] = args.tier
            write_json(cfgp, existing)
    reg = registry()
    entry = reg["projects"].setdefault(args.name, {"paths": {}})
    entry["paths"][machine()] = str(root)
    entry["tier"] = args.tier
    save_registry(reg)
    print("Project '%s' (%s tier) set up at %s" % (args.name, args.tier, h))
    if args.tier == "full":
        con = connect(root)
        render(root, con, load_config(root))
        print("Status file: %s" % (h / "STATUS.md"))
        print("Dashboard:   %s" % (h / "dashboard.html"))
        print("Rules file:  %s" % cfgp)
    else:
        print("State file:  %s" % (h / "STATE.md"))


def cmd_register_path(args):
    root = Path(args.path).expanduser().resolve()
    if not hdir(root).is_dir():
        raise HarnessError("%s has no .harness folder. Copy or pull the project here first." % root)
    reg = registry()
    entry = reg["projects"].setdefault(args.name, {"paths": {}})
    entry["paths"][machine()] = str(root)
    entry.setdefault("tier", read_json(hdir(root) / "config.json", {}).get("tier", "full"))
    save_registry(reg)
    print("On this computer (%s), project '%s' is at %s" % (machine(), args.name, root))


def cmd_projects(args):
    reg = registry()
    if not reg["projects"]:
        print("No projects registered on this computer.")
        return
    for name, entry in sorted(reg["projects"].items()):
        path = entry.get("paths", {}).get(machine())
        print("%-20s %-5s %s" % (name, entry.get("tier", "?"), path or "(no folder on this computer)"))


# ---------------------------------------------------------------- commands: sessions

def role_prefix(role, specialty):
    if specialty:
        return re.sub(r"[^a-z0-9]", "", specialty.lower())[:12] or "s"
    return {"coordinator": "c", "worker": "w", "reviewer": "r", "guest": "g"}.get(role, role[:1] or "x")


def do_join(root, con, cfg, sid, role, specialty=None, cwd=None, quiet=False):
    """Register (or re-role) a session. Returns the session row."""
    with tx(con):
        row = con.execute("SELECT * FROM sessions WHERE session_id=? AND state<>'ended'", (sid,)).fetchone() if sid else None
        label = specialty or role
        cap = ((cfg.get("roles") or {}).get(label) or {}).get("max_sessions")
        if cap:
            live = con.execute(
                "SELECT name FROM sessions WHERE state NOT IN ('ended') AND COALESCE(specialty, role)=? AND name<>?",
                (label, row["name"] if row else "")).fetchall()
            if len(live) >= int(cap):
                raise HarnessError(
                    "Project rule: at most %s session(s) may hold the role '%s', and %s already does. Ask for its "
                    "help with 'request %s', or have the owner close that session first (it runs 'leave')."
                    % (cap, label, ", ".join(r["name"] for r in live), label))
        if row:
            name = row["name"]
            set_session(con, name, role=role, specialty=specialty, state="active",
                        last_heartbeat=now(), machine=machine())
            event(con, "role", name, None, "%s -> %s" % (row["role"], role))
        else:
            prefix = role_prefix(role, specialty)
            n = 1
            while get_session(con, "%s%d" % (prefix, n)):
                n += 1
            name = "%s%d" % (prefix, n)
            con.execute(
                "INSERT INTO sessions(name,session_id,role,specialty,machine,state,last_heartbeat,joined_at,cwd) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (name, sid, role, specialty, machine(), "active", now(), now(), cwd or os.getcwd()))
            event(con, "joined", name, None, "role=%s%s" % (role, " specialty=%s" % specialty if specialty else ""))
        if role == "coordinator":
            for old in con.execute("SELECT name FROM sessions WHERE role='coordinator' AND name<>? AND state<>'ended'",
                                   (name,)).fetchall():
                set_session(con, old["name"], role="guest", stop_reason="replaced by %s" % name)
                event(con, "replaced", old["name"], None, "coordinator is now %s" % name)
    if sid:
        idx = session_index()
        idx[sid] = {"project": cfg.get("project") or "", "name": name, "root": str(root)}
        save_session_index(idx)
    return get_session(con, name)


def role_text(root, role, specialty=None):
    for cand in ([specialty] if specialty else []) + [role]:
        p = hdir(root) / "roles" / ("%s.md" % cand)
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""


def print_identity(ctx, sess, full=True):
    cmd = this_command()
    print("You are %s, role %s%s, in project '%s'." % (
        sess["name"], sess["role"], " (%s)" % sess["specialty"] if sess["specialty"] else "", ctx.project))
    print("Project folder: %s" % ctx.root)
    print("Ledger command (use exactly this, then a subcommand):")
    print("  %s --as %s" % (cmd, sess["name"]))
    if sess["current_task"]:
        print("Current task: %s  (run: show %s)" % (sess["current_task"], sess["current_task"]))
    if full:
        text = role_text(ctx.root, sess["role"], sess["specialty"])
        if text:
            print("\n----- role instructions -----\n" + text.rstrip())
            print("----- end role instructions -----")


def cmd_join(args):
    root = project_root(args.project)
    require_writable(root)
    con = connect(root)
    cfg = load_config(root)
    sid = args.session or os.environ.get("HARNESS_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if args.role not in ("coordinator", "worker", "reviewer", "guest"):
        raise HarnessError("Role must be coordinator, worker, reviewer or guest. "
                           "For a specialist, use --role worker --specialty NAME.")
    sess = do_join(root, con, cfg, sid, args.role, args.specialty)
    ctx = Ctx.__new__(Ctx)
    ctx.project, ctx.root, ctx.con, ctx.cfg, ctx.me, ctx.args, ctx.sid = args.project, root, con, cfg, sess, args, sid
    print_identity(ctx, sess)
    if not sid:
        print("\nNote: no session ID was available, so the hooks cannot see this session. "
              "Pass --as %s on every command." % sess["name"])
    scope = hooks_scope(root)
    if scope == "project" and not is_inside(os.getcwd(), root):
        print("\nNOTE FOR THE OWNER: this session was started outside the project folder, and the hooks for this "
              "project apply only to sessions started inside it. This session can use the ledger, but the write "
              "rules, the stop rule and activity tracking do NOT apply to it. Start it inside %s instead, or "
              "install the hooks user-wide." % root)
    elif scope == "none":
        print("\nNOTE FOR THE OWNER: no hooks are installed for this project on this computer, so none of the "
              "rules are enforced.")
    after_change(ctx)


def cmd_whoami(args):
    ctx = Ctx(args, need_session=True, write=False)
    print_identity(ctx, ctx.me, full=args.full)


def cmd_leave(args):
    ctx = Ctx(args, need_session=True)
    with tx(ctx.con):
        cur = ctx.me["current_task"]
        if cur:
            t = get_task(ctx.con, cur)
            if t["state"] == "in_progress":
                set_task(ctx.con, cur, state="queued")
                event(ctx.con, "requeued", ctx.who, cur, "session left")
        set_session(ctx.con, ctx.who, state="ended", current_task=None, stop_reason="left")
        event(ctx.con, "left", ctx.who)
    idx = session_index()
    for sid, e in list(idx.items()):
        if e.get("name") == ctx.who and e.get("project") == ctx.project:
            del idx[sid]
    save_session_index(idx)
    print("%s has left project %s." % (ctx.who, ctx.project))
    after_change(ctx)


# ---------------------------------------------------------------- commands: tasks

def read_detail(args, ctx):
    path = getattr(args, "detail_file", None)
    text = getattr(args, "detail", None)
    if path and text:
        raise HarnessError("Give --detail or --detail-file, not both: only one is kept. Put everything in the file.")
    if path:
        p = Path(path).expanduser()
        if not p.is_absolute():
            tries = [Path.cwd() / p, Path(ctx.root) / p]
            p = next((c for c in tries if c.exists()), tries[1])
        if not p.exists():
            raise HarnessError("Detail file not found: %s" % p)
        return stored_path(ctx.root, p)
    if text:
        if len(text) > SUMMARY_MAX:
            raise HarnessError(
                "The detail is %d characters; --detail takes one short line (max %d). Write the full detail in a "
                "file and pass it with --detail-file. A coordinator or owner writes it under .harness/notes/; a "
                "worker writes it in its task folder." % (len(text), SUMMARY_MAX))
        return "text:" + text
    return None


def create_task(ctx, title, state, detail, role=None, assigned=None, after=None, kind=None,
                job=None, priority=0, parent=None, requested_by=None):
    check_short(title, 160, "Title")
    deps = [d.strip().upper() for d in (after or "").split(",") if d.strip()]
    for d in deps:
        get_task(ctx.con, d)
    if assigned and not get_session(ctx.con, assigned):
        raise HarnessError("No session named '%s'." % assigned)
    tid = next_id(ctx.con, "T")
    ts = now()
    ctx.con.execute(
        "INSERT INTO tasks(id,title,detail_path,kind,role,assigned_to,state,priority,depends_on,job,parent,"
        "requested_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (tid, title, detail, kind or "default", role, assigned, state, priority, json.dumps(deps), job, parent,
         requested_by, ts, ts))
    event(ctx.con, "proposed" if state == "proposed" else "added", ctx.who, tid, title)
    return tid


def cmd_add(args):
    ctx = Ctx(args)
    if ctx.me and ctx.me["role"] not in ("coordinator", "guest"):
        raise HarnessError("Workers do not add tasks to the queue. Use 'propose' for a follow-up "
                           "(the coordinator decides) or 'request ROLE' to ask a specialist.")
    state = "proposed" if args.proposed else "queued"
    earlier = None
    if args.result:
        earlier = Path(args.result).expanduser()
        if not earlier.is_absolute():
            tries = [Path.cwd() / earlier, Path(ctx.root) / earlier]
            earlier = next((c for c in tries if c.exists()), tries[1])
        if not earlier.exists():
            raise HarnessError("Result not found: %s" % earlier)
    with tx(ctx.con):
        tid = create_task(ctx, args.title, state, read_detail(args, ctx), role=args.role, assigned=args.to,
                          after=args.after, kind=args.kind, job=args.job, priority=args.priority, parent=args.parent)
        if earlier is not None:
            set_task(ctx.con, tid, state="done", result_path=stored_path(ctx.root, earlier), done_by="earlier-work",
                     done_at=now(), summary="Earlier result, never independently checked")
            event(ctx.con, "done", "earlier-work", tid, "registered for review")
    if earlier is not None:
        print("Added %s as an earlier result waiting to be checked: %s" % (tid, args.title))
        if check_for(ctx.cfg, args.kind).get("script"):
            run_check(ctx, tid)
    else:
        print("Added %s%s: %s" % (tid, " (held as a proposal until it is accepted)" if args.proposed else "", args.title))
    after_change(ctx)


def cmd_propose(args):
    ctx = Ctx(args, need_session=True)
    parent = (args.task or ctx.me["current_task"] or "").upper() or None
    with tx(ctx.con):
        tid = create_task(ctx, args.title, "proposed", read_detail(args, ctx), kind=args.kind, parent=parent,
                          requested_by=ctx.who)
    print("Proposed %s. The coordinator decides whether it is queued." % tid)
    after_change(ctx)


def cmd_request(args):
    ctx = Ctx(args, need_session=True)
    parent = ctx.me["current_task"]
    with tx(ctx.con):
        kind = args.kind or (args.role if args.role in (ctx.cfg.get("checks") or {}) else None)
        tid = create_task(ctx, args.title, "queued", read_detail(args, ctx), role=args.role, kind=kind,
                          parent=parent, requested_by=ctx.who, priority=args.priority)
        if args.wait and parent:
            set_task(ctx.con, parent, state="blocked", block_on=tid,
                     block_reason="waiting for %s (%s)" % (tid, args.role))
            set_session(ctx.con, ctx.who, current_task=None)
            event(ctx.con, "blocked", ctx.who, parent, "waiting for %s" % tid)
    print("Request %s is queued for role '%s'." % (tid, args.role))
    if args.wait and parent:
        print("%s is blocked until %s finishes; it will return to the queue by itself. Run 'next'." % (parent, tid))
    after_change(ctx)


def cmd_accept(args):
    ctx = Ctx(args)
    with tx(ctx.con):
        t = get_task(ctx.con, args.task)
        if t["state"] != "proposed":
            raise HarnessError("%s is %s, not proposed." % (t["id"], t["state"]))
        fields = {"state": "queued"}
        if args.to:
            if not get_session(ctx.con, args.to):
                raise HarnessError("No session named '%s'." % args.to)
            fields["assigned_to"] = args.to
        if args.role:
            fields["role"] = args.role
        if args.priority is not None:
            fields["priority"] = args.priority
        set_task(ctx.con, t["id"], **fields)
        event(ctx.con, "accepted", ctx.who, t["id"])
    print("%s is queued." % t["id"])
    after_change(ctx)


def cmd_edit(args):
    ctx = Ctx(args)
    if ctx.me and ctx.me["role"] not in ("coordinator", "guest"):
        raise HarnessError("Only the coordinator or the owner changes a task. Use 'propose' or 'ask'.")
    with tx(ctx.con):
        t = get_task(ctx.con, args.task)
        if t["state"] not in ("proposed", "queued", "blocked", "needs_owner"):
            raise HarnessError("%s is %s; only tasks nobody is working on can be changed. Requeue it first." % (t["id"], t["state"]))
        fields, changed = {}, []
        if args.title:
            check_short(args.title, 160, "Title")
            fields["title"] = args.title
            changed.append("title")
        detail = read_detail(args, ctx)
        if detail:
            fields["detail_path"] = detail
            changed.append("detail")
        if args.kind:
            fields["kind"] = args.kind
            changed.append("kind=%s" % args.kind)
        if args.role:
            fields["role"] = None if args.role == "worker" else args.role
            fields["assigned_to"] = None
            changed.append("for role %s" % args.role)
        if args.to:
            if not get_session(ctx.con, args.to):
                raise HarnessError("No session named '%s'." % args.to)
            fields["assigned_to"] = args.to
            changed.append("to %s" % args.to)
        if args.unassign:
            fields["assigned_to"] = None
            changed.append("unassigned")
        if args.priority is not None:
            fields["priority"] = args.priority
            changed.append("priority %d" % args.priority)
        if not fields:
            raise HarnessError("Nothing to change. Give --title, --detail, --detail-file, --kind, --role, --to, --unassign or --priority.")
        set_task(ctx.con, t["id"], **fields)
        event(ctx.con, "edited", ctx.who, t["id"], ", ".join(changed))
    print("%s changed: %s" % (t["id"], ", ".join(changed)))
    after_change(ctx)


def cmd_unverify(args):
    ctx = Ctx(args)
    check_short(args.reason, SUMMARY_MAX, "Reason")
    if ctx.me and ctx.me["role"] not in ("reviewer", "coordinator", "guest"):
        raise HarnessError("Only the owner, the coordinator or a reviewer can withdraw a verification.")
    with tx(ctx.con):
        t = get_task(ctx.con, args.task)
        if t["state"] != "verified":
            raise HarnessError("%s is %s, not verified." % (t["id"], t["state"]))
        set_task(ctx.con, t["id"], state="done", verified_by=None, verified_at=None, reviewer=None,
                 check_passed=None, verify_note="verification withdrawn: %s" % args.reason)
        event(ctx.con, "unverified", ctx.who, t["id"], args.reason)
    print("%s is no longer verified. It is 'done' again and waits to be checked." % t["id"])
    later = built_on(ctx.con, t["id"])
    if later:
        print("Work already built on it: %s. It now shows as provisional on the board." % ", ".join(later))
    after_change(ctx)


def cmd_trial_clear(args):
    ctx = Ctx(args)
    if not args.yes:
        raise HarnessError("This cancels every task labelled as a trial (job 'trial'), whatever its state, and closes "
                           "the sessions that joined with the specialty 'trial'. Real tasks and recorded case results "
                           "are untouched. Add --yes to go ahead.")
    with tx(ctx.con):
        rows = ctx.con.execute("SELECT id FROM tasks WHERE job='trial' AND state<>'cancelled'").fetchall()
        for r in rows:
            set_task(ctx.con, r["id"], state="cancelled", block_reason="trial run, cleared")
        gone = ctx.con.execute("SELECT name FROM sessions WHERE specialty='trial' AND state<>'ended'").fetchall()
        for g in gone:
            set_session(ctx.con, g["name"], state="ended", current_task=None, stop_reason="trial over")
        event(ctx.con, "trial_cleared", ctx.who, None, "%d task(s), %d session(s)" % (len(rows), len(gone)))
    idx = session_index()
    names = set(g["name"] for g in gone)
    for sid, e in list(idx.items()):
        if e.get("project") == ctx.project and e.get("name") in names:
            del idx[sid]
    save_session_index(idx)
    print("Cleared %d trial task(s) and closed %d trial session(s). Case results stay on record." % (len(rows), len(gone)))
    after_change(ctx)


def cmd_reject(args):
    ctx = Ctx(args)
    check_short(args.reason, SUMMARY_MAX, "Reason")
    with tx(ctx.con):
        t = get_task(ctx.con, args.task)
        if t["state"] != "proposed":
            raise HarnessError("%s is %s, not proposed. Use 'cancel' for queued work." % (t["id"], t["state"]))
        set_task(ctx.con, t["id"], state="rejected", block_reason=args.reason)
        event(ctx.con, "rejected", ctx.who, t["id"], args.reason)
    print("%s rejected." % t["id"])
    after_change(ctx)


def cmd_assign(args):
    ctx = Ctx(args)
    with tx(ctx.con):
        t = get_task(ctx.con, args.task)
        target = get_session(ctx.con, args.to)
        if not target:
            raise HarnessError("No session named '%s'." % args.to)
        if t["state"] not in ("queued", "in_progress", "blocked", "proposed"):
            raise HarnessError("%s is %s and cannot be assigned." % (t["id"], t["state"]))
        if t["state"] == "in_progress" and t["assigned_to"] and t["assigned_to"] != args.to:
            set_session(ctx.con, t["assigned_to"], current_task=None)
            event(ctx.con, "reassigned", ctx.who, t["id"], "%s -> %s" % (t["assigned_to"], args.to))
        set_task(ctx.con, t["id"], assigned_to=args.to,
                 state="queued" if t["state"] in ("in_progress", "proposed") else t["state"])
        event(ctx.con, "assigned", ctx.who, t["id"], args.to)
    print("%s is assigned to %s. It will pick it up when it next stops or runs 'next'." % (t["id"], args.to))
    after_change(ctx)


def cmd_requeue(args):
    ctx = Ctx(args)
    check_short(args.reason, SUMMARY_MAX, "Reason")
    with tx(ctx.con):
        t = get_task(ctx.con, args.task)
        if t["state"] not in ("in_progress", "blocked", "needs_owner"):
            raise HarnessError("%s is %s; only in-progress, blocked or waiting tasks can be requeued." % (t["id"], t["state"]))
        if t["assigned_to"]:
            s = get_session(ctx.con, t["assigned_to"])
            if s and s["current_task"] == t["id"]:
                set_session(ctx.con, s["name"], current_task=None)
        set_task(ctx.con, t["id"], state="queued", block_on=None, block_reason=None,
                 assigned_to=None if args.unassign else t["assigned_to"])
        event(ctx.con, "requeued", ctx.who, t["id"], args.reason or "")
    print("%s is back in the queue." % t["id"])
    after_change(ctx)


def cmd_next(args):
    ctx = Ctx(args, need_session=True)
    if meta_get(ctx.con, "drain"):
        print("The project is draining for a handoff: no new tasks. Record where you are and stop.")
        return
    with tx(ctx.con):
        cur = ctx.me["current_task"]
        if cur:
            t = get_task(ctx.con, cur)
            if (ctx.me["role"] == "reviewer" and t["state"] == "done") or t["state"] == "in_progress":
                print("You already have %s." % cur)
                task = t
            else:
                set_session(ctx.con, ctx.who, current_task=None)
                task = None
        else:
            task = None
        if task is None:
            task = pick_next(ctx.con, ctx.cfg, ctx.me)
            if task is None:
                set_session(ctx.con, ctx.who, stop_reason="idle: nothing queued")
                print("Nothing is queued for you. You may stop; the coordinator will assign work.")
                return
            claim(ctx.con, ctx.root, ctx.me, task)
    show_task(ctx, task["id"])
    after_change(ctx)


def show_task(ctx, tid):
    t = get_task(ctx.con, tid)
    print("%s  [%s]  %s" % (t["id"], t["state"], t["title"]))
    for label, key in (("kind", "kind"), ("for role", "role"), ("assigned to", "assigned_to"),
                       ("requested by", "requested_by"), ("follows", "parent"), ("job", "job"),
                       ("blocked on", "block_on"), ("reason", "block_reason"),
                       ("summary", "summary"), ("done by", "done_by"), ("verified by", "verified_by")):
        if t[key]:
            print("  %-13s %s" % (label + ":", t[key]))
    if t["result_path"]:
        print("  %-13s %s" % ("result:", resolve_path(ctx.root, t["result_path"])))
    deps = json.loads(t["depends_on"] or "[]")
    if deps:
        print("  %-13s %s" % ("after:", ", ".join(deps)))
    for d_ in ctx.con.execute("SELECT * FROM decisions WHERE task=? ORDER BY asked_at", (t["id"],)).fetchall():
        print("  decision %s:  %s" % (d_["id"], d_["question"]))
        print("    owner's answer: %s" % (d_["answer"] if d_["state"] == "answered" else "(not yet answered)"))
    shaky = shaky_bases(ctx.con, t)
    if shaky:
        print("  PROVISIONAL:  built on %s, which was sent back by review and is not verified" % ", ".join(shaky))
    if t["verify_note"]:
        label = {"verified": "review note:", "done": "earlier failure (check it was fixed):"}.get(t["state"], "sent back because:")
        print("  %s %s" % (label, t["verify_note"]))
    d = t["detail_path"]
    if d and d.startswith("text:"):
        print("  detail:       %s" % d[5:])
    elif d:
        print("  detail file:  %s" % resolve_path(ctx.root, d))
        try:
            body = resolve_path(ctx.root, d).read_text(encoding="utf-8")
            if len(body) <= 4000:
                print("  ----- detail -----\n%s\n  ----- end detail -----" % body.rstrip())
        except (OSError, UnicodeDecodeError):
            pass
    print("  task folder:  %s" % work_dir(ctx.root, t["id"]))
    notes = ctx.con.execute("SELECT ts,session,detail FROM events WHERE task=? AND kind='checkpoint' ORDER BY id DESC LIMIT 5",
                            (t["id"],)).fetchall()
    for n in reversed(notes):
        print("  checkpoint %s %s: %s" % (n["ts"][:16], n["session"], n["detail"]))


def cmd_show(args):
    ctx = Ctx(args, write=False)
    show_task(ctx, args.task)


def cmd_list(args):
    ctx = Ctx(args, write=False)
    q = "SELECT * FROM tasks"
    cond, params = [], []
    if args.state:
        cond.append("state=?")
        params.append(args.state)
    elif not args.all:
        cond.append("state IN (%s)" % ",".join("?" * len(OPEN_STATES)))
        params.extend(OPEN_STATES)
    if args.mine and ctx.me:
        cond.append("(assigned_to=? OR done_by=?)")
        params.extend([ctx.who, ctx.who])
    if cond:
        q += " WHERE " + " AND ".join(cond)
    q += " ORDER BY CAST(SUBSTR(id,2) AS INTEGER)"
    rows = ctx.con.execute(q, params).fetchall()
    if not rows:
        print("No tasks.")
    for t in rows:
        waits = ""
        if t["state"] == "queued" and not deps_ready(ctx.con, ctx.cfg, t):
            waits = "  [waits for %s]" % ", ".join(json.loads(t["depends_on"] or "[]"))
        print("%-5s %-12s %-10s %s%s" % (t["id"], t["state"], t["assigned_to"] or t["role"] or "-", t["title"], waits))


def my_task(ctx, tid):
    tid = (tid or (ctx.me["current_task"] if ctx.me else None) or "").upper()
    if not tid:
        raise HarnessError("Which task? You have no current task; pass the task id.")
    return get_task(ctx.con, tid)


def cmd_checkpoint(args):
    ctx = Ctx(args, need_session=True)
    check_short(args.note, NOTE_MAX, "Checkpoint note")
    with tx(ctx.con):
        t = my_task(ctx, args.task)
        event(ctx.con, "checkpoint", ctx.who, t["id"], args.note)
    print("Checkpoint recorded on %s." % t["id"])


def cmd_done(args):
    ctx = Ctx(args)
    check_short(args.summary, SUMMARY_MAX, "Summary")
    with tx(ctx.con):
        t = my_task(ctx, args.task)
        if t["state"] != "in_progress":
            raise HarnessError("%s is %s, not in progress." % (t["id"], t["state"]))
        if ctx.me and t["assigned_to"] != ctx.who:
            raise HarnessError("%s belongs to %s." % (t["id"], t["assigned_to"]))
        rp = Path(args.result).expanduser()
        if not rp.is_absolute():       # accept a path relative to where the command ran, the project, or the task folder
            tries = [Path.cwd() / rp, Path(ctx.root) / rp, work_dir(ctx.root, t["id"]) / rp]
            rp = next((c for c in tries if c.exists()), tries[1])
        rp = Path(os.path.abspath(str(rp)))
        if not rp.exists():
            raise HarnessError("Result path does not exist: %s. A task is done only when its result is on disk." % rp)
        set_task(ctx.con, t["id"], state="done", result_path=stored_path(ctx.root, rp), summary=args.summary,
                 done_by=t["assigned_to"] or ctx.who, done_at=now(), check_passed=None, reviewer=None)
        if t["assigned_to"]:
            set_session(ctx.con, t["assigned_to"], current_task=None)
        event(ctx.con, "done", ctx.who, t["id"], args.summary)
        if not ctx.cfg.get("deps_need_verified"):
            release_dependents(ctx.con, t["id"])
        made = []
        for f in args.followup or []:
            made.append(create_task(ctx, f, "proposed", None, parent=t["id"], requested_by=ctx.who))
    print("%s is done (not yet verified)." % t["id"])
    if made:
        print("Follow-ups proposed: %s" % ", ".join(made))
    chk = check_for(ctx.cfg, t["kind"])
    if chk.get("script"):
        run_check(ctx, t["id"])
    print("Run 'next' for your next task.")
    after_change(ctx)


def cmd_block(args):
    ctx = Ctx(args)
    check_short(args.reason, SUMMARY_MAX, "Reason")
    manager = (not ctx.me) or ctx.me["role"] in ("coordinator", "guest")
    with tx(ctx.con):
        t = my_task(ctx, args.task)
        if manager and t["state"] in ("queued", "proposed"):
            on = args.on.upper() if args.on else None
            if on:
                get_task(ctx.con, on)
            set_task(ctx.con, t["id"], state="blocked", block_reason=args.reason, block_on=on)
            event(ctx.con, "blocked", ctx.who, t["id"], args.reason)
            print("%s is blocked: %s. It returns to the queue with 'requeue'%s." % (
                t["id"], args.reason, ", or by itself when %s finishes" % on if on else ""))
            after_change(ctx)
            return
        if not ctx.me:
            raise HarnessError("%s is %s. Without a session you can block only a queued or proposed task." % (t["id"], t["state"]))
        if t["state"] != "in_progress":
            raise HarnessError("%s is %s, not in progress." % (t["id"], t["state"]))
        on = args.on.upper() if args.on else None
        if on:
            get_task(ctx.con, on)
        set_task(ctx.con, t["id"], state="blocked", block_reason=args.reason, block_on=on)
        set_session(ctx.con, ctx.who, current_task=None, stop_reason="blocked: %s" % args.reason)
        event(ctx.con, "blocked", ctx.who, t["id"], args.reason)
    print("%s is blocked: %s. Run 'next' for other work." % (t["id"], args.reason))
    after_change(ctx)


def cmd_ask(args):
    ctx = Ctx(args)
    check_short(args.question, NOTE_MAX, "Question")
    with tx(ctx.con):
        tid = (args.task or (ctx.me["current_task"] if ctx.me else None) or "").upper() or None
        did = next_id(ctx.con, "D")
        ctx.con.execute("INSERT INTO decisions(id,task,asked_by,question,state,asked_at) VALUES(?,?,?,?,?,?)",
                        (did, tid, ctx.who, args.question, "open", now()))
        if tid:
            t = get_task(ctx.con, tid)
            if t["state"] == "in_progress" and ctx.me:
                set_task(ctx.con, tid, state="needs_owner", block_reason="decision %s" % did)
                set_session(ctx.con, ctx.who, current_task=None, stop_reason="waiting on owner: %s" % did)
        event(ctx.con, "asked", ctx.who, tid, "%s: %s" % (did, args.question))
    print("Question %s is in the owner's decision queue. Do not ask it in chat. Run 'next' for other work." % did)
    after_change(ctx)


def cmd_answer(args):
    ctx = Ctx(args)
    check_short(args.text, NOTE_MAX, "Answer")
    with tx(ctx.con):
        d = ctx.con.execute("SELECT * FROM decisions WHERE id=?", (args.decision.upper(),)).fetchone()
        if not d:
            raise HarnessError("No decision %s." % args.decision)
        ctx.con.execute("UPDATE decisions SET answer=?, state='answered', answered_at=? WHERE id=?",
                        (args.text, now(), d["id"]))
        released = False
        if d["task"]:
            t = get_task(ctx.con, d["task"])
            if t["state"] == "needs_owner":
                set_task(ctx.con, t["id"], state="queued", block_reason=None)
                released = True
        event(ctx.con, "answered", ctx.who, d["task"], "%s: %s" % (d["id"], args.text))
    print("Decision %s answered.%s" % (d["id"], " %s is back in the queue." % d["task"] if released else ""))
    after_change(ctx)


def cmd_cancel(args):
    ctx = Ctx(args)
    check_short(args.reason, SUMMARY_MAX, "Reason")
    with tx(ctx.con):
        t = get_task(ctx.con, args.task)
        if t["state"] in ("verified", "cancelled", "rejected"):
            raise HarnessError("%s is already %s." % (t["id"], t["state"]))
        if t["assigned_to"]:
            s = get_session(ctx.con, t["assigned_to"])
            if s and s["current_task"] == t["id"]:
                set_session(ctx.con, s["name"], current_task=None)
        set_task(ctx.con, t["id"], state="cancelled", block_reason=args.reason)
        event(ctx.con, "cancelled", ctx.who, t["id"], args.reason)
    print("%s cancelled." % t["id"])
    after_change(ctx)


# ---------------------------------------------------------------- commands: checking

def run_check(ctx, tid):
    t = get_task(ctx.con, tid)
    chk = check_for(ctx.cfg, t["kind"])
    script = chk.get("script")
    if not script:
        print("No checker script is configured for kind '%s'; this task needs a reviewer." % t["kind"])
        return None
    cmd = (script.replace("{result}", str(resolve_path(ctx.root, t["result_path"])) if t["result_path"] else "").replace("{task}", t["id"])
           .replace("{workdir}", str(work_dir(ctx.root, t["id"]))).replace("{python}", sys.executable))
    try:
        proc = subprocess.run(cmd, shell=True, cwd=str(ctx.root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=int(chk.get("timeout", 600)))
        out = proc.stdout.decode("utf-8", "replace")
        ok = proc.returncode == 0
    except subprocess.TimeoutExpired:
        out, ok = "checker timed out", False
    tail = " | ".join(out.strip().splitlines()[-3:])[:NOTE_MAX]
    needs_review = chk.get("review", True)
    if needs_review == "sample":
        every = max(1, int(chk.get("sample_every", 5)))
        needs_review = (int(re.sub(r"\D", "", tid) or 0) % every == 0) or (t["fail_count"] or 0) > 0
    with tx(ctx.con):
        if ok and not needs_review:
            set_task(ctx.con, tid, state="verified", check_passed=1, verified_by="check", verified_at=now(),
                     verify_note=tail)
            event(ctx.con, "check_pass", "check", tid, tail)
            event(ctx.con, "verified", "check", tid, "by script")
            release_dependents(ctx.con, tid)
            print("Checker passed: %s is verified." % tid)
        elif ok:
            set_task(ctx.con, tid, check_passed=1, verify_note=None if t["check_passed"] == 0 else t["verify_note"])
            event(ctx.con, "check_pass", "check", tid, tail)
            print("Checker passed: %s now waits for a reviewer." % tid)
        else:
            set_task(ctx.con, tid, state="queued", check_passed=0, assigned_to=t["done_by"], verify_note=tail,
                     fail_count=(t["fail_count"] or 0) + 1)
            event(ctx.con, "check_fail", "check", tid, tail)
            print("Checker FAILED: %s is back in the queue for %s.\n%s" % (tid, t["done_by"], out.strip()[-1500:]))
    return ok


def cmd_check(args):
    ctx = Ctx(args)
    t = get_task(ctx.con, args.task)
    if t["state"] != "done":
        raise HarnessError("%s is %s; only done tasks can be checked." % (t["id"], t["state"]))
    run_check(ctx, t["id"])
    after_change(ctx)


def cmd_verify(args):
    ctx = Ctx(args)
    if args.note and len(args.note) > NOTE_MAX:
        raise HarnessError("The note is %d characters; a review note is at most %d. Write the full review in a file "
                           "in the task's review/ folder and name that file in a short note." % (len(args.note), NOTE_MAX))
    if args.passed == args.failed:
        raise HarnessError("Say exactly one of --pass or --fail.")
    with tx(ctx.con):
        t = get_task(ctx.con, args.task)
        if t["state"] != "done":
            raise HarnessError("%s is %s; only done tasks can be verified." % (t["id"], t["state"]))
        if ctx.me:
            if ctx.me["name"] == t["done_by"]:
                raise HarnessError("You did %s, so you cannot verify it. The author never grades its own work." % t["id"])
            if ctx.me["role"] != "reviewer":
                raise HarnessError("Only a reviewer session (or the owner, with no session) can verify. "
                                   "The coordinator plans the work, so it does not grade it.")
        elif not args.owner:
            raise HarnessError("No session identified. If the owner is verifying by hand, add --owner.")
        who = ctx.who
        if ctx.me and ctx.me["current_task"] == t["id"]:
            set_session(ctx.con, who, current_task=None)
        if args.passed:
            set_task(ctx.con, t["id"], state="verified", verified_by=who, verify_note=args.note, verified_at=now())
            event(ctx.con, "verified", who, t["id"], args.note or "")
            release_dependents(ctx.con, t["id"])
        else:
            if not args.note:
                raise HarnessError("A failed review needs --note saying what is wrong, so the worker can fix it.")
            set_task(ctx.con, t["id"], state="queued", assigned_to=t["done_by"], verify_note=args.note,
                     fail_count=(t["fail_count"] or 0) + 1, reviewer=None)
            event(ctx.con, "verify_fail", who, t["id"], args.note)
    if args.passed:
        print("%s verified." % t["id"])
    else:
        later = built_on(ctx.con, t["id"])
        if later:
            print("Work already built on %s: %s. It now shows as provisional on the board." % (t["id"], ", ".join(later)))
        author = get_session(ctx.con, t["done_by"]) if t["done_by"] else None
        if author is not None and author["state"] != "ended":
            print("%s sent back to %s." % (t["id"], t["done_by"]))
        else:
            print("%s sent back. Its author's session has gone, so it is in the queue for another worker." % t["id"])
    after_change(ctx)


def cmd_promote(args):
    ctx = Ctx(args)
    t = get_task(ctx.con, args.task)
    if t["state"] != "verified":
        raise HarnessError("%s is %s. Only verified results are promoted into the project's main data." % (t["id"], t["state"]))
    if t["promoted_at"]:
        raise HarnessError("%s was already promoted at %s." % (t["id"], t["promoted_at"]))
    cmd = (ctx.cfg.get("promote") or {}).get("cmd")
    if cmd:
        full = (cmd.replace("{result}", str(resolve_path(ctx.root, t["result_path"])) if t["result_path"] else "").replace("{task}", t["id"])
                .replace("{python}", sys.executable))
        proc = subprocess.run(full, shell=True, cwd=str(ctx.root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = proc.stdout.decode("utf-8", "replace")
        if proc.returncode != 0:
            with tx(ctx.con):
                event(ctx.con, "promote_fail", ctx.who, t["id"], out.strip()[-300:])
            raise HarnessError("Promotion command failed:\n%s" % out.strip()[-1500:])
        print(out.strip()[-800:])
    with tx(ctx.con):
        set_task(ctx.con, t["id"], promoted_at=now())
        event(ctx.con, "promoted", ctx.who, t["id"], "by command" if cmd else "recorded by hand")
    print("%s promoted%s." % (t["id"], "" if cmd else " (no promote command is configured; this only records it)"))
    after_change(ctx)


def cmd_case(args):
    ctx = Ctx(args)
    cdir = hdir(ctx.root) / "cases"
    if args.action == "list":
        names = sorted(p.name for p in cdir.iterdir() if p.is_dir()) if cdir.is_dir() else []
        if not names:
            print("No known-answer cases yet.")
        for n in names:
            last = ctx.con.execute("SELECT ts,detail FROM events WHERE kind='case' AND detail LIKE ? ORDER BY id DESC LIMIT 1",
                                   (n + ":%",)).fetchone()
            print("%-30s %s" % (n, "%s %s" % (last["detail"].split(":", 2)[1], fmt_age(last["ts"])) if last else "never run"))
    elif args.action == "add":
        if not args.name:
            raise HarnessError("Give the case a short name.")
        d = cdir / args.name
        d.mkdir(parents=True, exist_ok=True)
        f = d / "case.md"
        if not f.exists():
            write_text(f, "# %s\n\n## Input\n\n(what the agent is given)\n\n## Known answer\n\n(what a correct result "
                          "contains)\n\n## How to tell\n\n(script to run, or what a reviewer looks for)\n" % args.name)
        print("Case file: %s" % f)
    elif args.action == "record":
        if args.result not in ("pass", "fail"):
            raise HarnessError("Result must be pass or fail.")
        check_short(args.note, SUMMARY_MAX, "Note")
        with tx(ctx.con):
            event(ctx.con, "case", ctx.who, None, "%s:%s:%s" % (args.name, args.result, args.note or ""))
        print("Recorded %s: %s" % (args.name, args.result))


# ---------------------------------------------------------------- board (the coordinator's view)

def classify(con, cfg, s):
    """One word for where a session stands, plus a short note."""
    stale = float(cfg.get("stale_minutes", 20))
    age = age_minutes(s["last_heartbeat"])
    cur = con.execute("SELECT * FROM tasks WHERE id=?", (s["current_task"],)).fetchone() if s["current_task"] else None
    if s["state"] == "closed":
        if cur is not None and cur["state"] == "in_progress":
            return "stale", "%s; its session window was closed" % cur["id"]
        return "closed", "session window closed"
    if cur is not None and cur["state"] in ("in_progress", "done"):
        if s["in_tool"] and age is not None and age >= stale:
            return "long-call", "%s on %s; inside one %s call for %dm" % (cur["id"], cur["title"][:40], s["in_tool"], age)
        if age is None or age >= stale:
            return "stale", "%s; no activity for %s" % (cur["id"], "%dm" % age if age is not None else "ever")
        return "working", "%s %s" % (cur["id"], cur["title"][:50])
    nxt = pick_next(con, cfg, s)
    if nxt is not None:
        return "has-next", "idle; %s is queued for it" % nxt["id"]
    waiting = con.execute("SELECT id,state,block_reason FROM tasks WHERE assigned_to=? AND state IN ('blocked','needs_owner')",
                          (s["name"],)).fetchall()
    if waiting:
        w = waiting[0]
        return ("needs-owner" if w["state"] == "needs_owner" else "blocked"), "%s: %s" % (w["id"], w["block_reason"] or "")
    return "idle", "nothing queued for it"


def board_data(con, cfg):
    sessions = []
    for s in con.execute("SELECT * FROM sessions WHERE state<>'ended' ORDER BY role, name").fetchall():
        if s["role"] == "guest" and not s["held_task"]:
            continue
        status, note = classify(con, cfg, s) if s["role"] != "coordinator" else ("coordinator", "")
        if status == "closed" or (s["role"] == "coordinator" and s["state"] == "closed"):
            continue
        sessions.append({"name": s["name"], "role": s["role"], "specialty": s["specialty"], "status": status,
                         "note": note, "last_heartbeat": s["last_heartbeat"], "current_task": s["current_task"],
                         "stop_reason": s["stop_reason"], "machine": s["machine"]})
    tasks = [dict(r) for r in con.execute("SELECT * FROM tasks ORDER BY CAST(SUBSTR(id,2) AS INTEGER)").fetchall()]
    decisions = [dict(r) for r in con.execute("SELECT * FROM decisions WHERE state='open' ORDER BY asked_at").fetchall()]
    counts = {}
    for t in tasks:
        counts[t["state"]] = counts.get(t["state"], 0) + 1
    return {"sessions": sessions, "tasks": tasks, "decisions": decisions, "counts": counts,
            "drain": meta_get(con, "drain"), "stale_minutes": cfg.get("stale_minutes", 20)}


def coordinator_gaps(con, cfg, data=None):
    """Things the coordinator should act on now. Empty list means the floor is covered."""
    data = data or board_data(con, cfg)
    gaps = []
    if data["drain"]:
        return gaps
    unassigned = [t for t in data["tasks"] if t["state"] == "queued" and not t["assigned_to"]]
    nobody = not [s for s in data["sessions"] if s["role"] != "coordinator"]
    if nobody and unassigned:
        wanted = sorted(set(t["role"] or "worker" for t in unassigned))
        gaps.append("%d task(s) are queued and no working session has joined yet. Start sessions for: %s"
                    % (len(unassigned), ", ".join(wanted)))
    for s in data["sessions"]:
        if s["status"] == "idle" and s["role"] != "reviewer" and not s["specialty"]:
            gaps.append("%s is idle with nothing queued: assign it a task, or note why none fits" % s["name"])
        elif s["status"] == "stale":
            gaps.append("%s looks stuck (%s): requeue its task or reassign it" % (s["name"], s["note"]))
        elif s["status"] == "blocked":
            gaps.append("%s is blocked (%s) with nothing else queued: give it other work or clear the blocker"
                        % (s["name"], s["note"]))
        elif s["status"] == "working" and s["role"] != "reviewer":
            ahead = [t for t in data["tasks"] if t["state"] == "queued" and t["assigned_to"] == s["name"]]
            if not ahead and not unassigned:
                gaps.append("%s has no task queued after its current one: queue one so it never finds the queue empty" % s["name"])
    have = set()
    for s in data["sessions"]:
        have.update([s["role"], s["specialty"]])
    orphan = {}
    for t in unassigned:
        wanted = t["role"] or "worker"
        if wanted not in have:
            orphan.setdefault(wanted, []).append(t["id"])
    for wanted, ids in sorted(orphan.items()) if not nobody else []:
        gaps.append("%d queued task(s) are addressed to role '%s' and no session has that role: %s "
                    "(start such a session, or re-address them with assign)" % (len(ids), wanted, ", ".join(ids[:8])))
    for t in data["tasks"]:
        if t["state"] in ("in_progress", "done", "verified"):
            row = con.execute("SELECT * FROM tasks WHERE id=?", (t["id"],)).fetchone()
            bases = shaky_bases(con, row)
            if bases:
                gaps.append("%s (%s) was built on %s, which was sent back by review and is not verified: treat %s as "
                            "provisional and have it rechecked once %s is settled"
                            % (t["id"], t["state"], ", ".join(bases), t["id"], ", ".join(bases)))
    props = [t for t in data["tasks"] if t["state"] == "proposed"]
    if props:
        gaps.append("%d proposed follow-up(s) wait for your decision: %s (accept or reject)"
                    % (len(props), ", ".join(t["id"] for t in props[:8])))
    if (cfg.get("promote") or {}).get("cmd"):
        waiting = [t for t in data["tasks"] if t["state"] == "verified" and not t["promoted_at"]]
        if waiting:
            gaps.append("%d verified result(s) are not yet in the project data: run promote on %s"
                        % (len(waiting), ", ".join(t["id"] for t in waiting[:8])))
    review_roles = [s for s in data["sessions"] if s["role"] == "reviewer"]
    need_review = [t for t in data["tasks"] if t["state"] == "done" and check_for(cfg, t["kind"]).get("review", True)]
    if need_review and not review_roles:
        gaps.append("%d result(s) are done but unverified and no reviewer session has joined: %s"
                    % (len(need_review), ", ".join(t["id"] for t in need_review[:8])))
    return gaps


def cmd_board(args):
    ctx = Ctx(args, write=False)
    data = board_data(ctx.con, ctx.cfg)
    if ctx.me and ctx.me["role"] == "coordinator" and not parked_info(ctx.root):
        with tx(ctx.con):
            event(ctx.con, "board", ctx.who, None, "")
            set_session(ctx.con, ctx.who, last_heartbeat=now(), state="active")
    print("PROJECT %s   %s" % (ctx.project, now()))
    if parked_info(ctx.root):
        print("PARKED on this computer: handed off at %s. Run 'resume' to work here." % parked_info(ctx.root).get("stamped_at"))
    if data["drain"]:
        print("DRAINING since %s: no new tasks; sessions are finishing and recording where they are." % data["drain"])
    print("\nSESSIONS")
    if not data["sessions"]:
        print("  (none have joined)")
    for s in data["sessions"]:
        print("  %-10s %-11s %-11s %s  [%s]" % (s["name"], s["specialty"] or s["role"], s["status"].upper(),
                                              s["note"], fmt_age(s["last_heartbeat"])))
    print("\nTASKS  " + "  ".join("%s=%d" % (k, data["counts"].get(k, 0)) for k in OPEN_STATES + ("verified",)))
    for state in ("in_progress", "blocked", "needs_owner", "proposed", "queued", "done"):
        rows = [t for t in data["tasks"] if t["state"] == state]
        for t in rows[:25]:
            extra = t["block_reason"] or t["summary"] or ""
            print("  %-5s %-12s %-10s %s%s" % (t["id"], state, t["assigned_to"] or t["role"] or "-", t["title"][:60],
                                              "  -- " + extra[:70] if extra else ""))
        if len(rows) > 25:
            print("  ... and %d more %s" % (len(rows) - 25, state))
    print("\nDECISIONS WAITING FOR THE OWNER")
    if not data["decisions"]:
        print("  (none)")
    for d in data["decisions"]:
        print("  %-4s %-6s asked %s by %s: %s" % (d["id"], d["task"] or "-", fmt_age(d["asked_at"]), d["asked_by"], d["question"]))
    gaps = coordinator_gaps(ctx.con, ctx.cfg, data)
    print("\nNEEDS ACTION")
    if not gaps:
        print("  (nothing: every session has work or a recorded reason)")
    for g in gaps:
        print("  - " + g)


def cmd_log(args):
    ctx = Ctx(args, write=False)
    q, params = "SELECT * FROM events", []
    if args.kind:
        q += " WHERE kind=?"
        params.append(args.kind)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(args.n)
    for e in reversed(ctx.con.execute(q, params).fetchall()):
        print("%s %-8s %-12s %-5s %s" % (e["ts"][:19], e["session"] or "-", e["kind"], e["task"] or "", e["detail"] or ""))


# ---------------------------------------------------------------- views

def render(root, con, cfg, min_interval=0):
    h = hdir(root)
    status = h / "STATUS.md"
    if min_interval and status.exists() and (time.time() - status.stat().st_mtime) < min_interval:
        return
    data = board_data(con, cfg)
    project = cfg.get("project") or Path(root).name
    lines = ["# %s: status" % project, "",
             "Generated %s on %s. Do not edit: this file is rewritten from the ledger." % (now(), machine()), ""]
    if data["drain"]:
        lines += ["**Draining for handoff since %s.**" % data["drain"], ""]
    lines += ["## Decisions waiting for the owner", ""]
    if data["decisions"]:
        for d in data["decisions"]:
            lines.append("- **%s** (%s, from %s, asked %s): %s" % (d["id"], d["task"] or "no task", d["asked_by"],
                                                                   (d["asked_at"] or "")[:16].replace("T", " ") + " UTC",
                                                                   d["question"]))
    else:
        lines.append("None.")
    lines += ["", "## Sessions", "", "| Session | Role | Status | Note | Last activity |", "|---|---|---|---|---|"]
    for s in data["sessions"]:
        lines.append("| %s | %s | %s | %s | %s |" % (s["name"], s["specialty"] or s["role"], s["status"],
                                                   (s["note"] or "").replace("|", "/"), s["last_heartbeat"] or ""))
    lines += ["", "## Tasks", "", "| Task | State | Who | Title | Note |", "|---|---|---|---|---|"]
    for t in data["tasks"]:
        if t["state"] in ("cancelled", "rejected"):
            continue
        note = t["block_reason"] or t["summary"] or ""
        lines.append("| %s | %s | %s | %s | %s |" % (t["id"], t["state"], t["assigned_to"] or t["role"] or "",
                                                   t["title"].replace("|", "/"), note.replace("|", "/")))
    write_text(status, "\n".join(lines) + "\n")
    payload = {"project": project, "generated": now(), "machine": machine(), "data": data,
               "parked": bool(parked_info(root))}
    write_text(h / "dashboard.html", DASHBOARD.replace("__DATA__", json.dumps(payload).replace("</", "<\\/")))


DASHBOARD = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="20">
<title>Harness status</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1c1a;--mute:#6b6862;--line:#dedbd4;--ok:#2f7d4f;--warn:#b7791f;--bad:#b3392f;--info:#35608f}
@media (prefers-color-scheme: dark){:root{--bg:#161614;--card:#21201d;--ink:#eceae4;--mute:#a09c93;--line:#383630;--ok:#6fc28f;--warn:#e0b05a;--bad:#ec7b70;--info:#8fb6e0}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1200px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:22px;margin:0}h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute);margin:28px 0 10px}
.sub{color:var(--mute);font-size:13px;margin-top:2px}
.banner{border:1px solid var(--warn);color:var(--warn);border-radius:8px;padding:8px 12px;margin-top:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:11px 13px}
.card b{font-size:15px}.tag{float:right;font-size:11px;font-weight:600;padding:2px 7px;border-radius:99px;border:1px solid currentColor}
.working{color:var(--ok)}.has-next,.coordinator,.long-call{color:var(--info)}.idle,.blocked{color:var(--warn)}.stale,.needs-owner{color:var(--bad)}
.note{color:var(--mute);font-size:13px;margin-top:5px;overflow-wrap:anywhere}
.dec{border-left:4px solid var(--bad)}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;align-items:start}
.col{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}
.col h3{margin:0 0 8px;font-size:13px;color:var(--mute)}
.t{border-top:1px solid var(--line);padding:7px 0;font-size:13px;overflow-wrap:anywhere}.t:first-of-type{border-top:0}
.id{font-weight:600;font-variant-numeric:tabular-nums}.who{color:var(--mute)}
.empty{color:var(--mute);font-size:13px}
</style></head><body><main>
<h1 id="title"></h1><div class="sub" id="sub"></div><div id="banners"></div>
<h2>Decisions waiting for you</h2><div id="decisions" class="grid"></div>
<h2>Sessions</h2><div id="sessions" class="grid"></div>
<h2>Tasks</h2><div id="tasks" class="cols"></div>
</main><script>
const P = __DATA__;
const D = P.data, $ = id => document.getElementById(id);
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function ago(ts){ if(!ts) return "never"; const m=(Date.now()-new Date(ts).getTime())/60000;
  if(m<1) return "just now"; if(m<90) return Math.floor(m)+" min ago"; if(m<2880) return Math.floor(m/60)+" h ago"; return Math.floor(m/1440)+" d ago"; }
$("title").textContent = P.project + ": status";
$("sub").textContent = "Read-only view of the ledger. Written " + ago(P.generated) + " on " + P.machine + ". This page reloads every 20 seconds.";
let b = "";
if (P.parked) b += '<div class="banner">Parked on this computer: the project was handed off. Run resume to work here.</div>';
if (D.drain) b += '<div class="banner">Draining for handoff: no new tasks are being handed out.</div>';
if ((Date.now()-new Date(P.generated).getTime())/60000 > 30) b += '<div class="banner">This view is more than 30 minutes old. Nothing has written to the ledger since then.</div>';
$("banners").innerHTML = b;
$("decisions").innerHTML = D.decisions.length ? D.decisions.map(d =>
  '<div class="card dec"><b>'+esc(d.id)+'</b> <span class="who">'+esc(d.task||"")+' from '+esc(d.asked_by)+', '+ago(d.asked_at)+'</span><div class="note" style="color:inherit">'+esc(d.question)+'</div></div>').join("")
  : '<div class="empty">Nothing is waiting on you.</div>';
$("sessions").innerHTML = D.sessions.length ? D.sessions.map(s =>
  '<div class="card"><span class="tag '+esc(s.status)+'">'+esc(s.status)+'</span><b>'+esc(s.name)+'</b> <span class="who">'+esc(s.specialty||s.role)+'</span><div class="note">'+esc(s.note||s.stop_reason||"")+'</div><div class="note">last activity '+ago(s.last_heartbeat)+'</div></div>').join("")
  : '<div class="empty">No sessions have joined.</div>';
const cols = [["proposed","Proposed"],["queued","Queued"],["in_progress","In progress"],["blocked","Blocked"],["needs_owner","Needs you"],["done","Done, unverified"],["verified","Verified"]];
$("tasks").innerHTML = cols.map(([k,label]) => { const rows = D.tasks.filter(t => t.state===k);
  const shown = k==="verified" ? rows.slice(-12).reverse() : rows;
  return '<div class="col"><h3>'+label+' ('+rows.length+')</h3>'+(shown.length ? shown.map(t =>
    '<div class="t"><span class="id">'+esc(t.id)+'</span> '+esc(t.title)+'<div class="who">'+esc(t.assigned_to||t.role||"unassigned")+(t.block_reason?' · '+esc(t.block_reason):'')+(t.summary?' · '+esc(t.summary):'')+'</div></div>').join("")
    : '<div class="empty">none</div>')+'</div>'; }).join("");
</script></body></html>
"""


def cmd_status(args):
    ctx = Ctx(args, write=False)
    render(ctx.root, ctx.con, ctx.cfg)
    if args.print_it:
        print((hdir(ctx.root) / "STATUS.md").read_text(encoding="utf-8"))
    else:
        print("Status file: %s" % (hdir(ctx.root) / "STATUS.md"))
        print("Dashboard:   %s" % (hdir(ctx.root) / "dashboard.html"))


def cmd_overview(args):
    rows = []
    for name, entry in sorted(registry()["projects"].items()):
        path = entry.get("paths", {}).get(machine())
        item = {"project": name, "path": path, "tier": entry.get("tier"), "error": None}
        try:
            if not path or not ledger_path(path).exists():
                raise HarnessError("no ledger on this computer" if entry.get("tier") != "lite" else "Lite tier: see STATE.md")
            con = connect(path, readonly=True)
            data = board_data(con, load_config(path))
            item.update(decisions=len(data["decisions"]),
                        active=len([s for s in data["sessions"] if s["status"] in ("working", "long-call", "coordinator")]),
                        stuck=len([s for s in data["sessions"] if s["status"] == "stale"]),
                        idle=len([s for s in data["sessions"] if s["status"] == "idle"]),
                        open_tasks=sum(data["counts"].get(k, 0) for k in ("queued", "in_progress", "blocked", "needs_owner")),
                        unverified=data["counts"].get("done", 0), drain=bool(data["drain"]),
                        parked=bool(parked_info(path)))
        except Exception as exc:
            item["error"] = str(exc)
        rows.append(item)
    total = sum(r.get("active", 0) for r in rows)
    print("ALL PROJECTS on %s   sessions working: %d" % (machine(), total))
    for r in rows:
        if r["error"]:
            print("  %-18s %s" % (r["project"], r["error"]))
        else:
            print("  %-18s decisions=%d working=%d stuck=%d idle=%d open-tasks=%d unverified=%d%s%s" % (
                r["project"], r["decisions"], r["active"], r["stuck"], r["idle"], r["open_tasks"], r["unverified"],
                " DRAINING" if r["drain"] else "", " PARKED" if r["parked"] else ""))
    html = ["<!doctype html><meta charset='utf-8'><meta http-equiv='refresh' content='30'><title>All harnesses</title>",
            "<style>body{font:15px system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;background:#f6f5f2;color:#1d1c1a}"
            "@media (prefers-color-scheme: dark){body{background:#161614;color:#eceae4}}"
            "table{border-collapse:collapse;width:100%}td,th{padding:8px 10px;border-bottom:1px solid #8884;text-align:left}"
            ".bad{color:#b3392f;font-weight:600}</style>",
            "<h1>All projects</h1><p>Sessions working across projects: <b>%d</b>. Written %s on %s.</p>" % (total, now(), machine()),
            "<table><tr><th>Project</th><th>Waiting on you</th><th>Working</th><th>Stuck</th><th>Idle</th><th>Open tasks</th><th>Unverified</th></tr>"]
    for r in rows:
        if r["error"]:
            html.append("<tr><td>%s</td><td colspan=6>%s</td></tr>" % (r["project"], r["error"]))
        else:
            link = (hdir(r["path"]) / "dashboard.html").resolve().as_uri()
            html.append("<tr><td><a href='%s'>%s</a></td><td class='%s'>%d</td><td>%d</td><td class='%s'>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>" % (
                link, r["project"], "bad" if r["decisions"] else "", r["decisions"], r["active"],
                "bad" if r["stuck"] else "", r["stuck"], r["idle"], r["open_tasks"], r["unverified"]))
    html.append("</table>")
    out = home() / "overview.html"
    write_text(out, "\n".join(html))
    print("Overview page: %s" % out)


# ---------------------------------------------------------------- saving and handoff

def snapshot(root, con, cfg, label="auto"):
    sdir = hdir(root) / "snapshots"
    sdir.mkdir(parents=True, exist_ok=True)
    dest = sdir / ("ledger-%s-%s.sqlite" % (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), label))
    out = sqlite3.connect(str(dest))
    try:
        con.backup(out)
    finally:
        out.close()
    keep = int((cfg.get("autosave") or {}).get("keep", 20))
    autos = sorted(sdir.glob("ledger-*-auto.sqlite"))
    for old in autos[:-keep] if keep > 0 else []:
        try:
            old.unlink()
        except OSError:
            pass
    return dest


def maybe_autosave(root, con, cfg):
    """Called from the hook after tool calls. Cheap unless the interval has passed."""
    auto = cfg.get("autosave") or {}
    minutes = float(auto.get("minutes", 5) or 0)
    if minutes <= 0:
        return False
    last = meta_get(con, "last_snapshot")
    if last and (age_minutes(last) or 0) < minutes:
        return False
    with tx(con):
        last = meta_get(con, "last_snapshot")
        if last and (age_minutes(last) or 0) < minutes:
            return False
        meta_set(con, "last_snapshot", now())
    dest = snapshot(root, con, cfg, "auto")
    try:
        travel = hdir(root) / "handoff" / "autosave.sqlite"
        travel.parent.mkdir(parents=True, exist_ok=True)
        tmp = travel.with_name("autosave.sqlite.new")
        shutil.copyfile(str(dest), str(tmp))
        replace_file(tmp, travel)
    except OSError:
        pass
    cmd = auto.get("cmd")
    if cmd:
        try:
            subprocess.Popen(cmd, shell=True, cwd=str(root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             stdin=subprocess.DEVNULL)
        except OSError:
            pass
    return True


SETUP_PARTS = ("config.json", "roles", "tools", "cases", "STATE.md", "check.py")


def cmd_snapshot(args):
    name = args.project or project_by_cwd(os.getcwd())
    if not name:
        raise HarnessError("Which project? Pass --project NAME.")
    root = project_root(name)
    cfg = load_config(root)
    con = connect(root) if ledger_path(root).exists() else None
    if not args.setup:
        if con is None:
            raise HarnessError("This project has no ledger to copy. Use 'snapshot --setup' to copy its rules and role files.")
        print("Snapshot: %s" % snapshot(root, con, cfg, "manual"))
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = hdir(root) / "snapshots" / ("setup-%s" % stamp)
    n = 2
    while dest.exists():                      # two undo points in the same second
        dest = hdir(root) / "snapshots" / ("setup-%s-%d" % (stamp, n))
        n += 1
    dest.mkdir(parents=True)
    kept = []
    for part in SETUP_PARTS:
        src = hdir(root) / part
        if src.is_dir():
            shutil.copytree(str(src), str(dest / part))
            kept.append(part + "/")
        elif src.exists():
            shutil.copyfile(str(src), str(dest / part))
            kept.append(part)
    write_json(dest / "MANIFEST.json", {"present": [p.rstrip("/") for p in kept], "made": now(), "machine": machine()})
    if con is not None:
        out = sqlite3.connect(str(dest / "ledger.sqlite"))
        try:
            con.backup(out)
        finally:
            out.close()
        kept.append("ledger.sqlite")
        with tx(con):
            event(con, "undo_point", None, None, dest.name)
    print("Undo point: %s" % dest.name)
    print("It holds: %s" % ", ".join(kept))
    print("To go back to it: restore %s   (add --ledger to put the ledger back too)" % dest.name)


def cmd_restore(args):
    name = args.project or project_by_cwd(os.getcwd())
    if not name:
        raise HarnessError("Which project? Pass --project NAME.")
    root = project_root(name)
    require_writable(root)
    src = hdir(root) / "snapshots" / args.name
    if not src.is_dir() or not args.name.startswith("setup-"):
        have = sorted(p.name for p in (hdir(root) / "snapshots").glob("setup-*"))
        raise HarnessError("No undo point named '%s'. Available: %s" % (args.name, ", ".join(have) or "none"))
    if not args.yes:
        raise HarnessError("This puts the rules file, role files, tools and cases back as they were at %s%s. A copy "
                           "of the present state is taken first. Add --yes to go ahead."
                           % (args.name, ", and the ledger too" if args.ledger else ""))
    print("First, a copy of the state as it is now:")
    keep_args = argparse.Namespace(project=name, setup=True)
    cmd_snapshot(keep_args)
    manifest = read_json(src / "MANIFEST.json", None)
    for part in SETUP_PARTS:
        saved, live = src / part, hdir(root) / part
        if manifest is not None and part not in manifest.get("present", []) and live.exists():
            # this part did not exist at the undo point; it is safe in the copy just taken
            if live.is_dir():
                shutil.rmtree(str(live))
            else:
                live.unlink()
            continue
        if saved.is_dir():
            if live.exists():
                shutil.rmtree(str(live))
            shutil.copytree(str(saved), str(live))
        elif saved.exists():
            shutil.copyfile(str(saved), str(live))
    if args.ledger and (src / "ledger.sqlite").exists():
        lp = ledger_path(root)
        for suffix in ("-wal", "-shm"):
            side = Path(str(lp) + suffix)
            if side.exists():
                side.unlink()
        shutil.copyfile(str(src / "ledger.sqlite"), str(lp))
    if ledger_path(root).exists():
        con = connect(root)
        with tx(con):
            event(con, "restored", None, None, "%s%s" % (args.name, " with ledger" if args.ledger else ""))
        render(root, con, load_config(root))
    print("Restored from %s." % args.name)


def cmd_end_sessions(args):
    ctx = Ctx(args)
    if not args.yes:
        raise HarnessError("This closes every session in the ledger and returns their unfinished tasks to the queue "
                           "with their checkpoints. Use it after the sessions have stopped, before changing roles or "
                           "rules, so that no session carries on under old instructions. Add --yes to go ahead.")
    requeued, closed = [], []
    with tx(ctx.con):
        for s_ in ctx.con.execute("SELECT * FROM sessions WHERE state<>'ended'").fetchall():
            if s_["current_task"]:
                t = ctx.con.execute("SELECT state FROM tasks WHERE id=?", (s_["current_task"],)).fetchone()
                if t and t["state"] == "in_progress":
                    set_task(ctx.con, s_["current_task"], state="queued", assigned_to=None)
                    requeued.append(s_["current_task"])
            set_session(ctx.con, s_["name"], state="ended", current_task=None, stop_reason="closed for reconfiguration")
            closed.append(s_["name"])
        ctx.con.execute("DELETE FROM meta WHERE key='drain'")
        event(ctx.con, "sessions_ended", ctx.who, None, ", ".join(closed))
    idx = session_index()
    for sid, e in list(idx.items()):
        if e.get("project") == ctx.project:
            del idx[sid]
    save_session_index(idx)
    print("Closed %d session(s): %s" % (len(closed), ", ".join(closed) or "none"))
    if requeued:
        print("Back in the queue (any checkpoints they had are kept): %s" % ", ".join(requeued))
    print("Start fresh sessions and have each one join.")
    after_change(ctx)


def cmd_unregister(args):
    reg = registry()
    entry = reg["projects"].get(args.name)
    if not entry:
        raise HarnessError("No project named '%s' in the registry." % args.name)
    if not args.yes:
        raise HarnessError("This removes '%s' from this computer's list of harness projects. Its folder and its "
                           ".harness folder are left exactly as they are. Add --yes to go ahead." % args.name)
    path = entry.get("paths", {}).pop(machine(), None)
    if not entry.get("paths"):
        del reg["projects"][args.name]
    save_registry(reg)
    idx = session_index()
    for sid, e in list(idx.items()):
        if e.get("project") == args.name:
            del idx[sid]
    save_session_index(idx)
    print("'%s' is no longer a harness project on this computer. Nothing in %s was changed." % (args.name, path or "its folder"))


def busy_sessions(con, since):
    """Sessions still mid-task with no checkpoint recorded since the drain began."""
    out = []
    for s in con.execute("SELECT * FROM sessions WHERE state<>'ended' AND current_task IS NOT NULL").fetchall():
        t = con.execute("SELECT state FROM tasks WHERE id=?", (s["current_task"],)).fetchone()
        if not t or t["state"] != "in_progress":
            continue
        cp = con.execute("SELECT 1 FROM events WHERE kind='checkpoint' AND task=? AND ts>=? LIMIT 1",
                         (s["current_task"], since)).fetchone()
        if not cp:
            out.append(s)
    return out


def cmd_drain(args):
    ctx = Ctx(args)
    if args.off:
        with tx(ctx.con):
            ctx.con.execute("DELETE FROM meta WHERE key='drain'")
            event(ctx.con, "drain_off", ctx.who)
        print("Drain cancelled. Tasks are being handed out again.")
        after_change(ctx)
        return
    since = meta_get(ctx.con, "drain")
    if not since:
        since = now()
        with tx(ctx.con):
            meta_set(ctx.con, "drain", since)
            event(ctx.con, "drain_on", ctx.who)
        print("Draining since %s. No new tasks will be handed out." % since)
        print("Each session will be told, the next time it tries to stop or finishes a tool call, to record where it is.")
    busy = busy_sessions(ctx.con, since)
    if busy:
        print("Still working without a checkpoint (%d):" % len(busy))
        for s in busy:
            print("  %-8s %s  last activity %s" % (s["name"], s["current_task"], fmt_age(s["last_heartbeat"])))
        print("Run 'drain' again to re-check. When it is clear: 'stamp' for a handoff to another computer, or "
              "'end-sessions' before reconfiguring. A session that is gone for good will never clear; if the owner "
              "confirms it is closed, go on without it (its unrecorded work is lost).")
    else:
        print("All sessions have finished or recorded where they are. You can run 'stamp' (for a handoff) or "
              "'end-sessions' (before reconfiguring).")
    after_change(ctx)


def file_sha256(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_shell(cmd, root, label):
    print("Running %s: %s" % (label, cmd))
    proc = subprocess.run(cmd, shell=True, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = proc.stdout.decode("utf-8", "replace").strip()
    if out:
        print(out[-1500:])
    return proc.returncode == 0


def cmd_stamp(args):
    ctx = Ctx(args)
    since = meta_get(ctx.con, "drain")
    if not since and not args.force:
        raise HarnessError("Run 'drain' first so sessions finish and record where they are. (--force skips this.)")
    busy = busy_sessions(ctx.con, since or now())
    if busy and not args.force:
        raise HarnessError("%d session(s) are still mid-task with no checkpoint: %s. Wait, or use --force and accept "
                           "that their unrecorded work is lost." % (len(busy), ", ".join(s["name"] for s in busy)))
    hd = hdir(ctx.root) / "handoff"
    hd.mkdir(parents=True, exist_ok=True)
    with tx(ctx.con):
        event(ctx.con, "stamp", ctx.who, None, "machine=%s" % machine())
    ctx.con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    snap = hd / "ledger.sqlite"
    tmp = hd / "ledger.sqlite.new"
    if tmp.exists():
        tmp.unlink()
    out = sqlite3.connect(str(tmp))
    try:
        ctx.con.backup(out)
    finally:
        out.close()
    replace_file(tmp, snap)
    last_event = ctx.con.execute("SELECT MAX(id) AS n FROM events").fetchone()["n"]
    stamp = {"project": ctx.project, "machine": machine(), "stamped_at": now(), "last_event": last_event,
             "sha256": file_sha256(snap), "harness_version": VERSION}
    write_json(hd / "STAMP.json", stamp)
    render(ctx.root, ctx.con, ctx.cfg)
    push = (ctx.cfg.get("handoff") or {}).get("push_cmd")
    pushed = None
    if push:
        pushed = run_shell(push, ctx.root, "the save command")
        if not pushed:
            print("\nThe save command FAILED, so the other computer cannot see this handoff yet. "
                  "The project is NOT parked. Fix the problem and run 'stamp' again.")
            sys.exit(1)
    write_json(hdir(ctx.root) / "local" / "PARKED.json", stamp)
    print("\nHandoff stamped: %s on %s, ledger event %s." % (stamp["stamped_at"], machine(), last_event))
    print("This computer is now parked for project %s: writes are refused until 'resume'." % ctx.project)
    if not push:
        print("No save command is configured (handoff.push_cmd), so YOU must get the project folder, "
              "including .harness/handoff/, to the other computer.")


def cmd_resume(args):
    name = args.project or project_by_cwd(os.getcwd())
    if not name:
        raise HarnessError("Which project? Pass --project NAME.")
    root = project_root(name)
    cfg = load_config(root)
    hd = hdir(root) / "handoff"
    pull = (cfg.get("handoff") or {}).get("pull_cmd")
    if pull and not args.no_pull:
        if not run_shell(pull, root, "the fetch command"):
            raise HarnessError("The fetch command failed, so this copy may not be the latest. Nothing was changed.")
    stamp = read_json(hd / "STAMP.json", None)
    parked = parked_info(root)
    lp = ledger_path(root)
    if not stamp:
        if parked:
            raise HarnessError("This computer is parked but no handoff stamp was found in %s." % hd)
        print("No handoff stamp found: nothing to resume from. This computer keeps working on its own copy.")
        return
    snap = hd / "ledger.sqlite"
    if not snap.exists() or file_sha256(snap) != stamp.get("sha256"):
        raise HarnessError("The handoff ledger does not match its stamp (%s). The copy is incomplete or still "
                           "syncing. Nothing was changed; fetch again and retry." % snap)
    local_last, local_stamped = None, False
    if lp.exists():
        c = sqlite3.connect(str(lp), timeout=30)
        try:
            local_last = c.execute("SELECT MAX(id) FROM events").fetchone()[0]
            row = c.execute("SELECT 1 FROM events WHERE kind='stamp' AND id=?", (stamp["last_event"],)).fetchone()
            local_stamped = bool(row)
        except sqlite3.Error:
            pass
        c.close()
    same_machine = stamp.get("machine") == machine()
    if same_machine and local_last == stamp.get("last_event"):
        action = "unpark"
    elif local_last is not None and local_last > stamp.get("last_event", 0) and not (same_machine or local_stamped) and not parked:
        if not args.force:
            raise HarnessError(
                "This computer's ledger has work the handoff does not (local event %s, handoff event %s from %s at %s). "
                "Two computers have diverged. Decide which copy to keep; --force replaces the local ledger with the "
                "handoff (the local one is kept in snapshots/)." % (local_last, stamp["last_event"], stamp["machine"], stamp["stamped_at"]))
        action = "replace"
    elif local_last is not None and local_last >= stamp.get("last_event", 0) and (same_machine or local_stamped):
        action = "unpark"
    else:
        action = "replace"
    if action == "replace":
        if lp.exists():
            keep = hdir(root) / "snapshots" / ("ledger-%s-before-resume.sqlite" % datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(lp), str(keep))
        for suffix in ("-wal", "-shm"):
            side = Path(str(lp) + suffix)
            if side.exists():
                side.unlink()
        shutil.copyfile(str(snap), str(lp))
    pk = hdir(root) / "local" / "PARKED.json"
    if pk.exists():
        pk.unlink()
    con = connect(root)
    requeued = []
    with tx(con):
        con.execute("DELETE FROM meta WHERE key='drain'")
        meta_set(con, "active_machine", machine())
        for s in con.execute("SELECT * FROM sessions WHERE state<>'ended'").fetchall():
            if s["current_task"]:
                t = con.execute("SELECT state FROM tasks WHERE id=?", (s["current_task"],)).fetchone()
                if t and t["state"] == "in_progress":
                    set_task(con, s["current_task"], state="queued", assigned_to=None)
                    requeued.append(s["current_task"])
            set_session(con, s["name"], state="ended", current_task=None, stop_reason="handoff to %s" % machine())
        event(con, "resume", None, None, "on %s from stamp %s by %s" % (machine(), stamp["stamped_at"], stamp["machine"]))
    idx = session_index()
    for sid, e in list(idx.items()):
        if e.get("project") == name:
            del idx[sid]
    save_session_index(idx)
    render(root, con, cfg)
    print("Resumed project %s on %s." % (name, machine()))
    print("Working from the handoff stamped %s on %s (ledger event %s)." % (stamp["stamped_at"], stamp["machine"], stamp["last_event"]))
    if action == "replace":
        print("The local ledger was replaced with the handoff copy; the old one is in .harness/snapshots/.")
    if requeued:
        print("Tasks that were mid-flight are back in the queue with their checkpoints: %s" % ", ".join(requeued))
    print("All earlier sessions are closed. Start fresh sessions and have each one join.")


def cmd_reset(args):
    ctx = Ctx(args)
    if not args.yes:
        raise HarnessError("This archives the ledger and starts an empty one (rules, roles, cases and task folders "
                           "stay). It is meant for clearing a trial run at setup. Add --yes to go ahead.")
    lp = ledger_path(ctx.root)
    keep = snapshot(ctx.root, ctx.con, ctx.cfg, "before-reset")
    case_results = [tuple(r) for r in ctx.con.execute("SELECT ts,session,kind,task,detail FROM events WHERE kind='case'").fetchall()]
    ctx.con.close()
    work = hdir(ctx.root) / "work"
    if work.is_dir() and any(work.iterdir()):
        shutil.move(str(work), str(hdir(ctx.root) / "snapshots" / (keep.name.replace(".sqlite", "") + "-work")))
        work.mkdir()
    for suffix in ("", "-wal", "-shm"):
        side = Path(str(lp) + suffix)
        if side.exists():
            side.unlink()
    con = sqlite3.connect(str(lp), timeout=30, isolation_level=None)
    con.executescript(SCHEMA)
    con.execute("PRAGMA journal_mode=WAL")
    con.row_factory = sqlite3.Row
    meta_set(con, "schema_version", str(SCHEMA_VERSION))
    meta_set(con, "created_at", now())
    meta_set(con, "active_machine", machine())
    event(con, "init", None, None, "reset; previous ledger kept as %s" % keep.name)
    con.executemany("INSERT INTO events(ts,session,kind,task,detail) VALUES(?,?,?,?,?)", case_results)
    idx = session_index()
    for sid, e in list(idx.items()):
        if e.get("project") == ctx.project:
            del idx[sid]
    save_session_index(idx)
    render(ctx.root, con, ctx.cfg)
    print("Ledger reset. The previous one is kept at %s" % keep)
    print("Recorded case results were carried over (%d)." % len(case_results))


# ---------------------------------------------------------------- hook support

def heartbeat(root, con, cfg, name, phase, tool=None):
    """Record activity. phase is 'pre' or 'post'."""
    if parked_info(root):
        return
    if phase == "pre":
        con.execute("UPDATE sessions SET last_heartbeat=?, state='active', in_tool=?, in_tool_since=? WHERE name=?",
                    (now(), tool, now(), name))
    else:
        con.execute("UPDATE sessions SET last_heartbeat=?, state='active', in_tool=NULL, in_tool_since=NULL, stop_blocks=0 "
                    "WHERE name=?", (now(), name))
        maybe_autosave(root, con, cfg)
        try:
            render(root, con, cfg, min_interval=30)
        except Exception:
            pass


def stop_decision(root, con, cfg, sess):
    """Decide whether a session may end its turn. Returns (allow, message)."""
    name = sess["name"]
    if parked_info(root):
        return True, "parked"
    if sess["stop_blocks"]:
        # We refused once already and the session did nothing since: let it go, and record that.
        with tx(con):
            set_session(con, name, stop_blocks=0, state="stopped",
                        stop_reason=sess["stop_reason"] or "stopped after one refusal")
            event(con, "stopped", name, sess["current_task"], "after refusal")
        return True, "second attempt"
    drain = meta_get(con, "drain")
    cur = con.execute("SELECT * FROM tasks WHERE id=?", (sess["current_task"],)).fetchone() if sess["current_task"] else None
    cmd = "%s --as %s" % (this_command(), name)

    def refuse(reason_kind, msg):
        with tx(con):
            set_session(con, name, stop_blocks=1, stop_reason=reason_kind)
            event(con, "stop_refused", name, cur["id"] if cur is not None else None, reason_kind)
        return False, msg

    def allow(reason):
        with tx(con):
            set_session(con, name, state="stopped", stop_reason=reason)
            event(con, "stopped", name, None, reason)
        return True, reason

    if sess["role"] == "coordinator":
        gaps = coordinator_gaps(con, cfg)
        if gaps:
            return refuse("coordinator: open gaps",
                          "Before you stop, the board shows work to hand out:\n- " + "\n- ".join(gaps[:8]) +
                          "\nAct on these with the ledger command (%s), or if one cannot be acted on, say why in your "
                          "report to the owner. Then stop." % cmd)
        return allow("coordinator: floor covered")
    if cur is not None and cur["state"] == "in_progress" and sess["role"] != "reviewer":
        if drain:
            cp = con.execute("SELECT 1 FROM events WHERE kind='checkpoint' AND task=? AND ts>=? LIMIT 1",
                             (cur["id"], drain)).fetchone()
            if cp:
                return allow("drained with checkpoint on %s" % cur["id"])
            return refuse("draining: no checkpoint",
                          "The project is being handed off to another computer. Save your files, then record exactly "
                          "where you are so a fresh session can continue:\n  %s checkpoint \"what is finished, what "
                          "is next, where the files are\"\nThen stop. Do not start anything new." % cmd)
        return refuse("task unfinished",
                      "Your task %s (%s) is not recorded as finished. Either continue it, or record why you are "
                      "stopping, with one of:\n  %s done %s --result <path> --summary \"...\"\n  %s block %s --reason "
                      "\"...\"\n  %s ask \"question for the owner\"\nThen run 'next'." % (
                          cur["id"], cur["title"], cmd, cur["id"], cmd, cur["id"], cmd))
    if cur is not None and sess["role"] == "reviewer" and cur["state"] == "done":
        return refuse("review unfinished",
                      "Your review of %s is not recorded. Run:\n  %s verify %s --pass --note \"...\"   or   --fail "
                      "--note \"what is wrong\"" % (cur["id"], cmd, cur["id"]))
    if drain:
        return allow("drained")
    if sess["held_task"] or sess["role"] in ("worker", "reviewer"):
        if sess["held_task"] or sess["role"] == "reviewer":
            with tx(con):
                fresh = get_session(con, name)
                nxt = pick_next(con, cfg, fresh)
                if nxt is not None:
                    claim(con, root, fresh, nxt)
                    set_session(con, name, stop_blocks=1)
                    event(con, "handed_out", name, nxt["id"], "at stop")
            if nxt is not None:
                verb = "review" if sess["role"] == "reviewer" else "task"
                return False, ("Your next %s is %s: %s\nRun this for the details, then do it:\n  %s show %s"
                               % (verb, nxt["id"], nxt["title"], cmd, nxt["id"]))
    waiting = con.execute("SELECT id,state FROM tasks WHERE assigned_to=? AND state IN ('blocked','needs_owner')",
                          (name,)).fetchall()
    if waiting:
        return allow("waiting: " + ", ".join("%s %s" % (w["id"], w["state"]) for w in waiting))
    return allow("idle: nothing queued")


def role_rules(cfg, sess):
    """Limits for a session: its base role's, with any entry named after its specialty laid on top."""
    roles = cfg.get("roles") or {}
    rules = dict(roles.get(sess["role"] or "worker") or {})
    rules.update(roles.get(sess["specialty"] or "") or {})
    return rules


def match_any(rel, patterns):
    rel = rel.replace("\\", "/")
    for pat in patterns:
        pat = pat.replace("\\", "/").replace("**", "*")
        if fnmatch.fnmatchcase(rel, pat) or fnmatch.fnmatchcase(rel, pat.rstrip("/*") + "/*") or rel == pat.rstrip("/*"):
            return True
    return False


def temp_roots():
    roots = {tempfile.gettempdir(), "/tmp", "/private/tmp", "/var/folders", "/private/var/folders"}
    cdir = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    roots.add(os.path.join(cdir, "projects"))
    roots.add(os.path.join(cdir, "plans"))
    return [r for r in roots if r]


def write_allowed(root, cfg, sess, target):
    """May this session write this file with a file tool? Returns (ok, reason, rule)."""
    target = Path(target).expanduser()
    if not target.is_absolute():
        target = Path(sess["cwd"] or os.getcwd()) / target
    root = Path(root)
    role = sess["role"] or "worker"
    rules = role_rules(cfg, sess)
    if not is_inside(target, root):
        if role == "guest" or cfg.get("outside_writes") == "allow":
            return True, "", ""
        if any(is_inside(target, t) for t in temp_roots()):
            return True, "", ""
        if match_any(str(target).replace("\\", "/"), cfg.get("extra_write_paths") or []):
            return True, "", ""
        return False, ("%s is outside project %s. While you work in this harness, write only in your task folder; "
                       "if this file is really needed there, ask the owner with the 'ask' command." % (target, cfg.get("project"))), "write:outside-project"
    rel = os.path.relpath(norm(target), norm(root)).replace("\\", "/")
    generated = (rel.startswith(".harness/ledger.sqlite") or rel in (".harness/STATUS.md", ".harness/dashboard.html")
                 or rel.startswith(".harness/handoff/") or rel.startswith(".harness/local/")
                 or rel.startswith(".harness/snapshots/"))
    owner_files = (rel == ".harness/config.json" or rel.startswith(".harness/roles/")
                   or rel.startswith(".harness/cases/") or rel.startswith(".harness/tools/"))
    if generated or (owner_files and role != "guest"):
        return False, ("%s belongs to the harness. The ledger and status files change only through the ledger "
                       "command (editing a status file changes nothing: it is regenerated). Rules, role files, "
                       "checker scripts and known-answer cases are the owner's: raise it with the 'ask' command." % rel), "write:harness-file"
    if match_any(rel, cfg.get("protected_paths") or []):
        return False, ("%s is protected project data. Write your result in your task folder, mark the task done, and "
                       "it reaches the project data through 'promote' after it is verified." % rel), "write:protected"
    if role == "guest":
        return True, "", ""
    pats = list(cfg.get("extra_write_paths") or [])
    cur = sess["current_task"]
    for p in rules.get("write") or []:
        if "{work}" in p:
            if cur:
                pats.append(p.replace("{work}", ".harness/work/%s" % cur))
        else:
            pats.append(p)
    if match_any(rel, pats):
        return True, "", ""
    where = (".harness/work/%s/" % cur) if cur else "a task folder (you have no current task: run 'next' first)"
    hint = ""
    if not sess["held_task"]:
        hint = (" If the owner opened this session for something other than harness work, run "
                "'join %s --role guest' to lift the worker limits." % (cfg.get("project") or "PROJECT"))
    return False, ("As a %s you may write only in %s. %s is outside it. Put the file there; if the project needs "
                   "it elsewhere, that happens at promotion.%s" % (role, where, rel, hint)), "write:outside-task-folder"


ALTER_VERBS = re.compile(r"^\s*(?:sudo\s+)?(rm|mv|tee|truncate|dd|chmod|chown|shred|sed\s+-i\S*|perl\s+-\S*i\S*)\b")
COPY_VERBS = re.compile(r"^\s*(?:sudo\s+)?(cp|rsync|ln|install|scp)\b")
SQLITE_VERB = re.compile(r"^\s*(?:sudo\s+)?sqlite3\b")
FETCH_HINT = re.compile(r"(?i)\b(curl|wget|aria2c|httpie|lynx|scp|rsync|git\s+clone|git\s+fetch|git\s+pull|pip3?\s+install|"
                        r"npm\s+i|npx|yt-dlp|invoke-webrequest|iwr|requests|urllib|httpx|playwright|selenium)\b|https?://")


def path_token_re(pattern):
    token = pattern.replace("**", "").replace("*", "").replace("?", "").strip("/")
    if not token:
        return None, token
    return re.compile(r"(?<![\w.-])" + re.escape(token) + r"(?![\w-])"), token


def bash_allowed(root, cfg, sess, command):
    """Pattern check on a shell command. Returns (ok, reason, rule). Cannot see inside scripts."""
    role = sess["role"] or "worker"
    full = command or ""
    # Only the parts of a chained command that are not the ledger command itself are checked below.
    segments = [seg for seg in re.split(r"&&|\|\||[;|\n]", full) if seg.strip() and "harness.py" not in seg]
    cmd = " ; ".join(segments)
    if "ledger.sqlite" in cmd:
        return False, ("The ledger is changed and read only through the ledger command, never directly. "
                       "Use the command's 'board', 'list', 'show' or 'log' to read it."), "shell:ledger"
    for item in cfg.get("bash_deny") or []:
        try:
            if re.search(item.get("pattern", "$^"), full):
                return False, item.get("reason") or "This command is blocked by a project rule.", "shell:project-rule"
        except re.error:
            continue
    if FETCH_HINT.search(cmd):                         # naming a site in a note or a question is fine; fetching is not
        for host in cfg.get("blocked_hosts") or []:
            h = host.get("host") if isinstance(host, dict) else host
            if h and h.lower() in cmd.lower():
                why = host.get("reason") if isinstance(host, dict) else None
                return False, "Project rule: do not fetch from %s. %s" % (h, why or ""), "shell:blocked-host"
    if role == "guest" or not segments:
        return True, "", ""
    if role in ("worker",) and re.search(r"(?<![\w-])\.harness[/\\]cases(?![\w-])", cmd):
        return False, ("Known-answer cases are held back from workers so that they stay a fair test. "
                       "Work from your task's detail."), "shell:cases"
    for pat in cfg.get("protected_paths") or []:
        rx, token = path_token_re(pat)
        if rx is None or not rx.search(cmd):
            continue
        why = ("This command looks like it would change protected project data (%s). Read it freely; write results "
               "in your task folder, and verified results reach the project data through 'promote'." % token)
        if re.search(r">{1,2}\s*[\"']?[^\s;&|]*" + rx.pattern, cmd):
            return False, why, "shell:protected"
        for seg in segments:
            if not rx.search(seg):
                continue
            if ALTER_VERBS.search(seg):
                return False, why, "shell:protected"
            if COPY_VERBS.search(seg):
                parts = seg.split()
                if parts and rx.search(parts[-1]):       # copying OUT of a protected folder is reading
                    return False, why, "shell:protected"
            if SQLITE_VERB.search(seg) and not re.search(r"sqlite3\s+(-readonly|\"?file:[^ ]*mode=ro)", seg):
                return False, (why + " To read a protected database, add -readonly to sqlite3."), "shell:protected"
    return True, "", ""


def url_allowed(cfg, tool_input):
    """Refuse a tool call whose address fields point at a blocked site. A search query that names it is fine."""
    values = []
    for key, v in (tool_input or {}).items():
        if key.lower() in ("url", "urls", "uri", "href", "link", "address"):
            values.append(json.dumps(v).lower())
    blob = " ".join(values)
    for host in cfg.get("blocked_hosts") or []:
        h = host.get("host") if isinstance(host, dict) else host
        if h and h.lower() in blob:
            why = host.get("reason") if isinstance(host, dict) else None
            return False, "Project rule: do not fetch from %s. %s" % (h, why or "")
    return True, ""


def message_allowed(cfg, sess, tool_input):
    rules = role_rules(cfg, sess)
    mode = rules.get("messaging", "none")
    if mode == "open":
        return True, ""
    text = ""
    for key in ("message", "content", "text", "prompt", "body"):
        v = (tool_input or {}).get(key)
        if isinstance(v, str):
            text = v
            break
    if mode == "nudge":
        limit = int(cfg.get("nudge_max_chars", 200))
        if len(text) <= limit:
            return True, ""
        return False, ("Messages to other sessions are wake-ups only (max %d characters), for example: 'You have a "
                       "new assignment; run next.' Put the content in the ledger with 'add' or 'assign'." % limit)
    return False, ("Sessions in this harness do not message each other: a message is state nobody else can see, and a "
                   "busy session reads it late. Use the ledger command instead: 'request ROLE' to ask a specialist, "
                   "'propose' for a follow-up, 'ask' for the owner.")


# ---------------------------------------------------------------- metrics (for the doctor)

def cmd_metrics(args):
    ctx = Ctx(args, write=False)
    con, cfg = ctx.con, ctx.cfg
    all_tasks = [dict(r) for r in con.execute("SELECT * FROM tasks").fetchall()]
    tasks = [t for t in all_tasks if t["job"] != "trial"]        # trial runs are not part of the project's record
    ev = con.execute("SELECT kind, COUNT(*) AS n FROM events GROUP BY kind").fetchall()
    kinds = dict((r["kind"], r["n"]) for r in ev)

    def minutes(a, b):
        ta, tb = parse_ts(a), parse_ts(b)
        return (tb - ta).total_seconds() / 60.0 if ta and tb else None

    def median(xs):
        xs = sorted(x for x in xs if x is not None)
        if not xs:
            return None
        mid = len(xs) // 2
        return round(xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2.0, 1)

    states = {}
    for t in tasks:
        states[t["state"]] = states.get(t["state"], 0) + 1
    finished = [t for t in tasks if t["state"] in ("done", "verified")]
    decs = [dict(r) for r in con.execute("SELECT * FROM decisions").fetchall()]
    open_decs = [d for d in decs if d["state"] == "open"]
    denies = {}
    for r in con.execute("SELECT detail FROM events WHERE kind='deny'").fetchall():
        rule = (r["detail"] or "").split(" | ")[0]
        denies[rule] = denies.get(rule, 0) + 1
    recent_denials = ["%s %s %s" % (r["ts"][:16], r["session"], r["detail"]) for r in con.execute(
        "SELECT ts,session,detail FROM events WHERE kind='deny' ORDER BY id DESC LIMIT 12").fetchall()]
    no_checkpoint = []
    for t in tasks:
        if t["state"] == "in_progress":
            n = con.execute("SELECT COUNT(*) AS n FROM events WHERE kind='checkpoint' AND task=?", (t["id"],)).fetchone()["n"]
            if not n:
                no_checkpoint.append(t["id"])
    empty_queue_stops = con.execute(
        "SELECT COUNT(*) AS n FROM events WHERE kind='stopped' AND detail LIKE 'idle: nothing queued%'").fetchone()["n"]
    sessions = [dict(r) for r in con.execute("SELECT * FROM sessions").fetchall()]
    cases = con.execute("SELECT ts,detail FROM events WHERE kind='case' ORDER BY id DESC LIMIT 20").fetchall()
    verified = [t for t in tasks if t["state"] == "verified"]
    reviews_pass = kinds.get("verified", 0)
    reviews_fail = kinds.get("verify_fail", 0) + kinds.get("check_fail", 0)
    long_running = [t["id"] for t in tasks if t["state"] == "in_progress" and (age_minutes(t["started_at"]) or 0) > 240]
    dead_deps = []
    by_id = dict((t["id"], t) for t in tasks)
    for t in tasks:
        if t["state"] in ("queued", "blocked"):
            for d in json.loads(t["depends_on"] or "[]") + ([t["block_on"]] if t["block_on"] else []):
                if by_id.get(d, {}).get("state") in ("cancelled", "rejected"):
                    dead_deps.append("%s waits on %s (%s)" % (t["id"], d, by_id[d]["state"]))
    out = {
        "project": ctx.project, "generated": now(), "tier": cfg.get("tier"), "goal": cfg.get("goal") or "",
        "created_at": meta_get(con, "created_at"), "active_machine": meta_get(con, "active_machine"),
        "tasks_by_state": states, "trial_tasks_left_out": len(all_tasks) - len(tasks),
        "sessions": {"total": len(sessions),
                     "open_by_role": dict((r, len([s for s in sessions if s["state"] != "ended" and s["role"] == r]))
                                          for r in sorted(set(s["role"] for s in sessions)))},
        "minutes_median": {
            "queued_to_started": median([minutes(t["created_at"], t["started_at"]) for t in tasks]),
            "started_to_done": median([minutes(t["started_at"], t["done_at"]) for t in finished]),
            "done_to_verified": median([minutes(t["done_at"], t["verified_at"]) for t in verified]),
            "decision_wait": median([minutes(d["asked_at"], d["answered_at"]) for d in decs if d["state"] == "answered"]),
        },
        "decisions": {"open": len(open_decs),
                      "oldest_open_minutes": round(max([age_minutes(d["asked_at"]) or 0 for d in open_decs] or [0]), 1)},
        "checking": {"verified": len(verified), "done_unverified": states.get("done", 0),
                     "verified_by_script": len([t for t in verified if t["verified_by"] == "check"]),
                     "verified_by_reviewer": len([t for t in verified if t["verified_by"] not in (None, "check", "owner")]),
                     "verified_by_owner": len([t for t in verified if t["verified_by"] == "owner"]),
                     "passes": reviews_pass, "failures": reviews_fail,
                     "tasks_failed_more_than_once": [t["id"] for t in tasks if (t["fail_count"] or 0) > 1],
                     "verified_not_promoted": len([t for t in verified if not t["promoted_at"]])},
        "followups": {"proposed_waiting": states.get("proposed", 0), "accepted": kinds.get("accepted", 0),
                      "rejected": kinds.get("rejected", 0)},
        "flow": {"stop_refused": kinds.get("stop_refused", 0), "handed_out_at_stop": kinds.get("handed_out", 0),
                 "stopped": kinds.get("stopped", 0), "requeued": kinds.get("requeued", 0),
                 "reassigned": kinds.get("reassigned", 0), "blocked": kinds.get("blocked", 0),
                 "coordinator_wakes": kinds.get("board", 0), "long_running_tasks": long_running,
                 "in_progress_without_checkpoint": no_checkpoint, "stopped_with_empty_queue": empty_queue_stops,
                 "checkpoints": kinds.get("checkpoint", 0), "dead_dependencies": dead_deps},
        "hook_denials": {"total": kinds.get("deny", 0), "by_rule": denies, "recent": recent_denials},
        "saving": {"last_snapshot": meta_get(con, "last_snapshot"), "stamps": kinds.get("stamp", 0),
                   "resumes": kinds.get("resume", 0)},
        "known_answer_cases": {
            "defined": len([p for p in (hdir(ctx.root) / "cases").iterdir() if p.is_dir()]) if (hdir(ctx.root) / "cases").is_dir() else 0,
            "recent_runs": ["%s %s" % (c["ts"][:16], c["detail"]) for c in cases]},
        "rules": {"protected_paths": len(cfg.get("protected_paths") or []), "blocked_hosts": len(cfg.get("blocked_hosts") or []),
                  "bash_deny": len(cfg.get("bash_deny") or []), "check_kinds": sorted((cfg.get("checks") or {}).keys()),
                  "promote_cmd_set": bool((cfg.get("promote") or {}).get("cmd")),
                  "handoff_push_set": bool((cfg.get("handoff") or {}).get("push_cmd"))},
        "field_notes": {
            "long_running_tasks": "in progress for more than 240 minutes",
            "coordinator_wakes": "times a coordinator session ran the board command",
            "stop_refused": "times the stop hook refused a session that tried to stop",
            "handed_out_at_stop": "times the stop hook gave a stopping session its next task",
            "stopped_with_empty_queue": "times a session was allowed to stop because nothing was queued for it",
            "hook_denials.recent": "time, session, rule, then the file or command that was refused",
            "minutes_median": "medians in minutes; null when there is nothing to measure"},
        "role_prompt_words": dict((p.stem, len(p.read_text(encoding="utf-8").split()))
                                  for p in sorted((hdir(ctx.root) / "roles").glob("*.md"))),
    }
    print(json.dumps(out, indent=1))


def cmd_scan(args):
    """Files changed in the project outside task folders: evidence of work that bypassed the ledger."""
    ctx = Ctx(args, write=False)
    since = parse_ts(meta_get(ctx.con, "created_at"))
    cutoff = time.time() - args.days * 86400
    if since:
        cutoff = max(cutoff, since.timestamp())
    skip = {".git", ".harness", ".claude", "node_modules", "__pycache__", ".venv", "venv"}
    hits = []
    for dirpath, dirnames, filenames in os.walk(str(ctx.root)):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                m = os.path.getmtime(p)
            except OSError:
                continue
            if m >= cutoff:
                hits.append((m, os.path.relpath(p, str(ctx.root)).replace("\\", "/")))
    hits.sort(reverse=True)
    promoted = ctx.con.execute("SELECT COUNT(*) AS n FROM events WHERE kind='promoted'").fetchone()["n"]
    print("Files changed outside .harness/ in the last %d day(s): %d   (promotions recorded: %d)" % (args.days, len(hits), promoted))
    for m, rel in hits[:args.n]:
        print("  %s  %s" % (datetime.fromtimestamp(m).strftime("%Y-%m-%d %H:%M"), rel))
    if len(hits) > args.n:
        print("  ... and %d more" % (len(hits) - args.n))


def settings_have_hooks(path):
    data = read_json(path, {})
    found = set()
    for evname, groups in (data.get("hooks") or {}).items():
        for g in groups if isinstance(groups, list) else []:
            for hk in (g.get("hooks") or []) if isinstance(g, dict) else []:
                blob = json.dumps(hk).replace("\\\\", "/").replace("\\", "/")
                if "hook.py" in blob and ("/.harness/" in blob or (Path(__file__).resolve().parent / "hook.py").as_posix() in blob):
                    found.add(evname)
    need = {"SessionStart", "PreToolUse", "PostToolUse", "Stop", "SessionEnd"}
    return need.issubset(found), sorted(found)


def hooks_scope(root=None):
    """Where the hooks are installed: 'user' (every session), 'project' (sessions started in the folder) or 'none'."""
    cdir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    if settings_have_hooks(cdir / "settings.json")[0]:
        return "user"
    if root is not None:
        for name in ("settings.local.json", "settings.json"):
            if settings_have_hooks(Path(root) / ".claude" / name)[0]:
                return "project"
    return "none"


# ---------------------------------------------------------------- install check

def cmd_check_install(args):
    ok = True

    def line(good, text):
        print("  [%s] %s" % ("ok" if good else "!!", text))
        return good

    print("Harness %s on %s (Python %s)" % (VERSION, machine(), sys.version.split()[0]))
    ok &= line(sys.version_info >= (3, 8), "Python 3.8 or newer")
    ok &= line((home() / "bin" / "harness.py").exists(), "ledger command installed at %s" % (home() / "bin"))
    ok &= line((home() / "bin" / "hook.py").exists(), "hook script installed")
    cdir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    user_wide = settings_have_hooks(cdir / "settings.json")[0]
    line(True, "user-wide hooks (%s): %s" % (cdir / "settings.json", "installed: they apply to every project and to sessions "
                                              "that join from any folder" if user_wide else "not installed (fine when each project has its own)"))
    for name, entry in sorted(registry()["projects"].items()):
        path = entry.get("paths", {}).get(machine())
        if not path:
            line(True, "project %s: no folder on this computer (fine if it lives on the other one)" % name)
            continue
        good = hdir(path).is_dir()
        ok &= line(good, "project %s at %s" % (name, path))
        if entry.get("tier") == "lite":
            continue
        scope = hooks_scope(path)
        ok &= line(scope != "none", "project %s hooks: %s" % (name, {
            "user": "covered by the user-wide hooks",
            "project": "installed for sessions started inside the project folder",
            "none": "NOT installed on this computer; run hooks_install.py --add --project \"%s\"" % path}[scope]))
    print("All good." if ok else "Something needs attention (lines marked !!).")
    sys.exit(0 if ok else 1)


# ---------------------------------------------------------------- argument parsing

def build_parser():
    p = argparse.ArgumentParser(prog="harness", description="Ledger command for a multi-session project.")
    p.add_argument("--project", help="project name from the registry")
    p.add_argument("--as", dest="as_name", help="your session name (given when you joined)")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="cmd")

    def add(name, fn, help_text):
        sp = sub.add_parser(name, help=help_text)
        sp.set_defaults(fn=fn)
        return sp

    sp = add("init", cmd_init, "set up a project folder")
    sp.add_argument("name")
    sp.add_argument("--path", default=".")
    sp.add_argument("--tier", choices=["lite", "full"], default="full")
    sp = add("register-path", cmd_register_path, "tell this computer where a project lives")
    sp.add_argument("name")
    sp.add_argument("path")
    add("projects", cmd_projects, "list registered projects")
    sp = add("join", cmd_join, "register this session with a role")
    sp.add_argument("project")
    sp.add_argument("--role", default="worker", help="coordinator, worker, reviewer or guest")
    sp.add_argument("--specialty", help="a specialist's name; it then receives only tasks addressed to that name")
    sp.add_argument("--session", help="session id, if it cannot be read from the environment")
    sp = add("whoami", cmd_whoami, "show your name, role and current task")
    sp.add_argument("--full", action="store_true")
    add("leave", cmd_leave, "take this session out of the harness")

    def task_opts(sp, to=True):
        sp.add_argument("title", help="one short line")
        sp.add_argument("--detail", help="one short line of detail (max %d characters)" % SUMMARY_MAX)
        sp.add_argument("--detail-file", help="a file holding the full detail: what is wanted, what is known, what done looks like")
        sp.add_argument("--kind", help="kind of task, which decides how it is checked (see 'checks' in the rules file)")
        if to:
            sp.add_argument("--role", help="address it to a role or specialty instead of ordinary workers")
            sp.add_argument("--to", help="address it to one session by name")
            sp.add_argument("--after", help="task ids that must finish first, comma-separated")
            sp.add_argument("--job", help="a label for grouping tasks that belong to one piece of work")
            sp.add_argument("--parent", help="the task this one follows from")
        sp.add_argument("--priority", type=int, default=0, help="higher numbers are handed out first")

    sp = add("add", cmd_add, "queue a task (coordinator or owner)")
    task_opts(sp)
    sp.add_argument("--proposed", action="store_true", help="hold it as a proposal instead of queueing it")
    sp.add_argument("--result", help="an existing result file: registers earlier work as done but unverified, so a reviewer can check it")
    sp = add("propose", cmd_propose, "propose a follow-up for the coordinator to decide")
    task_opts(sp, to=False)
    sp.add_argument("--task")
    sp = add("request", cmd_request, "ask a specialist role for something")
    sp.add_argument("role")
    task_opts(sp, to=False)
    sp.add_argument("--wait", action="store_true", help="block your current task until this is finished")
    sp = add("accept", cmd_accept, "queue a proposed task")
    sp.add_argument("task")
    sp.add_argument("--to")
    sp.add_argument("--role")
    sp.add_argument("--priority", type=int)
    sp = add("edit", cmd_edit, "change a task nobody is working on: its title, detail, kind, or who it is for")
    sp.add_argument("task")
    sp.add_argument("--title")
    sp.add_argument("--detail")
    sp.add_argument("--detail-file")
    sp.add_argument("--kind")
    sp.add_argument("--role", help="address it to this role or specialty ('worker' for ordinary workers)")
    sp.add_argument("--to", help="address it to one session by name")
    sp.add_argument("--unassign", action="store_true")
    sp.add_argument("--priority", type=int)
    sp = add("unverify", cmd_unverify, "withdraw a verification that was not a real check")
    sp.add_argument("task")
    sp.add_argument("--reason", required=True)
    sp = add("trial-clear", cmd_trial_clear, "cancel trial tasks and close trial sessions after proving a setup")
    sp.add_argument("--yes", action="store_true")
    sp = add("reject", cmd_reject, "turn down a proposed task")
    sp.add_argument("task")
    sp.add_argument("--reason", required=True)
    sp = add("assign", cmd_assign, "give a task to a session")
    sp.add_argument("task")
    sp.add_argument("to")
    sp = add("requeue", cmd_requeue, "put a stuck task back in the queue")
    sp.add_argument("task")
    sp.add_argument("--reason", default="")
    sp.add_argument("--unassign", action="store_true")
    add("next", cmd_next, "take your next task")
    sp = add("show", cmd_show, "show one task")
    sp.add_argument("task")
    sp = add("list", cmd_list, "list tasks")
    sp.add_argument("--state", choices=ALL_STATES)
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--mine", action="store_true")
    sp = add("checkpoint", cmd_checkpoint, "record where you are on a task")
    sp.add_argument("note")
    sp.add_argument("--task")
    sp = add("done", cmd_done, "mark a task done, with its result on disk")
    sp.add_argument("task", nargs="?")
    sp.add_argument("--result", required=True)
    sp.add_argument("--summary", required=True)
    sp.add_argument("--followup", action="append")
    sp = add("block", cmd_block, "record that a task cannot continue")
    sp.add_argument("task", nargs="?")
    sp.add_argument("--reason", required=True)
    sp.add_argument("--on", help="task id this one waits for")
    sp = add("ask", cmd_ask, "put a question in the owner's decision queue")
    sp.add_argument("question")
    sp.add_argument("--task")
    sp = add("answer", cmd_answer, "record the owner's answer to a decision")
    sp.add_argument("decision")
    sp.add_argument("text")
    sp = add("cancel", cmd_cancel, "cancel a task")
    sp.add_argument("task")
    sp.add_argument("--reason", required=True)
    sp = add("check", cmd_check, "run the configured checker script on a done task")
    sp.add_argument("task")
    sp = add("verify", cmd_verify, "pass or fail a done task (reviewer or owner)")
    sp.add_argument("task")
    sp.add_argument("--pass", dest="passed", action="store_true")
    sp.add_argument("--fail", dest="failed", action="store_true")
    sp.add_argument("--note", default="", help="what was checked, or what is wrong and how to fix it")
    sp.add_argument("--owner", action="store_true", help="the owner is verifying by hand, with no session")
    sp = add("promote", cmd_promote, "move a verified result into the project's main data")
    sp.add_argument("task")
    sp = add("case", cmd_case, "known-answer cases: list, add NAME, record NAME pass|fail")
    sp.add_argument("action", choices=["list", "add", "record"])
    sp.add_argument("name", nargs="?")
    sp.add_argument("result", nargs="?")
    sp.add_argument("--note", default="")
    add("board", cmd_board, "where everything stands, and what needs action")
    sp = add("status", cmd_status, "rewrite STATUS.md and the dashboard")
    sp.add_argument("--print", dest="print_it", action="store_true")
    sp = add("log", cmd_log, "recent events")
    sp.add_argument("-n", type=int, default=40)
    sp.add_argument("--kind", help="only events of this kind, for example deny, board, stopped, checkpoint")
    add("overview", cmd_overview, "one line per project on this computer")
    add("metrics", cmd_metrics, "numbers about how the harness is running (JSON)")
    sp = add("scan", cmd_scan, "files changed outside task folders")
    sp.add_argument("--days", type=int, default=7)
    sp.add_argument("-n", type=int, default=40)
    sp = add("snapshot", cmd_snapshot, "save a copy of the ledger now; --setup makes an undo point of the whole setup")
    sp.add_argument("--setup", action="store_true", help="also copy the rules file, role files, tools and cases")
    sp = add("restore", cmd_restore, "go back to an undo point made with snapshot --setup")
    sp.add_argument("name", help="the undo point's name, as printed when it was made")
    sp.add_argument("--ledger", action="store_true", help="put the ledger back too, not only rules and role files")
    sp.add_argument("--yes", action="store_true")
    sp = add("end-sessions", cmd_end_sessions, "close every session and requeue unfinished tasks, before reconfiguring")
    sp.add_argument("--yes", action="store_true")
    sp = add("unregister", cmd_unregister, "stop treating a folder as a harness project on this computer")
    sp.add_argument("name")
    sp.add_argument("--yes", action="store_true")
    sp = add("drain", cmd_drain, "stop handing out tasks before a handoff")
    sp.add_argument("--off", action="store_true")
    sp = add("stamp", cmd_stamp, "seal the handoff and park this computer")
    sp.add_argument("--force", action="store_true")
    sp = add("resume", cmd_resume, "take over the project on this computer")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--no-pull", action="store_true")
    sp = add("reset", cmd_reset, "archive the ledger and start an empty one (for clearing a trial run)")
    sp.add_argument("--yes", action="store_true")
    add("check-install", cmd_check_install, "check that the kit and hooks are installed")
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 2
    try:
        args.fn(args)
    except HarnessError as exc:
        sys.stderr.write("harness: %s\n" % exc)
        return 1
    except sqlite3.OperationalError as exc:
        sys.stderr.write("harness: the ledger is busy or unreadable (%s). Try again in a moment.\n" % exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
