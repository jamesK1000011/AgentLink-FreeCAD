# SPDX-License-Identifier: LGPL-2.1-or-later
# The fast path (efficiency design C6, A6) and targeted reads (22 Nov),
# agentlink/fastpath.py: one call runs a block of steps in the hub's step
# language, each call through the server's normal path, with one short answer;
# a block that is refused is taken back whole (batch's rollback, which stops at
# the person's undo step); a dry run checks every step first; get reads one
# value with its unit; the preference FastPath (and AGENTLINK_FASTPATH=off)
# turns both off.
#
# The real server (agentlink/tools.py build_server) runs on a stand-in FreeCAD
# (every module a mock) in a child process, so no other test sees it. The tools
# a block calls keep their own schemas; their work is a stand-in that makes
# objects in a stand-in document with an undo stack.
import json
import os
import subprocess
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def _child(case):
    import tempfile
    from unittest import mock

    class Auto(types.ModuleType):
        def __getattr__(self, k):
            if k.startswith("__"):
                raise AttributeError(k)
            m = mock.MagicMock(name=f"{self.__name__}.{k}")
            setattr(self, k, m)
            return m

    for n in ("FreeCAD", "FreeCADGui", "Part", "Mesh", "MeshPart", "Sketcher", "Import", "TechDraw", "Draft", "Spreadsheet", "PySide", "PySide.QtCore", "PySide.QtGui"):
        sys.modules[n] = Auto(n)
    fc = sys.modules["FreeCAD"]
    fc.GuiUp = False
    prefs = {"FastPath": case != "pref_off"}
    fc.ParamGet = lambda p: types.SimpleNamespace(GetInt=lambda k, d=0: d, GetBool=lambda k, d=False: prefs.get(k, d), GetString=lambda k, d="": d,
                                                  GetFloat=lambda k, d=0.0: d)
    os.environ["AGENTLINK_HOME"] = tempfile.mkdtemp(prefix="agentlink-fast-")
    if case == "env_off":
        os.environ["AGENTLINK_FASTPATH"] = "off"

    from agentlink import runners
    from agentlink.protocol import Tool, ToolError
    from agentlink.tools import Session, build_server

    class Obj:
        def __init__(self, name, type_id, parent=None):
            self.Name = self.Label = name
            self.TypeId = type_id
            self.parent = parent
            self.PropertiesList = ["Length"] if type_id == "PartDesign::Pad" else []
            self.InList = []

        def getParentGeoFeatureGroup(self):
            return self.parent

    class Doc:
        Name = Label = "FastDoc"
        FileName = ""

        def __init__(self):
            self.Objects, self.UndoNames, self.steps, self.open, self.undone = [], [], [], None, 0

        @property
        def UndoCount(self):
            return len(self.steps)

        def add(self, name, type_id, parent=None):
            base, n = name, 1
            while self.getObject(name) is not None:
                n += 1
                name = f"{base}{n:03d}"
            o = Obj(name, type_id, parent)
            self.Objects.append(o)
            if self.open is not None:
                self.open["made"].append(o)
            return o

        def getObject(self, name):
            return next((o for o in self.Objects if o.Name == name), None)

        def getObjectsByLabel(self, label):
            return [o for o in self.Objects if o.Label == label]

        def removeObject(self, name):
            self.Objects = [o for o in self.Objects if o.Name != name]

        def openTransaction(self, name=""):
            self.open = {"name": name, "made": []}

        def commitTransaction(self):
            if self.open is not None and self.open["made"]:
                self.steps.insert(0, self.open)
                self.UndoNames.insert(0, self.open["name"])
            self.open = None

        def abortTransaction(self):
            if self.open is not None:
                for o in self.open["made"]:
                    self.removeObject(o.Name)
            self.open = None

        def person_step(self, name):
            self.steps.insert(0, {"name": name, "made": []})
            self.UndoNames.insert(0, name)

        def undo(self):
            if self.steps:
                st = self.steps.pop(0)
                self.UndoNames.pop(0)
                for o in st["made"]:
                    self.removeObject(o.Name)
                self.undone += 1

        def recompute(self):
            pass

        def isTouched(self):
            return False

    s = Session(out_dir=tempfile.mkdtemp())
    doc = Doc()
    s.doc = doc
    doc.add("Body", "PartDesign::Body")  # sketch_new's own leading check wants a body (read before step 1)
    srv = build_server(s, lean=False)
    srv._oriented = True  # the first answer's whereYouAre has its own tests (test_orient_1122.py)
    s.server = srv
    seen = []   # (tool, arguments) of every call the server ran
    real_call = srv.call

    def call(params):
        seen.append((params.get("name"), json.loads(json.dumps(params.get("arguments") or {}))))
        return real_call(params)

    srv.call = call

    def body_of(a):
        b = a.get("body")
        o = doc.getObject(b) if b else None
        if o is None:
            o = next((x for x in doc.Objects if x.TypeId == "PartDesign::Body"), None) or doc.add("Body", "PartDesign::Body")
            doc.add("Origin", "App::Origin", o)
        return o

    def sketch_new(a):
        b = body_of(a)
        sk = doc.add(a.get("name") or "Sketch", "Sketcher::SketchObject", b)
        return {"sketch": sk.Label, "body": b.Label, "plane": a.get("plane")}

    def sketch_add(a):
        sk = doc.getObject(a.get("sketch") or "") if a.get("sketch") else None
        if sk is None:
            found = [o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject"]
            if len(found) != 1:
                raise ToolError("invalid_input", "sketch: there are several sketches, name one.")
            sk = found[0]
        doc.add("Geo", "Part::GeomCircle", sk)  # a step of its own, as a real sketch edit is
        return {"sketch": sk.Label, "added": len(a.get("items") or []), "health": {"ok": True, "verdict": "nothing red"}}

    def pd_pad(a):
        sk = doc.getObject(a.get("sketch") or "") if a.get("sketch") else None
        if sk is None:
            raise ToolError("invalid_input", "sketch: which one? (the stand-in wants it named)")
        pad = doc.add("Pad", "PartDesign::Pad", sk.parent)
        return {"pad": pad.Label, "length": a.get("length"), "health": {"ok": True, "verdict": "nothing red"}}

    srv.tools["sketch_new"].fn = sketch_new
    srv.tools["sketch_add"].fn = sketch_add
    srv.tools["pd_pad"].fn = pd_pad

    num = {"type": "object", "properties": {"n": {}, "sketch": {"type": "string"}}}

    def probe_change(a):
        doc.add(f"P{a.get('n')}", "Part::Feature")
        return {"n": a.get("n")}

    def probe_fail(a):
        raise ToolError("invalid_state", "probe_fail: told to refuse")

    def probe_person(a):
        doc.person_step("Person edit")  # the person's own step, made while the block ran
        return {"read": True}

    def probe_req(a):
        return {"sketch": a.get("sketch")}

    srv.add(Tool("probe_change", "A change for the fast tests.", num, probe_change, changes=True))
    srv.add(Tool("probe_fail", "A refusal for the fast tests.", num, probe_fail, changes=True))
    srv.add(Tool("probe_person", "A read during which the person makes a step.", num, probe_person))
    srv.add(Tool("probe_req", "A read that needs a sketch.", {"type": "object", "properties": {"sketch": {"type": "string"}}, "required": ["sketch"],
                                                               "additionalProperties": False}, probe_req))
    # A data tool whose leading check refuses when n is 0 (read by agentlink/needs.py before step 1).
    lead = {"runner": "steps", "group": "core", "description": "A leading check for the fast tests.", "changes": True,
            "inputSchema": {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"], "additionalProperties": False},
            "steps": [{"refuse": "probe_lead: n is 0, so there is nothing to make.", "code": "invalid_state", "when": "=a.n == 0"},
                      {"do": "=made(a.n)"}],
            "answer": {"fields": {"n": "=a.n"}}}
    lead_t = runners.tool("probe_lead", lead, {"made": lambda n: doc.add(f"L{n}", "Part::Feature")})
    srv.add(lead_t)

    # The readers get goes through, as stand-ins with their answers' shapes.
    srv.tools["object_get"].fn = lambda a: {"name": a["object"], "properties": {"Length": {"value": 4.0, "type": "Length"}}} if "Length" in a.get("filter", []) else {"properties": {}}
    srv.tools["measure"].fn = lambda a: ({"a": {"ref": a["a"], "type": "line", "length": 12.5, "mid": [1, 2, 3]}} if "Edge" in str(a["a"])
                                         else {"a": {"body": a["a"], "volume": 1520.0, "area": 912.4, "size": [10, 20, 4]}})
    srv.tools["measure_mass"].fn = lambda a: {"body": a.get("body"), "mass": 1.886, "density": 1.24, "volume": 1520.0}
    srv.tools["sketch_state"].fn = lambda a: {"sketch": a.get("sketch"), "dof": 2, "closedWires": 3}

    def fast(args):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "fast", "arguments": args}})["result"]
        return {"isError": bool(r.get("isError")), "body": json.loads(r["content"][0]["text"]), "chars": len(r["content"][0]["text"])}

    def one(name, args):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
        return {"isError": bool(r.get("isError")), "body": json.loads(r["content"][0]["text"]), "chars": len(r["content"][0]["text"])}

    def labels():
        return [o.Label for o in doc.Objects]

    design = {"do": [
        {"let": {"xs": [10, 30, 50]}},
        {"call": "sketch_new", "plane": "XY"},
        {"each": "x", "in": "=xs", "steps": [{"call": "sketch_add", "items": [{"circle": {"at": ["=x", 0], "radius": 3}}]}]},
        {"call": "pd_pad", "length": 4}]}
    out = {}
    if case == "design":
        out["got"] = fast(design)
        out["seen"] = seen
        out["labels"] = labels()
        rec = out["got"]["body"].get("record")
        out["record"] = json.load(open(os.path.join(s.out_dir, rec))) if rec else None
    elif case == "single":
        # The same work as single calls: what the answers cost.
        n = 0
        n += one("sketch_new", {"plane": "XY"})["chars"]
        for x in (10, 30, 50):
            n += one("sketch_add", {"sketch": "Sketch", "items": [{"circle": {"at": [x, 0], "radius": 3}}]})["chars"]
        n += one("pd_pad", {"sketch": "Sketch", "length": 4})["chars"]
        out["chars"] = n
        out["fastChars"] = None
    elif case == "flow":
        out["got"] = fast({"do": [
            {"let": {"k": 2, "names": []}},
            {"when": "=k > 1", "then": [{"call": "probe_change", "n": "=k * 10", "as": "r"}], "else": [{"call": "probe_fail"}]},
            {"push": {"names": "=r.n"}},
            {"choose": "=str(k)", "of": {"2": [{"call": "probe_change", "n": 22}]}, "else": [{"call": "probe_fail"}]},
            {"call": "probe_change", "n": 99, "when": "=k == 3"},
            {"try": [{"call": "probe_fail"}], "on": "refusal", "except": [{"get": "=error.code", "as": "caught"}]},
            {"get": "=names", "as": "names"}]})
        out["labels"] = labels()
        out["seen"] = [t for t, _a in seen]
    elif case == "required":
        out["first"] = fast({"do": [{"call": "sketch_new", "plane": "XY"}]})
        out["got"] = fast({"do": [{"call": "probe_req", "as": "r"}, {"get": "=r.sketch", "as": "sk"}]})
        out["seen"] = seen
    elif case == "rollback":
        out["got"] = fast({"do": [{"call": "probe_change", "n": 1}, {"call": "probe_change", "n": 2}, {"call": "probe_fail"}, {"call": "probe_change", "n": 3}]})
        out["labels"] = labels()
        out["undone"] = doc.undone
        out["seen"] = [t for t, _a in seen]
    elif case == "person":
        out["got"] = fast({"do": [{"call": "probe_change", "n": 1}, {"call": "probe_person"}, {"call": "probe_change", "n": 2}, {"call": "probe_fail"}]})
        out["labels"] = labels()
        out["undoNames"] = list(doc.UndoNames)
    elif case == "dry":
        out["bad"] = fast({"check": True, "do": [{"let": {"xs": [1, 2]}}, {"each": "x", "in": "=xs", "steps": [{"call": "sketch_add", "items": [], "bogus": 1}]}]})
        out["good"] = fast({"check": True, **design})
        out["seen"] = seen
        out["labels"] = labels()
    elif case == "a6":
        out["fast"] = fast({"do": [{"call": "probe_change", "n": 1, "when": "=False"}, {"call": "probe_person", "as": "p"}, {"call": "probe_lead", "n": 0}]})
        out["seenFast"] = [t for t, _a in seen]
        out["late"] = fast({"do": [{"call": "probe_change", "n": 1}, {"call": "probe_lead", "n": 0}]})
        out["labelsAfterLate"] = labels()
        del seen[:]
        out["batch"] = one("batch", {"check": True, "calls": [{"tool": "probe_person", "arguments": {}}, {"tool": "probe_lead", "arguments": {"n": 0}}]})
        out["seenBatch"] = [t for t, _a in seen]
        out["batchPlain"] = one("batch", {"calls": [{"tool": "probe_person", "arguments": {}}, {"tool": "probe_lead", "arguments": {"n": 0}}]})
        out["batchOk"] = one("batch", {"check": True, "calls": [{"tool": "probe_lead", "arguments": {"n": 1}}]})
    elif case == "get":
        fast({"do": [{"call": "sketch_new", "plane": "XY"}, {"call": "pd_pad", "length": 4}]})
        out["one"] = one("get", {"what": ["Pad.Length", "Body.volume", "Body.Edge7.length", "sketch.dof", "active.body", "active.sketch",
                                          "Body.mass", "bodies", "selection", "Sketch.closedWires"]})
        out["missing"] = one("get", {"what": "Nope.Length"})
        out["listMiss"] = one("get", {"what": ["Pad.Length", "Nope.Length"]})
        out["badform"] = one("get", {"what": "Pad"})
        out["noprop"] = one("get", {"what": "Pad.Width"})
        out["inBlock"] = fast({"do": [{"get": "Body.volume", "as": "v"}, {"get": "=v * 2", "as": "twice"}, {"get": "Pad.Length"}]})
    elif case in ("env_off", "pref_off"):
        out["fast"] = fast(design)
        out["get"] = one("get", {"what": "active.body"})
        out["labels"] = labels()
    elif case == "safety":
        out["maker"] = fast({"do": [{"let": {"f": "=maker('os.system')"}}]})
        out["fmt"] = fast({"do": [{"let": {"f": "='{0.__class__}'.format(1)"}}]})
        out["make"] = fast({"do": [{"make": "Part.show"}]})
        out["batch"] = fast({"do": [{"call": "batch", "calls": []}]})
        out["private"] = fast({"do": [{"let": {"f": "=a.__class__"}}]})
        out["unknown"] = fast({"do": [{"call": "no_such_tool"}]})
        out["labels"] = labels()
    print(json.dumps(out, default=str))


_cache = {}


def run_case(case):
    if case not in _cache:
        env = {k: v for k, v in os.environ.items() if k != "AGENTLINK_FASTPATH"}
        r = subprocess.run([sys.executable, os.path.abspath(__file__), "child", case], capture_output=True, text=True, timeout=180, cwd=ROOT, env=env)
        if r.returncode != 0:
            raise AssertionError(f"child {case} failed:\n{r.stderr[-4000:]}")
        _cache[case] = json.loads(r.stdout.strip().splitlines()[-1])
    return _cache[case]


class FastPath(unittest.TestCase):
    def test_design_block_runs_each_call_through_the_server(self):
        got = run_case("design")
        self.assertFalse(got["got"]["isError"], got["got"])
        body = got["got"]["body"]
        # One short line, with the real names of what was made.
        self.assertTrue(body["fast"].startswith("ok 5 calls "), body)
        self.assertIn("+Sketch", body["fast"])
        self.assertIn("+Pad", body["fast"])
        self.assertTrue(body["fast"].endswith("clean"), body)
        self.assertLessEqual(set(body), {"fast", "values", "warnings", "filled", "checkpoint", "record", "ms"})
        # Every call went through the server's own path, in order, with the sketch filled in from the block.
        tools = [t for t, _a in got["seen"]]
        self.assertEqual(tools, ["fast", "sketch_new", "sketch_add", "sketch_add", "sketch_add", "pd_pad"])
        self.assertEqual([a.get("sketch") for t, a in got["seen"] if t in ("sketch_add", "pd_pad")], ["Sketch"] * 4)
        self.assertEqual([a["items"][0]["circle"]["at"][0] for t, a in got["seen"] if t == "sketch_add"], [10, 30, 50])
        self.assertIn("pd_pad.sketch=Sketch", body["filled"])
        # The record holds each call's whole answer, by its step.
        rec = got["record"]
        self.assertTrue(rec["fast"])
        self.assertEqual([r["step"] for r in rec["results"]], ["do.1", "do.2.steps.0", "do.2.steps.0", "do.2.steps.0", "do.3"])
        self.assertEqual(rec["results"][-1]["result"]["pad"], "Pad")

    def test_terse_answer_is_shorter_than_single_calls(self):
        fast = run_case("design")["got"]["chars"]
        single = run_case("single")["chars"]
        self.assertLess(fast, single, (fast, single))

    def test_let_when_choose_try_push_with_calls(self):
        got = run_case("flow")
        self.assertFalse(got["got"]["isError"], got["got"])
        body = got["got"]["body"]
        self.assertEqual(body["values"]["names"], [20])
        self.assertEqual(body["values"]["caught"], "invalid_state")
        self.assertEqual(got["seen"], ["fast", "probe_change", "probe_change", "probe_fail"])
        self.assertIn("P20", got["labels"])
        self.assertIn("P22", got["labels"])
        self.assertNotIn("P99", got["labels"])
        self.assertTrue(any("(caught)" in w for w in body.get("warnings", [])), body)

    def test_required_field_fills_from_the_session(self):
        got = run_case("required")
        self.assertFalse(got["got"]["isError"], got["got"])
        self.assertEqual(got["got"]["body"]["values"]["sk"], "Sketch")
        self.assertIn("probe_req.sketch=Sketch", got["got"]["body"]["filled"])
        self.assertEqual([a for t, a in got["seen"] if t == "probe_req"], [{"sketch": "Sketch"}])

    def test_refused_call_rolls_the_block_back(self):
        got = run_case("rollback")
        self.assertTrue(got["got"]["isError"])
        err = got["got"]["body"]["error"]
        self.assertEqual(err["code"], "invalid_state")
        self.assertEqual(err["outcome"], "rolled_back")
        self.assertIn("step do.2 (probe_fail)", err["message"])
        self.assertIn("2 undo steps", err["message"])
        self.assertEqual(got["undone"], 2)
        self.assertNotIn("P1", got["labels"])
        self.assertNotIn("P3", got["labels"])
        self.assertEqual(got["seen"], ["fast", "probe_change", "probe_change", "probe_fail"])

    def test_rollback_stops_at_the_persons_step(self):
        got = run_case("person")
        self.assertTrue(got["got"]["isError"])
        err = got["got"]["body"]["error"]
        self.assertEqual(err["outcome"], "partial")
        self.assertIn("not the agent's (Person edit)", err["message"])
        self.assertIn("P1", got["labels"])
        self.assertNotIn("P2", got["labels"])
        self.assertEqual(got["undoNames"][0], "Person edit")

    def test_dry_run_refuses_with_the_step_number_and_runs_nothing(self):
        got = run_case("dry")
        self.assertTrue(got["bad"]["isError"])
        msg = got["bad"]["body"]["error"]["message"]
        self.assertIn("step do.1.steps.0 (sketch_add)", msg)
        self.assertIn("bogus", msg)
        self.assertIn("Nothing was run", msg)
        self.assertEqual(got["bad"]["body"]["error"]["outcome"], "not_started")
        self.assertFalse(got["good"]["isError"], got["good"])
        self.assertTrue(got["good"]["body"]["fast"].startswith("check ok: 5 calls"), got["good"])
        self.assertEqual([t for t, _a in got["seen"]], ["fast", "fast"])
        self.assertEqual(got["labels"], ["Body"])

    def test_a6_leading_checks_before_step_1(self):
        got = run_case("a6")
        # Fast: the leading check of step 2 refuses before step 1; nothing ran.
        self.assertTrue(got["fast"]["isError"])
        self.assertIn("step do.2 (probe_lead): probe_lead: n is 0", got["fast"]["body"]["error"]["message"])
        self.assertEqual(got["fast"]["body"]["error"]["code"], "invalid_state")
        self.assertEqual(got["seenFast"], ["fast"])
        # After a change the document is not known before the run: the step runs, is refused, and the block is taken back.
        self.assertTrue(got["late"]["isError"])
        self.assertEqual(got["late"]["body"]["error"]["outcome"], "rolled_back")
        self.assertNotIn("P1", got["labelsAfterLate"])
        # batch { check: true }: refused with the call's index, nothing run; without check it runs as before.
        self.assertTrue(got["batch"]["isError"])
        self.assertIn("calls.1 (probe_lead)", got["batch"]["body"]["error"]["message"])
        self.assertEqual(got["seenBatch"], ["batch"])
        self.assertFalse(got["batchPlain"]["isError"])
        self.assertEqual(got["batchPlain"]["body"].get("stopped"), 1)
        self.assertFalse(got["batchOk"]["isError"], got["batchOk"])

    def test_get_each_kind(self):
        got = run_case("get")
        self.assertFalse(got["one"]["isError"], got["one"])
        v = got["one"]["body"]
        self.assertEqual(v["Pad.Length"], "4 mm")
        self.assertEqual(v["Body.volume"], "1520 mm³")
        self.assertEqual(v["Body.Edge7.length"], "12.5 mm")
        self.assertEqual(v["sketch.dof"], 2)
        self.assertEqual(v["active.body"], "Body")
        self.assertEqual(v["active.sketch"], "Sketch")
        self.assertEqual(v["Body.mass"], "1.886 g")
        self.assertEqual(v["selection"], [])
        self.assertEqual(v["Sketch.closedWires"], 3)
        self.assertEqual(got["missing"]["body"]["error"]["code"], "not_found")
        # Live, 22 Nov: one value that cannot be read no longer loses the others.
        lm = got["listMiss"]
        self.assertFalse(lm["isError"], lm)
        self.assertEqual(lm["body"]["Pad.Length"], "4 mm")
        self.assertIn("Nope.Length", lm["body"]["missed"])
        self.assertEqual(got["badform"]["body"]["error"]["code"], "invalid_input")
        self.assertIn("no property Width", got["noprop"]["body"]["error"]["message"])
        blk = got["inBlock"]
        self.assertFalse(blk["isError"], blk)
        self.assertEqual(blk["body"]["values"], {"v": "1520 mm³", "twice": 3040.0, "Pad.Length": "4 mm"})

    def test_switch_off(self):
        for case in ("env_off", "pref_off"):
            got = run_case(case)
            self.assertTrue(got["fast"]["isError"], case)
            self.assertEqual(got["fast"]["body"]["error"]["code"], "not_allowed")
            self.assertIn("fast path off", got["fast"]["body"]["error"]["message"])
            self.assertEqual(got["get"]["body"]["error"]["code"], "not_allowed")
            self.assertEqual(got["labels"], ["Body"])

    def test_no_python_and_no_other_runner(self):
        got = run_case("safety")
        for k in ("maker", "fmt", "make", "batch", "private", "unknown"):
            self.assertTrue(got[k]["isError"], k)
            self.assertIn("Nothing was run", got[k]["body"]["error"]["message"], k)
        self.assertIn("maker()", got["maker"]["body"]["error"]["message"])
        self.assertIn("does not run in a fast block", got["batch"]["body"]["error"]["message"])
        self.assertEqual(got["labels"], ["Body"])


class Shape(unittest.TestCase):
    """The block's shape and a get's form, read without a server."""

    def test_shape_words(self):
        from agentlink import fastpath

        self.assertEqual(fastpath.shape_words([{"let": {"x": 1}}, {"call": "pd_pad", "length": "=x * 4"}]), [])
        self.assertTrue(fastpath.shape_words([{"set": {"o.Label": "x"}}]))
        self.assertTrue(fastpath.shape_words([{"do": "=x"}]))
        self.assertTrue(fastpath.shape_words([{"let": {"_x": 1}}]))
        self.assertTrue(fastpath.shape_words([{"let": {"x": "=__import__('os')"}}]))
        self.assertTrue(fastpath.shape_words([{"try": [], "on": "ValueError"}]))
        self.assertEqual(fastpath.shape_words([{"when": "=1", "then": [{"get": "active.body"}]}]), [])

    def test_with_unit(self):
        from agentlink import fastpath

        self.assertEqual(fastpath.with_unit(1520.0, "mm³"), "1520 mm³")
        self.assertEqual(fastpath.with_unit(152000.0, "mm³"), "152,000 mm³")
        self.assertEqual(fastpath.with_unit([1, 2.5, 3], "mm"), "[1, 2.5, 3] mm")
        self.assertEqual(fastpath.with_unit("x", "mm"), "x")
        self.assertIsNone(fastpath.what_words("Body.Edge7.length"))
        self.assertTrue(fastpath.what_words("Body"))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "child":
        _child(sys.argv[2])
    else:
        unittest.main()
