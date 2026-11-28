# SPDX-License-Identifier: LGPL-2.1-or-later
# One item for each call, the second line (27 Nov): the tools that took a
# list of objects as an input take one item, and its fields stand beside
# tool. td_cosmetic takes one figure, asm_fits one pair, cam_property_bag one
# value, sheet_table one configuration (add makes each next one), pd_binder
# one face or a list of references. The old list is refused with the flat
# form. The tools whose list is one ordered thing keep it, and LEFT names
# them: a new list of objects in tools.json fails the scan here.
# Three groups of tests:
#   - plain Python (the scan, schemas, the refusals of the check, the words);
#   - each tool on its family's stand-in FreeCAD (a child process for each
#     stand-in, with the prepared documents of the data tests' cases). This
#     is not FreeCAD: see the notes of the stand-in files;
#   - each entry calls only the helpers that its family gives.
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import protocol, runners  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402

# tool -> the list input that went
FLAT = {"td_cosmetic": "items", "asm_fits": "pairs", "cam_property_bag": "properties", "sheet_table": "configs", "pd_binder": None}
# The inputs that are still a list of objects: each is one ordered thing that
# its tool builds in one operation (owner decision open, 27 Nov).
LEFT = ["asm_motion.keys", "bim_layers.layers", "fea_native.heat", "fea_native.potentials", "fea_native.temperatures", "fea_shell.holds",
        "pd_multitransform.steps", "pd_shaft.segments", "td_gdt.frame"]


def _cw(entry):
    """Every word of a tools.json entry: its card and its inputs' meanings (agentlink.tooldata.card_words)."""
    from agentlink.tooldata import card_words
    return card_words(entry)


def _cw_text(entry):
    from agentlink.tooldata import card_text
    return card_text(entry)


def schema(name):
    return runners.tool(name, runners.entries()[name], {}).schema


def refused(name, args):
    try:
        protocol.check_input(schema(name), args, name)
    except ToolError as e:
        return e.message
    return None


def lists_of_objects():
    """Every input in tools.json whose schema is an array of objects, at any depth."""
    def is_obj(s):
        return isinstance(s, dict) and (s.get("type") == "object" or "properties" in s or any(is_obj(x) for x in s.get("anyOf", []) + s.get("oneOf", [])))

    def walk(s, path, out):
        if not isinstance(s, dict):
            return
        if is_obj(s.get("items")):
            out.append(path)
        walk(s.get("items"), path, out)
        for k, v in (s.get("properties") or {}).items():
            walk(v, f"{path}.{k}", out)
        for x in s.get("anyOf", []) + s.get("oneOf", []):
            walk(x, path, out)

    out = []
    for name, e in runners.entries().items():
        for k, v in (e["inputSchema"].get("properties") or {}).items():
            walk(v, f"{name}.{k}", out)
    return sorted(set(out))


# ---- the stand-ins (a child process for each) ----------------------------------------------

# which -> (the stand-in, the cases file, how to call its cases, the family file of each tool)
STANDS = {"td": ("_datatd2_standin", "_datatd2_cases", "techdraw", {"td_cosmetic": "techdraw"}),
          "cam": ("_datatd2_cam_standin", "_datatd2_cases", "cam_more", {"cam_property_bag": "cam_more"}),
          "asm": ("_dataasm_standin", "_dataasm_cases", None, {"asm_fits": "assembly_more"}),
          "sheet": ("_datasheet_standin", "_datasheet_cases", None, {"sheet_table": "sheet"}),
          "pd": ("_datask2_standin", "_datask2_cases", None, {"pd_binder": "feature_more"})}

V = {"view": "Front"}
PA, PB = {"part": "Base", "element": "Face3"}, {"part": "Pin", "element": "Face3"}
MAKE = {"action": "make", "params": ["length", "width"]}
# which -> [(key, tool, the case whose prepared document it runs on, the calls in order)]
RUNS = {
    "td": [
        ("line", "td_cosmetic", "a line", [{**V, "kind": "line", "from": [0, 0, 0], "to": [40, 0, 20]}]),
        ("circle", "td_cosmetic", "a circle", [{**V, "kind": "circle", "center": [20, 0, 10], "radius": 4, "style": "hidden"}]),
        ("centerline", "td_cosmetic", "a centerline, extended", [{**V, "kind": "centerline", "edges": ["Edge1", "Edge3"], "extend": 5.5}]),
        ("threadEnd", "td_cosmetic", "a tapped hole, end on, pitch given", [{**V, "kind": "thread", "circle": "Edge4", "internal": True, "pitch": 1.25}]),
        ("threadSide", "td_cosmetic", "a thread, side view", [{**V, "kind": "thread", "edges": ["Edge0", "Edge2"]}]),
        ("three", "td_cosmetic", "a line", [{**V, "kind": "line", "from": [0, 0, 0], "to": [40, 0, 20]}, {**V, "kind": "centerline", "edges": ["Edge0", "Edge2"]},
                                             {**V, "kind": "circle", "center": [20, 0, 10], "radius": 4}]),
        ("cleared", "td_cosmetic", "the earlier ones cleared", [{**V, "clear": True, "kind": "circle", "center": [20, 0, 10], "radius": 2}]),
        ("clearOnly", "td_cosmetic", "cleared, nothing new", [{**V, "clear": True}]),
        ("noKind", "td_cosmetic", "nothing asked", [dict(V)]),
        ("badKind", "td_cosmetic", "a kind it has not", [{**V, "kind": "arc"}]),
        ("noRadius", "td_cosmetic", "a circle of no radius", [{**V, "kind": "circle", "center": [20, 0, 10]}]),
        ("oneEdge", "td_cosmetic", "a centerline of one edge", [{**V, "kind": "centerline", "edges": ["Edge0"]}]),
    ],
    "cam": [
        ("three", "cam_property_bag", "three properties, named", [
            {"name": "Shop values", "property": "Depth", "type": "Length", "value": 4.5, "group": "Cut", "info": "how deep"},
            {"name": "Shop values", "property": "Passes", "type": "Integer", "value": 3},
            {"name": "Shop values", "property": "Spare"}]),
        ("empty", "cam_property_bag", "empty", [{}]),
        ("taken", "cam_property_bag", "a name taken", [{"name": "Plate", "property": "A", "type": "Bool", "value": True}]),
        ("twice", "cam_property_bag", "a name twice", [{"name": "Bag", "property": "Depth"}, {"name": "Bag", "property": "Depth", "type": "Length"}]),
        ("space", "cam_property_bag", "a name with a space", [{"property": "cut depth"}]),
        ("noName", "cam_property_bag", "a property with no name", [{"type": "Float"}]),
        ("badType", "cam_property_bag", "a type it has not", [{"property": "Tilt", "type": "Vector"}]),
        ("noFit", "cam_property_bag", "a value that does not fit", [{"property": "Passes", "type": "Integer", "value": 2.5}]),
        ("noCam", "cam_property_bag", "no CAM here", [{"property": "Depth"}]),
    ],
    "asm": [
        ("pair", "asm_fits", "held to H8/f7 at a size, by pairs", [{"a": PA, "b": PB, "fit": "H8/f7", "size": 10, "assembly": "Assembly"}]),
        ("pairFace", "asm_fits", "pairs, the fit of the call", [{"a": PA, "b": {"part": "Pin"}, "fit": "H7/p6"}]),
        ("joint", "asm_fits", "held to H7/g6", [{"fit": "H7/g6", "joint": "Cylindrical"}]),
        ("noPart", "asm_fits", "a pair with no part", [{"a": PA, "b": {"element": "Face3"}}]),
        ("onlyA", "asm_fits", "a pair with no part", [{"a": PA}]),
        ("noJoints", "asm_fits", "no joints", [{}]),
    ],
    "sheet": [
        ("makeAdd", "sheet_table", "made: a new sheet, the one body its owner", [
            {**MAKE, "config": "small", "values": [10, 5]}, {"action": "add", "config": "big", "values": {"width": "8 mm", "length": 20}}, {"action": "use", "config": "big"}]),
        ("byName", "sheet_table", "made: a new sheet, the one body its owner", [{**MAKE, "config": "small", "values": {"width": 5, "length": 10}}]),
        ("noConfig", "sheet_table", "make: no configs", [{"action": "make", "params": ["length"]}]),
        ("unnamed", "sheet_table", "make: a config unnamed", [{**MAKE, "values": [1, 2]}]),
        ("noValues", "sheet_table", "make: a config unnamed", [{**MAKE, "config": "small"}]),
        ("short", "sheet_table", "make: a config short of a value", [{**MAKE, "config": "small", "values": {"length": 1}}]),
        ("tooMany", "sheet_table", "make: a config with too many", [{**MAKE, "config": "small", "values": [1, 2, 3]}]),
        ("none", "sheet_table", "none to list", [{}]),
    ],
    "pd": [
        ("one", "pd_binder", "two faces of a feature", [{"body": "Cap", "from": "CutterBase", "faces": {"at": [0, 0, 0], "n": 2}}]),
        ("oneRef", "pd_binder", "model call 52", [{"body": "Cap", "from": "Sheet", "faces": "Face1"}]),
        ("refs", "pd_binder", "model call 52", [{"body": "Cap", "from": "Sheet", "faces": ["Face1", "Sheet.Face2"]}]),
        ("whole", "pd_binder", "the whole of it, frozen, named", [{"body": "Cap", "from": "Sheet", "frozen": True, "name": "Ref"}]),
        ("objects", "pd_binder", "two faces of a feature", [{"body": "Cap", "from": "CutterBase", "faces": [{"at": [0, 0, 0], "n": 2}, {"at": [0, 0, 0], "n": 3}]}]),
        ("mixed", "pd_binder", "model call 52", [{"body": "Cap", "from": "Sheet", "faces": ["Face1", {"at": [75, 60, 0]}]}]),
        ("number", "pd_binder", "model call 52", [{"body": "Cap", "from": "Sheet", "faces": [3]}]),
        ("noFace", "pd_binder", "model call 52", [{"body": "Cap", "from": "Sheet", "faces": ["Face99"]}]),
        ("otherObject", "pd_binder", "model call 52", [{"body": "Cap", "from": "Sheet", "faces": ["Cap.Face1"]}]),
        ("edge", "pd_binder", "model call 52", [{"body": "Cap", "from": "Sheet", "faces": ["Edge1"]}]),
    ],
}


def _child(which):
    import importlib
    import tempfile

    standin, cases_file, file_arg, where = STANDS[which]
    fc = importlib.import_module(standin).install()
    cases_mod = importlib.import_module(cases_file)
    mods = {f: importlib.import_module(f"agentlink.families.{f}") for f in set(where.values())}
    # What each family gives its entries (runners.tools is called with the helpers).
    seen, real = {}, runners.tools

    def spy(group, session, helpers, data=None, family=None):
        seen.setdefault((group, family), {}).update(helpers)
        return real(group, session, helpers, data, family)

    runners.tools = spy
    for m in mods.values():
        m.tools(fc.Session())
    runners.tools = real
    lost = {}
    for name in where:
        e = runners.entries()[name]
        gone = sorted(runners.calls(e) - set(seen.get((e["group"], e.get("family")), {})))
        if gone:
            lost[name] = gone
    tmp = tempfile.mkdtemp()
    got = cases_mod.cases(file_arg, fc, tmp) if file_arg else cases_mod.cases(fc, tmp, mods, mods)
    prepare = {(tool, case): prep for tool, case, prep, _args in got}
    out = {"lost": lost}
    for key, tool, case, calls in RUNS[which]:
        del fc.trace[:]
        fc.state["flags"] = {}
        if hasattr(fc, "fresh"):
            fc.fresh()
        s = fc.Session(tempfile.mkdtemp())
        prepare[(tool, case)](s)
        fc.trace.append("---- the call")
        t = next(t for t in mods[where[tool]].tools(s) if t.name == tool and t.fn.__module__ == "agentlink.runners")
        results = []
        for args in calls:
            try:
                results.append(["ok", t.fn(json.loads(json.dumps(args)))])
            except ToolError as e:
                results.append(["refused", e.code, e.message])
        text = json.dumps({"results": results, "trace": list(fc.trace), "objects": [o.Label for o in s.doc.Objects]}, ensure_ascii=False, default=repr)
        out[key] = json.loads(text.replace(s.out_dir, "<out>"))
    print(json.dumps(out, ensure_ascii=False))


_stand = {}


def stand(which):
    if which not in _stand:
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "child", which], capture_output=True, text=True, timeout=300, cwd=ROOT)
        if r.returncode != 0:
            raise AssertionError(f"child {which} failed:\n" + r.stderr[-4000:])
        _stand[which] = json.loads(r.stdout.strip().splitlines()[-1])
    return _stand[which]


def said(run, i=0):
    r = run["results"][i]
    return r[2] if r[0] == "refused" else json.dumps(r[1], ensure_ascii=False)


# ---- the scan -----------------------------------------------------------------------------

class Scan(unittest.TestCase):
    def test_the_lists_of_objects_that_are_left_are_the_named_ones(self):
        self.assertEqual(lists_of_objects(), LEFT)

    def test_the_five_have_no_list_of_objects_and_no_old_input(self):
        for name, old in FLAT.items():
            props = schema(name)["properties"]
            if old:
                self.assertNotIn(old, props, name)
            self.assertFalse([p for p in lists_of_objects() if p.startswith(name + ".")], name)
            self.assertIs(schema(name)["additionalProperties"], False, name)

    def test_the_snapshot_file_is_the_data(self):
        import _flat_1127b
        import _meant

        self.assertEqual(sorted(_flat_1127b.FLAT), sorted(FLAT))
        for name in FLAT:
            e = runners.entries()[name]
            snap = _flat_1127b.FLAT[name]
            self.assertEqual(_meant.word_gap(_cw_text(e), e["inputSchema"], _meant.words(snap["description"], snap["inputSchema"]), snap["inputSchema"]), ([], []), name)  # the words, as the card and the inputs hold them since 28 Nov
            self.assertEqual(_meant.bare(snap["inputSchema"]), _meant.bare(e["inputSchema"]), name)
            self.assertIn(name, _meant.FLAT_1127)

    def test_each_entry_calls_only_what_its_family_has(self):
        for which in STANDS:
            self.assertEqual(stand(which)["lost"], {}, which)


# ---- the old list is refused with the flat form ---------------------------------------------

class OldListRefused(unittest.TestCase):
    def test_td_cosmetic_items(self):
        msg = refused("td_cosmetic", {"view": "Front", "items": [{"kind": "line", "from": [0, 0, 0], "to": [40, 0, 20]}]})
        self.assertIn("td_cosmetic adds one figure for each call, so it has no items", msg)
        self.assertIn('{ "tool": "td_cosmetic", "view": "Front", "kind": "centerline", "edges": ["Edge1", "Edge3"] }', msg)
        self.assertIn("Several figures are several calls: in a batch, or with each.", msg)

    def test_asm_fits_pairs(self):
        msg = refused("asm_fits", {"pairs": [{"a": PA, "b": PB}]})
        self.assertIn("asm_fits reads one pair for each call, so it has no pairs", msg)
        self.assertIn('{ "tool": "asm_fits", "a": { "part": "Pin", "element": "Face3" }, "b": { "part": "Plate", "element": "Face7" } }', msg)
        self.assertIn("Several pairs are several calls: in a batch, or with each.", msg)

    def test_cam_property_bag_properties(self):
        msg = refused("cam_property_bag", {"name": "Feeds", "properties": [{"name": "depth", "type": "Length", "value": 2}]})
        self.assertIn("cam_property_bag adds one value for each call, so it has no properties", msg)
        self.assertIn('{ "tool": "cam_property_bag", "name": "Feeds", "property": "depth", "type": "Length", "value": 2 }', msg)
        self.assertIn("Several values are several calls with the same name: in a batch, or with each.", msg)

    def test_sheet_table_configs(self):
        msg = refused("sheet_table", {"action": "make", "params": ["length"], "configs": [{"name": "S", "values": [40]}]})
        self.assertIn("sheet_table makes a table with one configuration, so it has no configs", msg)
        self.assertIn('{ "tool": "sheet_table", "action": "make", "params": ["length", "width"], "config": "S", "values": [40, 20] }', msg)
        self.assertIn('{ "tool": "sheet_table", "action": "add", "config": "L", "values": [80, 40] }', msg)

    def test_the_example_of_each_refusal_passes_the_check(self):
        for name, old in FLAT.items():
            if not old:
                continue
            words = protocol.WRONG_FIELD_WORDS[name][old]
            at = 0
            found = 0
            while True:
                at = words.find('{ "tool": "' + name + '"', at)
                if at < 0:
                    break
                step, _end = json.JSONDecoder().raw_decode(words[at:])
                self.assertEqual(step.pop("tool"), name)
                self.assertIsNone(refused(name, step), (name, step))
                found += 1
                at += 1
            self.assertGreaterEqual(found, 1, name)

    def test_pd_binder_a_list_of_face_objects(self):
        got = stand("pd")
        for k in ("objects", "mixed", "number"):
            self.assertEqual(got[k]["results"][0][:2], ["refused", "invalid_input"], k)
            self.assertIn("A list of face objects is not taken", said(got[k]), k)
            self.assertIn('a list of references ["Face3", "Face5"]', said(got[k]), k)
            self.assertNotIn("Binder", " ".join(got[k]["trace"]), k)  # nothing was made


# ---- td_cosmetic ---------------------------------------------------------------------------

class TdCosmetic(unittest.TestCase):
    def test_the_figure_is_flat_typed_inputs_with_a_kind_enum(self):
        sch = schema("td_cosmetic")
        self.assertEqual(sch["properties"]["kind"]["enum"], ["line", "circle", "centerline", "thread"])
        self.assertEqual(sch["required"], ["view"])
        for k in ("style", "from", "to", "center", "radius", "edges", "extend", "circle", "internal", "pitch", "length", "clear"):
            self.assertIn("description", sch["properties"][k], k)
        self.assertIsNone(refused("td_cosmetic", {"view": "Front", "kind": "line", "from": [0, 0, 0], "to": [40, 0, 20]}))
        self.assertEqual(runners.entries()["td_cosmetic"]["kindInputs"], {"line": ["from", "to"], "circle": ["center", "radius"], "centerline": ["edges", "extend"],
                                                                            "thread": ["edges", "circle", "internal", "pitch", "length"]})

    def test_an_input_of_another_kind_is_refused_by_name(self):
        msg = refused("td_cosmetic", {"view": "Front", "kind": "line", "from": [0, 0, 0], "to": [1, 0, 0], "radius": 3})
        self.assertIn("input.radius: not an input of kind line. line takes from, to.", msg)
        self.assertIn("one of line, circle, centerline, thread", refused("td_cosmetic", {"view": "Front", "kind": "arc"}))

    def test_each_kind_makes_what_it_made_as_an_item(self):
        got = stand("td")
        want = {"line": {"kind": "line", "length_mm": 44.721}, "circle": {"kind": "circle", "radius": 4.0}, "centerline": {"kind": "centerline", "length_mm": 31.0},
                "threadEnd": {"kind": "thread", "end": True, "diameter": 11.534, "pitch": 1.25},
                "threadSide": {"kind": "thread", "end": False, "nominal": 20.0, "pitch": 2.5, "note": "M20x2.5"}}
        for k, made in want.items():
            r = got[k]["results"][0]
            self.assertEqual(r[0], "ok", (k, r))
            self.assertEqual(r[1]["made"], [made], k)
            self.assertEqual(r[1]["view"], "Front", k)

    def test_several_figures_are_several_calls_and_the_view_keeps_them(self):
        r = stand("td")["three"]["results"]
        self.assertEqual([x[0] for x in r], ["ok", "ok", "ok"])
        self.assertEqual([x[1]["made"][0]["kind"] for x in r], ["line", "centerline", "circle"])
        self.assertEqual([x[1]["total"] for x in r], [1, 2, 3])

    def test_clear_removes_the_earlier_ones_alone_or_with_a_figure(self):
        got = stand("td")
        self.assertEqual(got["cleared"]["results"][0][1]["total"], 1)
        self.assertEqual(got["cleared"]["results"][0][1]["made"], [{"kind": "circle", "radius": 2.0}])
        self.assertEqual(got["clearOnly"]["results"][0][1]["made"], [])
        self.assertEqual(got["clearOnly"]["results"][0][1]["total"], 0)

    def test_no_kind_is_refused_with_the_kinds(self):
        got = stand("td")
        self.assertEqual(got["noKind"]["results"][0][:2], ["refused", "invalid_input"])
        self.assertIn("kind: line { from, to } | circle { center, radius } | centerline { edges } | thread", said(got["noKind"]))
        self.assertIn("clear: true alone removes the figures.", said(got["noKind"]))
        self.assertEqual(said(got["noRadius"]), "circle: radius mm on the part.")
        self.assertIn("centerline: edges [two lines of the view]", said(got["oneEdge"]))


# ---- asm_fits ------------------------------------------------------------------------------

class AsmFits(unittest.TestCase):
    def test_a_pair_is_a_and_b_beside_tool(self):
        props = schema("asm_fits")["properties"]
        self.assertEqual(list(props), ["assembly", "joint", "a", "b", "fit", "size"])
        self.assertEqual(props["a"]["type"], "object")
        self.assertIsNone(refused("asm_fits", {"a": PA, "b": PB, "fit": "H8/f7", "size": 10}))

    def test_one_pair_reads_the_same_fit(self):
        got = stand("asm")
        fit = got["pair"]["results"][0][1]["fits"]
        self.assertEqual(len(fit), 1)
        self.assertEqual(fit[0]["hole"], {"part": "Base", "diameter": 10.0})
        self.assertEqual(fit[0]["shaft"], {"part": "Pin", "diameter": 9.98})
        self.assertEqual(fit[0]["fit"]["code"], "H8/f7")
        self.assertEqual(got["pair"]["results"][0][1]["verdict"], "pass")
        self.assertEqual(got["pairFace"]["results"][0][1]["fits"][0]["fit"]["type"], "interference")  # b with no element: a face of the part

    def test_the_joint_way_is_as_it_was(self):
        r = stand("asm")["joint"]["results"][0]
        self.assertEqual(r[1]["fits"][0]["joint"], "Cylindrical")
        self.assertEqual(r[1]["verdict"], "fix")

    def test_a_pair_short_of_an_end_is_refused_by_its_name(self):
        got = stand("asm")
        for k in ("noPart", "onlyA"):
            self.assertEqual(got[k]["results"][0], ["refused", "invalid_input", "b: { part, element }. A pair has a and b."], k)
        self.assertEqual(got["noJoints"]["results"][0], ["refused", "not_found", "No joints in Assembly to read fits from: give a and b { part, element } instead."])


# ---- cam_property_bag ----------------------------------------------------------------------

class CamPropertyBag(unittest.TestCase):
    def test_one_value_is_flat_inputs(self):
        props = schema("cam_property_bag")["properties"]
        self.assertEqual(list(props), ["name", "property", "type", "value", "group", "info"])
        self.assertEqual(props["type"]["enum"], ["Float", "Length", "Distance", "Angle", "Integer", "String", "Bool", "Percent", "Speed"])
        self.assertIsNone(refused("cam_property_bag", {"name": "Feeds", "property": "depth", "type": "Length", "value": 2}))
        self.assertIsNone(refused("cam_property_bag", {}))

    def test_several_values_are_several_calls_with_the_same_name(self):
        run = stand("cam")["three"]
        r = run["results"]
        self.assertEqual([x[0] for x in r], ["ok", "ok", "ok"])
        self.assertEqual([x[1]["properties"] for x in r], [["Depth"], ["Passes"], ["Spare"]])
        self.assertEqual([x[1]["bag"] for x in r], ["Shop values"] * 3)
        self.assertEqual([x[1].get("existing") for x in r], [None, True, True])
        self.assertEqual(r[0][1]["use"], "In an operation's expression it is Shop_values.<property>.")
        self.assertEqual(run["objects"].count("Shop values"), 1)  # one bag, not three
        trace = " ".join(run["trace"])
        self.assertEqual(trace.count("PropertyBag.Create("), 1)
        self.assertIn("addCustomProperty('App::PropertyLength', 'Depth', 'Cut', 'how deep')", trace)
        self.assertIn("addCustomProperty('App::PropertyInteger', 'Passes', 'Custom', '')", trace)
        self.assertIn("addCustomProperty('App::PropertyFloat', 'Spare', 'Custom', '')", trace)

    def test_a_bag_with_no_value_and_a_name_that_another_object_has(self):
        got = stand("cam")
        self.assertEqual(got["empty"]["results"][0][1]["properties"], [])
        taken = got["taken"]["results"][0][1]  # Plate is no bag: a new bag, its label made unique
        self.assertEqual(taken["bag"], "Plate 2")
        self.assertNotIn("existing", taken)

    def test_the_refusals(self):
        got = stand("cam")
        self.assertEqual(got["twice"]["results"][1], ["refused", "invalid_state", "Bag has the property Depth already: give another name, or object_set changes its value."])
        for k in ("space", "noName"):
            self.assertEqual(got[k]["results"][0][:2], ["refused", "invalid_input"], k)
            self.assertIn("property: the name of the value (letters and digits, no spaces).", said(got[k]), k)
            self.assertNotIn("PropertyBag.Create(", " ".join(got[k]["trace"]), k)
        self.assertEqual(said(got["badType"]), "type 'Vector': one of Float, Length, Distance, Angle, Integer, String, Bool, Percent, Speed.")
        self.assertEqual(said(got["noFit"]), "value 2.5 does not fit a Integer: type must be int")
        self.assertEqual(got["noCam"]["results"][0][1], "unavailable")


# ---- sheet_table ---------------------------------------------------------------------------

class SheetTable(unittest.TestCase):
    def test_make_takes_one_configuration(self):
        props = schema("sheet_table")["properties"]
        self.assertNotIn("configs", props)
        self.assertIn("config", props)
        self.assertEqual(props["values"]["type"], ["array", "object"])
        self.assertIsNone(refused("sheet_table", {"action": "make", "params": ["length", "width"], "config": "S", "values": [40, 20]}))

    def test_make_then_add_then_use(self):
        r = stand("sheet")["makeAdd"]["results"]
        self.assertEqual([x[0] for x in r], ["ok", "ok", "ok"], r)
        made, added, used = r[0][1], r[1][1], r[2][1]
        self.assertEqual(made["params"], ["length", "width"])
        self.assertEqual(made["configs"], [{"config": "small", "values": {"length": "10 mm", "width": "5 mm"}}])
        self.assertEqual(made["active"], "small")
        self.assertEqual(made["switch"], "Housing.Configuration")
        self.assertEqual(made["newSheet"], "DesignTable")
        self.assertEqual([c["config"] for c in added["configs"]], ["small", "big"])
        self.assertEqual(used["active"], "big")
        self.assertEqual(used["was"], "small")
        self.assertEqual(used["current"], {"length": {"value": 20.0, "unit": "mm"}, "width": {"value": 8.0, "unit": "mm"}})

    def test_values_by_param_name(self):
        r = stand("sheet")["byName"]["results"][0]
        self.assertEqual(r[1]["configs"], [{"config": "small", "values": {"length": "10 mm", "width": "5 mm"}}])

    def test_the_refusals(self):
        got = stand("sheet")
        self.assertEqual(said(got["noConfig"]), "config and values: the name of the first configuration, and its values, one for each param. action add makes each next configuration.")
        self.assertEqual(said(got["unnamed"]), "config: the name of the configuration.")
        self.assertEqual(said(got["noValues"]), "config 'small': values, one per param (2), as a list or { param: value }.")
        self.assertEqual(said(got["short"]), "config 'small': no value for width.")
        self.assertEqual(said(got["tooMany"]), "config 'small': values, one per param (2), as a list or { param: value }.")
        self.assertEqual(got["none"]["results"][0][1]["note"], 'None yet: sheet_table { action: "make", params, config, values }.')


# ---- pd_binder -----------------------------------------------------------------------------

class PdBinder(unittest.TestCase):
    def test_faces_is_one_face_or_a_list_of_references(self):
        f = schema("pd_binder")["properties"]["faces"]
        self.assertEqual([x["type"] for x in f["anyOf"]], ["string", "object", "array"])
        self.assertEqual(f["anyOf"][2]["items"], {"type": "string"})

    def test_one_face_and_a_list_of_references_make_one_binder(self):
        got = stand("pd")
        self.assertEqual(got["one"]["results"][0][1]["faces"], ["Face1"])
        self.assertEqual(got["oneRef"]["results"][0][1]["faces"], ["Face1"])
        refs = got["refs"]
        self.assertEqual(refs["results"][0][1]["faces"], ["Face1", "Face2"])  # "Sheet.Face2": the object's own name before it
        self.assertIn("Binder.Support = [(<Sheet>, ('Face1', 'Face2'))]", refs["trace"])
        self.assertEqual(refs["objects"].count("Sheet binder"), 1)
        self.assertEqual(got["whole"]["results"][0][1]["faces"], "whole")

    def test_a_reference_that_is_no_face_of_the_object_is_refused(self):
        got = stand("pd")
        for k, ref in (("noFace", "Face99"), ("otherObject", "Cap.Face1"), ("edge", "Edge1")):
            self.assertEqual(got[k]["results"][0], ["refused", "not_found", f"faces: {ref!r} is not a face of Sheet. It has Face1 to Face8."], k)


# ---- the texts ------------------------------------------------------------------------------

class Texts(unittest.TestCase):
    def test_no_card_guide_or_data_text_gives_the_old_list(self):
        old = ("items: [{ kind", "pairs: [{", "pairs [{", "properties: [{", "configs: [{", "configs: [")
        bad = []
        for name in FLAT:
            text = _cw(runners.entries()[name]) + json.dumps(runners.entries()[name]["steps"], ensure_ascii=False)
            bad += [f"{name}: {w}" for w in old if w in text]
        d = os.path.join(ROOT, "agentlink", "guides")
        for f in sorted(os.listdir(d)):
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                text = fh.read()
            bad += [f"{f}: {w}" for w in old if w in text]
        self.assertEqual(bad, [])

    def test_each_card_says_one_for_each_call(self):
        said_ = {"td_cosmetic": "One call adds one figure", "asm_fits": "One call reads one pair", "cam_property_bag": "One call adds one value",
                 "sheet_table": "action add makes each next configuration", "pd_binder": 'or a list of references ["Face3", "Face5"]'}
        for name, words in said_.items():
            self.assertIn(words, _cw(runners.entries()[name]), name)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "child":
        _child(sys.argv[2])
    else:
        unittest.main()
