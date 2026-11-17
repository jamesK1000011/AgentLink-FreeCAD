# SPDX-License-Identifier: LGPL-2.1-or-later
# The tool faults the window reviews found (docs/hardening/famfix-findings.md),
# on stand-ins (plain Python, no FreeCAD):
#   - FEM: FreeCAD's FEM mesh view made once with Agent Link's window
#     observer off, and "Cannot add static property" answered as a refusal
#     that says to restart FreeCAD;
#   - TechDraw: points of the view's indexed geometry turned to paper y down
#     by the frame's own y direction; an empty source's bounding box guarded;
#     FreeCAD's own centre marks and weld symbol; the balloon in the view's
#     unscaled frame;
#   - the entries: bim_rebar on a Draft wire, pd_multitransform's steps
#     hidden and the MultiTransform shown, fea_native and fem_mesh netgen
#     ready before they make anything.
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_hubfix2 import in_a_process  # noqa: E402

SETUP = '''
    class P:
        def __getattr__(self, k):
            return lambda name=None, default=None: default if default is not None else (0 if k in ("GetInt", "GetFloat", "GetUnsigned") else False if k == "GetBool" else "")
    fc.ParamGet = lambda path: P()
    fc.Version = lambda: ["1", "1", "3"]
    for m in ("Mesh", "MeshPart", "Fem", "Arch", "Draft", "TechDraw"):
        sys.modules.setdefault(m, Any(m))
'''


def entries():
    with open(os.path.join(HERE, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


class FemViews(unittest.TestCase):
    BODY = SETUP + '''
    from agentlink import changes
    from agentlink.families import strength
    from agentlink.protocol import ToolError
    said = []
    gui = types.ModuleType("FreeCADGui")
    gui.removeDocumentObserver = lambda o: said.append(("off", o))
    gui.addDocumentObserver = lambda o: said.append(("on", o))
    sys.modules["FreeCADGui"] = gui
    fc.GuiUp = True
    changes._state["gui"] = "watch"
    class D:
        def __init__(self, fail=None):
            self.fail = fail
        def addObject(self, t, n):
            said.append(("add", t))
            if self.fail:
                raise RuntimeError(self.fail)
            return types.SimpleNamespace(Name=n)
        def removeObject(self, n):
            said.append(("remove", n))
'''

    def test_made_once_with_the_observer_off(self):
        got = in_a_process(self.BODY + '''
    strength.fem_views_ready(D())
    strength.fem_views_ready(D())     # once a session
    print(json.dumps([said, strength._fem_views["ready"]]))
''')
        self.assertEqual(got, [[["off", "watch"], ["add", "Fem::FemMeshObject"], ["remove", "AgentLinkFemView"], ["on", "watch"]], True])

    def test_a_short_table_is_a_refusal_to_restart(self):
        got = in_a_process(self.BODY + '''
    try:
        strength.fem_views_ready(D("Cannot add static property"))
        out = None
    except ToolError as e:
        out = [e.code, e.message]
    print(json.dumps([out, said[-1], strength._fem_views["ready"]]))
''')
        self.assertEqual(got[0][0], "unavailable")
        self.assertIn("Restart FreeCAD (app_force_restart)", got[0][1])
        self.assertIn("nothing was made", got[0][1])
        self.assertEqual(got[1], ["on", "watch"])  # the observer is put back
        self.assertFalse(got[2])

    def test_no_window_nothing_to_do(self):
        got = in_a_process(self.BODY + '''
    fc.GuiUp = False
    strength.fem_views_ready(D("Cannot add static property"))
    print(json.dumps(said))
''')
        self.assertEqual(got, [])

    def test_the_route_falls_back_and_the_native_mesh_refuses(self):
        with open(os.path.join(HERE, "agentlink", "families", "strength.py"), encoding="utf-8") as f:
            src = f.read()
        route = src[src.index("    def _fem_build_and_run("):src.index("    def _solve_own(")]
        self.assertLess(route.index("fem_views_ready(doc)"), route.index("ObjectsFem.makeAnalysis"))
        self.assertIn("raise RuntimeError(e.message) from None", route)  # the own deck then solves
        native = src[src.index("    def native_mesh("):src.index("    def face_refs(")]
        self.assertIn("raise ToolError(\"unavailable\", FEM_VIEWS_BROKEN)", native)

    def test_the_entries_are_ready_before_they_make_anything(self):
        e = entries()
        steps = [json.dumps(s) for s in e["fea_native"]["steps"]]
        ready = steps.index(json.dumps({"do": "=fem_views_ready()"}))
        made = next(i for i, s in enumerate(steps) if "new_analysis" in s)
        self.assertLess(ready, made)
        netgen = next(s for s in e["fem_mesh"]["steps"] if s.get("when") == "=act == 'netgen'")
        self.assertEqual(netgen["then"][0], {"do": "=fem_views_ready()"})


class TechDrawPaper(unittest.TestCase):
    BODY = SETUP + '''
    from agentlink.families import techdraw as td
    class Box:
        def __init__(self, ok):
            self.ok = ok
        def isValid(self):
            return self.ok
        DiagonalLength = 1.0
    class View:
        Name = "V"
        Scale = 2.0
        def getScale(self):
            return 2.0
'''

    def test_indexed_geometry_to_paper_y_down_by_the_frame(self):
        got = in_a_process(self.BODY + '''
    v = View()
    up = {"V": (1.0, 1, 0.0, 0.0)}      # FreeCAD 1.1.3: unscaled, y up
    down = {"V": (2.0, -1, 0.0, 0.0)}   # scaled, y down
    print(json.dumps([td.to_paper(v, up, (3, 4)), td.to_paper(v, down, (6, 8)), td.flip_y(v, up, [(1, 2), (3, 0)]), td.flip_y(v, down, [(1, 2)])]))
''')
        self.assertEqual(got, [[6, -8], [6, 8], [[1, -2], [3, 0.0]], [[1, 2]]])

    def test_an_empty_source_box_is_no_frame(self):
        got = in_a_process(self.BODY + '''
    print(json.dumps([td.box_ok(types.SimpleNamespace(BoundBox=Box(False))), td.box_ok(types.SimpleNamespace(BoundBox=Box(True)))]))
''')
        self.assertEqual(got, [False, True])

    def test_centre_marks_in_the_window(self):
        got = in_a_process(self.BODY + '''
    fc.GuiUp = True
    vo = types.SimpleNamespace(ArcCenterMarks=False)
    on = td.native_marks(types.SimpleNamespace(ViewObject=vo), True)
    fc.GuiUp = False
    off = td.native_marks(types.SimpleNamespace(ViewObject=vo), False)
    print(json.dumps([on, vo.ArcCenterMarks, off]))
''')
        self.assertEqual(got, [True, True, False])

    def test_freecads_own_weld_symbol(self):
        got = in_a_process(self.BODY + '''
    import os, tempfile
    root = tempfile.mkdtemp()
    aws = os.path.join(root, "Mod", "TechDraw", "Symbols", "Welding", "AWS")
    os.makedirs(aws)
    for n in ("filletUp.svg", "filletDown.svg", "plug.svg"):
        open(os.path.join(aws, n), "w").close()
    fc.getResourceDir = lambda: root
    class Tile:
        def __init__(self, row):
            self.TileRow, self.SymbolFile, self.LeftText, self.RightText = row, "blank", "", ""
        def isDerivedFrom(self, t):
            return t == "TechDraw::DrawTileWeld"
    class W:
        Name = "WeldSymbol"
        def __init__(self):
            self.InList = [Tile(0), Tile(-1)]
    class Doc:
        def addObject(self, t, n):
            assert t == "TechDraw::DrawWeldSymbol"
            return W()
    added = []
    page = types.SimpleNamespace(addView=added.append)
    w, found, facts = td.native_weld(Doc(), page, "leader", {"kind": "fillet", "size": "5", "length": "50", "side": "arrow", "allAround": True, "field": False, "tail": "GMAW"})
    w2, found2, _ = td.native_weld(Doc(), page, "leader", {"kind": "bevel", "side": "both"})
    rows = [[t.TileRow, os.path.basename(t.SymbolFile), t.LeftText, t.RightText] for t in w.InList]
    print(json.dumps([found, rows, w.Leader, w.AllAround, w.TailText, len(added), found2, td.weld_svg("plug", False) is not None, facts]))
''')
        self.assertEqual(got, [True, [[0, "filletUp.svg", "5", "50"], [-1, "blank", "", ""]], "leader", True, "GMAW", 2, False, True,
                               {"tiles": [{"row": 0, "symbol": "filletUp.svg", "left": "5", "right": "50"},
                                          {"row": -1, "symbol": "blank", "left": "", "right": ""}]}])

    def test_the_balloon_in_the_views_unscaled_frame(self):
        steps = json.dumps(entries()["td_balloon"]["steps"])
        self.assertIn('"b.OriginX": "=p[0] / sc", "b.OriginY": "=-p[1] / sc"', steps)
        self.assertIn('"b.X": "=(p[0] + 15) / sc"', steps)

    def test_the_weld_and_the_marks_reach_the_window(self):
        e = entries()
        self.assertIn({"let": {"ws, has_svg, tiles": "=native_weld(page_holding(v), ln, spec)"}}, e["td_weld"]["steps"])
        self.assertIn("native_marks(v, ext > 0)", json.dumps(e["td_centermarks"]["steps"]))


class Entries(unittest.TestCase):
    def test_the_rebar_lies_on_a_draft_wire(self):
        steps = entries()["bim_rebar"]["steps"]
        s = json.dumps(steps)
        self.assertIn('{"let": {"line": "=rebar_line(p0, p1, bar)"}}', s)
        self.assertIn('"call": ["=host", "=line"]', s)
        with open(os.path.join(HERE, "agentlink", "families", "bim.py"), encoding="utf-8") as f:
            self.assertIn("Draft.make_wire, [p0, p1], closed=False, face=False", f.read())

    def test_multitransform_steps_hidden_tip_shown(self):
        steps = entries()["pd_multitransform"]["steps"]
        s = json.dumps(steps)
        self.assertIn('{"set": {"t.Visibility": false}}, {"push": {"subs": "=t"}}', s)
        self.assertEqual(steps[-1], {"set": {"mt.Visibility": True}})

    def test_import_over_the_model_says_so(self):
        e = entries()["bim_import"]
        self.assertEqual(e["answer"]["fields"]["note"]["when"], "=lies_over(made, before)")


if __name__ == "__main__":
    unittest.main()
