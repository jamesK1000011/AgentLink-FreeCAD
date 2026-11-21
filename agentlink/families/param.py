# SPDX-License-Identifier: LGPL-2.1-or-later
# Parameters: named values in a spreadsheet "Params" (name in column A, the
# value in B under the name as its alias, a note in C), and properties or
# named sketch constraints bound to expressions over them — FreeCAD's own
# expression engine, so the part stays parametric when opened by hand.

import re

from .. import cells as C
from .. import exprs
from .. import runners
from . import pd_common as pc
from . import picks

GROUP = "param"
INFO = "Named parameters in a Params spreadsheet, and properties or named sketch constraints bound to expressions over them."

SHEET = "Params"
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CELL = re.compile(r"^[A-Za-z]{1,2}[0-9]+$")


# The tools themselves are data (agentlink/data/tools.json, run by
# agentlink/runners.py's steps runner): each entry has the tool's words, its
# checks with their refusals, the order of its steps and its answer. What is
# here is what those entries call by name (docs/data-tools.md).


def sheet(doc, make=False):
    """The document's Params sheet, or None; make: made with its heading
    row (name, value, note) when there is none."""
    for o in doc.Objects:
        if o.TypeId == "Spreadsheet::Sheet" and o.Label == SHEET:
            return o
    if not make:
        return None
    ss = doc.addObject("Spreadsheet::Sheet", SHEET)
    ss.Label = SHEET
    ss.set("A1", "name")
    ss.set("B1", "value")
    ss.set("C1", "note")
    return ss


def rows(ss):
    """The sheet's parameters, (row, name) each, from row 2 down to the
    first empty name."""
    out = []
    r = 2
    while True:
        n = ss.getContents(f"A{r}")
        if not n:
            return out
        out.append((r, n.lstrip("'")))
        r += 1


def value_of(ss, name):
    """(value, unit) of a parameter as the sheet reads it now: a quantity as
    its number and unit; (None, FreeCAD's error) when it does not evaluate."""
    try:
        v = ss.get(name)
    except Exception as e:
        return None, str(e)
    if hasattr(v, "Value"):
        u = str(v).split(" ", 1)
        return round(float(v.Value), 6) + 0.0, (u[1] if len(u) > 1 else "")
    return v, ""


def qualified(doc, expr, keep=()):
    """expr with the Params sheet's names written in full (exprs.qualify):
    "size / 2" -> "Params.size / 2". (expression, {bare: full})."""
    ss = sheet(doc)
    if ss is None or not isinstance(expr, str):
        return expr, {}
    return exprs.qualify(expr, [n for _, n in rows(ss)], ss.Name, keep)


# FreeCAD 1.0's variable sets (App::VarSet): named values as an object's own
# properties, read in expressions as VarSet.size (its name) or by its label.
VARSET = "App::VarSet"
# A VarSet's own properties, not variables.
VARSET_OWN = {"Label", "Label2", "ExpressionEngine", "Visibility", "ExposedVarSet", "Exposed", "Proxy", "Placement"}
LENGTH_UNITS = ("mm", "cm", "dm", "m", "in", "ft", "yd", "mi", "µm", "um", "nm", "km", "\"", "'", "thou", "mil")
ANGLE_UNITS = ("deg", "°", "rad", "gon")


def varsets(doc):
    """The document's variable sets (App::VarSet)."""
    return [o for o in doc.Objects if getattr(o, "TypeId", "") == VARSET]


def varset_vars(o):
    """A VarSet's variables: its properties other than its own."""
    out = []
    for p in o.PropertiesList:
        if p in VARSET_OWN:
            continue
        try:
            if "Hidden" in (o.getPropertyStatus(p) or []):
                continue
        except Exception:
            pass
        out.append(p)
    return out


def var_type(value):
    """(property type, value to set) for a VarSet variable: "55 mm" a
    length, "30 deg" an angle, another quantity a quantity, a whole number
    an integer, a number a float, true/false a bool, other text a string;
    (None, None) for anything else."""
    if isinstance(value, bool):
        return "App::PropertyBool", value
    if isinstance(value, int):
        return "App::PropertyInteger", value
    if isinstance(value, float):
        return "App::PropertyFloat", value
    if not isinstance(value, str):
        return None, None  # none of them: the entry refuses
    m = re.match(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(\S.*)?$", value)
    if m and m.group(2):
        unit = m.group(2).strip()
        if unit in LENGTH_UNITS:
            return "App::PropertyLength" if not value.strip().startswith("-") else "App::PropertyDistance", value
        if unit in ANGLE_UNITS:
            return "App::PropertyAngle", value
        return "App::PropertyQuantity", value
    if m:
        return "App::PropertyFloat", float(m.group(1))
    return "App::PropertyString", value


def var_value(o, p):
    """(value, unit) of a VarSet's variable: a quantity as its number and
    unit, anything else as JSON takes it."""
    v = getattr(o, p)
    if hasattr(v, "Value") and hasattr(v, "Unit"):
        u = str(v).split(" ", 1)
        return round(float(v.Value), 6) + 0.0, (u[1] if len(u) > 1 else "")
    return picks.json_safe(v) if hasattr(picks, "json_safe") else v, ""


def by_varset_label(doc, expr):
    """A VarSet named by its label in an expression (Dims.size) written by
    its object name (VarSet001.size), which FreeCAD's expressions take."""
    if not isinstance(expr, str):
        return expr
    for o in varsets(doc):
        if o.Label != o.Name and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", o.Label):
            expr = re.sub(rf"(?<![A-Za-z0-9_.<]){re.escape(o.Label)}\.", o.Name + ".", expr)
    return expr


def users(doc, ss, name):
    """"Object.Property" of each property whose expression reads the sheet's
    (or the VarSet's) name, by the object's name or its <<label>>."""
    pat = re.compile(rf"(\b{re.escape(ss.Name)}|<<{re.escape(ss.Label)}>>)\.{re.escape(name)}\b")
    out = []
    for o in doc.Objects:
        for path, expr in getattr(o, "ExpressionEngine", []) or []:
            if pat.search(expr):
                out.append(f"{o.Label}.{path.lstrip('.')}")
    return out


def why(doc_, b):
    """A broken object's reason; for a sheet (FreeCAD says only that some
    cell failed) the cells and their own reasons."""
    o = next((x for x in doc_.Objects if x.Label == b["object"]), None)
    if o is not None and o.isDerivedFrom("Spreadsheet::Sheet"):
        from . import sheet as S

        cells_ = [c for c in (S.cell_reading(o, x) for x in S.filled(o)) if "error" in c]
        if cells_:
            return "; ".join(f"{c.get('alias') or c['cell']} ({c['content']}): {c['error']}" for c in cells_[:3])
    return b["error"]


def varset_rows(doc):
    """Each variable set with its variables as param_list answers them:
    name, value, unit, ref (<object>.<name>) and usedBy where anything reads it."""
    rows_ = []
    for o in varsets(doc):
        vs = []
        for p in varset_vars(o):
            val, u = var_value(o, p)
            e = {"name": p, "value": val, "unit": u, "ref": f"{o.Name}.{p}"}
            us = users(doc, o, p)
            if us:
                e["usedBy"] = us
            vs.append(e)
        rows_.append({"varset": o.Label, "object": o.Name, "variables": vs})
    return rows_


def varset_rows_one(o):
    """One variable set's variables: name, value, unit."""
    return [{"name": p, "value": var_value(o, p)[0], "unit": var_value(o, p)[1]} for p in varset_vars(o)]


def prop_at(o, path):
    """The value at a property path as param_bind takes it: "Length", or a
    nested one, "AttachmentOffset.Base.x", "Placement.Rotation.Angle" (an
    angle in degrees, as FreeCAD's expressions give it)."""
    import math

    parts = path.split(".")
    v = getattr(o, parts[0])
    for p in parts[1:]:
        v = getattr(v, p)
    if len(parts) > 1 and parts[-1] == "Angle" and parts[-2] == "Rotation" and isinstance(v, (int, float)):
        return math.degrees(v)
    return v


# Names that are two objects (bicycle test drive, 20 Nov, finding 8): FreeCAD
# reads "Pad.Length" by the object's Name first, so it bound the chainring's
# Pad when the frame's pad had the label "Pad". param_bind refuses a name that
# is one object's Name and another object's Label, and a default name of an
# object in another Body when the target's own Body has one like it.
LABEL_REF = re.compile(r"^<<(.+?)>>\.(.+)$")


def _stem(name):
    return re.sub(r"\d+$", "", name or "")


def _said_as(doc, o):
    """How to name o so that FreeCAD finds only it: <<Label>> when no other
    object has that label, else its Name."""
    n = sum(1 for x in doc.Objects if x.Label == o.Label)
    return f"<<{o.Label}>>" if n == 1 and ">>" not in o.Label else o.Name


def _where(o):
    b = pc.body_of(o) if o.TypeId != "PartDesign::Body" else None
    lab = f", label {o.Label}" if o.Label != o.Name else ""
    return f"{o.Name}{lab}{', in ' + b.Label if b is not None else ''}"


def _clash(doc, word, member, what):
    """The refusal's words when word is one object's Name and another
    object's Label; else None."""
    objs = list(doc.Objects)
    named = next((x for x in objs if x.Name == word), None)
    labelled = [x for x in objs if x.Label == word and x is not named]
    if named is None or not labelled:
        return None
    choices = [named] + labelled
    pick = " or ".join(f"{_said_as(doc, x)}.{member} ({_where(x)})" for x in choices)
    others = ", ".join(_where(x) for x in labelled)
    return (f"{what} {word}.{member}: {word!r} names two objects. It is the name of {_where(named)} and the label of {others}. "
            f"FreeCAD reads a name first, so {word}.{member} is {named.Name}'s. Say which by its label: {pick}.")


def target_object(doc, target):
    """(name as given, property path, object or None, refusal words or None)
    for param_bind's target: "Object.Property" by name or label, or
    "<<Label>>.Property" by label only."""
    m = LABEL_REF.match(target)
    if m:
        label, path = m.group(1), m.group(2)
        return label, path, next((x for x in doc.Objects if x.Label == label), None), None
    oname, path = target.split(".", 1)
    o = next((x for x in doc.Objects if oname in (x.Label, x.Name)), None)
    clash = _clash(doc, oname, path.split(".")[0], "target")
    if clash:
        o = next((x for x in doc.Objects if x.Name == oname), o)
    return oname, path, o, clash


def expression_clash(doc, o, expr):
    """Refusal words when an object the expression names before a "." is
    two objects (a Name and another's Label), or is a default name of an
    object in another Body while o's own Body has one like it; else None."""
    mine = pc.body_of(o) if o is not None and o.TypeId != "PartDesign::Body" else None
    for word, member in exprs.owners(expr):
        said = _clash(doc, word, member, "expression")
        if said:
            return said
        x = next((y for y in doc.Objects if y.Name == word), None)
        if x is None or mine is None or x is o or x.TypeId == "PartDesign::Body":
            continue
        theirs = pc.body_of(x)
        if theirs is None or theirs is mine:
            continue
        like = [y for y in (getattr(mine, "Group", None) or []) if y is not o and y.TypeId == x.TypeId and _stem(y.Name) == _stem(word)]
        if not like:
            continue
        here = " or ".join(f"{_said_as(doc, y)}.{member} ({_where(y)})" for y in like)
        return (f"expression {word}.{member}: {word} is {_where(x)}, but {o.Label} is in {mine.Label}, which has its own: {here}. "
                f"Say which by its label: {here}, or {_said_as(doc, x)}.{member} to keep the one in {theirs.Label}.")
    return None


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": doc, "finish": lambda tool, read: picks.finish(s, tool, read, recompute=False), "snapshot": lambda tool: s.snapshot(tool),
               "steps": lambda: len(s.steps),
               # the guard: what a change newly broke (not what was failing before the call), the references to find again
               "broken": pc.newly_broken, "ref_snap": lambda: [e for b in pc.pd_bodies(doc()) for e in pc.ref_snapshot(b)], "repair_refs": pc.repair_refs,
               "why": lambda b: why(doc(), b), "bodies_now": lambda: [pc.body_reading(b) for b in pc.pd_bodies(doc())],
               # FreeCAD's own
               "setprop": setattr, "getprop": getattr, "num_json": picks.num_json, "prop_at": prop_at,
               # the family's: the Params sheet, the variable sets, names
               "sheet": lambda make=False: sheet(doc(), make), "rows": rows, "value_of": value_of, "users": lambda o, name: users(doc(), o, name),
               "alias_problem": C.alias_problem, "varsets": lambda: varsets(doc()), "varset_vars": varset_vars, "varset_rows": lambda: varset_rows(doc()),
               "varset_rows_one": varset_rows_one, "var_type": var_type, "is_name": lambda n: bool(NAME.match(n)), "is_cell": lambda n: bool(CELL.match(n)),
               "reserved": lambda n: n in C.UNITS or n in C.CONSTANTS, "own_prop": lambda n: n in VARSET_OWN,
               "qualified": lambda expr: qualified(doc(), expr), "by_varset_label": lambda expr: by_varset_label(doc(), expr),
               # on an LCS or an origin, other objects by their label (<<Dims>>.lift): no sub-object lookup
               "doc_refs": lambda o, expr: picks.doc_refs(doc(), o, expr),
               # a name that is two objects (bicycle finding 8)
               "target_object": lambda t: target_object(doc(), t), "expression_clash": lambda o, expr: expression_clash(doc(), o, expr)}
    return runners.tools(GROUP, s, helpers)
