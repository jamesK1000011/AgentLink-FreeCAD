# SPDX-License-Identifier: LGPL-2.1-or-later
"""The "next" hint of session_state and the health check: one short line of
what FreeCAD's window is in the middle of, so the agent's next call fits it
— a dialog in front and its buttons, a sketch open in edit with its degrees
of freedom, an open task panel and its buttons, up to three tools that are
the likely next step with a few words each on why, the active workbench
and the status bar's text.

The likely next tools are ranked from the document's own state, not listed
by name: a small table of rules (data/nexthint.json, its schema beside it)
says, for a state — a failing recompute, an edge or a face picked, a sketch
open in edit with freedom left, a closed sketch no feature uses, a body
whose last feature is a pad, a drawing page in front, an assembly without
joints — which tools usually come next, and how much the rule weighs. The
state is read cheaply (tools.next_facts()); a tool that is not installed,
or whose FreeCAD command sits on the active workbench's toolbars and
reports itself inactive, is passed over (tools.now_state(): no command
outside those toolbars is ever asked). tool_groups { now: true } puts the
same picks first.

An add-on adds rules for its own tools with NEXT on its family module
({ id: entry }, the same shape as the file's entries): declare().

Plain Python: the state is read by tools.next_state(); here it is ranked,
put into words and kept under MAX characters.
"""
import json
import os

from . import toolindex

MAX = 400
MAX_TOOLS = 3        # tools said in the hint
MAX_SUGGEST = 4      # tools read from one rule
MAX_PICKS = 12       # tools whose commands are asked whether they are active
MAX_WHY = 60
MAX_FACT_WORDS = 160  # the facts a rule fit by, in words (fact_words)

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "nexthint.json")
SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "nexthint.schema.json")

# Rules installed add-ons declared (declare()): { id: entry }.
EXTRA = {}
_cache = {}


PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
PREF = "NextHints"
ENV = "AGENTLINK_NEXT_HINTS"


def on():
    """Whether the likely-next hints are given: the health's "next" line
    and the numbered options of a changing call's answer, and the likely
    next tools of session_state's next. The person's preference NextHints
    (Mod/AgentLink, bool, on); AGENTLINK_NEXT_HINTS=0 turns them off (test
    runs). A refusal keeps its own guidance either way."""
    if os.environ.get(ENV, "1").strip().lower() in ("0", "false", "off", "no"):
        return False
    try:
        import FreeCAD

        return bool(FreeCAD.ParamGet(PREFS).GetBool(PREF, True))
    except Exception:  # noqa: BLE001 - no FreeCAD here, or a stand-in without settings
        return True


def _cut(text, n):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:max(1, n - 1)].rstrip() + "…"


def _buttons(names, n=5):
    names = [_cut(b, 18) for b in (names or []) if str(b or "").strip()]
    return ", ".join(names[:n]) + (f" and {len(names) - n} more" if len(names) > n else "")


# ---- the facts ----------------------------------------------------------------------------

# Past this many objects the document's own state is not read for the hint
# (the selection, the sketch in edit and the page in front still are).
MAX_OBJECTS = 2000
MAX_NAMES = 6        # real names kept in a fact that lists them (bodies, sketches, picked edges)
# PartDesign's solid features (FreeCAD's type names, lower case) are told
# from its dress-ups and patterns by the rules themselves (data/nexthint.json).


MAX_LOOPS = 12      # closed wires of one sketch past which the meeting test is not run


def _sketch_progress(sk):
    """sketch-empty (no geometry), sketch-closed (every wire closed and the
    sketch ready for a feature), sketch-not-ready (every wire closed, but
    the solver flags constraints or two closed loops meet: sketch_state's
    readyForFeature is false) or sketch-open, of a sketch no feature uses
    yet."""
    try:
        if int(sk.GeometryCount) == 0:
            return "sketch-empty"
    except Exception:  # noqa: BLE001
        pass
    try:
        wires = sk.Shape.Wires
        if not (wires and all(w.isClosed() for w in wires)):
            return "sketch-open"
    except Exception:  # noqa: BLE001 - a null shape: nothing closed yet
        return "sketch-open"
    return "sketch-not-ready" if _not_ready(sk, wires) else "sketch-closed"


def _not_ready(sk, wires):
    """Whether a sketch whose wires are all closed is still not ready for a
    feature, as sketch_state's readyForFeature reads it (26 Nov QA: options
    gave pd_pad while readyForFeature was false): the solver's last reading
    names conflicting, redundant or malformed constraints, or two closed
    loops cross or touch (a loop inside another, apart from it, is a hole).
    Cheap reads only; False when one cannot be read."""
    try:
        for k in ("ConflictingConstraints", "RedundantConstraints", "MalformedConstraints"):
            if getattr(sk, k, None):
                return True
    except Exception:  # noqa: BLE001
        pass
    try:
        loops = list(wires)
        if len(loops) < 2 or len(loops) > MAX_LOOPS:
            return False
        size = max(sk.Shape.BoundBox.DiagonalLength, 1.0)
        for i in range(len(loops)):
            for j in range(i + 1, len(loops)):
                a, b = loops[i], loops[j]
                if not a.BoundBox.intersect(b.BoundBox):
                    continue
                if a.distToShape(b)[0] <= 1e-6 * size:
                    return True
    except Exception:  # noqa: BLE001 - not read: the wires' reading stands
        return False
    return False


def facts(doc, state=None, gui=None):
    """The document's own state as the rules read it (data/nexthint.json's
    "about" lists the facts), from FreeCAD's objects as they are (doc: the
    document; state: tools.now_state()'s, with the sketch in edit; gui:
    FreeCADGui in the window, None without one) and from cheap
    reads only: object State flags, the active body's Group and Tip, an
    unused sketch's wires, an assembly's joint group, the selection and
    the view in front. A fact that cannot be read is left out, and a rule
    that needs it then does not fit. Beside the facts the rules read, the
    real names an option's arguments are filled from (agentlink/options.py):
    bodyName, bodies, sketchName, sketches, tipName, editSketch, picked,
    pickedEdges, pickedFaces, failingName, assemblyName. Never raises."""
    state = state or {}
    out = {}
    if state.get("workbench"):
        out["workbench"] = state["workbench"]
    if state.get("editing"):
        out["editing"] = "sketch" if state["editing"] == "sketch" else "other"
        dof = (state.get("sketch") or {}).get("dof")
        if isinstance(dof, int):
            out["dof"] = "full" if dof == 0 else "free"
    subs = state.get("selSubs") or ()
    sel = next((k for k in ("edge", "face", "vertex") if k in subs), None) or ("object" if state.get("selected") else None)
    picked = None
    active_body = active_part = None
    # The real names an option's arguments are filled from (agentlink/options.py):
    # the sketch in edit, the picked object and its picked edges and faces.
    # Labels, as every answer names objects and every tool takes them (a
    # Haiku run, 23 Nov: an option said Sketch001 where sketch_new said Sketch 2).
    edit_name = (state.get("sketch") or {}).get("name") or (state.get("sketch") or {}).get("obj")
    if edit_name:
        out["editSketch"] = edit_name
    if gui is not None:
        try:
            if sel:
                first = gui.Selection.getSelectionEx()[0]
                picked = first.Object
                out["picked"] = str(picked.Label)
                names = [str(n).rsplit(".", 1)[-1] for n in (first.SubElementNames or ())]
                for kind, key in (("Edge", "pickedEdges"), ("Face", "pickedFaces")):
                    got = [n for n in names if n.startswith(kind)][:MAX_NAMES]
                    if got:
                        out[key] = got
        except Exception:  # noqa: BLE001
            picked = None
        try:
            view = gui.ActiveDocument.ActiveView
            if type(view).__name__ == "MDIViewPagePy":  # TechDraw's page view (FreeCAD 1.1: TechDraw/Gui/MDIViewPage.cpp)
                out["page"] = True
            elif hasattr(view, "getActiveObject"):
                active_body = view.getActiveObject("pdbody")
                active_part = view.getActiveObject("part")
        except Exception:  # noqa: BLE001
            pass
    if sel:
        out["selection"] = sel
        try:
            in_body = picked is not None and (picked.TypeId == "PartDesign::Body" or any(p.TypeId == "PartDesign::Body" for p in picked.InList))
            out["selectionIn"] = "body" if in_body else "other"
        except Exception:  # noqa: BLE001
            out["selectionIn"] = "other"
    try:
        objs = list(doc.Objects)
    except Exception:  # noqa: BLE001 - no document, or one that was closed
        return out
    out["document"] = "objects" if objs else "empty"
    if len(objs) > MAX_OBJECTS:
        return out
    try:
        bad = next((o for o in objs if "Invalid" in o.State), None)
        out["failing"] = bad is not None
        if bad is not None:
            out["failingName"] = str(bad.Label)
    except Exception:  # noqa: BLE001
        pass
    try:
        asms = [o for o in objs if o.TypeId == "Assembly::AssemblyObject"]
        if asms:
            asm = active_part if active_part in asms else asms[-1]
            group = list(asm.Group)
            joints = sum(len(g.Group) for g in group if g.TypeId == "Assembly::JointGroup")
            parts = [o for o in group if not o.TypeId.endswith("Group")]
            out["assembly"] = "empty" if not parts else ("jointed" if joints else "unjointed")
            out["assemblyName"] = str(asm.Label)
    except Exception:  # noqa: BLE001
        pass
    try:
        bodies = [o for o in objs if o.TypeId == "PartDesign::Body"]
        if not bodies:
            out["body"] = "none"
            return out
        body = active_body if active_body in bodies else None
        if body is None and picked is not None:
            body = picked if picked in bodies else next((p for p in picked.InList if p in bodies), None)
        if body is None:
            body = bodies[-1]
        out["bodyName"] = str(body.Label)
        out["bodies"] = [str(b.Label) for b in [body] + [b for b in reversed(bodies) if b is not body]][:MAX_NAMES]
        group = list(body.Group)
        sketches = [o for o in group if o.isDerivedFrom("Sketcher::SketchObject")]
        feats = [o for o in group if o.isDerivedFrom("PartDesign::Feature")]
        unused = [k for k in sketches if not any(p.isDerivedFrom("PartDesign::Feature") for p in k.InList)]
        out["features"] = "some" if feats else "none"
        if unused:
            out["body"] = _sketch_progress(unused[-1])
            if out["body"] == "sketch-open":
                try:
                    out["openWires"] = sum(1 for w in unused[-1].Shape.Wires if not w.isClosed())
                except Exception:  # noqa: BLE001 - not read: not said
                    pass
            out["sketchName"] = str(unused[-1].Label)
            out["sketches"] = [str(k.Label) for k in reversed(unused)][:MAX_NAMES]
        elif feats:
            out["body"] = "features"
            tip = getattr(body, "Tip", None) or feats[-1]
            out["lastFeature"] = str(tip.TypeId).rsplit("::", 1)[-1].lower()
            out["tipName"] = str(tip.Label)
        else:
            out["body"] = "empty"
    except Exception:  # noqa: BLE001
        pass
    return out



# ---- the rules ----------------------------------------------------------------------------

def _schema():
    if "schema" not in _cache:
        try:
            with open(SCHEMA, encoding="utf-8") as f:
                _cache["schema"] = json.load(f)
        except (OSError, ValueError):
            _cache["schema"] = None
    return _cache["schema"]


def problems(entry):
    """What is wrong with one rule, by the schema ([] when it fits)."""
    from . import datafiles

    schema = _schema()
    if schema is None:
        return [] if isinstance(entry, dict) and isinstance(entry.get("when"), dict) and isinstance(entry.get("suggest"), list) else ["not a rule"]
    out = datafiles.validate(entry, schema)
    if not out:
        out = _expr_problems(entry)
    return out


def _expr_problems(entry):
    """An option's expressions (arguments and choices: "=…") that the hub's
    checked language does not read (agentlink/expr.py; never eval)."""
    from . import expr

    out = []
    for s in entry.get("suggest") or ():
        for part in ("arguments", "choices"):
            for k, v in (s.get(part) or {}).items():
                if isinstance(v, str) and v.startswith("="):
                    bad = expr.check(v[1:])
                    if bad:
                        out.append(f"{s.get('tool')}.{part}.{k}: {bad}")
    return out


def load(path=None):
    """{ id: rule } from the data file ({} when it is missing or unreadable:
    the hint then says the state and names no tools). A rule that does not
    fit the schema is left out."""
    path = path or DATA
    if path not in _cache:
        try:
            with open(path, encoding="utf-8") as f:
                entries = json.load(f).get("entries", {})
            _cache[path] = {k: v for k, v in entries.items() if not problems(v)}
        except (OSError, ValueError, AttributeError):
            _cache[path] = {}
    return _cache[path]


def declare(entries, owner="an add-on"):
    """An add-on's own rules ({ id: entry }, its family module's NEXT): the
    same shape as the file's, checked by the same schema. Those that do not
    fit are left out; their problems are returned (for the log). A rule of
    the file is never replaced: an add-on's id that is taken is kept under
    "<owner>:<id>"."""
    bad = []
    if not isinstance(entries, dict):
        return [f"{owner}: NEXT is not an object of rules"]
    for k, v in entries.items():
        if not isinstance(k, str) or not k:
            continue
        p = problems(v)
        if p:
            bad.append(f"{owner}: next-hint rule {k}: {p[0]}")
            continue
        key = k if k not in load() else f"{owner}:{k}"
        EXTRA[key] = v
    return bad


def rules():
    """Every rule: the file's, then the add-ons'."""
    return {**load(), **EXTRA}


def _holds(cond, facts):
    """Whether every fact of cond has (one of) its value(s)."""
    for k, want in cond.items():
        have = facts.get(k)
        if isinstance(want, list):
            if have not in want:
                return False
        elif have != want:
            return False
    return True


def matches(rule, facts):
    """Whether a rule fits the facts: all of when, none of unless."""
    when = rule.get("when") or {}
    if not when or not _holds(when, facts):
        return False
    for k, want in (rule.get("unless") or {}).items():
        if _holds({k: want}, facts):
            return False
    return True


def _a(word):
    return ("an " if word[:1] in "aeiou" else "a ") + word


def fact_words(when, facts):
    """The facts of the document that made a rule fit, in words, from the
    facts read (owner, 27 Nov: the why of a likely next tool is FACTS ONLY,
    "sketch Path has 1 open wire", never an aim such as "close the
    outline"). Only the facts the rule's when names are said."""
    f = facts or {}
    out = []
    for k in (when or {}):
        v = f.get(k)
        if k == "failing" and v:
            out.append(f"{f.get('failingName') or 'an object'} fails to recompute")
        elif k == "selection" and v:
            on = f.get("picked")
            out.append(f"{_a(str(v))} is selected" + (f" on {on}" if on else ""))
        elif k == "editing" and v == "sketch":
            out.append(f"sketch {f.get('editSketch') or ''} is open in edit".replace("  ", " "))
        elif k == "dof" and v:
            out.append("the sketch in edit is fully constrained" if v == "full" else "the sketch in edit has degrees of freedom left")
        elif k == "page" and v:
            out.append("a drawing page is in front")
        elif k == "assembly" and v:
            name = f.get("assemblyName") or "the assembly"
            out.append({"empty": f"{name} has no parts", "unjointed": f"{name} has parts and no joints", "jointed": f"{name} has joints"}.get(v, f"{name}: {v}"))
        elif k == "workbench" and v:
            out.append(f"the workbench is {v}")
        elif k == "document" and v == "empty":
            out.append("the document has no objects")
        elif k == "body" and v:
            body = f.get("bodyName") or "the body"
            sk = f"sketch {f['sketchName']}" if f.get("sketchName") else "the newest sketch"
            n_open = f.get("openWires")
            out.append({
                "none": "the document has no PartDesign Body",
                "empty": f"{body} has no feature and no sketch",
                "sketch-empty": f"{sk} of {body} has no geometry",
                "sketch-open": f"{sk} of {body} has " + (f"{n_open} open wire{'' if n_open == 1 else 's'}" if isinstance(n_open, int) else "open wires"),
                "sketch-not-ready": f"{sk} of {body} has closed wires, and the solver flags constraints or two loops meet",
                "sketch-closed": f"{sk} of {body} has closed wires, and no feature uses it",
                "features": f"the tip of {body} is {f.get('tipName') or 'a feature'}" + (f" ({f['lastFeature']})" if f.get("lastFeature") else ""),
            }.get(v, f"{body}: {v}"))
        elif k == "features" and v and "body" not in (when or {}):
            out.append(f"{f.get('bodyName') or 'the body'} has {'no feature' if v == 'none' else 'features'}")
        elif k == "lastFeature" and v and "body" not in (when or {}):
            out.append(f"the tip is {f.get('tipName') or 'a feature'} ({v})")
    return "; ".join(x for x in out if x)


def rank(facts, table=None, limit=MAX_PICKS):
    """The likely next tools for these facts, likeliest first:
    [{ tool, why, rule, score }], each tool once (from its heaviest rule).
    A rule's first tool scores its weight, each later one a little less,
    so a heavier rule's tools come before a lighter one's."""
    table = rules() if table is None else table
    best = {}
    for order, (rid, rule) in enumerate(table.items()):
        try:
            if not matches(rule, facts or {}):
                continue
            weight = float(rule.get("weight") or 0)
            for k, s in enumerate((rule.get("suggest") or [])[:MAX_SUGGEST]):
                tool, why = s.get("tool"), fact_words(rule.get("when"), facts)
                if not isinstance(tool, str) or not tool:
                    continue
                score = weight - 0.1 * k
                if tool not in best or score > best[tool][0]:
                    best[tool] = (score, order, k, _cut(why, MAX_FACT_WORDS), rid)
        except Exception:  # noqa: BLE001 - one bad rule never stops the hint
            continue
    got = sorted(best.items(), key=lambda kv: (-kv[1][0], kv[1][1], kv[1][2], kv[0]))
    return [{"tool": t, "why": v[3], "rule": v[4], "score": v[0]} for t, v in got[:limit]]


def commands_of(picks, entry=toolindex.entry):
    """The FreeCAD commands of the picked tools, for now_state() to ask
    (it asks only those on the active workbench's toolbars)."""
    out = []
    for p in picks:
        try:
            out += [c for c in entry(p["tool"]).get("commands") or [] if c not in out]
        except Exception:  # noqa: BLE001
            continue
    return out


def available(picks, state=None, exists=None, entry=toolindex.entry, n=MAX_TOOLS):
    """The first n picks that can be called now: the tool exists here
    (exists(name); None: not checked) and FreeCAD does not say otherwise —
    a tool whose commands on the shown toolbars all report themselves
    inactive (state["active"]) is passed over; one FreeCAD was not asked
    about (its command is on another workbench's toolbars, or it has none)
    stays, since nothing says it cannot run."""
    active = (state or {}).get("active") or {}
    out = []
    for p in picks:
        name = p["tool"]
        try:
            if exists is not None and not exists(name):
                continue
            known = [active[c] for c in (entry(name).get("commands") or []) if c in active]
        except Exception:  # noqa: BLE001
            known = []
        if known and not any(known):
            continue
        out.append(p)
        if len(out) >= n:
            break
    return out


def words(picks, n=MAX_TOOLS):
    """"pd_pad (a closed sketch no feature uses yet), pd_pocket (…)"."""
    # Tools of the same facts are said together, the facts once:
    # "pd_pad, pd_pocket (sketch S of Body has closed wires, …)".
    groups = []
    for p in list(picks)[:n]:
        why = p.get("why") or ""
        if groups and groups[-1][1] == why:
            groups[-1][0].append(p["tool"])
        else:
            groups.append(([p["tool"]], why))
    return ", ".join(", ".join(t) + (f" ({w})" if w else "") for t, w in groups)


# ---- the line -----------------------------------------------------------------------------

def key(state):
    """What makes a hint news: the dialog, the sketch in edit and its
    freedom, the task panel, the workbench, and the rules that fit (the
    body got its first sketch, a recompute began to fail). Not the status
    bar's text, which moves with the mouse."""
    d, sk, p = state.get("dialog") or {}, state.get("sketch") or {}, state.get("panel") or {}
    return (state.get("workbench"), state.get("editing"), sk.get("name"), sk.get("dof"), bool(p), tuple(p.get("buttons") or ()),
            d.get("title"), tuple(d.get("buttons") or ()), tuple(state.get("rules") or ()))


def record(state, tools=()):
    """The next part as a record (owner, 28 Nov: answers as records), or None
    with no window: { dialog: { title, buttons }, editing: { sketch, dof } |
    { object }, taskPanel: { buttons }, likelyNext: [ { tool, why } ],
    workbench, statusBar }. With a dialog in front no tool is named:
    dialog_answer presses its buttons."""
    if not state or not state.get("window"):
        return None
    out = {}
    d = state.get("dialog")
    if d:
        out["dialog"] = {"title": d.get("title") or "untitled", "buttons": list(d.get("buttons") or [])}
    sk = state.get("sketch")
    if sk:
        out["editing"] = {"sketch": sk.get("name"), **({"dof": sk.get("dof")} if sk.get("dof") is not None else {})}
    elif state.get("editing"):
        out["editing"] = {"object": state["editing"]}
    p = state.get("panel")
    if p:
        out["taskPanel"] = {"buttons": list(p.get("buttons") or [])}
    picks = [t if isinstance(t, dict) else {"tool": str(t), "why": ""} for t in (tools or ())][:MAX_TOOLS]
    if picks and not d:
        out["likelyNext"] = [{"tool": t.get("tool"), **({"why": t["why"]} if t.get("why") else {})} for t in picks]
    if state.get("workbench"):
        out["workbench"] = state["workbench"]
    if state.get("status"):
        out["statusBar"] = state["status"]
    return out or None


def compose(state, tools=(), limit=MAX):
    """The hint, or None when there is nothing to say (no window).
    state: { window, workbench, editing, sketch { name, dof }, panel
    { buttons }, dialog { title, buttons }, status }; tools: the picks
    from available() ([{ tool, why }]; plain names are taken too). What
    matters most comes first, and the line is cut to limit: the likely
    next tools come before the workbench and the status bar's text, so
    they are not what is cut. With a dialog in front no tool is named:
    answering it is the next step."""
    if not state or not state.get("window"):
        return None
    parts = []
    d = state.get("dialog")
    if d:
        b = _buttons(d.get("buttons"))
        parts.append(f"a dialog is in front: {_cut(d.get('title') or 'untitled', 50)}" + (f" [{b}]" if b else "") + " — dialog_answer presses a button")
    sk = state.get("sketch")
    if sk:
        dof = sk.get("dof")
        parts.append(f"sketch {_cut(sk.get('name'), 40)} is open in edit"
                     + ("" if dof is None else (", fully constrained" if dof == 0 else f", {dof} DoF left")))
    elif state.get("editing"):
        parts.append(f"{_cut(state['editing'], 40)} is open in edit")
    p = state.get("panel")
    if p:
        b = _buttons(p.get("buttons"))
        parts.append("a task panel is open" + (f" [{b}]" if b else ""))
    picks = [t if isinstance(t, dict) else {"tool": str(t), "why": ""} for t in (tools or ())][:MAX_TOOLS]
    if picks and not d:
        parts.append("likely next: " + words(picks))
    if state.get("workbench"):
        parts.append(f"workbench {state['workbench']}")
    if state.get("status"):
        parts.append(f"status bar: {_cut(state['status'], 80)}")
    if not parts:
        return None
    return _cut("; ".join(parts), limit)
