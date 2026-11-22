# SPDX-License-Identifier: LGPL-2.1-or-later
# The hub's faults read off the live run of the unproven-hub and bim-rest
# models (private records: unproven-run-findings.md), on stand-ins (plain
# Python, no FreeCAD):
#   - workbench { activate } on the workbench that is active already
#     answers (the entry; its behaviour beside the old handler is in
#     tests/test_dataapp_data.py);
#   - job_start inside a batch: the batch is named as the reason, with what
#     to do, for a read that would be a job on its own;
#   - view_snapshot's fit frames the shown parts' own box, not the whole
#     scene graph;
#   - the unwrapping's own Python: a crash while FreeCAD's modules load is
#     told from one in the unwrapping;
#   - FreeCAD's nester: its printed reason is read, and the rotations are
#     tried one by one when together they stop it (the tool's behaviour
#     beside the old handler is in tests/test_bim_data.py);
#   - the FEM route's failure says where in the route it came up.
# draft_outline's and td_view_more's relative paths, td_view_more share and
# bim_library's merged records object are in the old-against-new tests of
# their families (test_datadraft_data, test_datatd2_data, test_bim_data).
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentlink import jobs  # noqa: E402
from test_hubfix2 import in_a_process  # noqa: E402

# FreeCAD's settings as the batch reads them, and the modules the families import.
SETUP = '''
    class P:
        def __getattr__(self, k):
            return lambda name=None, default=None: default if default is not None else (0 if k in ("GetInt", "GetFloat", "GetUnsigned") else False if k == "GetBool" else "")
    fc.ParamGet = lambda path: P()
    for m in ("Mesh", "MeshPart", "Fem", "Arch", "Draft"):
        sys.modules.setdefault(m, Any(m))
'''


def entries():
    with open(os.path.join(HERE, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


class WorkbenchAlreadyActive(unittest.TestCase):
    def test_the_entry_answers_before_it_asks_freecad(self):
        steps = entries()["workbench"]["steps"]
        then = next(s for s in steps if "then" in s)["then"]
        kinds = [next(k for k in ("let", "refuse", "answer", "do") if k in s) for s in then]
        # the workbench found, was read, the answer for "already active", only then FreeCAD asked to switch
        already = next(i for i, s in enumerate(then) if "answer" in s and s.get("when") == "=was == hit")
        asked = next(i for i, s in enumerate(then) if "let" in s and "ok" in s["let"])
        self.assertLess(already, asked, kinds)
        self.assertEqual(then[already]["answer"]["fields"]["note"], "Already active.")
        self.assertEqual(set(then[already]["answer"]["fields"]), {"active", "was", "note", "workbenches"})
        # FreeCAD's False is not read as a failure any more: only the workbench that is active after the call
        failed = next(s for s in then if "refuse" in s and s.get("code") == "failed")
        self.assertEqual(failed["when"], "=gui.activeWorkbench().name() != hit")
        self.assertIn("FreeCAD did not switch to {hit}", failed["refuse"]["fmt"])


class JobStartInABatch(unittest.TestCase):
    def test_the_words_name_the_batch_and_what_to_do(self):
        w = jobs.start_in_batch_refusal("body_check")
        self.assertTrue(w.startswith("job_start: not inside a batch, which is one answer and starts no job"), w)
        self.assertIn('call job_start { tool: "body_check", arguments } on its own', w)
        self.assertIn("call body_check itself here: a heavy read inside a batch runs in its place and the batch waits for it", w)
        self.assertNotIn("cannot run as a job", w)

    def test_in_a_batch_a_read_is_refused_for_the_batch_and_other_tools_for_themselves(self):
        out = tempfile.mkdtemp(prefix="agentlink-hubfix4-")
        got = in_a_process(SETUP + '''
    from agentlink import tools
    s = tools.Session(out_dir=%r)
    srv = tools.build_server(s, lean=False)
    def call(name, args):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
        return [r.get("isError", False), json.loads(r["content"][0]["text"])]
    def start(tool, **arguments):
        return {"tool": "job_start", "arguments": {"tool": tool, "arguments": arguments}}
    b = call("batch", {"calls": [start("body_check"), start("session_state"), start("nosuchtool"), start("view_render")], "rollback": False, "stopOnError": False})
    alone = call("job_start", {"tool": "session_state"})
    print(json.dumps({"batch": b, "alone": alone}))
''' % out)
        err, b = got["batch"]
        self.assertFalse(err, b)
        rows = b["results"]
        self.assertEqual([r["ok"] for r in rows], [False] * 4, rows)
        said = [r["error"]["message"] for r in rows]
        # a read that would be a job on its own: the batch is why not
        self.assertEqual(rows[0]["error"]["code"], "invalid_input")
        self.assertEqual(said[0], jobs.start_in_batch_refusal("body_check"))
        # a tool that is never a job is still refused for what it is, in or out of a batch
        self.assertIn("session_state cannot run as a job: it changes nothing, but it", said[1])
        self.assertEqual(said[1], got["alone"][1]["error"]["message"])
        self.assertEqual(rows[2]["error"], {"code": "not_found", "message": "nosuchtool: no such tool — tool_groups lists them."})
        self.assertIn("view_render cannot run as a job: only a read that leaves the window and the 3D view alone can", said[3])


class SnapshotFit(unittest.TestCase):
    BODY = SETUP + '''
    class Node:
        def __init__(self, kind):
            self.kind, self.kids, self.refs = kind, [], 0
            self.translation = self
        def setValue(self, *xyz):
            self.at = list(xyz)
        def addChild(self, c):
            self.kids.append(c)
        def ref(self):
            self.refs += 1
        def unref(self):
            self.refs -= 1
    coin = types.ModuleType("pivy.coin")
    coin.SbViewportRegion = lambda w, h: ("region", w, h)
    for k in ("SoSeparator", "SoTranslation", "SoCube"):
        setattr(coin, k, (lambda k: lambda: Node(k))(k))
    pivy = types.ModuleType("pivy")
    pivy.coin = coin
    sys.modules["pivy"], sys.modules["pivy.coin"] = pivy, coin

    class Cam:
        def viewAll(self, graph, region):
            calls.append((graph, region))
    class View:
        def fitAll(self):
            calls.append("fitAll")
        def getCameraNode(self):
            return Cam()
        def getSceneGraph(self):
            return "the whole scene graph"
    class Box:
        XLength, YLength, ZLength = 40.0, 30.0, 10.0
        Center = types.SimpleNamespace(x=20.0, y=15.0, z=5.0)
    calls = []
    from agentlink.families import view as V
'''

    def test_a_fit_frames_the_parts_own_box_as_a_cube_in_its_place(self):
        got = in_a_process(self.BODY + '''
    ok = V.snap_fit(View(), 800, 600, Box())
    graph, region = calls[1]
    at, cube = graph.kids
    print(json.dumps({"ok": ok, "first": calls[0], "n": len(calls), "graph": graph.kind, "kids": [k.kind for k in graph.kids], "at": at.at,
                      "cube": [cube.width, cube.height, cube.depth], "region": list(region), "refs": graph.refs}))
''')
        self.assertEqual(got, {"ok": True, "first": "fitAll", "n": 2, "graph": "SoSeparator", "kids": ["SoTranslation", "SoCube"], "at": [20.0, 15.0, 5.0],
                               "cube": [40.0, 30.0, 10.0], "region": ["region", 800, 600], "refs": 0})

    def test_a_flat_box_is_still_a_cube_and_no_box_is_the_scene_graph(self):
        got = in_a_process(self.BODY + '''
    class Flat(Box):
        ZLength = 0.0
    class Nothing(Box):
        XLength = YLength = ZLength = 0.0
    V.snap_fit(View(), 400, 300, Flat())
    flat = calls[-1][0].kids[1]
    V.snap_fit(View(), 400, 300, None)
    none = calls[-1][0]
    V.snap_fit(View(), 400, 300, Nothing())
    print(json.dumps({"flat": [flat.width, flat.height, flat.depth], "none": none, "nothing": calls[-1][0]}))
''')
        self.assertEqual(got["flat"][:2], [40.0, 30.0])
        self.assertGreater(got["flat"][2], 0)
        self.assertEqual(got["none"], "the whole scene graph")
        self.assertEqual(got["nothing"], "the whole scene graph")

    def test_the_entry_and_the_grid_fit_with_the_shown_box(self):
        with open(os.path.join(HERE, "agentlink", "families", "view.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('"snap_fit": lambda view, w, h: snap_fit(view, w, h, _fit_box(s))', src)
        self.assertIn("snap_fit(view, cw, ch, _fit_box(s))", src)
        # the check after the fit reads the same box
        self.assertIn("shown, box = shown_box(s)", src)


class UnwrapEnds(unittest.TestCase):
    def ends(self, stderr, code):
        return in_a_process(SETUP + '''
    from agentlink.families import meshobj
    print(json.dumps([meshobj.UNWRAP_MARK, list(meshobj.unwrap_stop(%r, %r))]))
''' % (stderr, code))[1]

    def test_a_crash_while_loading_is_told_from_one_in_the_unwrapping(self):
        mark = "agentlink-unwrap: "
        # brought down at import: no word of its own
        self.assertEqual(self.ends(mark + "loading\n", -11), ["load", "it stopped (code -11)"])
        # an import that fails with a word
        self.assertEqual(self.ends(mark + "loading\nTraceback (most recent call last):\nModuleNotFoundError: No module named 'flatmesh'\n", 1),
                         ["load", "ModuleNotFoundError: No module named 'flatmesh'"])
        # loaded, then brought down in the unwrapping: the surface's
        self.assertEqual(self.ends(mark + "loading\n" + mark + "loaded\n", -11), ["stopped", "it stopped (code -11)"])
        self.assertEqual(self.ends(mark + "loading\n" + mark + "loaded\nRuntimeError: singular matrix\n", 1), ["stopped", "RuntimeError: singular matrix"])
        # a Python that never marked anything (an older helper, a stand-in): as before
        self.assertEqual(self.ends("Traceback\nRuntimeError: singular matrix\n", 1), ["stopped", "RuntimeError: singular matrix"])
        self.assertEqual(self.ends("", -11), ["stopped", "it stopped (code -11)"])

    def test_the_helper_marks_before_and_after_the_imports_and_the_entry_has_the_refusal(self):
        with open(os.path.join(HERE, "agentlink", "families", "meshobj.py"), encoding="utf-8") as f:
            src = f.read()
        i, j, k = src.index("\"at('loading')"), src.index('"import flatmesh'), src.index("\"at('loaded')")
        self.assertLess(i, j)
        self.assertLess(j, k)
        said = json.dumps(entries()["meshobj_unwrap"]["steps"], ensure_ascii=False)
        self.assertIn("FreeCAD's own modules would not load there ({why}): nothing was unwrapped, and this surface is not the cause", said)
        self.assertIn("=stop == 'load'", said)


class NesterStops(unittest.TestCase):
    def test_its_printed_reason_is_read(self):
        got = in_a_process(SETUP + '''
    from agentlink.families import bim_gaps
    lines = [
        "Executing conformity tests… Everything OK ( 0:00:00.000321 )\\nPlacing piece 1 / 3 Area: 1500.00 cm² :  0.0 ,  90.0 ,  Adding piece to sheet 1\\n"
        "Placing piece 3 / 3 Area: 600.00 cm² :  0.0 ,  90.0 ,  Could not determine location on sheet. Aborting.\\n",
        "Executing conformity tests… One of the shapes does not contain exactly one face. Aborting.\\n",
        "Placing piece 1 / 1 Area: 2 m² :  0 , 90 , One face does not fit in the container. Aborting.\\n",
        "Executing conformity tests… Everything OK ( 0:00:00.1 )\\nRun time: 0:00:01\\n",
        "",
    ]
    print(json.dumps([bim_gaps.nest_reason(x) for x in lines]))
''')
        self.assertEqual(got[0], "Could not determine location on sheet.")
        self.assertEqual(got[1], "One of the shapes does not contain exactly one face.")
        self.assertEqual(got[2], "One face does not fit in the container.")
        self.assertEqual(got[3:], [None, None])

    def test_the_entry_says_which_rotation_laid_them_out(self):
        e = entries()["bim_nest"]
        f = e["answer"]["fields"]
        self.assertEqual(f["rotationsUsed"], {"when": "=nest_alone(n) is not None", "value": "=nest_alone(n)"})
        self.assertIn("each was tried alone", f["rotationsNote"]["value"])
        said = json.dumps(e["steps"], ensure_ascii=False)
        self.assertIn("The pieces would not nest: FreeCAD's nester stopped{nest_why(n)} Check each piece is a flat face", said)


class FemRouteFailure(unittest.TestCase):
    def test_where_in_the_route_it_came_up(self):
        got = in_a_process(SETUP + '''
    from agentlink.families import strength
    def route():
        raise RuntimeError("Cannot add static property")   # the line the mark must name
    try:
        route()
    except RuntimeError as e:
        here = strength.failed_at(e, own=__file__ if "__file__" in globals() else "<string>")
        elsewhere = strength.failed_at(e)
    print(json.dumps([here, elsewhere]))
''')
        self.assertRegex(got[0], r"^ \(<string>:\d+\)$")
        self.assertEqual(got[1], "")  # no frame in strength.py: nothing added

    def test_the_route_says_it(self):
        with open(os.path.join(HERE, "agentlink", "families", "strength.py"), encoding="utf-8") as f:
            self.assertIn('route_why = f"FreeCAD\'s FEM route failed here: {type(e).__name__}: {e}{failed_at(e)}"', f.read())


class StepKey(unittest.TestCase):
    def test_a_through_all_pocket_is_not_keyed_by_a_length_it_does_not_use(self):
        got = in_a_process(SETUP + '''
    from agentlink.families import notes
    class Q:
        def __init__(self, text):
            self.UserString = text
    class Shape:
        Solids = [1]
        def __init__(self, v):
            self.Volume = v
        def isNull(self):
            return False
    class F:
        def __init__(self, name, tid, vol, **props):
            self.Name = self.Label = name
            self.TypeId, self.Shape = tid, Shape(vol)
            self.__dict__.update(props)
            self.PropertiesList = list(props)
        def isDerivedFrom(self, t):
            return t == "PartDesign::Feature"
        def isValid(self):
            return True
    class Body:
        pass
    b = Body()
    b.Group = [F("Pad", "PartDesign::Pad", 12000.0, Length=Q("10.00 mm"), Type="Length"),
               F("Pocket", "PartDesign::Pocket", 11214.6, Length=Q("5.00 mm"), Type="ThroughAll"),
               F("Slot", "PartDesign::Pocket", 10674.6, Length=Q("3.00 mm"), Type="Length"),
               F("Boss", "PartDesign::Pad", 11000.0, Length=Q("4.00 mm"), Type="TwoLengths"),
               F("Stop", "PartDesign::Pocket", 10900.0, Length=Q("5.00 mm"), Type="UpToFace"),
               F("Round", "PartDesign::Fillet", 10890.0, Radius=Q("1.00 mm"))]
    b.Tip = b.Group[-1]
    print(json.dumps([r["key"] for r in notes.steps_of(b)]))
''')
        self.assertEqual(got, ["Length 10.00 mm", "Type ThroughAll", "Length 3.00 mm", "Length 4.00 mm", "Type UpToFace", "Radius 1.00 mm"])


if __name__ == "__main__":
    unittest.main()
