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
    { heavySlots, memoryCeilingGB } from Mod/AgentLink."""
    m = machine() or read_machine()
    for k, v in (overrides or {}).items():
        if v:
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
    model, fan, heavySlots, memoryCeilingGB }."""
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
        "memoryCeilingGB": round(0.5 * mem / 1024 ** 3, 1) if mem else None,
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
