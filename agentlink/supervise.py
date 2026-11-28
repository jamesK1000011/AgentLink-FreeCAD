# SPDX-License-Identifier: LGPL-2.1-or-later
# The headless server kept running: it serves in a child process, and when
# FreeCAD dies under a call (a crash in Open CASCADE takes the whole
# process), every call still waiting is answered with what happened and a
# fresh FreeCAD takes the next. Here, in the add-on, so whatever starts the
# server gets it without being changed.
#
# Unattended use (D, E, F): a watchdog reads the window's heartbeat (written
# from FreeCAD's main thread every 2 s, with any modal dialog in front) and
# times the call in hand. A FreeCAD that stops answering past its call's
# deadline is stopped by its own pid, started again in the background and
# its documents recovered from the newest good copy; a call stuck behind a
# dialog is answered "blocked by a dialog". Each of these is said once, in
# the answer to the call it happened in. Nothing is retried quietly.

import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time

try:
    from . import keep
except ImportError:
    keep = None
try:
    from . import window_watch
except ImportError:  # an update without it: no waiting for a restarting window
    window_watch = None
try:
    from . import sup_jobs
except ImportError:
    sup_jobs = None

FLAG = "AGENTLINK_SUPERVISED"
# The hidden FreeCAD's note that it took a call (protocol.TOOK; the same text,
# kept here so this module needs no FreeCAD-side import).
TOOK = "notifications/agentlink/took"
# How text that UTF-8 cannot hold (a lone surrogate, from a file name or an
# add-on's text) is written on the wire: as a backslash escape. Inside a JSON
# string that is a valid \uXXXX escape, so the line still goes out and parses;
# "strict" failed the write and the call had no answer.
WIRE_ERRORS = "backslashreplace"
WINDOW_PORT = int(os.environ.get("AGENTLINK_WINDOW_PORT", "7318"))
# Heavy tools: their deadline is their estimate times three (N); with no
# estimate yet, half an hour. The rest get a change's 120 s.
HEAVY = keep.HEAVY if keep is not None else set()
NO_ESTIMATE = 1800.0
# How long a heavy job waits for heat or memory pressure to pass before the
# answer says it waited and why.
QUEUE_WAIT = float(os.environ.get("AGENTLINK_QUEUE_WAIT", "600"))
PERSON_ACTIVE = 30.0


def queue_admit(tool):
    """A heavy job's turn (N): None to go, else the answer's words. Held when
    the person said wait (their window work came first); waits while macOS
    reports heat throttling or memory pressure, up to QUEUE_WAIT."""
    if keep is None or not keep.is_heavy(tool):
        return None
    q = keep.queue_state()
    if q.get("held"):
        return (f"Held: {q.get('notice') or 'the person was working in the window while a heavy job ran'}. New heavy jobs wait for their go — "
                "ask them in chat; queue_go once they say go.")
    t0 = time.time()
    while True:
        th = keep.mac_thermal()
        pr = keep.mac_pressure()
        if not th and pr not in ("warn", "critical"):
            break
        waited = time.time() - t0
        why = "macOS reports the Mac is throttling for heat" if th else f"macOS reports memory pressure ({pr})"
        if waited >= QUEUE_WAIT:
            return f"{tool} waited {int(waited)} s and did not start: {why}."
        time.sleep(min(15.0, max(1.0, QUEUE_WAIT - waited)))
    def admit(q):
        q["running"] = [{"tool": tool, "start": time.time(), "pid": os.getpid()}]

    keep.update_queue(admit)
    return None


def queue_done(tool):
    if keep is None or not keep.is_heavy(tool):
        return

    def done(q):
        q["running"] = [r for r in q.get("running") or [] if r.get("tool") != tool]
        keep.settled_notice(q)

    # Under the queue's lock (keep.queue_lock): the watchdog's "held" write
    # can no longer put back the entry taken out here (round 8, 00-042).
    keep.update_queue(done)


def queue_hold(person_active, busy, now=None):
    """The watchdog's turn on the queue, under its lock: leftovers taken
    out (keep.stale_running: no call in hand, or their FreeCAD gone), and,
    with the person working in the window while a heavy job runs, the queue
    held with its notice. person_active is asked of macOS before the lock
    (that is the slow part). {held, dropped} or None."""
    if keep is None:
        return None
    now = time.time() if now is None else now
    out = {}

    def turn(q):
        gone = keep.stale_running(q, busy, now=now)
        if gone:
            out["dropped"] = [r.get("tool") for r in gone if isinstance(r, dict)]
            keep.settled_notice(q)
        if q.get("running") and not q.get("held") and person_active:
            r = q["running"][0]
            q["held"] = True
            q["notice"] = f"A heavy job is running ({r.get('tool')}, since {time.strftime('%H:%M', time.localtime(r.get('start') or r.get('t') or now))}); new heavy jobs wait for your go"
            out["held"] = r.get("tool")
        return None if out else False

    keep.update_queue(turn)
    return out or None
# A call stuck behind a dialog this long is answered "blocked".
DIALOG_WAIT = 4.0
# A call held this long by a menu (a popup in the heartbeat, which no modal
# check sees) is answered "busy" after the menu is closed through the
# window's socket thread (gui_unstick), never by stopping FreeCAD.
POPUP_WAIT = float(os.environ.get("AGENTLINK_POPUP_WAIT", "10"))
# A dialog answer's own allowance: the first call into a window that has
# just started builds its session first (several seconds), so the answer to
# FreeCAD's Document Recovery at start was refused on every first try.
ANSWER_WAIT = 30.0


def _kinded(err):
    """The refusal's kind and its sentence (protocol.set_kind), when the
    protocol module loads here."""
    try:
        from .protocol import set_kind

        return set_kind(err)
    except Exception:  # noqa: BLE001 - words only
        return err


def _answer(mid, code, message, outcome=None):
    text = json.dumps({"error": _kinded({"code": code, "message": message, **({"status": outcome} if outcome else {})})})
    return json.dumps({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}], "isError": True}})


def _answer_body(mid, body):
    return json.dumps({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(body)}], "isError": True}})


def _result(mid, body):
    return json.dumps({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(body)}]}})


FREECAD_APP = "/Applications/FreeCAD.app"


def _is_force_restart(line):
    """app_force_restart, alone or as a batch of nothing else: a client lists
    tools only when it starts, so a new tool is reached through batch, and
    a batch would go to the very window that is stuck."""
    _mid, tool, args = _call_info(line)
    if tool == "app_force_restart":
        return True
    calls = (args or {}).get("calls") if tool == "batch" else None
    return bool(calls) and all(isinstance(c, dict) and c.get("tool") == "app_force_restart" for c in calls)


def _is_app_open(line):
    """app_open, alone or as a batch of nothing else: answered by the
    supervisor, which can start the window (the hidden FreeCAD cannot)."""
    _mid, tool, args = _call_info(line)
    if tool == "app_open":
        return True
    calls = (args or {}).get("calls") if tool == "batch" else None
    return bool(calls) and all(isinstance(c, dict) and c.get("tool") == "app_open" for c in calls)


def _unstick_call(line):
    """gui_unstick alone or as a batch of nothing else: ("alone" | "batch",
    all), else None. Answered here on a connection of its own, never behind
    the call a menu or dialog holds."""
    _mid, tool, args = _call_info(line)
    if tool == "gui_unstick":
        return ("alone", bool((args or {}).get("all")))
    calls = (args or {}).get("calls") if tool == "batch" else None
    if calls and all(isinstance(c, dict) and c.get("tool") == "gui_unstick" for c in calls):
        return ("batch", any(bool(c.get("all")) for c in calls))
    return None


def _call_info(line):
    try:
        m = json.loads(line)
    except ValueError:
        return None, None, None
    p = m.get("params") or {}
    return m.get("id"), p.get("name"), p.get("arguments") or {}


def deadline_for(tool, args=None, started=None):
    """Seconds the call in hand runs before the watchdog looks at it for a
    hang at all: a change's 120 s, or the call's own timeout and a minute.
    No estimate is read here (no prejudging): a FreeCAD past this is
    stopped only when it is truly hung (stalled: no heartbeat and no CPU
    work), never because it is slow."""
    if keep is None:
        return NO_ESTIMATE
    if os.environ.get("AGENTLINK_DEADLINE"):
        return float(os.environ["AGENTLINK_DEADLINE"])
    limit = keep.deadline("change")
    own = keep.call_deadline(tool, args)
    return max(limit, own) if own else limit


# ---- a true hang: no heartbeat and no CPU work ----------------------------------------------

# Seconds with no CPU work (FreeCAD and the processes it started) before a
# call with no heartbeat is taken for hung. A long OCC call keeps the CPU
# busy and is never stopped; a deadlock or a wait on nothing is.
STALL = float(os.environ.get("AGENTLINK_STALL", "60"))
# CPU seconds of progress over STALL that count as work.
STALL_CPU = float(os.environ.get("AGENTLINK_STALL_CPU", "0.5"))
# A FreeCAD with no heartbeat this long is stopped even while its CPU is
# busy (a loop that never ends). The person can app_force_restart sooner.
HANG_CEILING = float(os.environ.get("AGENTLINK_HANG_CEILING", "7200"))


def _clock_secs(text):
    """ps's cputime ("[[dd-]hh:]mm:ss[.xx]") in seconds, or None."""
    t = str(text or "").strip()
    if not t:
        return None
    days = 0
    if "-" in t:
        d, t = t.split("-", 1)
        try:
            days = int(d)
        except ValueError:
            return None
    try:
        parts = [float(x) for x in t.split(":")]
    except ValueError:
        return None
    secs = 0.0
    for p in parts:
        secs = secs * 60 + p
    return days * 86400 + secs


def cpu_tree(pid, table):
    """CPU seconds of pid and every process under it, from ps rows
    [(pid, ppid, secs)] (FreeCAD's solver children count: a CalculiX run
    is FreeCAD's work)."""
    kids = {}
    own = {}
    for p, pp, secs in table:
        kids.setdefault(pp, []).append(p)
        own[p] = secs
    if pid not in own:
        return None
    total, stack, seen = 0.0, [pid], set()
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        total += own.get(p) or 0.0
        stack.extend(kids.get(p, ()))
    return total


def ps_table():
    """[(pid, ppid, cpu secs)] of every process, or None when ps fails."""
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,time="], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    rows = []
    for line in out.splitlines():
        bits = line.split()
        if len(bits) < 3:
            continue
        try:
            secs = _clock_secs(bits[2])
            if secs is not None:
                rows.append((int(bits[0]), int(bits[1]), secs))
        except ValueError:
            continue
    return rows


class Progress:
    """CPU work of a process over time, for the hang rule. table(): the
    ps rows (a stand-in in the tests)."""

    def __init__(self, table=ps_table, clock=time.time):
        self.table = table
        self.clock = clock
        self.seen = {}  # pid -> (t of last progress, cpu then)

    def idle_for(self, pid, now=None):
        """Seconds since pid (with its children) last did CPU work, or None
        when its CPU cannot be read."""
        now = self.clock() if now is None else now
        rows = self.table()
        cpu = cpu_tree(int(pid), rows) if rows else None
        if cpu is None:
            return None
        got = self.seen.get(pid)
        if got is None or cpu - got[1] >= STALL_CPU:
            self.seen[pid] = (now, cpu)
            return 0.0
        return now - got[0]

    def forget(self, pid):
        self.seen.pop(pid, None)


def stalled(now, started, last_beat, limit, idle):
    """A true hang: past the call's limit, no heartbeat for keep.GRACE, and
    no CPU work for STALL (idle; None when it cannot be read: then only
    HANG_CEILING with no heartbeat). Or no heartbeat for HANG_CEILING."""
    grace = keep.GRACE if keep is not None else 60.0
    if now - started <= limit or now - last_beat <= grace:
        return False
    if now - last_beat > HANG_CEILING:
        return True
    return idle is not None and idle >= STALL


def _deadline(tool):
    if keep.is_heavy(tool):
        try:
            q = keep.queue_state()
            tm = q.get("timings") or {}
            # A tool timed against its own work (view_render's triangles x
            # views, heavy.WORK) keeps those runs under "tool:work".
            pts = (tm.get(tool) or []) + (tm.get(tool + ":work") or [])
            if pts:
                return keep.deadline("heavy", max(t for _, t in pts))
        except Exception:
            pass
        return NO_ESTIMATE
    return keep.deadline("change")


def nested_hang(hb, now, limit=None, fresh=10.0):
    """The window held by a call that will not end, though its heartbeat
    goes on: the GUI thread is inside a nested event loop (loops > 1, a
    dialog's or menu's own) with nothing open in front, past the call's
    deadline — limit (deadline_for its tool) or the until it said itself
    (live_run) — or the call's own guard gave up on that loop (stuck). The
    heartbeat is written from inside that loop, so the stale-heartbeat rule
    never saw it (live: busy "batch" for 12 minutes, every later call timed
    out). {tool, after, why} or None."""
    if not isinstance(hb, dict) or not hb.get("busy") or hb.get("dialog") or hb.get("popup"):
        return None
    try:
        since, t = float(hb.get("busySince") or 0), float(hb.get("t") or 0)
        front_at = float(hb.get("frontAt") or 0)
    except (TypeError, ValueError):
        return None
    if not since or now - t > fresh:
        return None  # no heartbeat: the hang rule by pings sees that one
    # A dialog or menu held the call (the person's time, not the call's):
    # the nested loop is timed from when it was last seen in front (live 87:
    # OK in a dialog that lived 112 s, the loop still ending, was taken for
    # a hang and FreeCAD was force-restarted).
    after = now - max(since, front_at)
    loops = hb.get("loops")
    nested = loops is None or (isinstance(loops, (int, float)) and loops > 1)
    out = {"tool": hb["busy"], "after": after}
    if hb.get("stuck") and nested:
        return {**out, "why": "its own guard gave up on a nested event loop"}
    until = hb.get("until")
    if until:
        try:
            past = now > float(until)
        except (TypeError, ValueError):
            past = False
        return {**out, "why": "past the time it said it would be done by, inside a nested event loop"} if past and nested else None
    if loops is not None and nested and limit is not None and after > limit:
        return {**out, "why": f"past its deadline ({int(limit)} s) inside a nested event loop with nothing open"}
    return None


# ---- after a restart: only what was open then comes back ----------------------------------

def docs_at_restart(*beats, pid=None):
    """The heartbeat that says what was open when FreeCAD was stopped: the
    newest of that FreeCAD's (by pid when known). An older heartbeat kept
    from an earlier call can list documents long closed since."""
    cands = [h for h in beats if isinstance(h, dict) and h]
    if pid is not None:
        cands = [h for h in cands if h.get("pid") == pid] or cands
    if not cands:
        return {}
    return max(cands, key=lambda h: float(h.get("t") or 0))


def hidden_docs(hidden, pid):
    """The documents of hidden.json that the FreeCAD which died held: none
    when the file is another FreeCAD's (an earlier session's)."""
    if not isinstance(hidden, dict):
        return []
    if pid is not None and hidden.get("pid") not in (None, pid):
        return []
    return [d for d in hidden.get("docs") or [] if isinstance(d, dict) and d.get("name")]


def temp_copy(file):
    """A document file in a temporary folder: a recovered copy (an add-on's
    agentlink-recovered- folders) or one of FreeCAD's own recovery files."""
    f = str(file or "")
    if not f:
        return False
    if os.path.basename(os.path.dirname(f)).startswith("agentlink-recovered-"):
        return True
    if ".agentlink-recovered-" in os.path.basename(f):  # a copy kept beside its original
        return True
    if "fc_recovery_file" in f.replace("\\", "/").lower():
        return True
    try:
        import tempfile

        tmp = os.path.realpath(tempfile.gettempdir())
        return os.path.realpath(f).startswith(tmp + os.sep)
    except Exception:
        return False


RECOVERED_LABEL = re.compile(r"\(recovered[^)]*\)\s*$")


def recoverable(docs):
    """The documents open at the stop that are recovered after the restart,
    and those left out: a "(recovered …)" copy from an earlier restart that
    nobody changed (the heartbeat's modified) is not recovered again — each
    restart reopened every old copy as well (live: "AgentLink (recovered
    15:55)" and "M18TestDrive-v3 (recovered 03:59)" came back again).
    (kept, left out)."""
    reopen, rec, left = restart_split(docs)
    return reopen + rec, left


def _is_copy(d):
    """A recovered copy: named "(recovered …)" or opened from a temporary
    folder (a copy whose label was put back to its original's)."""
    return bool(RECOVERED_LABEL.search(str(d.get("label") or ""))) or temp_copy(d.get("file"))


def reopened_by_recover(got):
    """The documents app_recover's answer says it opened again from their
    own files (its "reopened": [{ document, label, why }], from the add-on
    that recovers documents), by label — for the restart's own words."""
    out = []
    for r in (got or {}).get("reopened") or []:
        if isinstance(r, dict):
            name = r.get("label") or r.get("document") or r.get("name")
        else:
            name = r
        if name:
            out.append(str(name))
    return out


def restart_split(docs):
    """What happens to each document open at the stop, once FreeCAD is back,
    each document once (by its file, else its name):
    reopen — saved and unchanged: opened again from its own file, as itself
      (it came back as a "(recovered …)" copy though nothing was lost);
    recover — changed since saved, or never saved: from its newest saved
      copy (app_recover auto), each with modified said (true or false);
    left — a recovered copy nobody changed since it opened: not recovered
      again (a copy of a copy).
    (reopen, recover, left)"""
    reopen, rec, left, seen = [], [], [], set()
    for d in docs or []:
        if not isinstance(d, dict) or not (d.get("name") or d.get("label")):
            continue
        f = d.get("file") or ""
        key = ("file", os.path.abspath(f)) if f else ("name", d.get("name") or d.get("label"))
        if key in seen:
            continue
        seen.add(key)
        changed = bool(d.get("modified"))
        if _is_copy(d):
            (rec if changed else left).append(dict(d, modified=changed))
        elif f and not changed:
            reopen.append(d)
        else:
            rec.append(dict(d, modified=changed))
    return reopen, rec, left


def once(labels):
    """Labels for a record, each document once, in order."""
    out = []
    for x in labels or []:
        if x and x not in out:
            out.append(x)
    return out


def newer_copies(listing, since):
    """Of app_recover list's answer, the documents (names and labels) with a
    saved copy written after since (when the heartbeat last read them
    unchanged): a checkpoint taken inside the call that hung holds more than
    the file, so those are recovered, not reopened."""
    out = set()
    try:
        since = float(since or 0)
    except (TypeError, ValueError):
        since = 0.0
    if not isinstance(listing, dict) or not since:
        return out
    for e in listing.get("documents") or []:
        if not isinstance(e, dict):
            continue
        for c in e.get("copies") or []:
            try:
                if os.path.getmtime(c.get("path") or "") > since + 1.0:
                    out |= {e.get("document"), e.get("label")}
                    break
            except (OSError, TypeError):
                continue
    out.discard(None)
    return out


def base_label(label):
    """A label without its "(recovered …)" mark: the document it is a copy of."""
    return RECOVERED_LABEL.sub("", str(label or "")).strip()


def _copy_candidates(before, recovered, now_docs):
    """Documents open in the FreeCAD just started that were not open when it
    stopped and are copies (from a temporary folder, or "(recovered …)"),
    each with whether it must be kept: (doc, why kept or None)."""
    files = {os.path.abspath(d["file"]) for d in before or [] if isinstance(d, dict) and d.get("file")}
    fresh = {r.get("document") for r in recovered or [] if isinstance(r, dict) and r.get("document")}
    fresh |= {r.get("as") for r in recovered or [] if isinstance(r, dict) and r.get("as")}
    # The documents open at the stop that were never saved to a file of
    # their own (no file, or one in a temporary folder), by label: a copy
    # of one of them may be the only copy of its work, never a stray (live,
    # 18 Nov: "M18Build (recovered)", of a document never saved, was closed
    # as one and all its work was lost).
    unsaved = {base_label(d.get("label") or d.get("name")) for d in before or []
               if isinstance(d, dict) and (d.get("label") or d.get("name")) and (not d.get("file") or temp_copy(d.get("file")))}
    out = []
    for d in now_docs or []:
        if not isinstance(d, dict) or not d.get("name"):
            continue
        if d.get("name") in fresh or d.get("label") in fresh:
            continue
        f = d.get("file") or ""
        if f and os.path.abspath(f) in files:
            continue
        # A copy from a temporary folder, or an earlier "(recovered …)" copy
        # reopened from wherever it was kept, not open at the stop.
        if not temp_copy(f) and not RECOVERED_LABEL.search(str(d.get("label") or "")):
            continue
        if base_label(d.get("label") or d.get("name")) in unsaved:
            out.append((d, "unsaved"))
        elif d.get("modified"):
            out.append((d, "changed"))
        else:
            out.append((d, None))
    return out


def strays(before, recovered, now_docs):
    """Documents open in the FreeCAD just started that were not open when it
    stopped: copies opened again from temporary folders (old recovered
    copies). Not the copies just recovered, not a file that was open, not a
    copy of a document never saved that was open at the stop (kept_copies:
    it may be the only copy of its work), and not a copy with changes of
    its own."""
    return [d for d, why in _copy_candidates(before, recovered, now_docs) if why is None]


def kept_copies(before, recovered, now_docs):
    """The copies strays leaves open: [(doc, why)], why "unsaved" (a copy
    of a document open at the stop and never saved: maybe its only copy)
    or "changed" (changes of its own)."""
    return [(d, why) for d, why in _copy_candidates(before, recovered, now_docs) if why is not None]


def stop_pid(pid, grace=10.0):
    """TERM, then KILL after grace seconds, on that one process."""
    if not pid or int(pid) in (os.getpid(), os.getppid(), 0, 1):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    t0 = time.time()
    while time.time() - t0 < grace:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def _memory_job(q, window, state):
    """The heavy job in hand for the critical-pressure guard: {tool, start,
    pid (its FreeCAD)}, or None."""
    run = [r for r in (q or {}).get("running") or [] if isinstance(r, dict) and r.get("tool")]
    if not run:
        return None
    r = run[0]
    pid = r.get("pid")
    if not pid or pid == os.getpid():
        hb = heartbeat() or {}
        pid = hb.get("pid") if getattr(window, "inflight", None) else getattr((state or {}).get("child"), "pid", None)
    return {"tool": r.get("tool"), "start": float(r.get("start") or r.get("t") or time.time()), "pid": pid}


OWN = "AGENTLINK_OWN"
OWN_ID = "AGENTLINK_OWN_ID"


def own_mode(argv=None):
    """True when this server is asked to keep apart from the FreeCAD window
    (--own, or AGENTLINK_OWN=1): its calls never go to the window's link, and
    its hidden FreeCAD keeps its run marks in a folder of its own."""
    if argv is not None and "--own" in argv:
        return True
    return os.environ.get(OWN, "").strip().lower() in ("1", "true", "on", "yes")


def set_own(argv):
    """--own given: said in the environment for this process and the hidden
    FreeCAD it starts, with an id of its own (this process's pid) for its
    run marks (keep.runtime). Answers whether own mode is on."""
    if not own_mode(argv):
        return False
    os.environ[OWN] = "1"
    os.environ.setdefault(OWN_ID, str(os.getpid()))
    return True


SUPERVISOR_INFO = {"name": "agentlink-supervisor", "version": "1"}


def restart_initialize(client_info=None):
    """The initialize line for a FreeCAD started again: with the clientInfo
    the MCP client gave (so the fresh one knows the same client: approvals
    count only from a client that asks the person first), else the
    supervisor's own."""
    info = client_info if isinstance(client_info, dict) and client_info.get("name") else SUPERVISOR_INFO
    return json.dumps({"jsonrpc": "2.0", "id": "__restart", "method": "initialize",
                       "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": info}})


def client_line(client_info):
    """The line that tells the window link which MCP client this supervisor
    serves (protocol.CLIENT_METHOD), or None when the client gave no name."""
    if not (isinstance(client_info, dict) and client_info.get("name")):
        return None
    return json.dumps({"jsonrpc": "2.0", "id": "__client", "method": "agentlink/client", "params": {"clientInfo": client_info}})


def heartbeat():
    if keep is None:
        return None
    hb = keep._load(keep.path("heartbeat.json"), None)
    return hb if isinstance(hb, dict) else None


def heartbeat_any():
    """The heartbeat for window_watch (a test may set keep to None)."""
    return heartbeat()


def relaunch(app, why):
    """The window started again in the background (never in front). The
    command can be set (AGENTLINK_RELAUNCH, a JSON argv with {app}) for
    systems without macOS's open."""
    if keep is not None:
        keep.mark_launch(None, why)
    custom = os.environ.get("AGENTLINK_RELAUNCH")
    if custom:
        argv = [a.replace("{app}", app or "") for a in json.loads(custom)]
    elif sys.platform == "darwin" and app and app.endswith(".app"):
        argv = ["open", "-g", "-a", app]
    else:
        return False
    try:
        subprocess.Popen(argv, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def _answers_dialog(c):
    """A call that is itself the answer to the dialog in front (dialog_answer,
    or a batch of nothing but dialog_answer): never abandoned for waiting
    behind that dialog. The dialog's age ran past DIALOG_WAIT long before, so
    each such call was answered "waiting behind it" before it could run
    (GUI pass, FreeCAD's Preferences opened by a command). gui_input too:
    the window takes it only aimed inside the dialog."""
    try:
        from .protocol import front_call
    except ImportError:  # run apart from its package: the plain reading
        front = ("dialog_answer", "gui_input", "gui_unstick")
        calls = (c.get("args") or {}).get("calls") if c.get("tool") == "batch" and isinstance(c.get("args"), dict) else None
        return c.get("tool") in front or (isinstance(calls, list) and bool(calls) and all(isinstance(x, dict) and x.get("tool") in front for x in calls))
    return front_call(c.get("tool"), c.get("args"))


# The same words as protocol.ORIENT_HEAD (tests/test_orient_1122.py checks):
# the orientation's start in the words sent at initialize.
ORIENT_HEAD = "\n\nWhere you are, read at connect (session_state reads it again): "


class Window:
    """The FreeCAD window's link (the workbench's Start link), when it is on.
    Tried afresh for each call, so turning the link on or off takes effect
    at the next call; off (or AGENTLINK_WINDOW=0), calls stay hidden."""

    def __init__(self, write):
        self.write = write
        self.f = None
        self.sock = None
        # --own (AGENTLINK_OWN=1): this server never uses the window; its
        # calls run in its own hidden FreeCAD.
        self.own = own_mode()
        self.off = os.environ.get("AGENTLINK_WINDOW", "1") == "0" or self.own
        self.client_info = None  # the MCP client's clientInfo (its initialize), told to the window at each connection
        self.seen = False  # the window has answered this session
        self.inflight = None  # {id, tool, args, start}
        self.answered = set()  # ids answered early (a dialog, a hang)
        self.hang = None  # set by the watchdog before it stops the window
        self.last_hb = None
        self.lock = threading.Lock()
        self.last_reply = None  # the window's last answer line (app_restart's "restarting")
        # The window going down and back (finding 52): no mark file, no
        # fixed wait (agentlink/window_watch.py).
        self.watch = window_watch.Watch(heartbeat_any) if window_watch is not None else None
        if self.watch is not None:
            r = window_watch.restart_from_env()
            if r:
                # agentlink_update restarted the window before this
                # supervisor started: the launcher says so.
                self.watch.expect(r.get("pid"), pinned=r.get("pinned"), t=r.get("t"), why="agentlink_update")

    def _open(self):
        import socket

        if self.f is not None:
            return True
        # A window from before pairing (its heartbeat says nothing of it)
        # cannot pair: the hidden FreeCAD answers at once rather than after
        # a wait each call, and the person is told once to restart FreeCAD.
        hb = heartbeat() if keep is not None else None
        if hb and not hb.get("pairing") and time.time() - float(hb.get("t") or 0) < 10:
            if not getattr(self, "_told_old", False):
                self._told_old = True
                sys.stderr.write("Agent Link: the FreeCAD window runs add-ons from before the update (no pairing); restart FreeCAD (app_restart) to finish it.\n")
            return False
        if time.time() < getattr(self, "_pair_failed_until", 0):
            return False
        try:
            s = socket.create_connection(("127.0.0.1", WINDOW_PORT), timeout=0.3)
        except OSError:
            return False
        f = s.makefile("rw", encoding="utf-8", errors=WIRE_ERRORS, newline="\n")
        # Paired first (agentlink/link_token.py): both sides prove they know
        # the window's token. Whatever cannot is not the window: the hidden
        # FreeCAD answers instead.
        try:
            from . import link_token

            s.settimeout(5)
            link_token.client_pair(f)
        except ImportError:
            pass
        except Exception as e:  # noqa: BLE001 — Refused, a timeout, a reset
            sys.stderr.write(f"Agent Link: the window's port did not pair ({e}); the hidden FreeCAD answers.\n")
            self._pair_failed_until = time.time() + 30
            try:
                s.close()
            except OSError:
                pass
            return False
        s.settimeout(None)
        self.sock = s
        self.f = f
        self._tell_client()
        return True

    def _tell_client(self):
        """The window learns which MCP client this connection serves (the
        window never sees the client's initialize). An older window that
        does not know the line answers an error, which is left alone."""
        line = client_line(self.client_info)
        if line is None or self.f is None:
            return
        try:
            self._send(line, forward=False)
        except Exception:  # noqa: BLE001 - the calls still go on
            pass

    def note_client(self, client_info):
        """The MCP client's initialize came: its clientInfo, told to the
        window now when connected, else at the next connection."""
        if not isinstance(client_info, dict) or client_info == self.client_info:
            return
        self.client_info = client_info
        if self.f is not None:
            self._tell_client()

    def _drop(self):
        try:
            if self.sock is not None:
                import socket

                self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.f = None
        self.sock = None

    def _ready(self):
        """Connected to the window: True. While a restart is in hand
        (window_watch: app_restart answered, the launcher's word after
        agentlink_update, macOS saw FreeCAD start), the call waits for the
        first heartbeat of the new pid that pairs, up to window_watch.WAIT:
        True once it is back, else the words of the call's clear refusal.
        False: no window and no restart (the hidden FreeCAD answers)."""
        if self.watch is not None and self.watch.pending():
            if self.watch.back() is None:
                self._drop()  # the old window's connection: never used again
            got = self.watch.wait(self._open)
            if got is True:
                self._back_from_restart()
                return True
            if isinstance(got, str):
                return got
        if self._open():
            if self.watch is not None and self.watch.restart is not None:
                self._back_from_restart()
            return True
        if self.watch is not None:
            lost = self.watch.take_lost()
            if lost:
                return window_watch.Watch.lost_words(lost)
        return False

    def _back_from_restart(self):
        """The new window paired after a restart: the agent's pinned
        document of before made the session's document again (finding
        40: after a restart the front document was another one, and a
        call went to the wrong document). Never raises."""
        r = self.watch.done() if self.watch is not None else None
        pinned = (r or {}).get("pinned")
        if not pinned:
            return None
        try:
            hb = heartbeat_any() or {}
            # The window reopens its documents after it pairs: a few
            # seconds for the pinned one to be open.
            t0 = time.time()
            target = window_watch.pin_target(pinned, hb.get("docs"))
            while target is None and time.time() - t0 < 20:
                time.sleep(0.5)
                hb = heartbeat_any() or {}
                target = window_watch.pin_target(pinned, hb.get("docs"))
            if target is None:
                if keep is not None:
                    keep.log_watchdog({"event": "pin", "document": pinned.get("label") or pinned.get("name"), "found": False})
                return None
            if hb.get("pinned") == target:
                return target
            got = self.ask("doc_switch", {"document": target}, timeout=30)
            if keep is not None:
                keep.log_watchdog({"event": "pin", "document": target, "switched": got is not None})
            return target
        except Exception as e:  # noqa: BLE001 — a nicety on the way back
            sys.stderr.write(f"Agent Link: pinned document not restored ({e})\n")
            return None

    def _note_restart(self, tool, hb):
        """app_restart answered "restarting": the window goes down and a
        new one comes; calls wait for it (window_watch)."""
        if self.watch is None or tool not in ("app_restart",) or not self.last_reply:
            return
        try:
            r = json.loads(self.last_reply).get("result") or {}
            body = json.loads(r["content"][0]["text"]) if not r.get("isError") else {}
        except (ValueError, KeyError, IndexError, TypeError):
            body = {}
        if isinstance(body, dict) and body.get("restarting") and hb and hb.get("pid"):
            self.watch.expect(hb.get("pid"), pinned=window_watch.pinned_of(hb), why="app_restart")

    def _send(self, line, forward=True):
        """One go at the window: its answer (True, or the reply line when not
        forwarded), or False when it went away first."""
        try:
            mid = json.loads(line).get("id")
            self.f.write(line if line.endswith("\n") else line + "\n")
            self.f.flush()
            while True:
                got = self.f.readline()
                if not got:
                    raise OSError("window closed")
                got = got.rstrip("\n")
                if not got:
                    continue
                try:
                    gid = json.loads(got).get("id")
                except ValueError:
                    gid = None
                if forward and gid not in self.answered:
                    self.write(got)
                if gid == mid:
                    self.seen = True
                    self.last_reply = got
                    return True if forward else got
        except (OSError, AttributeError):
            self.f = None
            return False

    def ask(self, tool, args, timeout=180.0):
        """A call of the supervisor's own (recovery): its result, not passed on."""
        line = json.dumps({"jsonrpc": "2.0", "id": f"__sup{time.time()}", "method": "tools/call", "params": {"name": tool, "arguments": args}})
        t0 = time.time()
        while time.time() - t0 < timeout and not self._open():
            time.sleep(1)
        if self.f is None:
            return None
        got = self._send(line, forward=False)
        if not got:
            return None
        try:
            r = json.loads(got)["result"]
            return json.loads(r["content"][0]["text"])
        except (ValueError, KeyError, TypeError):
            return None

    def _refuse(self, line, why, code="invalid_state"):
        mid, _, _ = _call_info(line)
        self.write(_answer(mid, code, why))
        return True

    def abandon(self, why, code="invalid_state"):
        """Answer the call in hand now (a dialog holds it) and let go of the
        connection, so the next call can be taken; its late answer is dropped."""
        with self.lock:
            c = self.inflight
            if not c or c["id"] in self.answered:
                return False
            self.answered.add(c["id"])
            self.write(_answer(c["id"], code, why))
            c["abandoned"] = True
        self._drop()
        return True

    def unstick(self, timeout=6.0, all_=False):
        """gui_unstick on a connection of its own (the one in use waits on
        the call a menu holds): what it closed, or None when the window did
        not answer."""
        return self.side_call("gui_unstick", {"all": True} if all_ else {}, timeout)

    def settle_dialog(self, old_pid, t0, wait=45.0, tries=3):
        """After a restart, FreeCAD's Document Recovery the link pressed but
        that stayed up (live, 18 Nov: the log said pressed: cancel, the
        dialog stayed about 5 min and the heartbeat went stale; a
        dialog_answer { button: Cancel } then freed the window): verified
        here from the new window's heartbeat, and answered again through a
        connection of its own (dialog_answer Cancel) while it stays. Ends at
        once when the new window beats with nothing in front. The tries it
        took (0: none needed)."""
        start = time.time()
        done, end, seen = 0, start + wait, None
        while time.time() < end:
            hb = heartbeat()
            if not (hb and hb.get("pid") != old_pid and float(hb.get("t") or 0) > t0):
                if time.time() - start > 15.0:
                    return done  # no heartbeat of the new window: nothing to verify by
                time.sleep(0.5)
                continue
            now = time.time()
            fresh = now - float(hb.get("t") or 0) < 8.0
            dlg = hb.get("dialog")
            if fresh and not dlg:
                return done
            if dlg and keep is not None and keep.dialog_answer_for(dlg, ours=True)[0] == "press" and "recover" in (str(dlg.get("title")) + str(dlg.get("text"))).lower():
                seen = dlg
            if seen is None and not fresh:
                return done  # held by something other than Document Recovery: the watchdog's own rules
            stuck = seen is not None and (not fresh or dlg.get("pressFailed") or (dlg.get("pressed") and now - float(dlg.get("since") or now) > 8.0))
            if stuck and done < tries:
                got = self.side_call("dialog_answer", {"button": "Cancel"}, timeout=10.0)
                done += 1
                if keep is not None:
                    keep.log_watchdog({"event": "dialog", "by": "supervisor", "title": seen.get("title"), "pressed": "Cancel", "try": done, "answered": got is not None})
                time.sleep(4.0)
                continue
            if stuck:
                return done
            time.sleep(1.0)
        return done

    def side_call(self, tool, args, timeout=6.0):
        """One call on a connection of its own, beside the one in use: its
        answer (the tool's JSON), or None when the window did not answer or
        refused it."""
        tmp = Window(lambda line: None)
        tmp.off = False
        if not tmp._open():
            return None
        line = json.dumps({"jsonrpc": "2.0", "id": f"__side{time.time()}", "method": "tools/call", "params": {"name": tool, "arguments": args or {}}})
        try:
            tmp.sock.settimeout(timeout)
            got = tmp._send(line, forward=False)
        finally:
            tmp._drop()
        if not got:
            return None
        try:
            r = json.loads(got)["result"]
            return None if r.get("isError") else json.loads(r["content"][0]["text"])
        except (ValueError, KeyError, TypeError):
            return None

    def open_window(self, wait=90.0):
        """app_open: the FreeCAD window started in the background (open -g:
        never in front, no focus taken) when it is closed, and paired. The
        words for the answer, and whether a window answers now."""
        if self.off:
            why = "this server runs its own hidden FreeCAD (--own)" if self.own else "AGENTLINK_WINDOW=0"
            return {"opened": False, "note": f"The window link is off here ({why}): calls go to the hidden FreeCAD."}
        if self._open():
            return {"opened": False, "already": True, "note": "The FreeCAD window is open and linked."}
        hb = heartbeat() or self.last_hb or {}
        app = hb.get("app") or (FREECAD_APP if os.path.isdir(FREECAD_APP) else None)
        if not relaunch(app, "app_open"):
            return {"opened": False, "note": "FreeCAD could not be started from here (no FreeCAD.app found). The hidden FreeCAD takes the calls."}
        self.f = None
        t0 = time.time()
        while time.time() - t0 < wait and not self._open():
            time.sleep(1)
        if self.f is None:
            return {"opened": False, "started": True, "note": f"FreeCAD was started in the background, but its link did not come up within {int(wait)} s. "
                    "Call session_state in a moment: calls go to the window when it pairs."}
        if keep is not None:
            keep.log_watchdog({"event": "app_open", "app": app, "s": round(time.time() - t0, 1)})
        return {"opened": True, "seconds": round(time.time() - t0, 1), "app": app,
                "note": "The FreeCAD window is open in the background (not in front) and linked. Its documents are the ones it reopens; session_state tells which."}

    def force_restart(self):
        """app_force_restart, run here outside FreeCAD so it works whatever
        holds the window (a dialog, a hang, a crash half-way): the window's
        process stopped (TERM, then KILL), the call in hand answered, FreeCAD
        started again in the background and its documents recovered, as after
        a crash. The words for the answer."""
        # The newest heartbeat first: the one kept from before may name a
        # window that is gone, and its pid would stop nothing.
        hb = heartbeat() or self.last_hb or {}
        self.last_hb = hb
        pid, t0 = hb.get("pid"), time.time()
        if keep is not None:
            keep.log_watchdog({"event": "force_restart", "pid": pid})
        self.abandon("FreeCAD was force-restarted (app_force_restart) while this call waited; it did not finish.", code="failed")
        if pid:
            stop_pid(int(pid), grace=3.0)
        self.f = None
        if not hb.get("app"):
            hb = dict(hb, app=FREECAD_APP if os.path.isdir(FREECAD_APP) else None)
            self.last_hb = hb
        return self.recover("forced restart", "app_force_restart", t0)

    def recover(self, why, tool, t_crash):
        """After the window died (a crash or the watchdog): started again in
        the background and its documents recovered from the newest copy that
        opens. The words for the answer."""
        stopped = (self.hang or {}).get("pid")
        hb = docs_at_restart(self.last_hb, heartbeat(), pid=stopped)
        app, docs = hb.get("app"), hb.get("docs") or []
        if keep is not None:
            keep.log_watchdog({"event": why, "tool": tool, "docs": once(d.get("label") or d.get("name") for d in docs), "app": app})
        if not relaunch(app, why):
            reports = keep.crash_reports() if keep else []
            return ("The window could not be started again from here" + (f" (crash report: {reports[0]})" if reports else "") +
                    ". The hidden FreeCAD takes the next calls: app_recover lists the saved copies of " + (", ".join(d.get("label", "?") for d in docs) or "the documents") + ".")
        self.f = None
        t0 = time.time()
        while time.time() - t0 < 120 and not self._open():
            time.sleep(1)
        if self.f is None:
            reports = keep.crash_reports() if keep else []
            return ("FreeCAD was started again in the background but its link did not come up within 2 minutes" +
                    (f" (newest crash report: {reports[0]})" if reports else "") + ". The hidden FreeCAD takes the next calls: app_recover lists the saved copies.")
        settled = self.settle_dialog(hb.get("pid"), t0)
        pinned = window_watch.pinned_of(hb) if window_watch is not None else None
        reopen, rec_docs, old_copies = restart_split(docs)
        if reopen:
            newer = newer_copies(self.ask("app_recover", {"action": "list"}, timeout=30), hb.get("t"))
            rec_docs += [dict(d, modified=False) for d in reopen if d.get("name") in newer or d.get("label") in newer]
            reopen = [d for d in reopen if not (d.get("name") in newer or d.get("label") in newer)]
        reopened = []
        for d in reopen:
            if self.ask("doc_open", {"path": d["file"]}, timeout=60) is not None:
                reopened.append(d.get("label") or d.get("name"))
            else:
                rec_docs.append(dict(d, modified=False))
        if keep is not None and (reopened or old_copies):
            keep.log_watchdog({"event": "reopen", "reopened": reopened, "recover": once(d.get("label") for d in rec_docs),
                               "notAgain": once(d.get("label") for d in old_copies)})
        got = self.ask("app_recover", {"action": "auto", "documents": rec_docs, "since": t_crash}) if rec_docs else {"recovered": []}
        if not got:
            return "FreeCAD is back (started in the background); recovering its documents did not answer — app_recover lists the saved copies."
        parts = []
        if settled:
            parts.append(f"FreeCAD's Document Recovery stayed up after the link's press: answered Cancel again ({settled} time{'s' if settled > 1 else ''})")
        reopened = once(reopened + reopened_by_recover(got))
        if reopened:
            parts.append("opened again from their own files (saved, unchanged): " + ", ".join(reopened))
        for r in got.get("recovered") or []:
            parts.append(f"{r.get('label')} recovered from {r.get('source')} ({r.get('time')}, {r.get('lost')})")
        for r in got.get("failed") or []:
            parts.append(f"{r.get('label')}: no copy opened ({r.get('why')})")
        if old_copies:
            parts.append("not recovered again (earlier recovered copies nobody changed): " + ", ".join(d.get("label") or d.get("name") for d in old_copies))
        shut, left, kept = self.close_strays(docs, got.get("recovered") or [], hb.get("pid"), t0)
        if shut:
            parts.append("closed again as they were not open before the restart: " + ", ".join(shut))
        if left:
            parts.append("not open before the restart but left open as they have changes: " + ", ".join(left))
        if pinned and self.watch is not None:
            # The agent's document of before, the session's again (finding 40).
            self.watch.restart = {"old": hb.get("pid"), "t": t0, "pinned": pinned, "why": why, "quit": True, "launched": None}
            got_pin = self._back_from_restart()
            if got_pin:
                parts.append(f"the agent works in {got_pin} again, as before the restart")
        unsaved = [lab for lab, why in kept if why == "unsaved"]
        if unsaved:
            parts.append("kept open, as copies of work never saved to a file: " + ", ".join(unsaved) +
                         " (doc_save each to a file of its own, with the person's OK; closed unsaved, its work is lost)")
        return "FreeCAD is back (started in the background). " + ("; ".join(parts) + ". " if parts else "No documents to recover. ") + \
            "Recovered copies open beside the files as \"(recovered …)\"; the person's own files are untouched — app_recover { accept } saves one over its file, with their OK."

    def close_strays(self, before, recovered, old_pid, t0, wait=8.0):
        """After a restart, old recovered copies the new window opened from
        temporary folders (not open at the restart) closed again; one with
        changes of its own is left, and a copy of a document never saved is
        kept (kept_copies). (closed labels, left labels, kept [(label, why)])"""
        hb, end = None, time.time() + wait
        while time.time() < end:
            hb = heartbeat()
            if hb and hb.get("pid") != old_pid and float(hb.get("t") or 0) > t0:
                break
            hb = None
            time.sleep(0.5)
        if not hb:
            return [], [], []
        shut = []
        now_docs = hb.get("docs") or []
        kept = [(d.get("label") or d["name"], why) for d, why in kept_copies(before, recovered, now_docs)]
        # A copy with changes of its own is said with those doc_close left.
        left = [lab for lab, why in kept if why == "changed"]
        kept = [(lab, why) for lab, why in kept if why != "changed"]
        for d in strays(before, recovered, now_docs):
            got = self.ask("doc_close", {"documents": [d["name"]]}, timeout=20)
            (shut if got is not None else left).append(d.get("label") or d["name"])
        if (shut or left or kept) and keep is not None:
            keep.log_watchdog({"event": "strays", "closed": shut, "left": left, "kept": [{"document": lab, "why": why} for lab, why in kept]})
        return shut, left, kept

    def call(self, line):
        """Send one call to the window and pass its answer on. False when the
        window isn't there: the hidden FreeCAD takes the call.

        A connection the window dropped while restarting on purpose
        (app_restart leaves a mark; the calls it had not started were never
        run) is made again and the call sent once more. Dropped with no mark
        — a crash, a hang the watchdog stopped, or the person quit — the call
        may have run or not, so it is answered, not sent again: with FreeCAD
        started again in the background and its documents recovered."""
        if self.off:
            return False
        ready = self._ready()
        if isinstance(ready, str):
            # Between the quit and the pairing: said, never served headless.
            return self._refuse(line, ready, code="unavailable")
        if not ready:
            if self.seen:
                self.seen = False
                return self._refuse(line, "The FreeCAD window this session was working in has gone (closed or crashed): this call was not run. What was open there is not in the hidden FreeCAD, which has an empty document of its own. Ask the person to open FreeCAD again (its link starts with it), or carry on headless: the next call runs there.")
            return False
        mid, tool, args = _call_info(line)
        hb0 = heartbeat_any() if tool == "app_restart" else None
        with self.lock:
            self.inflight = {"id": mid, "tool": tool, "args": args, "start": time.time()}
            self.hang = None
        try:
            if self._send(line):
                self._note_restart(tool, hb0)
                return True
            c = self.inflight or {}
            if c.get("abandoned"):
                return True
            # The window dropped the connection: a restart under way
            # (app_restart answered, or calls it never started) is waited
            # for and the call sent once more.
            if tool == "app_restart" and self.watch is not None and hb0 and hb0.get("pid") and self.watch.restart is None:
                self.watch.expect(hb0.get("pid"), pinned=window_watch.pinned_of(hb0), why="app_restart")
            restarting = self.watch is not None and self.watch.pending()
            if restarting:
                again = self._ready()
                if isinstance(again, str):
                    return self._refuse(line, again, code="unavailable")
                return bool(again) and self._send(line)
            self.seen = False
            hang = self.hang
            t_crash = time.time()
            if hang and hang.get("heldBy") and hang["heldBy"] != tool:
                head = (f"The FreeCAD window was held by an earlier {hang['heldBy']} for {int(hang['after'])} s ({hang.get('why')}) and was stopped (its pid {hang['pid']}): "
                        f"{tool} waited behind it and was not run.")
            elif hang and hang.get("why"):
                head = f"FreeCAD's window stayed held during {tool} for {int(hang['after'])} s ({hang['why']}) and was stopped (its pid {hang['pid']})."
            elif hang:
                head = f"FreeCAD stopped responding during {tool} after {int(hang['after'])} s and was stopped (its pid {hang['pid']})."
            else:
                head = f"The FreeCAD window went away during {tool} (a crash, or it was quit): it may or may not have run."
            if tool in ("batch", "fast"):
                head += (" A batch keeps what ran as it goes: the newest batches/<date>-<time>.json in the session's folder (session_state's outDir) "
                         "lists each call that finished with its result — read it before running any of them again.")
            tail = self.recover("hang" if hang else "crash", tool, t_crash)
            return self._refuse(line, head + " " + tail, code="failed")
        finally:
            with self.lock:
                self.inflight = None


def run(script, argv):
    """Serve stdin/stdout through a child running script, restarted when it
    dies. Gives up after three deaths in a minute."""
    set_own(argv)
    argv = [a for a in argv if a != "--own"]
    out = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8", errors=WIRE_ERRORS)
    os.dup2(2, 1)
    lock = threading.Lock()
    pending = {}
    lines = {}  # id -> the line, for a quiet restart to send again
    took = {}  # id -> changes: the hidden FreeCAD took it off its input (protocol.TOOK)
    heavy_ids = {}  # hidden: id -> heavy tool, its queue place freed at the answer
    inflight = {}  # hidden: id -> {tool, args, start}
    hangs = {}  # call key -> times it hung
    deaths = []
    state = {"child": None, "ending": False, "hang": None, "recover": None, "restarting": False}
    env = {**os.environ, FLAG: "1"}

    def write_out(line):
        with lock:
            out.write(line + "\n")
            out.flush()

    # Calls past DETACH_AFTER move to the background (agentlink/sup_jobs.py):
    # every reply goes through jobs.write, which keeps a moved call's answer.
    jobs = sup_jobs.Jobs(write_out) if sup_jobs is not None else None
    write = jobs.write if jobs is not None else write_out
    child_lock = threading.Lock()

    def start():
        child = subprocess.Popen([sys.executable, script, *argv], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True, encoding="utf-8", errors=WIRE_ERRORS, bufsize=1)
        state["child"] = child

        def pump():
            for line in child.stdout:
                line = line.rstrip("\n")
                if not line.startswith("{"):
                    if line.strip():
                        sys.stderr.write(f"freecad: {line}\n")
                    continue
                try:
                    got = json.loads(line)
                    mid = got.get("id")
                except (ValueError, AttributeError):
                    got, mid = None, None
                if mid is None and isinstance(got, dict) and got.get("method") == TOOK:
                    # The hidden FreeCAD began this call (E2): not for the client.
                    p = got.get("params") or {}
                    if p.get("id") is not None:
                        took[p["id"]] = bool(p.get("changes", True))
                    continue
                if mid == "__restart":
                    continue
                if mid == "__recover":
                    state["recover"] = line
                    continue
                if isinstance(mid, str) and mid.startswith("__sv-"):
                    state.setdefault("sv", {})[mid] = line
                    continue
                if mid is not None and pending.get(mid) == "initialize" and isinstance(got, dict):
                    # The hidden FreeCAD read where the agent is; with the
                    # window link on, the window is where it works: its read
                    # goes in the words at connect instead.
                    line = window_orient(got, line)
                if mid is not None:
                    pending.pop(mid, None)
                    lines.pop(mid, None)
                    took.pop(mid, None)
                    if mid in heavy_ids:
                        queue_done(heavy_ids.pop(mid))
                    if inflight.pop(mid, None) is not None:
                        state["last_reply"] = time.time()
                write(line)
            code = child.wait()
            if state["ending"]:
                os._exit(0)
            died(code)

        threading.Thread(target=pump, daemon=True).start()
        return child

    def send_child(line):
        with child_lock:  # the reader thread sends job_status beside the main loop
            state["child"].stdin.write(line if line.endswith("\n") else line + "\n")
            state["child"].stdin.flush()

    def ask_child(name, arguments, child, timeout=60):
        """One call of the supervisor's own to the fresh child, its answer
        (the tool's JSON) or None (an error, or no answer in time)."""
        state["svn"] = state.get("svn", 0) + 1
        mid = f"__sv-{state['svn']}"
        send_child(json.dumps({"jsonrpc": "2.0", "id": mid, "method": "tools/call", "params": {"name": name, "arguments": arguments}}))
        t0 = time.time()
        while mid not in state.get("sv", {}) and time.time() - t0 < timeout and child.poll() is None:
            time.sleep(0.1)
        line = state.get("sv", {}).pop(mid, None)
        try:
            r = json.loads(line)["result"]
            return None if r.get("isError") else json.loads(r["content"][0]["text"])
        except (TypeError, ValueError, KeyError, IndexError):
            return None

    def died(code):
        quiet = keep is not None and os.path.exists(keep.runtime(".hidden-restart"))
        if quiet and code == 0:
            # Asked for (a settings rollback with the window closed): started
            # again without a word; nothing was in hand.
            try:
                os.remove(keep.runtime(".hidden-restart"))
            except OSError:
                pass
            start()
            try:
                send_child(restart_initialize(state.get("client")))
                send_child(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
                # It left right after its answer: calls queued behind it that
                # it never took go to the fresh one. A changing call it took
                # but did not answer may have changed something: answered
                # with outcome unknown, never sent twice (E2). A read it
                # took is sent again (it changes nothing).
                for mid in list(pending):
                    if mid not in lines:
                        continue
                    if took.pop(mid, False):
                        c = inflight.pop(mid, None) or {}
                        method = pending.pop(mid, None)
                        lines.pop(mid, None)
                        if mid in heavy_ids:
                            queue_done(heavy_ids.pop(mid))
                        if method == "tools/call":
                            write(_answer(mid, "failed", f"The hidden FreeCAD started again (a settings rollback) while {c.get('tool') or 'this call'} was under way: "
                                          "it may have changed the document before it stopped. It was not sent again. session_state shows the document as it is now.",
                                          outcome="unknown"))
                        continue
                    if mid in inflight:
                        inflight[mid]["start"] = time.time()
                    send_child(lines[mid])
            except OSError:
                pass
            return
        # While this restart is under way the dead child's calls are still
        # in inflight: the watchdog leaves them alone (else it takes them for
        # a second hang, counts it and stops the fresh child mid-recovery).
        state["restarting"] = True
        try:
            _restart(code)
        finally:
            state["restarting"] = False

    def _restart(code):
        hang = state.pop("hang", None)
        state["hang"] = None
        why = f"stopped by signal {-code}" if code < 0 else f"exited with code {code}"
        sys.stderr.write(f"Agent Link: FreeCAD {why}; starting it again\n")
        hidden = (keep._load(keep.path("hidden.json"), {}) if keep else {}) or {}
        dead = state.get("child")
        reopen, docs, _old_copies = restart_split(hidden_docs(hidden, getattr(dead, "pid", None)))
        t_crash = time.time()
        now = time.time()
        deaths[:] = [t for t in deaths if now - t < 60] + [now]
        if len(deaths) > 3:
            for mid, method in list(pending.items()):
                write(_answer(mid, "failed", f"FreeCAD {why} again: it died more than three times in a minute, so Agent Link stopped. Start it again once the cause is found."))
            sys.stderr.write("Agent Link: FreeCAD died more than three times in a minute; giving up\n")
            os._exit(1)
        child = start()
        recovered = None
        reopened = []
        try:
            send_child(restart_initialize(state.get("client")))
            send_child(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
            # Saved, unchanged documents opened again from their own files
            # (unless a copy newer than hidden.json's word holds more).
            if reopen:
                newer = newer_copies(ask_child("app_recover", {"action": "list"}, child, timeout=30), hidden.get("t"))
                for d in reopen:
                    if d.get("name") in newer or d.get("label") in newer or ask_child("doc_open", {"path": d["file"]}, child) is None:
                        docs.append(dict(d, modified=False))
                    else:
                        reopened.append(d.get("label") or d.get("name"))
            if docs:
                state["recover"] = None
                send_child(json.dumps({"jsonrpc": "2.0", "id": "__recover", "method": "tools/call", "params": {"name": "app_recover", "arguments": {"action": "auto", "documents": docs, "since": t_crash}}}))
                t0 = time.time()
                while state["recover"] is None and time.time() - t0 < 120 and child.poll() is None:
                    time.sleep(0.2)
                if state["recover"]:
                    try:
                        recovered = json.loads(json.loads(state["recover"])["result"]["content"][0]["text"])
                    except (ValueError, KeyError, TypeError):
                        recovered = None
        except OSError:
            pass
        tail = ""
        if recovered:
            parts = [f"{r.get('label')} recovered from {r.get('source')} ({r.get('time')}, {r.get('lost')})" for r in recovered.get("recovered") or []]
        else:
            parts = []
        reopened = once(reopened + reopened_by_recover(recovered))
        if reopened:
            parts.append("opened again from their own files (saved, unchanged): " + ", ".join(reopened))
        if recovered or reopened:
            tail = (" " + "; ".join(parts) + ".") if parts else ""
        elif docs:
            tail = " app_recover lists the saved copies of " + ", ".join(d.get("label", "?") for d in docs) + "."
        # Only the calls in hand now are answered and forgotten, and they are
        # forgotten before the answers go out: a call that comes in once an
        # answer is out goes to the fresh child, and clearing everything here
        # used to drop it from inflight, so nothing ever answered or timed it.
        answers = []
        for mid, method in list(pending.items()):
            c = inflight.pop(mid, None) or {}
            pending.pop(mid, None)
            lines.pop(mid, None)
            took.pop(mid, None)
            if mid in heavy_ids:
                queue_done(heavy_ids.pop(mid))
            if hang and mid == hang.get("id"):
                msg = f"FreeCAD stopped responding during {hang['tool']} after {int(hang['after'])} s; it was stopped and started again.{tail or ' Its documents are gone from memory: app_recover lists the saved copies.'}"
            else:
                msg = f"FreeCAD {why} during this call ({c.get('tool') or method}) and has been started again.{tail or ' The document and everything not saved in it is gone: session_state shows the fresh one; doc_open what was saved.'} If the same call does this again, it is the call — try another way."
            answers.append(json.dumps({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps({"error": _kinded({"code": "failed", "message": msg})})}], "isError": True} if method == "tools/call" else {}}))
        for line in answers:
            write(line)

    window = Window(write)
    progress = Progress()

    try:
        from . import memguard

        memwatch = memguard.Supervisor(stop=lambda p: threading.Thread(target=stop_pid, args=(p,), daemon=True).start(),
                                       log=keep.log_watchdog if keep is not None else None)
    except ImportError:
        memwatch = None

    def watchdog():
        """Every 2 s: a call stuck behind a dialog is answered; a FreeCAD
        past its call's deadline with no heartbeat for a minute is stopped
        (never while a save is in progress)."""
        while not state["ending"]:
            time.sleep(keep.PING_EVERY if keep else 2.0)
            try:
                now = time.time()
                q = keep.queue_state()
                active = False
                if q.get("running") and not q.get("held"):
                    idle = keep.person_idle_seconds()
                    hb = heartbeat() or {}
                    window_up = now - float(hb.get("t") or 0) < 10
                    active = idle is not None and idle < PERSON_ACTIVE and window_up
                if q.get("running"):
                    # Read again under the lock, after the slow idle check: a
                    # job that ended meanwhile stays ended (round 8, 00-042).
                    got = queue_hold(active, bool(window.inflight or inflight), now=now)
                    if got and got.get("held"):
                        keep.log_watchdog({"event": "held", "tool": got["held"]})
                    if got and got.get("dropped"):
                        keep.log_watchdog({"event": "stale", "tools": got["dropped"]})
                # The critical-pressure guard (agentlink/memguard.py): real
                # memory read every few seconds while a heavy job runs; at
                # CRITICAL that job alone is stopped, and its answer says why.
                if memwatch is not None:
                    memwatch.turn(_memory_job(q, window, state))
                c = window.inflight
                if c:
                    hb = heartbeat()
                    if hb:
                        window.last_hb = hb
                    dlg = (hb or {}).get("dialog")
                    # A dialog answer gets its own while to run (not the
                    # dialog's age), but not for ever: a window that never
                    # answers it must not hold every call behind it.
                    waited = now - (c["start"] if _answers_dialog(c) else float(dlg.get("since") or now)) if dlg else 0
                    # working: a batch runs its calls inside this dialog's or
                    # menu's loop (a gui_input of it opened it, fault 81b):
                    # not a call held behind it, so never abandoned for that.
                    if dlg and not dlg.get("pressed") and not dlg.get("working") and waited > (ANSWER_WAIT if _answers_dialog(c) else DIALOG_WAIT):
                        window.abandon(f"Blocked by a dialog in the FreeCAD window: \"{dlg.get('title')}\" — {str(dlg.get('text'))[:300]} (buttons: {', '.join(dlg.get('buttons') or []) or 'none'}). "
                                       f"{c['tool']} is waiting behind it. dialog_answer {{ button }} presses one of its buttons: read it and press what the job needs (Cancel backs out); app_force_restart if the window is stuck.")
                        continue
                    pop = (hb or {}).get("popup")
                    held = now - max(c["start"], float(pop.get("since") or now)) if pop else 0
                    # gui_input (or a batch of it) works inside a menu it
                    # opened: its own waits' while first, as for a dialog.
                    if pop and not pop.get("working") and held > (ANSWER_WAIT if _answers_dialog(c) else POPUP_WAIT) and not c.get("abandoned"):
                        # A menu holds the call (its own event loop; the
                        # heartbeat goes on, so no hang is seen): closed
                        # through the window's socket thread, the call
                        # answered busy, and FreeCAD left running.
                        from .gui_input import front_words

                        got = window.unstick()
                        what = front_words(pop)
                        keep.log_watchdog({"event": "popup", "tool": c["tool"], "title": pop.get("title"), "closed": bool(got and got.get("closed"))})
                        tail = (f" Agent Link closed it (gui_unstick), so the window takes calls again; {c['tool']} may not have finished."
                                if got and got.get("closed") else " Closing it did not work: gui_unstick, or app_force_restart if the window stays stuck.")
                        window.abandon(f"Blocked by {what} in the FreeCAD window: {c['tool']} waited behind it for {int(held)} s." + tail, code="busy")
                        continue
                    nh = nested_hang(hb, now, deadline_for((hb or {}).get("busy") or c["tool"], c.get("args") if (hb or {}).get("busy") == c["tool"] else None, c["start"]))
                    if nh and not keep.saving() and window.hang is None:
                        pid = (hb or {}).get("pid")
                        if pid:
                            window.hang = {"pid": pid, "after": nh["after"], "tool": c["tool"], "heldBy": nh["tool"], "why": nh["why"]}
                            keep.log_watchdog({"event": "hang", "where": "window", "nested": True, "tool": nh["tool"], "call": c["tool"], "after": nh["after"], "why": nh["why"], "pid": pid})
                            keep.note_stopped(nh["tool"], nh["after"])
                            stop_pid(int(pid))
                            continue
                    last = float((hb or {}).get("t") or c["start"])
                    limit = deadline_for(c["tool"], c.get("args"), c["start"])
                    pid = (hb or {}).get("pid")
                    idle = progress.idle_for(pid, now) if pid and now - max(last, c["start"]) > keep.GRACE else 0.0
                    if stalled(now, c["start"], max(last, c["start"]), limit, idle) and not keep.saving():
                        if pid:
                            window.hang = {"pid": pid, "after": now - c["start"], "tool": c["tool"]}
                            keep.log_watchdog({"event": "hang", "where": "window", "tool": c["tool"], "after": now - c["start"], "pid": pid})
                            keep.note_stopped(c["tool"], now - c["start"])
                            key = keep.call_key(c["tool"], c.get("args"))
                            hangs[key] = hangs.get(key, 0) + 1
                            stop_pid(int(pid))
                elif not window.off and not state.get("nested_restart"):
                    # No call in hand here (the stuck one was answered by its
                    # guard, or the client gave up on it): a window held by a
                    # nested loop is started again all the same, its
                    # documents recovered, before the next call waits on it.
                    hb = heartbeat()
                    nh = nested_hang(hb, now, deadline_for(hb.get("busy"), None, float(hb.get("busySince") or now))) if hb else None
                    if nh and not keep.saving():
                        state["nested_restart"] = True
                        keep.log_watchdog({"event": "hang", "where": "window", "nested": True, "tool": nh["tool"], "after": nh["after"], "why": nh["why"], "pid": hb.get("pid")})
                        keep.note_stopped(nh["tool"], nh["after"])

                        def _restart_held():
                            try:
                                window.force_restart()
                            finally:
                                state["nested_restart"] = False

                        threading.Thread(target=_restart_held, daemon=True).start()
                # The hidden FreeCAD runs one call at a time: the oldest is the
                # one in hand, started when the one before it answered.
                first = min(inflight.items(), key=lambda kv: kv[1]["start"]) if inflight else None
                for mid, h in [first] if first else []:
                    began = max(h["start"], state.get("last_reply") or 0)
                    limit = deadline_for(h["tool"], h.get("args"), began)
                    # The hidden FreeCAD writes no heartbeat: its CPU work
                    # (and its children's) alone says whether it is hung.
                    cpid = getattr(state.get("child"), "pid", None)
                    idle = progress.idle_for(cpid, now) if cpid and now - began > limit else 0.0
                    if (stalled(now, began, began, limit, idle) and not keep.saving() and state["hang"] is None
                            and not state.get("restarting")):
                        child = state["child"]
                        state["hang"] = {"id": mid, "tool": h["tool"], "after": now - began}
                        keep.log_watchdog({"event": "hang", "where": "hidden", "tool": h["tool"], "after": now - began, "pid": child.pid})
                        keep.note_stopped(h["tool"], now - began)
                        key = keep.call_key(h["tool"], h.get("args"))
                        hangs[key] = hangs.get(key, 0) + 1
                        threading.Thread(target=stop_pid, args=(child.pid,), daemon=True).start()
            except Exception as e:
                sys.stderr.write(f"Agent Link watchdog: {e}\n")

    start()
    if keep is not None:
        threading.Thread(target=watchdog, daemon=True).start()
    def ticker():
        """Every second: calls past their time answered (sup_jobs.tick)."""
        while not state["ending"]:
            time.sleep(1.0)
            try:
                jobs.tick(words=lambda c: f"{c['tool']}: FreeCAD did not answer within {int(c['after'])} s (a call holds its Python). Nothing was changed. Call it again in a moment.")
            except Exception as e:  # noqa: BLE001
                sys.stderr.write(f"Agent Link jobs: {e}\n")

    if jobs is not None:
        threading.Thread(target=ticker, name="agentlink-jobs", daemon=True).start()

    def window_orient(got, line):
        """The initialize answer with the window's orientation in place of
        the hidden FreeCAD's, when the window link is on. The line as it
        was when there is nothing to replace."""
        try:
            text = got["result"]["instructions"]
        except (KeyError, TypeError):
            return line
        if not isinstance(text, str) or ORIENT_HEAD not in text or not window_up():
            return line
        base = text.split(ORIENT_HEAD, 1)[0]
        o = window.side_call("session_state", {"orient": True}, timeout=3.0)
        if isinstance(o, dict) and o.get("where"):
            words = ORIENT_HEAD + json.dumps(o, ensure_ascii=False, separators=(",", ":"))
        else:
            words = "\n\nWhere you are: the FreeCAD window did not answer in time at connect; call session_state."
        got["result"]["instructions"] = base + words
        return json.dumps(got)

    def window_up():
        hb = heartbeat() or {}
        return not window.off and bool(hb.get("pairing")) and time.time() - float(hb.get("t") or 0) < 10

    def job_status_now(msg):
        """job_status, answered here at once (finding 41): a call-N job
        from this table; a job of FreeCAD's own (job-…) asked of the window
        on a connection of its own, or sent to the hidden FreeCAD beside
        the call in hand, with a time limit. True when taken here."""
        mid = msg.get("id")
        args = ((msg.get("params") or {}).get("arguments") or {})
        jid = args.get("job")
        if jid and jobs.mine(jid) or not jid:
            def answer():
                body, err = jobs.status(args)
                if not jid and window_up():
                    got = window.side_call("job_status", {}, timeout=3.0)
                    if isinstance(got, dict) and got.get("jobs"):
                        body["jobs"] = (got.get("jobs") or []) + body.get("jobs", [])
                    if isinstance(got, dict) and got.get("late"):
                        body["late"] = got["late"]  # the window's late answers (E6)
                if not body.get("jobs") and not body.get("late") and not jid and not err:
                    body["note"] = "No jobs. A call with no answer after about 60 s moves to the background as a job; job_start starts one."
                write_out(_answer_body(mid, body) if err else _result(mid, body))
            threading.Thread(target=answer, daemon=True).start()
            return True
        try:
            w = float(args.get("wait") or 0)
        except (TypeError, ValueError):
            w = 0.0
        limit = min(max(w, 0.0), 30.0) + 10.0
        if window_up():
            def ask():
                got = window.side_call("job_status", args, timeout=limit)
                if got is None:
                    write_out(_answer(mid, "busy", f"job_status: the FreeCAD window did not answer within {int(limit)} s (its job holds FreeCAD's Python). Nothing was changed. Call job_status again in a moment."))
                else:
                    write_out(_result(mid, got))
            threading.Thread(target=ask, daemon=True).start()
            return True
        # The hidden FreeCAD answers job_status on a thread of its own
        # (protocol.serve_lines); the reply is dropped if it comes too late.
        jobs.came(mid, "job_status", after=limit, mode="drop")
        try:
            send_child(json.dumps(msg))
        except OSError:
            jobs.forget(mid)
            write_out(_answer(mid, "unavailable", "job_status: the hidden FreeCAD is starting again; its jobs are gone."))
        return True

    def urgent(line):
        """app_force_restart, gui_unstick (alone or as a batch of nothing
        else) and job_status: answered at once, on threads of their own,
        even while a call the window holds is in hand — the reader takes
        them off stdin before they queue behind it."""
        try:
            msg = json.loads(line)
        except ValueError:
            return False
        if not isinstance(msg, dict):
            return False
        if jobs is not None and msg.get("method") == "tools/call" and (msg.get("params") or {}).get("name") == "job_status":
            return job_status_now(msg)
        if msg and msg.get("method") == "tools/call" and _is_app_open(line):
            oid = msg.get("id")
            pending.pop(oid, None)
            batched = (msg.get("params") or {}).get("name") == "batch"

            def _open_it(oid=oid, batched=batched):
                try:
                    got = window.open_window()
                    write(_result(oid, {"results": [{"tool": "app_open", "ok": True, "result": got}], "ran": 1} if batched else got))
                except Exception as e:  # noqa: BLE001
                    write(_answer(oid, "failed", f"app_open failed: {e}"))

            threading.Thread(target=_open_it, daemon=True).start()
            return True
        if msg and msg.get("method") == "tools/call" and _is_force_restart(line):
            # Answered here, never inside FreeCAD: the window may be the thing stuck.
            fid = msg.get("id")
            pending.pop(fid, None)

            def _force(fid=fid):
                try:
                    words = window.force_restart()
                    write(_result(fid, {"restarted": True, "note": words}))
                except Exception as e:  # noqa: BLE001
                    write(_answer(fid, "failed", f"Force restart failed: {e}"))

            threading.Thread(target=_force, daemon=True).start()
            return True
        un = _unstick_call(line) if msg and msg.get("method") == "tools/call" and not window.off else None
        if un is not None:
            uid = msg.get("id")
            pending.pop(uid, None)

            def _unstick(uid=uid, how=un[0], all_=un[1]):
                try:
                    got = window.unstick(all_=all_)
                except Exception as e:  # noqa: BLE001
                    got, why = None, str(e)
                else:
                    why = None
                if got is None:
                    write(_answer(uid, "unavailable", "gui_unstick: the FreeCAD window's link did not answer" + (f" ({why})" if why else "") +
                                  " (no window open, or something other than a menu or dialog holds it): app_force_restart."))
                elif how == "batch":
                    write(_result(uid, {"results": [{"tool": "gui_unstick", "ok": True, "result": got}], "ran": 1}))
                else:
                    write(_result(uid, got))

            threading.Thread(target=_unstick, daemon=True).start()
            return True
        return False

    lines_in = queue.Queue()

    def came(line):
        """A call is timed from when it came in; job_start { job,
        arguments } becomes the call it starts (sup_jobs.job_start_inner):
        it runs as any call does, where calls run, and its answer moves to
        the background at once (wait: false) or after DETACH_AFTER. The
        line to queue."""
        if jobs is None:
            return line
        try:
            msg = json.loads(line)
        except ValueError:
            return line
        if not isinstance(msg, dict) or msg.get("method") != "tools/call" or msg.get("id") is None:
            return line
        p = msg.get("params") or {}
        after = None
        if p.get("name") == "job_start":
            inner = sup_jobs.job_start_inner(p.get("arguments"))
            if inner is not None:
                tool, iargs, after = inner
                msg["params"] = {"name": tool, "arguments": iargs}
                line = json.dumps(msg)
        jobs.came(msg["id"], (msg.get("params") or {}).get("name"), after=after)
        if after == 0:
            jobs.tick()
        return line

    def reader():
        for line in sys.stdin:
            try:
                if urgent(line):
                    continue
                line = came(line)
            except Exception as e:  # noqa: BLE001
                sys.stderr.write(f"Agent Link: {e}\n")
            lines_in.put(line)
        lines_in.put(None)

    threading.Thread(target=reader, daemon=True).start()
    while True:
        line = lines_in.get()
        if line is None:
            break
        msg = None
        try:
            msg = json.loads(line)
            if msg.get("id") is not None and msg.get("method"):
                pending[msg["id"]] = msg["method"]
        except ValueError:
            pass
        if isinstance(msg, dict) and msg.get("method") == "initialize":
            # The client's name: for a restarted FreeCAD and for the window.
            info = (msg.get("params") or {}).get("clientInfo")
            if isinstance(info, dict):
                state["client"] = info
                window.note_client(info)
        if msg and msg.get("method") == "tools/call" and keep is not None:
            mid, tool, args = _call_info(line)
            if hangs.get(keep.call_key(tool, args), 0) >= 2:
                pending.pop(mid, None)
                write(_answer(mid, "invalid_state", f"{tool} with these arguments hung FreeCAD twice this session: refused for the rest of it. Try another way (other sizes, a rough pass, fewer objects)."))
                continue
        heavy_tool = None
        if msg and msg.get("method") == "tools/call":
            mid, tool, args = _call_info(line)
            held = queue_admit(tool)
            if held:
                pending.pop(mid, None)
                write(_answer(mid, "invalid_state", held))
                continue
            heavy_tool = tool if keep is not None and keep.is_heavy(tool) else None
        # Window first: a tool call goes to the FreeCAD window when its link
        # is on (Start link), so the person watches it land; else the hidden one.
        if msg and msg.get("method") == "tools/call" and window.call(line):
            pending.pop(msg.get("id"), None)
            if heavy_tool:
                queue_done(heavy_tool)
            continue
        if msg and msg.get("method") == "tools/call":
            mid, tool, args = _call_info(line)
            inflight[mid] = {"tool": tool, "args": args, "start": time.time()}
            lines[mid] = line
            if heavy_tool:
                heavy_ids[mid] = heavy_tool
        try:
            send_child(line)
        except OSError:
            # Between a death and the restart: the call is answered by died().
            pass
    state["ending"] = True
    try:
        state["child"].stdin.close()
    except OSError:
        pass
    state["child"].wait()
    return 0
