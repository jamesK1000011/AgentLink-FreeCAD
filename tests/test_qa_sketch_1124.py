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
    from agentlink.protocol import Tool, STOP_MARK
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


class TheSameCallAgain(unittest.TestCase):
    def test_refused_counted_and_cleared(self):
        got = in_a_process(SERVER + '''
    out = {}
    out["first"] = call("probe_make", {"x": 1})
    out["again"] = call("probe_make", {"x": 1})
    out["third"] = msg(call("probe_make", {"x": 1}))
    out["madeCount"] = len(D.Objects)
    for i in range(3):
        out["late"] = call("probe_make", {"x": 1})
    out["changed"] = call("probe_make", {"x": 2})
    # sketch geometry, inside a batch too
    out["add"] = call("sketch_add", {"x": 5})
    out["addAgain"] = msg(call("sketch_add", {"x": 5}))
    out["geometry"] = len(sk.Geometry)
    b = call("batch", {"calls": [{"tool": "sketch_add", "x": 6}, {"tool": "sketch_add", "x": 6}]})
    out["batch"] = [[r["ok"], (r.get("error") or {}).get("message")] for r in b[1]["results"]]
    # what is never refused: a read, a tool where a repeat is normal, a call that made nothing
    out["read"] = [call("probe_read", {"x": 1})[0] for _ in range(3)]
    out["recompute"] = [call("recompute", {"x": 1})[0] for _ in range(3)]
    out["set"] = [call("probe_set", {"x": 1})[0] for _ in range(3)]
    # what was made is gone: no refusal
    out["gone"] = call("probe_make", {"x": 7})[0]
    D.Objects.pop()  # what that call made, removed
    out["goneAgain"] = call("probe_make", {"x": 7})[0]
    # an undo clears the record
    call("probe_make", {"x": 8})
    call("history_undo", {})
    out["afterUndo"] = call("probe_make", {"x": 8})[0]
    # past the window of recent changing calls
    call("probe_make", {"x": 9})
    for i in range(10):
        call("probe_set", {"x": 100 + i})
    out["pastWindow"] = call("probe_make", {"x": 9})[0]
    # the person's own calls are not looked at
    call("probe_make", {"x": 10})
    s.by = "person"
    out["person"] = call("probe_make", {"x": 10})[0]
    s.by = "agent"
    # a new conversation starts a new record
    call("probe_make", {"x": 11})
    srv.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"clientInfo": {"name": "t"}}})
    out["newConversation"] = call("probe_make", {"x": 11})[0]
    # doc_new again: refused; it clears the record of the document before
    call("probe_make", {"x": 12})
    out["docNew"] = call("doc_new", {"name": "P"})[0]
    out["afterDocNew"] = call("probe_make", {"x": 12})[0]
    out["docNewAgain"] = msg(call("doc_new", {"name": "P"}))
    out["docs"] = len(docs)
    print(json.dumps(out))
''')
        self.assertFalse(got["first"][0])
        err, body = got["again"]
        self.assertTrue(err)
        m = body["error"]["message"]
        self.assertTrue(m.startswith("This call ran before with the same tool and arguments, and answered ok (made: Thing"), m)
        self.assertIn("; calls since then: 0)", m)
        self.assertIn("If it runs again, it adds the same again. Nothing was done.", m)
        self.assertIn("feature_remove (a feature of a body) or object_delete", m)
        self.assertEqual((body["error"]["code"], body["error"]["status"]), ("invalid_state", "not_started"))
        self.assertIn("calls since then: 1)", got["third"])
        self.assertIn("This is the same refusal as before", got["third"])  # counted by the repeat stop
        self.assertEqual(got["madeCount"], 2)  # the sketch and one thing: nothing made again
        self.assertTrue(got["late"][0])
        self.assertTrue(got["late"][1]["error"]["message"].startswith("No progress after 5 tries of probe_make"), got["late"])
        self.assertFalse(got["changed"][0])
        self.assertFalse(got["add"][0])
        self.assertIn("(made: Sketch geometry 0-1;", got["addAgain"])
        self.assertIn('sketch_edit { sketch: "Sketch", delete: [0, 1] }', got["addAgain"])
        self.assertEqual(got["geometry"], 2)
        self.assertEqual([ok for ok, _ in got["batch"]], [True, False])
        self.assertIn("calls since then: 0)", got["batch"][1][1])
        self.assertEqual(got["read"], [False] * 3)
        self.assertEqual(got["recompute"], [False] * 3)
        self.assertEqual(got["set"], [False] * 3)
        self.assertEqual((got["gone"], got["goneAgain"]), (False, False))
        self.assertFalse(got["afterUndo"])
        self.assertFalse(got["pastWindow"])
        self.assertFalse(got["person"])
        self.assertFalse(got["newConversation"])
        self.assertFalse(got["docNew"])
        self.assertFalse(got["afterDocNew"])  # another document: the record was cleared
        self.assertIn("(made: document Doc", got["docNewAgain"])
        self.assertIn("doc_close", got["docNewAgain"])
        self.assertEqual(got["docs"], 2)

    def test_the_same_arguments_on_another_sketch_or_body_are_no_repeat(self):
        # Coordinator, 24 Nov: sketch_new (Sketch 3), sketch_add with no sketch named; later sketch_new (Sketch 4) and
        # the same sketch_add: a normal step on another sketch. Also pd_pad { length } and a new body with no names.
        got = in_a_process(SERVER + '''
    from agentlink.families import pd_common as pc
    ASCH = {"type": "object", "properties": {"sketch": {"type": "string"}, "items": {"type": "array"}, "length": {"type": "number"}}, "additionalProperties": False}
    def sk_new(a):
        o = Sk(D, "Sketch%03d" % len(D.Objects))
        o.Label, o.Geometry = "Sketch %d" % (len([x for x in D.Objects if x.TypeId == "Sketcher::SketchObject"]) + 2), []
        D.Objects.append(o)
        pc.note_made_sketch(s, o)
        return {"sketch": o.Label}
    def sk_add(a):
        o = pc.sketch_of(s.doc, a.get("sketch"), None, s)
        n = len(o.Geometry)
        o.Geometry = o.Geometry + ["circle"]
        return {"sketch": o.Label, "added": [{"kind": "circle", "ids": [n]}]}
    def pad(a):
        o = pc.sketch_of(s.doc, a.get("sketch"), None, s)
        f = Obj(D, "Pad%03d" % len(D.Objects))
        D.Objects.append(f)
        return {"feature": f.Label, "sketch": o.Label}
    srv.tools["sketch_new"] = Tool("sketch_new", "New sketch.", SCH, sk_new, changes=True, group="sketch")
    srv.tools["sketch_add"] = Tool("sketch_add", "Add geometry.", ASCH, sk_add, changes=True, group="sketch")
    srv.tools["probe_pad"] = Tool("probe_pad", "Pad.", ASCH, pad, changes=True)
    srv.tools["probe_body"] = Tool("probe_body", "New body.", SCH, make, changes=True)
    C = {"items": [{"kind": "circle", "center": [0, 0], "radius": 2.5}]}
    out = {}
    call("sketch_new", {})
    out["add3"] = call("sketch_add", C)
    out["add3Again"] = msg(call("sketch_add", C))           # the same current sketch: refused
    call("sketch_new", {})
    out["add4"] = call("sketch_add", C)                     # another current sketch: not a repeat
    out["named"] = call("sketch_add", dict(C, sketch="Sketch 3"))[0]
    out["namedAgain"] = msg(call("sketch_add", dict(C, sketch="Sketch 3")))
    out["pad"] = call("probe_pad", {"length": 5})
    out["padAgain"] = msg(call("probe_pad", {"length": 5}))
    call("sketch_new", {})
    out["padNew"] = call("probe_pad", {"length": 5})[0]
    out["body"] = call("probe_body", {})[0]
    out["bodyAgain"] = msg(call("probe_body", {}))
    call("probe_make", {"x": 99})
    out["bodyLater"] = call("probe_body", {})[0]
    out["geometry"] = {o.Label: len(o.Geometry) for o in D.Objects if o.TypeId == "Sketcher::SketchObject"}
    print(json.dumps(out))
''')
        self.assertFalse(got["add3"][0])
        self.assertEqual(got["add3"][1]["sketch"], "Sketch 3")
        self.assertIn("(made: Sketch 3 geometry 0;", got["add3Again"])
        self.assertFalse(got["add4"][0], got["add4"])
        self.assertEqual(got["add4"][1]["sketch"], "Sketch 4")
        self.assertFalse(got["named"])
        self.assertIn("(made: Sketch 3 geometry 1;", got["namedAgain"])
        self.assertFalse(got["pad"][0])
        self.assertIsNotNone(got["padAgain"])
        self.assertFalse(got["padNew"])  # a new sketch is the default now: another pad, not a repeat
        self.assertFalse(got["body"])
        self.assertIsNotNone(got["bodyAgain"])  # nothing made since: the same call again
        self.assertFalse(got["bodyLater"])  # something made since: another step
        self.assertEqual(got["geometry"], {"Sketch": 0, "Sketch 3": 2, "Sketch 4": 1, "Sketch 5": 0})

    def test_a_rollback_clears_the_record(self):
        from agentlink import protocol

        srv = type("S", (), {})()
        srv._ran = [{"name": "probe_make", "call": "{}", "seq": 1, "made": [("object", "D", "A", "A", ())]}]
        protocol.again_clear(srv)
        self.assertEqual(srv._ran, [])
        protocol.again_clear(None)  # no server: nothing to do
        with open(os.path.join(ROOT, "agentlink", "tools.py"), encoding="utf-8") as f:
            src = f.read()
        body = src[src.index("def roll_back("):src.index("def ", src.index("def roll_back(") + 10)]
        self.assertIn('again_clear(getattr(s, "server", None))', body)


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

    def test_a_stray_line_is_remove_or_join(self):
        # A closed rectangle (0-3, the last side ending at (0, 0)) and line 4 from its corner out to (150, 0).
        lines = {**LINES, 3: ((0, 50), (0, 0))}
        got = self.words([(4, "line", 1, (100, 0)), (4, "line", 2, (150, 0))], [0, 1, 2, 3, 4], lines=lines)
        self.assertEqual(got, ["line 4 ends at (150, 0) on nothing: remove it (sketch_edit { delete: [4] }) or join that end to another end"])

    def test_a_small_gap_is_coincident(self):
        got = self.words([(3, "line", 2, (0, 0.4)), (0, "line", 1, (0, 0))], [0, 1, 2, 3])
        self.assertEqual(got, ["the end of line 3 (0, 0.4) is 0.4 mm from the start of line 0 (0, 0): sketch_constrain coincident joins them"])

    def test_a_lone_line_and_a_side_left_out(self):
        lone = {0: ((0, 0), (50, 0))}
        got = self.words([(0, "line", 1, (0, 0)), (0, "line", 2, (50, 0))], [0], size=50.0, lines=lone)
        self.assertEqual(got, ["line 0 touches nothing at (0, 0) or (50, 0): remove it (sketch_edit { delete: [0] }) or join its ends"])
        # three sides of a rectangle: the two ends are far apart (100 of 112 mm), so not a gap
        u = {0: ((0, 0), (100, 0)), 1: ((100, 0), (100, 50)), 2: ((100, 50), (0, 50))}
        got = self.words([(0, "line", 1, (0, 0)), (2, "line", 2, (0, 50))], [0, 1, 2], lines=u)
        self.assertEqual(len(got), 2)
        self.assertTrue(all("on nothing" in w for w in got), got)

    def test_an_end_on_another_curve_gets_no_words_of_its_own(self):
        # line 1 from the middle of line 0 (a T): no words fit, so the general todo stays
        t = {0: ((0, 0), (100, 0)), 1: ((50, 0), (50, 40))}
        got = self.words([(1, "line", 1, (50, 0)), (0, "line", 1, (0, 0)), (0, "line", 2, (100, 0))], [0, 1], size=108.0, lines=t)
        # line 1's start is on line 0: only line 0's own ends are said
        self.assertEqual(got, ["line 0 touches nothing at (0, 0) or (100, 0): remove it (sketch_edit { delete: [0] }) or join its ends"])
        got = self.words([(1, "line", 1, (50, 0))], [0, 1], size=108.0, lines=t)
        self.assertEqual(got, [])

    def test_state_of_uses_the_words(self):
        with open(os.path.join(ROOT, "agentlink", "families", "sketch.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('why += said or ["close the open wires: coincident constraints at the open vertices"]', src)

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
        self.assertEqual(got, ["line 4 ends at (150, 0) on nothing: remove it (sketch_edit { delete: [4] }) or join that end to another end"])


class ItemIndex(unittest.TestCase):
    def run_add(self, items):
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
               "state_of": lambda sk: {}}
    try:
        runners.run_steps("sketch_add", {"steps": e["steps"]}, {"items": %r}, helpers)
        print(json.dumps(["ok", len(sk.geo)]))
    except ToolError as x:
        print(json.dumps([x.code, x.message]))
''' % (ROOT, items))

    def test_the_failing_item_is_named(self):
        ok = [{"kind": "line"}] * 4
        self.assertEqual(self.run_add(ok + [{"kind": "same"}]), ["failed", "items[4]: Both points are equal"])
        self.assertEqual(self.run_add(ok[:1] + [{"kind": "bad"}]), ["invalid_input", "items[1]: circle: radius (or diameter), mm."])
        self.assertEqual(self.run_add([{"kind": "num"}]), ["invalid_input", "items[0]: size: not a number"])
        self.assertEqual(self.run_add([{"kind": "line"}, 5]), ["invalid_input", "items[1]: an object { kind, … }."])
        self.assertEqual(self.run_add(ok), ["ok", 4])


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
    inv = types.SimpleNamespace(multVec=lambda v: P(v.x, v.z, -v.y))
    pl = types.SimpleNamespace(inverse=lambda: inv)
    bb = types.SimpleNamespace(XMin=-20.04, XMax=20.04, YMin=0, YMax=15, ZMin=0, ZMax=8.26)
    body = types.SimpleNamespace(Shape=types.SimpleNamespace(isNull=lambda: False, Solids=[1], BoundBox=bb))
    sk = types.SimpleNamespace(getGlobalPlacement=lambda: pl)
    empty = types.SimpleNamespace(Shape=types.SimpleNamespace(isNull=lambda: False, Solids=[], BoundBox=bb))
    print(json.dumps([sketch.body_extent(body, sk), sketch.body_extent(empty, sk)]))
''')
        self.assertEqual(got, [{"x": [-20.0, 20.0], "y": [0.0, 8.3]}, None])

    def test_the_answer_and_the_cards(self):
        e = entries()
        new = e["sketch_new"]
        self.assertEqual(new["answer"]["fields"]["bodyExtent"], {"when": "=ext", "value": "=ext"})
        self.assertEqual(new["steps"][-2], {"let": {"ext": "=body_extent(b, sk)"}})
        self.assertIn("bodyExtent: the box of the body's solid in the sketch's own x/y", new["description"])
        add = e["sketch_add"]["description"]
        self.assertIn("rectangle {center|corner, size [w,h]}. rounded_rectangle {…, radius}. center puts the middle of the shape on that point. "
                      "A shape at center [0, 0] goes to the two sides of the sketch origin. corner is the lower-left corner of a rectangle. "
                      "Use corner to start a shape at an edge of the body (sketch_new gives bodyExtent).", add)


if __name__ == "__main__":
    unittest.main()
