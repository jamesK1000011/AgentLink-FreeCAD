# SPDX-License-Identifier: LGPL-2.1-or-later
# Findings 33-39 of the M18 live build (18 Nov 2026), without FreeCAD:
# heavy changes estimated first (insp_run, part_from_mesh, export), a big
# export sent to a job, a boolean sized by the face pairs whose boxes meet,
# a batch's start-time guess scaled by input size, part_from_mesh's note
# following refine, catalogue reads with the document closed, the link's
# own dialog press verified and pressed again, and a recovered copy of a
# document never saved kept open after a restart.
import json
import os
import sys
import tempfile
import time
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


class Home(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="agentlink-m18-")
        self.env = {k: os.environ.get(k) for k in ("AGENTLINK_HOME", "AGENTLINK_GATE")}
        os.environ["AGENTLINK_HOME"] = self.home
        os.environ["AGENTLINK_GATE"] = "1"
        from agentlink import heavy, jobs, keep

        self.heavy, self.jobs, self.keep = heavy, jobs, keep

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---- stand-ins ------------------------------------------------------------------------------

class Box:
    def __init__(self, lo, hi):
        self.XMin, self.YMin, self.ZMin = lo
        self.XMax, self.YMax, self.ZMax = hi
        self.DiagonalLength = sum((b - a) ** 2 for a, b in zip(lo, hi)) ** 0.5


class BSpline:
    def __init__(self, u, v):
        self.NbUPoles, self.NbVPoles = u, v


class Plane:
    pass


class Face:
    def __init__(self, srf=None, box=None):
        self.Surface = srf or Plane()
        if box is not None:
            self.BoundBox = box


class Shape:
    def __init__(self, faces, area=0.0, box=None):
        self.Faces = faces
        self.Area = area
        self.BoundBox = box or Box((0, 0, 0), (1, 1, 1))

    def isNull(self):
        return False


class Mesh:
    def __init__(self, facets):
        self.CountFacets = facets
        self.CountPoints = facets // 2


class Obj:
    def __init__(self, name, shape=None, mesh=None):
        self.Name = self.Label = name
        self.InList = []
        if shape is not None:
            self.Shape = shape
        if mesh is not None:
            self.Mesh = mesh


class Doc:
    def __init__(self, objs):
        self.Objects = objs
        self.Name = "D"

    def getObject(self, n):
        return next((o for o in self.Objects if o.Name == n), None)


class Sess:
    def __init__(self, doc):
        self.doc = doc


class Tool:
    def __init__(self, name, changes=True):
        self.name, self.changes = name, changes

    def changes_for(self, a):
        return self.changes


def smooth_loft():
    """Body032 of the M18 build: a 3-face smooth loft (one B-spline side of
    many poles, two flat caps)."""
    return Obj("Body032", Shape([Face(BSpline(91, 80)), Face(), Face()], area=20000.0, box=Box((0, 0, 0), (40, 30, 160))))


# ---- 38: part_from_mesh estimated first --------------------------------------------------------

class FromMesh(Home):
    def test_size_is_triangles_doubled_by_refine(self):
        s = Sess(Doc([Obj("Scan", mesh=Mesh(35000))]))
        self.assertEqual(self.heavy.sized_size(s, "part_from_mesh", {"mesh": "Scan"}), 70000.0)
        self.assertEqual(self.heavy.sized_size(s, "part_from_mesh", {"mesh": "Scan", "refine": False}), 35000.0)
        self.assertIsNone(self.heavy.sized_size(s, "part_from_mesh", {"mesh": "Nope"}))

    def test_binary_stl_file_is_counted_by_its_header(self):
        p = os.path.join(self.home, "t.stl")
        with open(p, "wb") as f:
            f.write(b"\0" * 80 + (3).to_bytes(4, "little") + b"\0" * 150)
        self.assertEqual(self.heavy.sized_size(Sess(Doc([])), "part_from_mesh", {"file": p}), 6.0)

    def test_big_mesh_is_asked_then_runs_with_the_long_deadline(self):
        from agentlink.protocol import ToolError

        g = self.heavy.Gate(Sess(Doc([Obj("Scan", mesh=Mesh(35000))])))
        t, a = Tool("part_from_mesh"), {"mesh": "Scan"}
        with self.assertRaises(ToolError) as cm:
            g.before(t, a)
        m = cm.exception.message
        for w in ("35,000 triangles", "refine", "meshobj_decimate", "refine: false", "Nothing was run"):
            self.assertIn(w, m)
        started = time.time()
        g.before(t, a)  # the same call again runs it
        self.assertGreater(self.keep.heavy_call_limit(started, time.time()), 300)
        g.after(t, a, True)
        self.assertFalse(os.path.exists(self.keep.heavy_call_mark()))

    def test_small_mesh_runs_at_once_and_is_marked(self):
        g = self.heavy.Gate(Sess(Doc([Obj("Small", mesh=Mesh(3600))])))
        started = time.time()
        g.before(Tool("part_from_mesh"), {"mesh": "Small"})
        self.assertIsNotNone(self.keep.heavy_call_limit(started, time.time()))
        g.after(Tool("part_from_mesh"), {}, True)

    def test_note_follows_refine(self):
        with open(os.path.join(os.path.dirname(HERE), "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            steps = json.load(f)["entries"]["part_from_mesh"]["steps"]
        notes = [s for s in steps if isinstance(s.get("let"), dict) and isinstance(s["let"].get("note"), str)]
        merged = [s for s in notes if "(refine)" in s["let"]["note"]]
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].get("when"), "=a.get('refine', True)")
        plain = [s for s in notes if "refine: false" in s["let"]["note"]]
        self.assertEqual(len(plain), 1)
        self.assertNotIn("when", plain[0])
        self.assertLess(steps.index(plain[0]), steps.index(merged[0]))


# ---- 33: insp_run of a smooth loft against a big scan, the loft the nominal --------------------

class Insp(Home):
    def test_solid_nominal_counts_points_times_its_faces(self):
        scan = Obj("Scan", mesh=Mesh(140000))
        s = Sess(Doc([scan, smooth_loft()]))
        mesh_vs_loft = self.heavy.sized_size(s, "insp_run", {"actual": "Scan", "nominals": ["Body032"]})
        self.assertGreater(self.keep.sized_estimate({}, "insp_run", mesh_vs_loft), 60)
        # a plain box nominal of 6 faces stays light
        s2 = Sess(Doc([scan, Obj("Box", Shape([Face()] * 6))]))
        light = self.heavy.sized_size(s2, "insp_run", {"actual": "Scan", "nominals": ["Box"]})
        self.assertLess(self.keep.sized_estimate({}, "insp_run", light), 30)

    def test_asked_first_with_the_lighter_ways(self):
        from agentlink.protocol import ToolError

        g = self.heavy.Gate(Sess(Doc([Obj("Scan", mesh=Mesh(140000)), smooth_loft()])))
        with self.assertRaises(ToolError) as cm:
            g.before(Tool("insp_run"), {"actual": "Scan", "nominals": ["Body032"]})
        self.assertIn("larger spacing", cm.exception.message)


# ---- 34: export that tessellates a smooth loft ---------------------------------------------------

class Export(Home):
    def sess(self):
        return Sess(Doc([smooth_loft()]))

    def test_tessellating_formats_only(self):
        s = self.sess()
        stl = self.heavy.sized_size(s, "export", {"objects": ["Body032"], "format": "stl", "tolerance": 0.05})
        self.assertGreater(self.keep.sized_estimate({}, "export", stl), 60)
        self.assertEqual(self.heavy.sized_size(s, "export", {"objects": ["Body032"], "format": "step"}), 0.0)
        self.assertEqual(self.heavy.sized_size(s, "export", {"objects": ["Body032"], "path": "/x/out.brep"}), 0.0)
        # a coarser tolerance is lighter
        coarse = self.heavy.sized_size(s, "export", {"objects": ["Body032"], "format": "stl", "tolerance": 0.2})
        self.assertLess(coarse, stl)

    def test_on_its_own_it_goes_to_a_job(self):
        t = Tool("export", changes=False)
        s = self.sess()
        self.assertTrue(self.jobs.wanted(t, {"objects": ["Body032"], "format": "stl", "tolerance": 0.05}, s))
        self.assertFalse(self.jobs.wanted(t, {"objects": ["Body032"], "format": "step"}, s))
        # a job is not asked nor marked: the window is free
        g = self.heavy.Gate(s)
        g.as_job = True
        g.before(t, {"objects": ["Body032"], "format": "stl", "tolerance": 0.05})
        self.assertFalse(os.path.exists(self.keep.heavy_call_mark()))
        g.as_job = False

    def test_in_a_batch_it_is_asked_first(self):
        from agentlink.protocol import ToolError

        s = self.sess()
        s.batch_now = {"i": 0}
        t = Tool("export", changes=False)
        a = {"objects": ["Body032"], "format": "stl", "tolerance": 0.05}
        self.assertFalse(self.jobs.wanted(t, a, s))
        g = self.heavy.Gate(s)
        with self.assertRaises(ToolError) as cm:
            g.before(t, a)
        self.assertIn("larger tolerance", cm.exception.message)


# ---- the part_boolean estimate: face pairs whose boxes meet ------------------------------------

class BooleanPairs(Home):
    def grid(self, n, x0=0.0):
        """n unit faces in a row along x from x0."""
        return [Face(box=Box((x0 + i, 0, 0), (x0 + i + 1, 1, 1))) for i in range(n)]

    def test_only_meeting_boxes_count(self):
        base = Obj("Base", Shape(self.grid(36000)))
        cutter = Obj("Cutter", Shape(self.grid(586, x0=100.0)))
        box = Obj("Box", Shape(self.grid(6, x0=5000.0)))
        s = Sess(Doc([base, cutter, box]))
        cut = self.heavy.boolean_parts(s, {"op": "cut", "base": "Base", "tools": ["Cutter"]})
        self.assertLess(cut["pairs"], 36000 * 586 / 100)
        self.assertEqual((cut["base"], cut["tools"]), (36000, 586))
        est_cut = self.keep.sized_estimate({}, "part_boolean", cut["size"])
        common = self.heavy.boolean_parts(s, {"op": "common", "base": "Base", "tools": ["Box"]})
        est_common = self.keep.sized_estimate({}, "part_boolean", common["size"])
        # live: the common took 29 s; the cut was put at 40 min before
        self.assertTrue(10 < est_common < 90, est_common)
        self.assertLess(est_cut, 5 * 60)
        self.assertEqual(self.keep.sized_key("part_boolean", {}), "part_boolean boxes")

    def test_words_name_the_pairs(self):
        from agentlink.protocol import ToolError

        base = Obj("Base", Shape(self.grid(60000)))
        tool = Obj("Tool", Shape(self.grid(60000)))
        g = self.heavy.Gate(Sess(Doc([base, tool])))
        with self.assertRaises(ToolError) as cm:
            g.before(Tool("part_boolean"), {"op": "fuse", "base": "Base", "tools": ["Tool"]})
        self.assertIn("face pairs whose boxes meet", cm.exception.message)


# ---- 37: a batch's start-time guess scaled by input size ---------------------------------------

class Typical(Home):
    def test_scaled_by_triangles(self):
        s = Sess(Doc([Obj("Big", mesh=Mesh(36000)), Obj("Small", mesh=Mesh(3600))]))
        self.jobs._RECENT.pop("part_from_mesh", None)
        self.jobs.note_time("part_from_mesh", 78.0, 72000.0)
        got = self.jobs.typical("part_from_mesh", s, {"mesh": "Small"})
        self.assertAlmostEqual(got, 7.8, delta=0.01)
        self.assertAlmostEqual(self.jobs.typical("part_from_mesh", s, {"mesh": "Small", "refine": False}), 3.9, delta=0.01)
        # no input size to scale by: None, so the call starts
        self.assertIsNone(self.jobs.typical("part_from_mesh", s, {"file": "/nowhere.obj"}))
        self.assertIsNone(self.jobs.typical("part_from_mesh"))
        self.jobs._RECENT.pop("part_from_mesh", None)

    def test_size_comes_from_the_gate(self):
        s = Sess(Doc([Obj("Small", mesh=Mesh(3600))]))
        self.jobs._RECENT.pop("part_from_mesh", None)
        g = self.heavy.Gate(s)
        g.before(Tool("part_from_mesh"), {"mesh": "Small"})
        g.after(Tool("part_from_mesh"), {}, True)
        self.assertEqual(s.sized_now, ("part_from_mesh", 7200.0))
        self.jobs.note_slow(Tool("part_from_mesh"), {"mesh": "Small"}, s, 2.0)
        self.assertEqual(self.jobs._RECENT["part_from_mesh"], [(2.0, 7200.0)])
        self.assertIsNone(s.sized_now)
        self.jobs._RECENT.pop("part_from_mesh", None)


# ---- 36: catalogue reads with the agent's document closed ---------------------------------------

def _gui_link():
    had = {k: sys.modules.get(k) for k in ("FreeCAD", "agentlink.tools", "agentlink.gui_link")}
    try:
        import FreeCAD  # noqa: F401
    except ImportError:
        fake = types.ModuleType("FreeCAD")
        fake.Console = types.SimpleNamespace(PrintWarning=lambda *a: None, PrintMessage=lambda *a: None)
        sys.modules["FreeCAD"] = fake
    if had["agentlink.tools"] is None:
        tools = types.ModuleType("agentlink.tools")
        tools.Session = tools.build_server = None
        sys.modules["agentlink.tools"] = tools
    sys.modules.pop("agentlink.gui_link", None)
    try:
        from agentlink import gui_link

        return gui_link
    finally:
        for k, v in had.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


gl = _gui_link()


def call(name, args=None):
    return json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}})


class ClosedDoc(unittest.TestCase):
    def test_catalogue_reads_need_no_document(self):
        for n in ("tool_find", "tool_groups", "guide_read", "session_state", "job_status", "usage_report"):
            self.assertTrue(gl.pinned_free_call(call(n), n), n)
        self.assertFalse(gl.pinned_free_call(call("part_box"), "part_box"))
        b = call("batch", {"calls": [{"tool": "tool_find"}, {"tool": "guide_read"}]})
        self.assertTrue(gl.pinned_free_call(b, "batch"))
        self.assertTrue(gl.catalogue_call(b, "batch"))
        mixed = call("batch", {"calls": [{"tool": "tool_find"}, {"tool": "part_box"}]})
        self.assertFalse(gl.pinned_free_call(mixed, "batch"))
        self.assertFalse(gl.catalogue_call(mixed, "batch"))

    def test_catalogue_reads_keep_the_word_for_the_next_call(self):
        self.assertTrue(gl.catalogue_call(call("tool_find"), "tool_find"))
        self.assertFalse(gl.catalogue_call(call("doc_open"), "doc_open"))
        self.assertFalse(gl.catalogue_call(call("session_state"), "session_state"))


# ---- 35: the link's own press verified and pressed again --------------------------------------

class PressVerified(Home):
    def test_pressed_again_harder_then_said_failed(self):
        tries = []
        old = gl.press_hard
        gl.press_hard = lambda d, label, n: tries.append(n) or True
        try:
            link = gl.Link.__new__(gl.Link)
            key = ("Gui::Dialog::DocumentRecovery", "Document Recovery", "")
            t = [1000.0]
            real = gl.time.time
            gl.time.time = lambda: t[0]
            try:
                d = {"title": "Document Recovery"}
                link._press_and_verify(d, key, "Cancel")
                self.assertEqual((tries, d.get("pressed")), ([0], "Cancel"))
                t[0] += 1.0  # too soon to press again
                d = {"title": "Document Recovery"}
                link._press_and_verify(d, key, "Cancel")
                self.assertEqual(tries, [0])
                for i in range(1, 4):
                    t[0] += gl.PRESS_RETRY
                    d = {"title": "Document Recovery"}
                    link._press_and_verify(d, key, "Cancel")
                    self.assertEqual(tries[-1], i)
                    self.assertEqual(d.get("pressed"), "Cancel")
                t[0] += gl.PRESS_RETRY
                d = {"title": "Document Recovery"}
                link._press_and_verify(d, key, "Cancel")
                self.assertEqual(len(tries), gl.PRESS_TRIES)
                self.assertNotIn("pressed", d)
                self.assertEqual(d["pressFailed"], gl.PRESS_TRIES)
            finally:
                gl.time.time = real
        finally:
            gl.press_hard = old
        log = [json.loads(ln) for ln in open(os.path.join(self.home, "watchdog.log"))]
        self.assertTrue(any(e.get("try") == 2 for e in log), log)
        self.assertTrue(any(e.get("pressFailed") for e in log), log)

    def test_press_hard_escalates(self):
        calls = []

        class W:
            def done(self, r):
                calls.append(("done", r))

            def hide(self):
                calls.append("hide")

            def close(self):
                calls.append("close")

        self.assertTrue(gl.press_hard({"widget": W()}, "Cancel", 2))
        self.assertTrue(gl.press_hard({"widget": W()}, "Cancel", 3))
        self.assertEqual(calls, [("done", 0), "hide", "close"])
        self.assertFalse(gl.press_hard({}, "Cancel", 3))


# ---- 39: a recovered copy of a document never saved is kept ------------------------------------

class UnsavedKept(unittest.TestCase):
    def test_unsaved_copy_is_not_a_stray(self):
        from agentlink import supervise as sv

        tmp = tempfile.gettempdir()
        before = [{"name": "M18Build", "label": "M18Build", "file": "", "modified": True},
                  {"name": "Grip", "label": "Grip", "file": "/srv/Grip.FCStd"}]
        # app_recover named its copy otherwise than the window did
        recovered = [{"label": "M18Build", "document": "M18Build_recovered"}]
        now = [{"name": "M18Build001", "label": "M18Build (recovered)", "file": os.path.join(tmp, "fc_recovery_files", "M18Build", "Document.xml")},
               {"name": "Grip_r", "label": "Grip (recovered 09:00)", "file": os.path.join(tmp, "agentlink-recovered-g", "Grip_r.FCStd")},
               {"name": "Old_r", "label": "Old (recovered 01:00)", "file": os.path.join(tmp, "agentlink-recovered-o", "Old_r.FCStd"), "modified": True}]
        self.assertEqual([d["name"] for d in sv.strays(before, recovered, now)], ["Grip_r"])
        self.assertEqual([(d["name"], why) for d, why in sv.kept_copies(before, recovered, now)], [("M18Build001", "unsaved"), ("Old_r", "changed")])
        self.assertEqual(sv.base_label("M18Build (recovered 10:00)"), "M18Build")


if __name__ == "__main__":
    unittest.main()
