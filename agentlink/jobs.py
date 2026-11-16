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
# took more than SLOW_READ; any read with background: true; job_start
# { tool, arguments } for any read. Never a picture or a window tool (Qt
# and the 3D view are the GUI thread's), never a change. While a job runs,
# changing calls on the document are refused (the worker reads it).

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


def eligible(tool, args):
    """A read that may run on a worker thread: changes nothing and touches
    neither Qt nor the 3D view."""
    from . import outputs

    name = tool.name
    if name in outputs.SHOT_TOOLS or name.startswith(NOT_JOBS_PREFIX) or name == "batch":
        return False
    try:
        return not tool.changes_for(args or {})
    except Exception:
        return not getattr(tool, "changes", True)


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
    if not eligible(tool, args):
        return False
    if getattr(session, "batch_now", None):
        return False
    if asked:
        return True
    if keep.is_heavy(tool.name):
        return True
    from . import heavy

    return past_slow(tool.name, heavy.size_of(session))


def running(doc=None):
    """The jobs still running (on doc's session when given)."""
    with _lock:
        return [j for j in JOBS.values() if j["status"] == "running" and (doc is None or j.get("doc") == doc)]


def _queue(add=None, drop=None):
    """The heavy queue's "running" list carries the job while it runs."""
    try:
        q = keep.queue_state()
        r = [x for x in (q.get("running") or []) if not (drop and x.get("job") == drop)]
        if add:
            r.append(add)
        q["running"] = r
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
           "estimate": keep.said_range(r) if r else None, "done": threading.Event()}
    with _lock:
        JOBS[jid] = job
    _queue(add={"tool": tool.name, "job": jid, "t": job["started"]})
    call = fn or (lambda: tool.fn(args))

    def work():
        try:
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
                    q = keep.queue_state()
                    keep.log_timing(q, tool.name, size, secs)
                    keep.save_queue(q)
                except Exception:
                    pass
            _queue(drop=jid)
            job["done"].set()

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
        out["took"] = round((job.get("finished") or now) - job["started"], 1)
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


def note_slow(tool, args, session, secs):
    """A read that took longer than SLOW_READ, not a heavy tool: its time
    logged, so the next call of its size goes to a job at once (a read past
    a client's 80 s never got its answer back)."""
    if secs <= SLOW_READ or keep.is_heavy(tool.name) or not eligible(tool, args):
        return
    try:
        from . import heavy

        q = keep.queue_state()
        keep.log_timing(q, tool.name, heavy.size_of(session), secs)
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
