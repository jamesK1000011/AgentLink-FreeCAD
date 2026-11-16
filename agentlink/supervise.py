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
    from . import restart_mark
except ImportError:  # an update without it: no waiting for a restarting window
    restart_mark = None
try:
    from . import keep
except ImportError:
    keep = None

FLAG = "AGENTLINK_SUPERVISED"
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
            return f"{tool} waited {int(waited)} s and did not start: {why}. Try again in a while, or a rough pass (smaller)."
        time.sleep(min(15.0, max(1.0, QUEUE_WAIT - waited)))
    q = keep.queue_state()
    q["running"] = [{"tool": tool, "start": time.time()}]
    keep.save_queue(q)
    return None


def queue_done(tool):
    if keep is None or not keep.is_heavy(tool):
        return
    q = keep.queue_state()
    q["running"] = [r for r in q.get("running") or [] if r.get("tool") != tool]
    keep.save_queue(q)
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


def _answer(mid, code, message):
    text = json.dumps({"error": {"code": code, "message": message}})
    return json.dumps({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}], "isError": True}})


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


def _unstick_call(line):
    """gui_unstick alone or as a batch of nothing else: ("alone" | "batch",
    all), else None. Answered here on a connection of its own, never behind
    the call a menu or dialog holds."""
    _mid, tool, args = _call_info(line)
    if tool == "gui_unstick":
        return ("alone", bool((args or {}).get("all")))
    calls = (args or {}).get("calls") if tool == "batch" else None
    if calls and all(isinstance(c, dict) and c.get("tool") == "gui_unstick" for c in calls):
        return ("batch", any(bool((c.get("arguments") or {}).get("all")) for c in calls if isinstance(c.get("arguments"), dict)))
    return None


def _call_info(line):
    try:
        m = json.loads(line)
    except ValueError:
        return None, None, None
    p = m.get("params") or {}
    return m.get("id"), p.get("name"), p.get("arguments") or {}


def deadline_for(tool, args=None, started=None):
    """Seconds the call in hand may run before a FreeCAD with no heartbeat is
    stopped. A call that marked itself heavy while it runs (a big Part
    boolean: keep.mark_heavy_call) gets its estimate times three."""
    if keep is None:
        return NO_ESTIMATE
    marked = keep.heavy_call_limit(started, time.time()) if started is not None else None
    if os.environ.get("AGENTLINK_DEADLINE"):
        base = float(os.environ["AGENTLINK_DEADLINE"])
        return max(base, marked) if marked else base
    limit = _deadline(tool)
    own = keep.call_deadline(tool, args) if keep.is_heavy(tool) else None
    limit = max(limit, own) if own else limit
    return max(limit, marked) if marked else limit


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
    keep_, left = [], []
    for d in docs or []:
        if isinstance(d, dict) and RECOVERED_LABEL.search(str(d.get("label") or "")) and not d.get("modified"):
            left.append(d)
        else:
            keep_.append(d)
    return keep_, left


def strays(before, recovered, now_docs):
    """Documents open in the FreeCAD just started that were not open when it
    stopped: copies opened again from temporary folders (old recovered
    copies). Not the copies just recovered, and not a file that was open."""
    files = {os.path.abspath(d["file"]) for d in before or [] if isinstance(d, dict) and d.get("file")}
    fresh = {r.get("document") for r in recovered or [] if isinstance(r, dict) and r.get("document")}
    fresh |= {r.get("as") for r in recovered or [] if isinstance(r, dict) and r.get("as")}
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
        out.append(d)
    return out


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


def heartbeat():
    if keep is None:
        return None
    hb = keep._load(keep.path("heartbeat.json"), None)
    return hb if isinstance(hb, dict) else None


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
    if c.get("tool") in ("dialog_answer", "gui_input", "gui_unstick"):
        return True
    calls = (c.get("args") or {}).get("calls") if c.get("tool") == "batch" else None
    return bool(calls) and all(isinstance(x, dict) and x.get("tool") in ("dialog_answer", "gui_input", "gui_unstick") for x in calls)


class Window:
    """The FreeCAD window's link (the workbench's Start link), when it is on.
    Tried afresh for each call, so turning the link on or off takes effect
    at the next call; off (or AGENTLINK_WINDOW=0), calls stay hidden."""

    def __init__(self, write):
        self.write = write
        self.f = None
        self.sock = None
        self.off = os.environ.get("AGENTLINK_WINDOW", "1") == "0"
        self.seen = False  # the window has answered this session
        self.inflight = None  # {id, tool, args, start}
        self.answered = set()  # ids answered early (a dialog, a hang)
        self.hang = None  # set by the watchdog before it stops the window
        self.last_hb = None
        self.lock = threading.Lock()

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
        f = s.makefile("rw", encoding="utf-8", newline="\n")
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
        return True

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
        """Connected to the window, waiting for it while it restarts
        (app_restart, agentlink_update leave a mark) rather than let the
        hidden FreeCAD answer for the document on screen."""
        return self._open() or bool(restart_mark and restart_mark.wait_until(self._open))

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
        tmp = Window(lambda line: None)
        tmp.off = False
        if not tmp._open():
            return None
        line = json.dumps({"jsonrpc": "2.0", "id": f"__unstick{time.time()}", "method": "tools/call", "params": {"name": "gui_unstick", "arguments": {"all": True} if all_ else {}}})
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
            keep.log_watchdog({"event": why, "tool": tool, "docs": [d.get("label") for d in docs], "app": app})
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
        docs, old_copies = recoverable(docs)
        got = self.ask("app_recover", {"action": "auto", "documents": docs, "since": t_crash}) if docs else {"recovered": []}
        if not got:
            return "FreeCAD is back (started in the background); recovering its documents did not answer — app_recover lists the saved copies."
        parts = []
        for r in got.get("recovered") or []:
            parts.append(f"{r.get('label')} recovered from {r.get('source')} ({r.get('time')}, {r.get('lost')})")
        for r in got.get("failed") or []:
            parts.append(f"{r.get('label')}: no copy opened ({r.get('why')})")
        if old_copies:
            parts.append("not recovered again (earlier recovered copies nobody changed): " + ", ".join(d.get("label") or d.get("name") for d in old_copies))
        shut, left = self.close_strays(docs, got.get("recovered") or [], hb.get("pid"), t0)
        if shut:
            parts.append("closed again as they were not open before the restart: " + ", ".join(shut))
        if left:
            parts.append("not open before the restart but left open as they have changes: " + ", ".join(left))
        return "FreeCAD is back (started in the background). " + ("; ".join(parts) + ". " if parts else "No documents to recover. ") + \
            "Recovered copies open beside the files as \"(recovered …)\"; the person's own files are untouched — app_recover { accept } saves one over its file, with their OK."

    def close_strays(self, before, recovered, old_pid, t0, wait=8.0):
        """After a restart, old recovered copies the new window opened from
        temporary folders (not open at the restart) closed again; one with
        changes of its own is left. (closed labels, left labels)"""
        hb, end = None, time.time() + wait
        while time.time() < end:
            hb = heartbeat()
            if hb and hb.get("pid") != old_pid and float(hb.get("t") or 0) > t0:
                break
            hb = None
            time.sleep(0.5)
        if not hb:
            return [], []
        shut, left = [], []
        for d in strays(before, recovered, hb.get("docs") or []):
            got = self.ask("doc_close", {"documents": [d["name"]]}, timeout=20)
            (shut if got is not None else left).append(d.get("label") or d["name"])
        if (shut or left) and keep is not None:
            keep.log_watchdog({"event": "strays", "closed": shut, "left": left})
        return shut, left

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
        if not self._ready():
            if self.seen:
                self.seen = False
                return self._refuse(line, "The FreeCAD window this session was working in has gone (closed or crashed): this call was not run. What was open there is not in the hidden FreeCAD, which has an empty document of its own. Ask the person to open FreeCAD again (its link starts with it), or carry on headless: the next call runs there.")
            return False
        mid, tool, args = _call_info(line)
        with self.lock:
            self.inflight = {"id": mid, "tool": tool, "args": args, "start": time.time()}
            self.hang = None
        try:
            if self._send(line):
                return True
            c = self.inflight or {}
            if c.get("abandoned"):
                return True
            restarting = restart_mark is not None and restart_mark.read() is not None
            if restarting:
                return self._ready() and self._send(line)
            self.seen = False
            hang = self.hang
            t_crash = time.time()
            if hang:
                head = f"FreeCAD stopped responding during {tool} after {int(hang['after'])} s and was stopped (its pid {hang['pid']})."
            else:
                head = f"The FreeCAD window went away during {tool} (a crash, or it was quit): it may or may not have run."
            tail = self.recover("hang" if hang else "crash", tool, t_crash)
            return self._refuse(line, head + " " + tail, code="failed")
        finally:
            with self.lock:
                self.inflight = None


def run(script, argv):
    """Serve stdin/stdout through a child running script, restarted when it
    dies. Gives up after three deaths in a minute."""
    out = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    os.dup2(2, 1)
    lock = threading.Lock()
    pending = {}
    lines = {}  # id -> the line, for a quiet restart to send again
    heavy_ids = {}  # hidden: id -> heavy tool, its queue place freed at the answer
    inflight = {}  # hidden: id -> {tool, args, start}
    hangs = {}  # call key -> times it hung
    deaths = []
    state = {"child": None, "ending": False, "hang": None, "recover": None, "restarting": False}
    env = {**os.environ, FLAG: "1"}

    def write(line):
        with lock:
            out.write(line + "\n")
            out.flush()

    def start():
        child = subprocess.Popen([sys.executable, script, *argv], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True, encoding="utf-8", bufsize=1)
        state["child"] = child

        def pump():
            for line in child.stdout:
                line = line.rstrip("\n")
                if not line.startswith("{"):
                    if line.strip():
                        sys.stderr.write(f"freecad: {line}\n")
                    continue
                try:
                    mid = json.loads(line).get("id")
                except ValueError:
                    mid = None
                if mid == "__restart":
                    continue
                if mid == "__recover":
                    state["recover"] = line
                    continue
                if mid is not None:
                    pending.pop(mid, None)
                    lines.pop(mid, None)
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
        state["child"].stdin.write(line if line.endswith("\n") else line + "\n")
        state["child"].stdin.flush()

    def died(code):
        quiet = keep is not None and os.path.exists(keep.path(".hidden-restart"))
        if quiet and code == 0:
            # Asked for (a settings rollback with the window closed): started
            # again without a word; nothing was in hand.
            try:
                os.remove(keep.path(".hidden-restart"))
            except OSError:
                pass
            start()
            try:
                send_child(json.dumps({"jsonrpc": "2.0", "id": "__restart", "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "agentlink-supervisor", "version": "1"}}}))
                send_child(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
                # It left right after its answer: calls queued behind it never
                # ran, so they go to the fresh one.
                for mid in list(pending):
                    if mid in lines:
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
        docs, _old_copies = recoverable(hidden_docs(hidden, getattr(dead, "pid", None)))
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
        try:
            send_child(json.dumps({"jsonrpc": "2.0", "id": "__restart", "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "agentlink-supervisor", "version": "1"}}}))
            send_child(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
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
            if mid in heavy_ids:
                queue_done(heavy_ids.pop(mid))
            if hang and mid == hang.get("id"):
                msg = f"FreeCAD stopped responding during {hang['tool']} after {int(hang['after'])} s; it was stopped and started again.{tail or ' Its documents are gone from memory: app_recover lists the saved copies.'}"
            else:
                msg = f"FreeCAD {why} during this call ({c.get('tool') or method}) and has been started again.{tail or ' The document and everything not saved in it is gone: session_state shows the fresh one; doc_open what was saved.'} If the same call does this again, it is the call — try another way."
            answers.append(json.dumps({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps({"error": {"code": "failed", "message": msg}})}], "isError": True} if method == "tools/call" else {}}))
        for line in answers:
            write(line)

    window = Window(write)

    def watchdog():
        """Every 2 s: a call stuck behind a dialog is answered; a FreeCAD
        past its call's deadline with no heartbeat for a minute is stopped
        (never while a save is in progress)."""
        while not state["ending"]:
            time.sleep(keep.PING_EVERY if keep else 2.0)
            try:
                now = time.time()
                q = keep.queue_state()
                if q.get("running") and not q.get("held"):
                    idle = keep.person_idle_seconds()
                    hb = heartbeat() or {}
                    window_up = now - float(hb.get("t") or 0) < 10
                    if idle is not None and idle < PERSON_ACTIVE and window_up:
                        r = q["running"][0]
                        q["held"] = True
                        q["notice"] = f"A heavy job is running ({r.get('tool')}, since {time.strftime('%H:%M', time.localtime(r.get('start') or now))}); new heavy jobs wait for your go"
                        keep.save_queue(q)
                        keep.log_watchdog({"event": "held", "tool": r.get("tool")})
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
                    if dlg and not dlg.get("pressed") and waited > (ANSWER_WAIT if _answers_dialog(c) else DIALOG_WAIT):
                        window.abandon(f"Blocked by a dialog in the FreeCAD window: \"{dlg.get('title')}\" — {str(dlg.get('text'))[:300]} (buttons: {', '.join(dlg.get('buttons') or []) or 'none'}). "
                                       f"{c['tool']} is waiting behind it. dialog_answer {{ button }} presses one of its buttons: read it and press what the job needs (Cancel backs out); app_force_restart if the window is stuck.")
                        continue
                    pop = (hb or {}).get("popup")
                    held = now - max(c["start"], float(pop.get("since") or now)) if pop else 0
                    # gui_input (or a batch of it) works inside a menu it
                    # opened: its own waits' while first, as for a dialog.
                    if pop and held > (ANSWER_WAIT if _answers_dialog(c) else POPUP_WAIT) and not c.get("abandoned"):
                        # A menu holds the call (its own event loop; the
                        # heartbeat goes on, so no hang is seen): closed
                        # through the window's socket thread, the call
                        # answered busy, and FreeCAD left running.
                        from .gui_input import front_words

                        got = window.unstick()
                        what = front_words(pop)
                        keep.log_watchdog({"event": "popup", "tool": c["tool"], "title": pop.get("title"), "closed": bool(got and got.get("closed"))})
                        tail = (f" Agent Link closed it (gui_unstick), so the window takes calls again; {c['tool']} may not have finished: check, then call it again."
                                if got and got.get("closed") else " Closing it did not work: gui_unstick, or app_force_restart if the window stays stuck.")
                        window.abandon(f"Blocked by {what} in the FreeCAD window: {c['tool']} waited behind it for {int(held)} s." + tail, code="busy")
                        continue
                    last = float((hb or {}).get("t") or c["start"])
                    limit = deadline_for(c["tool"], c.get("args"), c["start"])
                    if keep.hung(now, c["start"], max(last, c["start"]), limit) and not keep.saving():
                        pid = (hb or {}).get("pid")
                        if pid:
                            window.hang = {"pid": pid, "after": now - c["start"], "tool": c["tool"]}
                            keep.log_watchdog({"event": "hang", "where": "window", "tool": c["tool"], "after": now - c["start"], "pid": pid})
                            keep.note_stopped(c["tool"], now - c["start"])
                            key = keep.call_key(c["tool"], c.get("args"))
                            hangs[key] = hangs.get(key, 0) + 1
                            stop_pid(int(pid))
                # The hidden FreeCAD runs one call at a time: the oldest is the
                # one in hand, started when the one before it answered.
                first = min(inflight.items(), key=lambda kv: kv[1]["start"]) if inflight else None
                for mid, h in [first] if first else []:
                    began = max(h["start"], state.get("last_reply") or 0)
                    limit = deadline_for(h["tool"], h.get("args"), began)
                    if (keep.hung(now, began, began + limit, limit) and not keep.saving() and state["hang"] is None
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
    def urgent(line):
        """app_force_restart and gui_unstick (alone or as a batch of
        nothing else): answered at once, on threads of their own, even while
        a call the window holds is in hand — the reader takes them off stdin
        before they queue behind it."""
        try:
            msg = json.loads(line)
        except ValueError:
            return False
        if not isinstance(msg, dict):
            return False
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

    def reader():
        for line in sys.stdin:
            try:
                if urgent(line):
                    continue
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
