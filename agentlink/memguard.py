# SPDX-License-Identifier: LGPL-2.1-or-later
"""The critical-pressure guard: real memory watched while a heavy job runs.

The owner's decision (18 Nov 2026): no estimate refuses a job before it starts
(the old "would need about N GB" ceiling is gone). Instead the supervisor's
watchdog reads macOS's own memory pressure every few seconds while a heavy
job runs (sysctl kern.memorystatus_vm_pressure_level: 1 normal, 2 warn,
4 critical; read-only and cheap). At CRITICAL, two samples in a row:

  1. The job's own child processes (a solver, a mesher, a slicer that the
     job started) are stopped. FreeCAD and its documents stay.
  2. A mark is written (~/AgentLink/memory-stop.json). In FreeCAD, a small
     watcher reads it and stops a job that runs in FreeCAD's own Python
     (an exception raised in the job's thread, at its next Python line).
     A changing call's transaction is then aborted, so the document is as
     it was before the job.
  3. The call's answer says why (code "stopped"), and names the checkpoint
     made before the job (an add-on keeps checkpoints), or a saved copy.

Only that job stops. A job that holds Python inside one long C++ call is
stopped when that call returns; macOS itself acts before that if it must.

The guard is a user setting: Mod/AgentLink CriticalPressureGuard (bool, on
by default) or AGENTLINK_MEMORY_GUARD=off.
"""
import os
import subprocess
import sys
import threading
import time

PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
SETTING = "CriticalPressureGuard"
ENV = "AGENTLINK_MEMORY_GUARD"
EVERY = 3.0          # s between samples while a heavy job runs
NEED = 2             # critical samples in a row before a stop
MARK = "memory-stop.json"
MARK_FOR = 120.0     # s a mark stays good for the job it names


class MemoryStop(BaseException):
    """Raised in a job's thread at critical memory pressure. A
    BaseException, so a tool's own "except Exception" does not swallow it."""


# ---- the setting ----------------------------------------------------------------------------

def on(params=None):
    """The guard is on unless the person turned it off."""
    v = os.environ.get(ENV, "").strip().lower()
    if v in ("off", "0", "false", "no"):
        return False
    if v in ("on", "1", "true", "yes"):
        return True
    if params is not None:
        return bool(params.get("criticalPressureGuard", True))
    try:
        import FreeCAD

        return bool(FreeCAD.ParamGet(PREFS).GetBool(SETTING, True))
    except Exception:  # noqa: BLE001 - no FreeCAD here (the supervisor)
        pass
    try:
        from . import keep

        return bool(keep._load(keep.path("settings.json"), {}).get("criticalPressureGuard", True))
    except Exception:  # noqa: BLE001
        return True


# ---- reading the pressure -------------------------------------------------------------------

def _sysctl():
    try:
        r = subprocess.run(["sysctl", "kern.memorystatus_vm_pressure_level"], capture_output=True, text=True, timeout=3)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def level(read=None, platform=None):
    """normal, warn or critical; None where it cannot be read (not macOS)."""
    if (platform or sys.platform) != "darwin" and read is None:
        return None
    text = (read or _sysctl)()
    if not text:
        return None
    from .keep import memory_pressure_level

    return memory_pressure_level(text)


class Watch:
    """Samples while a job runs: sample(now) answers "critical" once NEED
    critical samples came in a row, else None. read(): the level now."""

    def __init__(self, read=level, every=EVERY, need=NEED, clock=time.time):
        self.read, self.every, self.need, self.clock = read, every, need, clock
        self.last = None
        self.row = 0
        self.seen = None

    def reset(self):
        self.row = 0
        self.last = None

    def sample(self, now=None):
        now = self.clock() if now is None else now
        if self.last is not None and now - self.last < self.every:
            return None
        self.last = now
        try:
            self.seen = self.read()
        except Exception:  # noqa: BLE001
            self.seen = None
        self.row = self.row + 1 if self.seen == "critical" else 0
        return "critical" if self.row >= self.need else None


# ---- the job's own child processes ----------------------------------------------------------

def _etime_secs(text):
    """ps etime: [[dd-]hh:]mm:ss -> seconds."""
    days = 0
    if "-" in text:
        d, text = text.split("-", 1)
        days = int(d)
    parts = [int(x) for x in text.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts[-3:]
    return days * 86400 + h * 3600 + m * 60 + s


def ps_rows():
    """[(pid, ppid, age s, rss KB)], or None when ps fails."""
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,etime=,rss="], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    rows = []
    for line in out.splitlines():
        b = line.split()
        if len(b) < 4:
            continue
        try:
            rows.append((int(b[0]), int(b[1]), _etime_secs(b[2]), int(b[3])))
        except ValueError:
            continue
    return rows


def job_children(fc_pid, job_age, rows):
    """The processes under FreeCAD (fc_pid) that started after the job did
    (job_age: s since it started), biggest memory first. FreeCAD itself and
    what was there before the job are never in it."""
    if not fc_pid or not rows:
        return []
    kids = {}
    info = {}
    for pid, ppid, age, rss in rows:
        kids.setdefault(ppid, []).append(pid)
        info[pid] = (age, rss)
    out, stack, seen = [], list(kids.get(int(fc_pid), ())), set()
    while stack:
        p = stack.pop()
        if p in seen or p == int(fc_pid):
            continue
        seen.add(p)
        age, rss = info.get(p, (None, 0))
        if age is not None and age <= job_age + 2:
            out.append((rss, p))
        stack.extend(kids.get(p, ()))
    return [p for _rss, p in sorted(out, reverse=True)]


# ---- the mark between the supervisor and FreeCAD --------------------------------------------

def _mark_path():
    from . import keep

    return keep.path(MARK)


def write_mark(tool, pid, children, level_now="critical", now=None):
    from . import keep

    m = {"tool": tool, "t": time.time() if now is None else now, "pid": pid, "children": list(children or []),
         "how": "children" if children else "in-process", "level": level_now}
    keep._save(_mark_path(), m)
    return m


def read_mark():
    from . import keep

    m = keep._load(_mark_path(), None)
    return m if isinstance(m, dict) else None


def take_mark(tool, since):
    """The mark for this tool's run (written after it started), taken
    away; None when there is none."""
    m = read_mark()
    if not m or m.get("tool") != tool or float(m.get("t") or 0) < since - 1 or time.time() - float(m.get("t") or 0) > MARK_FOR:
        return None
    try:
        os.remove(_mark_path())
    except OSError:
        pass
    return m


def words(tool, mark, checkpoint=None, copy=None, changes=True):
    how = ("Its own processes were stopped" if (mark or {}).get("how") == "children" else "It was stopped in FreeCAD") + "; FreeCAD and the other documents stay."
    if checkpoint:
        keep_words = f" The checkpoint {checkpoint} from before the job is kept. tool_find {{ query: \"restore checkpoint\" }} finds the tool that goes back to it."
    elif copy:
        keep_words = f" A copy of the document from before the job is kept at {copy}."
    elif changes:
        keep_words = " Its change was undone (the document is as before the job)."
    else:
        keep_words = " It changed nothing."
    return (f"{tool} was stopped: macOS reported critical memory pressure while it ran. {how}{keep_words} "
            "Try a coarser pass (fewer elements, points or faces), or close other apps first. "
            f"The person can turn this guard off (Mod/AgentLink {SETTING}).")


# ---- in FreeCAD: the watcher that stops a job in this Python --------------------------------

_lock = threading.Lock()
_JOBS = {}           # thread id -> (tool, started)
_watcher = []


def _raise_in(tid, exc):
    import ctypes

    return ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), ctypes.py_object(exc) if exc is not None else None)


def started(tool, tid=None, now=None):
    """A heavy job begins on this thread: watched until finished()."""
    tid = threading.get_ident() if tid is None else tid
    with _lock:
        _JOBS[tid] = (tool, time.time() if now is None else now)
    _ensure_watcher()
    return tid


def finished(tid=None):
    """The job on this thread ended: no stop reaches it any more."""
    tid = threading.get_ident() if tid is None else tid
    with _lock:
        got = _JOBS.pop(tid, None)
    try:
        _raise_in(tid, None)  # a stop not yet delivered is taken back
    except Exception:  # noqa: BLE001
        pass
    return got


def check_once(read=read_mark, raise_in=None):
    """One look at the mark: a job here that it names (and that started
    before it) is stopped. The tools stopped."""
    m = read()
    if not m or m.get("how") != "in-process" or time.time() - float(m.get("t") or 0) > MARK_FOR:
        return []
    raise_in = raise_in or _raise_in
    out = []
    with _lock:
        for tid, (tool, t0) in list(_JOBS.items()):
            if tool == m.get("tool") and t0 <= float(m.get("t") or 0) + 1 and not m.get("delivered"):
                raise_in(tid, MemoryStop)
                out.append(tool)
    if out:
        m["delivered"] = True
        try:
            from . import keep

            keep._save(_mark_path(), m)
        except Exception:  # noqa: BLE001
            pass
    return out


def _ensure_watcher():
    if _watcher:
        return

    def loop():
        while True:
            time.sleep(1.0)
            with _lock:
                busy = bool(_JOBS)
            if busy:
                try:
                    check_once()
                except Exception:  # noqa: BLE001
                    pass

    t = threading.Thread(target=loop, name="agentlink-memguard", daemon=True)
    _watcher.append(t)
    t.start()


# ---- in the supervisor: one turn of the watchdog --------------------------------------------

class Supervisor:
    """The supervisor's side: turn(now, job) once per watchdog tick.
    job: {tool, start, pid} of the heavy job in hand (pid: its FreeCAD), or
    None. rows(): ps rows; stop(pid): stops one process. Answers the mark
    when it stopped a job, else None."""

    def __init__(self, watch=None, rows=ps_rows, stop=None, guard=on, log=None):
        self.watch = watch or Watch()
        self.rows, self.stop, self.guard, self.log = rows, stop, guard, log
        self.done = set()

    def turn(self, job, now=None):
        now = time.time() if now is None else now
        if not job or not self.guard():
            self.watch.reset()
            return None
        k = (job.get("tool"), round(float(job.get("start") or 0), 3))
        if k in self.done:
            return None
        if self.watch.sample(now) != "critical":
            return None
        self.done.add(k)
        kids = job_children(job.get("pid"), now - float(job.get("start") or now), self.rows() or [])
        for p in kids:
            if self.stop is not None:
                try:
                    self.stop(p)
                except Exception:  # noqa: BLE001
                    pass
        m = write_mark(job.get("tool"), job.get("pid"), kids, now=now)
        if self.log is not None:
            try:
                self.log({"event": "memory", "level": "critical", "tool": job.get("tool"), "pid": job.get("pid"), "stopped": kids or "in-process"})
            except Exception:  # noqa: BLE001
                pass
        return m
