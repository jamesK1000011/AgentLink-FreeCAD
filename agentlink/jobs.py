# SPDX-License-Identifier: LGPL-2.1-or-later
# Long reads as jobs (unattended use, N). A client drops a call after about
# 80 s, so a read that runs longer (a wall-thickness map of a 124k-triangle
# scan) never got its answer back. Such a read runs on a worker thread
# beside the call: when it finishes within JOB_WAIT the call answers as
# ever; past that the call answers with a job id and the read goes on —
# job_status { job, wait } gives its answer when it is done. It sits in the
# heavy queue's "running" list while it runs (session_state shows it), and
# its time is logged as a heavy job's is, so the next one of its size is
# sent to a job at once.
#
# Which calls: a read (a tool that changes nothing) that is heavy
# (keep.HEAVY, an add-on's declared heavy tools) or whose past runs here
# took more than SLOW_READ, or that the watchdog stopped FreeCAD in before
# (keep.stopped_before); any read with background: true; job_start
# { tool, arguments } for any read. Never a picture or a window tool (Qt
# and the 3D view are the GUI thread's), never a change, never a read that
# drives the document on the way (IN_PLACE below). While a job runs,
# changing calls on the document are refused (the worker reads it).

import os
import threading
import time
import uuid

from . import keep
from .protocol import ToolError

# Seconds a call waits for its job before answering with the job's id: under
# a client's 80 s, with room for the reply.
JOB_WAIT = 45.0
# A read whose past runs here took longer than this goes to a job.
SLOW_READ = 20.0
# A finished job's answer is kept this long for job_status.
KEEP_DONE = 3600.0
# job_status waits at most this long for a job to finish.
MAX_POLL_WAIT = 30.0

NOT_JOBS_PREFIX = ("gui_", "window_", "dialog_", "view_", "app_", "doc_", "job_", "queue_")

_lock = threading.Lock()
JOBS = {}
# The queue's file is read, changed and written back here from two threads
# (a job's own as it ends, the call's as it logs a time): one at a time, or
# the later write put back what the other had just changed.
_queue_lock = threading.Lock()
# Called with a job's record when it ends, on the job's own thread (the
# window's echo: agentlink/echo.py job_listener, which hands it to the GUI
# thread). A listener never stops a job.
LISTENERS = []


def listen(fn):
    """fn(job) when a job ends (its own thread)."""
    if fn not in LISTENERS:
        LISTENERS.append(fn)


def answered(job):
    """The job's answer was given back in a call (the call that waited for
    it, or a batch that did): the window showed it with that call, so a
    listener leaves it."""
    try:
        job["answered"] = True
    except Exception:  # noqa: BLE001
        pass


# Reads that must run in place, on the GUI thread: each changes nothing by
# its kind (changes: false), yet on the way it drives the document, the
# window or the selection, which only the GUI thread may do. On a worker
# thread, with the GUI thread waiting for the job inside a batch, asm_sweep
# stopped FreeCAD for good (the watchdog started it again, three times).
# name → what it does on the way (said in background's refusal). Found by
# reading each read's code against FreeCAD 1.1's source; tests/
# test_hubfix3.py scans every read (the hub's Tool(…) calls and the entries
# of data/tools.json with the helpers they call) for the same signs and
# fails on one that is neither here, nor kept from jobs by its name
# (NOT_JOBS_PREFIX, outputs.SHOT_TOOLS), nor listed there as looked at.
IN_PLACE = {
    # poses placed, recomputed and put back (assembly.py sweep_run; assembly_more.py)
    "asm_sweep": "moves the parts through each pose and puts them back",
    "asm_motion": "moves the parts through each frame",
    # AssemblyObject::solve places the parts and redraws the joints
    # (src/Mod/Assembly/App/AssemblyObject.cpp: setNewPlacements,
    # redrawJointPlacements). exportAsASMT writes no property, but builds
    # the assembly's solver model afresh in the object itself (mbdAssembly,
    # objectPartMap), the one a solve or a drag in the window works in.
    "asm_list": "solves the assembly on the way, which places its parts",
    "asm_check": "solves the assembly on the way, which places its parts",
    "asm_export": "builds the assembly's solver model afresh, the one a solve or a drag in the window uses",
    # SketchObject::solve writes the solved geometry back and signals the
    # sketch's view (src/Mod/Sketcher/App/SketchObject.cpp).
    "sketch_state": "solves the sketch on the way",
    # views recomputed and Qt's events pumped while TechDraw's threads land
    # (techdraw.py recompute, settle, warm).
    "td_list": "recomputes views that have no lines yet",
    "td_geometry": "recomputes the page's views",
    "td_export": "recomputes the page's views",
    # the IFC file linked from the document's Meta, so a reopened document
    # finds it (families/ifc.py keep_link).
    "ifc_open": "links the IFC file it opens from the document (its Meta)",
    "ifc_save": "links the copy it writes from the document (its Meta)",
    # FreeCAD.setActiveDocument signals the window (src/App/Application.cpp;
    # src/Gui/Application.cpp slotActiveDocument activates an MDI window);
    # cam_post also sets the job's PostProcessorArgs and puts them back.
    "cam_list": "makes its document FreeCAD's active one",
    "cam_library": "makes its document FreeCAD's active one",
    "cam_post": "sets the job's post-processor arguments for the run and puts them back",
    # each point set on the robot's Tcp and axes, then put back and recomputed
    "robot_run": "moves the robot through the trajectory and puts its axes back",
    # FreeCAD.GuiUp switched off for the whole process while it writes
    "scad_export": "switches FreeCAD's window flag off while it writes",
    # exportIFC works on FreeCAD.ActiveDocument and recomputes it
    # (src/Mod/BIM/importers/exportIFC.py).
    "bim_export": "recomputes the document as FreeCAD's IFC exporter does",
    # the notes' faces looked for again and written back into the document
    "note_list": "writes the notes it followed back into the document",
    # its wait pumps Qt's events so the window keeps painting
    "addon_test": "keeps the window painting while it waits",
    # the OpenSCAD program it found is written to FreeCAD's settings
    # (openscad.py exe): a setting's observers run on the writing thread
    "scad_status": "writes the OpenSCAD program it found into FreeCAD's settings",
    # a checkpoint older than the session is read from its saved copy: a
    # document opened, recomputed and closed (tools.py _step_in_file)
    "history_diff": "opens a checkpoint's saved copy beside the document, and closes it",
    # now: true reads the window's selection and state (nexthint.py)
    "tool_groups": "reads the window's selection and state for now: true",
    # FreeCAD's undo and redo, a recompute and the step's snapshot
    "history_undo": "undoes steps in the document",
    "history_redo": "redoes steps in the document",
    # the window itself: selection, workbench, menus and commands (Qt), the
    # Report view's widget, what the window is in the middle of (next)
    "selection": "sets the window's selection",
    "workbench": "reads and activates the window's workbenches",
    "cmd_list": "reads the window's commands",
    "menu_list": "reads the window's menus",
    "report_read": "reads the window's Report view",
    "session_state": "reads the window (workbench, selection, what is open) for next",
    # settings written: every observer of the parameter group runs on the
    # writing thread, the window's own among them
    "pref_import": "writes settings the window listens to",
    "pref_reset": "writes settings the window listens to",
    # runs other tools, changes among them
    "live_run": "runs a script of calls, changes among them",
    "addon": "drives FreeCAD's Addon Manager",
}
MOVES_PARTS = IN_PLACE  # its first name, when it held asm_sweep and asm_motion alone

# Reads that run in place only as the document stands: a strength study of
# one solid of a body of several keeps a hidden helper object, made or
# refreshed (its Shape set) at the start of each of these (strength.py
# solid_holder). Any other study only reads, and the solve stays a job.
def _study_of_one_solid(session):
    from . import store

    return bool((store.read(session.doc, "fea", None) or {}).get("of"))


IN_PLACE_WHEN = {
    "fea_heat": (_study_of_one_solid, "refreshes the hidden helper of a study of one solid"),
    "fea_buckle": (_study_of_one_solid, "refreshes the hidden helper of a study of one solid"),
    "fea_modes": (_study_of_one_solid, "refreshes the hidden helper of a study of one solid"),
}


def in_place(name, why):
    """An add-on's read that drives the document or the window on the way
    (poses tried and put back, a solve, a recompute, the selection): never
    run as a job. why: a few words for background's refusal, after the
    tool's name ("moves the parts and puts them back")."""
    IN_PLACE[str(name)] = str(why)


def why_in_place(name, session=None):
    """What a read does on the way that keeps it on the GUI thread, or None."""
    why = IN_PLACE.get(name)
    if why is None and session is not None and name in IN_PLACE_WHEN:
        test, words = IN_PLACE_WHEN[name]
        try:
            why = words if test(session) else None
        except Exception:
            why = None  # no document, no study: nothing to refresh
    return why


def eligible(tool, args, session=None):
    """A read that may run on a worker thread: changes nothing and touches
    neither the document, Qt nor the 3D view on the way (session: as its
    document stands, where that decides it)."""
    from . import outputs

    name = tool.name
    if name in outputs.SHOT_TOOLS or name.startswith(NOT_JOBS_PREFIX) or name == "batch" or why_in_place(name, session) is not None:
        return False
    try:
        return not tool.changes_for(args or {})
    except Exception:
        return not getattr(tool, "changes", True)


def writes_file(tool, args):
    """Whether this call writes a file (an export; agentlink/paths.py
    WRITERS, an add-on's declared writers, or action: "export"): a read
    as far as the document goes, so it may run as a job, but what comes
    after it may need the file."""
    from . import paths

    return tool.name in paths.WRITERS or (args or {}).get("action") == "export"


def background_refusal(tool, args, in_batch, session=None):
    """Why background: true was not taken for this call, and what to do
    instead — by what the call is: a read asked for inside a batch (plain,
    or one that writes a file: the calls after it wait for the file, so it
    belongs in the batch's order), or a call that can never be a job."""
    name = tool.name
    if in_batch and eligible(tool, args, session):
        if writes_file(tool, args):
            return (f"background: not inside a batch, which is one answer. {name} writes a file: leave background out and it runs here in its place, "
                    f"the file written before the next call starts. (On its own, {name} with background: true runs as a job: it answers with a job id past 45 s, "
                    "and the file is whole only once job_status says done.)")
        return (f"background: not inside a batch, which is one answer — call {name} on its own with background: true "
                "(or job_start { tool, arguments }), or leave background out here.")
    try:
        changing = bool(tool.changes_for(args or {}))
    except Exception:  # noqa: BLE001
        changing = bool(getattr(tool, "changes", False))
    if changing:
        return (f"background: {name} changes the document, so it cannot run as a job (only a read that leaves the window and the 3D view alone can) — "
                "leave background out: it runs as a plain call" + (", here in the batch's order." if in_batch else "."))
    why = why_in_place(name, session)
    if why:
        return (f"background: {name} cannot run as a job — it changes nothing, but it {why}, which only the window's own thread may do. "
                "Leave background out" + (": it runs here in the batch's order." if in_batch else ": it runs as a plain call."))
    return (f"background: {name} cannot run as a job — only a read that leaves the window and the 3D view alone can (not a change, a picture or a window tool). "
            "Leave background out" + (": it runs here in the batch's order." if in_batch else "."))


def start_in_batch_refusal(name):
    """job_start inside a batch, for a read that would be a job on its own:
    it is the batch that starts no job (wanted), not the tool that cannot be
    one — and what to do instead."""
    return (f"job_start: not inside a batch, which is one answer and starts no job — call job_start {{ tool: \"{name}\", arguments }} on its own, "
            f"or call {name} itself here: a heavy read inside a batch runs in its place and the batch waits for it.")


def past_slow(tool_name, size):
    """Its past runs here say it takes longer than SLOW_READ at this size."""
    try:
        r = keep.estimate_range(keep.queue_state(), tool_name, size)
    except Exception:
        return False
    return bool(r) and r[1] > SLOW_READ


def wanted(tool, args, session, asked=False):
    """Whether this call runs as a job: asked (background: true, job_start),
    or a heavy read, or a read slow before. Never inside a batch (the batch
    is one answer)."""
    if not eligible(tool, args, session):
        return False
    if getattr(session, "batch_now", None):
        return False
    if asked:
        return True
    if keep.is_heavy(tool.name):
        return True
    # A read the watchdog stopped FreeCAD in before (it never answered, so
    # its time was never logged): a job from then on.
    if keep.stopped_before(tool.name) is not None:
        return True
    from . import heavy

    # A sized read (keep.SIZED: export's meshing) estimated past SLOW_READ
    # at its input size: a job, so the window is not frozen meanwhile
    # (live, 18 Nov: an STL export of a smooth loft held it past 123 s).
    if tool.name in keep.SIZED:
        est = sized_estimate(tool.name, args, session)
        if est is not None and est > SLOW_READ:
            return True
    return past_slow(tool.name, heavy.size_of(session))


def sized_estimate(name, args, session, size=None):
    """Seconds a sized tool (keep.SIZED) should take for these arguments
    (its input size), or None when the size cannot be read."""
    from . import heavy

    try:
        if size is None:
            size = heavy.sized_size(session, name, args or {})
        if not size:
            return None
        q = keep.queue_state()
        est = keep.sized_estimate(q, name, size, keep.sized_key(name, args or {}))
        after = keep.stopped_before(name, q=q)
        return max(est, 1.5 * after) if est is not None and after is not None else est
    except Exception:  # noqa: BLE001
        return None


def running(doc=None):
    """The jobs still running (on doc's session when given)."""
    with _lock:
        return [j for j in JOBS.values() if j["status"] == "running" and (doc is None or j.get("doc") == doc)]


def _queue(add=None, drop=None):
    """The heavy queue's "running" list carries the job while it runs."""
    try:
        with _queue_lock, keep.queue_lock():
            q = keep.queue_state()
            # A job dies with its FreeCAD: one this process does not know is a
            # leftover of a FreeCAD that was stopped, and would hold the queue's
            # one slot (and the person's "held") for good. Another FreeCAD's
            # running job (its pid alive) is its own to take out.
            with _lock:
                mine = set(JOBS)
            me = os.getpid()

            def kept(x):
                if drop and x.get("job") == drop:
                    return False
                if x.get("job") is None or x.get("job") in mine:
                    return True
                return x.get("pid") not in (None, me) and keep.pid_alive(x.get("pid"))
            r = [x for x in (q.get("running") or []) if isinstance(x, dict) and kept(x)]
            if add:
                r.append(add)
            q["running"] = r
            keep.settled_notice(q)
            keep.save_queue(q)
    except Exception:
        pass


def _prune():
    now = time.time()
    with _lock:
        for k in [k for k, j in JOBS.items() if j["status"] != "running" and now - (j.get("finished") or now) > KEEP_DONE]:
            JOBS.pop(k, None)


def start(tool, args, session, fn=None):
    """Run tool on a worker thread as a job: its record."""
    from . import heavy

    _prune()
    size = heavy.size_of(session)
    try:
        r = keep.estimate_range(keep.queue_state(), tool.name, size)
    except Exception:
        r = None
    jid = "job-" + uuid.uuid4().hex[:8]
    doc = getattr(getattr(session, "doc", None), "Name", None)
    job = {"job": jid, "tool": tool.name, "status": "running", "started": time.time(), "size": size, "doc": doc,
           "estimate": keep.said_range(r) if r else None, "done": threading.Event(),
           # Its arguments, for the window's words when it ends (never in an answer: summary leaves them).
           "args": dict(args or {}) if isinstance(args, dict) else {}}
    with _lock:
        JOBS[jid] = job
    _queue(add={"tool": tool.name, "job": jid, "t": job["started"], "pid": os.getpid()})
    call = fn or (lambda: tool.fn(args))
    # Where its thread is, should it still run after a minute
    # (protocol.hang_trace: <outDir>/crash/hang-job-<tool>.txt). A job runs
    # outside the call that started it, so the call's own watch ends with
    # the call's answer and never saw a job that hung.
    from .protocol import hang_trace

    watch = hang_trace(getattr(session, "out_dir", None), tool.name, "job")

    def work():
        try:
            with watch:
                out = call()
            job["result"] = out
            job["status"] = "done"
        except ToolError as e:
            job["error"] = {"code": e.code, "message": e.message}
            job["status"] = "failed"
        except Exception as e:  # noqa: BLE001 — the job's answer says it
            from .protocol import failed_words

            job["error"] = {"code": "failed", "message": failed_words(tool.name, e)}
            job["status"] = "failed"
        finally:
            job["finished"] = time.time()
            secs = job["finished"] - job["started"]
            if job["status"] == "done" and secs >= 1.0:
                try:
                    with _queue_lock, keep.queue_lock():
                        q = keep.queue_state()
                        keep.log_timing(q, tool.name, size, secs)
                        keep.save_queue(q)
                except Exception:
                    pass
            _queue(drop=jid)
            job["done"].set()
            for fn in list(LISTENERS):
                try:
                    fn(job)
                except Exception:  # noqa: BLE001  (the window's words never stop a job)
                    pass

    threading.Thread(target=work, name=f"agentlink-job-{tool.name}", daemon=True).start()
    return job


def summary(job):
    """What a job is now, for an answer: running (how long, the estimate)
    or its result or error."""
    out = {"job": job["job"], "tool": job["tool"], "status": job["status"]}
    now = time.time()
    if job["status"] == "running":
        out["running"] = round(now - job["started"], 1)
        if job.get("estimate"):
            out["expected"] = job["estimate"] + " (from past runs here)"
        out["next"] = f"job_status {{ job: \"{job['job']}\", wait: 25 }} waits for it and gives its answer."
    else:
        # Seconds; a short job to the millisecond (live, 17 Nov: body_check
        # and meshobj_info jobs all said 0.0 at one decimal).
        secs = max(0.0, (job.get("finished") or now) - job["started"])
        out["took"] = round(secs, 1) if secs >= 1.0 else round(secs, 3)
    return out


def wait_for(job, seconds):
    job["done"].wait(max(0.0, float(seconds)))
    return job["status"] != "running"


def get(jid):
    with _lock:
        j = JOBS.get(jid)
    if j is None:
        known = ", ".join(sorted(JOBS)[-5:]) or "none"
        raise ToolError("not_found", f"job {jid!r}: no such job here (a finished job's answer is kept an hour; a restart of FreeCAD loses them) — the jobs: {known}.")
    return j


def guard_change(tool, args, session):
    """A changing call while a job reads the same document: refused (the
    worker is reading it), with the job to wait for."""
    try:
        changes = tool.changes_for(args or {})
    except Exception:
        changes = bool(getattr(tool, "changes", False))
    if not changes:
        return
    doc = getattr(getattr(session, "doc", None), "Name", None)
    busy = running(doc)
    if busy:
        j = busy[0]
        raise ToolError("invalid_state", f"{j['tool']} is still running as {j['job']} and reads this document: {tool.name} would change it under it. "
                        f"job_status {{ job: \"{j['job']}\", wait: 25 }} waits for it (or doc_switch to another document). Nothing was run.")


# Each tool's last few times in this FreeCAD (every call that answered
# here, any tool): what a batch reads so that it does not start a call it
# has too little of its budget left for (one slow call took a 55 s batch
# to 75 s, past what a client waits).
_RECENT = {}
RECENT_KEEP = 5
_recent_lock = threading.Lock()


TYPICAL_MAX = 300.0  # s: a logged estimate above this is not trusted for a batch budget


def note_time(name, secs, size=None):
    """One call of tool name took secs (kept in memory, the last few), with
    its input size when it has one (a sized tool: keep.SIZED)."""
    try:
        secs = float(secs)
    except (TypeError, ValueError):
        return
    if secs < 0:
        return
    try:
        size = float(size) if size else None
    except (TypeError, ValueError):
        size = None
    with _recent_lock:
        t = _RECENT.setdefault(name, [])
        # A plain time, or (time, size) for a sized call.
        t.append((secs, size) if size else secs)
        del t[:-RECENT_KEEP]


def _middle(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2]


def typical(name, session=None, args=None):
    """Seconds a call of tool name typically takes here, or None when not
    known: the middle of its last times in this FreeCAD, and, where a slow
    read of it was logged (note_slow), its typical time at the open
    document's size — the larger of the two. A sized tool (keep.SIZED) has
    its times scaled by its input size (this call's against theirs): a
    part_from_mesh of 36k triangles took 78 s, and one of 3.6k was not
    started on that 78 s (live, 18 Nov). With no size to scale by: None,
    so the call starts."""
    with _recent_lock:
        t = [x if isinstance(x, tuple) else (x, None) for x in (_RECENT.get(name) or [])]
    sized = name in keep.SIZED
    if t and sized:
        if args is None or session is None:
            return None
        from . import heavy

        try:
            cur = heavy.sized_size(session, name, args)
        except Exception:  # noqa: BLE001
            cur = None
        scaled = [secs * float(cur) / size for secs, size in t if size] if cur else []
        return _middle(scaled) if scaled else None
    if t:
        # Measured here, now: the middle of the last times.
        return _middle(secs for secs, _size in t)
    if sized:
        # Not timed in this FreeCAD: its sized estimate at this call's size,
        # when sane (the same bound as below).
        est = sized_estimate(name, args, session) if args is not None and session is not None else None
        return est if est is not None and 0 < est <= TYPICAL_MAX else None
    try:
        q = keep.queue_state()
        if (q.get("timings") or {}).get(name):
            from . import heavy

            r = keep.estimate_range(q, name, heavy.size_of(session) if session is not None else 1)
            # The size-scaled estimate of the slow-read log can run wild (live,
            # 17 Nov: insp_run "2466 s", part_loft "7813307 s"): used only when sane.
            if r and 0 < r[1] <= TYPICAL_MAX:
                return r[1]
    except Exception:
        pass
    return None


def note_slow(tool, args, session, secs):
    """A read that took longer than SLOW_READ, not a heavy tool: its time
    logged, so the next call of its size goes to a job at once (a read past
    a client's 80 s never got its answer back). Every call's time is also
    kept in memory (note_time), for a batch's budget."""
    name = getattr(tool, "name", None)
    got = getattr(session, "sized_now", None)
    size = got[1] if isinstance(got, tuple) and len(got) == 2 and got[0] == name else None
    if got is not None:
        try:
            session.sized_now = None
        except Exception:  # noqa: BLE001
            pass
    note_time(name, secs, size)
    if secs <= SLOW_READ or keep.is_heavy(tool.name) or not eligible(tool, args, session):
        return
    try:
        from . import heavy

        size = heavy.size_of(session)
        with _queue_lock, keep.queue_lock():
            q = keep.queue_state()
            keep.log_timing(q, tool.name, size, secs)
            keep.save_queue(q)
    except Exception:
        pass


def status(a):
    """job_status: one job (wait up to MAX_POLL_WAIT s for it), or every
    job kept."""
    jid = a.get("job")
    if not jid:
        _prune()
        with _lock:
            js = list(JOBS.values())
        return {"jobs": [summary(j) for j in js], **({} if js else {"note": "No jobs: a long read (a heavy one, one slow before, or background: true) runs as one."})}
    j = get(jid)
    w = a.get("wait", 0)
    if isinstance(w, bool) or not isinstance(w, (int, float)) or w < 0:
        raise ToolError("invalid_input", f"wait: seconds to wait for it, 0 to {MAX_POLL_WAIT:.0f}.")
    wait_for(j, min(float(w), MAX_POLL_WAIT))
    out = summary(j)
    if j["status"] == "done":
        res = j.get("result")
        if isinstance(res, dict):
            res = {k: v for k, v in res.items() if k != "_png"}
        out["result"] = res
    elif j["status"] == "failed":
        out["error"] = j.get("error")
    return out
