# SPDX-License-Identifier: LGPL-2.1-or-later
# Parameters: named values in a spreadsheet "Params" (name in column A, the
# value in B under the name as its alias, a note in C), and properties or
# named sketch constraints bound to expressions over them — FreeCAD's own
# expression engine, so the part stays parametric when opened by hand.

import re

from .. import cells as C
from .. import exprs
from ..protocol import Tool, ToolError
from ..tools import obj
from . import pd_common as pc
from . import picks

GROUP = "param"
INFO = "Named parameters in a Params spreadsheet, and properties or named sketch constraints bound to expressions over them."

SHEET = "Params"
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CELL = re.compile(r"^[A-Za-z]{1,2}[0-9]+$")


def sheet(doc, make=False):
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
    out = []
    r = 2
    while True:
        n = ss.getContents(f"A{r}")
        if not n:
            return out
        out.append((r, n.lstrip("'")))
        r += 1


def value_of(ss, name):
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
    an integer, a number a float, true/false a bool, other text a string."""
    if isinstance(value, bool):
        return "App::PropertyBool", value
    if isinstance(value, int):
        return "App::PropertyInteger", value
    if isinstance(value, float):
        return "App::PropertyFloat", value
    if not isinstance(value, str):
        raise ToolError("invalid_input", f"{value!r}: a number, true/false, text, or a quantity with its unit (\"55 mm\", \"30 deg\").")
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
    pat = re.compile(rf"(\b{re.escape(ss.Name)}|<<{re.escape(ss.Label)}>>)\.{re.escape(name)}\b")
    out = []
    for o in doc.Objects:
        for path, expr in getattr(o, "ExpressionEngine", []) or []:
            if pat.search(expr):
                out.append(f"{o.Label}.{path.lstrip('.')}")
    return out


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    repaired = {}

    def check(doc_, what, refs=None):
        doc_.recompute()
        if refs and pc.newly_broken(doc_):
            found = pc.repair_refs(doc_, refs)
            if found:
                repaired.update(found)
        bad = pc.newly_broken(doc_)  # not what was failing before the call
        if bad:
            raise ToolError("failed", f"{what} breaks {bad[0]['object']}: {why(doc_, bad[0])}" + (f" (and {', '.join(b['object'] for b in bad[1:])})" if len(bad) > 1 else "") + " — nothing was kept. Choose a value the features can take.")

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

    def bodies_now():
        return [pc.body_reading(b) for b in pc.pd_bodies(doc())]

    def param_set(a):
        name = a.get("name")
        prob = C.alias_problem(name)
        if prob:
            # FreeCAD's rules for a cell's alias (PropertySheet::isValidAlias); it answers only "Invalid alias".
            raise ToolError("invalid_input", f"name {name!r}: {prob} — e.g. width, plate_thickness.")
        v = a.get("value")
        unit = a.get("unit", "mm" if isinstance(v, (int, float)) else "")
        if isinstance(v, bool) or not isinstance(v, (int, float, str)):
            raise ToolError("invalid_input", "value: a number (with unit mm, deg or \"\"), or an expression string over other parameters, e.g. \"width / 2\".")
        content = f"={v} {unit}".rstrip() if isinstance(v, (int, float)) else "=" + v.lstrip("=")
        ss = sheet(doc(), make=True)
        refs = [e for b in pc.pd_bodies(doc()) for e in pc.ref_snapshot(b)]
        repaired.clear()
        found = next((r for r, n in rows(ss) if n == name), None)
        new = found is None
        if new:
            found = len(rows(ss)) + 2
            ss.set(f"A{found}", "'" + name)  # as text: FreeCAD reads "inf" or "nan" typed bare as a number
        ss.set(f"B{found}", content)
        lit = content[1:].strip()
        if not (lit.startswith("<<") and lit.endswith(">>")) and ss.getContents(f"B{found}").startswith("'"):
            # Cell::setContent keeps what it cannot parse as text and the sheet stays valid.
            raise ToolError("invalid_input", f"{name} = {v!r}" + (f" {unit}" if unit and isinstance(v, (int, float)) else "") + ": FreeCAD cannot read it as an expression — a number with unit mm | deg | \"\" (or another unit FreeCAD knows: cm, m, in, rad), or a formula over other parameters, \"width / 2\". Nothing was kept.")
        if new:
            try:
                ss.setAlias(f"B{found}", name)
            except Exception as e:
                raise ToolError("invalid_input", f"name {name!r}: FreeCAD refuses it as an alias ({e}) — choose another.")
        if a.get("note") is not None:
            ss.set(f"C{found}", "'" + str(a["note"]))  # text, whatever it reads as
        check(doc(), f"{name} = {v}", refs)
        val, u = value_of(ss, name)
        if val is None:
            raise ToolError("invalid_input", f"{name} = {v!r} does not evaluate: {u} — param_list gives the names to use.")
        s.snapshot("param_set")
        out = {"name": name, "value": val, "unit": u, "ref": f"{ss.Name}.{name}", "new": new, "usedBy": users(doc(), ss, name), "bodies": bodies_now(), "step": len(s.steps)}
        if repaired:
            out["refsFound"] = dict(repaired)
            out["note"] = "The change renamed edges or faces later features use: each was found again by what it is. Check them with view_render."
        return out

    def varset_rows():
        rows_ = []
        for o in varsets(doc()):
            vs = []
            for p in varset_vars(o):
                val, u = var_value(o, p)
                e = {"name": p, "value": val, "unit": u, "ref": f"{o.Name}.{p}"}
                us = users(doc(), o, p)
                if us:
                    e["usedBy"] = us
                vs.append(e)
            rows_.append({"varset": o.Label, "object": o.Name, "variables": vs})
        return rows_

    def param_list(a):
        ss = sheet(doc())
        vsets = varset_rows()
        if ss is None:
            return {"params": [], **({"varsets": vsets} if vsets else {}), "note": "No Params sheet yet: param_set makes it." + (" The variable sets are listed under varsets." if vsets else "")}
        out = []
        for r, n in rows(ss):
            val, u = value_of(ss, n)
            e = {"name": n, "value": val, "unit": u, "content": ss.getContents(f"B{r}").lstrip("=")}
            note = ss.getContents(f"C{r}")
            if note:
                e["note"] = note.lstrip("'")
            us = users(doc(), ss, n)
            if us:
                e["usedBy"] = us
            out.append(e)
        res = {"sheet": ss.Name, "params": out, "refAs": f"{ss.Name}.<name>"}
        if vsets:
            res["varsets"] = vsets
        return res

    def _vs(ref):
        vs = varsets(doc())
        if not vs:
            raise ToolError("not_found", "No variable set here: varset_new { name, properties } makes one.")
        if ref is None:
            if len(vs) == 1:
                return vs[0]
            raise ToolError("invalid_input", f"varset: say which — {', '.join(o.Label for o in vs)}.")
        hit = next((o for o in vs if ref in (o.Label, o.Name)), None)
        if hit is None:
            raise ToolError("not_found", f"varset {ref!r}: the variable sets are {', '.join(o.Label for o in vs)}.")
        return hit

    def _set_vars(o, props, group="Variables"):
        if not isinstance(props, dict) or not props:
            raise ToolError("invalid_input", "properties: { name: value } — \"55 mm\" a length, \"30 deg\" an angle, a number, true/false or text.")
        done = {}
        for name, value in props.items():
            if not isinstance(name, str) or not NAME.match(name) or CELL.match(name):
                raise ToolError("invalid_input", f"properties.{name}: a name of letters, digits and _, not starting with a digit — and not a cell address (A1), which an expression would read as a cell.")
            if name in C.UNITS or name in C.CONSTANTS:
                # FreeCAD's own Add Property dialog refuses these (addProperty
                # from Python does not): <VarSet>.mm would not read as a variable.
                raise ToolError("invalid_input", f"properties.{name}: {name} is a unit or constant in FreeCAD's expressions — a longer name ({name}_value).")
            if name in VARSET_OWN:
                raise ToolError("invalid_input", f"properties.{name}: the VarSet's own property — another name.")
            typ, v = var_type(value)
            new = name not in o.PropertiesList
            if new:
                o.addProperty(typ, name, group, "Set by Agent Link (varset_new / varset_set)")
            try:
                setattr(o, name, v)
            except Exception as e:
                if new:
                    raise ToolError("invalid_input", f"properties.{name} = {value!r}: FreeCAD refuses it as a {typ.split('::')[-1]} ({e}) — a quantity is a number and a unit FreeCAD knows (\"55 mm\", \"2 in\", \"30 deg\"); other text is kept as text.")
                raise ToolError("invalid_input", f"properties.{name} = {value!r}: it is a {o.getTypeIdOfProperty(name)} — give a value of that kind ({e}).")
            done[name] = {"new": new, "type": o.getTypeIdOfProperty(name).split("::")[-1]}
        return done

    def varset_new(a):
        name = a.get("name") or "VarSet"
        if not isinstance(name, str) or not name.strip():
            raise ToolError("invalid_input", "name: the variable set's label (Dims), read in expressions as <Dims>.size.")
        if any(o.Label == name for o in doc().Objects):
            raise ToolError("invalid_input", f"name {name!r}: taken — varset_set adds to an existing set.")
        refs = [e for b in pc.pd_bodies(doc()) for e in pc.ref_snapshot(b)]
        try:
            o = doc().addObject(VARSET, "VarSet")
        except Exception as e:
            raise ToolError("unavailable", f"App::VarSet is FreeCAD 1.0's and later ({e}): param_set keeps parameters in a Params sheet instead.")
        o.Label = name
        try:
            done = _set_vars(o, a.get("properties") or {}, a.get("group") or "Variables") if a.get("properties") else {}
        except ToolError:
            doc().removeObject(o.Name)
            raise
        check(doc(), f"varset {name}", refs)
        s.snapshot("varset_new")
        return {"varset": o.Label, "object": o.Name, "set": done, "variables": varset_rows_one(o), "refAs": f"{o.Name}.<name>" + (f" (or {o.Label}.<name>: param_bind writes it by name)" if o.Label != o.Name else ""), "step": len(s.steps)}

    def varset_rows_one(o):
        return [{"name": p, "value": var_value(o, p)[0], "unit": var_value(o, p)[1]} for p in varset_vars(o)]

    def varset_set(a):
        o = _vs(a.get("varset"))
        refs = [e for b in pc.pd_bodies(doc()) for e in pc.ref_snapshot(b)]
        repaired.clear()
        done = _set_vars(o, a.get("properties"), a.get("group") or "Variables")
        check(doc(), f"varset {o.Label}", refs)
        s.snapshot("varset_set")
        out = {"varset": o.Label, "object": o.Name, "set": done, "variables": varset_rows_one(o), "usedBy": sorted({u for p in done for u in users(doc(), o, p)}), "bodies": bodies_now(), "step": len(s.steps)}
        if repaired:
            out["refsFound"] = dict(repaired)
        return out

    def param_remove(a):
        ss = sheet(doc())
        name = a.get("name")
        r = next((r for r, n in rows(ss) if n == name), None) if ss else None
        if r is None:
            raise ToolError("not_found", f"parameter {name!r}: not here — param_list gives them.")
        us = users(doc(), ss, name)
        if us:
            raise ToolError("invalid_state", f"{name} is used by {', '.join(us)}: param_bind each to null (or another expression) first.")
        ss.setAlias(f"B{r}", "")
        ss.removeRows(str(r), 1)
        check(doc(), f"Removing {name}")
        return picks.finish(s, "param_remove", lambda: {"removed": name, "left": [n for _, n in rows(ss)]}, recompute=False)

    def param_bind(a):
        target = a.get("target")
        if not isinstance(target, str) or "." not in target:
            raise ToolError("invalid_input", "target: \"Object.Property\" (\"Pad.Length\") or \"Sketch.<constraint name>\" (\"Sketch.width\") — the object by its label or name.")
        oname, path = target.split(".", 1)
        o = next((x for x in doc().Objects if oname in (x.Label, x.Name)), None)
        if o is None:
            raise ToolError("not_found", f"{oname!r}: no such object — feature_list names the features.")
        if o.TypeId == "Sketcher::SketchObject" and path.split(".")[0] not in o.PropertiesList:
            names = [c.Name for c in o.Constraints if c.Name]
            if path.startswith("Constraints."):
                path = path.split(".", 1)[1]
            if path not in names:
                raise ToolError("not_found", f"constraint {path!r}: not a named constraint of {o.Label} (a constraint is bound by its name, not its number) — they are: {', '.join(names) or 'none (name one with sketch_constrain or sketch_edit rename)'}.")
            con = next(c for c in o.Constraints if c.Name == path)
            if not getattr(con, "Driving", True):
                # SketchObject::validateExpression: "Reference constraints cannot be set!"
                raise ToolError("invalid_state", f"constraint {path!r} of {o.Label} is a reference (driven) dimension: it only measures, so it cannot be bound — bind a driving dimension instead.")
            path = f"Constraints.{path}"
        elif path.split(".")[0] not in o.PropertiesList:
            raise ToolError("not_found", f"{path}: not a property of {o.Label} — by FreeCAD's own name, as feature_list shows them (Length, Angle, Radius, Offset …)" + ("; a sketch's dimension is bound by its constraint's name." if o.TypeId == "Sketcher::SketchObject" else "."))
        expr = a.get("expression")
        if expr in (None, ""):
            o.setExpression(path, None)
            check(doc(), f"Unbinding {target}")
            return picks.finish(s, "param_bind", lambda: {"target": target, "expression": None, "bodies": bodies_now()}, recompute=False)
        given = str(expr)
        # A parameter by its bare name ("size") is the Params sheet's
        # (Params.size), as param_set answers it; a VarSet by its label
        # (Dims.size) is written by its object's name.
        expr, named = qualified(doc(), by_varset_label(doc(), given))
        try:
            o.evalExpression(expr)
        except Exception as e:
            ss = sheet(doc())
            have = [n for _, n in rows(ss)] if ss else []
            vs = [f"{o.Name}.{p}" for o in varsets(doc()) for p in varset_vars(o)]
            raise ToolError("invalid_input", f"{given!r} does not evaluate: {e} — a parameter by its name ({', '.join(have[:12]) or 'none yet: param_set makes one'}) or as {SHEET}.<name>, any sheet's cell as <Sheet>.<alias> or <Sheet>.A1 (sheet_list)"
                            + (f", or a variable set's: {', '.join(vs[:12])}" if vs else "") + ".")
        try:
            o.setExpression(path, expr)
        except Exception as e:
            raise ToolError("invalid_input", f"{target} = {given!r}: FreeCAD refuses it ({e}) — an expression must not read the thing it sets (a circle), and its unit must suit the property (a length for a length: \"width\", \"2 * 5 mm\").")
        check(doc(), f"Binding {target} to {expr}")
        try:
            now = picks.num_json(o.getDatum(path.split(".", 1)[1])) if path.startswith("Constraints.") else picks.num_json(getattr(o, path))
        except Exception:
            now = None
        out = {"target": target, "expression": expr, "value": now}
        if named:
            out["read"] = {"as": named, "note": "A bare name is the Params sheet's parameter."}
        return picks.finish(s, "param_bind", lambda: {**out, "bodies": bodies_now()}, recompute=False)

    return [
        Tool("param_set", "Set a named parameter in the Params spreadsheet (made when first needed): name (a letter, then letters, digits, _; not a cell address, a unit such as m, mm, s, N, or e / pi), value (a number with unit mm | deg | \"\", default mm; or an expression over others, \"width / 2\"), note. Everything bound to it recomputes; a value that does not evaluate or breaks a feature is refused with FreeCAD's error and nothing kept. Reply: value, unit, ref (Params.<name>), usedBy, bodies.",
             obj({"name": {"type": "string"}, "value": {"type": ["number", "string"]}, "unit": {"type": "string"}, "note": {"type": "string"}}, ["name", "value"]), param_set, changes=True),
        Tool("param_list", "The parameters: name, value, unit, what they are set to, and which properties use them; varsets: each variable set's variables (name, value, unit, ref, usedBy). Changes nothing.", obj({}), param_list),
        Tool("varset_new", "Make a variable set (App::VarSet, FreeCAD 1.0 on): name (its label), properties { size: \"55 mm\" (a length), angle: \"30 deg\", count: 3, ratio: 0.5, on: true, note: \"text\" } as its variables (names: letters, digits, _; not a unit or constant), group (Variables). Expressions read them as <object name>.size (the reply's refAs) — param_bind { target, expression: \"Dims.size\" } takes the label too.",
             obj({"name": {"type": "string"}, "properties": {"type": "object"}, "group": {"type": "string"}}, ["name"]), varset_new, changes=True),
        Tool("varset_set", "Set or add variables of a variable set: varset (its label; may be left out when there is one), properties { name: value } as varset_new takes them (an existing one keeps its kind: a length takes \"60 mm\", not text). Everything bound to them recomputes; a value that breaks a feature is refused and nothing kept. Reply: variables, usedBy, bodies.",
             obj({"varset": {"type": "string"}, "properties": {"type": "object"}, "group": {"type": "string"}}, ["properties"]), varset_set, changes=True),
        Tool("param_remove", "Remove a parameter no property uses (param_list shows usedBy; unbind each with param_bind expression: null first).", obj({"name": {"type": "string"}}, ["name"]), param_remove, changes=True),
        Tool("param_bind", "Bind a property or a named, driving sketch constraint to an expression: target \"Pad.Length\" | \"Sketch.width\" (the constraint's name, not its number), expression \"width\" (a parameter by its name), \"Params.width\", \"<Sheet>.<alias>\", \"Dims.size\" (a variable set's, by its label or name) or \"width / 2 + 1\"; null unbinds (the value stays). One that does not evaluate or breaks a feature is refused, nothing kept. A bound value is then changed by param_set, sheet_set or varset_set, not edited directly. Reply: expression as kept, value, bodies.",
             obj({"target": {"type": "string"}, "expression": {"type": ["string", "null"]}}, ["target", "expression"]), param_bind, changes=True),
    ]
