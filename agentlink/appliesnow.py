# SPDX-License-Identifier: LGPL-2.1-or-later
"""Which tools apply to the document as it is now: the live filter after a
changing call, and the meter that measures how right it was.

The reading of one tool is agentlink/needs.py's: the tool's own leading
checks, evaluated dry. Here that reading is taken for a small set of tools
after each changing call, within a time budget, and said as one short line
beside the health's "next":

    "appliesNow": { "groups": { "sketch": 14, "feature": 9 }, "not": 6,
                    "notChecked": 11, "ms": 40 }

group names and counts, never a tool's text. groups: the tools whose
leading checks all pass, by group; not: those one of whose checks refuses
now; notChecked: those that could not be told (most need the call's
arguments); partial: the tools the budget ran out before. The line is said
when it is not what was last said (as "next" is), and never inside a batch
(the batch's own answer carries it once). tool_groups { now: true } gives
the same reading in full; tool_groups { needs: tool, arguments } one tool
with its arguments.

Advice only: nothing is hidden, blocked or taken off tools/list.

Which tools (chosen()): those the tool index (agentlink/toolindex.py) puts
in the active workbench; then in the workbenches the index links to it —
one whose FreeCAD commands the active workbench's tools also do the work
of, or the other way round (Sketcher and Part Design); then in the
workbenches of the document's own objects. At most MAX_SET tools, in that
order. With no window it is the document's workbenches alone. A tool the
index gives no workbench (the document, view and hub tools) is not in the
pushed set; an add-on's tools are in it through what the add-on declared.

Preferences (Mod/AgentLink): AppliesNow (bool, on) switches the pushed line
off; AppliesNowBudget (ms, 150). AGENTLINK_APPLIES=off does the same for
the process.

The meter (Meter): for every call, what the last reading said of the tool
(applies, not, notChecked, or notEvaluated) and what happened (answered;
refused by a leading check, by a later check, or otherwise). Its counts are
kept per session and written to applies_meter.json in the session's
folder. The number to watch is notThenAnswered: calls the filter marked
"not" that then answered — a reading that was wrong. It must stay near
zero.
"""
import json
import os
import time

from . import needs, runners, toolindex

BUDGET_MS = 150
NOW_BUDGET_MS = 600   # tool_groups { now: true }: the same set, read on request
MAX_SET = 150
ONE_S = 0.05          # one tool's reading inside the pushed filter
AGAIN_S = 0.15        # a refused call read again for the meter (which check refused): no longer than this between steps
SLOW_MS = 40          # a reading this long is not taken again in the pushed filter (one helper cannot be stopped half-way)
CAP = 20              # names per class in the full reading
NOT_CAP = 6           # tools that would refuse, each with its refusal's code and first words
FILE = "applies_meter.json"
SESSIONS_KEPT = 20
PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"


def _pref(kind, name, default):
    try:
        import FreeCAD

        g = FreeCAD.ParamGet(PREFS)
        return g.GetBool(name, default) if kind == "bool" else g.GetInt(name, default)
    except Exception:  # noqa: BLE001 - no FreeCAD here, or a stand-in without settings
        return default


def enabled():
    """Whether the line is pushed after a changing call."""
    if os.environ.get("AGENTLINK_APPLIES", "on") in ("0", "false", "off"):
        return False
    return bool(_pref("bool", "AppliesNow", True))


def budget_ms():
    try:
        return max(10, min(2000, int(_pref("int", "AppliesNowBudget", BUDGET_MS))))
    except (TypeError, ValueError):
        return BUDGET_MS


# ---- which tools ------------------------------------------------------------------------------

def links(entries):
    """{workbench: [workbenches the index links to it]} from the tools'
    own entries ({tool: {workbench, commands}}): a command family
    ("Sketcher" of Sketcher_NewSketch) belongs to the workbench most of
    whose tools do its commands; two workbenches are linked when a tool of
    one does a command of the other's family."""
    count = {}
    for e in entries.values():
        wb = e.get("workbench")
        for c in e.get("commands") or ():
            fam = str(c).split("_")[0]
            if wb and fam != "Std":
                count.setdefault(fam, {})
                count[fam][wb] = count[fam].get(wb, 0) + 1
    home = {fam: sorted(by.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for fam, by in count.items()}
    out = {}
    for e in entries.values():
        wb = e.get("workbench")
        for c in e.get("commands") or ():
            other = home.get(str(c).split("_")[0])
            if wb and other and other != wb:
                out.setdefault(wb, set()).add(other)
                out.setdefault(other, set()).add(wb)
    return {k: sorted(v) for k, v in out.items()}


def _index(server):
    """(tools by workbench, links) for a server's tools, kept until its tools change."""
    key = (len(server.tools), len(toolindex.EXTRA))
    got = getattr(server, "_applies_index", None)
    if got is None or got[0] != key:
        entries = {t.name: toolindex.entry(t.name) for t in server.tools.values() if not getattr(t, "alias_of", None)}
        by = {}
        for name, e in entries.items():
            if e.get("workbench"):
                by.setdefault(e["workbench"], []).append(name)
        got = server._applies_index = (key, by, links(entries))
    return got[1], got[2]


def chosen(server, state):
    """(tool names in order, how they were chosen) for a window state
    (tools.now_state()'s): the module's docstring has the rule."""
    by, linked = _index(server)
    active = state.get("workbench") if state.get("window") else None
    benches, how = [], {}
    if active and active in by:
        benches.append(active)
        how["workbench"] = active
    if state.get("editing") == "sketch" and "SketcherWorkbench" not in benches:
        benches.append("SketcherWorkbench")
        how["editing"] = "sketch"
    link = [w for w in linked.get(active, ()) if w in by and w not in benches] if active else []
    if link:
        benches += link
        how["linked"] = link
    doc = sorted(w for w in (state.get("docBenches") or ()) if w in by and w not in benches)
    if doc:
        benches += doc
        how["document"] = doc
    names = [n for w in benches for n in sorted(by[w])]
    if len(names) > MAX_SET:
        how["cut"] = len(names) - MAX_SET
        names = names[:MAX_SET]
    return names, how


# ---- the reading ------------------------------------------------------------------------------

def take(session, budget=None, state=None, names=None):
    """The reading of the chosen tools now: { at, seq, ms, how, by {tool:
    class}, why {tool: its "not" refusal}, left (tools the budget ran out
    before) }, kept on the session as its last reading. Never raises."""
    t0 = time.time()
    server = getattr(session, "server", None)
    out = {"at": t0, "seq": getattr(session, "_applies_seq", 0), "ms": 0, "how": {}, "by": {}, "why": {}, "steps": {}, "left": 0}
    if server is None:
        return out
    budget = budget_ms() if budget is None else budget
    deadline = t0 + budget / 1000.0
    try:
        if names is None:
            if state is None:
                from .tools import now_state

                state = now_state(getattr(session, "doc", None), ())
            names, out["how"] = chosen(server, state)
        slow = session.__dict__.setdefault("_applies_slow", {})
        pushed = budget <= budget_ms()
        for i, name in enumerate(names):
            t = server.tools.get(name)
            if t is None:
                continue
            now = time.time()
            if now >= deadline:
                out["left"] = len(names) - i
                break
            if getattr(t, "entry", None) is None or (pushed and name in slow):
                out["by"][name] = "notChecked"
                continue
            r = needs.of_tool(t, None, budget=min(ONE_S if pushed else 0.5, deadline - now))
            took = (time.time() - now) * 1000
            if took > SLOW_MS:
                slow[name] = int(took)
            out["by"][name] = needs.klass(r)
            if r["applies"] is False:
                out["why"][name] = {"code": r["wouldRefuse"][0]["code"], "words": r["wouldRefuse"][0]["words"]}
                out["steps"][name] = r["wouldRefuse"][0].get("step")
    except Exception:  # noqa: BLE001 - the filter never fails the call it follows
        pass
    out["ms"] = int((time.time() - t0) * 1000)
    try:
        session._applies = out
    except Exception:  # noqa: BLE001
        pass
    return out


def line(reading, server):
    """The short line of a reading; None when no tool was chosen."""
    by = reading.get("by") or {}
    if not by and not reading.get("left"):
        return None
    groups = {}
    for name, k in by.items():
        if k == "applies":
            t = server.tools.get(name)
            g = t.group if t is not None else "?"
            groups[g] = groups.get(g, 0) + 1
    out = {"groups": dict(sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))), "not": sum(1 for k in by.values() if k == "not"),
           "notChecked": sum(1 for k in by.values() if k == "notChecked"), "ms": reading.get("ms", 0)}
    if reading.get("left"):
        out["partial"] = reading["left"]
    return out


def push(session, tool, out, count=True):
    """After a changing call that answered: the reading taken, and its
    line put beside "next" (in the answer's health; on a batch's answer
    itself) when it is not what was last said. Inside a batch nothing is
    read: the batch's answer carries the one line (count: False for the
    batch's own call, whose changes its calls counted). Never raises."""
    try:
        if count:  # one more change the last reading has not seen
            session._applies_seq = getattr(session, "_applies_seq", 0) + 1
        if getattr(session, "batch_now", None) is not None or not isinstance(out, dict) or not enabled():
            return out
        server = getattr(session, "server", None)
        if server is None:
            return out
        r = take(session)
        ln = line(r, server)
        said = {k: v for k, v in (ln or {}).items() if k != "ms"}
        if ln is None or said == getattr(session, "_applies_said", None):
            return out
        session._applies_said = said
        h = out.get("health")
        if isinstance(h, dict):
            h["appliesNow"] = ln
        else:
            out["appliesNow"] = ln
    except Exception:  # noqa: BLE001
        pass
    return out


def full(session, state=None):
    """The same reading in full, for tool_groups { now: true }: full_of()
    of a reading taken now with a longer budget."""
    return full_of(take(session, budget=NOW_BUDGET_MS, state=state), session.server)


def full_of(r, server):
    """A reading in full: tool names by class (applies by group; not, each
    with its refusal's code and first words; notChecked), CAP names a class
    (NOT_CAP for not), how the tools were chosen and how to get the rest."""
    by = r["by"]
    applies = {}
    for name, k in by.items():
        if k == "applies":
            t = server.tools.get(name)
            applies.setdefault(t.group if t is not None else "?", []).append(name)
    shown, groups = 0, {}
    for g in sorted(applies):
        room = max(0, CAP - shown)
        if room:
            groups[g] = applies[g][:room]
            shown += len(groups[g])
    nots = [n for n, k in by.items() if k == "not"]
    unknown = [n for n, k in by.items() if k == "notChecked"]
    out = {"chosen": r["how"], "tools": len(by), "applies": groups,
           "not": [{"tool": n, "code": r["why"][n]["code"], "words": _short(r["why"][n]["words"])} for n in nots[:NOT_CAP]],
           "notChecked": {"count": len(unknown), "tools": unknown[:CAP]}, "ms": r["ms"]}
    more = {k: v for k, v in (("applies", sum(len(v) for v in applies.values()) - shown), ("not", len(nots) - min(len(nots), NOT_CAP)),
                              ("notChecked", len(unknown) - min(len(unknown), CAP))) if v > 0}
    if more:
        out["more"] = more
    if r["left"]:
        out["partial"] = r["left"]
    out["note"] = ("From each tool's own leading checks, read without its arguments: advice, never a gate. "
                   "tool_groups { needs: \"tool\", arguments: {…} } reads one tool for a call and gives a refusal's whole words"
                   + ("; more: counts left out, the same call gives each." if more else "."))
    return out


def _short(words, n=70):
    words = " ".join(str(words).split())
    return words if len(words) <= n else words[:n].rsplit(" ", 1)[0] + " …"


def order(hits, session, name_of=lambda h: h, budget=None):
    """hits in their order, those whose leading checks refuse now moved
    after the rest (nothing dropped), and {name: True | False} for the
    tools that could be told. A tool that applies and one that could not
    be told keep their places: the search's own ranking decides there."""
    server = getattr(session, "server", None)
    known = {}
    if server is None:
        return list(hits), known
    deadline = time.time() + (budget_ms() if budget is None else budget) / 1000.0
    try:
        for h in hits:
            left = deadline - time.time()
            if left <= 0:
                break
            t = server.tools.get(name_of(h))
            if t is None or getattr(t, "entry", None) is None:
                continue
            r = needs.of_tool(t, None, budget=min(ONE_S, left))
            if r["applies"] is not None:
                known[t.name] = r["applies"]
    except Exception:  # noqa: BLE001
        pass
    return [h for h in hits if known.get(name_of(h)) is not False] + [h for h in hits if known.get(name_of(h)) is False], known


# ---- the meter --------------------------------------------------------------------------------

READINGS = ("applies", "not", "notChecked", "notEvaluated")
OUTCOMES = ("answered", "refusedLeading", "refusedLater", "refusedOther")


class Meter:
    """What the filter's last reading said of each called tool, and what
    happened: running counts for one session."""

    def __init__(self, session_id=None):
        self.session_id = session_id or time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
        self.calls = 0
        self.counts = {r: {o: 0 for o in OUTCOMES} for r in READINGS}
        self.stale = 0                 # calls whose reading was older than the last change
        self.not_then_answered = {}    # tool -> count: the filter said "not" (fresh), the call answered
        self.applies_then_leading = {}  # tool -> count: it said "applies" (fresh), a leading check refused
        self.not_same_check = 0        # "not", and the call was refused by the very check the reading named

    def note(self, session, name, refused, prior=None, args=None):
        """One call ended. refused: whether it was. prior: before_call()'s
        (the last reading and the count of changes as they were when the
        call began); args: the call's arguments. Where a data tool's
        refusal came from is told by reading the tool again with those
        arguments (a refused call left the document as it was): the same
        step refusing in the reading is a leading check's refusal; a
        reading that passes every leading check puts the refusal after the
        tool's first change; a reading that could not tell goes by the
        step's place in the entry (needs.leading)."""
        was, runners.REFUSED[0] = runners.REFUSED[0], None
        reading, seq = prior if prior is not None else (getattr(session, "_applies", None), getattr(session, "_applies_seq", 0))
        reading = reading or {}
        said = (reading.get("by") or {}).get(name, "notEvaluated")
        fresh = reading.get("seq") == seq
        outcome, step = "answered", None
        if refused:
            outcome = "refusedOther"
            if was is not None and was[0] == name:
                tool = getattr(getattr(session, "server", None), "tools", {}).get(name)
                entry = getattr(tool, "entry", None)
                step = was[1]
                if entry is not None and entry.get("runner") == "steps" and step is None:
                    outcome = "refusedLater"  # from the entry's own answer, after its steps
                elif entry is not None and entry.get("runner") == "steps":
                    import copy

                    again = needs.of_tool(tool, copy.deepcopy(args) if isinstance(args, dict) else {}, budget=AGAIN_S)
                    if again["applies"] is False:
                        lead = again["wouldRefuse"][0].get("step") == id(step)
                    else:
                        lead = again["applies"] is None and id(step) in needs.leading(entry)
                    outcome = "refusedLeading" if lead else "refusedLater"
        self.calls += 1
        self.counts[said][outcome] += 1
        if said in ("applies", "not") and not fresh:
            self.stale += 1
            return
        if said == "not" and outcome == "answered":
            self.not_then_answered[name] = self.not_then_answered.get(name, 0) + 1
        elif said == "not" and step is not None and (reading.get("steps") or {}).get(name) == id(step):
            self.not_same_check += 1
        elif said == "applies" and outcome == "refusedLeading":
            self.applies_then_leading[name] = self.applies_then_leading.get(name, 0) + 1

    def totals(self):
        checked = sum(sum(self.counts[r].values()) for r in ("applies", "not"))
        return {"calls": self.calls, "coverage": round(checked / self.calls, 3) if self.calls else 0.0, "checked": checked, "stale": self.stale,
                "notThenAnswered": dict(self.not_then_answered), "appliesThenLeadingRefusal": dict(self.applies_then_leading),
                "notRefusedByTheSameCheck": self.not_same_check, "byReading": {r: {o: n for o, n in self.counts[r].items() if n} for r in READINGS}}

    def report(self):
        """The short section usage_report carries."""
        t = self.totals()
        wrong = sum(t["notThenAnswered"].values())
        missed = sum(t["appliesThenLeadingRefusal"].values())
        return {"calls": t["calls"], "coverage": t["coverage"],
                "notThenAnswered": {"count": wrong, "tools": sorted(t["notThenAnswered"], key=lambda k: -t["notThenAnswered"][k])[:12]},
                "appliesThenLeadingRefusal": {"count": missed, "tools": sorted(t["appliesThenLeadingRefusal"], key=lambda k: -t["appliesThenLeadingRefusal"][k])[:12]},
                "stale": t["stale"], "byReading": t["byReading"],
                "note": "notThenAnswered must stay near zero (a wrong reading); appliesThenLeadingRefusal: a check the reading passed and the call did not; "
                        "coverage: the share of calls whose tool the filter had told; stale: calls after a change it had not read yet (in a batch)."}

    def write(self, folder):
        """The session's counts into folder/applies_meter.json, beside the
        other sessions' (the newest SESSIONS_KEPT): written whole to a
        file of its own and put in place in one step, so a reader never
        sees half of it and another session's counts are kept."""
        try:
            path = os.path.join(folder, FILE)
            doc = {}
            try:
                with open(path, encoding="utf-8") as f:
                    doc = json.load(f)
            except (OSError, ValueError):
                doc = {}
            sessions = doc.get("sessions") if isinstance(doc.get("sessions"), dict) else {}
            sessions[self.session_id] = {"updated": round(time.time(), 1), **self.totals()}
            keep = sorted(sessions, key=lambda k: sessions[k].get("updated", 0))[-SESSIONS_KEPT:]
            doc = {"about": "Agent Link's applies-now meter: what the filter's last reading said of each called tool, and what the call did. "
                            "notThenAnswered must stay near zero.",
                   "sessions": {k: sessions[k] for k in keep}}
            tmp = f"{path}.{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=1)
            os.replace(tmp, path)
            return path
        except OSError:
            return None


def meter_of(session):
    m = getattr(session, "_applies_meter", None)
    if m is None:
        m = session._applies_meter = Meter()
    return m


def before_call(session):
    """A call begins: (the last reading, the changes counted so far), for
    after_call — the call's own change and the reading after it must not
    be what it is measured against."""
    runners.REFUSED[0] = None
    return getattr(session, "_applies", None), getattr(session, "_applies_seq", 0)


def after_call(session, name, refused, prior=None, args=None):
    """Every call's end: counted, and the counts written. Never raises."""
    try:
        m = meter_of(session)
        m.note(session, name, refused, prior, args)
        folder = getattr(session, "out_dir", None)
        if folder and os.environ.get("AGENTLINK_APPLIES_METER", "on") not in ("0", "false", "off"):
            m.write(folder)
    except Exception:  # noqa: BLE001
        pass
