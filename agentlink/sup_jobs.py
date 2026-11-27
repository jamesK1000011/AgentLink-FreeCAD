# SPDX-License-Identifier: LGPL-2.1-or-later
# Calls that move themselves to the background (findings 41, 45; "no
# prejudging"). Every call starts normally. The supervisor, a process of
# its own that never waits on FreeCAD's threads, times each call from when
# it came in. A call with no answer after DETACH_AFTER (about 60 s) is
# answered with a job number ("call-N"), and goes on where it runs (the
# window's thread, or the hidden FreeCAD). Its real answer, when it comes,
# is kept here. job_status { job: "call-N" } is answered here at once, from
# this table, never queued behind FreeCAD. A client drops a call after about
# 80 s, so the job answer always goes first and no answer is lost. No
# estimate decides anything here. No FreeCAD: plain Python.

import json
import os
import threading
import time

DETACH_AFTER = float(os.environ.get("AGENTLINK_DETACH_AFTER", "60"))
MAX_POLL_WAIT = 30.0
KEEP_DONE = 3600.0
PREFIX = "call-"


def _text_result(mid, body, is_error=False):
    out = {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(body)}]}}
    if is_error:
        out["result"]["isError"] = True
    return json.dumps(out)


def _body_of(line):
    """(body, isError) of a tools/call reply line."""
    try:
        r = json.loads(line).get("result") or {}
        text = "".join(c.get("text", "") for c in r.get("content") or [] if c.get("type") == "text")
        return json.loads(text) if text else {}, bool(r.get("isError"))
    except (ValueError, AttributeError, TypeError):
        return {"raw": str(line)[:2000]}, True


class Jobs:
    """The calls in hand, by their JSON-RPC id, and the jobs they became.

    write(line): the client's stdout. clock: time.time."""

    def __init__(self, write, clock=time.time, after=None):
        self.write_out = write
        self.clock = clock
        self.after = DETACH_AFTER if after is None else float(after)
        self.lock = threading.Lock()
        self.calls = {}   # id -> {tool, t, after, mode, job}
        self.jobs = {}    # job -> {job, tool, id, started, status, result, error, done(Event)}
        self.n = 0
        self.ahead = None  # the job a new call waits behind (the oldest running one)

    # ---- the calls ----------------------------------------------------------------------

    def came(self, mid, tool, after=None, mode="job"):
        """A tools/call came in. after: seconds before it is answered for
        (None: DETACH_AFTER; 0: at once). mode "job": answered with a job
        number, its answer kept; "drop": answered with the words given to
        drop(), its late answer dropped."""
        if mid is None:
            return
        with self.lock:
            self.calls[mid] = {"tool": tool, "t": self.clock(), "after": self.after if after is None else float(after), "mode": mode}

    def write(self, line):
        """Every reply line to the client goes through here: a reply for a
        call that became a job is kept, not written."""
        try:
            mid = json.loads(line).get("id")
        except (ValueError, AttributeError):
            mid = None
        with self.lock:
            c = self.calls.pop(mid, None) if mid is not None else None
            job = c.get("job") if c else None
            dropped = bool(c and c.get("dropped"))
        if dropped:
            return False
        if job is None:
            self.write_out(line)
            return True
        body, err = _body_of(line)
        with self.lock:
            j = self.jobs.get(job)
            if j is None:
                return False
            j["finished"] = self.clock()
            if err:
                j["status"] = "failed"
                j["error"] = body.get("error") if isinstance(body, dict) and "error" in body else body
            else:
                j["status"] = "done"
                j["result"] = body
            j["done"].set()
        return False

    def tick(self, now=None, words=None):
        """Every call past its time: answered now (a job number, or the
        drop words). words(call): the drop answer's text for a call."""
        now = self.clock() if now is None else now
        out = []
        with self.lock:
            due = [(mid, c) for mid, c in self.calls.items() if not c.get("job") and not c.get("dropped") and now - c["t"] >= c["after"]]
            for mid, c in due:
                if c["mode"] == "drop":
                    c["dropped"] = True
                    out.append((mid, None, c))
                    continue
                self.n += 1
                jid = f"{PREFIX}{self.n}"
                c["job"] = jid
                ahead = self._ahead(mid)
                self.jobs[jid] = {"job": jid, "tool": c["tool"], "id": mid, "started": c["t"], "status": "running",
                                  "done": threading.Event(), "behind": ahead}
                out.append((mid, jid, c))
        for mid, jid, c in out:
            if jid is None:
                self.write_out(_text_result(mid, {"error": {"code": "busy", "message": (words(c) if words else "No answer in time.")}}, True))
            else:
                self.write_out(_text_result(mid, self.detached_words(jid, now)))
        return [jid for _m, jid, _c in out if jid]

    def _ahead(self, mid):
        """The oldest call before this one that is still running: what a
        queued call waits behind."""
        older = [(c["t"], c.get("job"), c["tool"]) for m, c in self.calls.items() if m != mid and c["t"] < self.calls[mid]["t"] and c["mode"] == "job"]
        if not older:
            return None
        t, job, tool = min(older)
        return {"tool": tool, "job": job}

    def detached_words(self, jid, now=None):
        j = self.jobs[jid]
        now = self.clock() if now is None else now
        secs = int(now - j["started"])
        b = j.get("behind")
        if b:
            where = f"It waits behind {b['tool']}" + (f" ({b['job']})" if b.get("job") else "") + ", which still runs in FreeCAD; it runs after that."
        else:
            where = "It goes on in FreeCAD."
        first = (f"{j['tool']} started as {jid}; this answer does not wait for it." if secs < 1 else
                 f"{j['tool']} has no answer after {secs} s, so it moved to the background as {jid}.")
        return {"job": jid, "tool": j["tool"], "status": "running", "running": secs,
                "note": f"{first} {where} Nothing was stopped.",
                "next": f"job_status {{ job: \"{jid}\", wait: 25 }} gives its answer. Calls sent meanwhile wait their turn behind it."}

    # ---- job_status ---------------------------------------------------------------------

    def mine(self, jid):
        return isinstance(jid, str) and jid.startswith(PREFIX)

    def summary(self, j, now=None):
        now = self.clock() if now is None else now
        out = {"job": j["job"], "tool": j["tool"], "status": j["status"]}
        if j["status"] == "running":
            out["running"] = round(now - j["started"], 1)
            out["next"] = f"job_status {{ job: \"{j['job']}\", wait: 25 }} waits for it and gives its answer."
        else:
            out["took"] = round(max(0.0, (j.get("finished") or now) - j["started"]), 1)
        return out

    def status(self, args, wait=True):
        """job_status for a call-N job (or the list of them): (body, isError)."""
        self._prune()
        jid = (args or {}).get("job")
        if not jid:
            with self.lock:
                js = list(self.jobs.values())
            return {"jobs": [self.summary(j) for j in js]}, False
        with self.lock:
            j = self.jobs.get(jid)
        if j is None:
            with self.lock:
                known = ", ".join(sorted(self.jobs)[-5:]) or "none"
            return {"error": {"code": "not_found", "message": f"job {jid!r}: not known here. A finished job's answer is kept for an hour. The server keeps them in its memory: they are lost when it starts again (agentlink_update). The jobs: {known}."}}, True
        w = (args or {}).get("wait", 0)
        if isinstance(w, bool) or not isinstance(w, (int, float)) or w < 0:
            return {"error": {"code": "invalid_input", "message": f"wait: seconds to wait for it, 0 to {MAX_POLL_WAIT:.0f}."}}, True
        stop = (args or {}).get("stop")
        if stop is not None and not isinstance(stop, bool):
            return {"error": {"code": "invalid_input", "message": "stop: true to stop the job, or leave it out."}}, True
        if wait and not stop:
            j["done"].wait(min(float(w), MAX_POLL_WAIT))
        out = self.summary(j)
        if stop:
            out["stop"] = self.stop_words(j)
        if j["status"] == "done":
            out["result"] = j.get("result")
        elif j["status"] == "failed":
            out["error"] = j.get("error")
        return out, False

    def stop_words(self, j):
        """job_status { job: "call-N", stop: true } (fault 89). A call-N job
        runs on FreeCAD's own thread: nothing is injected there, so it cannot
        stop in the middle. The words say so, and the next steps."""
        if j["status"] != "running":
            return f"Nothing to stop: the call is {j['status']}."
        cp = checkpoint_since(j["started"])
        lost = (f"The checkpoint {cp} from before the call is kept: tool_find {{ query: \"restore checkpoint\" }} finds the tool that goes back to it."
                if cp else "Unsaved work in FreeCAD is lost. tool_find { query: \"recover documents\" } finds a tool that lists the copies FreeCAD kept.")
        return (f"{j['tool']} ({j['job']}) runs on FreeCAD's own thread, so it cannot stop in the middle. Nothing was stopped. "
                f"Next: wait for it (job_status {{ job: \"{j['job']}\", wait: 25 }}), "
                f"or app_force_restart, which stops FreeCAD and starts it again. {lost}")

    def _prune(self):
        now = self.clock()
        with self.lock:
            for k in [k for k, j in self.jobs.items() if j["status"] != "running" and now - (j.get("finished") or now) > KEEP_DONE]:
                self.jobs.pop(k, None)

    def forget(self, mid):
        """A call answered another way (urgent paths): no longer timed."""
        with self.lock:
            self.calls.pop(mid, None)


def job_start_inner(args):
    """job_start { job, arguments, wait } as the call it starts: (tool,
    arguments, after) with after 0 for wait: false, else None (the
    normal DETACH_AFTER). None when it is not one the supervisor runs (no
    tool, a job_ or app_ tool, or agentlink_update)."""
    a = args or {}
    tool = a.get("job")
    if not isinstance(tool, str) or not tool or tool.startswith(("job_", "app_")) or tool == "agentlink_update":
        return None
    inner = a.get("arguments") or {}
    if not isinstance(inner, dict):
        return None
    return tool, dict(inner), (0.0 if a.get("wait") is False else None)


def checkpoint_since(t):
    """The checkpoint an add-on took before the call in hand, when it was
    taken after t (keep.call_checkpoint), or None."""
    try:
        from . import keep

        return keep.call_checkpoint(since=t)
    except Exception:  # noqa: BLE001
        return None
