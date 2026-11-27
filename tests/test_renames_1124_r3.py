# SPDX-License-Identifier: LGPL-2.1-or-later
# Rename sets 5, 6, 10 and 11 of 24 Nov (owner rule R5: a renamed input keeps
# no alias). Each set: the old name is refused like any unknown field, and
# the new name works, on the stand-in FreeCAD of the data tests (a case of
# tests/_data*_cases.py, given by the new names).
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

# The data tests' stand-ins: harness -> (its family files, does install() need patch()).
HARNESS = {"datask2": ("param", "feature_more", "sketch_more"), "datapd": ("feature", "std_more", "sketch"),
           "dataasm": ("assembly", "assembly_more"), "datacore": ("view", "unattended", "dev", "doc")}

CHILD = r'''
import importlib, inspect, json, sys, tempfile
sys.path[:0] = [%(root)r, %(here)r]
harness, tool, case, args, probe = json.loads(sys.argv[1])
stand = importlib.import_module("_" + harness + "_standin")
fc = stand.install()
if hasattr(fc, "patch"):
    fc.patch()
from agentlink.protocol import ToolError
files = %(files)r[harness]
new = {m: importlib.import_module("agentlink.families." + m) for m in files}
cases = importlib.import_module("_" + harness + "_cases").cases
n = len(inspect.signature(cases).parameters)
found = [c for c in (cases(fc, tempfile.mkdtemp()) if n == 2 else cases(fc, tempfile.mkdtemp(), new, new)) if c[0] == tool and c[1] == case]
assert len(found) == 1, (tool, case, len(found))
_t, _c, prepare, _a = found[0]
fc.state["flags"] = {}
s = fc.Session(tempfile.mkdtemp())
prepare(s)
t = [x for m in files for x in new[m].tools(s) if x.name == tool and x.fn.__module__ == "agentlink.runners"][0]
try:
    res = ["ok", t.fn(args)]
except ToolError as e:
    res = ["refused", e.code, e.message]
print(json.dumps([res, eval(probe) if probe else None], default=repr))
''' % {"root": ROOT, "here": HERE, "files": HARNESS}


def run_case(harness, tool, case, args, probe=None):
    """The new entry of tool, called with args on the stand-in prepared as the
    named case; with probe (a Python expression over s, the session), also
    its value after the call."""
    r = subprocess.run([sys.executable, "-c", CHILD, json.dumps([harness, tool, case, args, probe])], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    res, seen = json.loads(r.stdout.strip().splitlines()[-1])
    return (res, seen) if probe else res


def checked(tool, args):
    """protocol.check_input on the tool's card: the inputs as read, or the refusal's words."""
    schema = runners.entries()[tool]["inputSchema"]
    try:
        a = dict(args)
        protocol.check_input(schema, a, tool)
        return a
    except ToolError as e:
        return e.message


class Base(unittest.TestCase):
    maxDiff = None

    def refused_by_name(self, tool, args, old, new):
        said = checked(tool, args)
        self.assertIsInstance(said, str, f"{tool}: {old} was read")
        self.assertIn(f"input.{old}: not a known field", said)
        self.assertIn(new, said.split("the fields here:")[1])
        props = runners.entries()[tool]["inputSchema"]["properties"]
        self.assertNotIn(old, props)
        self.assertIn(new, props)
        self.assertNotIn(old, protocol.FIELD_ALIASES.get(tool, {}))
        self.assertNotIn(old, protocol.GOES_WITH.get(tool, {}))


class Set5Geometry(Base):
    """geo -> geometry: sketch_extend, sketch_bspline, sketch_edit's keys."""

    def test_old_name_refused(self):
        self.refused_by_name("sketch_extend", {"sketch": "S", "geo": 0, "by": 2}, "geo", "geometry")
        self.refused_by_name("sketch_bspline", {"sketch": "S", "geo": 0, "op": "degree"}, "geo", "geometry")

    def test_new_name_works(self):
        r = run_case("datask2", "sketch_extend", "sketcher call 42", {"sketch": "TourSketch", "geometry": 3, "end": 2, "by": 15.708})
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(r[1]["extended"], 3)
        r = run_case("datask2", "sketch_extend", "geo it has not", {"sketch": "TourSketch", "geometry": 9, "by": 2})
        self.assertEqual(r[0], "refused")
        self.assertTrue(r[2].startswith("geometry: the id of a line"), r)
        r = run_case("datask2", "sketch_bspline", "sketcher call 49", {"sketch": "TourSketch", "geometry": 6, "op": "degree", "by": 1})
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(r[1]["geometry"], 6)
        self.assertNotIn("geo", r[1])

    def test_sketch_edit_keys(self):
        r = run_case("datapd", "sketch_edit", "sketcher call 57", {"sketch": "PlateSketch", "trim": {"geometry": 1, "at": [-13, 0]}})
        self.assertEqual(r[0], "ok", r)
        r = run_case("datapd", "sketch_edit", "sketcher call 44", {"sketch": "PlateSketch", "mirror": {"geometry": [4], "about": "y"}})
        self.assertEqual(r[0], "ok", r)
        # The old key is not read: nothing to mirror.
        r = run_case("datapd", "sketch_edit", "sketcher call 44", {"sketch": "PlateSketch", "mirror": {"geos": [4], "about": "y"}})
        self.assertEqual(r[:2], ["refused", "invalid_input"])
        self.assertIn("mirror.geometry", r[2])
        d = runners.entries()["sketch_edit"]["description"]
        self.assertNotRegex(d, r"\bgeos?\b")



class Set6Reversed(Base):
    """flip -> reversed (sketch_new, sketch_attach); asm_joint reverse -> reversed."""

    def test_old_name_refused(self):
        self.refused_by_name("sketch_new", {"plane": "XY", "flip": True}, "flip", "reversed")
        self.refused_by_name("sketch_attach", {"sketch": "S", "plane": "XY", "flip": True}, "flip", "reversed")
        self.refused_by_name("asm_joint", {"kind": "fixed", "a": {}, "b": {}, "reverse": True}, "reverse", "reversed")

    def test_new_name_works(self):
        top = "[o for o in s.doc.Objects if o.Label == %r][0].MapReversed"
        r, rev = run_case("datapd", "sketch_new", "on a datum plane, flipped, a name taken", {"plane": "Mid", "reversed": True, "name": "Top"},
                          "s.doc.Objects[-1].MapReversed")
        self.assertEqual(r[0], "ok", r)
        self.assertIs(rev, True)
        r, rev = run_case("datask2", "sketch_attach", "flipped and turned on a later feature's face",
                          {"sketch": "Top", "plane": "Pad.Face3", "reversed": True, "rotate": 45}, top % "Top")
        self.assertEqual(r[0], "ok", r)
        self.assertIs(rev, True)
        j = {"kind": "fixed", "a": {"part": "Base", "element": "Face1"}, "b": {"part": "Lid", "element": "Face2"}}
        r = run_case("dataasm", "asm_joint", "reversed", dict(j, reversed=True))
        self.assertEqual(r[0], "ok", r)
        self.assertIs(r[1]["flipped"], True)
        r = run_case("dataasm", "asm_joint", "reversed", dict(j, keep=True, reversed=True))
        self.assertEqual(r[:2], ["refused", "invalid_input"])
        self.assertIn("not with reversed or autoFlip", r[2])

    def test_no_old_word_in_the_cards(self):
        for n in ("sketch_new", "sketch_attach"):
            self.assertNotRegex(runners.entries()[n]["description"], r"\bflip\b", n)
        self.assertNotRegex(runners.entries()["asm_joint"]["description"], r"\breverse\b")



class Set10Values(Base):
    """One property map, values: feature_edit set, varset_set/new properties; object_set values only."""

    def test_old_name_refused(self):
        self.refused_by_name("feature_edit", {"feature": "Pad", "set": {"Length": 20}}, "set", "values")
        self.refused_by_name("varset_set", {"properties": {"size": "60 mm"}}, "properties", "values")
        self.refused_by_name("varset_new", {"name": "Dims", "properties": {"size": "60 mm"}}, "properties", "values")
        for old in ("set", "properties", "props", "property", "value"):
            self.refused_by_name("object_set", {"object": "Box", old: 1}, old, "values")
        self.assertEqual(list(runners.entries()["object_set"]["inputSchema"]["properties"]), ["object", "values"])
        for t in ("object_set", "varset_set", "varset_new"):
            self.assertNotIn(t, protocol.FIELD_ALIASES)

    def test_new_name_works(self):
        r = run_case("datapd", "feature_edit", "several", {"feature": "pad", "values": {"Length": 20, "Type": "UpToLast", "Reversed": True}})
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(sorted(r[1]["set"]), ["Length", "Reversed", "Type"])
        r = run_case("datapd", "feature_edit", "set not an object", {"feature": "Pad", "values": ["Length", 20]})
        self.assertEqual(r[0], "refused")
        self.assertTrue(r[2].startswith("values: { Property: value }"), r)
        r = run_case("datask2", "varset_new", "sheet call 33", {"name": "NutVars", "values": {"Thickness": "8.4 mm", "Chamfer": "30 deg", "Count": 2}})
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(sorted(r[1]["set"]), ["Chamfer", "Count", "Thickness"])
        r = run_case("datask2", "varset_set", "sheet call 35", {"varset": "Dims", "values": {"size": "10.8 mm"}})
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(list(r[1]["set"]), ["size"])
        r = run_case("datacore", "object_set", "a length and a placement", {"object": "Block", "values": {"Length": 20}})
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(r[1]["set"]["Length"]["to"], 20.0)



class Set11Arguments(Base):
    """args -> arguments: cookbook_run, the examples and the options (nexthint.json)."""

    def test_old_name_refused(self):
        self.refused_by_name("cookbook_run", {"name": "mine", "entry": "mine_fit", "args": {"gap": 1}}, "args", "arguments")

    def test_new_name_works(self):
        from agentlink import cookbook

        e = runners.entries()["cookbook_run"]
        self.assertIn("a.get('arguments')", json.dumps(e["answer"]))
        self.assertEqual(cookbook.check_args({"type": "object", "properties": {"gap": {"type": "number"}}}, {"gap": 1}), {"gap": 1})
        with self.assertRaises(cookbook.Refused) as r:
            cookbook.check_args({"type": "object", "properties": {"gap": {"type": "number"}}, "required": ["gap"]}, {})
        self.assertEqual(r.exception.message, "arguments.gap: necessary for this entry.")
        view = cookbook._entry_view("mine_fit", {"recipe": {"python": {"module": "m", "function": "f", "args": {"type": "object"}}}}, ())
        self.assertEqual(view["arguments"], {"type": "object"})
        self.assertNotIn("args", view)

    def test_the_data_files_say_arguments(self):
        from agentlink import datafiles, examples, nexthint, options

        here = os.path.join(ROOT, "agentlink", "data")
        for f in ("examples.json", "nexthint.json"):
            self.assertEqual(datafiles.check(os.path.join(here, f)), [], f)
            with open(os.path.join(here, f), encoding="utf-8") as fh:
                self.assertNotIn('"args"', fh.read(), f)
        got = examples.for_tool("sketch_new", {"bodyName": "Body"})
        self.assertEqual(got["ready"]["body"], "Body")
        self.assertEqual(nexthint._expr_problems({"suggest": [{"tool": "x", "arguments": {"a": "=__import__('os')"}}]})[0][:14], "x.arguments.a:")
        pub = options.public({"step": 1, "list": [{"n": 1, "tool": "doc_new", "arguments": {}}]})
        self.assertEqual(pub["list"][0], {"n": 1, "step": {"tool": "doc_new"}})  # 27 Nov: an option row is a flat step



class ConstraintAndSketchWords(Base):
    """Local-model runs, 24 Nov: a constraint sent as { a, b, kind }, and
    sketch_add sent body. No aliases: the card types each constraint item,
    and the refusals name the right fields with one worked item."""

    def test_the_card_types_each_constraint(self):
        # 27 Nov: one constraint for each call; its fields are the top-level inputs of the card.
        e = runners.entries()["sketch_constrain"]
        props = e["inputSchema"]["properties"]
        self.assertEqual(list(props), ["sketch", "type", "refs", "value", "name"])
        self.assertEqual(e["inputSchema"]["required"], ["type"])
        self.assertIn("tangent", props["refs"]["description"])
        self.assertIn('Example: { "tool": "sketch_constrain", "type": "tangent", "refs": [0, 1] } makes line 0 tangent to circle 1.', e["description"])
        self.assertNotIn("a", protocol.FIELD_ALIASES.get("sketch_constrain", {}))

    def test_a_b_kind_refused_with_the_fields_and_one_constraint(self):
        m = checked("sketch_constrain", {"sketch": "S", "kind": "tangent", "a": 0, "b": 4})
        self.assertIsInstance(m, str)
        self.assertIn("input.kind: not a known field", m)
        self.assertIn("the fields here: sketch, type, refs, value, name.", m)
        self.assertIn("The constraint's kind goes in type.", m)
        self.assertIn("A constraint has only type, refs, value and name.", m)
        self.assertIn('Example: { "tool": "sketch_constrain", "type": "tangent", "refs": [0, 1] }.', m)

    def test_sketch_add_body_says_it_takes_sketch(self):
        said = checked("sketch_add", {"body": "Body", "kind": "circle", "center": [0, 0], "radius": 5})
        self.assertIsInstance(said, str)
        self.assertIn("input.body: not a known field — the fields here: sketch, kind, from, to, points,", said)
        self.assertIn("sketch_add takes sketch, not body: a sketch is already in a body.", said)
        self.assertIn('Example: { "tool": "sketch_add", "sketch": "Sketch", "kind": "rectangle"', said)
        # Another tool's unknown body is refused as before.
        self.assertNotIn("already in a body", checked("sketch_constrain", {"body": "Body", "type": "horizontal"}))


if __name__ == "__main__":
    unittest.main()
