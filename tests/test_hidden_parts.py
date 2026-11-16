# SPDX-License-Identifier: LGPL-2.1-or-later
# Live (16 Nov 2026, the bike stem): part_boolean common with keep on a
# PartDesign Body hid the Body and the screw and said nothing; object_delete
# of the result left its BaseFeature and base shape behind and the inputs
# hidden; view_render then drew neither, silently, and asm_check passed with
# hidden parts left out. view_render drew an assembly and each of its parts
# (everything twice, 8 s became 70 s). fea_solve on a 2-solid Body failed
# with no word from CalculiX. Tutor needed a VarSet. On stand-in modules.
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textwrap  # noqa: E402

from test_stem_findings_more import run_stub as _run  # noqa: E402


def run_stub(code):
    """The stand-in run, DOC_EXTRA and the body each dedented on their own."""
    if code.startswith(DOC_EXTRA):
        return _run(textwrap.dedent(DOC_EXTRA) + textwrap.dedent(code[len(DOC_EXTRA):]))
    return _run(code)

DOC_EXTRA = """
    class Obj2(Obj):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
        def addProperty(self, typ, name, group="", doc=""):
            self.PropertiesList.append(name)
            setattr(self, name, [] if "List" in typ else None)
            return self
        def setEditorMode(self, p, m): pass
        @property
        def OutListRecursive(self):
            out, todo = [], list(self.Group)
            while todo:
                x = todo.pop()
                if x not in out:
                    out.append(x)
                    todo += list(getattr(x, "Group", []) or [])
            return out
    def getObject(self, n):
        return next((o for o in self.Objects if o.Name == n), None)
    Doc.getObject = getObject
    Doc.getObjectsByLabel = lambda self, l: [o for o in self.Objects if o.Label == l]
"""


class Parts(unittest.TestCase):
    def test_assembly_is_not_a_body_and_hidden_parts_are_named(self):
        out = run_stub(DOC_EXTRA + """
            from agentlink.tools import Session
            stem = Obj2("Body", "PartDesign::Body", Shape(2), "Stem")
            stem.Visibility = False
            screw = Obj2("Screw", "Part::FeaturePython", Shape(1), "M8x25-Screw")
            screw.Visibility = False
            plate = Obj2("Plate", "Part::Feature", Shape(1))
            asm = Obj2("Asm", "Assembly::AssemblyObject", Shape(3), "StemAssembly")
            asm.Group = [stem, screw, plate]
            helper = Obj2("FeaParts", "Part::Feature", Shape(2), "FEA parts")
            helper.Visibility = False
            helper.addProperty("App::PropertyBool", "AgentLinkHelper")
            doc = Doc([stem, screw, plate, asm, helper])
            s = Session.__new__(Session)
            s.doc, s.meta = doc, {}
            print(json.dumps({"bodies": [o.Label for o in s.bodies()], "hidden": [o.Label for o in Session.hidden_in(doc)],
                              "state": s._hidden_state()}))
        """)
        self.assertEqual(out["bodies"], ["Plate"])            # the assembly is not drawn over its parts
        self.assertEqual(out["hidden"], ["Stem", "M8x25-Screw"])  # the study's helper is not a part
        self.assertIn("hidden, so not in bodies", out["state"]["hiddenNote"].lower().replace("hidden, so", "hidden, so"))
        self.assertEqual(out["state"]["assemblies"][0]["name"], "StemAssembly")
        self.assertEqual(out["state"]["assemblies"][0]["type"], "assembly")

    def test_container_of_nothing_drawn_stays(self):
        out = run_stub(DOC_EXTRA + """
            from agentlink.tools import Session
            asm = Obj2("Asm", "Assembly::AssemblyObject", Shape(1), "Asm")
            doc = Doc([asm])
            s = Session.__new__(Session)
            s.doc, s.meta = doc, {}
            print(json.dumps([o.Label for o in s.bodies()]))
        """)
        self.assertEqual(out, ["Asm"])

    def test_asm_check_checks_hidden_and_nested_parts(self):
        out = run_stub(DOC_EXTRA + """
            sys.modules["JointObject"] = types.SimpleNamespace(JointTypes=["Fixed"])
            sys.modules["UtilsAssembly"] = types.ModuleType("UtilsAssembly")
            from agentlink.families import assembly as A
            stem = Obj2("Body", "PartDesign::Body", Shape(2), "Stem")
            stem.Visibility = False
            screw = Obj2("Screw", "Part::FeaturePython", Shape(1), "M8x25-Screw")
            sub = Obj2("Sub", "App::Part", Shape(1), "Sub")
            sub.Group = [screw]
            joints = Obj2("Joints", "Assembly::JointGroup", Shape(0))
            sk = Obj2("Sk", "Sketcher::SketchObject", Shape(0))
            asm = Obj2("Asm", "Assembly::AssemblyObject", Shape(3), "StemAssembly")
            asm.Group = [stem, sub, joints, sk]
            parts, hidden, left = A._check_parts(asm)
            print(json.dumps({"parts": [p.Label for p in parts], "hidden": hidden, "left": left}))
        """)
        self.assertEqual(out["parts"], ["Stem", "M8x25-Screw"])
        self.assertEqual(out["hidden"], ["Stem"])
        self.assertEqual(out["left"], ["Sk"])


class Boolean(unittest.TestCase):
    def test_delete_of_a_result_takes_its_helpers_and_shows_the_inputs(self):
        out = run_stub(DOC_EXTRA + """
            from agentlink.families import picks
            from agentlink.tools import Session
            stem = Obj2("Body", "PartDesign::Body", Shape(1), "Stem")
            screw = Obj2("Screw", "Part::FeaturePython", Shape(1), "M8x25-Screw")
            doc = Doc([stem, screw])
            made = []
            def add(typ, name):
                o = Obj2(name + str(len(doc.Objects)), typ, Shape(1) if typ != "App::Origin" else Shape(0))
                doc.Objects.append(o)
                if typ == "PartDesign::Body":
                    fb = Obj2("BaseFeature" + str(len(doc.Objects)), "PartDesign::FeatureBase", Shape(1), "BaseFeature")
                    doc.Objects.append(fb)
                    o.Group = [fb]
                    fb.link("_Body", "App::PropertyLinkHidden", o)
                    org = Obj2("Origin" + str(len(doc.Objects)), "App::Origin", Shape(0))
                    doc.Objects.append(org)
                    org.link("x", "App::PropertyLink", org) if False else None
                    o.Origin = org
                    org.InList.append(o)
                    o._fb = fb
                return o
            doc.addObject = add
            s = Session.__new__(Session)
            s.doc, s.meta, s.steps = doc, {}, []
            s.unique = lambda l, *a: l
            class Geo: pass
            picks.geo.clean = lambda sh: sh
            res = picks.bake(s, stem, Shape(1), "DbgCommon", consumed=[screw], keep=True)
            res._fb.link("BaseFeature", "App::PropertyLink", [o for o in doc.Objects if o.Label.endswith("base shape")][0])
            res.BaseFeature = None
            hid = s.last_hidden
            made, hidrec, labels = picks.made_record(res)
            # object_delete's own logic
            from agentlink.families import doc as D
            D.errors = lambda d: []
            picks.finish = lambda s_, tool, fn, **k: fn()
            tl = {t.name: t for t in D.tools(s)}
            ans = tl["object_delete"].fn({"objects": ["DbgCommon"]})
            print(json.dumps({"hid": hid, "made": len(made), "ans": ans, "left": [o.Label for o in doc.Objects],
                              "visible": [o.Label for o in doc.Objects if o.Visibility]}))
        """)
        self.assertEqual(out["hid"], ["Stem", "M8x25-Screw"])
        self.assertGreaterEqual(out["made"], 2)
        self.assertEqual(sorted(out["left"]), ["M8x25-Screw", "Stem"])  # no BaseFeature, no base shape
        self.assertEqual(sorted(out["visible"]), ["M8x25-Screw", "Stem"])
        self.assertEqual(sorted(out["ans"]["shownAgain"]), ["M8x25-Screw", "Stem"])
        self.assertIn("alongWith", out["ans"])


class Fea(unittest.TestCase):
    def test_unheld_words(self):
        out = run_stub("""
            sys.modules.setdefault("Part", types.ModuleType("Part"))
            from agentlink.families import strength as S
            one = S.unheld_words("Stem", 2, [(2, Vec(1, 2, 3))])
            two = S.unheld_words("Stem", 3, [(2, Vec(1, 2, 3)), (3, Vec(0, 0, 0))])
            tail = S.last_lines("CalculiX 2.21\\n*ERROR in e_c3d: nonpositive jacobian\\nstep 1\\nJob finished")
            print(json.dumps({"one": one, "two": two, "tail": tail}))
        """)
        self.assertIn("solid 2 (at [1.0, 2.0, 3.0]) touches no held face", out["one"])
        self.assertIn("solid 2 (at [1.0, 2.0, 3.0]) and solid 3 (at [0.0, 0.0, 0.0]) touch no held face", out["two"])
        self.assertIn("fea_setup { solid: n }", out["one"])
        self.assertTrue(out["tail"].startswith("*ERROR in e_c3d"))

    def test_ccx_said_reads_femtools_output(self):
        out = run_stub("""
            sys.modules.setdefault("Part", types.ModuleType("Part"))
            from agentlink.families import strength as S
            fea = types.SimpleNamespace(ccx_stdout=b"Reading\\n*ERROR reading *CLOAD: node 12 not defined\\n", ccx_stderr="")
            print(json.dumps(S.ccx_said(fea, "/nonexistent/ccx", 5)))
        """)
        self.assertIn("node 12 not defined", out)


class VarSets(unittest.TestCase):
    def test_kinds_and_labels(self):
        out = run_stub("""
            from agentlink.families import param as P
            kinds = {k: P.var_type(v)[0] for k, v in {"size": "55 mm", "ang": "30 deg", "n": 3, "r": 0.5, "on": True, "note": "steel", "f": "2.5", "p": "3 N"}.items()}
            vs = types.SimpleNamespace(TypeId="App::VarSet", Label="Dims", Name="VarSet001")
            doc = types.SimpleNamespace(Objects=[vs])
            print(json.dumps({"kinds": kinds, "e": P.by_varset_label(doc, "Dims.size / 2 + MyDims.size + VarSet001.size")}))
        """)
        k = out["kinds"]
        self.assertEqual(k["size"], "App::PropertyLength")
        self.assertEqual(k["ang"], "App::PropertyAngle")
        self.assertEqual((k["n"], k["r"], k["on"], k["note"]), ("App::PropertyInteger", "App::PropertyFloat", "App::PropertyBool", "App::PropertyString"))
        self.assertEqual(k["f"], "App::PropertyFloat")
        self.assertEqual(k["p"], "App::PropertyQuantity")
        self.assertEqual(out["e"], "VarSet001.size / 2 + MyDims.size + VarSet001.size")


if __name__ == "__main__":
    unittest.main()
