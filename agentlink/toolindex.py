# SPDX-License-Identifier: LGPL-2.1-or-later
"""The tool index: what FreeCAD itself knows of each tool, for finding one.

data/tool_index.json says, for every tool Agent Link itself defines, the
workbench it belongs to (FreeCAD's class name, or null), the FreeCAD
commands it does the work of, and a few search words its name lacks. It is
generated (scripts/tool_index.py) from the live echo's tables
(agentlink/echo.py) and a hand-kept additions file. An add-on gives the same
three fields in its tools.json entries (agentlink/tooldata.py), which reach
declare() here when its tools are built: nothing of an add-on is kept in
this repository, and an add-on that is not installed costs nothing.

tool_groups { find } ranks with rank(); tool_groups { now: true } with
fits(), from the window's state. Plain Python: no FreeCAD is imported here.
"""
import json
import os
import re

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tool_index.json")
FIELDS = ("workbench", "commands", "words")

# What installed add-ons said of their own tools (declare()).
EXTRA = {}
_cache = {}

# The words a person uses for a workbench: one of these in a search lifts
# that workbench's tools.
WORKBENCH_WORDS = {
    "PartDesignWorkbench": ("partdesign", "pd"),
    "SketcherWorkbench": ("sketcher", "sketch"),
    "PartWorkbench": ("part",),
    "DraftWorkbench": ("draft",),
    "BIMWorkbench": ("bim", "arch", "building", "architecture", "ifc"),
    "TechDrawWorkbench": ("techdraw", "drawing", "td"),
    "AssemblyWorkbench": ("assembly", "asm"),
    "SpreadsheetWorkbench": ("spreadsheet", "sheet"),
    "FemWorkbench": ("fem", "fea"),
    "MeshWorkbench": ("mesh",),
    "SurfaceWorkbench": ("surface",),
    "CAMWorkbench": ("cam", "cnc", "machining", "path"),
    "PointsWorkbench": ("points", "pointcloud"),
    "OpenSCADWorkbench": ("openscad", "scad"),
    "RobotWorkbench": ("robot",),
    "InspectionWorkbench": ("inspection",),
    "ReverseEngineeringWorkbench": ("reverse", "reen"),
    "MaterialWorkbench": ("material",),
}
WORKBENCHES = tuple(WORKBENCH_WORDS)

# An object's type → the workbench whose tools work on it.
TYPE_BENCH = (
    ("Sketcher::", "SketcherWorkbench"), ("PartDesign::", "PartDesignWorkbench"), ("Part::", "PartWorkbench"),
    ("Mesh::", "MeshWorkbench"), ("Points::", "PointsWorkbench"), ("TechDraw::", "TechDrawWorkbench"),
    ("Spreadsheet::", "SpreadsheetWorkbench"), ("Fem::", "FemWorkbench"), ("Assembly::", "AssemblyWorkbench"),
    ("Path::", "CAMWorkbench"), ("Robot::", "RobotWorkbench"), ("Inspection::", "InspectionWorkbench"),
    ("Surface::", "SurfaceWorkbench"),
)
# A Python-made object's proxy module → its workbench (a Draft wire and a
# BIM wall are both Part::FeaturePython by type).
PROXY_BENCH = (
    ("draftobjects", "DraftWorkbench"), ("draft", "DraftWorkbench"), ("Draft", "DraftWorkbench"),
    ("Arch", "BIMWorkbench"), ("bim", "BIMWorkbench"), ("nativeifc", "BIMWorkbench"),
    ("Path", "CAMWorkbench"), ("femobjects", "FemWorkbench"), ("JointObject", "AssemblyWorkbench"),
)
STOP = {"a", "an", "the", "to", "of", "in", "on", "for", "with", "and", "or", "by", "it", "is", "my", "how", "do", "from", "into", "make", "add"}


def load(path=None):
    """{tool: {workbench, commands, words}} from the index file ({} when it
    is missing or unreadable: the search then goes by names and descriptions)."""
    path = path or DATA
    if path not in _cache:
        try:
            with open(path, encoding="utf-8") as f:
                _cache[path] = json.load(f).get("entries", {})
        except (OSError, ValueError):
            _cache[path] = {}
    return _cache[path]


def clean(e):
    """An entry with only the three fields, each of its own type; None when
    nothing is left."""
    if not isinstance(e, dict):
        return None
    wb = e.get("workbench")
    out = {"workbench": wb if isinstance(wb, str) and wb else None,
           "commands": [c for c in (e.get("commands") or []) if isinstance(c, str) and c] if isinstance(e.get("commands"), list) else [],
           "words": [w.lower() for w in (e.get("words") or []) if isinstance(w, str) and w] if isinstance(e.get("words"), list) else []}
    return out if out["workbench"] or out["commands"] or out["words"] else None


def declare(name, e):
    """An add-on's own entry for one of its tools (its tools.json fields)."""
    got = clean(e)
    if isinstance(name, str) and got:
        EXTRA[name] = got


def bench_for_command(cmd):
    """The workbench a declared tool runs the FreeCAD command cmd in (an
    add-on's tools.json: commands and workbench), or None."""
    for src in (EXTRA, load()):
        for e in src.values():
            if isinstance(e, dict) and e.get("workbench") and cmd in (e.get("commands") or ()):
                return e["workbench"]
    return None


def entry(name, fallback=None):
    """A tool's entry: the index's, else what its add-on declared, with
    fallback(name) -> (workbench, command) (the echo's declarations) filling
    what is still empty. Always the three fields."""
    e = load().get(name) or EXTRA.get(name)
    out = {"workbench": None, "commands": [], "words": []}
    if e:
        out = {"workbench": e.get("workbench"), "commands": list(e.get("commands") or []), "words": list(e.get("words") or [])}
    if fallback is not None and (out["workbench"] is None or not out["commands"]) and name not in load():
        try:
            wb, cmd = fallback(name)
        except Exception:  # noqa: BLE001 - an add-on's own callable
            wb, cmd = None, None
        if out["workbench"] is None and isinstance(wb, str) and wb:
            out["workbench"] = wb
        if not out["commands"] and isinstance(cmd, str) and cmd:
            out["commands"] = [cmd]
    return out


# ---- words --------------------------------------------------------------------------------

def norm(w):
    """A word as compared: lower case, a plural's s dropped."""
    w = w.lower()
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return w


def tokens(text):
    return [norm(w) for w in re.findall(r"[a-z0-9]+", str(text or "").lower())]


def query_words(find):
    """The words of a search that count: stop words go unless nothing is left."""
    raw = [w for w in re.findall(r"[a-z0-9]+", str(find or "").lower()) if len(w) > 1]
    kept = [w for w in raw if w not in STOP]
    return list(dict.fromkeys(norm(w) for w in (kept or raw)))


def command_tokens(cmd):
    """PartDesign_AdditiveLoft → partdesign, additive, loft."""
    out = []
    for part in str(cmd).split("_"):
        out.append(part.lower())
        out += [p.lower() for p in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+", part)]
    return {norm(t) for t in out if t}


def workbenches_named(words):
    """The workbenches a search's words name."""
    return {wb for wb, ws in WORKBENCH_WORDS.items() if any(norm(x) in words for x in ws)}


def first_sentence(text, n=160):
    """A description's first full sentence, for a one-line "does": ended at
    a full stop (never at a colon, a decimal point or "e.g."), and cut at a
    word with … when it runs past n characters."""
    t = " ".join(str(text or "").split())
    end = len(t)
    for m in re.finditer(r"\.(?=\s+\S|$)", t):
        before = t[:m.start()]
        if re.search(r"\b(e\.g|i\.e|etc|vs|approx|incl|no)$", before, re.I):
            continue
        end = m.end()
        break
    s = t[:end]
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(",;:([{|—-") + " …"


# ---- find ---------------------------------------------------------------------------------

def score(words, name, e, description="", group="", about="", named=None):
    """(words matched, score) of one tool for a search's words. Per word: the
    best of the tool's name, the index's words and its commands; then its
    workbench when the word names it; then the description (its first
    sentence above the rest). The group's about counts a little and never
    makes a match by itself. A name's words the search did not ask for
    count a little against it."""
    name = name.lower()
    name_words = set(tokens(name))
    idx_words = {norm(w) for w in e.get("words") or []}
    cmd_words = set()
    for c in e.get("commands") or []:
        cmd_words |= command_tokens(c)
    cmd_text = " ".join(c.lower() for c in e.get("commands") or [])
    # "G-code" is found by gcode too.
    plain = str(description or "")
    lead_text = first_sentence(plain, 160)
    text = " ".join(tokens(plain) + tokens(plain.replace("-", "")))
    lead = " ".join(tokens(lead_text) + tokens(lead_text.replace("-", "")))
    group_words = set(tokens(group))
    about = " ".join(tokens(about))
    named = workbenches_named(set(words)) if named is None else named
    wb = e.get("workbench")
    matched, total = 0, 0.0
    for w in words:
        best = 0.0
        if w in name_words:
            best = 10
        elif len(w) > 2 and w in name:
            best = 6
        if w in idx_words:
            best = max(best, 7)
        elif len(w) > 3 and any(x.startswith(w) or (len(x) > 3 and w.startswith(x)) for x in idx_words):
            best = max(best, 5)
        if w in cmd_words:
            best = max(best, 6)
        elif len(w) > 3 and w in cmd_text:
            best = max(best, 4)
        got = best
        if wb and wb in named and any(norm(x) == w for x in WORKBENCH_WORDS.get(wb, ())):
            got += 5
        if w in group_words:
            got += 3
        if re.search(rf"\b{re.escape(w)}", lead):
            got += 3
        elif re.search(rf"\b{re.escape(w)}", text):
            got += 1.5
        if got >= 1.5:
            matched += 1
        elif re.search(rf"\b{re.escape(w)}", about):
            got += 0.5
        total += got
    # Between two tools a search fits alike, the plainer one first: each
    # word of a name past its family that the search did not ask for costs
    # a little (td_dim before td_dim_special for "drawing dimension").
    rest = name.split("_")[1:] or [name]
    spare = sum(1 for tok in rest if not any(w == norm(tok) or (len(tok) > 2 and w.startswith(tok)) or (len(w) > 2 and tok.startswith(w)) for w in words))
    if matched:
        total -= min(spare, 2) * 1.5
    return matched, total


def rank(rows, find, bonus=None):
    """rows [{name, description, group, about, entry}] ranked for a search:
    [(row, matched, score)] best first — tools matching every word above
    those matching fewer, then by score, then by name. bonus(row) -> number
    is added to a hit's score (what fits now)."""
    words = query_words(find)
    if not words:
        return []
    named = workbenches_named(set(words))
    hits = []
    for r in rows:
        m, s = score(words, r["name"], r.get("entry") or {}, r.get("description", ""), r.get("group", ""), r.get("about", ""), named)
        if m:
            if bonus is not None:
                s += bonus(r)
            hits.append((r, m, s))
    hits.sort(key=lambda h: (-h[1], -h[2], h[0]["name"]))
    return hits


# ---- now ----------------------------------------------------------------------------------

def bench_of(type_id, proxy_module=None):
    """The workbench an object belongs to, by its proxy's module (a
    Python-made object) and then its type; None when neither says."""
    mod = str(proxy_module or "")
    if mod:
        head = mod.split(".")[0]
        for k, wb in PROXY_BENCH:
            if head == k or head.startswith(k):
                return wb
    for k, wb in TYPE_BENCH:
        if str(type_id or "").startswith(k):
            return wb
    return None


OPENERS = {"Std_New", "Std_Open", "Std_Import"}


def fits(e, state, keys=()):
    """(score, [why]) of how well a tool fits the present state.

    state: window (bool), workbench (the active one's class name),
    editing ("sketch" when one is open in edit), selBenches (workbenches of
    the selected objects), selSubs ("edge", "face", "vertex" picked),
    docBenches (workbenches of the document's objects; None: no document),
    active {command: True | False} as FreeCAD's commands report themselves
    (a command missing from it is unknown here and counts for nothing).
    keys: the tool's input names (an "edges" input fits picked edges)."""
    wb = e.get("workbench")
    why, total = [], 0.0
    known = [state.get("active", {}).get(c) for c in e.get("commands") or []]
    known = [k for k in known if k is not None]
    if any(known):
        total += 6
        why.append("command active")
    elif known:
        total -= 3
        why.append("command inactive")
    if wb and wb == state.get("workbench"):
        total += 4
        why.append("workbench")
    if state.get("editing") == "sketch" and wb == "SketcherWorkbench":
        total += 6
        why.append("sketch open")
    if wb and wb in (state.get("selBenches") or ()):
        total += 3
        why.append("selection")
    keys = {str(k).lower() for k in keys}
    for sub in state.get("selSubs") or ():
        if sub in keys or sub + "s" in keys or (sub == "vertex" and "vertices" in keys):
            total += 2
            why.append(f"{sub} picked")
    doc = state.get("docBenches")
    if doc is None:
        if OPENERS & set(e.get("commands") or []):
            total += 5
            why.append("no document")
    elif wb and wb in doc:
        total += 2 if state.get("window") else 3
        why.append("document")
    return total, why
