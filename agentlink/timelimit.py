# SPDX-License-Identifier: LGPL-2.1-or-later
"""The run's time limit, as a setting (decision 7, 24 Nov).

A runner that gives an agent a fixed time (a test run, a scheduled job)
passes the limit to Agent Link in the environment:

    AGENTLINK_TIME_LIMIT_MIN    the run's limit in minutes (a number > 0)

It is read once, when Agent Link starts. The time counts from the first
tools/call, not from the start of the server: a client can start the
server some time before the agent's first call.

When it is set, session_state has "time": "N of M minutes used". The
health verdict that a changing answer carries ends with the same words
("time: N of M minutes used") only from half the limit on (SHOW_FROM): before
that the line was noise in every verdict (24 Nov blind QA). A batch says it
once, on its last call's health. N is whole minutes, rounded down. When it
is not set (or not a number above 0), nothing is shown: normal use does
not change.
"""
import os
import time

ENV = "AGENTLINK_TIME_LIMIT_MIN"
SHOW_FROM = 0.5   # the part of the limit used from which a health verdict says the time


def _read(raw):
    try:
        v = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return v if v > 0 and v == v and v != float("inf") else None


LIMIT = _read(os.environ.get(ENV, ""))   # read at start
_first = [None]                          # time of the first tools/call


def configure(raw=None):
    """Read the limit again (tests; raw: a value in place of the
    environment's) and start the count again. The limit, or None."""
    global LIMIT
    LIMIT = _read(os.environ.get(ENV, "") if raw is None else raw)
    _first[0] = None
    return LIMIT


def started(now=None):
    """Mark the first tools/call. Later calls change nothing."""
    if _first[0] is None:
        _first[0] = time.time() if now is None else now


def _num(v):
    return str(int(v)) if v == int(v) else f"{v:g}"


def used(now=None):
    """'N of M minutes used', or None when no limit is set."""
    if LIMIT is None:
        return None
    t0 = _first[0]
    n = 0 if t0 is None else max(0, int(((time.time() if now is None else now) - t0) // 60))
    return f"{n} of {_num(LIMIT)} minutes used"


def line(now=None):
    """'time: N of M minutes used', or None when no limit is set."""
    u = used(now)
    return f"time: {u}" if u else None


def matters(now=None):
    """Whether a health verdict says the time: a limit is set and at least
    SHOW_FROM of it is used."""
    if LIMIT is None or _first[0] is None:
        return False
    return ((time.time() if now is None else now) - _first[0]) / 60.0 >= LIMIT * SHOW_FROM


def state():
    """{ time } for session_state, or {} when no limit is set."""
    u = used()
    return {"time": u} if u else {}


def mark_health(h, now=None):
    """The time line added at the end of a health verdict (once), from half
    the limit on (matters). Never raises."""
    try:
        ln = line(now) if matters(now) else None
        if ln and isinstance(h, dict) and ln not in str(h.get("facts", "")):
            h["facts"] = f"{h.get('facts', '')}; {ln}".lstrip("; ")
    except Exception:  # noqa: BLE001
        pass
    return h
