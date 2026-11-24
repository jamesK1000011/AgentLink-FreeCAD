# SPDX-License-Identifier: LGPL-2.1-or-later
# The findings of the skeleton bicycle build of 20 Nov 2026, on the data
# tests' stand-in FreeCADs in a child process each:
#   1  pd_pipe sweeps along chosen edges of any object (a SubShapeBinder of a
#      skeleton), joined end to end; sketch { circle: { d, wall } } makes the
#      tube's sketch square to the path at its start (attached NormalToEdge),
#      d and wall numbers or expressions; mode and transition passed on;
#   2  shape_query lists the edges and vertices of an object with no solid;
#   3  sheet_table make with sheet: "Sizes" makes that sheet when it is not there;
#   4  object_list type matches a full type by isDerivedFrom too, and label filters.
import json
import os
import subprocess
import sys
import textwrap
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)


def child(standin, family, setup, *bodies):
    """bodies run in a Python of its own on the stand-in FreeCAD standin,
    with run(name, args) calling the family's tool; what it prints last, as JSON."""
    code = textwrap.dedent(f'''
        import json, sys, tempfile
        sys.path[:0] = [{ROOT!r}, {TESTS!r}]
        import {standin} as standin
        fc = standin.install()
        from agentlink.protocol import ToolError
        from agentlink.families import {family} as F
        s = fc.Session(tempfile.mkdtemp())

        def run(name, args):
            t = next(t for t in F.tools(s) if t.name == name)
            try:
                return ["ok", t.fn(json.loads(json.dumps(args)))]
            except ToolError as e:
                return ["refused", e.code, e.message]
    ''') + textwrap.dedent(setup) + "\n" + "\n".join(textwrap.dedent(b) for b in bodies)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


# A body with a solid and a binder of a skeleton: a frame of four lines,
# Edge3 of which runs backwards (its end meets Edge2's end).
PD_SETUP = '''
V = fc.Vec
b = fc.body(s)
fc.feature(s, b, "Pad", "Base")
pts = [V(0, 0, 0), V(100, 0, 0), V(100, 50, 0), V(0, 50, 0)]
edges = [fc.edge(pts[0], pts[1]), fc.edge(pts[1], pts[2]), fc.edge(pts[3], pts[2]), fc.edge(V(300, 0, 0), V(400, 0, 0))]
binder = s.doc.new("PartDesign::SubShapeBinder", "FrameSkel")
binder.__dict__["Shape"] = fc.Shape("compound", [], edges=edges)
b._place(binder)
fc.sketch(s, b, "Ring")
exprs = []
fc.Obj.setExpression = lambda self, p, e: exprs.append([self.Label, p, e])
'''


class PdPipe(unittest.TestCase):
    def pd(self, *bodies):
        return child("_datapd_standin", "feature", PD_SETUP, *bodies)

    def test_a_tube_along_one_edge_of_a_binder(self):
        got = self.pd('''
            out = run("pd_pipe", {"path": "FrameSkel", "edges": ["Edge3"], "sketch": {"circle": {"d": 28.6, "wall": 0.9}}, "transition": "Round corner"})
            pipe = [o for o in s.doc.Objects if o.TypeId == "PartDesign::AdditivePipe"][0]
            sk = pipe.Profile
            print(json.dumps({"out": out, "spine": [pipe.Spine[0].Label, pipe.Spine[1]], "transition": pipe.Transition,
                              "map": [sk.MapMode, sk.MapPathParameter, [[x[0].Label, x[1]] for x in sk.AttachmentSupport]],
                              "circles": [g.Radius for g in sk.Geometry], "names": [c.Name for c in sk.Constraints if c.Type == "Diameter"],
                              "dias": [c.Value for c in sk.Constraints if c.Type == "Diameter"], "exprs": exprs}))
        ''')
        self.assertEqual(got["out"][0], "ok", got["out"])
        ans = got["out"][1]
        self.assertEqual(ans["feature"], "Pipe")
        self.assertEqual(ans["sketch"], "FrameSkel tube")
        self.assertEqual(ans["path"], "FrameSkel")
        self.assertEqual(ans["edges"], ["Edge3"])
        self.assertIn("NormalToEdge", ans["sketchIs"])
        self.assertGreater(ans["volumeChange"], 0)
        self.assertEqual(got["spine"], ["FrameSkel", ["Edge3"]])
        self.assertEqual(got["transition"], "Round corner")
        # One edge alone: it starts at its own start (parameter 0).
        self.assertEqual(got["map"], ["NormalToEdge", 0.0, [["FrameSkel", "Edge3"]]])
        self.assertEqual(got["names"], ["od", "id"])
        self.assertAlmostEqual(got["dias"][0], 28.6)
        self.assertAlmostEqual(got["dias"][1], 26.8)
        self.assertEqual(got["exprs"], [])

    def test_edges_joined_end_to_end_start_at_the_free_end(self):
        got = self.pd('''
            out = run("pd_pipe", {"path": "FrameSkel", "edges": ["Edge3", "Edge2"], "sketch": {"circle": {"d": "Geo.tt_od", "wall": "Geo.tt_wall"}}})
            pipe = [o for o in s.doc.Objects if o.TypeId == "PartDesign::AdditivePipe"][0]
            print(json.dumps({"out": out, "spine": pipe.Spine[1], "map": [pipe.Profile.MapMode, pipe.Profile.MapPathParameter,
                              pipe.Profile.AttachmentSupport[0][1]], "exprs": exprs}))
        ''')
        self.assertEqual(got["out"][0], "ok", got["out"])
        # The first edge named with a free end starts the chain: Edge3 from its start, then Edge2 backwards.
        self.assertEqual(got["spine"], ["Edge3", "Edge2"])
        self.assertEqual(got["map"], ["NormalToEdge", 0.0, "Edge3"])
        self.assertEqual(got["exprs"], [["FrameSkel tube", "Constraints.od", "Geo.tt_od"], ["FrameSkel tube", "Constraints.id", "(Geo.tt_od) - 2 * (Geo.tt_wall)"]])

    def test_a_chain_that_starts_backwards(self):
        got = self.pd('''
            out = run("pd_pipe", {"path": "FrameSkel", "edges": ["Edge2", "Edge1"], "sketch": {"circle": {"d": 20}}})
            pipe = [o for o in s.doc.Objects if o.TypeId == "PartDesign::AdditivePipe"][0]
            print(json.dumps([out, pipe.Spine[1], pipe.Profile.MapPathParameter, len(pipe.Profile.Geometry)]))
        ''')
        out, spine, param, circles = got
        self.assertEqual(out[0], "ok", out)
        # Edge2's start meets Edge1: the chain starts at Edge2's free end, its parameter 1.
        self.assertEqual(spine, ["Edge2", "Edge1"])
        self.assertEqual(param, 1.0)
        self.assertEqual(circles, 1)  # no wall: a rod

    def test_a_sketch_profile_on_a_sketch_path_answers_as_before(self):
        got = self.pd('''
            fc.sketch(s, b, "Path", edges=3)
            print(json.dumps(run("pd_pipe", {"path": "Path", "sketch": "Ring"})))
        ''')
        self.assertEqual(got[0], "ok", got)
        self.assertNotIn("sketch", got[1])
        self.assertNotIn("sketchIs", got[1])

    def test_refusals(self):
        got = self.pd('''
            print(json.dumps([run("pd_pipe", a) for a in (
                {"path": "FrameSkel", "edges": ["Edge1", "Edge4"], "sketch": "Ring"},
                {"path": "FrameSkel", "edges": ["Edge9"], "sketch": "Ring"},
                {"path": "FrameSkel", "edges": ["Edge1", "Edge1"], "sketch": "Ring"},
                {"path": "FrameSkel", "sketch": {"circle": {"d": 10, "wall": 5}}},
                {"path": "FrameSkel", "sketch": {"circle": {"wall": 1}}},
                {"path": "FrameSkel", "sketch": "Ring", "mode": "Sideways"},
                {"path": "Nope", "sketch": "Ring"},
            )]))
        ''')
        self.assertEqual([g[0] for g in got], ["refused"] * 7, got)
        self.assertIn("do not join end to end", got[0][2])
        self.assertIn("is not an edge of FrameSkel (Edge1 … Edge4)", got[1][2])
        self.assertIn("each edge once", got[2][2])
        self.assertIn("less than half of d", got[3][2])
        self.assertIn("{ circle: { d: 28.6, wall: 0.9 } }", got[4][2])
        self.assertIn("mode 'Sideways': one of Standard", got[5][2])
        self.assertIn("sketch 'Nope': no such sketch", got[6][2])


class ShapeQueryOfWires(unittest.TestCase):
    def test_edges_of_an_object_with_no_solid(self):
        got = child("_datapd_standin", "measure", PD_SETUP, '''
            fc.Shape.isSame = lambda x, y: x is y
            out = run("shape_query", {"body": "FrameSkel"})
            v = run("shape_query", {"body": "FrameSkel", "kind": "vertex", "limit": 2})
            print(json.dumps([out, v]))
        ''')
        out, v = got
        self.assertEqual(out[0], "ok", out)
        self.assertEqual(out[1]["kind"], "edge")
        self.assertEqual(out[1]["found"], 4)
        self.assertIn("edges only", out[1]["shapeIs"])
        e3 = out[1]["items"][2]
        self.assertEqual(e3["ref"], "Edge3")
        self.assertEqual(e3["from"], [0.0, 50.0, 0.0])
        self.assertEqual(e3["to"], [100.0, 50.0, 0.0])
        self.assertEqual(e3["length"], 100.0)
        self.assertEqual(v[0], "ok", v)
        self.assertEqual(v[1]["kind"], "vertex")


class SheetTableNamedSheet(unittest.TestCase):
    def test_make_with_a_sheet_that_is_not_there(self):
        got = child("_datasheet_standin", "sheet", "", '''
            out = run("sheet_table", {"action": "make", "sheet": "Sizes", "params": ["tt_od"], "configs": [{"name": "M", "values": [28.6]}]})
            print(json.dumps([out, [o.Label for o in s.doc.Objects if o.TypeId == "Spreadsheet::Sheet"]]))
        ''')
        out, sheets = got
        self.assertEqual(out[0], "ok", out)
        self.assertEqual(out[1]["newSheet"], "Sizes")
        self.assertIn("Sizes", sheets)


class ObjectListFilters(unittest.TestCase):
    def test_full_type_derived_and_label(self):
        got = child("_datapd_standin", "doc", PD_SETUP, '''
            print(json.dumps([run("object_list", a) for a in ({"type": "Part::Feature"}, {"type": "PartDesign::Body"}, {"label": "skel"},
                                                                {"type": "Nope::Thing"})]))
        ''')
        derived, bodies, by_label, none = got
        self.assertEqual(derived[0], "ok", derived)
        # Part::Feature: the PartDesign features and the sketch are made from it, though no TypeId holds the words.
        self.assertIn("Base", [o["label"] for o in derived[1]["objects"]])
        self.assertIn("Ring", [o["label"] for o in derived[1]["objects"]])
        self.assertEqual([o["label"] for o in bodies[1]["objects"]], ["Body"])
        self.assertEqual([o["label"] for o in by_label[1]["objects"]], ["FrameSkel"])
        self.assertEqual(none[1]["count"], 0)
        self.assertIn("PartDesign::Body", none[1]["typesHere"])


if __name__ == "__main__":
    unittest.main()
