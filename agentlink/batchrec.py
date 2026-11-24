# SPDX-License-Identifier: LGPL-2.1-or-later
"""A batch's record of what ran (plain Python; used by tools.py's batch)."""
import json
import os
import re
import time

# Every batch keeps what ran in a file of its own under the session's
# folder (batches/<time>.json), rewritten as each call ends: after a forced
# restart or a dropped call the agent reads there what ran. The newest
# BATCH_KEEP are kept.
BATCH_DIR, BATCH_KEEP = "batches", 20


def batch_record_path(out_dir, now=None, taken=os.path.exists):
    """batches/<date>-<time>.json under out_dir, with -2, -3 … when two
    batches start in one second."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now if now is not None else time.time()))
    base = os.path.join(out_dir, BATCH_DIR, stamp)
    path, n = base + ".json", 1
    while taken(path):
        n += 1
        path = f"{base}-{n}.json"
    return path


def batch_records_trim(folder, keep=BATCH_KEEP):
    """All but the newest keep records in folder removed (by name: the
    names are their times). The paths removed."""
    try:
        names = sorted(n for n in os.listdir(folder) if re.fullmatch(r"\d{8}-\d{6}(-\d+)?\.json", n))
    except OSError:
        return []
    gone = []
    for n in names[:-keep] if keep > 0 else names:
        try:
            os.remove(os.path.join(folder, n))
            gone.append(os.path.join(folder, n))
        except OSError:
            pass
    return gone


class BatchRecord:
    """A batch's record: { started, calls, first, running, results } while
    it runs, the whole answer when it ends. write() never raises; a write
    that is slow (large answers) is then made every fifth call and at the
    end."""

    def __init__(self, out_dir, total, first, now=None):
        self.path, self.ok, self.slow, self.n = None, True, False, 0
        self.head = {"started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now if now is not None else time.time())), "calls": total, "first": first}
        try:
            folder = os.path.join(out_dir, BATCH_DIR)
            os.makedirs(folder, exist_ok=True)
            self.path = batch_record_path(out_dir, now)
            batch_records_trim(folder, BATCH_KEEP - 1)
        except Exception:
            self.ok = False

    def write(self, body, final=False):
        if not self.ok or self.path is None:
            return
        self.n += 1
        if self.slow and not final and self.n % 5:
            return
        t0 = time.time()
        try:
            tmp = self.path + ".part"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({**self.head, **body}, f, ensure_ascii=False, default=str)
            os.replace(tmp, self.path)
        except Exception:
            self.ok = False
            return
        if time.time() - t0 > 0.05:
            self.slow = True


# The file's own note in a batch { to } reply.
TO_NOTE = ("Each call's whole answer is in the file (results[i].result; a call with a writeTo of its own: in that file, written here); "
           "here: ok, a refusal's words and the health verdict. record_read { path: the file, at: \"results.0.result\" } gives any part of it "
           "back (results count from this part's first call, i minus start).")


# The part of a health verdict that stands from call to call: the objects
# that were failing before the call (agentlink/health.py words it).
STANDING = re.compile(r"^\d+ objects? still failing from before this call: ")
STANDING_NOTE = ("A line's health leaves out the part \"… still failing from before this call: …\" when it is the same as in the "
                 "last line that gave it: it is said at the first call it shows in and again only when it changes "
                 "(\"as before\": nothing else was said). The file has every verdict whole.")


# Said once a conversation, not on every reply (agentlink/once.py).
from . import once as _once  # noqa: E402


def clock_start(prev, now=None):
    """When a batch's budget starts: the outer batch's start for a batch run
    inside a call of it (prev: the session's batch_now), else now. A batch
    that was answered already (its gui_input step's dialog held it, and
    this batch is the client's next call, run inside that dialog's loop) is
    no outer batch: this one has its own clock (live 84: "Stopped after
    80 s (budget 55 s)" for a call of 1 s, the dialog's whole life counted)."""
    now = time.time() if now is None else now
    if isinstance(prev, dict) and not prev.get("answered") and prev.get("t0"):
        return prev["t0"]
    return now

# A batch's calls run one after another, never at the same time: said once a
# conversation on the batch's answer (local-model runs, 23 Nov: a model
# took the calls of a batch to run in parallel).
ORDER_NOTE = "The calls ran one at a time, in order: each call saw what the calls before it made."

_once.register("batch", "order", ORDER_NOTE)
_once.register("batch", "toNote", TO_NOTE)
_once.register("batch", "note", TO_NOTE)
_once.register("batch", "healthNote", STANDING_NOTE)


def brief_verdicts(verdicts):
    """A run of health verdicts for a batch's compact lines: the standing
    part (STANDING) is kept where it first shows and where it changes, and
    left out where it repeats the last one given; the rest of each verdict
    is untouched. A verdict that was only the repeated part reads "as
    before". Returns (the verdicts, whether anything was left out); None
    stays None."""
    out, last, cut = [], None, False
    for v in verdicts:
        if not isinstance(v, str):
            out.append(v)
            continue
        parts = v.split("; ")
        standing = next((p for p in parts if STANDING.match(p)), None)
        if standing is None:
            out.append(v)
            continue
        if standing != last:
            last = standing
            out.append(v)
            continue
        rest = [p for p in parts if p is not standing]
        out.append("; ".join(rest) if rest else "as before")
        cut = True
    return out, cut


# A health verdict with nothing to act on: such a line is left out of a
# lines: "refused" reply.
CLEAN = re.compile(r"^(nothing red|as before|([^;]*: )?(\d+ parts? )?valid, closed, \d+ solids?( \(AllowCompound\))?|[^;]*: assembly solved|[^;]*: empty|[^;]*: fully constrained|CalculiX ran clean)$")


def clean_verdict(v):
    """Whether every part of a health verdict says all is well."""
    return v is None or all(CLEAN.match(p.strip()) for p in str(v).split("; "))


def to_reply(got, first, path, size, lines="all"):
    """A batch's answer as batch { to } gives it back once the whole of it
    is in the file at path: a line per call (ok, a refusal's words, the
    health verdict, a call's own file) and every other key of the answer
    as it is — the batch's own note among them. A batch that stopped
    before a heavy read or out of time says in its note how to go on
    (next, notRun, heavy): that note stays as note, and the file's is
    toNote beside it; with no note of the batch's own, note is the file's."""
    only, lines = lines, []
    for i, r in enumerate(got.get("results") or []):
        row = {"i": first + i, "tool": r.get("tool"), "ok": bool(r.get("ok"))}
        if r.get("undone"):
            row["undone"] = True
        if not r.get("ok"):
            e = r.get("error") or {}
            row["error"] = f"{e.get('code')}: {e.get('message')}" if isinstance(e, dict) else str(e)
        else:
            res = r.get("result")
            h = res.get("health") if isinstance(res, dict) else r.get("health")
            if isinstance(h, dict) and h.get("verdict"):
                row["health"] = h["verdict"]
            if isinstance(r.get("written"), dict):
                row["written"] = r["written"].get("path")
        lines.append(row)
    # A standing "still failing from before" part once, not on every line
    # (40 lines each repeated two objects' names, live).
    brief, cut = brief_verdicts([row.get("health") for row in lines])
    for row, v in zip(lines, brief):
        if v is not None:
            row["health"] = v
    counts = None
    if only in ("refused", "counts"):
        counts = {"ok": sum(1 for r in lines if r["ok"]), "refused": sum(1 for r in lines if not r["ok"])}
        # counts: no line at all (a run made for its files or pictures, read from the file afterwards)
        lines = [] if only == "counts" else [r for r in lines if not r["ok"] or not clean_verdict(r.get("health"))]
    short = {k: v for k, v in got.items() if k != "results"}
    short.update({"results": lines, "written": {"path": path, "bytes": size}})
    if counts is not None:
        short["counts"] = counts
    if cut:
        short["healthNote"] = STANDING_NOTE
    if isinstance(got.get("note"), str) and got["note"].strip():
        short["toNote"] = TO_NOTE
    else:
        short["note"] = TO_NOTE
    return short


def record_reply(got, first, record_path, from_file, lines):
    """What a batch without to answers once its record (record_path, None
    when it could not be written) holds the whole answer: a batch from a
    file, or one given lines, answers as batch { to } does from the record
    (a plain file batch's reply repeated every call's answer, 10-35 k
    characters, live); any other batch answers whole. The record's path is
    the reply's written, so record is not given twice."""
    if not isinstance(got, dict) or not (from_file or lines) or lines == "full" or not record_path or not os.path.isfile(record_path):
        return got
    short = to_reply(got, first, record_path, os.path.getsize(record_path), lines=lines or "all")
    short.pop("record", None)
    return short


def read_part(path, name, at=None):
    """record_read { path, at }: the part at the dotted path at of the JSON
    file at path (name: as the agent gave it) — a batch's record or a writeTo file, so an
    answer a reply left out can be read back. Raises chain.Miss in a
    refusal's words."""
    from . import chain

    try:
        value = chain.at(chain.read_json(path, name), at, name)
    except chain.Miss as e:
        raise chain.Miss(e.code, e.message.replace(chain.FILE + ": ", "path: ", 1).replace(chain.AT + " ", "at ", 1)) from None
    return {"path": path, "at": at or "", "value": value}
