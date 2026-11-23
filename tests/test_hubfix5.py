# SPDX-License-Identifier: LGPL-2.1-or-later
# The hub's faults of private records: hubfix5-findings.md, on stand-ins
# (plain Python, no FreeCAD):
#   - view_snapshot: where the parts land is worked out from the camera for
#     the picture's own size; after a fit that did not take it says so and
#     does not advise the same call; a turn and a fit run without FreeCAD's
#     animation; datum planes, hidden bodies and moved Parts in the box;
#   - meshobj_unwrap: the outlines are found here, not by flatmesh's
#     boundary walk, and the helper marks its unwrapping;
#   - the Report view: FreeCAD's own known BIM wall fault said once and
#     counted, its traceback with it;
#   - usage_report: an error answer whose text is not one JSON is still an
#     error; refusals the window writes itself, and a busy answer to a
#     call that then finished, are counted;
#   - the records object is not touched by a record's write.
import json
import math
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentlink import emptywhy, report_watch, store, usage  # noqa: E402
from test_hubfix2 import in_a_process  # noqa: E402
from test_hubfix4 import SETUP  # noqa: E402

CAM_ORTHO = """#Inventor V2.1 ascii

OrthographicCamera {
  viewportMapping ADJUST_CAMERA
  position 0 0 100
  nearDistance 1
  farDistance 200
  focalDistance 100
  height 20
}
"""


class Camera(unittest.TestCase):
    def test_the_camera_text_is_read_with_coins_defaults(self):
        cam = emptywhy.camera_of(CAM_ORTHO)
        self.assertTrue(cam["ortho"])
        self.assertEqual(cam["position"], [0.0, 0.0, 100.0])
        self.assertEqual((cam["axis"], cam["angle"]), ([0.0, 0.0, 1.0], 0.0))
        self.assertEqual(cam["height"], 20.0)
        p = emptywhy.camera_of("PerspectiveCamera {\n  position 1 2 3\n  orientation 1 0 0  1.5707964\n  heightAngle 0.5\n}\n")
        self.assertFalse(p["ortho"])
        self.assertEqual(p["axis"], [1.0, 0.0, 0.0])
        self.assertAlmostEqual(p["angle"], math.pi / 2, places=5)
        self.assertEqual(p["heightAngle"], 0.5)
        self.assertIsNone(emptywhy.camera_of(""))
        self.assertIsNone(emptywhy.camera_of(None))

    def test_points_land_in_the_pictures_own_pixels(self):
        cam = emptywhy.camera_of(CAM_ORTHO)
        # 20 mm high in a 200 x 100 picture: 5 px a mm, the middle at (100, 50)
        got = emptywhy.in_picture(cam, [(0, 0, 0), (5, 0, 0), (0, 5, 0)], 200, 100)
        self.assertEqual([tuple(round(c, 6) for c in p) for p in got], [(100.0, 50.0), (125.0, 50.0), (100.0, 75.0)])
        # a tall picture keeps the width (Coin's ADJUST_CAMERA): 20 mm across 100 px
        tall = emptywhy.in_picture(cam, [(10, 0, 0)], 100, 200)
        self.assertAlmostEqual(tall[0][0], 100.0)

    def test_a_perspective_point_behind_the_camera_makes_no_claim(self):
        cam = emptywhy.camera_of("PerspectiveCamera {\n  position 0 0 10\n}\n")
        self.assertIsNone(emptywhy.in_picture(cam, [(0, 0, 20)], 100, 100))
        ahead = emptywhy.in_picture(cam, [(0, 0, 0)], 100, 100)
        self.assertEqual([tuple(round(c, 6) for c in p) for p in ahead], [(50.0, 50.0)])


class SnapshotWords(unittest.TestCase):
    def test_after_a_fit_a_speck_is_not_sent_back_to_the_same_call(self):
        box = {"min": [0, 0, 0], "max": [40, 30, 10]}
        words = emptywhy.off_screen([(400, 300), (402, 301)], (800, 600), fitted=True, box=box)
        self.assertIn("The fit did not take", words)
        self.assertIn("view_render", words)
        self.assertIn("[0.0, 0.0, 0.0] to [40.0, 30.0, 10.0] mm", words)
        self.assertNotIn("view_snapshot with a view", words)
        out = emptywhy.off_screen([(900, 100), (950, 200)], (800, 600), fitted=True)
        self.assertIn("outside the frame", out)
        self.assertNotIn("view_snapshot with a view", out)

    def test_without_a_fit_the_old_advice_stands_and_nan_makes_no_claim(self):
        self.assertIn("view_snapshot with a view", emptywhy.off_screen([(400, 300), (402, 301)], (800, 600)))
        self.assertIsNone(emptywhy.off_screen([(float("nan"), 1), (2, 3)], (800, 600)))
        self.assertIsNone(emptywhy.off_screen([(100, 100), (500, 400)], (800, 600), fitted=True))

    def test_the_entry_hands_the_size_and_the_fit_to_the_check(self):
        with open(os.path.join(HERE, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            steps = json.dumps(json.load(f)["entries"]["view_snapshot"]["steps"])
        self.assertIn("=snap_empty(view, w, h, fitted)", steps)


STAND_INS = SETUP + '''
    class BB:
        def __init__(self, other=None):
            self.XMin, self.YMin, self.ZMin, self.XMax, self.YMax, self.ZMax = (
                (other.XMin, other.YMin, other.ZMin, other.XMax, other.YMax, other.ZMax) if other else (0,) * 6)
        def add(self, o):
            self.XMin, self.YMin, self.ZMin = min(self.XMin, o.XMin), min(self.YMin, o.YMin), min(self.ZMin, o.ZMin)
            self.XMax, self.YMax, self.ZMax = max(self.XMax, o.XMax), max(self.YMax, o.YMax), max(self.ZMax, o.ZMax)
        def isValid(self):
            return True
        def transformed(self, m):
            b = BB(self)
            b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax = [c + m for c in (self.XMin, self.YMin, self.ZMin, self.XMax, self.YMax, self.ZMax)]
            return b
    fc.BoundBox = BB
    def box(lo, hi):
        b = BB()
        b.XMin, b.YMin, b.ZMin = lo
        b.XMax, b.YMax, b.ZMax = hi
        return b
    class Move:
        def __init__(self, by):
            self.by = by
        def multiply(self, other):
            return self
        def isIdentity(self):
            return self.by == 0
        def toMatrix(self):
            return self.by
    class Obj:
        def __init__(self, name, bb, shown=True, parent=None, moved=0):
            self.Label = self.Name = name
            self.ViewObject = types.SimpleNamespace(Visibility=shown)
            self.Shape = types.SimpleNamespace(isNull=lambda: False, BoundBox=bb) if bb else None
            self.parent, self.moved = parent, moved
            self.Placement = types.SimpleNamespace(inverse=lambda: None)
        def getParentGeoFeatureGroup(self):
            return self.parent
        def getParentGroup(self):
            return None
        def getGlobalPlacement(self):
            return Move(self.parent.moved if self.parent else 0)
'''


class ShownBox(unittest.TestCase):
    def test_datum_planes_hidden_bodies_and_moved_parts(self):
        got = in_a_process(STAND_INS + '''
    from agentlink.families import view as V
    hidden_body = Obj("Body", None, shown=False)
    moved_part = Obj("Part", None, moved=100)
    objs = [
        Obj("Bracket", box((0, 0, 0), (40, 30, 10))),
        Obj("DatumPlane", box((-1e100, -1e100, 0), (1e100, 1e100, 0))),       # shown, left out of the box
        Obj("Pad", box((500, 500, 500), (600, 600, 600)), parent=hidden_body),  # its Body is hidden
        Obj("Pin", box((0, 0, 0), (5, 5, 5)), parent=moved_part),              # drawn 100 mm on
    ]
    s = types.SimpleNamespace(doc=types.SimpleNamespace(Objects=objs))
    shown, b = V.shown_box(s)
    print(json.dumps([shown, [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]]))
''')
        self.assertEqual(got, [3, [0, 0, 0, 105, 105, 105]])

    def test_a_turn_and_a_fit_run_without_the_animation_and_put_it_back(self):
        got = in_a_process(STAND_INS + '''
    sys.modules["pivy"] = None  # no Coin here: the window's fit only
    from agentlink.families import view as V
    seen = []
    class View:
        on = True
        def isAnimationEnabled(self):
            return self.on
        def setAnimationEnabled(self, v):
            seen.append(v)
            self.on = v
        def fitAll(self):
            seen.append(["fit", self.on])
    v = View()
    V.snap_fit(v, 100, 100, None)
    class Bare:
        def fitAll(self):
            seen.append("bare")
    V.snap_fit(Bare(), 100, 100, None)
    print(json.dumps([seen, v.on]))
''')
        self.assertEqual(got, [[False, ["fit", False], True, "bare"], True])


class Unwrap(unittest.TestCase):
    def test_the_outlines_are_found_here_where_two_meet_at_a_point(self):
        got = in_a_process(SETUP + '''
    import numpy as np
    from agentlink.families import meshobj
    # two triangles that touch at one point (0): flatmesh's own walk reads
    # past its table there; here it is two outlines
    Q = np.array([[0, 0], [1, 0], [0, 1], [-1, 0], [0, -1]], float)
    loops = meshobj.flat_loops(Q, np.array([[0, 1, 2], [0, 3, 4]]))
    square = meshobj.flat_loops(np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float), np.array([[0, 1, 2], [0, 2, 3]]))
    none = meshobj.flat_loops(Q, np.zeros((0, 3)))
    print(json.dumps({"two": [list(b.shape) for b in loops], "square": sorted({tuple(p) for p in square[0].tolist()}), "n": len(square), "none": none}))
''')
        self.assertEqual(len(got["two"]), 2)
        self.assertTrue(all(n >= 3 and k == 2 for n, k in got["two"]))
        self.assertEqual(got["n"], 1)
        self.assertEqual(got["square"], [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]])
        self.assertEqual(got["none"], [])

    def test_the_helper_no_longer_asks_flatmesh_for_the_outlines_and_marks_its_work(self):
        with open(os.path.join(HERE, "agentlink", "families", "meshobj.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("fl.getFlatBoundaryNodes()", src)
        i, j, k = src.index("\"at('unwrapping')"), src.index("fl.findFlatNodes("), src.index("\"at('unwrapped')")
        self.assertLess(i, j)
        self.assertLess(j, k)


WALL = ["12:01:02  Traceback (most recent call last):",
        "File \"/Applications/FreeCAD.app/Contents/Resources/Mod/BIM/ArchWall.py\", line 1684, in updateData",
        "<class 'AttributeError'>: 'Gui.ViewProviderGeometryObject' object has no attribute 'DiffuseColor'"]


class KnownFault(unittest.TestCase):
    def setUp(self):
        self.saved = (report_watch._report_widget, report_watch._blocks, report_watch._problem_colours, report_watch._report_text,
                      dict(report_watch._state))

    def tearDown(self):
        (report_watch._report_widget, report_watch._blocks, report_watch._problem_colours, report_watch._report_text, st) = self.saved
        report_watch._state.clear()
        report_watch._state.update(st)

    def use(self, rows):
        report_watch._report_widget = lambda: object()
        report_watch._blocks = lambda w, start: (rows[start:], len(rows))
        report_watch._problem_colours = lambda: {"#ff0000"}
        report_watch._report_text = lambda: "\n".join(t for t, _c in rows)
        report_watch._state.update({"seen": 0, "known": {}})

    def test_folded_with_its_traceback_and_others_kept(self):
        other = ["Traceback (most recent call last):", "File \"x.py\", line 1, in f", "ValueError: bad"]
        kept, counts = report_watch.fold_known(WALL + ["Error: something of ours"] + WALL + other + ["'Gui.ViewProviderGeometryObject' object has no attribute 'DiffuseColor'"])
        self.assertEqual(kept, ["Error: something of ours"] + other)
        self.assertEqual(list(counts.values()), [3])

    def test_said_once_on_the_answers_and_counted_by_report_read(self):
        rows = [(t, "#ff0000") for t in WALL * 3 + ["Error: ours"]]
        self.use(rows)
        first = report_watch.take()
        self.assertEqual(len(first), 2)
        self.assertTrue(first[0].startswith("FreeCAD's own, known: BIM's ArchWall.py"))
        self.assertEqual(first[1], "Error: ours")
        rows += [(t, "#ff0000") for t in WALL * 2]
        self.assertEqual(report_watch.take(), [])  # said already: not again
        r = report_watch.read(40, True)
        self.assertEqual(r["known"][0]["times"], 5)
        self.assertEqual(r["problems"], 1)
        self.assertTrue(r["lines"][0].endswith("(× 5)"))
        self.assertEqual(r["lines"][1:], ["Error: ours"])

    def test_it_does_not_open_the_report_view(self):
        self.assertEqual(report_watch.problems_to_open([(t, "#ff0000") for t in WALL], {"#ff0000"}), [])


class UsageErrors(unittest.TestCase):
    def test_an_error_whose_text_is_not_one_json_still_counts(self):
        self.assertIsNone(usage.err_code({"content": [{"type": "text", "text": "{}"}]}))
        self.assertEqual(usage.err_code({"isError": True, "content": [{"type": "text", "text": '{"error":{"code":"busy"}}'},
                                                                        {"type": "text", "text": "more"}]}), "busy")
        self.assertEqual(usage.err_code({"isError": True, "content": [{"type": "text", "text": "not json"}]}), "error")
        self.assertEqual(usage.err_code({"isError": True}), "error")

    def test_the_server_counts_an_error_with_two_text_parts(self):
        import tempfile

        from agentlink import protocol
        from agentlink.protocol import Server, Tool

        where = tempfile.mkdtemp()
        srv = Server("t", "1", [Tool("fail", "Refuse.", {"type": "object", "properties": {}},
                                     lambda a: (_ for _ in ()).throw(protocol.ToolError("invalid_input", "no")))], "")
        srv.meter = usage.Meter(where)
        real = srv._call

        def two_parts(params):
            r = real(params)
            r["content"].append({"type": "text", "text": "a second part"})
            return r

        srv._call = two_parts
        srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "fail", "arguments": {}}})
        t = srv.meter.session_totals()
        self.assertEqual((t["calls"], t["errors"]), (1, 1))

    def test_refusals_of_the_window_and_a_late_busy_are_counted(self):
        import tempfile

        from test_gui_link_dialog import gui_link

        where = tempfile.mkdtemp()
        m = usage.Meter(where)
        link = types.SimpleNamespace(server=types.SimpleNamespace(meter=m))
        line = json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "pd_pad", "arguments": {"sketch": "S"}}})
        reply = {"jsonrpc": "2.0", "id": 4, "result": {"content": [{"type": "text", "text": '{"error":{"code":"invalid_state","message":"closed"}}'}], "isError": True}}
        gui_link.Link._meter_refused(link, line, reply)
        m.call("sketch_new", "{}", "{}", None, None, 5)   # ran and answered …
        gui_link.Link._meter_amend(link, "sketch_new")    # … but the agent had been told busy
        gui_link.Link._meter_amend(link, "sketch_new")    # once only
        t = m.session_totals()
        self.assertEqual((t["calls"], t["errors"]), (2, 2))
        by = {b["tool"]: b["errors"] for b in t["byTool"]}
        self.assertEqual(by, {"pd_pad": 1, "sketch_new": 1})
        r = usage.report(1, where)
        self.assertEqual((r["calls"], r["errors"]), (2, 2))


class Records(unittest.TestCase):
    def test_a_record_is_an_output_and_a_new_holder_is_not_left_touched(self):
        status, did = {}, []

        class O:
            PropertiesList = []

            def addProperty(self, t, p, g, d):
                self.PropertiesList.append(p)
                setattr(self, p, "")

            def setEditorMode(self, p, m):
                pass

            def getPropertyStatus(self, p):
                return status.get(p, [])

            def setPropertyStatus(self, p, s):
                status.setdefault(p, []).append(s)
                did.append(("status", p))

            def __setattr__(self, k, v):
                if k.startswith(store._prop("")[:3]) and did is not None:
                    did.append(("set", k))
                object.__setattr__(self, k, v)

            def purgeTouched(self):
                did.append("purged")

        o = O()
        store._set(o, "materials", '{"Body": "pla"}')
        p = store._prop("materials")
        self.assertEqual(status[p], ["Output"])
        self.assertLess(did.index(("status", p)), len(did) - 1)  # the status before the write
        store._set(o, "materials", "{}")
        self.assertEqual(status[p], ["Output"])  # set once
        store._untouch(o)
        self.assertEqual(did[-1], "purged")


if __name__ == "__main__":
    unittest.main()
