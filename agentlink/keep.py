# SPDX-License-Identifier: LGPL-2.1-or-later
# What Agent Link keeps on disk so the work survives with no one at the Mac
# (unattended use): the versions before an update, the machine preset, the
# heavy-job queue, the launch mark and the watchdog's log. All of it under
# ~/AgentLink, all of it local. Saved copies of documents (checkpoints,
# auto-saves, recovery), the settings log and approved macros are an
# add-on's, through agentlink/hooks.py; they live under ~/AgentLink too.
#
# No FreeCAD here: the supervisor, the window's link and the hidden FreeCAD
# all read it, and the rules (what to keep, what is due, what to answer) are
# tested without FreeCAD.

import hashlib
import json
import os
import re
import time


def home():
    return os.environ.get("AGENTLINK_HOME") or os.path.expanduser("~/AgentLink")


def path(*parts):
    return os.path.join(home(), *parts)


def runtime(name):
    """A run mark of one hidden FreeCAD and its supervisor (the restart mark,
    the heavy call in hand, the checkpoint before it): in the home, or, for a
    server started with --own (AGENTLINK_OWN_ID), in own/<id>/, so two such
    servers never read each other's marks."""
    own = os.environ.get("AGENTLINK_OWN_ID", "").strip()
    if own and own.isalnum():
        return path("own", own, name)
    return path(name)


def stamp(t=None):
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(t if t is not None else time.time()))


def _load(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(p, value):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=1)
    os.replace(tmp, p)


# ---- D. after a crash: the supervisor names the newest crash report -----------------------

def crash_reports(limit=1, folder=None):
    d = folder or os.path.expanduser("~/Library/Logs/DiagnosticReports")
    try:
        fs = [os.path.join(d, f) for f in os.listdir(d) if f.lower().startswith("freecad")]
    except OSError:
        return []
    return sorted(fs, key=os.path.getmtime, reverse=True)[:limit]


# ---- E. the watchdog ----------------------------------------------------------------------

PING_EVERY = 2.0
GRACE = float(os.environ.get("AGENTLINK_GRACE", "60"))
DEADLINES = {"read": 30.0, "change": float(os.environ.get("AGENTLINK_DEADLINE", "120"))}


def deadline(kind, estimate=None):
    """Seconds a call may take: a read 30, a change 120, a heavy job its
    estimate times three (never under a change's)."""
    if kind == "heavy":
        return max(DEADLINES["change"], 3.0 * float(estimate or 0))
    return DEADLINES.get(kind, DEADLINES["change"])


def hung(now, started, last_ping, limit):
    """Stuck: past its deadline and no ping for a minute. A long solve that
    keeps the event loop alive keeps pinging and is never stuck."""
    return (now - started) > limit and (now - last_ping) > GRACE


def call_key(tool, args):
    return tool + ":" + hashlib.sha256(json.dumps(args or {}, sort_keys=True, default=str).encode()).hexdigest()[:16]


def saving_flag():
    """Written by whoever is saving a copy of a document (an add-on's
    auto-save): the watchdog waits for it rather than call a long save a
    hang."""
    return path(".saving")


def saving(limit=120.0):
    """A save in progress; a stale flag is not."""
    try:
        return time.time() - os.path.getmtime(saving_flag()) < limit
    except OSError:
        return False


def note_stopped(tool, after, keep_n=5):
    """The watchdog stopped FreeCAD during a call of tool after so many
    seconds: kept, so that tool runs as a job (a read) or with a longer
    deadline, asked first (a change) from then on (heavy.Gate,
    jobs.wanted)."""
    try:
        q = queue_state()
        rows = q.setdefault("stopped", {}).setdefault(tool, [])
        rows.append([time.time(), float(after)])
        del rows[:-keep_n]
        save_queue(q)
    except Exception:  # noqa: BLE001 — a read-only home: nothing kept
        pass


def stopped_before(tool, within=30 * 86400.0, q=None):
    """The longest a call of tool ran before the watchdog stopped FreeCAD,
    within the last 30 days, or None."""
    try:
        q = q if q is not None else queue_state()
        rows = (q.get("stopped") or {}).get(tool) or []
        now = time.time()
        got = [float(a) for t, a in rows if now - float(t) < within]
        return max(got) if got else None
    except Exception:  # noqa: BLE001
        return None


def log_watchdog(event):
    p = path("watchdog.log")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), **event}, default=str) + "\n")


# ---- F. dialogs ---------------------------------------------------------------------------

def launch_mark():
    return path("launch.json")


def mark_launch(pid, why):
    _save(launch_mark(), {"pid": pid, "t": time.time(), "why": why})


def launched_by_us(pid=None, limit=600.0):
    m = _load(launch_mark(), None)
    if not isinstance(m, dict):
        return False
    if pid is not None and m.get("pid") not in (pid, None):
        return False
    return time.time() - float(m.get("t") or 0) < limit


# Dialogs anyone may close: information boxes with a plain OK.
HARMLESS = ("ok", "close")


def dialog_answer_for(d, ours, restarting=False, save_rule="agent", agent_docs=()):
    """What the link does about a modal dialog: ("press", button) or
    ("report", why). d = { class, title, text, buttons }."""
    title = (d.get("title") or "").lower()
    text = (d.get("text") or "").lower()
    buttons = [b.lower().replace("&", "") for b in d.get("buttons") or []]
    if "recover" in title or "document recovery" in text or "recover" in " ".join(buttons):
        if ours:
            # Skipped: Agent Link reopens its documents itself (the restart's
            # reopen list, an add-on's recovered copies); the recovery files
            # stay, and a question about removing them is answered No.
            for b in ("skip", "cancel", "no", "close"):
                if b in buttons:
                    return ("press", b)
            # FreeCAD 1.1's Document Recovery has only Start Recovery and
            # Cleanup…: closed as Escape closes it (press backs out with
            # reject when there is no such button).
            return ("press", "Cancel")
        return ("report", "FreeCAD's recovery dialog, in a FreeCAD the person started: it is theirs.")
    if restarting and ("save" in title or "save changes" in text or "unsaved" in text):
        name = re.search(r"['\"“]([^'\"”]+)['\"”]", d.get("text") or "")
        doc = name.group(1) if name else None
        save = save_rule == "all" or (save_rule == "agent" and doc in agent_docs)
        for b in (("save", "yes") if save else ("discard", "don't save", "no")):
            if b in buttons:
                return ("press", b)
    return ("report", "Not one with a set answer: the person decides, in chat.")


def harmless(d):
    buttons = [b.lower().replace("&", "") for b in d.get("buttons") or []]
    return len(buttons) <= 1 and all(b in HARMLESS for b in buttons) and (d.get("class") or "").endswith("MessageBox")


# ---- G. versions --------------------------------------------------------------------------

def versions():
    return _load(path("versions.json"), {"history": []})


def record_versions(before, after=None, outcome=None, keep=2):
    v = versions()
    v.setdefault("history", []).append({"t": time.time(), "before": before, "after": after, "outcome": outcome})
    v["history"] = v["history"][-(keep * 3):]
    _save(path("versions.json"), v)
    return v


# ---- N. the machine and heavy jobs --------------------------------------------------------

# Heavy tools: solves (FEM, assembly), meshing, alignment and deviation,
# slicing, renders and big booleans. They go through the queue, are timed
# for estimates, and get their estimate times three as a deadline.
HEAVY = {
    "fea_native", "fea_buckle", "fea_shell", "fem_mesh", "fea_refine", "fea_solve", "fea_heat", "strength_check",
    "asm_motion", "asm_sweep", "view_render", "cam_sim",
    "meshobj_boolean", "meshobj_offset", "meshobj_decimate", "points_mesh", "part_extract",
    "steps_render", "addon_test",
}
# Heavy tools that take their own "timeout" (seconds), and its default where
# a call may leave it out: the watchdog gives such a call that long and a
# minute (call_deadline), so a long run is not taken for a hang.
TIMEOUT_DEFAULTS = {}


def call_deadline(tool, args):
    """Seconds the watchdog gives a call that says how long it may run, or
    None when it does not."""
    t = (args or {}).get("timeout", TIMEOUT_DEFAULTS.get(tool)) if isinstance(args, dict) else TIMEOUT_DEFAULTS.get(tool)
    if isinstance(t, bool) or not isinstance(t, (int, float)) or t <= 0:
        return None
    return float(t) + 60.0
# Heavy tools of add-ons (their tools.json "heavy", or a family's HEAVY) are
# known only where the families load: the serving child. It writes them
# here, so the supervising parent gives them a heavy job's deadline too.
_ADDON_HEAVY = {"mtime": None, "names": frozenset()}


def declare_heavy(names):
    names = set(names or ())
    if not names or names <= HEAVY:
        return
    HEAVY.update(names)
    try:
        have = set(_load(path("heavy-tools.json"), []))
        if not names <= have:
            _save(path("heavy-tools.json"), sorted(have | names))
    except Exception:  # noqa: BLE001 — a read-only home: this process still knows them
        pass


def is_heavy(tool):
    if tool in HEAVY:
        return True
    p = path("heavy-tools.json")
    try:
        m = os.path.getmtime(p)
    except OSError:
        return False
    if m != _ADDON_HEAVY["mtime"]:
        _ADDON_HEAVY.update(mtime=m, names=frozenset(_load(p, [])))
    return tool in _ADDON_HEAVY["names"]


# Tools heavy only at some sizes: a Part boolean of faceted solids (a scan
# made a solid) holds FreeCAD's GUI thread inside OCC with no heartbeat, and
# an undo or a check of such a document takes long too. They are not queued
# (a small boolean must not wait for the person's go); their size gives an
# estimate, and the call in hand is marked (heavy-call.json) so the watchdog
# gives it that estimate times three rather than stopping FreeCAD at 120 s.
# The estimate: from this tool's past runs here (two or more), else the
# prior below. A boolean's size is the face pairs OCC may intersect (base
# faces x tool faces); the others' size is the document's faces.
SIZED = {
    "part_boolean": {"per_second": 30000.0, "ask": True},
    # A loft's work grows far faster than its faces (spans x points per
    # profile): 91 profiles of 36 points ruled took 9.7 s, of 80 points
    # past 120 s (the watchdog stopped FreeCAD). Its size is (faces /
    # 1000) cubed (heavy.loft_size), timed apart ruled and smooth
    # (sized_key).
    "part_loft": {"per_second": 3.5, "ask": True},
    # Inspection of a free-form body: its tessellation and FreeCAD's
    # Inspection on it grow with the B-spline poles (a lofted solid of 3
    # faces ran past 120 s against a 140k-triangle scan; a 3242-face
    # ruled one took under 1 s), and each measured point against a solid
    # nominal is an OCC distance and a classifier (points x nominal
    # faces). Size: heavy.insp_size. Asked first like a boolean (live, 18
    # Nov: it froze the window >160 s with no word first).
    "insp_run": {"per_second": 50.0, "ask": True},
    # A mesh made a solid: a face per triangle, sewn, and refine (the
    # default) about doubles it (live, 18 Nov: 36k triangles 78 s, 35k
    # with refine past 123 s, the watchdog stopped FreeCAD). Size:
    # triangles, x2 with refine (heavy.from_mesh_size).
    "part_from_mesh": {"per_second": 500.0, "ask": True},
    # An export that tessellates (STL, OBJ, 3MF, glTF ...): OCC meshes
    # each face to the tolerance, slow on a B-spline face of many poles
    # (live, 18 Nov: a smooth 3-face loft to STL at 0.05 held the window
    # past 123 s). Size: heavy.tess_size, the same units as insp_run's.
    # A read: past jobs.SLOW_READ it runs as a job; in a batch it is
    # asked first.
    "export": {"per_second": 50.0, "ask": True},
    "body_check": {"per_second": 100.0, "ask": False},
    "history_undo": {"per_second": 100.0, "ask": False},
    "history_redo": {"per_second": 100.0, "ask": False},
}
# A sized call estimated over this is asked about first (the same call again
# runs it): the window is frozen until OCC finishes.
SIZED_ASK_OVER = 60.0
# A sized call estimated over this is marked for the watchdog.
SIZED_MARK_OVER = 10.0


def boolean_size(base_faces, tool_faces):
    """Face pairs a boolean may intersect: base faces times all tool faces."""
    return max(1, int(base_faces or 0)) * max(1, sum(int(n or 0) for n in tool_faces or ()))


# A boolean's own work for each face of its inputs (building the result,
# merging coplanar faces), in face pairs: a common of a 36k-face solid
# with a 6-face box took 29 s (live, 18 Nov), though few face pairs meet.
BOOLEAN_FACE_WORK = 24


def boolean_work(pairs, faces):
    """A boolean's size from the face pairs whose boxes meet (OCC only
    intersects those) and its faces in all."""
    return max(1, int(pairs or 0)) + BOOLEAN_FACE_WORK * max(0, int(faces or 0))


# Sized tools whose size measure changed: timed under a key of their own,
# so runs logged against the old measure are not read against the new.
SIZED_KEYS = {"part_boolean": "part_boolean boxes", "export": "export tess"}


def sized_key(tool, args):
    """The timing key a sized call is logged and estimated under: a ruled
    loft apart from a smooth one (their times differ)."""
    if tool == "part_loft" and isinstance(args, dict) and args.get("ruled"):
        return "part_loft ruled"
    return SIZED_KEYS.get(tool, tool)


def sized_estimate(q, tool, size, key=None):
    """Seconds a sized tool should take at this size: its past runs here
    (under key, the tool's name by default) when there are two or more,
    else the prior. None for other tools."""
    spec = SIZED.get(tool)
    if spec is None or not size:
        return None
    key = key or tool
    pts = [p for p in (q.get("timings") or {}).get(key, []) if p and p[0] > 0]
    if len(pts) >= 2:
        est = estimate(q, key, size)
        if est is not None:
            return est
    return float(size) / spec["per_second"]


def call_checkpoint_mark():
    return runtime("call-checkpoint.json")


def mark_call_checkpoint(tool, checkpoint, t=None):
    """The checkpoint an add-on took before the call in hand (heavy.py): the
    supervisor names it when that call cannot stop (job_status stop)."""
    _save(call_checkpoint_mark(), {"tool": tool, "checkpoint": str(checkpoint), "pid": os.getpid(), "t": t if t is not None else time.time()})


def clear_call_checkpoint():
    try:
        os.remove(call_checkpoint_mark())
    except OSError:
        pass


def call_checkpoint(since=0.0):
    """The id of the checkpoint taken before the call in hand, when it was
    taken at or after since (less a second), else None."""
    m = _load(call_checkpoint_mark(), None)
    if not isinstance(m, dict) or not m.get("checkpoint"):
        return None
    try:
        if float(m.get("t") or 0) < float(since or 0) - 1.0:
            return None
    except (TypeError, ValueError):
        return None
    return m["checkpoint"]


def heavy_call_mark():
    return runtime("heavy-call.json")


def mark_heavy_call(tool, estimate_s, size, pid=None, t=None):
    """The call in hand is a heavy one: its tool, estimate and start, for the
    supervisor's watchdog (any process may run it: the window or the hidden
    FreeCAD)."""
    _save(heavy_call_mark(), {"tool": tool, "estimate": float(estimate_s), "size": size, "pid": pid if pid is not None else os.getpid(), "t": t if t is not None else time.time()})


def clear_heavy_call():
    try:
        os.remove(heavy_call_mark())
    except OSError:
        pass


def heavy_call_limit(started, now=None):
    """Seconds the watchdog gives the call that started at `started`, when a
    heavy-call mark was written during it (by it or by a call inside its
    batch): the estimate times three, never under a change's deadline. None
    when there is no such mark (an older mark is a call that already ended
    or a FreeCAD that was stopped)."""
    m = _load(heavy_call_mark(), None)
    if not isinstance(m, dict):
        return None
    try:
        t, est = float(m.get("t") or 0), float(m.get("estimate") or 0)
    except (TypeError, ValueError):
        return None
    if started is None or t < float(started) - 1.0:
        return None
    lim = deadline("heavy", est)
    if now is not None and now - t > lim + 600.0:
        return None
    return lim


SYSCTL_KEYS = ("machdep.cpu.brand_string", "hw.perflevel0.physicalcpu", "hw.physicalcpu", "hw.ncpu", "hw.memsize", "hw.model")


def _run(argv, timeout=5):
    import subprocess

    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def read_machine():
    """The preset, read from the machine once (macOS sysctl; elsewhere what
    Python can see) and kept in machine.json."""
    import sys

    got = {}
    if sys.platform == "darwin":
        for k in SYSCTL_KEYS:
            v = _run(["sysctl", "-n", k]).strip()
            if v:
                got[k] = v
    else:
        got["hw.ncpu"] = str(os.cpu_count() or 1)
        got["hw.physicalcpu"] = got["hw.ncpu"]
        try:
            with open("/proc/meminfo") as f:
                kb = int(re.search(r"MemTotal:\s+(\d+)", f.read()).group(1))
            got["hw.memsize"] = str(kb * 1024)
        except (OSError, AttributeError, ValueError):
            pass
        got["hw.model"] = "linux"
    m = machine_from(got)
    m["read"] = time.time()
    save_machine(m)
    return m


def preset(overrides=None):
    """The kept preset (read once), with the person's own settings on top:
    { heavySlots, criticalPressureGuard } from Mod/AgentLink."""
    m = machine() or read_machine()
    m.pop("memoryCeilingGB", None)  # gone (18 Nov): the critical-pressure guard watches real memory instead
    m.setdefault("criticalPressureGuard", True)
    for k, v in (overrides or {}).items():
        if v or v is False:
            m[k] = v
    return m


_cache = {}


def _cached(key, fn, ttl=10.0):
    v = _cache.get(key)
    if v and time.time() - v[0] < ttl:
        return v[1]
    out = fn()
    _cache[key] = (time.time(), out)
    return out


def person_idle_seconds():
    import sys

    if sys.platform != "darwin":
        return None
    return _cached("idle", lambda: hid_idle_seconds(_run(["ioreg", "-c", "IOHIDSystem", "-r", "-k", "HIDIdleTime"])))


def mac_thermal():
    import sys

    if os.environ.get("AGENTLINK_FAKE_THERMAL"):  # tests
        return True
    return sys.platform == "darwin" and _cached("therm", lambda: thermal_limited(_run(["pmset", "-g", "therm"])))


def mac_pressure():
    import sys

    if sys.platform != "darwin":
        return "normal"
    return _cached("press", lambda: memory_pressure_level(_run(["sysctl", "kern.memorystatus_vm_pressure_level"])))

def machine_from(sysctl):
    """The preset from sysctl's answers: { chip, cores, perfCores, memoryGB,
    model, fan, heavySlots, criticalPressureGuard }."""
    def num(k, d=0):
        try:
            return int(str(sysctl.get(k, d)).strip())
        except ValueError:
            return d

    model = str(sysctl.get("hw.model", "")).strip()
    mem = num("hw.memsize")
    perf = num("hw.perflevel0.physicalcpu") or num("hw.physicalcpu")
    fan = not model.startswith("MacBookAir") if model else True
    slots = 1 if not fan else (2 if perf >= 8 else 1)
    return {
        "chip": str(sysctl.get("machdep.cpu.brand_string", "")).strip(),
        "cores": num("hw.ncpu") or num("hw.physicalcpu"),
        "perfCores": perf,
        "memoryGB": round(mem / 1024 ** 3, 1) if mem else None,
        "model": model,
        "fan": fan,
        "heavySlots": slots,
        "criticalPressureGuard": True,
    }


def machine():
    return _load(path("machine.json"), None)


def save_machine(m):
    _save(path("machine.json"), m)


def thermal_limited(pmset_therm):
    """`pmset -g therm`: a CPU speed limit under 100 means throttled."""
    m = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", pmset_therm or "")
    return bool(m) and int(m.group(1)) < 100


def memory_pressure_level(text):
    """`memory_pressure` / sysctl kern.memorystatus_vm_pressure_level: normal,
    warn or critical."""
    t = (text or "").lower()
    m = re.search(r"memorystatus_vm_pressure_level:\s*(\d)", t) or re.search(r"pressure level:\s*(\d)", t)
    if m:
        return {1: "normal", 2: "warn", 4: "critical"}.get(int(m.group(1)), "normal")
    m = re.search(r"system-wide memory free percentage:\s*(\d+)%", t)
    if m:
        free = int(m.group(1))
        return "critical" if free < 10 else ("warn" if free < 20 else "normal")
    return "normal"


def hid_idle_seconds(ioreg):
    """`ioreg -c IOHIDSystem`: HIDIdleTime is in nanoseconds."""
    m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', ioreg or "")
    return int(m.group(1)) / 1e9 if m else None


def queue_state():
    return _load(path("queue.json"), {"running": [], "waiting": [], "held": False, "timings": {}})


def save_queue(q):
    _save(path("queue.json"), q)


# The queue file is read and written by the supervisor (its main thread and
# its watchdog) and by each FreeCAD (a job's start and end, a heavy call's
# timing). Round 8 (00-042): the watchdog read the queue with fea_buckle
# running, asked macOS how long the person had been idle, and wrote it back
# held — after fea_buckle's end had been written in between: "A heavy job is
# running (fea_buckle, since 13:06)" stayed in the status bar for good. Each
# read-change-write now holds this lock (a file lock: any process), the
# slow part (asking macOS) done before it.
QUEUE_LOCK_WAIT = 5.0
_lock_depth = __import__("threading").local()


class queue_lock:
    """with queue_lock(): one read-change-write of queue.json at a time,
    across processes (fcntl.flock on queue.lock) and threads. Re-entrant in
    a thread. Past QUEUE_LOCK_WAIT s it goes on unlocked rather than hold
    a call up (held: False in that case). Never raises."""

    def __enter__(self):
        self.f = None
        self.held = False
        depth = getattr(_lock_depth, "n", 0)
        _lock_depth.n = depth + 1
        if depth:
            self.held = True  # the outer one holds it
            return self
        try:
            import fcntl

            os.makedirs(home(), exist_ok=True)
            self.f = open(path("queue.lock"), "a+")
            t0 = time.time()
            while True:
                try:
                    fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.held = True
                    break
                except OSError:
                    if time.time() - t0 > QUEUE_LOCK_WAIT:
                        break
                    time.sleep(0.02)
        except Exception:  # noqa: BLE001 — no fcntl (Windows) or no home: unlocked, as before
            pass
        return self

    def __exit__(self, *exc):
        _lock_depth.n = max(0, getattr(_lock_depth, "n", 1) - 1)
        if self.f is not None:
            try:
                import fcntl

                fcntl.flock(self.f, fcntl.LOCK_UN)
            except Exception:  # noqa: BLE001
                pass
            try:
                self.f.close()
            except Exception:  # noqa: BLE001
                pass
        return False


def update_queue(fn):
    """queue.json read, fn(q) run on it, written back, under queue_lock:
    fn's value. fn returning False leaves the file as it was."""
    with queue_lock():
        q = queue_state()
        got = fn(q)
        if got is not False:
            save_queue(q)
        return got


def pid_alive(pid):
    """Whether a process of this id still runs (signal 0). Plain Python."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


# A heavy call the supervisor let through is "running" in the queue until its
# answer comes back (queue_done); one with no call in hand for this long is a
# leftover (its end lost): taken out (stale_running).
STALE_AFTER = 15.0


def stale_running(q, busy, now=None, me=None):
    """q's running entries that are leftovers, taken out of q: a
    supervisor's own (no job) when it has no call in hand (busy false) and
    it is older than STALE_AFTER; a job's whose process is gone. The
    entries taken out. Plain Python."""
    now = time.time() if now is None else now
    me = os.getpid() if me is None else me
    keep_, gone = [], []
    for r in q.get("running") or []:
        if not isinstance(r, dict):
            gone.append(r)
            continue
        start = float(r.get("start") or r.get("t") or 0)
        if r.get("job") is not None:
            dead = r.get("pid") is not None and not pid_alive(r.get("pid"))
        else:
            mine = r.get("pid") in (None, me)
            dead = mine and not busy and now - start > STALE_AFTER
        (gone if dead else keep_).append(r)
    if gone:
        q["running"] = keep_
    return gone


# The hold's words once no heavy job runs (round 7: "A heavy job is running
# (…, since 12:44)" stayed in the status bar and in session_state long
# after that job ended).
HELD_IDLE = "No heavy job runs now; new heavy jobs wait for your go (one ran while you were working in the window)"


def settled_notice(q):
    """q with its hold's notice put right once nothing runs: the "is
    running" words replaced by HELD_IDLE (the hold itself stays until
    queue_go). True when changed. Plain Python."""
    if q.get("running") or not q.get("held"):
        return False
    if str(q.get("notice") or "").startswith("A heavy job is running"):
        q["notice"] = HELD_IDLE
        return True
    return False


def status_line(q, alive=None):
    """The status bar's line for the heavy queue: the hold's notice only while
    a heavy job runs, else None (the line is not said again, so it goes).
    alive(entry): whether a running entry is a job still running (the
    window's own jobs it can tell); a leftover does not keep the line.
    Plain Python."""
    running = q.get("running") or []
    if alive is not None:
        running = [r for r in running if _alive_or_unknown(alive, r)]
    if q.get("held") and q.get("notice") and running:
        return "Agent Link: " + str(q["notice"]) + " (say go in chat)."
    return None


def _alive_or_unknown(alive, r):
    try:
        return bool(alive(r))
    except Exception:  # noqa: BLE001
        return True


def log_timing(q, tool, size, seconds, keep=40):
    t = q.setdefault("timings", {}).setdefault(tool, [])
    t.append([float(size), float(seconds)])
    del t[:-keep]
    return q


def estimate(q, tool, size):
    """Seconds for a heavy job of this size, from its past runs: a line
    through them (time per unit of size), else None."""
    pts = [(s, t) for s, t in (q.get("timings") or {}).get(tool, []) if s > 0]
    if not pts:
        return None
    if len(pts) == 1:
        s, t = pts[0]
        return t * float(size) / s
    n = len(pts)
    mx, my = sum(s for s, _ in pts) / n, sum(t for _, t in pts) / n
    den = sum((s - mx) ** 2 for s, _ in pts)
    if den <= 0:
        return my
    b = sum((s - mx) * (t - my) for s, t in pts) / den
    a = my - b * mx
    return max(0.0, a + b * float(size))


def estimate_range(q, tool, size, last=12, recent=5, decay=0.75):
    """(low, typical, high) seconds for a job of this size, from the time
    per unit of size of its last runs here, or None with no runs. The
    newest runs count most (each older run decay times the one after it:
    the typical is their weighted middle), and low and high are the fastest
    and slowest of the newest few — so one slow run (a render that hit a
    busy Mac) does not stand as the estimate, and runs from before a fix
    made the tool faster stop weighing on it after a run or two (two 80–120 s
    renders from before renders were sized kept a 3 s render's estimate at
    13 s)."""
    pts = [(s, t) for s, t in ((q.get("timings") or {}).get(tool) or [])[-last:] if s > 0 and t >= 0]
    if not pts:
        return None
    rates = [t / s for s, t in pts]
    n = len(rates)
    weighted = sorted((r, decay ** (n - 1 - i)) for i, r in enumerate(rates))
    half, run, mid = sum(w for _r, w in weighted) / 2.0, 0.0, weighted[-1][0]
    for r, w in weighted:
        run += w
        if run >= half:
            mid = r
            break
    newest = rates[-recent:]
    lo, hi = min(min(newest), mid), max(max(newest), mid)
    return lo * float(size), mid * float(size), hi * float(size)


def said_range(r):
    """An estimate_range in words: "about 20 s (12–40 s from 5 runs)"."""
    if not r:
        return None
    lo, mid, hi = r

    def f(x):
        return f"{x:.0f} s" if x < 90 else f"{x / 60:.0f} min"

    return f"about {f(mid)}" + ("" if f(lo) == f(hi) else f" ({f(lo)} to {f(hi)})")


def admit(q, preset, busy_person, thermal, pressure):
    """Whether a new heavy job may start now: (True, None) or (False, why)."""
    if q.get("held"):
        return False, "held until the person says go (queue_go): they were working in the window when a job ran"
    if busy_person:
        return False, "the person is working in the window: new heavy jobs wait for their go (queue_go)"
    if thermal:
        return False, "macOS reports the Mac is throttling for heat"
    if pressure in ("warn", "critical"):
        return False, f"macOS reports memory pressure ({pressure})"
    slots = int((preset or {}).get("heavySlots") or 1)
    if len(q.get("running") or []) >= slots:
        return False, f"{slots} heavy job{'s' if slots > 1 else ''} at once on this Mac, and that many are running"
    return True, None
