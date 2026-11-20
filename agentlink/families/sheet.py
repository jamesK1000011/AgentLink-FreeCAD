# SPDX-License-Identifier: LGPL-2.1-or-later
# Spreadsheets: any cell of any sheet read and written (values, expressions,
# aliases, units), formatted, rows and columns inserted and removed, CSV in
# and out — and design tables, built the way FreeCAD's own "Configuration
# table" dialog builds them (a dynamic enumeration bound to a column of
# configuration names, the active row bound to the chosen one), so a part
# made here switches by hand in FreeCAD too.

import os
import re

from .. import cells as C
from .. import paths
from .. import runners
from ..protocol import ToolError, bad
from . import pd_common as pc
from . import picks

GROUP = "sheet"
INFO = "Spreadsheets: any cell read and written (values, expressions, aliases, units), formatting, rows and columns, CSV import and export, and design tables (configurations) that drive a part."

READ_CAP = 400  # cells one sheet_read answers
RANGE_CAP = 20000  # cells one sheet_clear / sheet_format range may span (a whole column is 16384)
STYLES = ("bold", "italic", "underline")
H_ALIGN = ("left", "center", "right")
V_ALIGN = ("top", "vcenter", "bottom")
CONF_PROP = "Configuration"
CONF_GROUP = "ConfigurationTable"
HIDDEN = re.compile(r"^=\s*hiddenref\(\s*(.+?)\.(\w+)\.String\s*\)\s*$")
BIND = re.compile(r"^\.?cells\.Bind\.([A-Z]+[0-9]+)\.([A-Z]+[0-9]+)$")


def addr_or_refuse(a, what="cell"):
    """A cell's address in capitals without $, or the refusal that says what is wrong with it."""
    try:
        C.parse(a)
    except C.AddressError as e:
        raise bad(f"{what}: {e}.")
    return str(a).upper().replace("$", "")


def range_or_refuse(r, what="range"):
    """A range as "A1:C4" (one cell: "A1"), or the refusal that says what is wrong with it."""
    try:
        a, b = C.parse_range(r)
    except C.AddressError as e:
        raise bad(f"{what}: {e} — \"A1\" or \"A1:C4\".")
    return C.range_text(a, b)


def small_range(rng, tool):
    """rng, refused when it spans more cells than a tool takes at once."""
    if C.size(rng) > RANGE_CAP:
        raise bad(f"range {rng}: {C.size(rng)} cells, more than {tool} takes at once ({RANGE_CAP}) — sheet_read gives the used range; work on that.")
    return rng


# ---- reading a sheet ----


def sheets(doc):
    """The document's spreadsheets."""
    return [o for o in doc.Objects if o.isDerivedFrom("Spreadsheet::Sheet")]  # a BOM is one too


def find(doc, ref):
    """A sheet by label or name (any case), or the only one when none is named."""
    all_ = sheets(doc)
    if ref is None:
        if len(all_) == 1:
            return all_[0]
        if not all_:
            raise ToolError("not_found", "No spreadsheet in the document: sheet_new makes one.")
        raise bad(f"sheet: say which — {', '.join(o.Label for o in all_)}.")
    for o in all_:
        if ref in (o.Label, o.Name):
            return o
    for o in all_:
        if o.Label.lower() == str(ref).lower():
            return o
    raise ToolError("not_found", f"sheet {ref!r}: not here — the sheets: {', '.join(o.Label for o in all_) or 'none (sheet_new)'}.")


def sheet_named(doc, ref):
    """The sheet with that label or name (any case), or None: sheet_table
    make makes a sheet with that label when there is none (test drive of
    20 Nov: sheet: "Sizes" was refused)."""
    try:
        return find(doc, ref)
    except ToolError:
        return None


def filled(ss):
    """The addresses that hold something, row by row."""
    for m in ("getNonEmptyCells", "getUsedCells"):
        if hasattr(ss, m):
            try:
                return sorted({a for a in getattr(ss, m)() if ss.getContents(a)}, key=C.sort_key)
            except Exception:
                pass
    # Older builds: walk outward until a band of empty rows and columns.
    out = []
    for r in range(1, 401):
        for c in range(1, 53):
            a = C.name(r, c)
            if ss.getContents(a):
                out.append(a)
    return out


def value_of(ss, a):
    """(value, unit, error): a cell's computed value as JSON."""
    try:
        v = ss.get(a)
    except Exception as e:
        msg = str(e)
        return None, "", (msg or "does not evaluate")
    if isinstance(v, str) and v.startswith("ERR: "):
        # A cell whose expression failed holds FreeCAD's "ERR: <reason>" as
        # its text (Sheet::recomputeCell): Sheet.get does not raise for it.
        try:
            raw = ss.getContents(a)
        except Exception:
            raw = ""
        if raw.startswith("="):
            return None, "", (v[5:].strip() or "does not evaluate")
    if hasattr(v, "Value") and hasattr(v, "Unit"):
        parts = str(v).split(" ", 1)
        return round(float(v.Value), 6) + 0.0, (parts[1] if len(parts) > 1 else ""), None
    if isinstance(v, bool):
        return bool(v), "", None
    if isinstance(v, float):
        return round(v, 9) + 0.0, "", None
    if isinstance(v, (int, str)):
        return v, "", None
    return str(v), "", None


def cell_reading(ss, a, full=False):
    """One cell as the tools answer it: content, value and unit or error, alias; full: its format too."""
    raw = ss.getContents(a)
    e = {"cell": a, "content": raw}
    if not raw:
        # Nothing in it: Sheet.get raises for an empty cell (FreeCAD keeps no
        # value for one), which is not an error of the cell's.
        e["empty"] = True
    else:
        val, unit, err = value_of(ss, a)
        if err:
            e["error"] = err
        else:
            e["value"] = val
            if unit:
                e["unit"] = unit
    try:
        al = ss.getAlias(a)
    except Exception:
        al = None
    if al:
        e["alias"] = al
    if full:
        for key, getter in (("style", "getStyle"), ("align", "getAlignment")):
            try:
                g = getattr(ss, getter)(a)
            except Exception:
                g = None
            if g:
                e[key] = sorted(str(x) for x in g)
        for key, getter in (("color", "getForeground"), ("background", "getBackground")):
            try:
                g = C.rgba_hex(getattr(ss, getter)(a))
            except Exception:
                g = None
            if g:
                e[key] = g
        try:
            du = ss.getDisplayUnit(a)
        except Exception:
            du = None
        if du:
            e["displayUnit"] = du if isinstance(du, str) else str(du[0] if isinstance(du, (tuple, list)) else du)
    return e


def aliases(ss, addrs):
    """{alias: address} of the cells among addrs that have one."""
    out = {}
    for a in addrs:
        try:
            al = ss.getAlias(a)
        except Exception:
            al = None
        if al:
            out[al] = a
    return out


def bindings(ss):
    """[(from, to, expression)] — ranges bound to other cells."""
    out = []
    for path, expr in getattr(ss, "ExpressionEngine", []) or []:
        m = BIND.match(path.lstrip("."))
        if m:
            out.append((m.group(1), m.group(2), expr))
    return out


def users_of(doc, ss, alias):
    """What reads a sheet's alias in an expression: ["Pad.Length", …]."""
    pat = re.compile(rf"(\b{re.escape(ss.Name)}|<<{re.escape(ss.Label)}>>)\.{re.escape(alias)}\b")
    out = []
    for o in doc.Objects:
        if o is ss:
            continue
        for path, expr in getattr(o, "ExpressionEngine", []) or []:
            if pat.search(expr):
                out.append(f"{o.Label}.{path.lstrip('.')}")
    return out


# ---- design tables ----


def tables(doc, ss):
    """The design tables on a sheet: where each sits, its parameters, its
    configurations and which one is on."""
    out = []
    for a in filled(ss):
        m = HIDDEN.match(ss.getContents(a))
        if not m:
            continue
        owner_ref, prop = m.group(1), m.group(2)
        owner = next((o for o in doc.Objects if owner_ref.strip("<>") in (o.Name, o.Label)), None)
        r, c = C.parse(a)
        params = []
        cc = c + 1
        while r > 1 and cc <= C.MAX_COL and ss.getContents(C.name(r - 1, cc)):
            params.append((C.name(r, cc), ss.getContents(C.name(r - 1, cc)).lstrip("'")))
            cc += 1
        confs = []
        rr = r + 1
        while rr <= C.MAX_ROW and ss.getContents(C.name(rr, c)):
            confs.append((rr, ss.getContents(C.name(rr, c)).lstrip("'")))
            rr += 1
        active = None
        if owner is not None and hasattr(owner, prop):
            try:
                active = getattr(owner, prop)
            except Exception:
                active = None
        items = []
        if owner is not None and hasattr(owner, prop):
            try:
                items = list(owner.getEnumerationsOfProperty(prop) or [])
            except Exception:
                items = []
        out.append({"items": items, "at": a, "owner": owner, "ownerLabel": owner.Label if owner is not None else owner_ref,
                    "property": prop, "params": params, "configs": confs, "active": active})
    return out


def table_reading(ss, t):
    """A design table as the tools answer it: each configuration's values, the active one, what is current."""
    rows = []
    for rr, n in t["configs"]:
        vals = {}
        for j, (_, p) in enumerate(t["params"]):
            v, u, err = value_of(ss, C.name(rr, C.parse(t["at"])[1] + 1 + j))
            if err:
                vals[p] = f"error: {err}"
            elif isinstance(v, float) and u:
                vals[p] = f"{v:g} {u}"
            else:
                vals[p] = v
        rows.append({"config": n, "values": vals})
    act = {}
    for a, p in t["params"]:
        v, u, err = value_of(ss, a)
        act[p] = {"value": v, **({"unit": u} if u else {}), **({"error": err} if err else {})}
    names = [n for _, n in t["configs"]]
    out_of_step = t["items"] and t["items"] != names
    return {**({"switchOffers": t["items"]} if out_of_step else {}), "at": t["at"], "switch": f"{t['ownerLabel']}.{t['property']}", "active": t["active"], "params": [p for _, p in t["params"]],
            "configs": rows, "current": act, "refAs": f"{ss.Name}.<param>"}


def said(fn, *a, **kw):
    """(what a cells function answers, None), or (None, what it says is wrong
    with the address, value or colour): the entry has the refusal's words."""
    try:
        return fn(*a, **kw), None
    except C.AddressError as e:
        return None, str(e)


def alias_cell(ss, al):
    """The cell an alias names in a sheet, or None."""
    try:
        return ss.getCellFromAlias(al)
    except Exception:
        return None


def bind_row(ss, owner, prop, r0, c0, n, first_conf):
    """A design table's active row (under the header at r0, c0; n parameters)
    bound to the row of the configuration the switch owner.prop is on, as
    FreeCAD's own Configuration table dialog writes it."""
    a_from, a_to = C.name(r0 + 1, c0 + 1), C.name(r0 + 1, c0 + n)
    cf, ct = C.col_name(c0 + 1), C.col_name(c0 + n)
    ss.setExpression(f".cells.Bind.{a_from}.{a_to}",
                     f"tuple(.cells; <<{cf}>> + str(hiddenref({owner.Name}.{prop}) + {first_conf}); <<{ct}>> + str(hiddenref({owner.Name}.{prop}) + {first_conf}))")


def line_count(p):
    """How many lines a written text file has."""
    with open(p, encoding="utf-8", errors="replace") as f:
        return len(f.read().splitlines())


def write_text(p, text):
    """text written to the file p."""
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def check(what):
        """Recompute; when the change broke something that was sound before, undo it and refuse, naming the failing cells."""
        doc().recompute()
        b = pc.newly_broken(doc())  # not what was failing before the call
        if not b:
            return
        # A sheet says only that some cell failed: name the cells.
        why = []
        for x in b:
            o = doc().getObject(next((o.Name for o in doc().Objects if o.Label == x["object"]), ""))
            if o is not None and o.TypeId == "Spreadsheet::Sheet":
                bad_cells = [c for c in (cell_reading(o, a) for a in filled(o)) if "error" in c]
                why.append(f"{x['object']} " + "; ".join(f"{c['cell']} ({c['content']}): {c['error']}" for c in bad_cells[:3]) if bad_cells
                           else f"{x['object']}: {x['error']} (no cell reads as an error: cells that depend on each other in a circle are left unevaluated — report_read has FreeCAD's line)")
            else:
                why.append(f"{x['object']}: {x['error']}")
        # Undo here and recompute, so the sheet's values stand as they were
        # (rolling back alone leaves the cells uncomputed).
        doc().abortTransaction()
        doc().recompute()
        raise ToolError("failed", f"{what} breaks " + "; and ".join(why) + " — nothing was kept.")

    def bodies_now():
        """Each PartDesign body's reading now (what a changed cell did to the part)."""
        return [pc.body_reading(b) for b in pc.pd_bodies(doc())]

    def done(tool, out, ss=None):
        """The tail of a changing sheet tool: one snapshot and the step, the sheet's label in the answer."""
        out = picks.finish(s, tool, out, recompute=False)
        if ss is not None:
            out.setdefault("sheet", ss.Label)
        return out

    def qualified(ss, params, body):
        """A formula with the Params sheet's parameters named in full: a
        parameter by its bare name in another sheet's formula is the Params
        sheet's (=size*2 -> =Params.size*2), unless the sheet has an alias of
        that name itself."""
        from . import param as P

        def own(n):
            try:
                return bool(ss.getCellFromAlias(n))
            except Exception:
                return False

        names = [n for _, n in P.rows(params)]
        return "=" + P.exprs.qualify(body[1:], names, params.Name, [n for n in names if own(n)])[0]

    def params_sheet():
        """The Params sheet param_set keeps, or None."""
        from . import param as P

        return P.sheet(doc())

    def path_of(p, ext):
        """A file's path in the session's folder, ext added when it has none."""
        p = paths.local(s, str(p))
        if not os.path.splitext(p)[1]:
            p += ext
        return paths.made(s, p)

    def chart_path(p):
        """Where a chart is written: in the out folder unless absolute, .svg, its folder made."""
        p = p if os.path.isabs(p) else os.path.join(s.out_dir, p)
        if not p.lower().endswith(".svg"):
            p += ".svg"
        paths.made(s, p)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def column(ss, rng):
        """A range's computed values, None for a cell that is empty or fails."""
        vals = []
        for c in C.cells_in(range_or_refuse(rng)):
            v, _u, err = value_of(ss, c)
            vals.append(None if err or v in ("", None) else v)
        return vals

    def chart_svg(series, x, kind, a):
        """(the chart's SVG, None), or (None, why the charts module cannot draw it)."""
        from .. import charts

        try:
            return charts.svg(series, x=x, kind=kind, title=a.get("title", ""), xlabel=a.get("xlabel", ""), ylabel=a.get("ylabel", "")), None
        except ValueError as e:
            return None, str(e)

    def table_at(ss, at):
        """The design table whose active row starts at that cell."""
        return next(t for t in tables(doc(), ss) if t["at"] == at)

    # The tools are data (agentlink/data/tools.json, docs/data-tools.md): the entries call these by name.
    helpers = {"doc": doc, "done": done, "check": check, "unique": s.unique, "find": lambda ref: find(doc(), ref), "sheet_named": lambda ref: sheet_named(doc(), ref), "sheets": lambda: sheets(doc()), "ref_list": picks.ref_list,
               "bodies_now": bodies_now, "users": lambda ss, alias: users_of(doc(), ss, alias), "tables": lambda ss: tables(doc(), ss), "table_at": table_at,
               # reading a sheet
               "filled": filled, "aliases": aliases, "bindings": bindings, "cell_reading": cell_reading, "value_of": value_of, "table_reading": table_reading, "column": column,
               "alias_cell": alias_cell, "call_on": lambda o, method, *args: getattr(o, method)(*args), "params_sheet": params_sheet, "qualified": qualified, "bind_row": bind_row, "set_prop": setattr,
               # addresses and cell contents (agentlink/cells.py)
               "address": addr_or_refuse, "range_of": range_or_refuse, "small_range": small_range, "cells_in": C.cells_in, "parse": C.parse, "parse_range": C.parse_range,
               "range_text": C.range_text, "cell": C.name, "col_name": C.col_name, "offset": C.offset, "bounds": C.bounds, "sort_key": C.sort_key, "alias_problem": C.alias_problem,
               "cell_content": C.content, "content": lambda v, text=False: said(C.content, v, text=text), "grid": lambda at, rows: said(C.grid, at, rows),
               "hex_rgba": lambda v: said(C.hex_rgba, v), "name_ok": lambda t: bool(C.NAME.match(t)), "col_ok": lambda t: bool(C.COL.match(t)), "MAX_ROW": C.MAX_ROW,
               # files
               "DELIM": {"comma": ",", "tab": "\t", "semicolon": ";", ",": ",", "\t": "\t", ";": ";"}, "path_of": path_of, "chart_path": chart_path, "chart_svg": chart_svg,
               "isfile": os.path.isfile, "basename": os.path.basename, "getsize": os.path.getsize, "stem": lambda p: os.path.splitext(os.path.basename(p))[0],
               "folder_for": lambda p: os.makedirs(os.path.dirname(p), exist_ok=True), "line_count": line_count, "write_text": write_text}
    return runners.tools(GROUP, s, helpers)
