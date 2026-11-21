# SPDX-License-Identifier: LGPL-2.1-or-later
# Where a call's time goes besides the tool's own work: the parts of the hub
# that run round every call (the echo in the window and its view fit, the
# health check, the undo step, the add-ons' hooks, the batch's record, the
# applies-now filter: appliesNow, and its meter: appliesMeter), each timed
# under a name. A batch puts the split on a call's row as "around"
# when what ran round the tool took long (agentlink/tools.py), so a slow
# document can be read from the answers instead of guessed at.
#
# Cheap: two clock readings and a dict entry per part. One thread's story
# (the thread the calls run on); a job's worker thread adds nothing here.
import threading
import time

_parts = {}
_owner = [None]

# Parts that run inside a call's own "ms" (the server times the tool with
# them); every other part runs outside it.
INSIDE = ("healthMark", "health", "snapshot", "undoStep", "afterChange", "outputs", "appliesNow", "recompute")


def start():
    """Begin a call's split on this thread: what was gathered is dropped."""
    _owner[0] = threading.get_ident()
    _parts.clear()


def add(name, seconds):
    if _owner[0] != threading.get_ident():
        return
    _parts[name] = _parts.get(name, 0.0) + max(0.0, float(seconds))


class part:
    """with around.part("fit"): … — the block's time under that name."""

    def __init__(self, name):
        self.name = name
        self.t = 0.0

    def __enter__(self):
        self.t = time.time()
        return self

    def __exit__(self, *exc):
        add(self.name, time.time() - self.t)
        return False


def take():
    """The parts gathered since start(), in ms, and the split ended."""
    out = {k: int(round(v * 1000)) for k, v in _parts.items()}
    _parts.clear()
    _owner[0] = None
    return out


def split(wall_ms, tool_ms, parts, floor=500, least=5):
    """What a batch says of one call, or None when nothing round the tool
    took long. wall_ms: the whole call as the batch saw it; tool_ms: the
    answer's own "ms" (the tool with the parts in INSIDE); parts: take()'s.

    { wall, outside, inside (when any), tool }: outside is the time the
    answer's ms does not count, by part, with "other" for what no part
    claims; inside is the hub's share of the answer's ms, by part; tool is
    what is left of ms for the tool itself. Given when the outside total or
    the inside parts' total reaches floor ms; parts under least ms are left
    out."""
    wall_ms, tool_ms = int(wall_ms), int(tool_ms or 0)
    inside = {k: v for k, v in parts.items() if k in INSIDE}
    outside = {k: v for k, v in parts.items() if k not in INSIDE}
    out_total = max(0, wall_ms - tool_ms)
    in_total = sum(inside.values())
    if out_total < floor and in_total < floor:
        return None
    other = out_total - sum(outside.values())
    row = {"wall": wall_ms, "outside": {"ms": out_total, **{k: v for k, v in outside.items() if v >= least}}}
    if other >= least:
        row["outside"]["other"] = other
    shown = {k: v for k, v in inside.items() if v >= least}
    if shown:
        row["inside"] = shown
    row["tool"] = max(0, tool_ms - in_total)
    return row
