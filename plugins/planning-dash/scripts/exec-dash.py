#!/usr/bin/env python3
"""Live dashboard for a /planning:exec run, shown in an agterm HTML overlay.

A background watcher reads the plan's checkboxes, the run's progress file
(/tmp/progress-*.txt whose Plan: names the plan), the run's subagent logs
under ~/.claude/projects and the orchestrator's own transcript (its phase
announcements, and when it saw each subagent finish) every few seconds, and
writes data.js next to a static page that polls it. A run moved into a worktree
under .claude/worktrees ticks the plan copy there, so the copy on the run's
branch is the one read.

    exec-dash.py --toggle --project DIR    open/close the session's own run, else the newest run of DIR's project
    exec-dash.py PLAN --open               open a given plan's dashboard
    exec-dash.py PLAN --stop               stop that plan's watcher
"""
import argparse
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.basename(__file__)
TEMPLATE = os.path.join(HERE, "exec-dash.html")
PROJECTS = os.path.expanduser("~/.claude/projects")
SESSIONS = os.path.expanduser("~/.claude/sessions")  # one <pid>.json per live Claude Code process
CACHE = os.path.expanduser("~/.cache/exec-dash")
LINGER = 120  # seconds the watcher keeps refreshing after the run completes
IDLE_EXIT = 3 * 3600  # seconds without any activity after which the watcher stops
ARGS = None  # the command line, parsed in main()

WORKTREE_RE = re.compile(r"^(.*)/\.claude/worktrees/[^/]+(/.*)$")
TASK_RE = re.compile(r"^###\s+(?:Task|Iteration)\s+(\d+):\s*(.*?)\s*$")
CHECK_RE = re.compile(r"^(\s*)- \[([ xX])\]\s+(.*)$")
BULLET_RE = re.compile(r"^(\s*)- (.*)$")
FILE_RE = re.compile(r"^- (Create|Modify|Delete|Move|Rename)[^:]*:\s*(.*)$")
TS_RE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\]\s?(.*)$")
# progress entries: "[task] Task 1: ... — completed", "task 1: <title>", "[decision] task 1: ...", "[deviation] fixer: ..."
KIND_RE = re.compile(r"^\[(\w+)\]\s*")
TASK_NOTE_RE = re.compile(r"^(?:\[\w+\]\s*)?task\s+(\d+)\b", re.I)
WHO_RE = re.compile(r"^(task\s+\d+|fixer)\b\s*:?\s*", re.I)
# "review phase 1: findings", "review phase 1 (critical re-check, iteration 2): clean", "review phase 3: external review not run — ..."
PHASE_RE = re.compile(r"^(?:-+\s*)?review phase\s+(\d)\b(.*)$", re.I)
SKIP_RE = re.compile(r"\b(skipped|not run|not available|unavailable)\b", re.I)
# the orchestrator's transcript: the "--- Review phase N: ... ---" lines it prints before spawning a phase's agents,
# the launch result of each background Agent call, and the hand-back or task notification that tells it one finished
ANNOUNCE_RE = re.compile(r"^\s*-{2,}\s*(?:review phase\s+(\d)\b[^\n]*|finaliz[^\n]*)", re.I | re.M)
HANDBACK_RE = re.compile(r'<agent-message from="([0-9a-f]+)">\s*\[Subagent hand-back\]')
NOTIF_RE = re.compile(r"<task-notification>\s*<task-id>([0-9a-f]+)</task-id>")
# what Claude Code prints in place of a reply when a request fails ("Please run /login · API Error: 403 ...")
API_ERROR_RE = re.compile(r"\bAPI Error\b")
# the exec skill's call that starts a run, `init-progress.sh /tmp/progress-<stem>.txt <plan> <branch>`, in a Bash
# call of the orchestrator's transcript (its "command" string; a tool result or a reply quoting the line does not count)
INIT_RE = re.compile(rb'"command":"(?:[^"\\]|\\.)*?init-progress\.sh[\\"\']*\s+[\\"\']*(/tmp/progress-[^\s"\'\\<>]+\.txt)')

PHASES = [
    ("tasks", "Tasks"),
    ("review1", "Review 1 · comprehensive"),
    ("review2", "Review 2 · smells"),
    ("review3", "Review 3 · external"),
    ("review4", "Review 4 · critical"),
    ("finalize", "Finalize"),
    ("stats", "Stats"),
]
LOG_DETAIL_LINES = 400


def local_ts(s):
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))


def iso_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


# ---------------------------------------------------------------- plan


def resolve_plan(path):
    """PATH, or where the plan went: docs/plans/completed/, or the project's copy once its worktree is gone."""
    for p in (path, os.path.join(os.path.dirname(path), "completed", os.path.basename(path))):
        if os.path.exists(p):
            return p
    m = WORKTREE_RE.match(path)
    return resolve_plan(m.group(1) + m.group(2)) if m else None


def parse_plan(path):
    title, tasks, task, item, section = None, [], None, None, None
    for raw in open(path, encoding="utf-8").read().splitlines():
        line = raw.rstrip()
        if title is None and line.startswith("# "):
            title = line[2:].strip()
            continue
        m = TASK_RE.match(line)
        if m:
            task = {"n": int(m.group(1)), "title": m.group(2), "items": [], "files": []}
            tasks.append(task)
            item, section = None, None
            continue
        if line.startswith("#"):
            task, item, section = None, None, None
            continue
        if task is None:
            continue
        if line.strip() == "**Files:**":
            section = "files"
            continue
        m = CHECK_RE.match(line)
        if m:
            section = "items"
            item = {"text": m.group(3), "done": m.group(2) != " ", "sub": []}
            task["items"].append(item)
            continue
        if section == "files":
            m = FILE_RE.match(line)
            if m:
                task["files"].append({"kind": m.group(1), "paths": m.group(2)})
            elif line.startswith("  ") and task["files"]:
                task["files"][-1]["paths"] += " " + line.strip()
            continue
        if item is not None and line.strip():
            m = BULLET_RE.match(line)
            if m and len(m.group(1)) > 0:
                item["sub"].append(m.group(2))
            elif item["sub"] and line.startswith("    "):
                item["sub"][-1] += " " + line.strip()
            elif line.startswith("  "):
                item["text"] += " " + line.strip()
    for t in tasks:
        t["total"] = len(t["items"])
        t["done"] = sum(1 for i in t["items"] if i["done"])
    return {"title": title or os.path.basename(path), "tasks": tasks}


# ---------------------------------------------------------------- progress file


def parse_progress(path):
    out = {"header": {}, "entries": [], "completed": None, "markers": [], "decisions": []}
    if not path or not os.path.exists(path):
        return out
    entry = None
    for line in open(path, encoding="utf-8", errors="replace").read().splitlines():
        m = TS_RE.match(line)
        if m:
            text = m.group(2).strip()
            km = KIND_RE.match(text)
            kind = km.group(1).lower() if km else None
            body = text[km.end():] if km else text
            entry = {"ts": local_ts(m.group(1)), "text": m.group(2), "detail": [], "kind": kind}
            out["entries"].append(entry)
            pm = PHASE_RE.match(body)
            if pm:
                out["markers"].append({"ts": entry["ts"], "phase": "review" + pm.group(1), "text": body.strip("- "),
                                       "skip": bool(SKIP_RE.search(pm.group(2)))})
            elif body.lower().startswith("finalize"):
                out["markers"].append({"ts": entry["ts"], "phase": "finalize", "text": body})
            if body.lower() == "completed":
                out["completed"] = entry["ts"]
            if kind in ("decision", "deviation"):
                wm = WHO_RE.match(body)
                out["decisions"].append({"ts": entry["ts"], "kind": kind, "who": wm.group(1).lower() if wm else "",
                                         "text": body[wm.end():] if wm else body})
            continue
        if entry is None:
            for key in ("Plan", "Branch", "Started", "Completed"):
                if line.startswith(key + ":"):
                    out["header"][key.lower()] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Completed:"):
            try:
                out["completed"] = local_ts(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.strip() and line.strip() != "---":
            entry["detail"].append(line)
    started = out["header"].get("started")
    out["started"] = local_ts(started) if started else None
    return out


# ---------------------------------------------------------------- subagent logs


def new_records(path, offset):
    """(new offset, parsed JSON lines) of a transcript past OFFSET; whole lines only, the rest next tick."""
    try:
        size = os.path.getsize(path)
        if size <= offset:
            return offset, []
        with open(path, "rb") as f:
            f.seek(offset)
            chunk = f.read(size - offset)
    except OSError:
        return offset, []  # moving with its session, or half written: next tick
    end = chunk.rfind(b"\n")
    if end < 0:
        return offset, []
    records = []
    for raw in chunk[: end + 1].splitlines():
        try:
            records.append(json.loads(raw))
        except ValueError:
            continue
    return offset + end + 1, records


def texts_of(record):
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [c.get("text") or "" for c in content if isinstance(c, dict) and c.get("type") == "text"]
    return []


def api_error(record, ts):
    """The API error an assistant record reports; None from any later assistant record, which shows the session went on."""
    for text in texts_of(record):
        if API_ERROR_RE.search(text):
            line = next((ln.strip() for ln in text.splitlines() if API_ERROR_RE.search(ln)), text.strip())
            return {"ts": ts, "text": " ".join(line.split())[:200]}
    return None


def context_of(msg):
    """Input side of the request an assistant record answers: the context size as the request was made (exact,
    unlike the output side, which is still being written when the record lands)."""
    usage = msg.get("usage") or {}
    return usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)


class AgentLog:
    """Incrementally parsed subagent transcript."""

    def __init__(self, path):
        self.path = path
        self.id = os.path.basename(path)[: -len(".jsonl")]
        self.short = self.id[len("agent-"):] if self.id.startswith("agent-") else self.id  # as the orchestrator names it
        self.offset = 0
        self.desc = ""
        self.start = self.last = self.finished = self.notified = None
        self.tools = 0
        self.context = 0
        self.model = None
        self.error = None
        self.last_tool = self.last_tool_ts = None

    def refresh(self):
        meta = self.path[: -len(".jsonl")] + ".meta.json"
        try:
            if not self.desc and os.path.exists(meta):
                self.desc = json.load(open(meta)).get("description", "")
        except (OSError, ValueError):
            pass
        self.offset, records = new_records(self.path, self.offset)
        for d in records:
            try:
                self.consume(d)
            except (KeyError, TypeError, AttributeError):
                continue

    def consume(self, d):
        ts = d.get("timestamp")
        if ts:
            t = iso_ts(ts)
            self.start = self.start or t
            self.last = t
        msg = d.get("message") or {}
        content = msg.get("content")
        if d.get("type") != "assistant":
            return
        self.error = api_error(d, self.last)
        self.model = msg.get("model") or self.model
        self.context = context_of(msg) or self.context
        for c in content if isinstance(content, list) else []:
            if not isinstance(c, dict) or c.get("type") != "tool_use":
                continue
            if c.get("name") == "SubagentHandback":
                self.finished = self.last
                continue
            self.tools += 1
            self.last_tool = describe_tool(c.get("name", "?"), c.get("input") or {})
            self.last_tool_ts = self.last

    def as_dict(self):
        # a subagent that hands back ends there; one that stops any other way (API error, interrupt, plain
        # final text) only shows in the orchestrator's transcript, as the task notification it received
        end = self.finished or self.notified
        return {
            "id": self.id,
            "desc": self.desc,
            "start": self.start,
            "last": self.last,
            "end": end,
            "running": end is None,
            "tools": self.tools,
            "context": self.context,
            "model": self.model,
            "error": self.error,
            "lastTool": self.last_tool,
            "lastToolTs": self.last_tool_ts,
        }


def describe_tool(name, inp):
    if name == "Bash":
        what = inp.get("description") or inp.get("command", "")
    elif name in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        what = os.path.basename(inp.get("file_path", "") or inp.get("notebook_path", ""))
    elif name in ("Grep", "Glob"):
        what = inp.get("pattern", "")
    else:
        what = ""
    what = " ".join(str(what).split())
    return {"name": name, "what": what[:140]}


class Orchestrator:
    """Incrementally parsed main transcript of the exec session."""

    def __init__(self):
        self.offsets = {}
        self.markers = []   # the "--- Review phase N: ... ---" and "--- Finalize ---" lines it prints before a phase
        self.launched = {}  # subagent id -> {ts, desc, model} from the Agent tool's launch result
        self.ended = {}     # subagent id -> when its hand-back or task notification reached the orchestrator
        self.last = None    # its latest record
        self.error = None   # the API error it last printed, while nothing followed it
        self.context = 0    # its own context size at its latest request: what auto-compaction watches
        self.model = None

    def refresh(self, paths):
        for path in paths:
            self.offsets[path], records = new_records(path, self.offsets.get(path, 0))
            for d in records:
                try:
                    self.consume(d)
                except (KeyError, TypeError, AttributeError, ValueError):
                    continue
        self.markers.sort(key=lambda m: m["ts"])

    def consume(self, d):
        ts = d.get("timestamp")
        if not ts:
            return
        ts = iso_ts(ts)
        self.last = max(self.last or 0, ts)
        if d.get("type") == "assistant":
            self.error = api_error(d, ts)
            msg = d.get("message") or {}
            self.model = msg.get("model") or self.model
            self.context = context_of(msg) or self.context
            for text in texts_of(d):
                for m in ANNOUNCE_RE.finditer(text):
                    phase = "review" + m.group(1) if m.group(1) else "finalize"
                    self.markers.append({"ts": ts, "phase": phase, "text": m.group(0).strip(" -\n")})
        elif d.get("type") == "user":
            result = d.get("toolUseResult")
            if isinstance(result, dict) and result.get("status") == "async_launched" and result.get("agentId"):
                self.launched[result["agentId"]] = {"ts": ts, "desc": result.get("description") or "",
                                                    "model": result.get("resolvedModel")}
            for text in texts_of(d):
                for rx in (HANDBACK_RE, NOTIF_RE):
                    for m in rx.finditer(text):
                        self.ended.setdefault(m.group(1), ts)


class Agents:
    def __init__(self, project, plan_path):
        self.project = project
        self.plan_name = os.path.basename(plan_path)
        # the project's dir under ~/.claude/projects, and those of its worktrees (same prefix)
        self.enc = re.sub(r"[^A-Za-z0-9]", "-", project)
        self.session_dir = None
        self.since = None  # when the run started, once its progress file says
        self.logs = {}
        self.orch = Orchestrator()
        self.next_search = 0

    def find_session(self):
        dirs = []
        for proj in glob.glob(os.path.join(PROJECTS, glob.escape(self.enc) + "*")):
            dirs += [d for d in glob.glob(os.path.join(proj, "*", "subagents")) if os.path.isdir(d)]
        # sessions still written to after the run began; the newest few when the run has not started yet
        if self.since:
            dirs = [d for d in dirs if os.path.getmtime(d) >= self.since - 600]
        dirs.sort(key=os.path.getmtime, reverse=True)
        for sub in dirs if self.since else dirs[:12]:
            for meta in glob.glob(os.path.join(sub, "agent-*.meta.json")):
                try:
                    desc = json.load(open(meta)).get("description", "")
                except ValueError:
                    continue
                if not re.search(r"\btask\s+\d+\b", desc, re.I):
                    continue
                # an exec task agent's prompt names the plan file it works through
                try:
                    with open(meta[: -len(".meta.json")] + ".jsonl", "rb") as f:
                        if self.plan_name.encode() in f.read(20000):
                            return sub
                except OSError:
                    continue
        return None

    @property
    def session_id(self):
        """Claude Code session id of the orchestrator, once its subagent logs are found."""
        return os.path.basename(os.path.dirname(self.session_dir)) if self.session_dir else None

    def refresh(self):
        if self.session_dir is None and time.time() >= self.next_search:
            self.session_dir = self.find_session()
            self.next_search = time.time() + 15
        if self.session_dir is None:
            return []
        # a session that moves between the project and a worktree goes on under another project dir
        where = os.path.join(PROJECTS, glob.escape(self.enc) + "*")
        self.orch.refresh(glob.glob(os.path.join(where, self.session_id + ".jsonl")))
        for path in glob.glob(os.path.join(where, self.session_id, "subagents", "agent-*.jsonl")):
            log = self.logs.get(os.path.basename(path))
            if log is None:
                log = self.logs[os.path.basename(path)] = AgentLog(path)
            log.path = path  # the file moves with its session; the parsed state carries over
            log.refresh()
            launched = self.orch.launched.get(log.short)
            if launched:
                log.desc = log.desc or launched["desc"]
                log.model = log.model or launched["model"]
            log.notified = self.orch.ended.get(log.short)
        return sorted((a.as_dict() for a in self.logs.values() if a.start), key=lambda a: a["start"])


# ---------------------------------------------------------------- agterm


def claude_processes():
    """Live Claude Code processes, from ~/.claude/sessions/<pid>.json: pid, sessionId, cwd, startedAt."""
    out = []
    for path in glob.glob(os.path.join(SESSIONS, "*.json")):
        try:
            d = json.load(open(path))
            os.kill(int(d["pid"]), 0)
        except (OSError, ValueError, KeyError, TypeError):
            continue  # unreadable, or the process is gone
        out.append(d)
    return out


def agterm_session_of(pid):
    """The agterm session a process runs in, from the AGTERM_SESSION_ID in its environment (ps -E, macOS)."""
    try:
        env = subprocess.run(["ps", "-Eww", "-o", "command=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"\bAGT(?:ERM)?_SESSION_ID=([0-9A-Fa-f-]{8,})", env)
    return m.group(1) if m else None


def transcript_of(proc):
    """The main transcript of a Claude Code process, as bytes (it lives under its cwd's project dir)."""
    enc = re.sub(r"[^A-Za-z0-9]", "-", proc.get("cwd") or "")
    try:
        with open(os.path.join(PROJECTS, enc, proc["sessionId"] + ".jsonl"), "rb") as f:
            return f.read()
    except (OSError, KeyError, TypeError):
        return b""


def session_run(target):
    """(progress file, cwd) of the run that the Claude Code process in agterm session TARGET started: the last
    initializer call in its transcript, when it ran several. None when the session runs no Claude Code (a plain
    shell, say) or that one never started a run."""
    for p in sorted(claude_processes(), key=lambda p: p.get("startedAt") or 0, reverse=True):
        session = agterm_session_of(p["pid"])
        if not session or not session.upper().startswith(target.upper()):
            continue
        for m in reversed(INIT_RE.findall(transcript_of(p))):
            progress = m.decode()
            if os.path.isfile(progress):
                return progress, p.get("cwd")
    return None


class Agterm:
    def __init__(self, socket, name=None):
        self.ctl = shutil.which("agtermctl") or "/opt/homebrew/bin/agtermctl"
        self.socket = socket
        self.exec_session = None  # the agterm session running the orchestrator, once found
        self.next_search = 0
        self.searched_sid = None
        # the run's line in the exec session's title bar, "<plan>: 4/11"; no name keeps the title bar untouched
        self.name = name
        self.title = None  # the line set last

    def owns_title(self, session):
        """Whether the exec session's title-bar context is ours to write: empty, or a line of this run (an earlier
        watcher's too). A line someone else set is left alone."""
        current = session.get("context") or ""
        return not current or current == self.title or current.startswith(self.name + ":")

    def set_title(self, session, text):
        if not self.name or not session or not self.owns_title(session):
            return
        if text != self.title or (session.get("context") or "") != text:
            if self.run("session", "context", text, "--target", session["id"]) is not None:
                self.title = text

    def clear_title(self, session_id):
        """Take the run's line down; from the live tree, as the session may have been given another line since."""
        if not self.name or not session_id:
            return
        for _, s in self.sessions():
            if s["id"].upper() == session_id.upper() and s.get("context") and self.owns_title(s):
                self.run("session", "context", "--clear", "--target", session_id)

    def find_exec_session(self, project, sid, needles):
        """The orchestrator's agterm session: that of the Claude Code process of session SID, or, before the
        subagent logs tell SID, of the live process under PROJECT whose transcript names the run (NEEDLES,
        most telling first; the newest process wins a tie)."""
        procs = claude_processes()
        if sid:
            procs = [p for p in procs if p.get("sessionId") == sid]
        else:
            texts = [(p, transcript_of(p)) for p in procs if (p.get("cwd") or "").startswith(project)]
            procs = next(([p for p, t in texts if n.encode() in t] for n in needles
                          if any(n.encode() in t for _, t in texts)), [])
        for p in sorted(procs, key=lambda p: p.get("startedAt") or 0, reverse=True):
            session = agterm_session_of(p["pid"])
            if session:
                return session
        return None

    def call(self, *args, timeout=5):
        """(ok, result or error message) for one agtermctl request."""
        cmd = [self.ctl, *args, "--json"] + (["--socket", self.socket] if self.socket else [])
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            reply = json.loads(proc.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            return False, str(e)
        return (True, reply.get("result") or {}) if reply.get("ok") else (False, reply.get("error", "failed"))

    def run(self, *args, timeout=5):
        ok, result = self.call(*args, timeout=timeout)
        return result if ok else None

    def sessions(self):
        tree = self.run("tree")
        if not tree:
            return []
        tree = tree.get("tree", tree)
        return [(w, s) for w in tree.get("workspaces", []) for s in w.get("sessions", [])]

    def state(self, project, sid, needles):
        # once a minute, and at once when the subagent logs first tell the orchestrator's session id
        due = time.time() >= self.next_search or (sid is not None and sid != self.searched_sid)
        if not self.exec_session and due:
            self.next_search, self.searched_sid = time.time() + 60, sid
            self.exec_session = self.find_exec_session(project, sid, needles)
        if not self.exec_session:
            return None
        for w, s in self.sessions():
            if s["id"].upper() == self.exec_session.upper():
                return {"id": s["id"], "name": s.get("name"), "workspace": w.get("name"),
                        "status": s.get("status") or "idle", "context": s.get("context")}
        return None


def plan_name(path, limit=48):
    """The plan's heading for the title bar, cut at a word when long; the file stem when it has none."""
    title = parse_plan(path)["title"]
    if title == os.path.basename(path):
        title = os.path.splitext(title)[0]
    if len(title) > limit:
        title = title[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return title


def title_line(data, name):
    """The run as one line for the exec session's title bar: '<plan>: 4/11', then the review phase once the tasks
    are done ('11/11 · review 1 ×2'), then 'done'."""
    done = sum(1 for t in data["tasks"] if t["status"] == "done")
    text = "%s: %d/%d" % (name, done, len(data["tasks"]))
    if data["completed"]:
        return text + " · done"
    phase = next((p for p in data["phases"] if p["status"] == "running" and p["key"] != "tasks"), None)
    if phase:
        text += " · " + phase["key"].replace("review", "review ")
        if phase["iterations"] > 1:
            text += " ×%d" % phase["iterations"]
    return text


# ---------------------------------------------------------------- model


def build(plan_path, progress_path, agents, agterm, project):
    now = time.time()
    current = resolve_plan(plan_path)
    plan = parse_plan(current) if current else {"title": os.path.basename(plan_path), "tasks": []}
    prog = parse_progress(progress_path)
    agents.since = prog["started"]
    agent_list = agents.refresh()
    completed = prog["completed"]
    prog_markers = prog["markers"]
    # what the orchestrator announced, up to completion (its final summary may quote the phase names again)
    announced = [m for m in agents.orch.markers if not completed or m["ts"] <= completed]
    markers = sorted(prog_markers + announced, key=lambda m: m["ts"])
    review_start = min((m["ts"] for m in markers if m["phase"].startswith("review")), default=None)
    review_lines = [m for m in prog_markers if m["phase"].startswith("review")]

    def phase_of(a):
        d = a["desc"].lower()
        if "finaliz" in d:
            return "finalize"
        if "stats" in d:
            return "stats"
        if completed and a["start"] > completed:
            return "extra"
        m = re.search(r"\btask\s+(\d+)\b", d)
        if m and (review_start is None or a["start"] < review_start):
            return "task:" + m.group(1)
        # the orchestrator names some phases in the subagent's description...
        if "smell" in d:
            return "review2"
        if "external" in d or "codex" in d:
            return "review3"
        if "final critical" in d or "critical pass" in d:
            return "review4"
        m = re.search(r"\bphase\s*([1-4])\b", d)
        if m:
            return "review" + m.group(1)
        # ...else it is the phase it announced last before spawning the agent
        before = [mk for mk in announced if mk["ts"] <= a["start"] + 2 and mk["phase"].startswith("review")]
        if before:
            return before[-1]["phase"]
        if not any(w in d for w in ("review", "re-check", "fix", "critical")):
            return "extra"
        # last resort, the progress file: a phase's "review phase N" line is written when its reviewers return,
        # so a reviewer ends before its phase's line and a fixer starts after it
        if "fix" in d:
            prev = [mk for mk in review_lines if mk["ts"] <= a["start"] + 2]
            return prev[-1]["phase"] if prev else "review1"
        after = [mk for mk in review_lines if mk["ts"] >= (a["end"] or a["last"] or a["start"])]
        return after[0]["phase"] if after else "review1"

    for a in agent_list:
        a["phase"] = phase_of(a)
    # an attempt superseded by a retry, and anything still open when the run completed, ended with its last record
    attempts = {}
    for a in agent_list:
        if a["phase"].startswith("task:"):
            attempts.setdefault(a["phase"], []).append(a)
    for mine in attempts.values():
        for prev, nxt in zip(mine, mine[1:]):
            if prev["end"] is None:
                prev["end"], prev["running"] = min(prev["last"] or nxt["start"], nxt["start"]), False
    if completed:
        for a in agent_list:
            if a["end"] is None and a["start"] <= completed:
                a["end"], a["running"] = a["last"], False

    # tasks
    notes = {}
    for e in prog["entries"]:
        m = TASK_NOTE_RE.match(e["text"].strip())
        if m:
            notes.setdefault(int(m.group(1)), []).append(e)
    first_open = next((t["n"] for t in plan["tasks"] if t["done"] < t["total"]), None)
    prev_end = prog["started"]
    for t in plan["tasks"]:
        mine = [a for a in agent_list if a["phase"] == "task:%d" % t["n"]]
        t["agents"] = [a["id"] for a in mine]
        t["attempts"] = len(mine)
        t["tools"] = sum(a["tools"] for a in mine)
        t["notes"] = notes.get(t["n"], [])
        running = [a for a in mine if a["running"]]
        status_notes = [e for e in t["notes"] if e["kind"] in (None, "task")]  # not the decisions it logged
        failed_note = any(re.search(r"FAILED|BLOCKED", e["text"]) for e in status_notes[-1:])
        complete = t["total"] > 0 and t["done"] == t["total"]
        if complete:
            t["status"] = "done"
        elif running:
            t["status"] = "running"
        elif failed_note:
            t["status"] = "failed"
        elif t["n"] == first_open and not completed and review_start is None:
            t["status"] = "next"
        else:
            t["status"] = "pending"
        t["start"] = min((a["start"] for a in mine), default=None)
        ends = [a["end"] for a in mine if a["end"]]
        t["end"] = max(ends) if complete and ends else None
        if complete and t["start"] is None:
            # no transcript (older run, other machine): fall back to the progress timestamps
            t["end"] = t["notes"][-1]["ts"] if t["notes"] else None
            t["start"] = prev_end if t["end"] else None
        if t["status"] == "running" and running:
            last = max(running, key=lambda a: a["last"] or 0)
            t["now"] = {"tool": last["lastTool"], "ts": last["lastToolTs"], "last": last["last"],
                        "context": last["context"], "model": last["model"], "error": last["error"]}
        prev_end = t["end"] or prev_end

    # phases
    phases = []
    for key, label in PHASES:
        mine = [a for a in agent_list if (a["phase"].startswith("task:") if key == "tasks" else a["phase"] == key)]
        lines = [m for m in prog_markers if m["phase"] == key]
        said = [m for m in announced if m["phase"] == key]
        # a phase the progress file reports as not run (no external reviewer available) ran no agent
        skipped = not mine and any(m.get("skip") for m in lines)
        starts = [] if skipped else [m["ts"] for m in lines + said] + [a["start"] for a in mine]
        if key == "tasks":
            starts = [prog["started"]] if prog["started"] else starts
        phases.append({
            "key": key, "label": label,
            "start": min(starts) if starts else None,
            # each iteration is announced once and logged once; the two sources may each miss some
            "iterations": max(1, len(lines), len(said)) if key.startswith("review") else 1,
            "skipped": skipped,
            "agents": [a["id"] for a in mine],
            "running": any(a["running"] for a in mine),
            "tools": sum(a["tools"] for a in mine),
        })
    started_idx = [i for i, p in enumerate(phases) if p["start"]]
    last_idx = max(started_idx, default=-1)
    for i, p in enumerate(phases):
        later = [q["start"] for q in phases[i + 1:] if q["start"]]
        if p["start"] is None:
            p["status"] = "skipped" if p.pop("skipped") or i < last_idx or completed else "pending"
            p["end"] = None
        elif later:
            p["status"], p["end"] = "done", min(later)
        elif completed:
            p["status"], p["end"] = "done", completed
        else:
            p["status"], p["end"] = "running", None
        p.pop("skipped", None)

    # the latest thing anyone wrote: a subagent or orchestrator record, a progress entry, a ticked checkbox
    activity = [a["last"] or 0 for a in agent_list] + [agents.orch.last or 0]
    for f in (progress_path, current):
        if f and os.path.exists(f):
            activity.append(os.path.getmtime(f))
    needles = [os.path.basename(p) for p in (progress_path, plan_path) if p]
    session = agterm.state(project, agents.session_id, needles) if agterm else None
    return {
        "generatedAt": now,
        "plan": {"title": plan["title"], "path": os.path.relpath(current or plan_path, project),
                 "moved": bool(current) and os.path.basename(os.path.dirname(current)) == "completed"},
        "branch": prog["header"].get("branch"),
        "progressFile": progress_path,
        "started": prog["started"],
        "completed": completed,
        "tasks": plan["tasks"],
        "phases": phases,
        "agents": agent_list,
        "log": [{"ts": e["ts"], "text": e["text"], "kind": e["kind"], "detail": e["detail"][:LOG_DETAIL_LINES],
                 "detailTotal": len(e["detail"])} for e in prog["entries"]][-60:],
        "decisions": prog["decisions"],
        "orchestrator": {"last": agents.orch.last, "error": agents.orch.error,
                         "context": agents.orch.context, "model": agents.orch.model},
        "activity": max(activity, default=0) or None,
        "session": session,
        "watcher": {"interval": ARGS.interval, "stall": ARGS.stall, "contextLimit": ARGS.context_limit},
    }


# ---------------------------------------------------------------- run discovery


def progress_header(progress):
    """{plan, branch, started} from the lines a progress file opens with."""
    header = {}
    try:
        with open(progress, encoding="utf-8", errors="replace") as f:
            for line in f.read(4000).splitlines():
                if line.startswith("---") or TS_RE.match(line):
                    break
                for key in ("Plan", "Branch", "Started"):
                    if line.startswith(key + ":"):
                        header[key.lower()] = line.split(":", 1)[1].strip()
    except OSError:
        pass
    return header


def git_branch(root):
    try:
        proc = subprocess.run(["git", "-C", root, "rev-parse", "--abbrev-ref", "HEAD"],
                              capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() or None


def find_project(directory):
    d, home = os.path.abspath(directory), os.path.expanduser("~")
    while d not in ("/", home):
        if os.path.isdir(os.path.join(d, "docs", "plans")):
            return d
        d = os.path.dirname(d)
    return None


def plan_roots(project):
    # a run in an isolated worktree keeps its plan there
    worktrees = glob.glob(os.path.join(project, ".claude", "worktrees", "*"))
    return [project] + sorted(worktrees, key=os.path.getmtime, reverse=True)


def progress_files():
    return sorted(glob.glob("/tmp/progress-*.txt"), key=os.path.getmtime, reverse=True)


def find_progress(plan_path):
    name = os.path.basename(plan_path)
    for f in progress_files():
        header = progress_header(f).get("plan")
        if header and os.path.basename(header) == name:
            return f
    return "/tmp/progress-%s.txt" % os.path.splitext(name)[0]


def find_run(directory, own=None):
    """(plan, project, progress) of the exec run to show for the project holding DIRECTORY: the run OWN
    (progress file, cwd) of the session the dashboard opens on, when its Claude Code started one, else the
    project's newest run."""
    project = find_project(directory) or (find_project(own[1]) if own and own[1] else None)
    if not project:
        sys.exit("no docs/plans in %s or above" % directory)
    roots = plan_roots(project)
    branches = {r: git_branch(r) for r in roots}
    files = progress_files()
    if own:
        files = [own[0]] + [f for f in files if f != own[0]]
    for f in files:
        header = progress_header(f)
        rel, branch = header.get("plan"), header.get("branch")
        if not rel:
            continue
        # a run moved into a worktree ticks the plan copy there: the root on the run's branch goes first
        ordered = sorted(roots, key=lambda r: branches[r] != branch) if branch else roots
        candidates = [rel] if os.path.isabs(rel) else [os.path.join(r, rel) for r in ordered]
        for plan in candidates:
            if plan.startswith(project + os.sep) and resolve_plan(plan):
                return plan, project, f
    plans = [p for r in roots for p in glob.glob(os.path.join(r, "docs", "plans", "*.md"))]
    if not plans:
        sys.exit("no plan in %s/docs/plans" % project)
    plan = max(plans, key=os.path.getmtime)
    return plan, project, find_progress(plan)


# ---------------------------------------------------------------- watcher and overlay


def write_js(out_dir, data):
    tmp = os.path.join(out_dir, "data.js.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("window.onDashData(" + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + ");\n")
    os.replace(tmp, os.path.join(out_dir, "data.js"))


def watcher_pid(pid_file):
    try:
        pid = int(open(pid_file).read().strip())
        cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
    except (OSError, ValueError):
        return None
    return pid if SCRIPT in cmd and pid != os.getpid() else None


def spawn_watcher(plan, project, out_dir):
    """Start the refresh loop in a detached process that outlives this one."""
    # a long-lived child must not carry the launching session's AGTERM_* identity
    env = {k: v for k, v in os.environ.items() if not k.startswith(("AGTERM_", "AGT_"))}
    args = [sys.executable, os.path.abspath(__file__), plan, "--watch", "--project", project,
            "--interval", str(ARGS.interval), "--stall", str(ARGS.stall), "--context-limit", str(ARGS.context_limit)]
    if ARGS.socket:
        args += ["--socket", ARGS.socket]
    if ARGS.no_title:
        args.append("--no-title")
    with open(os.path.join(out_dir, "watcher.log"), "a") as log:
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True, env=env)


def is_dashboard(path):
    """Whether PATH is a page of this script's: ~/.cache/exec-dash/<plan>/index.html."""
    return bool(path) and os.path.dirname(os.path.dirname(os.path.realpath(path))) == os.path.realpath(CACHE)


def overlay_on(agterm, target):
    """'ours' when an exec dashboard covers TARGET (this run's or another's: the key toggles whichever is up),
    'other' for any other overlay, else None (a HUD gets replaced)."""
    for _, s in agterm.sessions():
        if not s["id"].upper().startswith(target.upper()):
            continue
        pages = s.get("htmlOverlays") or []
        if any(is_dashboard(p.get("file")) for p in pages):
            return "ours"
        return "other" if (s.get("overlay") or pages) else None
    return None


def watch(plan, project, progress, out_dir, agents, agterm):
    pid_file = os.path.join(out_dir, "watcher.pid")
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    done_at = None
    session_id = None
    try:
        while True:
            try:
                data = build(plan, progress, agents, agterm, project)
            except Exception:  # noqa: BLE001 - a half-moved file must not end the watcher
                traceback.print_exc()
                sys.stderr.flush()
                time.sleep(ARGS.interval)
                continue
            write_js(out_dir, data)
            if data["session"]:
                session_id = data["session"]["id"]
                agterm.set_title(data["session"], title_line(data, agterm.name))
            if data["completed"]:
                done_at = done_at or time.time()
                if time.time() - done_at > LINGER:
                    break
            if time.time() - (data["activity"] or 0) > IDLE_EXIT:
                break
            time.sleep(ARGS.interval)
    finally:
        agterm.clear_title(session_id)
        try:
            if open(pid_file).read().strip() == str(os.getpid()):
                os.remove(pid_file)
        except OSError:
            pass


# ---------------------------------------------------------------- main


def main():
    global ARGS
    env = os.environ.get
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("plan", nargs="?",
                   help="plan file (default: the --target session's own run, else the newest run of --project)")
    p.add_argument("--project", help="a directory in the project (default: the plan's project, else cwd)")
    p.add_argument("--open", action="store_true", help="open the dashboard in an agterm overlay")
    p.add_argument("--toggle", action="store_true", help="open the dashboard, or close it when it is open")
    p.add_argument("--stop", action="store_true", help="stop the plan's watcher")
    p.add_argument("--target", default=env("AGTERM_SESSION_ID") or env("AGT_SESSION_ID"),
                   help="session to show the overlay on (default: $AGTERM_SESSION_ID)")
    p.add_argument("--socket", default=env("AGTERM_SOCKET") or env("AGT_SOCKET"),
                   help="agterm control socket (default: $AGTERM_SOCKET)")
    p.add_argument("--no-title", action="store_true", help="leave the exec session's title-bar context line alone")
    p.add_argument("--interval", type=float, default=3, help="seconds between refreshes (default 3)")
    p.add_argument("--stall", type=float, default=600, help="warn when nothing was written for this long (default 600s)")
    p.add_argument("--context-limit", type=int, default=200000,
                   help="context window the orchestrator's context size is measured against (default 200000)")
    p.add_argument("--watch", action="store_true", help=argparse.SUPPRESS)  # internal: the refresh loop itself
    ARGS = p.parse_args()

    if ARGS.plan:
        plan = os.path.abspath(ARGS.plan)
        project = find_project(ARGS.project or os.path.dirname(plan)) or os.getcwd()
        progress = find_progress(plan)
    else:
        # the run of the session the dashboard opens on, when its Claude Code started one
        own = session_run(ARGS.target) if ARGS.target else None
        plan, project, progress = find_run(ARGS.project or os.getcwd(), own)
    current = resolve_plan(plan)
    if not current:
        sys.exit("plan not found: %s" % plan)
    out_dir = os.path.join(CACHE, os.path.splitext(os.path.basename(plan))[0])
    index = os.path.join(out_dir, "index.html")
    pid_file = os.path.join(out_dir, "watcher.pid")
    agterm = Agterm(ARGS.socket, None if ARGS.no_title else plan_name(current))

    if ARGS.stop:
        pid = watcher_pid(pid_file)
        if pid:
            os.kill(pid, signal.SIGTERM)
            for _ in range(50):
                if watcher_pid(pid_file) != pid:
                    break
                time.sleep(0.1)
        print("stopped %d" % pid if pid else "no watcher running")
        return

    showing = ARGS.open or ARGS.toggle
    if showing:
        if not ARGS.target:
            sys.exit("no session to show the dashboard on: pass --target")
        state = overlay_on(agterm, ARGS.target)
        if state == "ours" and ARGS.toggle:
            ok, err = agterm.call("session", "overlay", "close", "--target", ARGS.target)
            sys.exit(0 if ok else "could not close the dashboard: %s" % err)
        if state == "other":
            sys.exit("another overlay is open on this session; close it first")

    os.makedirs(out_dir, exist_ok=True)
    shutil.copyfile(TEMPLATE, index)
    agents = Agents(project, plan)
    if ARGS.watch:
        watch(plan, project, progress, out_dir, agents, agterm)
        return
    write_js(out_dir, build(plan, progress, agents, agterm, project))
    if not watcher_pid(pid_file):
        spawn_watcher(plan, project, out_dir)
    if showing:
        ok, err = agterm.call("session", "overlay", "open", "--html", index, "--cwd", out_dir, "--js",
                              "--target", ARGS.target)
        if not ok:
            sys.exit("could not open the dashboard: %s" % err)
    print(out_dir)


if __name__ == "__main__":
    main()
