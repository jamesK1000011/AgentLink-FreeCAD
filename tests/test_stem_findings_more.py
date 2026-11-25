# SPDX-License-Identifier: LGPL-2.1-or-later
# More from the bike stem and shell test drives (16 Nov 2026), held here with
# stand-ins where FreeCAD is not importable: a render's time read against
# what it drew; a Body of two solids (AllowCompound) kept as a part and
# checked solid by solid; a BOP-only finding on a valid shape a warning; a
# sketch attached to the feature that owns its face; a rolled-back batch
# leaving nothing behind; long reads as jobs; the whole body mirrored;
# parts found by object name while a workbench relabels them; each layer a
# colour of its own.
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class _Home(unittest.TestCase):
    """A queue of its own: AGENTLINK_HOME in a temp folder."""

    def setUp(self):
        self.env = {k: os.environ.get(k) for k in ("AGENTLINK_HOME", "AGENTLINK_GATE")}
        os.environ["AGENTLINK_HOME"] = tempfile.mkdtemp(prefix="agentlink-more-")
        os.environ.pop("AGENTLINK_GATE", None)
        from agentlink import keep

        self.keep = keep

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---- 1. a render's time follows what it drew ---------------------------------------------

class RenderTime(_Home):
    def test_range_from_rates(self):
        q = {"timings": {"t": [[100, 10.0], [200, 30.0], [400, 40.0]]}}
        lo, mid, hi = self.keep.estimate_range(q, "t", 1000)
        self.assertAlmostEqual(lo, 100.0)
        self.assertAlmostEqual(mid, 100.0)
        self.assertAlmostEqual(hi, 150.0)
        self.assertIsNone(self.keep.estimate_range({}, "t", 5))
        self.assertIn("to", self.keep.said_range((10, 20, 40)))
        self.assertEqual(self.keep.said_range((20, 20, 20)), "about 20 s")

    def test_render_logged_against_its_work(self):
        from agentlink import heavy

        class Doc:
            Objects = []

        class Sess:
            doc = Doc()

        class T:
            name, changes = "view_render", False

        s = Sess()
        g = heavy.Gate(s)
        g.before(T(), {})
        self.assertIsNone(s.heavy_work)
        s.heavy_work = ("view_render:work", 50000)
        g.after(T(), {}, True)
        tm = self.keep.queue_state()["timings"]
        self.assertEqual(tm["view_render:work"][0][0], 50000.0)
        self.assertNotIn("view_render", tm)
        # The watchdog's deadline reads the work key too.
        from agentlink import supervise

        self.assertLess(supervise._deadline("view_render"), supervise.NO_ESTIMATE)

    def test_one_slow_run_is_a_range_not_the_estimate(self):
        q = {"timings": {"view_render:work": [[100000, 17.0], [100000, 15.0], [100000, 360.0]]}}
        lo, mid, hi = self.keep.estimate_range(q, "view_render:work", 100000)
        self.assertLess(mid, 20)
        self.assertGreater(hi, 300)


class Colours(unittest.TestCase):
    def test_no_two_layers_alike(self):
        from agentlink import render

        cs = [render.colour(i) for i in range(14)]
        for i in range(len(cs)):
            for j in range(i):
                self.assertFalse(render._close(cs[i], cs[j]), (i, j, cs[i], cs[j]))
        # A seventh part is not the first's orange.
        self.assertNotEqual(render.colour(6), render.colour(0))
        # An add-on layer that came in a part's colour gets another.
        layers = [{"name": "Stem", "color": render.colour(0)}, {"name": "Screw", "color": render.colour(1)},
                  {"name": "scan", "color": render.colour(0)}, {"name": "map", "colors": [1], "color": render.colour(0)}]
        render.distinct_colours(layers)
        self.assertFalse(render._close(layers[2]["color"], layers[0]["color"]))
        self.assertFalse(render._close(layers[2]["color"], layers[1]["color"]))
        self.assertEqual(layers[3]["color"], render.colour(0))  # a map keeps its own colours


# ---- 7. long reads as jobs ------------------------------------------------------------------

class Jobs(_Home):
    def setUp(self):
        super().setUp()
        from agentlink import jobs
        from agentlink.protocol import Server, Tool

        self.jobs = jobs
        self.old_wait = jobs.JOB_WAIT
        jobs.JOB_WAIT = 0.3
        self.gate = threading.Event()

        def slow(a):
            self.gate.wait(5)
            return {"thickness": 2.5, "_png": b"x"}

        def boom(a):
            self.gate.wait(5)
            raise ValueError("ray cast failed")

        class Doc:
            Name = "Shell"
            Objects = []

        class Sess:
            doc = Doc()

        self.session = Sess()
        obj = {"type": "object", "properties": {}, "additionalProperties": False}
        self.srv = Server("t", "0", [
            Tool("thickness_measure", "A long read.", obj, slow),
            Tool("bad_read", "A read that fails.", obj, boom),
            Tool("quick", "A quick read.", obj, lambda a: {"ok": True}),
            Tool("pad", "A change.", obj, lambda a: {"made": True}, changes=True),
            Tool("view_render", "A picture.", obj, lambda a: {"pic": True}),
            Tool("job_status", "Jobs.", {"type": "object", "properties": {"job": {"type": "string"}, "wait": {"type": "number"}}, "additionalProperties": False}, jobs.status),
        ])
        self.srv.session = self.session

    def tearDown(self):
        self.gate.set()
        self.jobs.JOB_WAIT = self.old_wait
        super().tearDown()

    def call(self, name, args=None):
        r = self.srv.call({"name": name, "arguments": args or {}})
        return r.get("isError", False), json.loads(r["content"][0]["text"])

    def test_background_read_answers_with_a_job_then_the_result(self):
        err, out = self.call("thickness_measure", {"background": True})
        self.assertFalse(err, out)
        self.assertEqual(out["status"], "running")
        jid = out["job"]
        self.assertIn("job_status", out["next"])
        # The queue carries it while it runs.
        self.assertEqual(self.keep.queue_state()["running"][0]["job"], jid)
        # A change to the document it reads waits.
        err, e = self.call("pad")
        self.assertTrue(err)
        self.assertIn(jid, e["error"]["message"])
        # Another read goes on.
        self.assertFalse(self.call("quick")[0])
        self.gate.set()
        err, st = self.call("job_status", {"job": jid, "wait": 5})
        self.assertFalse(err, st)
        self.assertEqual(st["status"], "done")
        self.assertEqual(st["result"], {"thickness": 2.5})
        self.assertEqual(self.keep.queue_state()["running"], [])
        self.assertFalse(self.call("pad")[0])

    def test_quick_job_answers_as_the_tool(self):
        self.gate.set()
        err, out = self.call("thickness_measure", {"background": True})
        self.assertFalse(err, out)
        self.assertEqual(out["thickness"], 2.5)

    def test_failed_job(self):
        err, out = self.call("bad_read", {"background": True})
        self.gate.set()
        err, st = self.call("job_status", {"job": out["job"], "wait": 5})
        self.assertEqual(st["status"], "failed")
        self.assertIn("ray cast failed", st["error"]["message"])

    def test_slow_before_is_not_prejudged(self):
        # No prejudging (18 Nov): a slow run before is logged data only; the
        # call runs and answers as ever.
        from agentlink import heavy

        q = self.keep.queue_state()
        self.keep.log_timing(q, "thickness_measure", heavy.size_of(self.session), 95.0)
        self.keep.save_queue(q)
        err, out = self.call("thickness_measure")
        self.assertNotEqual(out.get("status"), "running", out)

    def test_slow_read_is_logged(self):
        # A name of this test's own: note_slow leaves a HEAVY tool alone, and
        # an installed add-on may declare any real tool heavy (one did for
        # the name this test borrowed, in keep.HEAVY and heavy-tools.json).
        class T:
            name, changes = "slow_read_stand_in", False

            def changes_for(self, a):
                return False

        self.assertFalse(self.keep.is_heavy(T.name))
        self.jobs.note_slow(T(), {}, self.session, 95.0)
        self.assertTrue(self.jobs.past_slow(T.name, 1))

    def test_heavy_read_is_not_logged_as_slow(self):
        # What that add-on showed: a tool declared heavy is queued and timed
        # as heavy tools are, so its long read is not logged a second time.
        class T:
            name, changes = "heavy_read_stand_in", False

            def changes_for(self, a):
                return False

        self.keep.HEAVY.add(T.name)
        try:
            self.jobs.note_slow(T(), {}, self.session, 95.0)
            self.assertFalse(self.jobs.past_slow(T.name, 1))
        finally:
            self.keep.HEAVY.discard(T.name)

    def test_not_jobs(self):
        e = self.call("pad", {"background": True})[1]["error"]["message"]
        self.assertIn("cannot run as a job", e)
        self.assertIn("cannot run as a job", self.call("view_render", {"background": True})[1]["error"]["message"])
        self.assertIn("no such job", self.call("job_status", {"job": "job-nope"})[1]["error"]["message"])
        self.assertIn("jobs", self.call("job_status")[1])

    def test_key_error_is_a_sentence(self):
        from agentlink.protocol import failed_words

        w = failed_words("asm_joint", KeyError("M8x25-Screw219"))
        self.assertIn("'M8x25-Screw219'", w)
        self.assertIn("renamed or removed", w)


# ---- on stand-in FreeCAD modules, in a Python of their own ----------------------------------

STUBS = textwrap.dedent("""
    import sys, types, json
    sys.path.insert(0, ROOT)

    class Vec:
        def __init__(self, x=0, y=0, z=0):
            if isinstance(x, Vec):
                x, y, z = x.x, x.y, x.z
            self.x, self.y, self.z = float(x), float(y), float(z)
        def __add__(self, o): return Vec(self.x + o.x, self.y + o.y, self.z + o.z)
        def __sub__(self, o): return Vec(self.x - o.x, self.y - o.y, self.z - o.z)
        def __mul__(self, k): return Vec(self.x * k, self.y * k, self.z * k)
        def dot(self, o): return self.x * o.x + self.y * o.y + self.z * o.z
        @property
        def Length(self): return self.dot(self) ** 0.5

    class Plc:
        def __init__(self, base=None, rot=None):
            self.Base = Vec(base or Vec())
            self.Rotation = rot or types.SimpleNamespace(Axis=Vec(0, 0, 1), Angle=0.0)
        def copy(self): return Plc(self.Base, self.Rotation)
        def isSame(self, o, tol=0): return (self.Base - o.Base).Length <= tol

    fc = types.ModuleType("FreeCAD")
    fc.Vector, fc.Placement, fc.Rotation, fc.Matrix = Vec, Plc, (lambda *a: "rot"), object
    fc.GuiUp = False
    fc.Version = lambda: ["1", "1", "3"]
    fc.ParamGet = lambda p: types.SimpleNamespace(GetInt=lambda k, d=0: d, GetBool=lambda k, d=False: d, GetString=lambda k, d="": d, GetFloat=lambda k, d=0.0: d)
    fc.newDocument = lambda n: None
    fc.Console = types.SimpleNamespace(PrintWarning=lambda *a: None, PrintMessage=lambda *a: None, PrintError=lambda *a: None)
    sys.modules["FreeCAD"] = fc
    sys.modules["Part"] = types.ModuleType("Part")

    class BB:
        def __init__(self, c=(0, 0, 0)):
            self.Center = Vec(*c)
            self.XMin = self.YMin = self.ZMin = 0.0
            self.XMax = self.YMax = self.ZMax = 1.0
            self.XLength = self.YLength = self.ZLength = 1.0

    class Shell:
        def __init__(self, closed=True): self.c = closed
        def isClosed(self): return self.c

    class Shape:
        def __init__(self, solids=1, valid=True, check=None, closed=True, at=(0, 0, 0)):
            self.n, self.valid, self.err, self.c = solids, valid, check, closed
            self.BoundBox = BB(at)
            self.Volume, self.Area, self.ShapeType = 10.0 * max(solids, 1), 5.0, "Compound" if solids > 1 else "Solid"
            self.Faces, self.Edges = [], []
        @property
        def Solids(self):
            return [Shape(0 if self.n == 0 else 1, at=(i * 10, 0, 0)) for i in range(self.n)] if self.n != 1 else [self]
        @property
        def Shells(self): return [Shell(self.c)]
        def isNull(self): return False
        def isValid(self): return self.valid
        def check(self, bop):
            if self.err: raise ValueError(self.err)
        def hashCode(self): return id(self)

    class Obj:
        def __init__(self, name, type_="Part::Feature", shape=None, label=None):
            self.Name, self.Label, self.TypeId = name, label or name, type_
            self.Shape = shape if shape is not None else Shape()
            self.InList, self.Group, self.PropertiesList, self.links, self.Visibility = [], [], [], {}, True
            self.parent = None
        def getParentGeoFeatureGroup(self): return self.parent
        def getTypeIdOfProperty(self, p): return self.links[p][0]
        def getPropertyByName(self, p): return self.links[p][1]
        def link(self, prop, kind, target):
            self.PropertiesList.append(prop)
            self.links[prop] = (kind, target)
            target.InList.append(self)

    class Doc:
        def __init__(self, objs=()):
            self.Objects, self.Name, self.Label = list(objs), "Stem", "Stem"
            self.UndoCount = 0
        def recompute(self): pass
        def removeObject(self, n):
            self.Objects = [o for o in self.Objects if o.Name != n]
""")


def run_stub(body):
    code = STUBS.replace("ROOT", repr(ROOT)) + textwrap.dedent(body)
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise AssertionError(p.stderr[-3000:])
    return json.loads(p.stdout.strip().splitlines()[-1])


class OnStandIns(unittest.TestCase):
    def test_2_3_compound_body_is_a_part_and_listed(self):
        out = run_stub("""
            from agentlink.tools import Session
            body = Obj("Body", "PartDesign::Body", Shape(2), "Stem")
            body.AllowCompound = True
            pad = Obj("Pad", "PartDesign::Pad", Shape(1))
            pad.parent = body
            body.Group = [pad]
            pad.link("_Body", "App::PropertyLinkHidden", body)   # FreeCAD 1.x's feature-to-body link
            pad2 = Obj("Pad001", "PartDesign::Pad", Shape(2))
            pad2.parent = body
            body.Group.append(pad2)
            pad2.link("BaseFeature", "App::PropertyLink", pad)
            screw = Obj("Screw", "Part::FeaturePython", Shape(1), "M8x25-Screw219")
            screw.link("BaseObject", "App::PropertyLinkSub", body)
            doc = Doc([body, pad, pad2, screw])
            s = Session.__new__(Session)
            s.doc, s.meta = doc, {}
            names = [o.Label for o in s.bodies()]
            rows = [s._body_row(o) for o in s.bodies()]
            print(json.dumps({"names": names, "rows": rows}))
        """)
        self.assertEqual(out["names"], ["Stem", "M8x25-Screw219"])
        stem = out["rows"][0]
        self.assertEqual(stem["solids"], 2)
        self.assertIn("AllowCompound", stem["multiSolid"])
        self.assertEqual(stem["object"], "Body")
        self.assertEqual(out["rows"][1]["object"], "Screw")

    def test_4_body_check_compound_and_soft_bop(self):
        out = run_stub("""
            from agentlink.tools import Session
            body = Obj("Body", "PartDesign::Body", Shape(2, check="Checking ...\\nEdge12: BOPAlgo_InvalidCurveOnSurface"), "Stem")
            body.AllowCompound = True
            loose = Obj("Loose", "Part::Feature", Shape(2))
            broken = Obj("Broken", "Part::Feature", Shape(1, valid=False, check="Edge3: BOPAlgo_InvalidCurveOnSurface"))
            selfx = Obj("Selfx", "Part::Feature", Shape(1, check="BOPAlgo_SelfIntersect"))
            s = Session.__new__(Session)
            s.doc, s.meta = Doc([body, loose, broken, selfx]), {}
            out = {o.Label: s.body_check({"body": o.Label}) for o in (body, loose, broken, selfx)}
            print(json.dumps(out, default=str))
        """)
        st = out["Stem"]
        self.assertTrue(st["ok"], st)
        self.assertEqual(len(st["each"]), 2)
        self.assertIn("intended", st)
        self.assertTrue(st["checkGeometry"]["warning"])
        self.assertTrue(any("InvalidCurveOnSurface" in w for w in st["warnings"]), st["warnings"])
        # AllowCompound is on by default: not "on purpose" (QA 1126e).
        self.assertIn("2 separate solids", st["intended"])
        self.assertNotIn("on purpose", st["intended"])
        self.assertIn("2 separate solids, not one part.", st["warnings"])
        self.assertFalse(out["Loose"]["ok"])           # two solids not meant
        self.assertFalse(out["Broken"]["ok"])          # not valid by BRepCheck: still a problem
        self.assertFalse(out["Selfx"]["ok"])           # a self-intersection is never soft

    def test_6_take_back_removes_what_undo_left(self):
        out = run_stub("""
            from agentlink.tools import undo_mark, take_back
            a = Obj("Box")
            doc = Doc([a])
            u0, names0 = undo_mark(doc)
            sk = Obj("CavitySketch", "Sketcher::SketchObject")
            pocket = Obj("Pocket", "PartDesign::Pocket")
            pocket.link("Profile", "App::PropertyLink", sk)
            doc.Objects += [sk, pocket]
            gone = take_back(doc, None, names0)
            print(json.dumps({"gone": gone, "left": [o.Name for o in doc.Objects]}))
        """)
        self.assertEqual(out["left"], ["Box"])
        self.assertEqual(out["gone"], ["Pocket", "CavitySketch"])

    def test_extra_asm_joint_while_a_workbench_relabels(self):
        out = run_stub("""
            sys.modules["JointObject"] = types.SimpleNamespace(JointTypes=["Fixed", "Revolute"], Joint=lambda j, i: None)
            sys.modules["UtilsAssembly"] = types.ModuleType("UtilsAssembly")
            from agentlink.families import assembly as A

            stem = Obj("Body", "PartDesign::Body", label="Stem")
            stem.Placement = Plc()
            screw = Obj("Screw", "Part::FeaturePython", label="M8x25-Screw219")
            screw.Placement = Plc()
            counter = [219]

            class D(Doc):
                def recompute(self):
                    # Fasteners counts its screws' labels up on every recompute.
                    counter[0] += 3
                    screw.Label = f"M8x25-Screw{counter[0]}"
                    screw.Placement = Plc(Vec(0, 0, 5))

            doc = D([stem, screw])

            class J:
                Label = "Fixed"
                Proxy = types.SimpleNamespace(setJointConnectors=lambda j, r: None, updateJCSPlacements=lambda j: None)

            asm = Obj("Assembly", "Assembly::AssemblyObject")
            A._assembly = lambda d, r: asm
            A._grounded = lambda a: [stem]
            A._parts = lambda a: [stem, screw]
            A._joints = lambda a: types.SimpleNamespace(newObject=lambda t, n: J())
            A._element = lambda s, p, q, w: "Edge1"
            A._status = lambda a: (0, "solved")
            A._overlaps = lambda parts, clearance=0.0, *more, **kw: ([], [])
            sess = types.SimpleNamespace(doc=doc)
            fn = next(t.fn for t in A.tools(sess) if t.name == "asm_joint")
            r = fn({"kind": "fixed", "a": {"part": "Stem", "element": "Edge1"}, "b": {"part": "M8x25-Screw", "element": "Edge1"}})
            refused = None
            try:
                A._part(types.SimpleNamespace(Group=[]), "x")
            except Exception as e:
                refused = str(e)
            print(json.dumps({"moved": list(r["moved"]), "b": r["b"]}))
        """)
        self.assertEqual(out["moved"], ["M8x25-Screw222"])
        self.assertTrue(out["b"].startswith("M8x25-Screw222"))

    def test_1_render_work(self):
        out = run_stub("""
            from agentlink.families import view
            L = [{"F": [0] * 1000}, {"F": [0] * 500}]
            print(json.dumps({"one": view.render_work(L, ["iso"], 800, 600), "four": view.render_work(L, ["iso", "top", "front", "right"], 800, 600),
                              "key": view.RENDER_KEY}))
        """)
        self.assertEqual(out["one"], 1500 + 800 * 600 // 50)
        self.assertEqual(out["four"], 4 * out["one"])
        self.assertEqual(out["key"], "view_render:work")

    def test_5_face_bound_to_its_owner(self):
        out = run_stub("""
            sys.modules["Sketcher"] = types.ModuleType("Sketcher")
            from agentlink.families import pd_common as pc

            class Face:
                def __init__(self, area, at, edges=4):
                    self.Area, self.CenterOfMass, self.Edges = area, Vec(*at), [0] * edges

            class F(Obj):
                def __init__(self, name, faces):
                    super().__init__(name, "PartDesign::Pad")
                    self.faces = faces
                def isDerivedFrom(self, t): return t == "PartDesign::Feature"

            # The top face: made by Pad, kept by the pocket; the pocket's
            # floor is its own.
            top = Face(400, (0, 0, 10))
            pad = F("Pad", [top])
            pocket = F("Pocket", [Face(400, (0, 0, 10)), Face(50, (0, 0, 6))])
            sk = Obj("Sketch", "Sketcher::SketchObject")
            sk.isDerivedFrom = lambda t: False
            body = Obj("Body", "PartDesign::Body")
            body.Group, body.Tip = [pad, sk, pocket], pocket

            def find_face(shape, q, tol=0.5, body=None, names=()):  # body, names: 22 Nov face selectors
                for i, f in enumerate(shape.faces):
                    if (f.CenterOfMass - Vec(*q["at"])).Length < tol:
                        return i, f
                raise pc.ToolError("not_found", "no face")

            pc.find_face = find_face
            pc.tip_shape = lambda b, need=True: (b.Tip, b.Tip)
            for o in (pad, pocket):
                o.Shape = o
                o.Shape.Solids, o.Shape.isNull = [1], (lambda: False)
            a = pc.plane_ref(body, {"at": [0, 0, 10], "normal": [0, 0, 1]})
            b = pc.plane_ref(body, {"at": [0, 0, 6], "normal": [0, 0, 1]})
            c = pc.plane_ref(body, {"at": [0, 0, 10], "normal": [0, 0, 1], "feature": "Pocket"})
            print(json.dumps({"a": [a[0][0].Name, a[0][1]], "b": [b[0][0].Name, b[0][1]], "c": c[0][0].Name, "said": a[1]}))
        """)
        self.assertEqual(out["a"], ["Pad", ["Face1"]])
        self.assertEqual(out["b"], ["Pocket", ["Face2"]])
        self.assertEqual(out["c"], "Pocket")
        self.assertIn("Pad's", out["said"])

    def test_8_transforms_take_all(self):
        out = run_stub("""
            sys.modules["Sketcher"] = types.ModuleType("Sketcher")
            from agentlink.families import feature as F
            pc = F.pc

            class Feat(Obj):
                def __init__(self, name, kind, mode=None):
                    super().__init__(name, kind)
                    self.mode = mode
                    if mode:
                        self.PropertiesList.append("TransformMode")
                def isDerivedFrom(self, t):
                    if t == "PartDesign::Feature":
                        return True
                    return t == "PartDesign::FeatureAddSub" and self.TypeId in ("PartDesign::Pad", "PartDesign::Pocket")
                def getEnumerationsOfProperty(self, p): return self.mode

            def run(mode):
                pad, pocket = Feat("Pad", "PartDesign::Pad"), Feat("Pocket", "PartDesign::Pocket")
                fillet = Feat("Fillet", "PartDesign::Fillet")
                body = Obj("Body", "PartDesign::Body")
                body.Group, body.Tip = [pad, pocket, fillet], fillet
                def new_obj(kind, name):
                    f = Feat(name, kind, mode)
                    body.Group.append(f)
                    return f
                body.newObject = new_obj
                pc.pd_body = lambda d, r: body
                pc.tip_shape = lambda b, need=True: (b.Tip, b.Tip.Shape)
                pc.volume = lambda b: 1.0
                pc.settle = lambda s, b, f, tool, before, change, hint=None: {"tool": tool, "tip": b.Tip.Name}
                pc.plane_ref = lambda b, r, w="plane": ((None, [""]), "YZ")
                sess = types.SimpleNamespace(doc=Doc([]), unique=lambda l, own=None: l)
                fn = next(t.fn for t in F.tools(sess) if t.name == "pd_mirrored")
                out = fn({"features": "all"})
                f = body.Group[-1]
                return {"out": out, "originals": [o.Name for o in getattr(f, "Originals", [])], "mode": getattr(f, "TransformMode", None)}

            print(json.dumps({"old": run(None), "new": run(["Transform tool shapes", "Transform body"])}))
        """)
        self.assertEqual(out["old"]["originals"], ["Pad", "Pocket"])
        self.assertIn("fillets", out["old"]["out"]["repeated"])
        self.assertEqual(out["old"]["out"]["tip"], "Mirrored")
        self.assertEqual(out["new"]["mode"], "Transform body")
        self.assertEqual(out["new"]["originals"], [])

    def test_extra_concave_fillet_adds_material(self):
        out = run_stub("""
            sys.modules["Sketcher"] = types.ModuleType("Sketcher")
            from agentlink.families import pd_common as pc
            vol = [100.0]
            pc.broken = lambda d: []
            pc.body_reading = lambda b: {"volume": vol[0]}
            pc.picks.finish = lambda s, tool, out, recompute=False: out
            sess = types.SimpleNamespace(doc=Doc([]))
            fil = Obj("Fillet", "PartDesign::Fillet")
            res = {}
            vol[0] = 104.0   # an inside corner: material added
            res["concave"] = pc.settle(sess, None, fil, "pd_fillet", 100.0, "changed")["volumeChange"]
            vol[0] = 97.0    # an outside corner: taken away
            res["convex"] = pc.settle(sess, None, fil, "pd_fillet", 100.0, "changed")["volumeChange"]
            vol[0] = 100.0
            try:
                pc.settle(sess, None, fil, "pd_fillet", 100.0, "changed")
            except Exception as e:
                res["same"] = str(e)
            th = Obj("Thickness", "PartDesign::Thickness")
            try:
                pc.settle(sess, None, th, "pd_thickness", 100.0, "cut")
            except Exception as e:
                res["shell"] = str(e)
            print(json.dumps(res))
        """)
        self.assertEqual(out["concave"], 4.0)
        self.assertEqual(out["convex"], -3.0)
        self.assertIn("as it was", out["same"])
        self.assertNotIn("profile", out["same"])
        self.assertNotIn("profile", out["shell"])
        # The two tools ask for "changed" (either sign), not "cut": they are data now (agentlink/data/tools.json).
        from agentlink import runners
        for name in ("pd_fillet", "pd_chamfer"):
            self.assertEqual(runners.entries()[name]["answer"]["with"][4], "changed", name)

    def test_extra_polyline_holds_its_axis_sides(self):
        out = run_stub("""
            sys.modules["Sketcher"] = types.ModuleType("Sketcher")
            sys.modules["Part"].LineSegment = lambda a, b: ("line", a, b)
            from agentlink.families import sketch as S
            S._line = lambda a, b: ("line", a, b)
            G, C, D = S.build({"kind": "polyline", "closed": True, "points": [[0, 0], [40, 0], [40, 5], [5, 5], [5, 30], [0, 30]]})
            G2, C2, _ = S.build({"kind": "polyline", "points": [[0, 0], [10, 3], [10, 8]]})
            print(json.dumps({"c": [list(c) for c in C if c[0] != "Coincident"], "c2": [list(c) for c in C2 if c[0] != "Coincident"]}))
        """)
        self.assertEqual(out["c"], [["Horizontal", 0], ["Vertical", 1], ["Horizontal", 2], ["Vertical", 3], ["Horizontal", 4], ["Vertical", 5]])
        self.assertEqual(out["c2"], [["Vertical", 1]])

if __name__ == "__main__":
    unittest.main()
