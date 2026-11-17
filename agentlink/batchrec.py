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
TO_NOTE = ("Each call's whole answer is in the file (results[i].result; a call with a to of its own: in that file, written here); "
           "here: ok, a refusal's words and the health verdict.")


# The part of a health verdict that stands from call to call: the objects
# that were failing before the call (agentlink/health.py words it).
STANDING = re.compile(r"^\d+ objects? still failing from before this call: ")
STANDING_NOTE = ("A line's health leaves out the part \"… still failing from before this call: …\" when it is the same as in the "
                 "last line that gave it: it is said at the first call it shows in and again only when it changes "
                 "(\"as before\": nothing else was said). The file has every verdict whole.")


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
CLEAN = re.compile(r"^(nothing red|as before|([^;]*: )?(\d+ parts? )?valid, closed, \d+ solids?( \(AllowCompound\))?|[^;]*: assembly solved|[^;]*: empty)$")


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
    if only == "refused":
        counts = {"ok": sum(1 for r in lines if r["ok"]), "refused": sum(1 for r in lines if not r["ok"])}
        lines = [r for r in lines if not r["ok"] or not clean_verdict(r.get("health"))]
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
