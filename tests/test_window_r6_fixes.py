# SPDX-License-Identifier: LGPL-2.1-or-later
# The faults window review round 6 found in TechDraw, Robot, object_appearance
# and the words (docs/hardening/window-r6-*.md), on stand-ins (plain Python,
# no FreeCAD):
#   - TechDraw: a leader's WayPoints y down as FreeCAD keeps them; labels
#     placed in free space; td_dimset's lanes in paper mm; centre marks made
#     bigger and counted; the weld's tiles read back; a dimension's broken 3D
#     references named (FreeCAD's "Shape index N out of bound M");
#   - Robot: its scene marks carry words; a robot or trajectory never
#     selected (FreeCAD's Robot task watchers widened the Tasks panel);
#     robot_tool sets ToolBase before ToolShape;
#   - object_appearance: the selection cleared after it; the core model
#     makes "Block moved" only where the clearance call needs it;
#   - words: every part_ / points_ tool has its own.
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_famfix import TechDrawPaper, entries  # noqa: E402
from test_hubfix2 import in_a_process  # noqa: E402

TD = TechDrawPaper.BODY


def src(*parts):
    with open(os.path.join(HERE, *parts), encoding="utf-8") as f:
        return f.read()


class TechDrawPlacing(unittest.TestCase):
    def test_leader_points_run_y_down(self):
        got = in_a_process(TD + '''
    print(json.dumps([td.leader_points(20, 15, 5), td.leader_points(-30, -10, 20), td.leader_points(3, 15, 5)]))
''')
        # an end 20 right and 15 UP on the page is 15 DOWN in FreeCAD's WayPoints
        self.assertEqual(got, [[[0, 0], [15, -15], [20, -15]], [[0, 0], [-10, 10], [-30, 10]], [[0, 0], [3, -15]]])

    def test_free_spot_keeps_off_busy_boxes_and_the_paper_edge(self):
        got = in_a_process(TD + '''
    busy = [(100.0, 100.0, 40.0, 40.0)]
    free = td.free_spot(busy, (297, 210), (200, 50), 10, 5)
    moved = td.free_spot(busy, (297, 210), (100, 100), 10, 5, away=(90, 100))
    edge = td.free_spot([], (297, 210), (2, 100), 10, 5)
    side = td.free_spot([], (297, 210), (100, 100), 10, 5, dx=8, side_of=120)
    print(json.dumps([free, moved, edge, side]))
''')
        self.assertEqual(got[0], [200, 50])
        x, y = got[1]
        self.assertTrue(abs(x - 100) >= 26 or abs(y - 100) >= 23.5, got[1])   # clear of the 40 x 40 box
        self.assertLessEqual(((x - 100) ** 2 + (y - 100) ** 2) ** 0.5, 28.01)  # the nearest ring that is free
        self.assertGreaterEqual(got[2][0] - 5, 5)                             # 5 mm in from the edge
        self.assertEqual(got[3], [100, 100])

    def test_the_entries_place_in_free_space(self):
        e = entries()
        leader = json.dumps(e["td_leader"]["steps"])
        self.assertIn("clear_xy(page, at,", leader)
        self.assertIn("side_of=vx + p[0]", leader)
        self.assertIn("clear_xy(page, want, fig.w, fig.h", json.dumps(e["td_finish"]["steps"]))
        self.assertIn("clear_xy(page, at, fig.w, fig.h", json.dumps(e["td_gdt"]["steps"]))
        self.assertIn("clear_xy(page_holding(v)", json.dumps(e["td_weld"]["steps"]))
        self.assertIn("clear_xy(page, at, len(text)", json.dumps(e["td_area"]["steps"]))
        special = json.dumps(e["td_dim_special"]["steps"])
        self.assertIn('"mid": "=ref_point(v, names[0])[1]"', special)
        self.assertIn("clear_xy(page, (vx + mid[0], vy - mid[1])", special)
        dimset = json.dumps(e["td_dimset"]["steps"])
        self.assertIn('"half": "=paper_half(v)"', dimset)
        self.assertNotIn("bb.YLength / 2", dimset)
        self.assertIn('"end": ["=num(to[0], 2)", "=num(to[1], 2)"], "...tiles": "=tiles"', json.dumps(e["td_weld"]["answer"]))

    def test_the_export_reads_waypoints_y_down(self):
        self.assertIn("pts = [(ox + p.x, H - oy + p.y) for p in v.WayPoints]", src("agentlink", "families", "techdraw.py"))


class TechDrawFacts(unittest.TestCase):
    def test_broken_3d_references_named(self):
        got = in_a_process(TD + '''
    body = types.SimpleNamespace(Label="Body", Shape=types.SimpleNamespace(Edges=[], Vertexes=[1, 2], Faces=[]))
    d = types.SimpleNamespace(References3D=[(body, ["Edge29", "Vertex2"])])
    ok = types.SimpleNamespace(References3D=[(body, ["Vertex1"])])
    none = types.SimpleNamespace()
    print(json.dumps([td.broken_3d(d), td.broken_3d(ok), td.broken_3d(none)]))
''')
        self.assertEqual(got, [["Body.Edge29: Body has 0 edges"], [], []])

    def test_centre_marks_bigger_and_counted(self):
        got = in_a_process(TD + '''
    fc.GuiUp = True
    class C:
        def __init__(self, x, y, r):
            self.Center, self.Radius = fc.Vector(x, y, 0) if hasattr(fc, "Vector") else types.SimpleNamespace(x=x, y=y, z=0), r
    def P(x, y):
        return types.SimpleNamespace(x=x, y=y, z=0)
    class E:
        def __init__(self, curve):
            self.Curve = curve
    class C2:
        def __init__(self, x, y, r):
            self.Center, self.Radius = P(x, y), r
    class Line:
        pass
    edges = [E(C2(0, 0, 5)), E(C2(0, 0, 5)), E(C2(10, 0, 3)), E(Line())]
    verts = [types.SimpleNamespace(Point=P(0, 0)), types.SimpleNamespace(Point=P(5, 5))]
    vo = types.SimpleNamespace(ArcCenterMarks=False, CenterScale=0.5)
    class View:
        ViewObject = vo
        def getEdgeByIndex(self, i):
            if i >= len(edges):
                raise IndexError(i)
            return edges[i]
        def getVertexByIndex(self, i):
            if i >= len(verts):
                raise IndexError(i)
            return verts[i]
    v = View()
    on = td.native_marks(v, True)
    print(json.dumps([on, vo.ArcCenterMarks, vo.CenterScale, td.mark_facts(v)]))
''')
        # Round 8: FreeCAD's own crosses (which mark a slot's ends too) are
        # off; the chain lines are cosmetic lines (none in this stand-in).
        self.assertEqual(got, [True, False, 0.5, {"centres": 2, "marked": 1, "scale": 0.5, "crosses": False}])

    def test_weld_tiles_read_back_and_text_raised(self):
        got = in_a_process(TD + '''
    fc.GuiUp = True
    class Tile:
        def __init__(self, row, parent):
            self.TileRow, self.SymbolFile, self.LeftText, self.RightText, self.TileParent = row, "", "", "", parent
        def isDerivedFrom(self, t):
            return t == "TechDraw::DrawTileWeld"
    vo = types.SimpleNamespace(TileFontSize=2.6)
    class W:
        Name = "WeldSymbol"
        ViewObject = vo
        InList = []                      # not yet: the document has them
    tiles = []
    class Doc:
        Objects = tiles
        def addObject(self, t, n):
            w = W()
            tiles.extend([Tile(0, w), Tile(-1, w)])
            return w
    fc.getResourceDir = lambda: "/nowhere"
    w, found, facts = td.native_weld(Doc(), types.SimpleNamespace(addView=lambda o: None), "leader", {"kind": "fillet", "size": "3", "side": "arrow", "h": 3.5})
    print(json.dumps([found, facts]))
''')
        self.assertEqual(got, [False, {"tiles": [{"row": 0, "symbol": None, "left": "3", "right": ""},
                                                 {"row": -1, "symbol": None, "left": "", "right": ""}], "tileTextMm": 3.5}])


class RobotAndAppearance(unittest.TestCase):
    BODY = TD + '''
    sys.modules.setdefault("FreeCADGui", types.ModuleType("FreeCADGui"))
    from agentlink import echo
'''

    def test_robot_marks_have_words_and_robots_are_never_selected(self):
        got = in_a_process(self.BODY + '''
    pl = lambda x, y, z: types.SimpleNamespace(Base=types.SimpleNamespace(x=x, y=y, z=z), multiply=lambda o: o)
    wp = [types.SimpleNamespace(Pos=pl(1, 2, 3)), types.SimpleNamespace(Pos=pl(4, 5, 6))]
    traj = types.SimpleNamespace(TypeId="Robot::TrajectoryObject", Label="Stroke", Base=None, Trajectory=types.SimpleNamespace(Waypoints=wp))
    pin = types.SimpleNamespace(Label="Pin")
    robot = types.SimpleNamespace(TypeId="Robot::RobotObject", Label="Arm", ToolShape=pin)
    doc = types.SimpleNamespace(Objects=[robot, traj])
    words = echo.robot_words(robot, doc, [(0, 0, 0), (10, 0, 0)])
    print(json.dumps([[w for _, w in words], echo._watcher_type(robot), echo._watcher_type(traj), echo._watcher_type(pin)]))
''')
        self.assertEqual(got, [["base Arm", "tool point (Pin)", "Stroke start", "Stroke end"], True, True, False])

    def test_the_echo_wiring(self):
        e = src("agentlink", "echo.py")
        self.assertIn('COLOUR_TOOLS = ("object_appearance",)', e)
        self.assertIn('tr["selectionCleared"]', e)
        self.assertIn("scene_marks(list(dict.fromkeys(marks + [w[0] for w in words])), lines, labels=words)", e)
        self.assertIn("    if _watcher_type(o):\n        return False", e)
        a = src("agentlink", "annotate.py")
        self.assertIn('def marks(self, owner, points=(), lines=(), colour="#e8a33d", size=9, labels=()):', a)

    def test_robot_tool_sets_where_before_what(self):
        steps = entries()["robot_tool"]["steps"]
        keys = [list(s.get("set", {}))[0] for s in steps if "set" in s]
        self.assertEqual(keys, ["r.ToolBase", "r.ToolShape"])
        fields = entries()["robot_tool"]["answer"]["fields"]
        self.assertIn("drawnAt", fields)
        self.assertIn("toolVisible", fields)

    def test_block_moved_is_made_where_it_is_needed(self):
        calls = json.loads(src("docs", "hardening", "models", "coredoc-model.json"))["calls"]
        dup = next(i for i, c in enumerate(calls) if c["tool"] == "object_duplicate" and c["arguments"].get("name") == "Block moved")
        self.assertEqual(calls[dup + 1]["arguments"].get("object"), "Block moved")
        for tool in ("object_appearance", "shape_query", "measure"):
            last = max(i for i, c in enumerate(calls) if c["tool"] == tool and "Block" in json.dumps(c["arguments"]))
            self.assertLess(last, dup, tool)
        first_use = min(i for i, c in enumerate(calls) if i > dup + 1 and "Block moved" in json.dumps(c["arguments"]))
        self.assertEqual(calls[first_use]["tool"], "clearance")
        self.assertEqual(sum(1 for c in calls if c["tool"] == "robot_new"), 1)
        self.assertEqual(calls[82]["tool"], "robot_move")  # the $from 82 chain is where it was


class Words(unittest.TestCase):
    def test_every_part_and_points_tool_has_its_own(self):
        tools = entries()
        words = json.loads(src("agentlink", "data", "activity.json"))["entries"]
        bare = [k for k, v in tools.items() if k.startswith(("part_", "points_", "compound_")) and k not in words and not v.get("activity")]
        self.assertEqual(bare, [])

    def test_the_words_carry_the_values(self):
        got = in_a_process(TD + '''
    from agentlink import activity
    print(json.dumps([activity.did("part_slices", {"body": "Block", "count": 5}),
                      activity.did("object_appearance", {"objects": ["Block"], "color": "#3366cc", "transparency": 30}),
                      activity.did("part_compound", {"bodies": ["A", "B"], "explode": True}),
                      activity.did("material_set", {"bodies": ["Block"], "id": "PLA"})]))
''')
        self.assertEqual(got, ["Cut 5 slices through Block", "Coloured Block #3366cc, 30 % see-through", "Took A and B apart",
                               "Gave Block the material PLA"])


if __name__ == "__main__":
    unittest.main()
