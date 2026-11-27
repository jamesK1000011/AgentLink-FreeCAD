# SPDX-License-Identifier: LGPL-2.1-or-later
# Blind QA of nine local-model runs (24 Nov), the sketch and repeat faults:
#   1. a changing call sent again exactly (the same sketch_add 13 times, a
#      whole batch with doc_new again) is refused, and the refusal counts
#      toward the repeat stop;
#   2. a loose open end of a sketch's outline is said as one (remove it or
#      join it), apart from a small gap between two ends (coincident);
#   3. sketch_add's refusal of one item names it: items[n];
#   4. (tests/test_sketch_names_1124.py) a change to a feature's profile sketch says so;
#   5. sketch_new gives the body's extent in the sketch's own x/y, and the
#      sketch_add card says what center and corner do.
import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from test_hubfix2 import in_a_process  # noqa: E402
from test_hubfix4 import SETUP as _SETUP  # noqa: E402

SETUP = _SETUP + '''
    sys.modules.setdefault("Sketcher", Any("Sketcher"))
'''


def entries():
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


# A server on the stand-in FreeCAD with probe tools: probe_make makes an
# object; sketch_add (a probe) adds geometry to a stand-in sketch and answers
# as sketch_add does; a read; recompute; doc_new; history_undo.
SERVER = SETUP + '''
    from agentlink import tools
    from agentlink.protocol import Tool
    import tempfile
    D = new("Part")
    s = tools.Session(doc=D, out_dir=tempfile.mkdtemp(prefix="agentlink-qa1124-"))
    srv = tools.build_server(s, lean=False)
    s.server = srv
    SCH = {"type": "object", "properties": {"x": {"type": "number"}, "name": {"type": "string"}}, "additionalProperties": False}
    class Sk(Obj):
        TypeId = "Sketcher::SketchObject"
    sk = Sk(D, "Sketch")
    sk.Geometry = []
    D.Objects.append(sk)
    def make(a):
        o = Obj(D, "Thing%03d" % len(D.Objects))
        o.Label = a.get("name") or o.Name
        D.Objects.append(o)
        return {"object": o.Label}
    def add(a):
        n = len(sk.Geometry)
        sk.Geometry += ["line", "line"]
        return {"sketch": sk.Label, "added": [{"kind": "rectangle", "ids": [n, n + 1]}]}
    def doc_new(a):
        d = new("Doc%d" % len(docs))
        s.doc = d
        return {"document": d.Name, "label": d.Name}
    srv.tools["probe_make"] = Tool("probe_make", "Make a thing.", SCH, make, changes=True)
    srv.tools["probe_set"] = Tool("probe_set", "Set a thing.", SCH, lambda a: {"set": True}, changes=True)
    srv.tools["probe_read"] = Tool("probe_read", "Read.", SCH, make, changes=False)
    srv.tools["sketch_add"] = Tool("sketch_add", "Add geometry.", SCH, add, changes=True, group="sketch")
    srv.tools["recompute"] = Tool("recompute", "Recompute.", SCH, make, changes=True)
    srv.tools["doc_new"] = Tool("doc_new", "A new document.", SCH, doc_new, changes=False)
    srv.tools["history_undo"] = Tool("history_undo", "Undo.", SCH, lambda a: {"undone": 1}, changes=True)
    def call(name, args):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
        body = json.loads(r["content"][0]["text"])
        return [r.get("isError", False), body]
    def msg(r):
        return r[1]["error"]["message"] if r[0] else None
'''


# The open ends of an outline, with lines only: dist is a point's distance to a segment.
LINES = {0: ((0, 0), (100, 0)), 1: ((100, 0), (100, 50)), 2: ((100, 50), (0, 50)), 3: ((0, 50), (0, 0.4)), 4: ((100, 0), (150, 0))}


def seg_dist(i, p, lines=LINES):
    (ax, ay), (bx, by) = lines[i]
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (ax + t * dx, ay + t * dy))


class OpenEnds(unittest.TestCase):
    def words(self, ends, curves, size=112.0, lines=LINES):
        got = in_a_process(SETUP + '''
    from agentlink.families import sketch
    import math
    lines = {int(k): v for k, v in %r.items()}
    def dist(i, p):
        (ax, ay), (bx, by) = lines[i]
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
        return math.dist(p, (ax + t * dx, ay + t * dy))
    print(json.dumps(sketch.open_end_words(%r, %r, %r, dist)))
''' % (lines, ends, curves, size))
        return got

    # 27 Nov (owner): the words are facts only. Each open end has its ref and
    # the measured distance to the nearest other open end. No share of the
    # outline's size decides anything, and nothing says what was meant.
    TAIL = ""

    def test_a_stray_line_says_its_open_end_and_the_distance(self):
        # A closed rectangle (0-3, the last side ending at (0, 0)) and line 4 from its corner out to (150, 0).
        lines = {**LINES, 3: ((0, 50), (0, 0))}
        got = self.words([(4, "line", 1, (100, 0)), (4, "line", 2, (150, 0))], [0, 1, 2, 3, 4], lines=lines)
        # line 4's start is on the rectangle (a branch: branch_words says it); its end is the open end
        self.assertEqual(got, ["the end of line 4 [4, 2] (150, 0) is an open end; the nearest other open end is the start of line 4 [4, 1] (100, 0), 50 mm away" + self.TAIL])

    def test_two_ends_that_are_each_others_nearest_are_one_phrase(self):
        got = self.words([(3, "line", 2, (0, 0.4)), (0, "line", 1, (0, 0))], [0, 1, 2, 3])
        self.assertEqual(got, ["the end of line 3 [3, 2] (0, 0.4) and the start of line 0 [0, 1] (0, 0) are open ends, 0.4 mm apart" + self.TAIL])

    def test_the_same_words_at_any_distance_and_any_size(self):
        lone = {0: ((0, 0), (50, 0))}
        got = self.words([(0, "line", 1, (0, 0)), (0, "line", 2, (50, 0))], [0], size=50.0, lines=lone)
        self.assertEqual(got, ["the start of line 0 [0, 1] (0, 0) and the end of line 0 [0, 2] (50, 0) are open ends, 50 mm apart" + self.TAIL])
        # three sides of a rectangle: the same form as a small gap, with the measured distance
        u = {0: ((0, 0), (100, 0)), 1: ((100, 0), (100, 50)), 2: ((100, 50), (0, 50))}
        ends = [(0, "line", 1, (0, 0)), (2, "line", 2, (0, 50))]
        want = ["the start of line 0 [0, 1] (0, 0) and the end of line 2 [2, 2] (0, 50) are open ends, 50 mm apart" + self.TAIL]
        for size in (1.0, 112.0, 5000.0):  # the outline's size decides nothing
            self.assertEqual(self.words(ends, [0, 1, 2], size=size, lines=u), want)
        for w in got + want:
            for banned in ("remove it", "joins them", "on nothing", "touches nothing", "sketch_constrain", "not a full circle"):
                self.assertNotIn(banned, w)

    def test_an_end_on_another_curve_gets_no_words_of_its_own(self):
        # line 1 from the middle of line 0 (a T): its start is a branch, which branch_words says
        t = {0: ((0, 0), (100, 0)), 1: ((50, 0), (50, 40))}
        got = self.words([(1, "line", 1, (50, 0)), (0, "line", 1, (0, 0)), (0, "line", 2, (100, 0))], [0, 1], size=108.0, lines=t)
        # only line 0's own ends are said; line 1's start is the nearest open end of each
        self.assertEqual(got, ["the start of line 0 [0, 1] (0, 0) is an open end; the nearest other open end is the start of line 1 [1, 1] (50, 0), 50 mm away",
                               "the end of line 0 [0, 2] (100, 0) is an open end; the nearest other open end is the start of line 1 [1, 1] (50, 0), 50 mm away" + self.TAIL])
        got = self.words([(1, "line", 1, (50, 0))], [0, 1], size=108.0, lines=t)
        self.assertEqual(got, [])

    def test_no_threshold_is_left_in_the_code(self):
        with open(os.path.join(ROOT, "agentlink", "families", "sketch.py"), encoding="utf-8") as f:
            src = f.read()
        for name in ("NEAR_GAP", "ROUND_NEAR", "ROUND_NEAR_MM", "TINY_GAP_MM", "TINY_GAP"):
            self.assertNotRegex(src, r"(?m)^%s\s*=" % name)
            self.assertNotRegex(src, r"[^A-Z_,]%s[^A-Z_,]\s*\*" % name)
        self.assertIn("SAME_POINT = pc.TOUCH", src)  # the one tolerance: float equality, FreeCAD's own
        self.assertIn("Precision::Confusion", src)

    def test_state_of_uses_the_words(self):
        with open(os.path.join(ROOT, "agentlink", "families", "sketch.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("said += _branch_words(sk, joins) + gaps", src)
        self.assertNotIn("close the open wires", src)  # facts only (27 Nov)

    def test_the_sketch_ends_are_matched_to_their_curves(self):
        got = in_a_process(SETUP + '''
    import types, math
    from agentlink.families import sketch
    class P:
        def __init__(self, x, y, z=0):
            self.x, self.y, self.z = x, y, z
    class LineSegment:
        def __init__(self, a, b):
            self.StartPoint, self.EndPoint = P(*a), P(*b)
        def toShape(self):
            a, b = (self.StartPoint.x, self.StartPoint.y), (self.EndPoint.x, self.EndPoint.y)
            def d(v):
                p = (v.x, v.y)
                dx, dy = b[0] - a[0], b[1] - a[1]
                t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
                return (math.dist(p, (a[0] + t * dx, a[1] + t * dy)),)
            return types.SimpleNamespace(distToShape=d)
    sketch.Part = types.SimpleNamespace(Vertex=lambda v: v)
    sketch.V = P
    sk = types.SimpleNamespace(Geometry=[LineSegment((0, 0), (100, 0)), LineSegment((100, 0), (100, 50)), LineSegment((100, 50), (0, 50)),
                                         LineSegment((0, 50), (0, 0)), LineSegment((100, 0), (150, 0)), LineSegment((10, 10), (20, 10))],
                               getConstruction=lambda i: i == 5,
                               Shape=types.SimpleNamespace(BoundBox=types.SimpleNamespace(DiagonalLength=158.1)))
    print(json.dumps(sketch._open_end_words(sk, [[150.0, 0.0]])))
''')
        self.assertEqual(got, ["the end of line 4 [4, 2] (150, 0) is an open end, the only one"])


class ItemIndex(unittest.TestCase):
    """The failing shape is named by its own words (27 Nov: sketch_add takes one shape for each call, so there is no items[i] prefix)."""

    def run_add(self, shape):
        return in_a_process(SETUP + '''
    import os, types
    from agentlink import runners
    from agentlink.families import sketch
    from agentlink.protocol import ToolError
    e = json.load(open(os.path.join(%r, "agentlink", "data", "tools.json")))["entries"]["sketch_add"]
    class Sk:
        def __init__(self):
            self.geo = []
        def addGeometry(self, g, cons=False):
            if g == "same":
                raise RuntimeError("Both points are equal")
            self.geo.append(g)
            return len(self.geo) - 1
        def addConstraint(self, c):
            return 0
    sk = Sk()
    def build(it):
        if it["kind"] == "bad":
            raise ToolError("invalid_input", "circle: radius (or diameter), mm.")
        if it["kind"] == "num":
            raise ValueError("size: not a number")
        return (["same"] if it["kind"] == "same" else ["ok"]), [], []
    helpers = {"sketch_of": lambda ref: sk, "build": build, "is_tuple": lambda x: isinstance(x, tuple), "constraint": lambda t: t,
               "remap": lambda t, ids: t, "item_error": sketch.item_error, "doc": lambda: types.SimpleNamespace(recompute=lambda: 0),
               "state_of": lambda sk: {}, "by_default": sketch.by_default}
    try:
        runners.run_steps("sketch_add", {"steps": e["steps"]}, %r, helpers)
        print(json.dumps(["ok", len(sk.geo)]))
    except ToolError as x:
        print(json.dumps([x.code, x.message]))
''' % (ROOT, shape))

    def test_the_failing_item_is_named(self):
        self.assertEqual(self.run_add({"kind": "same"}), ["failed", "Both points are equal"])
        self.assertEqual(self.run_add({"kind": "bad"}), ["invalid_input", "circle: radius (or diameter), mm."])
        self.assertEqual(self.run_add({"kind": "num"}), ["invalid_input", "size: not a number"])
        self.assertEqual(self.run_add({"kind": "line"}), ["ok", 1])


class BodyExtent(unittest.TestCase):
    def test_the_body_box_in_the_sketch_x_y(self):
        got = in_a_process(SETUP + '''
    import types
    from agentlink.families import sketch
    class P:
        def __init__(self, x, y, z=0):
            self.x, self.y, self.z = x, y, z
    sketch.V = P
    # An XZ sketch: its x is the world x, its y the world z, its normal -y. The inverse takes world (x, y, z) to (x, z, -y).
    # sketch x = world x, sketch y = world z, normal = -world y
    rot = types.SimpleNamespace(multVec=lambda v: {(1, 0, 0): P(1, 0, 0), (0, 1, 0): P(0, 0, 1), (0, 0, 1): P(0, -1, 0)}[(v.x, v.y, v.z)])
    pl = types.SimpleNamespace(Base=P(0, 0, 0), Rotation=rot)
    bb = types.SimpleNamespace(XMin=-20.04, XMax=20.04, YMin=0, YMax=15, ZMin=0, ZMax=8.26)
    body = types.SimpleNamespace(Shape=types.SimpleNamespace(isNull=lambda: False, Solids=[1], BoundBox=bb))
    sk = types.SimpleNamespace(getGlobalPlacement=lambda: pl)
    empty = types.SimpleNamespace(Shape=types.SimpleNamespace(isNull=lambda: False, Solids=[], BoundBox=bb))
    print(json.dumps([sketch.body_extent(body, sk), sketch.body_extent(empty, sk)]))
''')
        self.assertEqual(got, [{"x": [-20.0, 20.0], "y": [0.0, 8.3], "normal": [-15.0, 0.0]}, None])

    def test_the_answer_and_the_cards(self):
        e = entries()
        new = e["sketch_new"]
        self.assertEqual(new["answer"]["fields"]["bodyExtent"], {"when": "=ext", "value": "=ext"})
        self.assertEqual(new["steps"][-2], {"let": {"ext": "=body_extent(b, sk)", "said": "=face_said(b, link, what) if 'face' in a else what"}})
        self.assertIn("bodyExtent: the box of the body's solid in the sketch's own frame", new["description"])
        add = e["sketch_add"]["description"]
        self.assertIn("rectangle {center|corner, size}. rounded_rectangle {…, radius}.", add)
        # 27 Nov: the facts about each input are in the schema's own descriptions
        props = e["sketch_add"]["inputSchema"]["properties"]
        self.assertIn("[x, y]: the middle of the shape. A shape at [0, 0] goes to the two sides of the sketch origin.", props["center"]["description"])
        self.assertIn("rectangle: [x, y] of its lower-left corner. Use it to start a shape at an edge of the body (sketch_new gives bodyExtent).",
                      props["corner"]["description"])


if __name__ == "__main__":
    unittest.main()
