# SPDX-License-Identifier: LGPL-2.1-or-later
# The fast path (efficiency design C6, A6) and targeted reads (22 Nov),
# agentlink/fastpath.py: one call runs a list of flat steps ({ tool, inputs }),
# each call through the server's normal path, with one short answer;
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
        return {"sketch": sk.Label, "added": 1, "kind": a.get("kind"), "center": a.get("center"), "health": {"facts": "recompute: FreeCAD reports no recompute error"}}

    def pd_pad(a):
        sk = doc.getObject(a.get("sketch") or "") if a.get("sketch") else None
        if sk is None:
            raise ToolError("invalid_input", "sketch: which one? (the stand-in wants it named)")
        pad = doc.add("Pad", "PartDesign::Pad", sk.parent)
        return {"pad": pad.Label, "length": a.get("length"), "health": {"facts": "recompute: FreeCAD reports no recompute error"}}

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

    def run1(step):
        # run takes { calls: [step] } (27 Nov), the same list as batch and fast.
        return one("run", {"calls": [step]})

    def labels():
        return [o.Label for o in doc.Objects]

    design = {"calls": [
        {"tool": "sketch_new", "plane": "XY"},
        {"tool": "sketch_add", "each": {"x": [10, 30, 50]}, "kind": "circle", "center": ["$x", 0], "radius": 3},
        {"tool": "pd_pad", "length": 4}]}
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
            n += one("sketch_add", {"sketch": "Sketch", "kind": "circle", "center": [x, 0], "radius": 3})["chars"]
        n += one("pd_pad", {"sketch": "Sketch", "length": 4})["chars"]
        out["chars"] = n
        out["fastChars"] = None
    elif case in ("old_a", "old_b", "old_c"):
        # Every old form is refused with the new form in the words, and nothing runs.
        # (Four calls in a case: the server stops a fifth refusal of the same tool.)
        steps = {"arguments": {"tool": "probe_change", "arguments": {"n": 1}}, "call": {"call": "probe_change", "n": 1},
                 "as": {"tool": "probe_change", "n": 1, "as": "r"}, "when": {"tool": "probe_change", "n": 1, "when": "=True"},
                 "let": {"let": {"x": 1}}, "try": {"try": [], "except": []}, "choose": {"choose": "=1", "of": {}},
                 "each": {"each": "x", "in": [1, 2], "steps": [{"tool": "probe_change", "n": "=x"}]}, "get": {"get": "Body.volume"}}
        for k in {"old_a": ("arguments", "call", "as", "when"), "old_b": ("let", "try", "choose", "each"), "old_c": ("get",)}[case]:
            out[k] = fast({"calls": [steps[k]]})
        if case == "old_c":
            out["do"] = fast({"do": [{"tool": "probe_change", "n": 1}]})
        out["labels"] = labels()
        out["seen"] = [t for t, _a in seen]
    elif case == "required":
        out["first"] = fast({"calls": [{"tool": "sketch_new", "plane": "XY"}]})
        out["got"] = fast({"calls": [{"tool": "probe_req"}]})
        out["seen"] = seen
    elif case == "rollback":
        out["got"] = fast({"rollback": True, "calls": [{"tool": "probe_change", "n": 1}, {"tool": "probe_change", "n": 2}, {"tool": "probe_fail"}, {"tool": "probe_change", "n": 3}]})
        out["labels"] = labels()
        out["undone"] = doc.undone
        out["seen"] = [t for t, _a in seen]
    elif case == "keep":
        # The default since 23 Nov (owner): what ran before a refusal stays.
        out["got"] = fast({"calls": [{"tool": "probe_change", "n": 1}, {"tool": "probe_change", "n": 2}, {"tool": "probe_fail"}]})
        out["labels"] = labels()
        out["undone"] = doc.undone
    elif case == "person":
        out["got"] = fast({"rollback": True, "calls": [{"tool": "probe_change", "n": 1}, {"tool": "probe_person"}, {"tool": "probe_change", "n": 2}, {"tool": "probe_fail"}]})
        out["labels"] = labels()
        out["undoNames"] = list(doc.UndoNames)
    elif case == "dry":
        out["bad"] = fast({"check": True, "calls": [{"tool": "sketch_add", "each": {"x": [1, 2]}, "kind": "circle", "bogus": 1}]})
        out["good"] = fast({"check": True, **design})
        out["seen"] = seen
        out["labels"] = labels()
    elif case == "a6":
        out["fast"] = fast({"calls": [{"tool": "probe_person"}, {"tool": "probe_lead", "n": 0}]})
        out["seenFast"] = [t for t, _a in seen]
        out["late"] = fast({"rollback": True, "calls": [{"tool": "probe_change", "n": 1}, {"tool": "probe_lead", "n": 0}]})
        out["labelsAfterLate"] = labels()
        del seen[:]
        out["batch"] = one("batch", {"check": True, "calls": [{"tool": "probe_person"}, {"tool": "probe_lead", "n": 0}]})
        out["seenBatch"] = [t for t, _a in seen]
        out["batchPlain"] = one("batch", {"calls": [{"tool": "probe_person"}, {"tool": "probe_lead", "n": 0}]})
        out["batchOk"] = one("batch", {"check": True, "calls": [{"tool": "probe_lead", "n": 1}]})
    elif case == "get":
        fast({"calls": [{"tool": "sketch_new", "plane": "XY"}, {"tool": "pd_pad", "length": 4}]})
        out["one"] = one("get", {"what": ["Pad.Length", "Body.volume", "Body.Edge7.length", "sketch.dof", "active.body", "active.sketch",
                                          "Body.mass", "bodies", "selection", "Sketch.closedWires"]})
        out["missing"] = one("get", {"what": "Nope.Length"})
        out["listMiss"] = one("get", {"what": ["Pad.Length", "Nope.Length"]})
        out["badform"] = one("get", {"what": "Pad"})
        out["noprop"] = one("get", {"what": "Pad.Width"})
        out["inBlock"] = fast({"calls": [{"tool": "get", "what": "Body.volume"}, {"tool": "get", "what": ["Pad.Length", "Nope.Length"]}]})
    elif case in ("env_off", "pref_off"):
        out["fast"] = fast(design)
        out["get"] = one("get", {"what": "active.body"})
        out["labels"] = labels()
    elif case == "names":
        # Live, 22 Nov: a local model put the client's prefixed name inside a batch.
        out["prefixed"] = one("batch", {"calls": [{"tool": "agentlink_tool_find", "words": "pad"}]})
        out["unknown"] = one("batch", {"calls": [{"tool": "agentlink_pd_pad_create"}]})
        out["toolread"] = fast({"calls": [{"tool": "get", "what": "body_check"}]})
    elif case == "safety":
        # No Python, no other runner: a step is a tool step and nothing else.
        out["maker"] = fast({"calls": [{"tool": "probe_change", "n": "=maker('os.system')"}]})
        out["make"] = fast({"calls": [{"make": "Part.show"}]})
        out["batch"] = fast({"calls": [{"tool": "batch", "calls": []}]})
        out["run"] = fast({"calls": [{"tool": "run", "tool_": "x"}]})
        out["unknown"] = fast({"calls": [{"tool": "no_such_tool"}]})
        out["labels"] = labels()
    elif case == "flat1127":
        # 27 Nov: the renamed inputs (card, job) and the flat sketch inputs, through run, batch and fast.
        out["findRun"] = run1({"tool": "tool_find", "card": "sketch_add"})
        out["findBatch"] = one("batch", {"calls": [{"tool": "tool_find", "card": "pd_pad"}]})
        out["findFast"] = fast({"calls": [{"tool": "tool_find", "card": "pd_pad"}]})
        out["groupsRun"] = run1({"tool": "tool_groups", "card": "pd_pad"})
        out["groupsBatch"] = one("batch", {"calls": [{"tool": "tool_groups", "card": "pd_pad"}]})
        out["groupsFast"] = fast({"calls": [{"tool": "tool_groups", "card": "pd_pad"}]})
        out["jobRun"] = run1({"tool": "job_start", "job": "measure_mass", "arguments": {}})
        out["jobBatch"] = one("batch", {"calls": [{"tool": "job_start", "job": "measure_mass", "arguments": {}}]})
        out["jobFast"] = fast({"calls": [{"tool": "job_start", "job": "measure_mass", "arguments": {}}]})
        out["oldFind"] = one("tool_find", {"tool": "pd_pad"})
        out["oldGroups"] = one("tool_groups", {"tool": "pd_pad"})
        out["oldJob"] = one("job_start", {"tool": "probe_change"})
        one("sketch_new", {"plane": "XY"})
        del seen[:]
        out["addRun"] = run1({"tool": "sketch_add", "kind": "rectangle", "center": [0, 0], "size": [40, 20]})
        out["itemsRun"] = run1({"tool": "sketch_add", "items": [{"kind": "circle", "center": [0, 0], "radius": 3}]})
        out["badKind"] = run1({"tool": "sketch_add", "kind": "squiggle"})
        out["eachBatch"] = one("batch", {"calls": [{"tool": "sketch_add", "each": {"x": [15, 45]}, "kind": "circle", "center": ["$x", 15], "radius": 5}]})
        out["twoBatch"] = one("batch", {"calls": [{"tool": "sketch_add", "kind": "rectangle", "center": [0, 0], "size": [40, 20]},
                                                  {"tool": "sketch_add", "kind": "circle", "center": [5, 5], "radius": 2}]})
        out["conRun"] = run1({"tool": "sketch_constrain", "type": "horizontal", "refs": [0]})
        out["consRun"] = run1({"tool": "sketch_constrain", "constraints": [{"type": "horizontal", "refs": [0]}]})
        out["seenSketch"] = [[t, a] for t, a in seen if t == "sketch_add"]
        from agentlink import staticbase as _sb, tools as _tools
        out["props"] = {n: sorted(srv.tools[n].schema["properties"]) for n in ("tool_find", "tool_groups", "job_start")}
        out["texts"] = {"STATIC_NOTE": _tools.STATIC_NOTE, "WORKING": _tools.WORKING, "TG_CARDS_NOTE": _tools.TG_CARDS_NOTE, "BASIC_FORM": _sb.BASIC_FORM}
    elif case == "result1127":
        # 27 Nov: each call's answer starts with result, in run, in batch and in fast (the stand-in tools answer as the real ones: result first).
        def probe_result(a):
            doc.add(f"R{a.get('n')}", "Part::Feature")
            return {"result": {"objects": 1}, "n": a.get("n"), "volumeChange": 5.0}

        srv.add(Tool("probe_result", "A change that says its result.", num, probe_result, changes=True))
        out["run"] = run1({"tool": "probe_result", "n": 1})
        out["runMany"] = one("run", {"calls": [{"tool": "probe_result", "n": 9}, {"tool": "pd_pad", "sketch": "S", "length": 6}, {"tool": "probe_change", "n": 10}]})
        out["batch"] = one("batch", {"calls": [{"tool": "probe_result", "n": 2}, {"tool": "probe_change", "n": 3}, {"tool": "probe_result", "n": 4}]})
        out["fast"] = fast({"calls": [{"tool": "probe_result", "n": 5}, {"tool": "probe_change", "n": 6}, {"tool": "probe_result", "n": 7}]})
        out["fastNone"] = fast({"calls": [{"tool": "probe_change", "n": 8}]})
    elif case == "flat":
        # One flat step everywhere (26 Nov): run, batch and fast take the same steps.
        calls = [{"tool": "probe_change", "n": 1}, {"tool": "probe_change", "n": 2}]
        out["run"] = run1({"tool": "probe_change", "n": 7})
        out["direct"] = one("probe_change", {"n": 8})
        out["approve"] = [run1({"tool": t, "path": "x"}) for t in ("approve_file", "approve_code")]
        out["runInRun"] = run1({"tool": "run", "x": 1})
        out["batchSame"] = one("batch", {"calls": calls})
        out["labelsBatch"] = labels()
        out["fastSame"] = fast({"calls": calls})
        out["do"] = fast({"do": calls})
        out["batchDo"] = one("batch", {"do": calls})
        del seen[:]
        out["eachRun"] = run1({"tool": "probe_change", "each": {"x": [15, 45]}, "n": "$x"})
        one("sketch_new", {"plane": "XY"})
        out["eachBatch"] = one("batch", {"calls": [{"tool": "sketch_add", "each": {"x": [15, 45]}, "sketch": "Sketch", "kind": "circle", "center": ["$x", 15], "radius": 5}]})
        out["eachFast"] = fast({"calls": [{"tool": "sketch_add", "each": {"x": [3, 4, 5]}, "sketch": "Sketch", "kind": "circle", "center": ["$x", 0], "radius": 1}]})
        out["seenEach"] = [[t, a] for t, a in seen if t in ("probe_change", "sketch_add")]
        del seen[:]
        out["twoVars"] = one("batch", {"calls": [{"tool": "probe_change", "each": {"x": [1], "y": [2]}, "n": "$x"}]})
        out["badLoop"] = one("batch", {"calls": [{"tool": "probe_change", "n": 11}, {"tool": "probe_change", "each": {"s": ["A", 5]}, "sketch": "$s", "n": 12}, {"tool": "probe_change", "n": 13}]})
        out["labelsLoop"] = labels()
        out["from"] = one("batch", {"calls": [{"tool": "sketch_new", "name": "FromSk", "plane": "XY"}, {"tool": "probe_req", "sketch": {"$from": 0, "$at": "sketch"}}]})
        out["writeFast"] = fast({"calls": [{"tool": "probe_change", "n": 20, "writeTo": "a.json"}]})
        out["writeEach"] = one("batch", {"calls": [{"tool": "probe_change", "each": {"x": [1, 2]}, "n": "$x", "writeTo": "a.json"}]})
        out["writeBatch"] = one("batch", {"calls": [{"tool": "probe_change", "n": 21, "writeTo": "w.json"}]})
        out["writeFile"] = os.path.exists(os.path.join(s.out_dir, "w.json"))
        out["oldBatch"] = {k: one("batch", {"calls": [v]}) for k, v in {"arguments": {"tool": "probe_change", "arguments": {"n": 1}}, "as": {"tool": "probe_change", "n": 1, "as": "r"},
                                                                         "when": {"tool": "probe_change", "n": 1, "when": "=True"}, "let": {"let": {"x": 1}}}.items()}
        out["oldRun"] = [run1(v) for v in ({"tool": "probe_change", "arguments": {"n": 1}}, {"tool": "probe_change", "n": 1, "try": []})]
        # 27 Nov: run takes { calls: [step] }, the same list as batch and fast; it runs the first step only.
        out["runOne"] = one("run", {"calls": [{"tool": "probe_change", "n": 31}]})
        out["directOne"] = one("probe_change", {"n": 32})
        before = labels()
        out["runThree"] = one("run", {"calls": [{"tool": "probe_change", "n": 41}, {"tool": "sketch_new", "plane": "XY"}, {"tool": "probe_change", "n": 43}]})
        out["runThreeNew"] = [x for x in labels() if x not in before]
        before = labels()
        out["runBadLater"] = one("run", {"calls": [{"tool": "probe_change", "n": 51}, {"nope": 1}, "text"]})
        out["runBadLaterNew"] = [x for x in labels() if x not in before]
        out["oldFlat"] = one("run", {"tool": "probe_change", "n": 61})
        out["oldFlatNew"] = [x for x in labels() if x == "P61"]
        out["emptyCalls"] = one("run", {"calls": []})
        out["noCalls"] = one("run", {})
        out["notList"] = one("run", {"calls": {"tool": "probe_change", "n": 62}})
        out["extraKey"] = one("run", {"calls": [{"tool": "probe_change", "n": 63}], "rollback": True})
        out["batchInRun"] = one("run", {"calls": [{"tool": "batch", "calls": [{"tool": "probe_change", "n": 64}]}]})
        out["fastInRun"] = one("run", {"calls": [{"tool": "fast", "calls": [{"tool": "probe_change", "n": 65}]}]})
        out["approveInRun"] = one("run", {"calls": [{"tool": "approve_code", "path": "x"}]})
        out["eachCalls"] = one("run", {"calls": [{"tool": "probe_change", "each": {"x": [71, 72]}, "n": "$x"}]})
        out["eachExtra"] = one("run", {"calls": [{"tool": "probe_change", "each": {"x": [73]}, "n": "$x"}, {"tool": "probe_change", "n": 74}]})
        out["wrongFirst"] = one("run", {"calls": [{"tool": "probe_change", "arguments": {"n": 1}}, {"tool": "probe_change", "n": 75}]})
        out["labelsEnd"] = labels()
        from agentlink import callshape as _cs
        out["collide"] = sorted(f"{n}.{k}" for n, t in srv.tools.items() for k in (t.schema or {}).get("properties", {}) if k in _cs.RESERVED)
        out["reserved"] = sorted(_cs.RESERVED)
        out["listed"] = [t["name"] for t in srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]]
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
    def test_batch_reads_prefixed_names_and_near_names(self):
        got = run_case("names")
        self.assertFalse(got["prefixed"]["isError"], got["prefixed"])
        # A tool that is not here is refused by itself, in its order (23 Nov).
        self.assertFalse(got["unknown"]["isError"], got["unknown"])
        self.assertEqual(got["unknown"]["body"]["refused"]["code"], "not_found")
        msg = got["unknown"]["body"]["results"][0]["error"]["message"]
        self.assertIn("near: pd_pad", msg)
        self.assertIn('{ "tool": "body_check" }', got["toolread"]["body"]["error"]["message"])

    def test_design_block_runs_each_call_through_the_server(self):
        got = run_case("design")
        self.assertFalse(got["got"]["isError"], got["got"])
        body = got["got"]["body"]
        # One short line, with the real names of what was made.
        self.assertTrue(body["fast"].startswith("ran 5 calls "), body)
        self.assertIn("+Sketch", body["fast"])
        self.assertIn("+Pad", body["fast"])
        self.assertTrue(body["fast"].endswith("health: no fault in the readings of the calls"), body)
        self.assertLessEqual(set(body), {"fast", "values", "warnings", "filled", "checkpoint", "record", "ms", "made", "checks", "now"})
        # Every call went through the server's own path, in order, with the sketch filled in from the block.
        tools = [t for t, _a in got["seen"]]
        self.assertEqual(tools, ["fast", "sketch_new", "sketch_add", "sketch_add", "sketch_add", "pd_pad"])
        self.assertEqual([a.get("sketch") for t, a in got["seen"] if t in ("sketch_add", "pd_pad")], ["Sketch"] * 4)
        # The loop: one call for each value, "$x" put in a list.
        self.assertEqual([a["center"] for t, a in got["seen"] if t == "sketch_add"], [[10, 0], [30, 0], [50, 0]])
        self.assertIn("pd_pad.sketch=Sketch", body["filled"])
        # The record holds each call's whole answer, by its step.
        rec = got["record"]
        self.assertTrue(rec["fast"])
        self.assertEqual([r["step"] for r in rec["results"]], ["calls.0", "calls.1", "calls.2", "calls.3", "calls.4"])
        self.assertEqual(rec["results"][-1]["result"]["pad"], "Pad")

    def test_terse_answer_is_shorter_than_single_calls(self):
        fast = run_case("design")["got"]["chars"]
        single = run_case("single")["chars"]
        self.assertLess(fast, single, (fast, single))

    def test_old_forms_are_refused_with_the_new_form(self):
        got = {}
        for c in ("old_a", "old_b", "old_c"):
            r = run_case(c)
            got.update({k: v for k, v in r.items() if k not in ("labels", "seen")})
            self.assertEqual(r["labels"], ["Body"], c)
            self.assertEqual(set(r["seen"]), {"fast"}, c)
        words = {"arguments": "beside tool", "call": "old form", "as": "$from", "when": "not part of a step", "let": "use each",
                 "try": "not part of a step", "choose": "not part of a step", "each": "each is now a key of the step", "get": '"tool": "get"'}
        for k, w in words.items():
            self.assertTrue(got[k]["isError"], k)
            msg = got[k]["body"]["error"]["message"]
            self.assertIn(w, msg, (k, msg))
            self.assertIn("Nothing was run", msg, k)
        self.assertTrue(got["do"]["isError"])
        self.assertIn("do is now calls", got["do"]["body"]["error"]["message"])

    def test_required_field_fills_from_the_session(self):
        got = run_case("required")
        self.assertFalse(got["got"]["isError"], got["got"])
        self.assertIn("probe_req.sketch=Sketch", got["got"]["body"]["filled"])
        self.assertEqual([a for t, a in got["seen"] if t == "probe_req"], [{"sketch": "Sketch"}])

    def test_design_block_names_what_it_made(self):
        body = run_case("design")["got"]["body"]
        made = body["made"]
        self.assertTrue(made and all({"name", "label", "type"} <= set(m) for m in made), made)
        self.assertIn("Pad", [m["type"] for m in made])

    def test_refusal_names_what_ran(self):
        err = run_case("rollback")["got"]["body"]["error"]
        self.assertIn("Ran before it: calls.0 probe_change, calls.1 probe_change.", err["message"])

    def test_keep_keeps_what_ran(self):
        got = run_case("keep")
        err = got["got"]["body"]["error"]
        self.assertEqual(err["status"], "kept")
        self.assertIn("Ran before it: calls.0 probe_change, calls.1 probe_change.", err["message"])
        self.assertIn("Go on from step calls.2", err["message"])
        self.assertEqual(got["undone"], 0)
        self.assertIn("P1", got["labels"])

    def test_refused_call_rolls_the_block_back(self):
        got = run_case("rollback")
        self.assertTrue(got["got"]["isError"])
        err = got["got"]["body"]["error"]
        self.assertEqual(err["code"], "invalid_state")
        self.assertEqual(err["status"], "rolled_back")
        self.assertIn("step calls.2 (probe_fail)", err["message"])
        self.assertIn("2 undo steps", err["message"])
        self.assertEqual(got["undone"], 2)
        self.assertNotIn("P1", got["labels"])
        self.assertNotIn("P3", got["labels"])
        self.assertEqual(got["seen"], ["fast", "probe_change", "probe_change", "probe_fail"])

    def test_rollback_stops_at_the_persons_step(self):
        got = run_case("person")
        self.assertTrue(got["got"]["isError"])
        err = got["got"]["body"]["error"]
        self.assertEqual(err["status"], "partial")
        self.assertIn("not the agent's (Person edit)", err["message"])
        self.assertIn("P1", got["labels"])
        self.assertNotIn("P2", got["labels"])
        self.assertEqual(got["undoNames"][0], "Person edit")

    def test_dry_run_refuses_with_the_step_number_and_runs_nothing(self):
        got = run_case("dry")
        self.assertTrue(got["bad"]["isError"])
        msg = got["bad"]["body"]["error"]["message"]
        self.assertIn("step calls.0 (sketch_add)", msg)
        self.assertIn("bogus", msg)
        self.assertIn("Nothing was run", msg)
        self.assertEqual(got["bad"]["body"]["error"]["status"], "not_started")
        self.assertFalse(got["good"]["isError"], got["good"])
        self.assertTrue(got["good"]["body"]["fast"].startswith("check: no refusal found: 5 calls"), got["good"])
        self.assertEqual([t for t, _a in got["seen"]], ["fast", "fast"])
        self.assertEqual(got["labels"], ["Body"])

    def test_a6_leading_checks_before_step_1(self):
        got = run_case("a6")
        # Fast: the leading check of step 2 refuses before step 1; nothing ran.
        self.assertTrue(got["fast"]["isError"])
        self.assertIn("step calls.1 (probe_lead): probe_lead: n is 0", got["fast"]["body"]["error"]["message"])
        self.assertEqual(got["fast"]["body"]["error"]["code"], "invalid_state")
        self.assertEqual(got["seenFast"], ["fast"])
        # After a change the document is not known before the run: the step runs, is refused, and the block is taken back.
        self.assertTrue(got["late"]["isError"])
        self.assertEqual(got["late"]["body"]["error"]["status"], "rolled_back")
        self.assertNotIn("P1", got["labelsAfterLate"])
        # batch { check: true }: refused with the call's index, nothing run; without check it runs as before.
        self.assertTrue(got["batch"]["isError"])
        self.assertIn("calls.1 (probe_lead)", got["batch"]["body"]["error"]["message"])
        self.assertEqual(got["seenBatch"], ["batch"])
        self.assertFalse(got["batchPlain"]["isError"])
        self.assertEqual(got["batchPlain"]["body"]["refused"]["call"], 1)
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
        self.assertEqual(blk["body"]["values"], {"Body.volume": "1520 mm³", "Pad.Length": "4 mm"})

    def test_switch_off(self):
        for case in ("env_off", "pref_off"):
            got = run_case(case)
            self.assertTrue(got["fast"]["isError"], case)
            self.assertEqual(got["fast"]["body"]["error"]["code"], "not_allowed")
            self.assertIn("fast path off", got["fast"]["body"]["error"]["message"])
            self.assertEqual(got["get"]["body"]["error"]["code"], "not_allowed")
            self.assertEqual(got["labels"], ["Body"])

    def test_a_step_is_a_tool_step_and_nothing_else(self):
        got = run_case("safety")
        for k in ("make", "batch", "run", "unknown"):
            self.assertTrue(got[k]["isError"], k)
        self.assertIn("Nothing was run", got["make"]["body"]["error"]["message"])
        self.assertIn("a step has no \"tool\"", got["make"]["body"]["error"]["message"])
        self.assertIn("does not run in a fast block", got["batch"]["body"]["error"]["message"])
        self.assertIn("does not run in a fast block", got["run"]["body"]["error"]["message"])
        # "=maker(...)" is only text now: no expression is read. The tool gets it as it is.
        self.assertFalse(got["maker"]["isError"], got["maker"])
        self.assertEqual(got["labels"], ["Body", "P=maker('os.system')"])


class Shape(unittest.TestCase):
    """The block's shape and a get's form, read without a server."""

    def test_steps_of(self):
        from agentlink import callshape

        class Srv:
            tools = {}

        got = callshape.steps_of(Srv, {"tool": "pd_pad", "length": 4, "each": {"x": [1, 2]}, "sketch": "S"}, "calls.0", "fast")
        self.assertEqual([p["inputs"] for p in got], [{"length": 4, "sketch": "S"}] * 2)
        for bad in ({"let": {"x": 1}}, {"set": 1}, {"tool": "x", "as": "r"}, {"tool": "x", "arguments": {}}, {"tool": "x", "each": {"a": [1], "b": [2]}},
                    {"tool": "x", "each": {"a": []}}, {"tool": "x", "each": {"a": [1]}, "n": "$b"}, {"tool": "x", "writeTo": "a.json"}):
            with self.assertRaises(callshape.Refused, msg=str(bad)):
                callshape.steps_of(Srv, bad, "calls.0", "fast")

    def test_with_unit(self):
        from agentlink import fastpath

        self.assertEqual(fastpath.with_unit(1520.0, "mm³"), "1520 mm³")
        self.assertEqual(fastpath.with_unit(152000.0, "mm³"), "152000 mm³")
        # The feature answers' precision, in plain notation (24 Nov blind QA: "1.405e+04 mm³").
        self.assertEqual(fastpath.with_unit(14053.6512, "mm³"), "14053.65 mm³")
        self.assertEqual(fastpath.with_unit(14053.6, "mm²"), "14053.6 mm²")
        self.assertEqual(fastpath.with_unit(0.012345, "mm"), "0.0123 mm")
        self.assertEqual(fastpath.with_unit(-2.5, "mm"), "-2.5 mm")
        self.assertEqual(fastpath.with_unit([1234567.891, 0.5], "mm"), "[1234567.89, 0.5] mm")
        self.assertEqual(fastpath.with_unit(1.88612, "g"), "1.8861 g")
        self.assertEqual(fastpath.with_unit(15260.5, "g"), "15260.5 g")
        self.assertEqual(fastpath.with_unit([1, 2.5, 3], "mm"), "[1, 2.5, 3] mm")
        self.assertEqual(fastpath.with_unit("x", "mm"), "x")
        self.assertIsNone(fastpath.what_words("Body.Edge7.length"))
        self.assertTrue(fastpath.what_words("Body"))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "child":
        _child(sys.argv[2])
    else:
        unittest.main()
