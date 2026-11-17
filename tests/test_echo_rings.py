# SPDX-License-Identifier: LGPL-2.1-or-later
# The echo's fourth window pass (docs/hardening/round4-findings.md): every
# family's tools mapped to the button on its workbench's toolbar, the "»"
# lit only for a button truly in its toolbar's overflow, the tree and the
# property view brought up to the selection, an Assembly never isolated by
# the echo's own selection, covers judged along the line of sight, and the
# rest of the window state. Without FreeCAD: plain rules and stand-ins.
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agentlink import activity, echo  # noqa: E402
from test_gui_link_dialog import gui_link  # noqa: E402  (gui_link with its FreeCAD stand-in)

COMMANDS = os.path.join(HERE, "..", "docs", "hardening", "freecad-1.1.0-commands.txt")


def known_commands():
    with open(COMMANDS, encoding="utf-8") as f:
        return {ln.strip() for ln in f if ln.strip() and not ln.startswith("#")}


def tools_by_family():
    with open(os.path.join(HERE, "..", "agentlink", "data", "tool_index.json"), encoding="utf-8") as f:
        names = list(json.load(f)["entries"])
    fams = {}
    for n in names:
        fams.setdefault(n.split("_")[0], []).append(n)
    return fams


class Rings(unittest.TestCase):
    def test_every_command_is_freecads(self):
        known = known_commands()
        bad = sorted({v for v in echo.COMMAND.values() if v not in known})
        for _tool, (_key, table) in echo.BY_ARG.items():
            bad += [v for v in table.values() if v not in known]
        bad += [c for c in ("FEM_ConstraintSelfWeight", "FEM_ConstraintPressure", "FEM_ConstraintTemperature") if c not in known]
        self.assertEqual(bad, [])

    def test_the_families_the_reviews_counted(self):
        """Round 3 lit 1 of 21 Mesh, 1 of 15 Surface, 1 of 10 Points, 4 of 23
        Sheet buttons: every tool of those families now has its command."""
        fams = tools_by_family()
        reads = {"sheet_chart", "sheet_list", "sheet_read"}  # reads keep the last change's ring
        # Round 6: typing in cells, inserting rows, clearing have no toolbar
        # button (the Alias button they lit was another job's).
        reads |= {"sheet_set", "sheet_rows", "sheet_clear"}
        for fam in ("meshobj", "surface", "points", "sheet"):
            missing = [n for n in fams[fam] if not echo.command_for(n, {}) and n not in reads]
            self.assertEqual(missing, [], fam)
        for fam, least in (("part", 28), ("bim", 44), ("draft", 17), ("td", 28), ("fea", 12), ("cam", 12)):
            got = sum(1 for n in fams[fam] if echo.command_for(n, {}))
            self.assertGreaterEqual(got, least, fam)

    def test_by_what_was_asked(self):
        self.assertEqual(echo.command_for("part_primitive", {"kind": "box"}), "Part_Box")  # asm 001
        self.assertEqual(echo.command_for("part_primitive", {"kind": "wedge"}), "Part_Primitives")
        self.assertEqual(echo.command_for("part_boolean", {"op": "fuse"}), "Part_Fuse")  # asm 005
        self.assertEqual(echo.command_for("part_boolean", {"op": "cut"}), "Part_Cut")  # cam 003
        self.assertEqual(echo.command_for("fea_load", {"gravity": True}), "FEM_ConstraintSelfWeight")  # fem 033
        self.assertEqual(echo.command_for("fea_load", {"force": 100}), "FEM_ConstraintForce")
        self.assertEqual(echo.command_for("meshobj_boolean", {"op": "difference"}), "Mesh_Difference")
        self.assertEqual(echo.command_for("draft_modify", {"op": "upgrade"}), "Draft_Upgrade")  # draft 006
        self.assertEqual(echo.command_for("points_fit", {"shape": "cylinder"}), "Reen_ApproxCylinder")


class Overflow(unittest.TestCase):
    def test_rule(self):
        self.assertTrue(echo.in_overflow([(True, True), (True, False)], 1))
        self.assertTrue(echo.in_overflow([(True, True), (True, False), (False, False)], 1))
        self.assertFalse(echo.in_overflow([(True, False), (True, True)], 0))


class ViewsFollow(unittest.TestCase):
    def test_which_timers_run(self):
        rows = [("Gui::PropertyView", True, True), ("Gui::TreeWidget", True, True), ("Gui::TreeWidget", True, False),
                ("Gui::TreeWidget", False, True), ("QWidget", True, True)]
        self.assertEqual(echo.to_fire(rows), [0, 1])


class Isolation(unittest.TestCase):
    def test_a_joint_selected_does_not_isolate(self):
        cleared = []
        asm = types.SimpleNamespace(Label="CrankSlider", ViewObject=types.SimpleNamespace(clearIsolate=lambda: cleared.append(1)))
        doc = types.SimpleNamespace(findObjects=lambda t: [asm] if t == "Assembly::AssemblyObject" else [])
        joint = types.SimpleNamespace(PropertiesList=["JointType", "Reference1"], Document=doc)
        part = types.SimpleNamespace(PropertiesList=["Shape"], Document=doc)
        self.assertEqual(echo.isolation_off([part]), [])
        self.assertEqual(echo.isolation_off([joint]), ["CrankSlider"])
        self.assertEqual(cleared, [1])


class Sight(unittest.TestCase):
    DOWN = (-0.577, 0.577, -0.577)  # FreeCAD's isometric view direction

    def test_roof_over_the_room(self):
        room = (2, 2, 0, 8, 8, 3)
        roof = (0, 0, 3, 10, 10, 6)
        slab = (-5, -5, -1, 15, 15, 0)  # under it: never in the way from above
        self.assertEqual(echo.covers([room], [("roof", roof)]), [])  # the old rule missed it (bim 018-043)
        self.assertEqual(echo.covers_in_view([room], [("roof", roof), ("slab", slab)], self.DOWN), ["roof"])
        self.assertEqual(echo.covers_in_view([room], [("roof", roof)], None), [])

    def test_in_front_of_a_sketch_face_on(self):
        sketch = (0, 0, 5, 40, 30, 5)  # a sketch on z = 5, looked at from above
        plate = (-10, -10, 6, 50, 40, 10)  # above it: in front
        under = (-10, -10, 0, 50, 40, 4)
        self.assertEqual(echo.covers_in_view([sketch], [("plate", plate), ("under", under)], (0, 0, -1)), ["plate"])

    def test_a_box_holding_the_point_is_left_to_covers(self):
        self.assertFalse(echo.sight_hits((0, 0, 0, 10, 10, 10), (5, 5, 5), (0, 0, -1)))
        self.assertTrue(echo.sight_hits((0, 0, 6, 10, 10, 10), (5, 5, 5), (0, 0, -1)))
        self.assertFalse(echo.sight_hits((20, 0, 6, 30, 10, 10), (5, 5, 5), (0, 0, -1)))

    def test_containers_are_never_covers(self):
        body = types.SimpleNamespace(TypeId="PartDesign::Body")
        level = types.SimpleNamespace(TypeId="Part::FeaturePython", Proxy=type("BuildingPart", (), {})())
        slab = types.SimpleNamespace(TypeId="Part::FeaturePython", Proxy=type("Structure", (), {})(), PropertiesList=["Shape"],
                                     Shape=object())
        self.assertTrue(echo.is_container(body))
        self.assertTrue(echo.is_container(level))
        self.assertFalse(echo.is_container(slab))

    def test_uncover_takes_the_host_not_the_level(self):
        """A rebar's host slab may be made see-through (it is what it is
        built from); the level holding both never is."""
        class VO:
            PropertiesList = ["Transparency", "Visibility"]

            def __init__(self):
                self.Transparency, self.Visibility = 0, True

        def bb(*b):
            return types.SimpleNamespace(XMin=b[0], YMin=b[1], ZMin=b[2], XMax=b[3], YMax=b[4], ZMax=b[5],
                                         isValid=lambda: True, DiagonalLength=1.0)

        level = types.SimpleNamespace(Name="Level", Label="Ground floor", TypeId="App::DocumentObjectGroup", ViewObject=VO(),
                                      Shape=types.SimpleNamespace(BoundBox=bb(-1, -1, -1, 11, 11, 11)), PropertiesList=["Group"])
        slab = types.SimpleNamespace(Name="Slab", Label="Floor slab", TypeId="Part::FeaturePython", ViewObject=VO(),
                                     Shape=types.SimpleNamespace(BoundBox=bb(0, 0, 0, 10, 10, 2)), PropertiesList=["Shape"])
        bars = types.SimpleNamespace(Name="Rebar", Label="Slab bars", TypeId="Part::FeaturePython", ViewObject=VO(),
                                     Shape=types.SimpleNamespace(BoundBox=bb(1, 1, 0.5, 9, 9, 0.7)), PropertiesList=["Shape"],
                                     InListRecursive=[level], OutListRecursive=[slab])
        doc = types.SimpleNamespace(Name="House", Objects=[level, slab, bars])
        for o in doc.Objects:
            o.Document = doc
        saved = echo.FreeCAD
        echo.FreeCAD = types.SimpleNamespace(Console=types.SimpleNamespace(PrintLog=lambda *a: None))
        self.addCleanup(setattr, echo, "FreeCAD", saved)
        self.addCleanup(echo._covers.clear)
        self.assertEqual(echo.uncover(doc, [bars], direction=(0, 0, -1)), ["Floor slab"])
        self.assertEqual(level.ViewObject.Transparency, 0)


class Reads(unittest.TestCase):
    def test_refs(self):
        self.assertEqual(echo.read_refs("measure", {"a": "Block.Face6", "b": "Block.Face5"}, {}),
                         [("Block", "Face6"), ("Block", "Face5")])
        self.assertEqual(echo.read_refs("measure", {"a": "Block", "b": "My.Part"}, {}), [])
        self.assertEqual(echo.read_refs("shape_query", {"body": "Block"}, {"body": "Block", "items": [{"ref": "Face6"}]}),
                         [("Block", "Face6")])

    def test_result_names(self):
        self.assertEqual(echo.out_names("points_fit", {}, {"object": "Shaft wall", "body": "Shaft fit"}), ["Shaft fit"])
        self.assertEqual(echo.out_names("object_duplicate", {}, {"duplicated": [{"from": "Block", "copy": "Block moved"}]}),
                         ["Block moved"])
        self.assertEqual(echo.out_names("asm_ground", {"part": "Base"}, {"assembly": "CrankSlider", "grounded": ["Base"]}), ["Base"])
        self.assertEqual(echo.out_names("link_make", {}, {"link": "Ghost", "to": "Block"}), ["Ghost"])
        self.assertEqual(echo.out_names("text_document", {}, {"text": "Build notes", "chars": 18}), ["Build notes"])

    def test_sheets(self):
        self.assertEqual(echo.sheet_refs("param_set", {}, {"ref": "Params.width"}), ["Params"])
        self.assertEqual(echo.sheet_refs("asm_bom", {}, {"bom": "BOM", "sheet": "Bills_of_Materials"}), ["Bills_of_Materials", "BOM"])
        bom = types.SimpleNamespace(TypeId="Assembly::BomObject", isDerivedFrom=lambda t: t == "Spreadsheet::Sheet")
        self.assertTrue(echo.is_sheet(bom))  # asm 055: the old test by TypeId never opened it
        self.assertFalse(echo.is_sheet(types.SimpleNamespace(TypeId="Part::Box", isDerivedFrom=lambda t: False)))


class Leftovers(unittest.TestCase):
    def test_inspection_hidden_by_a_later_change(self):
        vo = types.SimpleNamespace(Visibility=True)
        insp = types.SimpleNamespace(Name="Inspection", TypeId="Inspection::Feature", ViewObject=vo)
        doc = types.SimpleNamespace(Name="Core", getObject=lambda n: insp if n == "Inspection" else None)
        self.addCleanup(echo._inspections.clear)
        self.assertEqual(echo.inspections_after(doc, "insp_run", [insp]), [])
        self.assertEqual(echo.inspections_after(doc, "insp_update", []), [])
        self.assertTrue(vo.Visibility)
        self.assertEqual(echo.inspections_after(doc, "scad_import", []), ["Inspection"])
        self.assertFalse(vo.Visibility)

    def test_profile_hidden_once_used(self):
        sk = types.SimpleNamespace(Name="Master", TypeId="Sketcher::SketchObject", ViewObject=types.SimpleNamespace(Visibility=True))
        pad = types.SimpleNamespace(Name="Pad", PropertiesList=["Profile", "Shape"], Profile=(sk, [""]),
                                    Shape=types.SimpleNamespace(isNull=lambda: False, Solids=[1]))
        self.assertEqual(echo.profiles_hidden([pad]), ["Master"])
        self.assertFalse(sk.ViewObject.Visibility)
        self.assertEqual(echo.profiles_hidden([pad]), [])

    def test_cam_operation_shown(self):
        op_vo = types.SimpleNamespace(Visibility=False)
        op = types.SimpleNamespace(Label="Profile", PropertiesList=["Path", "Base"], ViewObject=op_vo)
        stock_vo = types.SimpleNamespace(Visibility=False, Transparency=0)
        block = types.SimpleNamespace(Label="Block", ViewObject=types.SimpleNamespace(Visibility=True))
        clone = types.SimpleNamespace(Label="Clone", ViewObject=types.SimpleNamespace(Visibility=True))
        job = types.SimpleNamespace(Label="Job", Name="Job", PropertiesList=["Operations", "Stock", "Model"],
                                    Operations=types.SimpleNamespace(Group=[op]), Stock=types.SimpleNamespace(ViewObject=stock_vo),
                                    Model=types.SimpleNamespace(Group=[clone]),
                                    Proxy=types.SimpleNamespace(baseObject=lambda j, b: block))
        doc = types.SimpleNamespace(Objects=[job, op, block, clone])
        doc.getObject = lambda n: None
        done = echo.cam_shown(doc, [op])
        self.assertTrue(op_vo.Visibility)  # CAM's GUI Create does this; the App Create leaves it hidden
        self.assertTrue(stock_vo.Visibility)
        self.assertEqual(stock_vo.Transparency, 70)
        self.assertFalse(block.ViewObject.Visibility)  # the original, as CAM's job editor hides it
        self.assertIn("Profile", done)


class Words(unittest.TestCase):
    def test_key_values(self):
        self.assertEqual(activity.key_value({"facets": 152}), "152 facets")
        self.assertEqual(activity.key_value({"result": 50.8, "to": "mm", "value": 2}), "50.8 mm")
        self.assertEqual(activity.key_value({"file": "C:/Work/models/house.ifc"}), "wrote house.ifc")
        self.assertEqual(activity.key_value({"materials": [1, 2, 3]}), "3 materials")
        self.assertIsNone(activity.key_value({"note": "A long explanation."}))
        self.assertEqual(echo.change_words("Made a mesh", {"facets": 10}), "Made a mesh: 10 facets")
        self.assertEqual(echo.change_words("Padded Profile by 53 mm", {"length": 53}), "Padded Profile by 53 mm")

    def test_a_value_before_a_cut_off_note(self):
        self.assertEqual(activity.outcome("material_list", True, {"found": 12, "note": "Typical figures; check yours before ..."}),
                         "12 found")

    def test_what_was_done(self):
        self.assertEqual(activity.did("doc_info", {"comment": "x", "company": "t"}), "Set the document's comment to x")  # core 0030
        self.assertEqual(activity.did("doc_info", {}), "Read the document's details")
        self.assertEqual(activity.did("fea_load", {"gravity": True}), "Put gravity on the part")  # fem 033
        self.assertEqual(activity.did("part_from_mesh", {"mesh": "Taper"}, {"object": "Taper solid"}), "Turned Taper into a solid")

    def test_doc_graph_says_its_own_words(self):
        self.assertFalse(echo.watching("doc_graph"))  # core 0031 showed doc_info's words


class LightBatch(unittest.TestCase):
    def test_a_batch_asking_for_to_or_lines_is_not_light(self):
        def call(args):
            return json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "batch", "arguments": args}})

        calls = [{"tool": "job_status", "arguments": {}}]
        self.assertIsNotNone(gui_link._thread_batch(call({"calls": calls}), {"job_status"}))
        self.assertIsNone(gui_link._thread_batch(call({"calls": calls, "to": "x.json", "lines": "counts"}), {"job_status"}))
        self.assertIsNone(gui_link._thread_batch(call({"calls": calls, "lines": "counts"}), {"job_status"}))


if __name__ == "__main__":
    unittest.main()


# ---- round 5: the echo never opens a second task dialog ------------------------------------

class NeverASecondDialog(unittest.TestCase):
    """With a task dialog up that the echo did not open (Control.activeDialog()
    true, or a person's sketch in edit), every echo path is replayed, reads
    and changes: nothing may call setEdit, resetEdit, doubleClicked,
    activateWorkbench, runCommand, doCommand or showDialog — each of those can
    make FreeCAD ask "A dialog is already open in the task panel" in a modal
    box (ViewProviderSketch.cpp 3434-3448), which stopped a batch live."""

    TOOLS = [("sketch_new", True, {"body": "Nut"}, {"sketch": "NutSketch"}),
             ("sketch_add", True, {"sketch": "NutSketch"}, {"added": [{"ids": [0]}]}),
             ("sketch_attach", True, {"sketch": "NutSketch"}, {"sketch": "NutSketch"}),
             ("sketch_state", False, {"sketch": "NutSketch"}, {"sketch": "NutSketch"}),
             ("pd_pad", True, {"sketch": "NutSketch"}, {"feature": "Pad"}),
             ("sheet_list", False, {}, {"sheets": [{"sheet": "Dimensions", "usedBy": ["NutSketch.Constraints.hex_d"]}]}),
             ("sheet_read", False, {"sheet": "Dimensions"}, {"sheet": "Dimensions"}),
             ("sheet_set", True, {"sheet": "Dimensions"}, {"sheet": "Dimensions"}),
             ("param_set", True, {"name": "w", "value": 1}, {"ref": "Params.w"}),
             ("td_list", False, {"page": "Page"}, {"page": "Page"}),
             ("td_view", True, {"page": "Page"}, {"page": "Page", "view": "Pad"}),
             ("text_document", True, {"name": "Notes"}, {"text": "Notes"}),
             ("asm_new", True, {"parts": ["Nut"]}, {"assembly": "Nut"}),
             ("measure", False, {"a": "Pad.Face1", "b": "Pad.Face2"}, {"distance": 8.4}),
             ("object_get", False, {"object": "Pad"}, {"object": "Pad"})]

    def setUp(self):
        self.calls = []
        rec = self.calls

        def obj(name, type_id):
            o = types.SimpleNamespace(Name=name, Label=name, TypeId=type_id, InList=[], Parents=[], PropertiesList=[],
                                      isDerivedFrom=lambda t, tid=type_id: t == tid)
            o.ViewObject = types.SimpleNamespace(Visibility=True, doubleClicked=lambda n=name: rec.append(("doubleClicked", n)))
            return o

        self.doc = types.SimpleNamespace(Name="Nut", Label="Nut")
        self.doc.Objects = [obj("NutSketch", "Sketcher::SketchObject"), obj("Dimensions", "Spreadsheet::Sheet"),
                            obj("Params", "Spreadsheet::Sheet"), obj("Page", "TechDraw::DrawPage"),
                            obj("Notes", "App::TextDocument"), obj("Pad", "PartDesign::Pad")]
        for o in self.doc.Objects:
            o.Document = self.doc
        self.doc.getObject = lambda n: next((o for o in self.doc.Objects if o.Name == n), None)
        self.doc.findObjects = lambda *a, **k: []
        self.person_edit = None
        gd = types.SimpleNamespace(Document=self.doc, ActiveView=None,
                                   getInEdit=lambda: self.person_edit,
                                   setEdit=lambda *a: rec.append(("setEdit",) + a),
                                   resetEdit=lambda: rec.append(("resetEdit",)))
        self.gd = gd
        gui = types.ModuleType("FreeCADGui")
        gui.ActiveDocument = gd
        gui.Control = types.SimpleNamespace(activeDialog=lambda: True, showDialog=lambda *a: rec.append(("showDialog",)),
                                            closeDialog=lambda: rec.append(("closeDialog",)), showModelView=lambda: None)
        gui.editDocument = lambda: gd if self.person_edit is not None else None
        gui.runCommand = lambda *a: rec.append(("runCommand",) + a)
        gui.doCommand = lambda *a: rec.append(("doCommand",) + a)
        gui.activateWorkbench = lambda wb: rec.append(("activateWorkbench", wb))
        gui.activeWorkbench = lambda: types.SimpleNamespace(name=lambda: "NoneWorkbench")
        gui.listWorkbenches = lambda: {w: 1 for _p, w in echo.WORKBENCH}
        gui.Selection = types.SimpleNamespace(clearSelection=lambda: None, addSelection=lambda *a: None, getSelection=lambda: [])
        gui.getMainWindow = lambda: types.SimpleNamespace(statusBar=lambda: types.SimpleNamespace(showMessage=lambda *a: None),
                                                          findChild=lambda *a: None, findChildren=lambda *a: [])
        gui.SendMsgToActiveView = lambda *a: None
        self.had = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        keys = ("FreeCAD", "enabled", "say", "_paint", "_wait", "_qt", "fit", "rings_off", "flash_command", "restore_covers")
        self.saved = {k: getattr(echo, k) for k in keys}
        params = types.SimpleNamespace(GetBool=lambda k, d=True: d, GetInt=lambda k, d=0: d)
        echo.FreeCAD = types.SimpleNamespace(GuiUp=True, ActiveDocument=self.doc, ParamGet=lambda p: params,
                                             listDocuments=lambda: {"Nut": self.doc}, getDocument=lambda n: self.doc,
                                             Console=types.SimpleNamespace(PrintLog=lambda *a: None))
        echo.enabled = lambda: True
        echo.say = lambda words, ms=echo.HOLD_MS, where="": words
        echo._paint = lambda *a, **k: None
        echo._wait = lambda ms: None
        echo._qt = lambda: (None, None, types.SimpleNamespace(QMdiArea=object, QToolBar=object, QTabBar=object))
        echo.fit = lambda animate=True, selection=False: "all"
        echo.rings_off = lambda: True
        echo.flash_command = lambda *a, **k: "button"
        echo.restore_covers = lambda: []
        self.addCleanup(echo._agent_edits.clear)

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(echo, k, v)
        if self.had is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = self.had

    def replay(self):
        from test_echo_hold import Tool, reply

        for name, changes, args, body in self.TOOLS:
            session = types.SimpleNamespace(doc=self.doc, batch_now=None)
            e = echo.Echo(session)
            tool = Tool(name, changes)
            e.before(tool, dict(args))
            e.after(tool, dict(args), reply(body))
            self.assertEqual(self.calls, [], name)

    def test_a_task_dialog_is_open(self):
        self.replay()

    def test_a_persons_sketch_is_in_edit(self):
        sk = self.doc.getObject("NutSketch")
        self.person_edit = types.SimpleNamespace(Object=sk)
        self.replay()

    def test_the_rule(self):
        self.assertEqual(echo.foreign_task(), "a task dialog is open")
        sk = self.doc.getObject("NutSketch")
        self.person_edit = types.SimpleNamespace(Object=sk)
        self.assertIn("not by the agent", echo.foreign_task())
        echo._agent_edits.add(("Nut", "NutSketch"))
        self.assertIsNone(echo.foreign_task(self.gd))  # the echo's own sketch here: setEdit closes it, asking nothing
