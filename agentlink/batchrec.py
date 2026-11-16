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
