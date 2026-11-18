# SPDX-License-Identifier: LGPL-2.1-or-later
# What working through Agent Link costs the agent, measured on this side: the
# size of every call's arguments and answer, the pictures sent, and the tool
# list each session loads up front. Agent Link cannot see what Claude counts,
# so these are estimates — text at about 3.5 characters a token (JSON with
# numbers runs denser than prose), a picture at width × height / 750 tokens,
# as Anthropic's vision guide gives it — good for seeing where the cost goes
# and whether a change made it smaller, not for billing.
#
# Kept a line per call in ~/AgentLink/usage/<day>.jsonl, by whichever FreeCAD
# ran the call (the window, or the hidden one when the window is not there),
# so nothing is counted twice.

import json
import os
import struct
import threading
import time

CHARS_PER_TOKEN = 3.5
DAYS_KEPT = 60


def est_tokens(chars):
    return int(round(chars / CHARS_PER_TOKEN))


def png_tokens(data):
    """Tokens a PNG costs as an image block: width × height / 750, after the
    long side is held to 1568 px as Claude resizes it."""
    try:
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            return 0
        w, h = struct.unpack(">II", data[16:24])
    except Exception:
        return 0
    long_side = max(w, h)
    if long_side > 1568:
        f = 1568 / long_side
        w, h = int(w * f), int(h * f)
    return int(round(w * h / 750))


def folder():
    return os.path.join(os.path.expanduser("~"), "AgentLink", "usage")


# ---- the usage log (docs/design/usage-log-2026-11-18.md) ---------------------
#
# Each call's row also holds: the job it is in (job, step n), the gap since
# the call before, its group, the answer's bytes and estimated tokens, the
# pictures (count, bytes), a refusal's or error's reason, and marks: a retry,
# a tool search and its hits, a group switch, an undo or a rollback, a
# background handoff. A job row starts each job (versions, window or
# headless). A dialog row ends each dialog. Never the arguments' values,
# never file contents or geometry: words pass clean() first.

JOB_GAP = 600.0  # s: a call after a pause this long starts a new job
RETRY_S = 120.0  # s: the same tool again within this, with changed arguments, is a retry
WORDS_MAX = 160
UNDO_KINDS = ("undo", "redo", "restore")  # history_<kind>: the hub's undo and redo, and an add-on's checkpoint restore
FIND_TOOLS = ("tool_find", "tool_groups")
MAX_DAY_BYTES = 20 * 1024 * 1024  # a day's file stops growing past this (a run gone wild)

_HOME = os.path.expanduser("~")


def clean(text, n=WORDS_MAX):
    """Words safe for the log: a path under the user folder shortened to ~,
    any other absolute path replaced by <path>, cut to n characters."""
    import re

    t = str(text or "")
    if _HOME and len(_HOME) > 1:
        t = t.replace(_HOME, "~")
    t = re.sub(r"(?<![~\w.])(/[^\s\"'`,;:)\]}]+){2,}", "<path>", t)
    t = re.sub(r"\b[A-Za-z]:\\[^\s\"']+", "<path>", t)
    return t[:n]


def _arg_sig(args):
    """A hash of the arguments, kept in memory only: it tells a retry with
    changed arguments. Never written."""
    try:
        return hash(json.dumps(args, sort_keys=True, default=str))
    except Exception:  # noqa: BLE001
        return 0


def _versions(server_version=None):
    out = {"agentlink": server_version}
    try:
        import FreeCAD

        out["freecad"] = ".".join(str(x) for x in FreeCAD.Version()[:3])
    except Exception:  # noqa: BLE001
        out["freecad"] = None
    out["addons"] = _addons()
    try:
        from . import ext

        if ext.loaded:
            out["extensions"] = {k: str(v) for k, v in sorted(ext.loaded.items())}
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import extstate

        out["loaded"] = sorted(extstate.short_name(r["extension"]) for r in extstate.state().get("loaded", []))
    except Exception:  # noqa: BLE001
        pass
    bundle = os.path.basename(os.path.dirname(_here()))
    if bundle.startswith("addons-"):
        out["bundle"] = bundle[7:]  # the launcher's install: each add-on's pinned commit, 7 characters each
    return out


def _here():
    """This add-on's folder (Mod/AgentLink, or the launcher's copy)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git_commit(folder):
    """The short commit of a git checkout at folder, read from .git (no git
    run), or None."""
    g = os.path.join(folder, ".git")
    try:
        if os.path.isfile(g):
            with open(g, encoding="utf-8") as f:
                line = f.read().strip()
            if not line.startswith("gitdir:"):
                return None
            g = os.path.join(folder, line[7:].strip())
        if not os.path.isdir(g):
            return None
        with open(os.path.join(g, "HEAD"), encoding="utf-8") as f:
            head = f.read().strip()
        if not head.startswith("ref:"):
            return head[:7]
        ref = head[4:].strip()
        p = os.path.join(g, ref)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return f.read().strip()[:7]
        with open(os.path.join(g, "packed-refs"), encoding="utf-8") as f:
            for line in f:
                if line.rstrip().endswith(" " + ref):
                    return line[:7]
    except OSError:
        return None
    return None


_ADDONS = {}


def _addons():
    """Every add-on beside this one in the Mod folder that has a
    package.xml: {folder: {version, date, commit}}. Read once a process."""
    if "v" in _ADDONS:
        return _ADDONS["v"]
    import re

    out = {}
    mod = os.path.dirname(_here())
    try:
        names = sorted(os.listdir(mod))
    except OSError:
        names = []
    for n in names:
        p = os.path.join(mod, n)
        x = os.path.join(p, "package.xml")
        if not os.path.isfile(x):
            continue
        try:
            with open(x, encoding="utf-8") as f:
                text = f.read(20000)
        except OSError:
            continue
        row = {}
        for k in ("version", "date"):
            m = re.search(rf"<{k}>([^<]+)</{k}>", text)
            if m:
                row[k] = m.group(1).strip()[:40]
        c = _git_commit(p)
        if c:
            row["commit"] = c
        out[n[:60]] = row
        if len(out) >= 40:
            break
    _ADDONS["v"] = out
    return out


def _mode():
    try:
        import FreeCAD

        return "window" if getattr(FreeCAD, "GuiUp", False) else "headless"
    except Exception:  # noqa: BLE001
        return "headless"


def _json_of(text):
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _error_of(text):
    d = _json_of(text)
    e = d.get("error") if d else None
    return clean(e.get("message")) if isinstance(e, dict) else None


def marks(tool, args, reply_text, error):
    """The marks of one call, read from its name, its arguments' keys and
    flags, and its answer: {find, groups, undo, rollback, background, batch
    steps}. Argument values are never kept, but a search's words (cleaned)
    and tool names."""
    out = {}
    args = args if isinstance(args, dict) else {}
    if tool in FIND_TOOLS:
        q = args.get("find") if tool == "tool_groups" else (args.get("queries") or args.get("words"))
        if q:
            got = _json_of(reply_text) or {}
            hits = []
            for part in (got.get("results") or [got]):
                hits += [h.get("tool") for h in (part.get("tools") or []) if isinstance(h, dict) and h.get("tool")]
            words = q if isinstance(q, list) else [q]
            out["find"] = {"words": [clean(w, 60) for w in words[:6]], "hits": hits[:20]}
        sw = {k: [str(g) for g in args[k]][:20] for k in ("enable", "disable") if tool == "tool_groups" and isinstance(args.get(k), list)}
        if sw:
            out["groups"] = sw
    if tool.startswith("history_") and tool[8:] in UNDO_KINDS and not error:
        out["undo"] = tool[8:]
    if tool == "batch":
        calls = args.get("calls") if isinstance(args.get("calls"), list) else []
        out["steps"] = [str(c.get("tool")) for c in calls[:40] if isinstance(c, dict)]
        if len(calls) > 40:
            out["moreSteps"] = len(calls) - 40
        got = _json_of(reply_text) or {}
        if "undone" in got:
            out["rollback"] = got.get("undone")
    got = None
    if not error and ('"job"' in reply_text[:400]):
        got = _json_of(reply_text) or {}
        if got.get("job") and got.get("status") in ("running", "queued"):
            out["background"] = str(got["job"])[:40]
    if args.get("background") in (True, "true") and "background" not in out:
        out["background"] = True
    return out


class Meter:
    """Counts a server's calls and lists, this session and on disk."""

    def __init__(self, where=None, session_id=None, write=True, version=None):
        self.where = where or folder()
        self.session_id = session_id or time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
        self.write = write
        self.lock = threading.Lock()
        self.calls = []
        self.listed = None
        self.version = version
        # The job now: its id, number, steps so far; the last call's end, tool and argument hash.
        self.job = None
        self.job_n = 0
        self.step = 0
        self.batch_n = 0
        self.last = None  # (end time, tool, arg hash)
        self.prev = None  # the same, for the last call that is not a batch's own row (retries)
        self.dialog = None  # the dialog up now: {key, title, text, buttons, since, blocked, by}
        if write:
            prune(self.where)

    def _append(self, row):
        if not self.write:
            return
        try:
            os.makedirs(self.where, exist_ok=True)
            p = os.path.join(self.where, time.strftime("%Y-%m-%d") + ".jsonl")
            if os.path.exists(p) and os.path.getsize(p) > MAX_DAY_BYTES:
                return
            with open(p, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
        except OSError:
            pass

    def list(self, tools, instructions=""):
        """tools/list answered: the up-front cost of every listed definition."""
        chars = len(json.dumps(tools, separators=(",", ":"), ensure_ascii=False)) + len(instructions or "")
        self.listed = {"tools": len(tools), "chars": chars, "tokens": est_tokens(chars)}
        self._append({"t": round(time.time(), 1), "s": self.session_id, "kind": "list", **self.listed})

    def new_job(self, why="start", now=None):
        """Start a job: at the session's start, on initialize (a new
        conversation), or on the first call after a pause of JOB_GAP s.
        Writes a job row with the versions and window or headless."""
        now = time.time() if now is None else now
        with self.lock:
            self.job_n += 1
            self.job = f"{self.session_id}-j{self.job_n}"
            self.step = 0
            self.batch_n = 0
        self._append({"t": round(now, 1), "s": self.session_id, "kind": "job", "job": self.job, "why": why, "mode": _mode(), **_versions(self.version)})
        return self.job

    def call(self, tool, args_text, reply_text, image=None, error=None, ms=0, args=None, group=None, images=None):
        now = time.time()
        start = now - (ms or 0) / 1000.0
        last = self.last
        if self.job is None:
            self.new_job("start", start)
        elif last is not None and start - last[0] > JOB_GAP:
            self.new_job("pause", start)
        # images: [(the picture's first bytes, its size in bytes)], every picture of the answer.
        pics = list(images) if images else ([(image, len(image))] if image else [])
        img = sum(png_tokens(h) for h, _n in pics if h)
        sig = _arg_sig(args) if args is not None else None
        with self.lock:
            self.step += 1
            row = {"t": round(now, 1), "s": self.session_id, "kind": "call", "tool": tool, "job": self.job, "n": self.step, "in": len(args_text), "out": len(reply_text),
                   "bytes": len(reply_text.encode("utf-8", "replace")), "tok": est_tokens(len(reply_text)), "img": img, "ms": int(ms)}
            if group:
                row["grp"] = group
            if pics:
                row["imgs"] = len(pics)
                row["imgBytes"] = sum(int(n or 0) for _h, n in pics)
            if last is not None:
                row["gap"] = int(max(0.0, start - last[0]) * 1000)
            if error:
                row["err"] = error
                why = _error_of(reply_text)
                if why:
                    row["why"] = why
            # A retry: the same tool as the call before, with changed arguments, soon. A batch's own row does not
            # count as the call before: its calls are rows of their own, written before it (live 73: object_get
            # refused in one batch, then object_get again in the next was not marked).
            prev = self.prev
            if prev is not None and prev[1] == tool and sig is not None and prev[2] != sig and start - prev[0] <= RETRY_S:
                row["retry"] = True
            try:
                m = marks(tool, args or {}, reply_text, error)
            except Exception:  # noqa: BLE001 - the marks only
                m = {}
            if m.get("steps") is not None:
                self.batch_n += 1
                m["batch"] = f"{self.job}-b{self.batch_n}"
            row.update(m)
            if tool == "dialog_answer" and not error and self.dialog is not None:
                self.dialog["by"] = "agent"
            self.last = (now, tool, sig)
            if tool != "batch":
                self.prev = (now, tool, sig)
            self.calls.append(row)
            del self.calls[:-5000]
        self._append(row)

    # ---- dialogs (the window's heartbeat tells each one) ----

    def dialog_seen(self, d, now=None):
        """The heartbeat's dialog in front (gui_link.modal_info), or None
        when none is. A dialog that goes is written as a dialog row: title,
        text and buttons (cleaned), who answered (agentlink, agent or
        person), the seconds it held the window, and the calls it blocked."""
        now = time.time() if now is None else now
        if d:
            key = (d.get("class"), d.get("title"), d.get("text"))
            if self.dialog is not None and self.dialog["key"] == key:
                return
            self._dialog_end(now)
            self.dialog = {"key": key, "title": clean(d.get("title"), 80), "text": clean(d.get("text")), "buttons": [clean(b, 30) for b in (d.get("buttons") or [])][:8],
                           "since": float(d.get("since") or now), "blocked": 0, "by": None}
        else:
            self._dialog_end(now)

    def dialog_pressed(self, by="agentlink"):
        """Agent Link (its dialog rule) or the supervisor pressed a button of the dialog up now."""
        if self.dialog is not None and self.dialog["by"] is None:
            self.dialog["by"] = by

    def _dialog_end(self, now):
        d, self.dialog = self.dialog, None
        if d is None:
            return
        if d["by"] is None and _supervisor_pressed(d["key"][1], d["since"]):
            d["by"] = "agentlink"
        row = {"t": round(now, 1), "s": self.session_id, "kind": "dialog", "job": self.job, "title": d["title"], "text": d["text"], "buttons": d["buttons"],
               "by": d["by"] or "person", "secs": round(max(0.0, now - d["since"]), 1), "blocked": d["blocked"]}
        with self.lock:
            self.calls.append(row)
        self._append(row)

    def refused(self, tool, args_text, reply_text, code=None):
        """A call the window answered with a refusal of its own, before the
        call ran (a dialog holding the window, the agent's document closed
        or not in front): counted as a call that erred, as the agent saw it.
        A refusal while a dialog is up counts as a call that dialog blocked."""
        if self.dialog is not None:
            self.dialog["blocked"] += 1
        self.call(tool, args_text, reply_text, None, code or "error", 0)

    def amend(self, tool, code="busy"):
        """The last call of tool, counted as answered, was answered to the
        agent with an error after all (the window wrote "busy" while the
        call was still running): counted as erred. Kept on disk as a line
        of its own (kind "amend"). False when there was none to amend."""
        with self.lock:
            row = next((r for r in reversed(self.calls) if r.get("tool") == tool), None)
            if row is None or row.get("err"):
                return False
            row["err"] = code
            if self.dialog is not None:
                self.dialog["blocked"] += 1
        self._append({"t": round(time.time(), 1), "s": self.session_id, "kind": "amend", "tool": tool, "err": code})
        return True

    def session_totals(self):
        with self.lock:
            rows = list(self.calls)
        return totals(rows, self.listed)


def err_code(result):
    """The error code of a tools/call result ({"content": […], "isError"}),
    or None when it is not an error. An error whose text cannot be read
    still counts (code "error"): the meter once read the whole answer's
    texts joined as one JSON, so an error answer with a second text part
    was not counted at all."""
    if not isinstance(result, dict) or not result.get("isError"):
        return None
    try:
        content = result.get("content") or []
        first = next((c.get("text", "") for c in content if c.get("type") == "text"), "")
        err = json.loads(first).get("error")
        code = err.get("code") if isinstance(err, dict) else None
        return str(code) if code else "error"
    except Exception:  # noqa: BLE001 - an error all the same
        return "error"


def _supervisor_pressed(title, since):
    """Whether the supervisor (another process) logged a press on a dialog
    of this title since it came up: read from the end of watchdog.log."""
    try:
        from . import keep

        p = keep.path("watchdog.log")
        with open(p, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 16384))
            tail = f.read().decode("utf-8", "replace").splitlines()
    except Exception:  # noqa: BLE001
        return False
    for line in tail:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("event") == "dialog" and e.get("by") == "supervisor" and e.get("pressed") and e.get("title") == title and float(e.get("t", 0)) >= since - 1:
            return True
    return False


def prune(where=None):
    """Rotation: a day's file older than DAYS_KEPT days is removed."""
    where = where or folder()
    now = time.time()
    try:
        names = os.listdir(where)
    except OSError:
        return
    for n in names:
        if not n.endswith(".jsonl"):
            continue
        try:
            day = time.mktime(time.strptime(n[:-6], "%Y-%m-%d"))
        except ValueError:
            continue
        if now - day > DAYS_KEPT * 86400:
            try:
                os.remove(os.path.join(where, n))
            except OSError:
                pass


def tokens_of(row):
    return est_tokens(row.get("in", 0)) + est_tokens(row.get("out", 0)) + row.get("img", 0)


def totals(rows, listed=None):
    calls = [r for r in rows if r.get("kind", "call") == "call"]
    by = {}
    for r in calls:
        b = by.setdefault(r["tool"], {"tool": r["tool"], "calls": 0, "tokens": 0, "imageTokens": 0, "errors": 0, "ms": 0, "inChars": 0, "outChars": 0, "maxOut": 0})
        b["calls"] += 1
        b["inChars"] += r.get("in", 0)
        b["outChars"] += r.get("out", 0)
        b["maxOut"] = max(b["maxOut"], r.get("out", 0))
        b["tokens"] += tokens_of(r)
        b["imageTokens"] += r.get("img", 0)
        b["errors"] += 1 if r.get("err") else 0
        b["ms"] += r.get("ms", 0)
    out = {"calls": len(calls), "tokens": sum(b["tokens"] for b in by.values()), "imageTokens": sum(b["imageTokens"] for b in by.values()),
           "errors": sum(b["errors"] for b in by.values()), "byTool": sorted(by.values(), key=lambda b: -b["tokens"])}
    if listed:
        out["toolList"] = listed
    return out


def read_days(days=7, where=None):
    where = where or folder()
    rows = []
    now = time.time()
    if not os.path.isdir(where):
        return rows
    for n in sorted(os.listdir(where)):
        if not n.endswith(".jsonl"):
            continue
        p = os.path.join(where, n)
        try:
            day = time.mktime(time.strptime(n[:-6], "%Y-%m-%d"))
        except ValueError:
            continue
        if now - day > DAYS_KEPT * 86400:
            try:
                os.remove(p)
            except OSError:
                pass
            continue
        if now - day > days * 86400 + 86400:
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if now - r.get("t", 0) <= days * 86400:
                    rows.append(r)
    return rows


def report(days=7, where=None, top=12):
    """Calls and estimated tokens over the last days: per day, per session
    (with its tool list's cost), and the tools that cost the most."""
    rows = read_days(days, where)
    calls = [r for r in rows if r.get("kind") == "call"]
    lists = [r for r in rows if r.get("kind") == "list"]
    amended = len([r for r in rows if r.get("kind") == "amend"])
    sessions = {}
    for r in lists:
        sessions.setdefault(r["s"], {"session": r["s"], "listed": r["tools"], "listTokens": r["tokens"], "calls": 0, "tokens": 0})
    for r in calls:
        s = sessions.setdefault(r["s"], {"session": r["s"], "listed": None, "listTokens": 0, "calls": 0, "tokens": 0})
        s["calls"] += 1
        s["tokens"] += tokens_of(r)
    per_day = {}
    for r in calls:
        d = time.strftime("%Y-%m-%d", time.localtime(r["t"]))
        x = per_day.setdefault(d, {"day": d, "calls": 0, "tokens": 0})
        x["calls"] += 1
        x["tokens"] += tokens_of(r)
    t = totals(calls)
    list_tok = sum(s["listTokens"] for s in sessions.values())
    out = {"days": days, "calls": t["calls"], "tokens": t["tokens"] + list_tok, "callTokens": t["tokens"], "toolListTokens": list_tok,
           "imageTokens": t["imageTokens"], "errors": t["errors"] + amended, "perDay": sorted(per_day.values(), key=lambda x: x["day"]),
           "sessions": len(sessions), "topTools": t["byTool"][:top],
           "note": "Estimates from what passed through Agent Link (text at ~3.5 characters a token, pictures at width × height / 750): where the cost goes, not Claude's own count. The tool list is paid at each session's start; your plan's usage page has the real totals."}
    tips = []
    if out["tokens"] and list_tok > 0.3 * out["tokens"]:
        tips.append("The tool list is over a third of it: fewer groups listed (tool_groups disable) cuts every session's start.")
    if t["tokens"] and t["imageTokens"] > 0.4 * t["tokens"]:
        tips.append("Pictures are over 40 %: smaller ones (view_snapshot width) or inline: false where a file will do.")
    big = [b for b in t["byTool"] if b["calls"] and b["tokens"] / b["calls"] > 4000]
    if big:
        tips.append("Large answers: " + ", ".join(f"{b['tool']} (~{b['tokens'] // b['calls']} a call)" for b in big[:4]) + " — ask for less (detail: false, a filter, a range).")
    if tips:
        out["tips"] = tips
    return out


# ---- the usage log's report (usage_report { log: true }) --------------------

def _watchdog_counts(days):
    """Events of the supervisor's watchdog log (keep.path("watchdog.log"))
    over the days, counted by event: hangs, force restarts, dialogs
    pressed and the like. Read only."""
    out = {}
    try:
        from . import keep

        p = keep.path("watchdog.log")
        if not os.path.isfile(p):
            return out
        since = time.time() - days * 86400
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if float(e.get("t", 0)) >= since:
                    k = str(e.get("event"))
                    out[k] = out.get(k, 0) + 1
    except Exception:  # noqa: BLE001
        pass
    return out


def _runs(names, cap=30):
    """['a', 'a', 'b'] -> ['a×2', 'b'], at most cap items."""
    out = []
    for n in names:
        if out and out[-1][0] == n:
            out[-1][1] += 1
        else:
            out.append([n, 1])
    words = [f"{n}×{k}" if k > 1 else n for n, k in out]
    return words[:cap] + ([f"… {len(words) - cap} more"] if len(words) > cap else [])


def _pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def log_report(days=7, where=None, jobs=8, watchdog=True):
    """The usage log, summed for the agent on request: jobs and their steps,
    refusals and errors per tool with their reasons, retries, tool searches
    and whether a hit was used, group switches, undos and rollbacks,
    background handoffs, watchdog events, dialogs, gaps between calls,
    answer sizes and pictures. Never file contents or arguments."""
    rows = read_days(days, where)
    calls = [r for r in rows if r.get("kind") == "call"]
    job_rows = {r["job"]: r for r in rows if r.get("kind") == "job" and r.get("job")}
    by_job = {}
    for r in calls:
        by_job.setdefault(r.get("job") or r.get("s"), []).append(r)
    # Refusals and errors per tool, with their reasons.
    errs = {}
    for r in calls:
        if r.get("err"):
            e = errs.setdefault(r["tool"], {"tool": r["tool"], "count": 0, "codes": {}, "reasons": {}})
            e["count"] += 1
            e["codes"][r["err"]] = e["codes"].get(r["err"], 0) + 1
            if r.get("why"):
                w = r["why"][:100]
                e["reasons"][w] = e["reasons"].get(w, 0) + 1
    for e in errs.values():
        e["reasons"] = [{"why": w, "count": n} for w, n in sorted(e["reasons"].items(), key=lambda x: -x[1])[:3]]
    # Retries.
    retries = [r for r in calls if r.get("retry")]
    # Tool searches, and whether a hit was then called in the same job (alone or in a batch).
    finds = {"searches": 0, "used": 0, "unused": []}
    for job, rs in by_job.items():
        for i, r in enumerate(rs):
            f = r.get("find")
            if not f:
                continue
            finds["searches"] += 1
            hits = set(f.get("hits") or ())
            later = set()
            for x in rs[i + 1:]:
                later.add(x["tool"])
                later.update(x.get("steps") or ())
            if hits & later:
                finds["used"] += 1
            elif len(finds["unused"]) < 5:
                finds["unused"].append({"words": f.get("words"), "hits": (f.get("hits") or [])[:3]})
    if finds["searches"]:
        finds["usedRate"] = round(finds["used"] / finds["searches"], 2)
    # Group switches: tool_groups enable / disable, and a call in another group than the call before.
    switches = {"enableDisable": len([r for r in calls if r.get("groups")]), "groupChanges": 0}
    for rs in by_job.values():
        g = [r.get("grp") for r in rs if r.get("grp")]
        switches["groupChanges"] += sum(1 for a, b in zip(g, g[1:]) if a != b)
    undos = {}
    for r in calls:
        if r.get("undo"):
            undos[r["undo"]] = undos.get(r["undo"], 0) + 1
    rollbacks = [r for r in calls if "rollback" in r]
    bg = {}
    for r in calls:
        if r.get("background"):
            bg[r["tool"]] = bg.get(r["tool"], 0) + 1
    dialogs = [r for r in rows if r.get("kind") == "dialog"]
    dsum = {"count": len(dialogs)}
    if dialogs:
        by = {}
        for d in dialogs:
            by[d.get("by", "person")] = by.get(d.get("by", "person"), 0) + 1
        dsum.update({"answeredBy": by, "secsBlocked": round(sum(d.get("secs", 0) for d in dialogs), 1), "longestSecs": max(d.get("secs", 0) for d in dialogs),
                     "callsBlocked": sum(d.get("blocked", 0) for d in dialogs),
                     "last": [{k: d.get(k) for k in ("title", "text", "buttons", "by", "secs", "blocked")} for d in dialogs[-3:]]})
    gaps = [r["gap"] for r in calls if r.get("gap") is not None]
    pics = [r for r in calls if r.get("imgs")]
    big = {}
    for r in calls:
        b = big.setdefault(r["tool"], 0)
        big[r["tool"]] = max(b, r.get("bytes", r.get("out", 0)))
    jl = []
    for job in list(by_job)[-jobs:]:
        rs = by_job[job]
        j = job_rows.get(job, {})
        names = []
        for r in rs:
            names.append(r["tool"] if not r.get("steps") else f"{r['tool']}[{', '.join(_runs(r['steps'], 8))}]")
        jl.append({"job": job, "mode": j.get("mode"), "why": j.get("why"), "versions": {k: j.get(k) for k in ("agentlink", "freecad", "addons", "bundle", "loaded") if j.get(k) is not None},
                   "steps": len(rs) + sum(len(r.get("steps") or ()) for r in rs), "calls": len(rs), "errors": len([r for r in rs if r.get("err")]),
                   "retries": len([r for r in rs if r.get("retry")]), "secs": round(rs[-1]["t"] - rs[0]["t"] + rs[0].get("ms", 0) / 1000, 1),
                   "tokens": sum(tokens_of(r) for r in rs), "sequence": _runs(names)})
    out = {"days": days, "calls": len(calls), "jobs": len(by_job), "modes": {}, "versions": sorted({json.dumps({k: j.get(k) for k in ("agentlink", "freecad", "addons")}, sort_keys=True) for j in job_rows.values()})[-3:],
           "errorsByTool": sorted(errs.values(), key=lambda e: -e["count"])[:10],
           "retries": {"count": len(retries), "afterError": 0, "tools": sorted({r["tool"] for r in retries})[:10]},
           "toolFind": finds, "groupSwitches": switches, "undos": undos,
           "rollbacks": {"count": len(rollbacks), "stepsUndone": sum(int(r.get("rollback") or 0) for r in rollbacks)},
           "background": {"handoffs": sum(bg.values()), "tools": bg}, "dialogs": dsum,
           "gapMs": {"median": _pct(gaps, 0.5), "p90": _pct(gaps, 0.9), "max": max(gaps) if gaps else None},
           "answers": {"bytes": sum(r.get("bytes", r.get("out", 0)) for r in calls), "tokens": sum(r.get("tok", est_tokens(r.get("out", 0))) for r in calls),
                       "largestByTool": dict(sorted(big.items(), key=lambda x: -x[1])[:5])},
           "pictures": {"count": sum(r["imgs"] for r in pics), "bytes": sum(r.get("imgBytes", 0) for r in pics), "tokens": sum(r.get("img", 0) for r in pics)},
           "lastJobs": jl,
           "note": "From the usage log on this side (~/AgentLink/usage). No file contents, arguments or geometry are kept. Tokens are estimates."}
    out["versions"] = [json.loads(v) for v in out["versions"]]
    for j in job_rows.values():
        out["modes"][j.get("mode") or "?"] = out["modes"].get(j.get("mode") or "?", 0) + 1
    # A retry after an error: the call before it (same job, same tool) erred.
    for rs in by_job.values():
        rs = [r for r in rs if r["tool"] != "batch"]
        for a, b in zip(rs, rs[1:]):
            if b.get("retry") and a.get("err"):
                out["retries"]["afterError"] += 1
    if watchdog:
        out["watchdog"] = _watchdog_counts(days)
    return out


# ---- the panel's usage strip ------------------------------------------------

def _k(n):
    return f"{n / 1000:.1f}k" if n < 1_000_000 else f"{n / 1_000_000:.2f}M"


# Said on the strip itself: the figures are Agent Link's own estimate.
NOT_BILLING = "estimate, not billing"


def strip(r):
    """'Today ~41.2k · week ~310.5k tokens (estimate, not billing)' from
    usage.report."""
    import time

    today = time.strftime("%Y-%m-%d")
    t = sum(d["tokens"] for d in r.get("perDay", []) if d["day"] == today)
    return f"Today ~{_k(t)} · week ~{_k(r.get('tokens', 0))} tokens ({NOT_BILLING})"


def text(r):
    if r.get("error"):
        return f"No usage to show: {r['error']}"
    lines = ["Estimates made by Agent Link, not billing: your plan's usage page has the real totals.", ""]
    lines += [f"Last {r['days']} days: {r['calls']} calls, ~{_k(r['tokens'])} tokens (tool lists ~{_k(r['toolListTokens'])}, pictures ~{_k(r['imageTokens'])}).", ""]
    lines += [f"{d['day']}: {d['calls']} calls, ~{_k(d['tokens'])}" for d in r.get("perDay", [])[-7:]]
    lines += ["", "Most costly tools:"] + [f"  {b['tool']}: {b['calls']} calls, ~{_k(b['tokens'])}" for b in r.get("topTools", [])[:8]]
    lines += [""] + r.get("tips", []) + ["", r.get("note", "")]
    return "\n".join(lines)
