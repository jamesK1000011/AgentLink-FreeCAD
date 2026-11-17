# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datasheet_data.py runs through the old handler and the
# new data entry of each converted tool of families/sheet.py and std_more.py,
# on the stand-in FreeCAD (tests/_datasheet_standin.py): its normal paths and
# each of its refusals.
import os
import random
import sys

# The family files whose tools were converted.
FILES = ("sheet", "std_more")
# Each converted tool and its group.
SHEET = ("sheet_new", "sheet_list", "sheet_read", "sheet_set", "sheet_clear", "sheet_format", "sheet_rows", "sheet_import", "sheet_export", "sheet_chart", "sheet_table")
STD = ("doc_graph", "object_freeze", "units_convert", "object_align", "link_make", "link_edit", "object_duplicate", "doc_merge", "doc_info", "doc_revert", "doc_save_all", "text_document",
       "object_appearance", "scad_tidy", "robot_tool", "sheet_cells")
CONVERTED = {**{k: "sheet" for k in SHEET}, **{k: "std_more" for k in STD}}
# Tools of those files kept as code, and why: none.
KEPT = {}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ("sheet_new", "a name taken"): {"made": "Sizes 2", "name": "Spreadsheet001", "step": 1, "sheet": "Sizes 2"},
    ("sheet_list", "an alias nothing uses"): {"sheets": [{"sheet": "Sizes", "name": "Spreadsheet", "cells": 5, "range": "A1:D3", "aliases": ["length"]}]},
    ("sheet_read", "a range"): {"sheet": "Sizes", "range": "A1:B1", "cells": [{"cell": "A1", "content": "40", "value": 40, "alias": "length"}, {"cell": "B1", "content": "=A1 / 2", "value": 20.0}]},
    ("sheet_read", "a sheet not there"): ["refused", "not_found", "sheet 'Nope': not here — the sheets: Sizes."],
    ("sheet_set", "a bound cell"): ["refused", "invalid_state", "C2 is bound to another range (a design table's active row): change the table's rows, or switch it with sheet_table use."],
    ("sheet_set", "an alias in use elsewhere"): ["refused", "invalid_input", "alias 'length': it already names A1 in Sizes — take it off there first (aliases { \"A1\": \"\" }) or choose another name."],
    ("sheet_set", "a cell that does not evaluate"): ["refused", "failed", "A5 = '=nothere * 2' does not evaluate: name 'nothere' is not defined — nothing was kept."],
    ("sheet_set", "a change that breaks a body"): ["refused", "failed", "That change breaks Block: Curves are disjoint. — nothing was kept."],
    ("sheet_set", "an alias in use: drives and bodies"): {"drives": ["Pad.Length", "Pad.Width"], "sheet": "Sizes", "step": 1},
    ("sheet_clear", "an alias in use"): ["refused", "invalid_state", "A1 holds aliases in use by Pad.Length, Pad.Width: unbind each (param_bind { target, expression: null }) first; force: true clears anyway, "
                                         "and is refused if a user then fails."],
    ("sheet_clear", "a range"): {"cleared": "B1:C2", "cells": 3, "step": 1, "sheet": "Sizes"},
    ("sheet_format", "style, alignment, colours, a unit, sizes"): {"range": "A1:B2", "changed": ["style", "align", "color", "background", "displayUnit", "width", "height"]},
    ("sheet_format", "a merge that loses an alias in use"): ["refused", "invalid_state", "Merging A1:D1 clears all but A1, and cells there hold aliases in use by Pad.Length, Pad.Width: move those cells (sheet_set) "
                                                             "or unbind them first."],
    ("sheet_rows", "two rows in"): {"inserted": "2 rows at 2", "note": "References and aliases moved with the cells, as FreeCAD does by hand.", "step": 1, "sheet": "Sizes"},
    ("sheet_rows", "two columns out"): {"removed": "2 columns at C"},
    ("sheet_import", "a new sheet from a file"): {"from": "<out>/parts.csv", "cells": 6, "range": "A1:B3", "sheet": "parts"},
    ("sheet_import", "a sheet that holds cells"): ["refused", "invalid_state", "Sizes already holds cells: replace: true clears it first, or leave sheet out for a new one."],
    ("sheet_export", "tabs to a path"): {"sheet": "Sizes", "file": "<out>/sub/out.tsv", "rows": 3},
    ("sheet_chart", "bars with labels and names"): {"sheet": "Sizes", "path": "<out>/charts/sizes.svg", "kind": "bar", "series": ["first", "B1:B3"], "points": 3},
    ("sheet_chart", "a kind it has not"): ["refused", "invalid_input", "kind: line, bar or scatter"],
    ("sheet_table", "made: a new sheet, the one body its owner"): {"at": "A2", "switch": "Housing.Configuration", "active": "small", "params": ["length", "width"], "sheet": "DesignTable",
                                                                    "current": {"length": {"value": 10.0, "unit": "mm"}, "width": {"value": 5.0, "unit": "mm"}}},
    ("sheet_table", "use"): {"active": "big", "was": "small", "current": {"length": {"value": 20.0, "unit": "mm"}, "width": {"value": 8.0, "unit": "mm"}}, "drives": ["Pad.Length"]},
    ("sheet_table", "use: several tables"): ["refused", "invalid_input", "Several design tables: say which with sheet and at — Table A2, Second A2."],
    ("sheet_table", "add: one value missing"): ["refused", "invalid_input", "values: none for length."],
    ("doc_graph", "drawn"): {"objects": 3, "links": 2, "roots": ["Block", "Fused", "Pin"], "uses": {"Fused": ["Block", "Pin"]}, "path": "<out>/model.dot", "svg": "<out>/model.svg"},
    ("object_freeze", "thawed, one that will not; recomputes on"): {"skipRecompute": False, "unfrozen": ["Block"], "not": ["Pin"], "note": "Unfrozen: recompute { force: true } brings them up to date."},
    ("units_convert", "inches to mm"): {"value": "2.5 in", "to": "mm", "result": 63.5, "text": "63.5 mm"},
    ("units_convert", "different kinds"): ["refused", "invalid_input", "45 deg and mm measure different things (Angle vs Length): to must be a unit of the same kind as value's."],
    ("object_align", "four pairs that do not agree"): {"object": "Block", "pairs": 4, "rms": 0.8398, "worst": 1.4492},
    ("object_align", "points on one line"): ["refused", "invalid_input", "pairs: the from-points lie on one line; three that are not in a line set the turn."],
    ("link_make", "placed, named, an array"): {"link": "Second", "name": "Link", "to": "Block", "count": 3, "placement": {"at": [20.0, 0.0, 0.0], "axis": [0.0, 0.0, 1.0], "angle": 0.0}},
    ("link_make", "a group"): {"link": "Kit", "kind": "group", "elements": ["Block", "Pin"]},
    ("link_edit", "unlink"): {"copy": "Block 2", "from": "Block", "volume": 1000.0},
    ("link_edit", "import_all"): {"imported": ["Imported"], "links": ["Far link"]},
    ("object_duplicate", "the shape alone"): {"duplicated": [{"from": "Block", "copy": "Block copy", "simple": True}]},
    ("doc_merge", "merged, the records left behind"): {"merged": "part.FCStd", "count": 1, "objects": ["Bracket"], "errors": []},
    ("doc_merge", "more than it lists"): {"count": 45, "more": 5},
    ("doc_info", "set"): {"author": "A maker", "comment": "made here", "label": "Bracket", "uid": "uid-1", "bytes": 0},
    ("doc_revert", "back to the file"): {"document": "Reopened", "reverted": "<out>/saved.FCStd", "objects": 1},
    ("doc_save_all", "one saved, one never"): {"saved": ["/somewhere/model.FCStd"], "neverSaved": ["Other part"]},
    ("text_document", "found, a line added"): {"text": "Log", "chars": 12, "lines": 2},
    ("object_appearance", "a colour, faces and transparency in the window"): {"set": [{"object": "Block", "color": "#0080ff", "faces": 2, "transparency": 40, "shown": True}]},
    ("scad_tidy", "colour coded, one that is not valid"): {"coloured": [{"object": "Block", "is": "invalid", "color": "#ff0000"}]},
    ("scad_tidy", "explode"): {"exploded": [{"from": "Fused", "pieces": ["Block", "Pin"]}]},
    ("scad_tidy", "replace: nothing it uses"): ["refused", "invalid_input", "old: Block does not use Pin (it uses nothing)."],
    ("robot_tool", "not a robot"): ["refused", "invalid_input", "robot: Block is not a robot (Part::Feature) — robot_new makes one."],
    ("sheet_cells", "a range split"): ["refused", "invalid_input", "split C1:D1: one cell of the merged one, \"C1\"."],
}
# Refusals written in the data that no case here reaches: none.
UNREACHED = []


def cases(fc, tmp, old, new):
    scad = {k: sys.modules[k] for k in ("expandplacements", "OpenSCADFeatures", "OpenSCADUtils", "replaceobj")}

    def prep(*fns, **flags):
        def prepare(s):
            fc.fc.GuiUp = False
            random.seed(7)
            fc.state["flags"].update(flags)
            fc.state.pop("docs", None)
            sys.modules.update(scad)
            for fn in fns:
                fn(s)
        return prepare

    def block(s):
        return fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10)))

    def sizes(s):
        return fc.sheet("Sizes", {"A1": "40", "B1": "=A1 / 2", "C1": "=3 mm", "D1": "'note", "A3": "=A1 + nothere"}, {"length": "A1"})

    def plain(s):
        return fc.sheet("Sizes", {"A1": "40", "B1": "=A1 / 2", "C1": "=3 mm", "D1": "'note", "A2": "1", "B2": "2.5", "A3": "3", "B3": "7"}, {"length": "A1"})

    def other(s):
        return fc.sheet("Other", {"A1": "1"})

    def pad(s):
        o = fc.body("Pad", fc.solid("pad", (0, 0, 0), (40, 10, 5)), type_="PartDesign::Body", name="Pad")
        o.__dict__["ExpressionEngine"] = [("Length", "Spreadsheet.length * 2"), (".Width", "<<Sizes>>.length")]
        return o

    def params(s):
        ss = fc.sheet("Params", {"A1": "name", "B1": "value", "A2": "size", "B2": "12", "A3": "depth", "B3": "4"}, {"size": "B2", "depth": "B3"})
        ss.__dict__["Name"] = "Params"
        return ss

    def body(s):
        return fc.body("Housing", fc.solid("housing", (0, 0, 0), (10, 10, 10)), type_="PartDesign::Body", name="Body")

    def table(s, label="Table", owner=None, at_col="A"):
        """A design table as sheet_table make leaves it: two parameters, two configurations, the first on."""
        o = owner or body(s)
        o.__dict__.update(enums={"Configuration": ["small", "big"]}, Configuration="small")
        ss = fc.sheet(label, {"A1": "'configuration", "B1": "'length", "C1": "'width", "A2": f"=hiddenref({o.Name}.Configuration.String)",
                              "A3": "'small", "B3": "=10 mm", "C3": "=5 mm", "A4": "'big", "B4": "=20 mm", "C4": "=8 mm"}, {"length": "B2", "width": "C2"})
        ss.__dict__["ExpressionEngine"] = [(".cells.Bind.B2.C2", f"tuple(.cells; <<B>> + str(hiddenref({o.Name}.Configuration) + 3); <<C>> + str(hiddenref({o.Name}.Configuration) + 3))")]
        return ss

    def two_tables(s):
        table(s)
        g = fc.state["doc"].new("App::DocumentObjectGroup", "Group")
        table(s, "Second", g).__dict__["Name"] = "Spreadsheet001"

    def many(s):
        fc.sheet("Big", {f"A{i}": str(i) for i in range(1, 421)})

    def csv(name, text):
        def write(s):
            with open(os.path.join(s.out_dir, name), "w", encoding="utf-8") as f:
                f.write(text)
        return write

    BROKEN_SHEET = {"invalid_types": ("Spreadsheet::Sheet",)}
    T = "sheet_new"
    yield T, "plain", prep(), {}
    yield T, "named", prep(), {"name": "Sizes"}
    yield T, "a name taken", prep(sizes), {"name": "Sizes"}
    yield T, "a name FreeCAD would not keep", prep(), {"name": "a/b"}

    T = "sheet_list"
    yield T, "none", prep(block), {}
    yield T, "sheets, aliases in use, a table", prep(sizes, pad, other, lambda s: table(s, owner=fc.body("Bar", fc.solid("bar", (0, 0, 0), (1, 1, 1)), type_="PartDesign::Body", name="Bar"))), {}
    yield T, "an alias nothing uses", prep(sizes), {}

    T = "sheet_read"
    yield T, "all", prep(sizes), {}
    yield T, "a range", prep(sizes), {"sheet": "Sizes", "range": "a1:b1"}
    yield T, "cells, with their format", prep(sizes, lambda s: s.doc.Objects[0].setStyle("A1", "bold", "replace")), {"cells": ["b1", "A1", "Z9"], "format": True}
    yield T, "a range that is none", prep(sizes), {"range": "A1:"}
    yield T, "a cell that is none", prep(sizes), {"cells": ["AAA1"]}
    yield T, "no sheet", prep(block), {}
    yield T, "two sheets, none named", prep(sizes, other), {}
    yield T, "by another case", prep(sizes, other), {"sheet": "other"}
    yield T, "a sheet not there", prep(sizes), {"sheet": "Nope"}
    yield T, "more than a call answers", prep(many), {}
    yield T, "a design table and its bound row", prep(table), {}
    yield T, "an older FreeCAD's sheet", prep(sizes, no_used_cells=True), {"range": "A1:D1"}

    T = "sheet_set"
    yield T, "cells and an alias", prep(sizes), {"cells": {"a2": 12, "B2": "=A2 * 2", "C2": "10 mm", "D2": "text", "A3": None}, "aliases": {"B2": "width"}}
    yield T, "rows from at, as text", prep(sizes), {"at": "B5", "rows": [["x", "y"], [1, None], [2.0, "=B6 + 1"]], "text": True}
    yield T, "rows that are not rows", prep(sizes), {"rows": [1, 2]}
    yield T, "at that is no cell", prep(sizes), {"at": "5B", "rows": [[1]]}
    yield T, "a cell that is none", prep(sizes), {"cells": {"AAA1": 1}}
    yield T, "nothing", prep(sizes), {"sheet": "Sizes"}
    yield T, "a bound cell", prep(table), {"cells": {"A9": 1, "C2": 4}}
    yield T, "true in a cell", prep(sizes), {"cells": {"A2": True}}
    yield T, "a parameter by its bare name", prep(sizes, params), {"sheet": "Sizes", "cells": {"A2": "=size * 2 + length", "B2": "=<<a>>"}}
    yield T, "in the Params sheet itself", prep(params), {"cells": {"B4": "=size * 2"}}
    yield T, "a formula FreeCAD keeps as text", prep(sizes), {"cells": {"A2": "=((1 + 2"}}
    yield T, "an alias that is a unit", prep(sizes), {"aliases": {"B1": "mm"}}
    yield T, "an alias in use elsewhere", prep(sizes), {"aliases": {"B1": "length"}}
    yield T, "an alias set again on its cell, one removed", prep(sizes), {"aliases": {"A1": "length", "B1": ""}}
    yield T, "an alias that is a property", prep(sizes), {"aliases": {"B1": "Label"}}
    yield T, "an alias FreeCAD refuses", prep(sizes, alias_refused=("wide",)), {"aliases": {"B1": "wide"}}
    yield T, "a change that breaks the sheet", prep(sizes, **BROKEN_SHEET), {"cells": {"A2": 1}}
    yield T, "a change that breaks it with no cell in error", prep(plain, **BROKEN_SHEET), {"cells": {"A5": 1}}
    yield T, "a change that breaks a body", prep(plain, block, invalid_types=("Part::Feature",)), {"cells": {"A5": 1}}
    yield T, "a cell that does not evaluate", prep(plain), {"cells": {"A5": "=nothere * 2"}}
    yield T, "an alias in use: drives and bodies", prep(plain, pad), {"cells": {"A1": 8}}

    T = "sheet_clear"
    yield T, "a range", prep(plain), {"range": "b1:c2"}
    yield T, "an alias in use", prep(plain, pad), {"range": "A1"}
    yield T, "an alias in use, forced", prep(plain, pad), {"range": "A1", "force": True}
    yield T, "forced, and a user fails", prep(plain, pad, objects_invalid=True), {"range": "A1", "force": True}
    yield T, "more cells than it takes", prep(plain), {"range": "A1:ZZ16384"}
    yield T, "no range", prep(plain), {}

    T = "sheet_format"
    yield T, "style, alignment, colours, a unit, sizes", prep(plain), {"range": "A1:B2", "style": ["bold", "italic"], "align": ["center", "top"], "color": "#ff0000", "background": "#eeeeee80",
                                                                      "displayUnit": "cm", "width": 120, "height": 30}
    yield T, "all cleared", prep(plain), {"range": "A1", "style": [], "align": [], "color": None, "background": None, "displayUnit": None}
    yield T, "colour cleared on an older sheet", prep(plain, old_sheet=True), {"range": "A1", "color": None}
    yield T, "one alignment as a word", prep(plain), {"range": "A1", "align": "right"}
    yield T, "a style it has not", prep(plain), {"range": "A1", "style": ["blink"]}
    yield T, "two alignments of a kind", prep(plain), {"range": "A1", "align": ["left", "right"]}
    yield T, "a colour that is none", prep(plain), {"range": "A1", "color": "red"}
    yield T, "a background that is none", prep(plain), {"range": "A1", "background": "#12"}
    yield T, "a unit FreeCAD has not", prep(plain), {"range": "A1", "displayUnit": "furlong"}
    yield T, "too wide", prep(plain), {"range": "A1", "width": 5}
    yield T, "too high", prep(plain), {"range": "A1", "height": 5000}
    yield T, "merged", prep(plain), {"range": "A2:B3", "merge": True}
    yield T, "one cell merged", prep(plain), {"range": "A2", "merge": True}
    yield T, "a merge that loses an alias in use", prep(lambda s: plain(s).setAlias("B1", "length"), pad), {"range": "D1:A1", "merge": True}
    yield T, "split", prep(plain), {"range": "A2:B3", "merge": False}
    yield T, "nothing", prep(plain), {"range": "A1"}
    yield T, "a range too large", prep(plain), {"range": "A1:ZZ16384", "style": ["bold"]}
    yield T, "a format that breaks the sheet", prep(sizes, **BROKEN_SHEET), {"range": "A1", "style": ["bold"]}

    T = "sheet_rows"
    yield T, "two rows in", prep(plain), {"action": "insert", "rows": 2, "count": 2}
    yield T, "a row out", prep(plain), {"action": "remove", "rows": 2}
    yield T, "a column in", prep(plain), {"action": "insert", "columns": "b"}
    yield T, "two columns out", prep(plain), {"action": "remove", "columns": "C", "count": 2}
    yield T, "no action", prep(plain), {"rows": 1}
    yield T, "too many", prep(plain), {"action": "insert", "rows": 1, "count": 5000}
    yield T, "a row past the end", prep(plain), {"action": "insert", "rows": 0}
    yield T, "a column that is none", prep(plain), {"action": "insert", "columns": "A1"}
    yield T, "neither", prep(plain), {"action": "remove"}
    yield T, "a row in use out", prep(plain, pad, objects_invalid=True), {"action": "remove", "rows": 1}

    T = "sheet_import"
    yield T, "a new sheet from a file", prep(csv("parts.csv", "name,size\nbolt,8\nnut,=B2 + 1\n")), {"path": "parts"}
    yield T, "tabs, by the name", prep(csv("parts.tsv", "name\tsize\nbolt\t8\n")), {"path": "parts.tsv"}
    yield T, "semicolons into a sheet, replaced", prep(plain, csv("p.csv", "a;b\n1;2\n")), {"path": "p.csv", "sheet": "Sizes", "replace": True, "delimiter": "semicolon"}
    yield T, "into an empty sheet", prep(lambda s: fc.sheet("Empty"), csv("p.csv", "a,b\n")), {"path": "p.csv", "sheet": "Empty"}
    yield T, "no file", prep(), {"path": "gone.csv"}
    yield T, "no path", prep(), {}
    yield T, "a delimiter it has not", prep(csv("p.csv", "a|b\n")), {"path": "p.csv", "delimiter": "pipe"}
    yield T, "a sheet that holds cells", prep(plain, csv("p.csv", "a,b\n")), {"path": "p.csv", "sheet": "Sizes"}
    yield T, "a file FreeCAD cannot read", prep(csv("p.csv", "a,\"b\n"), import_fails=True), {"path": "p.csv"}
    yield T, "an import that breaks the sheet", prep(csv("p.csv", "=nothere\n"), **BROKEN_SHEET), {"path": "p.csv"}

    T = "sheet_export"
    yield T, "plain", prep(plain), {}
    yield T, "tabs to a path", prep(plain), {"sheet": "Sizes", "path": "sub/out.tsv"}
    yield T, "a delimiter it has not", prep(plain), {"delimiter": "pipe"}
    yield T, "FreeCAD says no", prep(plain, export_fails=True), {}
    yield T, "nothing written", prep(plain, export_writes_nothing=True), {"delimiter": ";"}

    T = "sheet_chart"
    yield T, "a line", prep(plain), {"y": "A1:A3"}
    yield T, "bars with labels and names", prep(plain), {"kind": "bar", "x": "D1:D3", "y": ["A1:A3", "B1:B3"], "names": ["first"], "title": "Sizes", "xlabel": "n", "ylabel": "mm", "path": "charts/sizes"}
    yield T, "a scatter", prep(plain), {"kind": "scatter", "x": "A1:A3", "y": ["B1:B3"], "path": os.path.join(tmp, "scatter.svg")}
    yield T, "a scatter with no x", prep(plain), {"kind": "scatter", "y": ["B1:B3"]}
    yield T, "no y", prep(plain), {"y": []}
    yield T, "a y of text", prep(plain), {"y": ["D1:D3"]}
    yield T, "a y that is no range", prep(plain), {"y": "A1:"}
    yield T, "a kind it has not", prep(plain), {"kind": "pie", "y": "A1:A3"}

    T = "sheet_table"
    CONF = [{"name": "small", "values": [10, 5]}, {"name": "big", "values": {"width": "8 mm", "length": 20}}]
    MAKE = {"action": "make", "params": ["length", "width"], "configs": CONF}
    yield T, "none to list", prep(plain), {}
    yield T, "listed", prep(two_tables, plain), {"action": "list"}
    yield T, "one sheet's listed", prep(two_tables), {"action": "list", "sheet": "Second"}
    yield T, "made: a new sheet, the one body its owner", prep(body), MAKE
    yield T, "made: no body, a group its owner; named", prep(block), {**MAKE, "name": "Variants", "active": "big"}
    yield T, "made: in a sheet, at a cell, units, owner and property named", prep(other, body, block), {**MAKE, "sheet": "Other", "at": "f2", "units": {"length": "cm", "width": ""}, "owner": "Block", "property": "Size"}
    yield T, "made: no CopyOnChange here", prep(body, fail=("setPropertyStatus",)), MAKE
    yield T, "make: no params", prep(body), {"action": "make", "configs": CONF}
    yield T, "make: a param that is a unit", prep(body), {**MAKE, "params": ["mm", "width"]}
    yield T, "make: a param twice", prep(body), {**MAKE, "params": ["width", "width"]}
    yield T, "make: no configs", prep(body), {"action": "make", "params": ["length"]}
    yield T, "make: a config unnamed", prep(body), {**MAKE, "configs": [{"values": [1, 2]}]}
    yield T, "make: a config short of a value", prep(body), {**MAKE, "configs": [{"name": "small", "values": {"length": 1}}]}
    yield T, "make: a config with too many", prep(body), {**MAKE, "configs": [{"name": "small", "values": [1, 2, 3]}]}
    yield T, "make: a config twice", prep(body), {**MAKE, "configs": [CONF[0], CONF[0]]}
    yield T, "make: at that is no cell", prep(body), {**MAKE, "at": "1A"}
    yield T, "make: cells in the way", prep(plain, body), {**MAKE, "sheet": "Sizes"}
    yield T, "make: a param already an alias", prep(plain, body), {**MAKE, "sheet": "Sizes", "at": "F1"}
    yield T, "make: an owner not there", prep(body), {**MAKE, "owner": "Nobody"}
    yield T, "make: the sheet its own owner", prep(plain, body), {**MAKE, "sheet": "Sizes", "at": "F1", "params": ["a1x"], "configs": [{"name": "s", "values": [1]}], "owner": "Sizes"}
    yield T, "make: a property that is no name", prep(body), {**MAKE, "property": "my prop"}
    yield T, "make: a property the owner has", prep(body), {**MAKE, "property": "Label"}
    yield T, "make: true for a value", prep(body), {**MAKE, "configs": [{"name": "small", "values": [True, 2]}]}
    yield T, "make: an alias FreeCAD refuses", prep(body, alias_refused=("width",)), MAKE
    yield T, "make: active not a config", prep(body), {**MAKE, "active": "huge"}
    yield T, "make: the switch does not take", prep(body, enum_refuses=("Configuration",)), MAKE
    yield T, "make: the table breaks a body", prep(body, objects_invalid=True), MAKE
    yield T, "crash: make: a config that is no object", prep(body), {**MAKE, "configs": ["small"]}
    yield T, "use", prep(table, pad), {"action": "use", "config": "big"}
    yield T, "use: at its header cell", prep(two_tables), {"action": "use", "sheet": "Second", "at": "a1", "config": "big"}
    yield T, "use: a config it has not", prep(table), {"action": "use", "config": "huge"}
    yield T, "use: no table", prep(plain), {"action": "use", "config": "big"}
    yield T, "use: several tables", prep(two_tables), {"action": "use", "config": "big"}
    yield T, "use: none at that cell", prep(table), {"action": "use", "at": "F9", "config": "big"}
    yield T, "use: the switch breaks a body", prep(table, objects_invalid=True), {"action": "use", "config": "big"}
    yield T, "add", prep(table), {"action": "add", "config": "mid", "values": [15, "6 mm"]}
    yield T, "add: by name, a unit, a row below in the way", prep(lambda s: table(s).set("A5", "'below")), {"action": "add", "config": "mid", "values": {"width": 6, "length": 15}, "units": {"width": "cm"}}
    yield T, "add: a name it has", prep(table), {"action": "add", "config": "big", "values": [1, 2]}
    yield T, "add: one value missing", prep(table), {"action": "add", "config": "mid", "values": {"width": 6}}
    yield T, "add: too few values", prep(table), {"action": "add", "config": "mid", "values": [1]}
    yield T, "add: no values", prep(table), {"action": "add", "config": "mid"}
    yield T, "crash: add: true for a value", prep(table), {"action": "add", "config": "mid", "values": [True, 2]}
    yield T, "an action it has not", prep(plain), {"action": "drop"}

    # ---- families/std_more.py ------------------------------------------------------------------

    def pin(s):
        return fc.body("Pin", fc.solid("pin", (20, 0, 0), (22, 2, 10)))

    def empty(s):
        return fc.body("Ghost", fc.Shape("nothing", "Compound", null=True, solids=0, shells=0))

    def seen(o):
        v = fc.View(o.Name)
        v.__dict__.update(ShapeColor=(0.5, 0.5, 0.5), DiffuseColor=[], Transparency=0, Visibility=False)
        o.__dict__["ViewObject"] = v
        return o

    def link(s, label="Block link", to=None, **kw):
        to = to or block(s)
        src = to[0] if isinstance(to, tuple) else to
        lk = s.doc.new("App::Link", "Link", LinkedObject=to, ElementList=[], Shape=src.__dict__["Shape"] if "Shape" in src.__dict__ else empty(s).Shape, **kw)
        lk.__dict__.update(Label=label, OutList=[src])
        src.InList.append(lk)
        return lk

    def far_link(s):
        lk = link(s, "Far link", (fc.Obj("Elsewhere", "Part::Feature"), ["Face1"]))
        lk.LinkedObject[0].__dict__["Document"] = object()

    def nothing_link(s):
        lk = s.doc.new("App::Link", "Link", LinkedObject=None, ElementList=[])
        lk.__dict__["Label"] = "Loose"

    def used_link(s):
        lk = link(s)
        g = s.doc.new("App::DocumentObjectGroup", "Group", Group=[lk])
        lk.InList.append(g)

    def fuse(s, type_="Part::Fuse"):
        a, b = seen(block(s)), pin(s)
        f = fc.body("Fused", fc.solid("fused", (0, 0, 0), (22, 10, 10)), type_=type_, name="Fusion", OutList=[a, b])
        f.Placement = fc.fc.Placement(fc.Vec(0, 0, 5))
        return f

    def nested(s):
        f = fuse(s, "Part::Compound")
        top = fc.body("Top", f.Shape, type_="Part::Compound", name="Top", OutList=[f])
        f.InList.append(top)

    def robot(s):
        r = s.doc.new("Robot::RobotObject", "Robot")
        r.__dict__["Label"] = "Arm"

    def saved_doc(s):
        p = os.path.join(s.out_dir, "saved.FCStd")
        open(p, "w").close()
        s.doc.FileName = p

    def docs(s):
        other = type(s.doc)()
        other.Name, other.Label, other.FileName = "Other", "Other part", ""
        s.doc.FileName = "/somewhere/model.FCStd"
        fc.state["docs"] = {"Doc": s.doc, "Other": other}

    def window(s):
        fc.fc.GuiUp = True

    def switch(s):
        s.doc.RecomputesFrozen = False

    def touched(s):
        block(s).__dict__["State"] = ["Touched"]
        pin(s).__dict__["State"] = []

    def fcstd(name="part.FCStd"):
        return csv(name, "")

    T = "doc_graph"
    yield T, "what uses what", prep(fuse), {}
    yield T, "written as .dot", prep(fuse), {"path": "graphs/model"}
    yield T, "drawn, no GraphViz here", prep(fuse), {"svg": True}
    yield T, "drawn", prep(fuse, dot="dot-here"), {"svg": True, "path": "model.dot"}
    yield T, "GraphViz fails", prep(fuse, dot="dot-here", dot_returns=1), {"svg": True}

    T = "object_freeze"
    yield T, "the document's recomputes off", prep(block, switch), {"skipRecompute": True}
    yield T, "no switch on this FreeCAD", prep(block), {"skipRecompute": False}
    yield T, "frozen in the window", prep(block, pin, window), {"objects": ["Block", "Pin"]}
    yield T, "thawed, one that will not; recomputes on", prep(lambda s: block(s).__dict__.update(frozen=True), lambda s: pin(s).__dict__.update(frozen=True), window, switch, will_not_freeze=("Pin",)), \
        {"objects": ["Block", "Pin"], "frozen": False, "skipRecompute": False}
    yield T, "already frozen", prep(lambda s: block(s).__dict__.update(frozen=True), window), {"objects": ["Block"], "frozen": True}
    yield T, "no window", prep(block), {"objects": ["Block"]}
    yield T, "nothing asked", prep(block), {}
    yield T, "an object not there", prep(block, window), {"objects": ["Nope"]}

    T = "units_convert"
    yield T, "inches to mm", prep(), {"value": "2.5 in", "to": "mm"}
    yield T, "a bare number to cm", prep(), {"value": 30, "to": "cm"}
    yield T, "nothing", prep(), {"value": "", "to": "mm"}
    yield T, "no unit", prep(), {"value": "1 mm"}
    yield T, "not a quantity", prep(), {"value": "two inches", "to": "mm"}
    yield T, "a unit FreeCAD has not", prep(), {"value": "1 mm", "to": "furlong"}
    yield T, "different kinds", prep(), {"value": "45 deg", "to": "mm"}
    yield T, "a unit of nothing", prep(), {"value": "1 mm", "to": "nil"}

    T = "object_align"
    A3 = [[[0, 0, 0], [10, 0, 0]], [[1, 0, 0], [10, 1, 0]], [[0, 1, 0], [9, 0, 0]]]
    yield T, "one pair: moved", prep(block), {"object": "Block", "pairs": [[[0, 0, 0], [5, 6, 7]]]}
    yield T, "three pairs: turned", prep(block), {"object": "Block", "pairs": A3}
    yield T, "four pairs that do not agree", prep(block), {"object": "Block", "pairs": A3 + [[[0, 0, 1], [10, 0, 3]]]}
    yield T, "no pairs", prep(block), {"object": "Block", "pairs": []}
    yield T, "no object", prep(block), {"pairs": A3}
    yield T, "pairs that are not numbers", prep(block), {"object": "Block", "pairs": [[["a", 0, 0], [1, 0, 0]]]}
    yield T, "pairs that are not points", prep(block), {"object": "Block", "pairs": [[[0, 0], [1, 0]]]}
    yield T, "points on one line", prep(block), {"object": "Block", "pairs": [[[0, 0, 0], [1, 0, 0]], [[1, 0, 0], [2, 0, 0]], [[2, 0, 0], [3, 0, 0]]]}
    yield T, "an object with no placement", prep(block, no_placement="Block"), {"object": "Block", "pairs": A3}
    yield T, "an object not there", prep(block), {"object": "Nope", "pairs": A3}

    T = "link_make"
    yield T, "a link", prep(block), {"to": "Block"}
    yield T, "placed, named, an array", prep(block), {"to": "Block", "at": [20, 0, 0], "name": "Second", "count": 3}
    yield T, "to an element", prep(block), {"to": "Block.Face1"}
    yield T, "to an element of nothing", prep(empty), {"to": "Ghost.Face1"}
    yield T, "to an element it has not", prep(block), {"to": "Block.Face99"}
    yield T, "a group", prep(block, pin), {"kind": "group", "objects": ["Block", "Pin"], "name": "Kit"}
    yield T, "an empty group", prep(block), {"kind": "group"}
    yield T, "a kind it has not", prep(block), {"kind": "element", "to": "Block"}
    yield T, "a count past the end", prep(block), {"to": "Block", "count": 5000}
    yield T, "a count that is true", prep(block), {"to": "Block", "count": True}
    yield T, "nothing to link", prep(block), {}
    yield T, "an object not there", prep(block), {"to": "Nope"}
    yield T, "a link, the objects not valid", prep(block, invalid_types=("App::Link",)), {"to": "Block"}

    T = "link_edit"
    yield T, "replace", prep(link, pin), {"action": "replace", "link": "Block link", "to": "Pin"}
    yield T, "replace: by itself", prep(link), {"action": "replace", "link": "Block link", "to": "Block link"}
    yield T, "replace: by what is built from it", prep(used_link, lambda s: s.doc.Objects[-1].__dict__.update(OutList=[s.doc.Objects[1]])), {"action": "replace", "link": "Block link", "to": "Group"}
    yield T, "not a link", prep(block), {"action": "replace", "link": "Block", "to": "Block"}
    yield T, "no link named", prep(link), {"action": "unlink"}
    yield T, "unlink", prep(link), {"action": "unlink", "link": "Block link"}
    yield T, "unlink: named, what used it repointed", prep(used_link), {"action": "unlink", "link": "Block link", "name": "Real"}
    yield T, "unlink: a link to nothing", prep(nothing_link), {"action": "unlink", "link": "Loose"}
    yield T, "unlink: no shape", prep(lambda s: link(s, "Ghost link", empty(s))), {"action": "unlink", "link": "Ghost link"}
    yield T, "import_all: none outside", prep(link), {"action": "import_all"}
    yield T, "import_all", prep(link, far_link), {"action": "import_all"}
    yield T, "import: one, FreeCAD answers nothing", prep(far_link, import_gives_none=True), {"action": "import", "links": ["Far link"]}
    yield T, "import: none named", prep(link), {"action": "import"}
    yield T, "an action it has not", prep(link), {"action": "drop", "link": "Block link"}

    T = "object_duplicate"
    yield T, "two copies", prep(block, pin), {"objects": ["Block", "Pin"]}
    yield T, "with what it is built from, named", prep(block), {"objects": "Block", "dependencies": True, "name": "Twin"}
    yield T, "the shape alone", prep(block), {"objects": ["Block"], "simple": True}
    yield T, "none", prep(block), {"objects": []}

    T = "doc_merge"
    yield T, "merged, the records left behind", prep(block, fcstd()), {"path": "part.FCStd"}
    yield T, "more than it lists", prep(fcstd(), merge_brings=[f"Part{i}" for i in range(45)]), {"path": "part.FCStd"}
    yield T, "no path", prep(), {"path": " "}
    yield T, "no file", prep(), {"path": "gone.FCStd"}
    yield T, "not a FreeCAD document", prep(csv("part.step", "")), {"path": "part.step"}
    yield T, "FreeCAD cannot merge it", prep(fcstd(), fail=("mergeProject",)), {"path": "part.FCStd"}
    yield T, "nothing came in", prep(fcstd(), merge_brings=["AgentLinkRecords"]), {"path": "part.FCStd"}
    yield T, "one that came in is broken", prep(fcstd(), objects_invalid=True), {"path": "part.FCStd"}

    T = "doc_info"
    yield T, "read", prep(block), {}
    yield T, "set", prep(block, saved_doc), {"author": "A maker", "comment": "made here", "label": "Bracket"}
    yield T, "the id", prep(block), {"uid": "x"}
    yield T, "a number for text", prep(block), {"company": 5}

    T = "doc_revert"
    yield T, "back to the file", prep(block, saved_doc), {}
    yield T, "never saved", prep(block), {}
    yield T, "a file that is gone", prep(block, lambda s: setattr(s.doc, "FileName", os.path.join(s.out_dir, "gone.FCStd"))), {}

    T = "doc_save_all"
    yield T, "one saved, one never", prep(docs), {}
    yield T, "none with a file", prep(block), {}
    yield T, "all with a file", prep(saved_doc), {}

    T = "text_document"
    yield T, "new, with text", prep(), {"text": "first"}
    yield T, "found, a line added", prep(lambda s: s.doc.new("App::TextDocument", "Text", Text="first").__dict__.update(Label="Log")), {"name": "Log", "text": "second", "append": True}
    yield T, "found, replaced", prep(lambda s: s.doc.new("App::TextDocument", "Text", Text="first").__dict__.update(Label="Notes")), {"text": 12}
    yield T, "read only", prep(), {"name": "Empty"}

    T = "object_appearance"
    yield T, "a colour, no window", prep(block), {"objects": ["Block"], "color": "#ff8000"}
    yield T, "a colour, faces and transparency in the window", prep(lambda s: seen(block(s))), {"objects": ["Block"], "color": [0, 0.5, 1], "faces": {"Face2": "#ff0000", "3": "#00ff00"}, "transparency": 40}
    yield T, "random, twice set", prep(block, lambda s: seen(pin(s)), lambda s: s.doc.Objects[0].addProperty("App::PropertyColor", "AgentLinkColor")), {"objects": ["Block", "Pin"], "random": True}
    yield T, "faces on the view's colour", prep(lambda s: seen(block(s))), {"objects": "Block", "faces": {"Face1": "#0000ff"}}
    yield T, "faces, no window", prep(block), {"objects": "Block", "faces": {"Face1": "#0000ff"}, "transparency": 10.7}
    yield T, "nothing to set", prep(block), {"objects": ["Block"]}
    yield T, "too clear", prep(block), {"objects": ["Block"], "transparency": 140}
    yield T, "faces as a list", prep(block), {"objects": ["Block"], "faces": ["Face1"]}
    yield T, "no faces to colour", prep(empty), {"objects": ["Ghost"], "faces": {"Face1": "#ff0000"}}
    yield T, "a face it has not", prep(block), {"objects": ["Block"], "faces": {"Face9": "#ff0000"}}
    yield T, "a face that is no face", prep(block), {"objects": ["Block"], "faces": {"Edge1": "#ff0000"}}
    yield T, "no objects", prep(block), {"objects": [], "color": "#ff0000"}
    yield T, "a face's colour that is none", prep(block), {"objects": ["Block"], "faces": {"Face1": "red"}}

    T = "scad_tidy"
    yield T, "colour coded, all", prep(touched, empty, lambda s: seen(s.doc.Objects[1])), {"action": "color_code"}
    yield T, "colour coded, one that is not valid", prep(lambda s: block(s).Shape.__dict__.update(valid=False)), {"action": "color_code", "objects": ["Block"]}
    yield T, "explode", prep(fuse), {"action": "explode", "objects": ["Fused"]}
    yield T, "explode: unplaced", prep(lambda s: setattr(fuse(s, "Part::MultiFuse"), "Placement", fc.fc.Placement())), {"action": "explode", "objects": ["Fused"]}
    yield T, "explode: not a fusion", prep(block), {"action": "explode", "objects": ["Block"]}
    yield T, "explode: one that is used", prep(nested), {"action": "explode", "objects": ["Fused"]}
    yield T, "explode: none named", prep(block), {"action": "explode"}
    yield T, "expand placements", prep(fuse), {"action": "expand_placements", "objects": ["Fused"]}
    yield T, "tolerance", prep(lambda s: seen(block(s)), pin), {"action": "tolerance", "objects": ["Block", "Pin"], "vertex": 0.1, "face": 0}
    yield T, "tolerance: below zero", prep(block), {"action": "tolerance", "objects": ["Block"], "edge": -1}
    yield T, "tolerance: no shape", prep(empty), {"action": "tolerance", "objects": ["Ghost"]}
    yield T, "remove subtree", prep(fuse), {"action": "remove_subtree", "objects": ["Fused"]}
    yield T, "replace", prep(fuse, lambda s: fc.body("Peg", fc.solid("peg", (0, 0, 0), (1, 1, 1)))), {"action": "replace", "parent": "Fused", "old": "Pin", "new": "Peg"}
    yield T, "replace: not one it uses", prep(fuse, lambda s: fc.body("Peg", fc.solid("peg", (0, 0, 0), (1, 1, 1)))), {"action": "replace", "parent": "Fused", "old": "Peg", "new": "Pin"}
    yield T, "replace: nothing it uses", prep(block, pin), {"action": "replace", "parent": "Block", "old": "Pin", "new": "Pin"}
    yield T, "replace: a loop", prep(nested), {"action": "replace", "parent": "Fused", "old": "Pin", "new": "Top"}
    yield T, "replace: by itself", prep(fuse), {"action": "replace", "parent": "Fused", "old": "Pin", "new": "Fused"}
    yield T, "an action it has not", prep(block), {"action": "polish"}
    yield T, "crash: no OpenSCAD workbench", prep(fuse, lambda s: sys.modules.pop("expandplacements")), {"action": "expand_placements", "objects": ["Fused"]}

    T = "robot_tool"
    yield T, "a tool shape, placed", prep(robot, pin), {"robot": "Arm", "tool": "Pin", "at": [0, 0, 50]}
    yield T, "a tool shape", prep(robot, pin), {"robot": "Arm", "tool": "Pin"}
    yield T, "not a robot", prep(block, pin), {"robot": "Block", "tool": "Pin"}
    yield T, "a tool with no shape", prep(robot, empty), {"robot": "Arm", "tool": "Ghost"}

    T = "sheet_cells"
    yield T, "merged", prep(plain), {"sheet": "Sizes", "merge": "a2:b3"}
    yield T, "split", prep(plain), {"sheet": "Sizes", "split": "a2"}
    yield T, "both", prep(plain), {"sheet": "Sizes", "merge": "A2:B2", "split": "C1"}
    yield T, "not a sheet", prep(block), {"sheet": "Block", "merge": "A1:B1"}
    yield T, "neither", prep(plain), {"sheet": "Sizes"}
    yield T, "a merge that is no range", prep(plain), {"sheet": "Sizes", "merge": "A1:"}
    yield T, "a split that is no cell", prep(plain), {"sheet": "Sizes", "split": "1A"}
    yield T, "one cell merged", prep(plain), {"sheet": "Sizes", "merge": "A1"}
    yield T, "a range split", prep(plain), {"sheet": "Sizes", "merge": "A1:B1", "split": "C1:D1"}
