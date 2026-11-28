# SPDX-License-Identifier: LGPL-2.1-or-later
# Facts only (owner, 27 Nov): the hub does what FreeCAD does and says what was
# measured. These tests pin each new fact of the branch `factsonly`:
#   - a feature that changed nothing and a dress-up that FreeCAD kept are
#     answered, with the measured fact, and not refused;
#   - FreeCAD's own defaults, and "<input> not given, so <input> is <value>";
#   - the values FreeCAD stored, under FreeCAD's property names;
#   - no word of advice in the texts that these tests read.
# The FreeCAD-facing code runs on stand-ins here (child processes). What must
# be seen on a real FreeCAD 1.1 is in the build report.
import json
import os
import subprocess
import sys
import textwrap
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import resultline as rl  # noqa: E402

CHILD = '''
import json, sys, types
sys.path.insert(0, %r); sys.path.insert(0, %r)
import _datapd_standin
fc = _datapd_standin.install()
fc.patch()
from agentlink.families import pd_common as pc
''' % (ROOT, HERE)


def _cw(entry):
    """Every word of a tools.json entry: its card and its inputs' meanings (agentlink.tooldata.card_words)."""
    from agentlink.tooldata import card_words
    return card_words(entry)


def child(body):
    r = subprocess.run([sys.executable, "-c", CHILD + textwrap.dedent(body)], capture_output=True, text=True, timeout=120, cwd=HERE)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def entries():
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


def source(*path):
    with open(os.path.join(ROOT, "agentlink", *path), encoding="utf-8") as f:
        return f.read()


SETTLE = '''
        class BB:
            def __init__(s, b): s.XMin, s.XMax, s.YMin, s.YMax, s.ZMin, s.ZMax = b; s.DiagonalLength = 100.0
        class Shp:
            def __init__(s, valid=True, faces=6): s.ok, s.Faces, s.BoundBox, s.Solids = valid, [0] * faces, BB((0, 60, 0, 30, 0, 5)), [0]
            def isNull(s): return False
            def isValid(s): return s.ok
            def countElement(s, k): return len(s.Faces)
            def optimalBoundingBox(s, a, b): return types.SimpleNamespace(isValid=lambda: True, **s.BoundBox.__dict__)
        class Doc:
            Objects = []
            def recompute(s): pass
        vol = [100.0]
        pc.newly_broken = lambda d: []
        pc.body_reading = lambda b: {"volume": vol[0]}
        pc.picks.finish = lambda s, tool, out, recompute=False: out
        sess = types.SimpleNamespace(doc=Doc())
        def feat(kind, **kw):
            return types.SimpleNamespace(Label=kind, Name=kind, TypeId="PartDesign::" + kind, PropertiesList=list(kw), BaseFeature=None, **kw)
'''


class NothingRefusedThatFreeCADKept(unittest.TestCase):
    def test_a_feature_that_changes_no_volume_is_answered(self):
        got = child(SETTLE + '''
        body = types.SimpleNamespace(Label="Body", Shape=Shp())
        out = {}
        for kind, tool, must in (("Pad", "pd_pad", "add"), ("Pocket", "pd_pocket", "cut"), ("Fillet", "pd_fillet", "changed"), ("Thickness", "pd_thickness", "cut")):
            r = pc.settle(sess, body, feat(kind), tool, 100.0, must)
            out[kind] = [r["volumeChange"], r.get("result", {}), r.get("valid")]
        print(json.dumps(out))
        ''')
        for kind in ("Pad", "Pocket", "Fillet", "Thickness"):
            self.assertEqual(got[kind][0], 0.0, kind)
            self.assertEqual(got[kind][2], True, kind)
        self.assertNotIn("material", got["Pad"][1])  # a change that rounds to 0 has no material word: volumeChange says 0
        self.assertNotIn("material", got["Pocket"][1])
        self.assertIn("edgesGiven", got["Fillet"][1])

    def test_a_dress_up_with_a_shape_that_is_not_valid_is_answered_with_the_fact(self):
        got = child(SETTLE + '''
        body = types.SimpleNamespace(Label="Body", Shape=Shp(valid=False))
        vol[0] = 97.0
        r = pc.settle(sess, body, feat("Fillet", Radius=2.0), "pd_fillet", 100.0, "changed")
        big = pc.shape_valid(types.SimpleNamespace(Shape=Shp(valid=False, faces=5000)))
        print(json.dumps([r["valid"], r["result"], big, pc.shape_valid(types.SimpleNamespace(Shape=None))]))
        ''')
        self.assertIs(got[0], False)
        self.assertIsInstance(got[1], dict)  # the fact is the answer's valid: false, not a sentence
        self.assertEqual(got[2], "not checked: the shape has 5000 faces, and the check runs for 3000 at most")  # a limit that is used is said
        self.assertIsNone(got[3])

    def test_freecads_error_is_passed_with_measured_facts_only(self):
        got = child(SETTLE + '''
        from agentlink.protocol import ToolError
        body = types.SimpleNamespace(Label="Body", Shape=Shp())
        out = []
        for err in ("BRep_API: command not done", "Result has multiple solids"):
            pc.newly_broken = lambda d, err=err: [{"object": "Pad", "type": "Pad", "error": err}]
            try:
                pc.settle(sess, body, feat("Pad"), "pd_pad", 100.0, "add", hint="Try a smaller size.")
            except ToolError as e:
                out.append(e.message)
        print(json.dumps(out))
        ''')
        self.assertEqual(got[0], "Pad (Pad) failed: BRep_API: command not done — nothing was kept.")
        self.assertEqual(got[1], "Pad (Pad) failed: Result has multiple solids — nothing was kept. AllowCompound is false on Body.")

    def test_no_text_of_a_refused_result_is_left(self):
        pd = source("families", "pd_common.py")
        for gone in ("added no material", "cut nothing — the profile", "removed no material", "left the body as it was", "Try a smaller size", "needs a sketch of its own",
                     "Nothing was kept. {hint}", "Move the outline over the body"):
            self.assertNotIn(gone, pd, gone)
        e = entries()
        for name, gone in (("pd_pad", "a pad inside the body"), ("pd_pocket", "refuses a pocket that cuts nothing"), ("pd_groove", "refuses a groove"),
                           ("pd_chamfer", "refuses only a chamfer"), ("pd_hole", "modelThread makes nothing"), ("doc_save", "saved only after"),
                           ("doc_new", "saves only after")):
            self.assertNotIn(gone, _cw(e[name]), name)

    def test_the_save_gate_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "agentlink", "measured.py")))
        for path in (("protocol.py",), ("tools.py",), ("fastpath.py",)):
            self.assertNotIn("measure_refusal", source(*path), path)

    def test_a_sketch_state_has_facts_and_no_verdict(self):
        src = source("families", "sketch.py")
        for gone in ("readyForFeature", "no profile yet", "close the open wires", "make one outline", "use an arc there", "fix the constraints named"):
            self.assertNotIn(gone, src, gone)
        for fact in ('out["wiresMeet"]', 'out["selfCrossing"] = "not tested"', 'out["points"]', 'out["openVerticesCount"]'):
            self.assertIn(fact, src, fact)


class WhatFreeCADStored(unittest.TestCase):
    def test_stored_values_by_freecads_names(self):
        got = child('''
        ax = types.SimpleNamespace(Label="X_Axis", Name="X_Axis")
        f = types.SimpleNamespace(TypeId="PartDesign::LinearPattern", PropertiesList=["Direction", "Reversed", "Mode", "Length", "Offset", "Occurrences", "Refine", "Label"],
                                  Direction=(ax, [""]), Reversed=False, Mode="Extent", Length=types.SimpleNamespace(Value=100.0), Offset=10.0, Occurrences=2, Refine=True, Label="LP")
        h = types.SimpleNamespace(TypeId="PartDesign::Hole", PropertiesList=["DepthType", "Depth", "DrillPoint", "DrillPointAngle", "ThreadFit", "Threaded"],
                                  DepthType="Dimension", Depth=25.0, DrillPoint="Angled", DrillPointAngle=118.0, ThreadFit="Medium", Threaded=False)
        print(json.dumps([pc.stored_values(f), pc.stored_values(h), pc.stored_values(None), pc.stored_values(types.SimpleNamespace(TypeId="Part::Box", PropertiesList=[]))]))
        ''')
        self.assertEqual(got[0]["Direction"], "X_Axis")
        self.assertEqual({k: got[0][k] for k in ("Reversed", "Mode", "Offset", "Occurrences", "Refine")},
                         {"Reversed": False, "Mode": "Extent", "Offset": 10.0, "Occurrences": 2, "Refine": True})
        self.assertNotIn("Direction2", got[0])  # only what this FreeCAD's feature has
        self.assertEqual(got[1], {"DepthType": "Dimension", "Depth": 25.0, "DrillPoint": "Angled", "DrillPointAngle": 118.0, "ThreadFit": "Medium", "Threaded": False})
        self.assertEqual(got[2:], [{}, {}])

    def test_not_given_in_the_form_of_sketch_add(self):
        got = child('''
        a = {"radius": None, "sides": "two"}
        out = pc.not_given({}, a, {"radius": 1, "sides": "one", "reversed": False, "angle": 1.5, "length": None, "extent": "length"})
        print(json.dumps([out, pc.not_given({}, {"radius": 2}, {"radius": 1})]))
        ''')
        self.assertEqual(got[0], {"notGiven": {"radius": 1, "reversed": False, "angle": 1.5, "extent": "length"}})  # a record since 28 Nov
        self.assertEqual(got[1], {})

    def test_every_core_feature_tool_says_what_was_not_given(self):
        e = entries()
        for name in ("pd_pad", "pd_pocket", "pd_revolution", "pd_groove", "pd_hole", "pd_fillet", "pd_chamfer", "pd_draft", "pd_thickness",
                     "pd_mirrored", "pd_linear_pattern", "pd_polar_pattern"):
            self.assertIn("=not_given(out, a, {", json.dumps(e[name]["answer"]), name)
            self.assertEqual(len(e[name]["answer"]["with"]), 7 if name in ("pd_fillet", "pd_chamfer") else 4, name)  # no must_change, no hint


class FreeCADsDefaults(unittest.TestCase):
    """FreeCAD 1.1 source (src/Mod/PartDesign/App): Hole DepthType Dimension,
    Depth 25, DrillPoint Angled, Threaded false; Pad Length 10; Pocket Length 5;
    LinearPattern Occurrences 2, Length 100; PolarPattern Occurrences 3."""

    def test_the_hole_sets_depth_and_drill_point_only_when_given(self):
        s = json.dumps(entries()["pd_hole"]["steps"])
        self.assertIn('{"set": {"f.DepthType": "ThroughAll"}, "when": "=depth == \'through\'"}', s)
        self.assertIn('"when": "=depth is not None and depth != \'through\'"', s)
        self.assertIn('"when": "=point is not None"', s)
        self.assertIn("a.get('threaded', False)", s)
        self.assertNotIn("a.get('depth', 'through')", s)
        self.assertNotIn("a.get('drillPoint', 'flat')", s)

    def test_a_length_or_a_count_left_out_is_freecads(self):
        e = entries()
        for name in ("pd_pad", "pd_pocket"):
            s = json.dumps(e[name]["steps"])
            self.assertIn('{"set": {"f.Length": "=float(L)"}, "when": "=L is not None"}', s, name)
            self.assertIn("L is not None and (not is_num(L) or L <= 0)", s, name)
        for name in ("pd_linear_pattern", "pd_polar_pattern"):
            s = json.dumps(e[name]["steps"])
            self.assertIn('{"set": {"f.Occurrences": "=n"}, "when": "=n is not None"}', s, name)
            self.assertIn("n < 1", s, name)  # FreeCAD's Occurrences takes 1
        self.assertIn("FreeCAD's default: 3", _cw(e["pd_polar_pattern"]))

    def test_two_sides_keeps_freecads_second_side(self):
        got = child('''
        from agentlink.families import feature as F
        f = types.SimpleNamespace(PropertiesList=["SideType", "Type2", "Type", "Length2"], SideType="One side", Type="ThroughAll", Type2="Length", Length2=5.0)
        F.set_sides(f, "two")
        g = types.SimpleNamespace(PropertiesList=["Refine"], Refine=True)
        F.pipe_options(g, {})
        print(json.dumps([f.SideType, f.Type2, f.Length2, g.Refine]))
        ''')
        self.assertEqual(got, ["Two sides", "Length", 5.0, True])

    def test_the_fit_words_are_mapped_in_the_card(self):
        d = _cw(entries()["pd_hole"])
        self.assertIn("fit: close|normal|loose is FreeCAD's ThreadFit Fine|Medium|Coarse for ISO metric", d)
        self.assertIn("LinearPattern also has Direction2 and Occurrences2", _cw(entries()["pd_linear_pattern"]))


class SketchAddDefaults(unittest.TestCase):
    def test_every_value_the_builder_filled_is_said(self):
        got = child('''
        from agentlink.families import sketch
        print(json.dumps([sketch.by_default({"kind": "arc", "center": [1, 1], "radius": 2}),
                          sketch.by_default({"kind": "polygon", "radius": 5, "construction": True}),
                          sketch.by_default({"kind": "bspline", "points": [], "interpolate": False}),
                          sketch.by_default({"kind": "line", "from": [0, 0], "to": [1, 1], "construction": False})]))
        ''')
        self.assertEqual(got[0], {"start": 0, "end": 90, "construction": False})
        self.assertEqual(got[1], {"center": [0, 0], "sides": 6, "rotation": 0})
        self.assertEqual(got[2], {"closed": False, "degree": 3, "construction": False})
        self.assertIsNone(got[3])


class BlindfoldGaps(unittest.TestCase):
    """Audit section 4: the fact that closes each gap is in the answer."""

    def test_a_placement_that_is_not_the_identity_is_said(self):
        got = child('''
        from agentlink import geometry as geo
        class Rot:
            Axis = types.SimpleNamespace(x=0.0, y=0.0, z=1.0); Angle = 1.5707963267948966
        class P:
            def __init__(s, ident): s.ident = ident; s.Base = types.SimpleNamespace(x=10.0, y=0.0, z=5.0); s.Rotation = Rot()
            def isIdentity(s): return s.ident
        print(json.dumps([geo.placement_fact(types.SimpleNamespace(Placement=P(True))), geo.placement_fact(types.SimpleNamespace(Placement=P(False))),
                          geo.placement_fact(types.SimpleNamespace())]))
        ''')
        self.assertEqual(got, [None, {"at": [10.0, 0.0, 5.0], "axis": [0.0, 0.0, 1.0], "angle": 90.0}, None])
        self.assertIn('out["bodyPlacement"] = placed', source("families", "pd_common.py"))
        self.assertIn('row["placement"] = placed', source("tools.py"))
        self.assertIn('row["bounds"] = {ax: [', source("tools.py"))  # session_state: where each body is (a record since 28 Nov)

    def test_the_new_body_says_its_placement_and_allow_compound(self):
        f = entries()["pd_body_new"]["answer"]["fields"]
        self.assertEqual(f["placement"], "=placement_json(b.Placement)")
        self.assertEqual(f["allowCompound"]["value"], "=get(b, 'AllowCompound')")
        self.assertEqual(f["next"], 'sketch_new { body, plane: "XY" }')  # decision 7: next stays

    def test_a_face_sketch_says_what_freecad_stores_and_who_set_the_offset(self):
        got = child('''
        from agentlink.families import sketch
        pad = types.SimpleNamespace(Label="Pad", Name="Pad")
        ao = types.SimpleNamespace(Base=types.SimpleNamespace(x=1.0, y=2.0, z=0.0), Rotation=types.SimpleNamespace(Axis=types.SimpleNamespace(x=0.0, y=0.0, z=1.0), Angle=0.0))
        sk = types.SimpleNamespace(PropertiesList=["AttachmentSupport"], AttachmentSupport=[(pad, ("Face3",))], MapMode="FlatFace", MapReversed=False, AttachmentOffset=ao)
        print(json.dumps([sketch.attachment(sk, "a face sketch is lined up with the world"), sketch.attachment(sk)]))
        ''')
        self.assertEqual(got[0], {"AttachmentSupport": "Pad: Face3", "MapMode": "FlatFace", "MapReversed": False,
                                  "AttachmentOffset": {"at": [1.0, 2.0, 0.0], "axis": [0.0, 0.0, 1.0], "angle": 0.0},
                                  "setBy": "Agent Link set AttachmentOffset (a face sketch is lined up with the world). FreeCAD's own value is the identity."})
        self.assertNotIn("setBy", got[1])
        self.assertIn('"attachment": "=attachment(sk, wrote)"', json.dumps(entries()["sketch_new"]["answer"]))

    def test_sketch_add_lists_the_constraints_a_shape_came_with(self):
        got = child('''
        from agentlink.families import sketch
        C = lambda t, a, ap, b=-2000, bp=0, v=None: types.SimpleNamespace(Type=t, Name="", First=a, FirstPos=ap, Second=b, SecondPos=bp, Third=-2000, ThirdPos=0, Driving=True, Value=v)
        sk = types.SimpleNamespace(Constraints=[C("Coincident", 0, 2, 1, 1), C("Horizontal", 0, 0), C("Radius", 4, 0, v=5.0)])
        print(json.dumps(sketch.con_list(sk, [0, 1, 2, 9])))
        ''')
        self.assertEqual(got, [{"id": 0, "type": "Coincident", "refs": [[0, 2], [1, 1]]}, {"id": 1, "type": "Horizontal", "refs": [[0, 0]]},
                               {"id": 2, "type": "Radius", "value": 5.0, "refs": [[4, 0]]}])
        self.assertIn('"constraintList": "=con_list(sk, cids)"', json.dumps(entries()["sketch_add"]["steps"]))

    def test_the_first_feature_says_which_side_of_its_sketch_it_went(self):
        got = child('''
        class V3:
            def __init__(s, x, y, z): s.x, s.y, s.z = x, y, z
        import FreeCAD
        FreeCAD.Vector = V3
        bb = types.SimpleNamespace(XMin=0.0, XMax=60.0, YMin=0.0, YMax=30.0, ZMin=-5.0, ZMax=0.0)
        shape = types.SimpleNamespace(BoundBox=bb, countElement=lambda k: 6, optimalBoundingBox=lambda a, b: types.SimpleNamespace(isValid=lambda: True, **bb.__dict__))
        pl = types.SimpleNamespace(Base=V3(0.0, 0.0, 0.0), Rotation=types.SimpleNamespace(multVec=lambda v: V3(0.0, 0.0, 1.0)))
        sk = types.SimpleNamespace(Label="Base", Placement=pl)
        feat = types.SimpleNamespace(Profile=(sk, []))
        print(json.dumps(pc.normal_span(feat, types.SimpleNamespace(Shape=shape))))
        ''')
        self.assertEqual(got, {"sketch": "Base", "span": [-5.0, 0.0]})

    def test_export_says_the_tolerance_used_and_the_unit(self):
        f = entries()["export"]["answer"]["fields"]
        self.assertEqual(f["tolerance"], {"when": "=tol is not None", "value": "=tol"})
        self.assertEqual(f["notGiven"]["value"], {"tolerance": 0.01})
        self.assertIn("fileUnit", f)
        self.assertEqual(f["toleranceUnit"], {"when": "=tol is not None", "value": "mm"})
        self.assertIn('return None if fmt in ("wrl", "x3d") else "mm"', source("families", "doc.py"))


class OpinionOut(unittest.TestCase):
    """Decision 4: no method advice, no guess of what was meant, in the
    cards, answers, refusals and guides. Decision 7: the likely next steps
    stay, with their ranking."""

    ADVICE = ("Prefer ", "prefer ", " should ", "Use it for ", "safer", "usually", "is a mistake", "If you meant", "when you are not sure", "Try a smaller", "try smaller")

    def test_no_advice_word_in_a_data_tools_card(self):
        for name, e in entries().items():
            for w in self.ADVICE:
                self.assertNotIn(w, _cw(e), f"{name}: {w!r}")

    def test_no_advice_in_the_core_code_texts(self):
        for path, gone in ((("families", "pd_common.py"), ("If you meant", "Try a smaller", "feature_remove {first", "Choose a face away")),
                           (("families", "sketch.py"), ("the shape moved; check it", "dimension and fix it")),
                           (("families", "feature.py"), ("bicycle runs, a rim",)),
                           (("once.py",), ("DOF_NOTE", "it pads as drawn")),
                           (("tools.py",), ("For new work, make a document", "printing, exporting and measuring are fine", "may need a smaller step",
                                            "Those calls answered ok", "whether a body is sound")),
                           (("protocol.py",), ("is expected to succeed",))):
            text = source(*path)
            for w in gone:
                self.assertNotIn(w, text, f"{path}: {w!r}")

    def test_the_design_guide_is_not_a_guide_of_the_hub(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "agentlink", "guides", "design.md")))
        self.assertTrue(os.path.exists(os.path.join(ROOT, "skills", "design-kickoff", "design.md")))
        with open(os.path.join(ROOT, "skills", "design-kickoff", "SKILL.md"), encoding="utf-8") as f:
            self.assertNotIn('topic: "design"', f.read())
        start = source("guides", "start.md")
        for gone in ("made and judged", "Don't assume a part is printed", "never send the same call again", "is the cause"):
            self.assertNotIn(gone, start, gone)
        feature = source("guides", "feature.md")
        for gone in ("FreeCAD's own advice", "usually a mistake", "what was meant", "Try a smaller value", "Keep one call under"):
            self.assertNotIn(gone, feature, gone)

    def test_the_next_steps_stay_and_their_ranking_is_as_it_was(self):
        with open(os.path.join(ROOT, "agentlink", "data", "nexthint.json"), encoding="utf-8") as f:
            text = f.read()
        hint = json.loads(text)["entries"]
        self.assertEqual(len(hint), 27)  # the rules, as the audit counted them
        for gone in ("fillets last", "on a stable plane", "in place first", "when done", "sound solid", "read its todo"):
            self.assertNotIn(gone, text, gone)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "agentlink", "options.py")))
        self.assertEqual(entries()["pd_body_new"]["answer"]["fields"]["next"], 'sketch_new { body, plane: "XY" }')

    def test_the_used_sketch_note_gives_facts_only(self):
        got = child('''
        feat = types.SimpleNamespace(Label="Pad", TypeId="PartDesign::Pad")
        def sk(label, users): return types.SimpleNamespace(Label=label, Name=label, TypeId="Sketcher::SketchObject", InList=users)
        base = sk("Base", [feat]); feat.Profile = (base, [])
        frees = [sk(f"Free{i}", []) for i in range(5)]
        body = types.SimpleNamespace(Label="Body", Group=[base] + frees)
        print(json.dumps(pc.used_sketch_note(base, body, "sketch_add")))
        ''')
        self.assertEqual(got, "Base is used by Pad, so this change also changes Pad. Body also has sketches that no feature uses: Free4, Free3, Free2 and 2 more.")


class HealthIsWhatFreeCADReports(unittest.TestCase):
    """Decision 5: no ok, no verdict, no todo, no advice; each fact with its
    source first; a limit that is used is said."""

    def test_no_grade_and_no_advice_is_left_in_the_health_code(self):
        h = source("health.py")
        for gone in ('{"ok"', '"verdict"', "todos", "practice", "fusehint", "HEALTH_TODOS", "history_undo", "inside out", "nothing red"):
            self.assertNotIn(gone, h, gone)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "agentlink", "practice.py")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "agentlink", "fusehint.py")))
        for src in ('rc["failing"] = ', 'sk_out.append(sketch_record(r))', 'shapes_out.append(shape_record(r))', 'measured.append({"parts"',
                    'addons.setdefault(_owner, [])', 'win["dialog"] = '):
            self.assertIn(src, h, src)

    def test_a_limit_that_is_used_is_said_with_the_true_reason(self):
        h = source("health.py")
        self.assertIn("(the pass tests {MAX_PAIRS} pairs at most)", h)
        self.assertIn("(out of time: the pass has {OVERLAP_S:g} s)", h)
        self.assertIn("(the free geometry is not named: {n_geo} geometries, over {SKETCH_GEO})", h)
        self.assertIn("more ({len(lists[key])} in all)", h)
        self.assertIn("(the check reads {MAX_SHAPES} at most)", h)

    def test_the_health_of_a_call_with_no_news(self):
        from agentlink import health

        self.assertEqual(health.nothing(), {"recompute": "ok", "fault": False})
        out = health.attach(types.SimpleNamespace(doc=None), "pd_pad", {"depth": 0}, {})
        self.assertEqual(out["health"], {"notRead": "no document", "fault": False})  # 27 Nov review: not read is not "no error"
        doc = types.SimpleNamespace(Name="D", Objects=[])
        out = health.attach(types.SimpleNamespace(doc=doc), "pd_pad", health.mark(types.SimpleNamespace(doc=doc)), {})
        self.assertEqual(out["health"], health.nothing())  # the state pass ran on every object: none failed

    def test_body_check_reads_freecads_checks_only(self):
        t = source("tools.py")
        body = t[t.index("    def body_check(self, a):"):t.index("    def check_rec(gap):")]
        for gone in ("soundness", "narrow", "shortEdges", "practice", "problems", '"ok"', "refine_todo"):
            self.assertNotIn(gone, body, gone)
        card = t[t.index('Tool("body_check", "'):t.index("s.body_check),")]
        self.assertNotIn("sound", card)
        self.assertNotIn("sliver", card)
        self.assertIn("checkGeometry", card)

    def test_the_fast_summary_has_no_grade(self):
        f = source("fastpath.py")
        for gone in ('"clean"', "not clean", "check ok"):
            self.assertNotIn(gone, f, gone)
        self.assertIn('"health: no fault in the readings of the calls"', f)

    def test_lines_refused_keeps_calls_with_a_recompute_error(self):
        from agentlink import batchrec

        got = {"results": [{"tool": "a", "ok": True, "result": {"health": {"recompute": "ok", "fault": False, "shapes": [{"object": "B", "valid": True, "closed": True, "solids": 2}]}}},
                           {"tool": "b", "ok": True, "result": {"health": {"recompute": {"failing": [{"object": "Pad", "error": "x"}]}, "fault": True}}},
                           {"tool": "c", "ok": False, "error": {"code": "failed", "message": "m"}}]}
        out = batchrec.to_reply(got, 0, "p", 1, lines="refused")
        self.assertEqual([r["i"] for r in out["results"]], [1, 2])
        self.assertFalse(hasattr(batchrec, "clean_verdict"))


class NoRepeatGuard(unittest.TestCase):
    """Decision 6: a changing call sent again runs again, and the server
    keeps no count of equal refusals."""

    def test_the_guards_and_their_texts_are_gone(self):
        from agentlink import protocol

        for name in ("again_before", "again_after", "again_clear", "repeat_words", "REPEAT_SAME", "REPEAT_HINT", "REPEAT_STOP", "AGAIN_WINDOW", "AGAIN_WORDS", "STOP_MARK"):
            self.assertFalse(hasattr(protocol, name), name)
        for path, gone in ((("protocol.py",), ("This call ran before", "If it runs again, it adds the same again", "No progress after", "the same refusal as before",
                                                "Refused the same way", "the server tells you to stop")),
                           (("tools.py",), ("ran_before", "_batch_kept", "do not send them again", "_repeat_quiet", "ranBefore"))):
            text = source(*path)
            for w in gone:
                self.assertNotIn(w, text, w)

    def test_the_same_changing_call_twice_runs_twice_and_a_refusal_is_not_counted(self):
        from agentlink.protocol import Server, Tool, ToolError

        ran = []

        def make(a):
            ran.append(dict(a))
            return {"made": len(ran)}

        def bad(a):
            raise ToolError("invalid_input", "length: mm, over 0.")

        schema = {"type": "object", "properties": {"length": {"type": "number"}}, "additionalProperties": False}
        srv = Server("t", "0", [Tool("probe_make", "Make.", schema, make, changes=False), Tool("probe_bad", "Refuse.", schema, bad, changes=False)])
        for _ in range(3):
            r = srv.call({"name": "probe_make", "arguments": {"length": 5}})
            self.assertFalse(r.get("isError"), r)
        self.assertEqual(len(ran), 3)
        said = []
        for _ in range(7):
            r = srv.call({"name": "probe_bad", "arguments": {"length": 0}})
            err = json.loads(r["content"][0]["text"])["error"]
            said.append((err["kind"], err["message"]))
            self.assertNotIn("repeat", err)
        self.assertEqual(len(set(said)), 1)  # the same refusal each time: no count, no stop
        self.assertEqual(said[0][0], "fixable")


class LimitsAndRewritesAreSaid(unittest.TestCase):
    """Decision 8: the behaviour stays, and the answer says it each time."""

    def test_an_input_name_read_as_another_is_said(self):
        from agentlink import protocol

        schema = {"type": "object", "properties": {"center": {"type": "array"}, "kind": {"type": "string"}}, "additionalProperties": False}
        a = {"kind": "circle", "centre": [1, 2]}
        said = protocol.check_input(schema, a, "sketch_add")
        self.assertEqual(a, {"kind": "circle", "center": [1, 2]})
        self.assertEqual(said, ["centre as center"])

    def test_a_cut_list_says_how_many_are_left_out(self):
        from agentlink import options

        opts = {"step": 3, "list": [{"n": i + 1, "tool": "pd_pad", "arguments": {"sketch": "S" * 30}} for i in range(4)]}
        line = options.line(opts, limit=100)
        self.assertTrue(line.endswith("; and 3 more (session_state gives them)"), line)
        self.assertEqual(options.line(opts, limit=1000).count("pd_pad"), 4)
        self.assertEqual(options._cut_value("a=" + "x" * 50, 10), "a=xxxxxxxx…")
        self.assertIn('out["edgesNotShown"] = n_edges - len(edges)', source("resultline.py"))
        self.assertIn('out["sideLimit"] = EDGES_SIDED', source("families", "pd_common.py"))
        self.assertIn('f" and {len(names) - PLANES_SHOWN} more"', source("families", "pd_common.py"))

    def test_a_box_that_is_not_exact_says_so(self):
        got = child('''
        from agentlink import geometry as geo
        class S:
            def __init__(s, n, exact=True): s.n, s.exact = n, exact; s.BoundBox = types.SimpleNamespace(XMin=-19.85, XMax=19.85, YMin=0, YMax=1, ZMin=0, ZMax=1, XLength=39.7, YLength=1, ZLength=1)
            def countElement(s, k): return s.n
            def optimalBoundingBox(s, a, b):
                if not s.exact: raise RuntimeError("no")
                return types.SimpleNamespace(XMin=-20.0, XMax=20.0, YMin=0, YMax=1, ZMin=0, ZMax=1, XLength=40.0, YLength=1, ZLength=1, isValid=lambda: True)
        small, big = S(6), S(601)
        print(json.dumps([geo.bound_box(small).XMin, geo.box_note(small), geo.bound_box(big).XMin, geo.box_note(big), geo.box_of(big).get("exact"), geo.box_of(small).get("exact"),
                          pc.exact_box(small)[:2]]))
        ''')
        self.assertEqual(got[0], -20.0)  # the exact box, not the box of the display mesh (-19.85)
        self.assertEqual(got[1], "")
        self.assertEqual(got[2], -19.85)
        self.assertTrue(got[3].startswith("The box is not exact: the shape has 601 faces, and the exact box is worked out for 600 at most."), got[3])
        self.assertEqual(got[4:6], [False, None])
        self.assertEqual(got[6], [-20.0, 20.0])


class MeasuredFactsCorrected(unittest.TestCase):
    """Decision 9: facts that were false in runs on the real FreeCAD."""

    def test_a_point_joined_to_the_origin_is_said_as_the_origin(self):
        got = child('''
        from agentlink.families import sketch
        sk = types.SimpleNamespace(Geometry=[])
        print(json.dumps([sketch.ref_words(sk, -1, 1), sketch.ref_words(sk, -2, 1), sketch.ref_words(sk, -1, 0), sketch.ref_words(sk, -2, 0), sketch.ref_words(sk, -1, 2)]))
        ''')
        self.assertEqual(got, ["the origin", "the origin", "the x axis", "the y axis", "the end of the x axis"])

    def test_a_refusal_example_has_only_the_named_tools_own_inputs(self):
        from agentlink import callshape

        self.assertNotIn("plane", callshape.old_words("arguments", "calls.0", "doc_new"))
        self.assertIn('{ "tool": "doc_new", <the inputs> }', callshape.old_words("arguments", "calls.0", "doc_new"))
        self.assertIn('{ "tool": "sketch_new", "plane": "XY" }', callshape.old_words("arguments", "calls.0", "sketch_new"))

    def test_doc_save_does_not_answer_touched_or_modified(self):
        e = entries()["doc_save"]
        self.assertNotIn("modified_state", json.dumps(e["answer"]))
        self.assertNotIn("touched", _cw(e))

    def test_the_used_sketch_note_says_when_the_body_is_not_recomputed(self):
        got = child('''
        feat = types.SimpleNamespace(Label="Pad", Name="Pad", TypeId="PartDesign::Pad", State=["Touched"])
        sk = types.SimpleNamespace(Label="Base", Name="Base", TypeId="Sketcher::SketchObject", InList=[feat], State=[], Document=types.SimpleNamespace(RecomputesFrozen=False))
        feat.Profile = (sk, [])
        body = types.SimpleNamespace(Label="Body", Name="Body", Group=[sk, feat], State=[], hasObject=lambda o: True)
        pc.body_of = lambda o: body
        mark = {"sketch": "Base", "body": "Body", "volume": 72.0, "box": (0, 1, 0, 1, 0, 1), "solids": 1}
        change = pc.used_change(sk, mark)
        print(json.dumps([change, pc.used_sketch_note(sk, body, "sketch_add", change)]))
        ''')
        self.assertEqual(got[0], "Body is not recomputed yet (its features are Touched), so its change is not measured here.")
        self.assertEqual(got[1], "Note: Base is the profile of Pad. " + got[0])


class HubFactsOfTheBrief(unittest.TestCase):
    """Decision 10: the facts that only the test brief gave are in the
    descriptions that every client gets (the static list's own, and the
    full ones)."""

    NOW = 'The answer ends with now: the names in each body as they are, by label. Example: "now": { "Body": ["Sketch→Pad"] }.'
    KIND = "A refusal has a kind: fixable, retry or stop. fixable: the message names what to change. retry: the error's words name a busy, locked or timed-out state."
    NOTOOL = "There is no sketch_rectangle, sketch_circle or pad tool: sketch_add takes kind, and the pad tool is pd_pad."

    def ste(self):
        with open(os.path.join(ROOT, "agentlink", "data", "ste.json"), encoding="utf-8") as f:
            d = json.load(f)
        return next(v for v in d.values() if isinstance(v, dict) and "batch" in v)

    def test_now_and_the_kinds_are_in_run_batch_and_fast(self):
        ste = self.ste()
        for name in ("run", "batch", "fast"):
            self.assertIn(self.NOW, ste[name], name)
        for name in ("run", "batch"):
            self.assertIn(self.KIND, ste[name], name)
        full = source("tools.py") + source("families", "fast.py")
        self.assertEqual(full.count(self.NOW.replace('"', '\\"')), 3)
        self.assertEqual(full.count(self.KIND), 2)

    def test_the_tool_names_that_are_not_there(self):
        self.assertIn(self.NOTOOL, self.ste()["tool_find"])
        self.assertIn(self.NOTOOL, source("tools.py"))
        from agentlink import runners

        names = set(runners.entries())
        self.assertFalse({"sketch_rectangle", "sketch_circle", "pad"} & names)
        self.assertTrue({"sketch_add", "pd_pad"} <= names)

    def test_each_feature_card_says_what_result_holds(self):
        said = "result says what changed and where: the material, the body before, each axis, the contact, the solids."
        e = entries()
        cards = [n for n in e if said in _cw(e[n])]
        self.assertEqual(len(cards), 14)
        for n in ("pd_pad", "pd_pocket", "pd_hole", "pd_fillet", "pd_linear_pattern", "pd_pipe"):
            self.assertIn(n, cards)

    def test_the_stop_after_equal_refusals_is_in_no_description(self):
        text = json.dumps(self.ste()) + source("tools.py") + source("families", "fast.py")
        self.assertNotIn("After 5 refusals", text)
        self.assertNotIn("says stop", text)


class SessionSteps(unittest.TestCase):
    """Decision 11: session_state has the part steps, the fact list of this
    session's calls of changing tools; get reads the parts by name."""

    def server(self):
        from agentlink.protocol import Server, Tool, ToolError

        schema = {"type": "object", "properties": {"name": {"type": "string"}, "length": {"type": "number"}}, "additionalProperties": False}

        def refuse(a):
            raise ToolError("invalid_input", "length: mm, over 0.")

        tools = [Tool("probe_body", "Make.", schema, lambda a: {"body": a.get("name") or "Body", "step": 1}, changes=True),
                 Tool("probe_pad", "Pad.", schema, lambda a: {"result": "Pad added material.", "feature": "Pad", "volumeChange": 6000.0, "step": 2}, changes=True),
                 Tool("probe_bad", "Refuse.", schema, refuse, changes=True),
                 Tool("probe_read", "Read.", schema, lambda a: {"bodies": []}, changes=False)]
        return Server("t", "0", tools)

    def test_steps_lists_a_made_object_a_feature_with_its_volume_change_and_a_refused_call(self):
        from agentlink import protocol

        srv = self.server()
        srv.call({"name": "probe_body", "arguments": {"name": "Plate"}})
        srv.call({"name": "probe_read", "arguments": {}})  # a read: no line
        srv.call({"name": "probe_pad", "arguments": {"length": 6}})
        srv.call({"name": "probe_bad", "arguments": {"length": 0}})
        srv.call({"name": "probe_pad", "arguments": {"length": 6}})  # the same call again runs again (decision 6): one more line
        got = protocol.steps_part(srv)
        self.assertEqual(got, {"steps": ["call 1: probe_body Plate: history step 1", "call 2: probe_read",
                                         "call 3: probe_pad Pad: volume change +6000 mm³; history step 2", "call 4: probe_bad: refused invalid_input",
                                         "call 5: probe_pad Pad: volume change +6000 mm³; history step 2"]})  # 27 Nov live proof: every call, reads too

    def test_the_newest_lines_that_fit_and_the_cut_off_notice(self):
        from agentlink import protocol

        srv = self.server()
        for i in range(30):
            srv.call({"name": "probe_body", "arguments": {"name": f"B{i}"}})
        got = protocol.steps_part(srv, limit=200)
        self.assertLess(len(got["steps"]), 30)
        self.assertEqual(got["steps"][-1], "call 30: probe_body B29: history step 1")  # the newest are kept
        n = 30 - len(got["steps"])
        self.assertEqual(got["stepsLeftOut"], f"{n} older lines are not shown: steps holds 200 characters at most. "
                                              "The batch records (batches/ in the session folder) hold the calls of each batch.")
        self.assertNotIn("stepsLeftOut", protocol.steps_part(srv))

    STATE = '''
        from agentlink import tools
        from agentlink.protocol import ToolError
        ses = types.SimpleNamespace(STATE_PARTS=tools.Session.STATE_PARTS, orientation=lambda: {"where": "hidden"},
                                    _state_all=lambda a, only=None: {k: v for k, v in {"document": "Part", "bodies": [{"name": "Body"}], "step": 1, "steps": ["1 pd_pad Pad: step 1"], "outDir": "/tmp/x"}.items() if only is None or k in only})
        def st(a):
            try:
                return tools.Session.session_state(ses, a)
            except ToolError as e:
                return ["refused", e.code, e.message]
        NAMES = ", ".join(tools.Session.STATE_PARTS)
'''

    def test_no_what_gives_all_parts_with_steps(self):
        got = child(self.STATE + '''
        print(json.dumps([list(st({})), st({"orient": True})]))
        ''')
        self.assertEqual(got[0], ["document", "bodies", "step", "steps", "outDir"])
        self.assertEqual(got[1], {"where": "hidden"})  # orient: true stays the short read, with no steps

    def test_what_as_a_name_and_as_a_list(self):
        got = child(self.STATE + '''
        print(json.dumps([st({"what": "steps"}), st({"what": ["steps", "bodies"]}), st({"what": ["bodies"]}), st({}), st({"what": ["next"]})]))
        ''')
        self.assertEqual(got[0], {"steps": ["1 pd_pad Pad: step 1"]})
        self.assertEqual(got[1], {"steps": ["1 pd_pad Pad: step 1"], "bodies": [{"name": "Body"}]})
        self.assertEqual(got[2], {"bodies": [{"name": "Body"}]})  # no steps key
        self.assertEqual(got[1], {k: got[3][k] for k in ("steps", "bodies")})  # one code path: the same data as the full answer
        self.assertEqual(got[4], {})  # a part that the document does not have now is left out

    def test_an_unknown_part_name_is_refused_with_the_names(self):
        got = child(self.STATE + '''
        print(json.dumps([st({"what": "volume"}), st({"what": ["steps", "volume"]}), st({"what": []}), st({"what": "steps", "orient": True}), NAMES]))
        ''')
        for r in got[:4]:
            self.assertEqual(r[:2], ["refused", "invalid_input"])
        self.assertEqual(got[0][2], "what: volume is not a part name. The part names: " + got[4] + ".")
        self.assertIn("steps", got[4])

    def test_the_descriptions_and_get_is_as_it_was(self):
        t = source("tools.py")
        orient = t[t.index("    def orientation(self):"):t.index("    STATE_PARTS = (")]
        self.assertNotIn("steps_part", orient)
        self.assertNotIn('"only"', t)
        with open(os.path.join(ROOT, "agentlink", "data", "ste.json"), encoding="utf-8") as f:
            ste = next(v for v in json.load(f).values() if isinstance(v, dict) and "session_state" in v)["session_state"]
        for said in ("The answer gives all parts: document, label, freecad, bodies, documents, step, steps, outDir, where, next, options.",
                     "what: a part name or a list of part names. The answer then has only those parts.", "orient: true does not give steps.",
                     "An unknown name is refused, and the refusal lists the names.",
                     "it starts again at initialize, and it stays when a document is closed."):
            self.assertIn(said, ste, said)
            self.assertIn(said, t, said)
        from agentlink import fastpath

        self.assertEqual(fastpath.ACTIVE, ("active.body", "active.sketch", "active.document", "selection", "bodies"))
        self.assertFalse(hasattr(fastpath, "SESSION_PARTS"))
        self.assertNotIn("steps", source("families", "fast.py").split('Tool("get"')[1].split("Tool(")[0])


class ReviewFixes(unittest.TestCase):
    """The independent review of 27 Nov (factsonly-REVIEW.md): one test for each fix."""

    def test_a1_fast_does_not_say_no_error_over_a_fault_or_an_unread_health(self):
        from agentlink import fastpath

        import json

        for h in ({"recompute": {"failingBefore": ["Pad001"]}, "fault": True}, {"notRead": "the health check did not run (KeyError: x)", "fault": True},
                  {"notRead": "no document", "fault": False}, {"recompute": "ok", "fault": True, "shapes": [{"object": "Body", "valid": False, "closed": True, "solids": 1}]},
                  {"recompute": "ok", "fault": True, "window": {"dialog": "Missing link"}}):
            self.assertEqual(json.loads(fastpath._health_words({"health": h})), h, h)
        self.assertIsNone(fastpath._health_words({"health": {"recompute": "ok", "fault": False, "shapes": [{"object": "Body", "valid": True, "closed": True, "solids": 1}]}}))
        run = types.SimpleNamespace(calls=1, made=[], health_bad=1)
        self.assertIn("health: a fault or no reading after 1 call (warnings)", fastpath._summary(run, True, 0.1, None, None))
        run.health_bad = 0
        self.assertTrue(fastpath._summary(run, True, 0.1, None, None).endswith("health: no fault in the readings of the calls"))
        self.assertNotIn("no recompute error", source("fastpath.py"))

    def test_a2_nothing_is_said_only_when_the_state_pass_ran(self):
        from agentlink import health

        got = health.check(types.SimpleNamespace(doc=None), "pd_pad", {"depth": 0})
        self.assertEqual(got, {"notRead": "no document", "fault": False})
        h = source("health.py")
        self.assertIn('rc["notRead"] = f"{len(objs)} objects, and the State flags are read for {MAX_OBJECTS} at most"', h)
        self.assertIn('return health.not_read("the build was not run")', source("tools.py"))

    def test_a3_wires_meet_counts_every_pair(self):
        got = child('''
        from agentlink.families import sketch
        names = [f"circle {i}" for i in range(5)]
        every = sketch.cross_words(names, lambda i, j: (0, 0), cap=None)
        cut = sketch.cross_words(names, lambda i, j: (0, 0))
        print(json.dumps([len(every), len(cut), cut[-1]]))
        ''')
        self.assertEqual(got, [10, 5, "and 6 more loops that meet"])
        src = source("families", "sketch.py")
        self.assertIn("return cross_words([name(w) for w in loops], meet, cap=None)", src)
        self.assertIn('out["wiresMeet"] = len(cross)  # every pair that meets', src)

    def test_a4_the_body_before_is_read_with_the_bodys_placement(self):
        got = child('''
        class Pl:
            def __init__(s, n, ident=False): s.n, s.ident = n, ident
            def isIdentity(s): return s.ident
            def multiply(s, o): return Pl(s.n + "*" + o.n)
            Base = types.SimpleNamespace(x=100.0, y=0.0, z=0.0); Rotation = types.SimpleNamespace(Axis=types.SimpleNamespace(x=0.0, y=0.0, z=1.0), Angle=0.0)
        class Shape:
            def __init__(s): s.Placement = Pl("feature")
            def isNull(s): return False
            def copy(s): return Shape()
        old = Shape()
        placed = pc.in_body_frame(types.SimpleNamespace(Placement=Pl("body")), old)
        same = pc.in_body_frame(types.SimpleNamespace(Placement=Pl("body", True)), old)
        print(json.dumps([placed.Placement.n, placed is old, old.Placement.n, same is old, pc.in_body_frame(types.SimpleNamespace(Placement=Pl("body")), None)]))
        ''')
        self.assertEqual(got, ["body*feature", False, "feature", True, None])
        pd = source("families", "pd_common.py")
        self.assertEqual(pd.count('in_body_frame(body, getattr(base, "Shape", None) if base is not None else None)'), 2)
        self.assertNotIn("the boxes here are the world's", pd)
        self.assertIn('out["containerPlacement"] = held', pd)

    def test_a5_a6_steps_mark_a_rollback_and_list_form_and_check_refusals(self):
        from agentlink import protocol
        from agentlink.protocol import Server, Tool

        schema = {"type": "object", "properties": {"name": {"type": "string"}}, "additionalProperties": True}
        srv = None

        def batch(a):
            srv.call({"name": "probe_make", "arguments": {"name": "A"}})
            protocol.note_refused(srv, "pad", "not_found", "a batch step, refused by its form")
            if a.get("rollback"):
                protocol.note_rolled_back(srv)
            return {"ran": 1}

        def nested(a):
            srv.call({"name": "probe_make", "arguments": {"name": "inner"}})  # a tool that calls a tool: one line, the client's
            return {"object": "outer"}

        srv = Server("t", "0", [Tool("probe_make", "Make.", schema, lambda a: {"body": a.get("name"), "step": 1}, changes=True),
                                Tool("batch", "Batch.", schema, batch, changes=True), Tool("probe_nested", "Nested.", schema, nested, changes=True)])
        srv.call({"name": "probe_make", "arguments": {"name": "Kept"}})
        srv.call({"name": "batch", "arguments": {"rollback": True}})
        srv.call({"name": "probe_nested", "arguments": {}})
        self.assertEqual(protocol.steps_part(srv)["steps"],
                         ["call 1: probe_make Kept: history step 1", "call 2: probe_make A: history step 1; taken back by rollback",
                          "call 3: pad: refused not_found (a batch step, refused by its form)", "call 4: probe_nested outer"])
        self.assertIn("note_refused(server, str(stop.tool or \"fast\"), stop.code", source("fastpath.py"))
        self.assertIn("note_rolled_back(getattr(s, \"server\", None), ROLLED_BACK if out.get(\"result\") == \"rolled_back\"", source("tools.py"))

    def test_a7_a_part_that_is_not_returned_is_not_built(self):
        got = child('''
        from agentlink import tools
        built = []
        def part(name, value):
            def f(*a, **k):
                built.append(name); return value
            return f
        ses = types.SimpleNamespace(STATE_PARTS=tools.Session.STATE_PARTS, steps=[1, 2], out_dir="/tmp/x", where="hidden",
                                    _hidden_state=part("hidden", {}), _steps_state=part("steps", {"steps": ["1 x"]}), _next_state=part("next", {}),
                                    _options_state=part("options", {"options": "o"}), _tools_state=part("toolsChanged", {"toolsChanged": "names"}),
                                    _extensions_state=part("leftOut", {}), _unattended_state=part("machine", {}), _front_state=part("front", {}))
        ses._state_parts = lambda a: tools.Session._state_parts(ses, a)
        ses._state_all = lambda a, only=None: tools.Session._state_all(ses, a, only)
        one = tools.Session.session_state(ses, {"what": "steps"})
        first = list(built)
        two = tools.Session.session_state(ses, {"what": ["toolsChanged", "step"]})
        print(json.dumps([one, first, two, built[len(first):]]))
        ''')
        self.assertEqual(got, [{"steps": ["1 x"]}, ["steps"], {"toolsChanged": "names", "step": 2}, ["toolsChanged"]])

    def test_a8_model_thread_goes_to_freecads_property_whatever_threaded_is(self):
        e = entries()["pd_hole"]
        s = json.dumps(e["steps"])
        self.assertIn('{"set": {"f.ModelThread": "=bool(a.modelThread)"}, "when": "=a.modelThread is not None and has_prop(f, \'ModelThread\')"}', s)
        self.assertNotIn("f.Threaded and has_prop(f, 'ModelThread')", s)
        a = json.dumps(e["answer"])
        self.assertIn("'modelThread': bool(get(f, 'ModelThread', False))", a)
        self.assertIn("'drillPoint': str(f.DrillPoint).lower()", a)  # read from the feature, not a constant
        self.assertIn("fit_word(f)", a)

    def test_a9_a10_a11_check_row_cut_said_and_refine_stated(self):
        from agentlink import fastpath

        row = fastpath.check_row("calls.0", "body_check", {"body": "B", "valid": True, "closed": True, "solids": 1, "volume": 5, "checkGeometry": {"errors": ["Edge3: BOPAlgo_InvalidCurveOnSurface"]}})
        self.assertEqual(row["checkGeometry"], {"errors": ["Edge3: BOPAlgo_InvalidCurveOnSurface"]})
        self.assertIs(row["closed"], True)
        t = source("tools.py")
        self.assertIn('s["checkGeometry"]["errorsInAll"] = len(said)', t)
        self.assertIn("return False, lines or [type(e).__name__]", source("geometry.py"))
        self.assertNotIn('"body_check": {"did": ["Checked {body}", "Checked the part"], "result": ["Sound if {ok=true}"', source("data", "activity.json"))
        self.assertIn('"Valid if {valid=true}"', source("data", "activity.json"))
        got = child('''
        pipe = types.SimpleNamespace(TypeId="PartDesign::AdditivePipe", PropertiesList=["Mode", "Transition", "Refine"], Mode="Standard", Transition="Transformed", Refine=True)
        prim = types.SimpleNamespace(TypeId="PartDesign::AdditiveBox", PropertiesList=["Length", "Refine"], Length=10.0, Refine=False)
        print(json.dumps([pc.stored_values(pipe), pc.stored_values(prim)]))
        ''')
        self.assertEqual(got, [{"Mode": "Standard", "Transition": "Transformed", "Refine": True}, {"Refine": False}])
        self.assertIn("'refine': get(f, 'Refine')", json.dumps(entries()["pd_pipe"]["answer"]))

    def test_b_the_listed_sentences_and_the_guessed_cause_are_gone(self):
        from agentlink import protocol

        e = entries()
        for name, gone in (("pd_boolean", "refuses a fuse or cut"), ("pd_primitive", "Use a primitive"), ("pd_primitive", "must overlap"),
                           ("sketch_attach", "Use it when"), ("part_from_mesh", "first use meshobj_decimate")):
            self.assertNotIn(gone, _cw(e[name]), name)
        steps = json.dumps({n: e[n]["steps"] for n in ("pd_pad", "pd_pocket", "pd_hole", "pd_revolution", "pd_groove")})
        for gone in ("pd_pad (or pd_primitive) first", "or two features", "make the hole by diameter, then feature_edit", "make it one-sided, then feature_edit"):
            self.assertNotIn(gone, steps, gone)
        self.assertEqual(protocol.KIND_WORDS["retry"], "")
        err = protocol.set_kind({"code": "busy", "message": "FreeCAD is busy with another call."})
        self.assertEqual((err["kind"], err["message"]), ("retry", "FreeCAD is busy with another call."))  # the raw error; no guessed cause
        self.assertNotIn("FreeCAD was busy or not ready", source("protocol.py").split("OLD_KIND_WORDS = (")[0])  # only in the list of old words that are taken out

    def test_c2_d2_a_parabolas_ends_are_said_and_a_held_recompute_is_said_as_held(self):
        got = child('''
        from agentlink.families import sketch
        feat = types.SimpleNamespace(Label="Pad", Name="Pad", TypeId="PartDesign::Pad", State=[])
        sk = types.SimpleNamespace(Label="Base", Name="Base", TypeId="Sketcher::SketchObject", InList=[feat], State=[], Document=types.SimpleNamespace(RecomputesFrozen=True))
        body = types.SimpleNamespace(Label="Body", Name="Body", Group=[sk, feat], State=[])
        pc.body_of = lambda o: body
        held = pc.used_change(sk, {"sketch": "Base", "body": "Body", "volume": 1.0, "box": (0, 1, 0, 1, 0, 1), "solids": 1})
        print(json.dumps([sketch.by_default({"kind": "parabola", "vertex": [0, 0], "focal": 3, "construction": False}), held]))
        ''')
        self.assertEqual(got[0], {"rotation": 0, "from": -6.0, "to": 6.0})
        self.assertEqual(got[1], 'The document\'s recompute is held (a batch with build: "end"), so the change of Body is not measured here.')


class LiveProof1127(unittest.TestCase):
    """The live proof on FreeCAD 1.1.3 of 27 Nov (live-proof-1127/RESULT.md)."""

    def test_doc_new_and_every_call_have_a_line_with_named_numbers(self):
        from agentlink import protocol
        from agentlink.protocol import Server, Tool

        schema = {"type": "object", "properties": {"name": {"type": "string"}}, "additionalProperties": True}
        srv = Server("t", "0", [Tool("doc_new", "New.", schema, lambda a: {"document": a.get("name"), "label": a.get("name")}, changes=False),
                                Tool("pd_body_new", "Body.", schema, lambda a: {"body": "Q", "step": 2}, changes=True)])
        srv.call({"name": "doc_new", "arguments": {"name": "Part"}})
        srv.call({"name": "pd_body_new", "arguments": {}})
        self.assertEqual(protocol.steps_part(srv)["steps"], ["call 1: doc_new Part", "call 2: pd_body_new Q: history step 2"])

    def test_sketch_frames_are_in_the_world(self):
        got = child('''
        from agentlink.families import sketch
        import FreeCAD
        class P:
            def __init__(s, x): s.x = x
            def multiply(s, o): return P(s.x + o.x)
            def inverse(s): return P(-s.x)
        sk = types.SimpleNamespace(Placement=P(0.0), getGlobalPlacement=lambda: P(100.0))
        bare = types.SimpleNamespace(Placement=P(5.0))
        print(json.dumps([sketch.world_pl(sk).x, sketch.holder_pl(sk).x, sketch.world_pl(bare).x, sketch.holder_pl(bare)]))
        ''')
        self.assertEqual(got, [100.0, 100.0, 5.0, None])
        tj = json.dumps(entries()["sketch_new"])
        for said in ("=axes(world_pl(sk))", "=frame(world_pl(sk))", "on_words(said, world_pl(sk))", "face_frame(sk.Placement, a.get('up'), holder_pl(sk))"):
            self.assertIn(said, tj, said)
        self.assertNotIn("=axes(sk.Placement)", json.dumps(entries()))
        self.assertIn("return orient.axes_rec(frame(pl))", source("families", "sketch.py"))

    def test_every_point_where_two_wires_meet(self):
        got = child('''
        from agentlink.families import sketch
        two = sketch.cross_words(["circle 0", "circle 1"], lambda i, j: [(4, 9.165), (4, -9.165)])
        one = sketch.cross_words(["circle 0", "circle 1"], lambda i, j: (10, 0))
        print(json.dumps([two, one]))
        ''')
        self.assertEqual(got, [["circle 0 meets circle 1 at (4, 9.165) and (4, -9.165)"], ["circle 0 meets circle 1 at (10, 0)"]])
        src = source("families", "sketch.py")
        self.assertIn("found += [v.Point for v in a.section(b).Vertexes]", src)
        for key in ('out["openEnds"] = gaps', 'out["branches"] = branches', 'out["meets"] = cross', 'st["moved"] = words'):
            self.assertIn(key, src, key)
        self.assertNotIn('out["todo"]', src)
        self.assertIn("meets: each pair of closed wires that meet, with every point where they meet.", _cw(entries()["sketch_state"]))

    def test_each_number_of_an_export_has_its_unit(self):
        got = child('''
        from agentlink.families import doc
        print(json.dumps(doc.verify_units({"triangles": 12, "size": [40.0, 40.0, 15.0], "sizeOfBodies": [40.0, 40.0, 15.0], "note": "x", "volumeDiff": 0.1, "other": 3})))
        ''')
        self.assertEqual(got, {"triangles": "count", "size": "mm", "sizeOfBodies": "mm", "volumeDiff": "mm³", "other": "not known"})
        f = entries()["export"]["answer"]["fields"]
        self.assertEqual(f["fileUnit"]["value"], "=unit_of(fmt)")
        self.assertEqual(f["verifyUnits"]["value"], "=verify_units(verify)")
        self.assertNotIn("unit", f)

    def test_no_advice_tail_in_refusals(self):
        from agentlink import protocol

        self.assertEqual((protocol.KIND_WORDS["fixable"], protocol.KIND_WORDS["stop"]), ("", ""))
        err = protocol.set_kind({"code": "invalid_input", "message": "what: nosuchpart is not a part name. The part names: a, b. Change what the error names and call again."})
        self.assertEqual(err["message"], "what: nosuchpart is not a part name. The part names: a, b.")
        for path, gone in ((("families", "pd_common.py"), "Use a name exactly as"), (("supervise.py",), "Try again in a while"),
                           (("coedit.py",), "then call again"), (("families", "unattended.py"), "then call again"), (("tools.py",), "correct the call and go on"),
                           (("cookbook.py",), "Correct the file and import it again"), (("guides", "model.md"), "and try again")):
            self.assertNotIn(gone, source(*path), gone)
        text = json.dumps(entries())
        for gone in ("Try again without fix", "check the points run round", "check the box or plane against that", "check the folder can be written",
                     "check the brackets", "check the delimiter", "check the operations", "else check the sizes", "call again for the next"):
            self.assertNotIn(gone, text, gone)


class Sentences(unittest.TestCase):
    def test_a_volume_change_is_its_rounded_number(self):
        self.assertIsNone(rl.material("pd_pad", 0.004))
        self.assertEqual(rl.material("pd_pad", 0.006), "added")
        self.assertEqual(rl.material("pd_pocket", -0.006), "removed")
        self.assertEqual(rl.body_change_text("Body", 72.0, 72.0), "After this call the volume of Body is 72 mm³: volume change 0 mm³.")

    def test_a_dress_up_says_edges_given_and_edges_changed(self):
        got = rl.dressup_result(12, {"size": 2.0}, [], 1, 1, changed=4)
        self.assertEqual(got, {"edgesGiven": 12, "edgesChanged": 4, "size": 2.0, "solidsWas": 1})

    def test_edges_changed_is_measured_on_the_new_shape(self):
        got = child('''
        class E:
            def __init__(s, mid): s.mid = mid; s.FirstParameter, s.LastParameter = 0.0, 1.0
            def valueAt(s, u): return s.mid
        class Skin:
            def distToShape(s, v): return (0.0 if v == "on" else 1.5, [], [])
        pc.Part = types.SimpleNamespace(Compound=lambda faces: Skin(), Vertex=lambda p: p)
        old = types.SimpleNamespace(Edges=[E("on"), E("off"), E("off")])
        new = types.SimpleNamespace(Faces=[])
        print(json.dumps([pc.edges_changed(old, new, ["Edge1", "Edge2", "Edge3"]), pc.edges_changed(old, new, ["Edge9"])]))
        ''')
        self.assertEqual(got, [2, None])


class LiveProofB3fc1d0(unittest.TestCase):
    """The live proof on b3fc1d0 (live-proof-1127/RESULT.md, section "b3fc1d0"), items a to f."""

    def test_a_part_container_recompute_and_doc_close_lines_carry_their_result(self):
        from agentlink.protocol import step_line

        # Records since 28 Nov (answers as records).
        self.assertEqual(step_line(54, "part_container", {"part": "Box1", "objects": ["BC"]}),
                         {"call": 54, "tool": "part_container", "object": "Box1", "objects": ["BC"]})
        self.assertEqual(step_line(102, "recompute", {"recomputed": 3, "ok": False, "errors": [{"object": "Fillet", "error": "x"}]}),
                         {"call": 102, "tool": "recompute", "recomputed": 3, "failing": ["Fillet"]})
        self.assertEqual(step_line(103, "recompute", {"recomputed": 1, "ok": True, "errors": []}),
                         {"call": 103, "tool": "recompute", "recomputed": 1, "failing": []})
        self.assertEqual(step_line(5, "doc_close", {"closed": ["lp2_fail"], "discarded": ["lp2_fail"], "open": ["AgentLink"]}),
                         {"call": 5, "tool": "doc_close", "closed": ["lp2_fail"], "discarded": ["lp2_fail"]})
        many = step_line(7, "part_container", {"part": "P", "objects": [f"B{i}" for i in range(8)]})
        self.assertEqual(many["objects"], [f"B{i}" for i in range(8)])
        self.assertEqual(step_line(8, "pd_pad", None, {"code": "invalid_input"}), {"call": 8, "tool": "pd_pad", "refused": "invalid_input"})

    def test_a_reads_and_doc_close_are_not_left_out_of_the_steps(self):
        src = source("protocol.py")
        body = src[src.index("def note_step"):src.index("def note_refused")]
        self.assertNotIn("changes", body)
        self.assertNotIn("doc_close", body)

    WORLD = '''
        from agentlink import geometry as geo
        from agentlink.families import sketch as sk_mod
        class Pl:
            def __init__(s, x=0.0): s.x = x
            def multiply(s, o): return Pl(s.x + o.x)
            def inverse(s): return Pl(-s.x)
            def isIdentity(s): return abs(s.x) < 1e-12
        class BB:
            def __init__(s, x0, x1): s.XMin, s.XMax, s.YMin, s.YMax, s.ZMin, s.ZMax = x0, x1, -10.0, 10.0, 10.0, 10.0
        class Shp:
            def __init__(s, x0, x1, pl=None): s.x0, s.x1, s.Placement = x0, x1, pl or Pl()
            def copy(s): return Shp(s.x0, s.x1, s.Placement)
            def getElement(s, sub): return Shp(s.x0, s.x1, s.Placement)
        class Obj:
            def __init__(s, shape, own, glob): s.Shape, s.Placement, s._g = shape, Pl(own), Pl(glob)
            def getGlobalPlacement(s): return s._g
        geo.bound_box = lambda sh: BB(sh.x0 + sh.Placement.x, sh.x1 + sh.Placement.x)
    '''

    def test_b_a_face_of_a_feature_in_a_placed_body_or_container_is_put_in_the_world(self):
        got = child(self.WORLD + '''
        pad = Obj(Shp(-10.0, 10.0), 0.0, 100.0)  # a feature of a body at x 100: its shape is in the body's frame
        body = Obj(Shp(-10.0, 10.0, Pl(100.0)), 100.0, 150.0)  # the body's shape has its Placement; a container adds 50
        free = Obj(Shp(-10.0, 10.0), 0.0, 0.0)
        w = lambda o, sh=None: geo.bound_box(geo.world_shape(o, sh))
        print(json.dumps([[w(pad).XMin, w(pad).XMax], [w(body).XMin, w(body).XMax], [w(free).XMin, w(free).XMax],
                          [w(pad, pad.Shape.getElement("Face6")).XMin]]))
        ''')
        self.assertEqual(got, [[90.0, 110.0], [140.0, 160.0], [-10.0, 10.0], [90.0]])

    def test_b_the_sketch_ranges_read_the_world_shape(self):
        src = source("families", "sketch.py")
        for fn in ("def body_ranges", "def face_ranges"):
            body = src[src.index(fn):src.index("\ndef ", src.index(fn) + 5)]
            self.assertIn("geo.world_shape(", body)
        pdc = source("families", "pd_common.py")
        for fn in ("def outside_words", "def normal_span", "def sketch_lies"):
            body = pdc[pdc.index(fn):pdc.index("\ndef ", pdc.index(fn) + 5)]
            self.assertIn("geo.world_shape(", body)

    def test_c_the_profiles_are_placed_as_the_region_is(self):
        pdc = source("families", "pd_common.py")
        body = pdc[pdc.index("def profile_results"):pdc.index("\ndef ", pdc.index("def profile_results") + 5)]
        self.assertIn("in_body_frame(body, f)", body)
        self.assertLess(body.index("in_body_frame(body, f)"), body.index("prism = "))

    def test_d_the_count_after_the_sides_is_of_the_faces_not_looked_at(self):
        old = (0, 9, 0, 4, 0, 2)
        cut = rl.feature_result("pd_pocket", -1, region=[(1, 2, 1, 2, 0, 2)], old_box=old, cut=True, faces=["+z at z 30"], faces_more=686, solids=1, solids_was=1)
        self.assertEqual(cut["opensNotLooked"], 686)
        add = rl.feature_result("pd_pad", 1, region=[(1, 2, 1, 2, 2, 3)], old_box=old, faces=["+z at z 5"], faces_more=7, touching=True, solids=1, solids_was=1)
        self.assertEqual(add["touches"], {"touching": True, "faces": ["+z at z 5"], "facesNotLooked": 7})

    def test_e_fit_not_given_says_freecads_stored_word(self):
        got = child('''
        from agentlink.families import feature
        print(json.dumps([feature.fit_word(types.SimpleNamespace(ThreadFit="Medium")), feature.fit_word(types.SimpleNamespace(ThreadFit="Fine"))]))
        ''')
        self.assertEqual(got, ["Medium", "Fine"])
        self.assertNotIn("FIT_WORDS", source("families", "feature.py"))

    def test_f_the_restart_words_and_their_kind_are_one_fact(self):
        from agentlink import window_watch as ww
        from agentlink.protocol import set_kind

        w = ww.Watch.__new__(ww.Watch)
        w.restart = {"why": "agentlink_update", "launched": True}
        waiting = w.waiting_words(45)
        lost = ww.Watch.lost_words({"why": "agentlink_update"})
        self.assertEqual(ww.words_kind(waiting), "retry")
        self.assertEqual(ww.words_kind(lost), "stop")
        for t in (waiting, lost):
            self.assertNotIn("Call it again", t)
            self.assertNotIn("Ask the person", t)
        e = set_kind({"code": "unavailable", "message": waiting}, ww.words_kind(waiting))
        self.assertEqual(e["kind"], "retry")
        self.assertNotIn("Do not call it again", e["message"])
        sup = source("supervise.py")
        self.assertIn('code="unavailable", kind=window_watch.words_kind(ready)', sup)
        self.assertNotIn("Call it again in a moment", sup)


class QaS1127e(unittest.TestCase):
    """Blind QA s1127e (qa-s1127e/QA-REPORT.md): the hub items."""

    def test_1_holes_is_0_when_nothing_was_drilled_and_the_spots_are_said(self):
        got = child('''
        out = {"volumeChange": 0.0}
        n0 = pc.holes_cut(2, out)
        out2 = {"volumeChange": -50.0, pc.NOT_CUT: 1}
        n1 = pc.holes_cut(3, out2)
        out3 = {"volumeChange": -50.0}
        n2 = pc.holes_cut(2, out3)
        print(json.dumps([n0, out, n1, out2, n2, out3]))
        ''')
        self.assertEqual(got, [0, {"volumeChange": 0.0, "holeSpots": 2}, 2, {"volumeChange": -50.0, "holeSpots": 3}, 2, {"volumeChange": -50.0}])
        self.assertIn("holes is the number of holes that removed material (0 when the volume change is 0 mm³)", _cw(entries()["pd_hole"]))

    def test_2_the_kind_follows_the_type_where_the_measured_change_has_the_other_sign(self):
        got = child('''
        feat = types.SimpleNamespace(TypeId="PartDesign::AdditivePipe", Label="Pipe")
        line = pc.sign_facts(feat, -678.58, {"material": "removed"})
        pad = types.SimpleNamespace(TypeId="PartDesign::Pad", Label="Pad")
        ok = pc.sign_facts(pad, 10.0, {"material": "added"})
        print(json.dumps([line, ok, pc.add_sub(feat), pc.add_sub(types.SimpleNamespace(TypeId="PartDesign::Hole")), pc.add_sub(types.SimpleNamespace(TypeId="PartDesign::Fillet"))]))
        ''')
        self.assertEqual(got[0], {"material": "removed", "featureKind": "additive"})
        self.assertEqual(got[1], {"material": "added"})
        self.assertEqual(got[2:], ["additive", "subtractive", None])

    def test_2_body_check_gives_the_gap_of_several_solids_as_a_record(self):
        self.assertEqual(rl.body_check_result(12.5), {"nearestGap": 12.5, "solidsTouch": False})
        self.assertEqual(rl.body_check_result(None), {})
        self.assertIn("checkGeometry", source("tools.py"))

    def test_3_a_hole_profile_says_the_volume_it_drilled_not_an_area_share(self):
        pdc = source("families", "pd_common.py")
        body = pdc[pdc.index("def profile_results"):pdc.index("\ndef ", pdc.index("def profile_results") + 5)]
        self.assertIn("hole_d is not None", body)
        self.assertIn("drilled {hit.Volume:.4g} mm³", body)
        self.assertLess(body.index("hole_d is not None"), body.index("whole = f.Area"))

    def test_4_part_boolean_lists_the_inputs_left_in_the_document(self):
        e = entries()["part_boolean"]
        self.assertIn('"inputsLeft"', json.dumps(e["answer"]))
        self.assertIn("With name, the result is a new object with that label, and body stays in the document as it was.", _cw(e))
        self.assertNotIn("Trap", _cw(e))
        steps = json.dumps(e["steps"])
        for w in ("Move a tool into the base", "may repair it", "Overlap the pieces clearly", "Check each with body_check"):
            self.assertNotIn(w, steps)
        self.assertIn("def inputs_left(members, result):", source("families", "model.py"))

    def test_5_a_given_diameter_that_was_not_set_is_said(self):
        got = child('''
        from agentlink.families import feature
        class G:
            def __init__(s, r): s.Radius = r
        G.__name__ = "Circle"
        sk = types.SimpleNamespace(Geometry=[G(3.0)], getConstruction=lambda i: False)
        f = types.SimpleNamespace(Diameter=6.6, ThreadSize="M6x1.0", Threaded=False)
        a = {"thread": "M6", "diameter": 5}
        f2 = types.SimpleNamespace(Diameter=6.0, ThreadSize="", Threaded=False)
        print(json.dumps([feature.hole_size_facts(a, f, sk), feature.hole_size_facts({"diameter": 6}, f2, sk)]))
        ''')
        self.assertEqual(got[0]["diameterNotSet"], "diameter 5 given and not set: with thread, ThreadSize M6x1.0 is set, and FreeCAD sets Diameter from it (clearance): Diameter 6.6")
        self.assertEqual(got[0]["circles"], "the sketch has circles of diameter 6; FreeCAD's Hole drills its Diameter 6.6 at each circle's centre")
        self.assertEqual(got[1], {})
        self.assertIn("hole_size_facts(a, f, sk)", json.dumps(entries()["pd_hole"]))

    def test_6_the_advice_clauses_are_gone(self):
        texts = json.dumps(entries()) + "".join(source(*p) for p in (("tools.py",), ("families", "pd_common.py"), ("families", "picks.py"), ("families", "model.py"),
                                                                     ("families", "techdraw.py"), ("sup_jobs.py",), ("gui_link.py",)))
        for w in ("pd_pad a closed sketch (or pd_primitive) first", "pd_body_new makes one", "Next: send a new batch", "Next: fix call",
                  "a mesh becomes a body with", "doc_save first", "or its link is off or still starting", "Trap:", "ask the person first",
                  "close the outline, or", "pd_pad a sketch first", "Next: wait for it", "Press Cancel"):
            self.assertNotIn(w, texts, w)

    def test_7_why_is_the_facts_the_rule_fits_by(self):
        from agentlink import nexthint

        for rid, rule in nexthint.load().items():
            for sg in rule["suggest"]:
                self.assertNotIn("why", sg, rid)
        got = nexthint.rank({"body": "sketch-open", "bodyName": "Body", "sketchName": "Path", "openWires": 1, "features": "some"})
        self.assertTrue(got)
        self.assertTrue(all(p["why"] == "sketch Path of Body has 1 open wire" for p in got), got)
        line = nexthint.words(got)
        self.assertEqual(line.count("(sketch Path of Body has 1 open wire)"), 1)
        for w in ("close the outline", "find ends that do not meet", "not closed yet", "nothing here yet", "a plain box"):
            self.assertNotIn(w, json.dumps(nexthint.load()))
        self.assertNotIn("new work in a document of its own", source("options.py"))

    def test_8_a_part_feature_is_not_called_a_body(self):
        got = child('''
        sh = types.SimpleNamespace(isNull=lambda: False, Solids=[1])
        box = types.SimpleNamespace(TypeId="Part::Box", Label="Box", Shape=sh, InList=[])
        doc = types.SimpleNamespace(Objects=[box])
        print(json.dumps([pc.part_solids_words(doc), pc.part_solids_words(types.SimpleNamespace(Objects=[]))]))
        ''')
        self.assertEqual(got, [" The document has Box (Part::Box): a Part feature, not a PartDesign Body.", ""])
        self.assertIn("It is a Part feature such as Part::Box or Part::Cylinder, not a PartDesign Body.", _cw(entries()["part_primitive"]))
        self.assertNotIn("as a body", _cw(entries()["part_primitive"]))

    def test_9_other_accuracy_items(self):
        from agentlink import timelimit

        # H5: where the minutes count from
        self.assertIn("since the first tool call", source("timelimit.py"))
        # H9: a pattern's Originals are stored
        pdc = source("families", "pd_common.py")
        for t in ("LinearPattern", "PolarPattern", "Mirrored", "MultiTransform"):
            self.assertIn(f'"PartDesign::{t}": ("Originals"', pdc)
        # H7: the solid a zero-change feature put, measured
        self.assertIn("tool_span(feat, body, sk, pl)", pdc)
        # H11: sketch_attach's face has its form
        self.assertIn("A face by its name is text in plane", entries()["sketch_attach"]["inputSchema"]["properties"]["face"]["description"])
        # H12: fast names the health fact
        self.assertIn("health_first", source("fastpath.py"))
        # H14: doc_new says the other documents of that label
        self.assertIn("same_label(d)", json.dumps(entries()["doc_new"]["answer"]))
        self.assertIn("def same_label(d, base=None):", source("families", "doc.py"))
        # H17: no mesh clause on a shape-less object
        self.assertNotIn("a mesh becomes a body", source("families", "picks.py"))


class QaS1127f(unittest.TestCase):
    """Blind QA of the retests s1127f (qa-s1127f/QA-REPORT.md): the hub items."""

    def test_1_part_boolean_lists_what_a_removed_body_held_and_removed_is_measured(self):
        e = entries()["part_boolean"]
        steps, ans = json.dumps(e["steps"]), json.dumps(e["answer"])
        self.assertIn("input_members([base] + tl)", steps)
        self.assertLess(steps.index("input_members([base] + tl)"), steps.index("=baked(base, res"))
        self.assertIn("removed_of(members)", ans)
        self.assertIn("inputs_left(members, o)", ans)
        self.assertNotIn("[t.Label for t in tl]\"}, \"inputsLeft", ans)
        self.assertIn("Objects that a removed PartDesign Body held can stay in the document.", _cw(e))
        src = source("families", "model.py")
        for f in ("def input_members(objs):", "def inputs_left(members, result):", "def removed_of(members):"):
            self.assertIn(f, src)

    def test_2_doc_close_gives_label_and_name(self):
        e = entries()["doc_close"]
        steps = json.dumps(e["steps"])
        self.assertIn("d.Label + ' (' + d.Name + ')' for d in picked if unsaved(d)", steps)
        self.assertIn('"closed": "=d.Label + \' (\' + d.Name + \')\'"', steps)
        self.assertNotIn("First use doc_save", _cw(e))
        self.assertIn("closed, discarded and the refusal give each document as label (name).", _cw(e))

    def test_3_pattern_copies_are_placed_as_freecad_places_them(self):
        got = child('''
        from agentlink.families import feature
        FreeCAD = sys.modules["FreeCAD"]
        V = FreeCAD.Vector
        line = types.SimpleNamespace(TypeId="App::Line", Placement=FreeCAD.Placement(V(0, 0, 0), FreeCAD.Rotation()))
        lin = types.SimpleNamespace(TypeId="PartDesign::LinearPattern", Occurrences=3, Reversed=False, Mode="Extent", Length=20.0, Offset=0.0,
                                    Occurrences2=1, Direction=(line, [""]))
        pls = feature.pattern_copies(lin)
        one = types.SimpleNamespace(TypeId="PartDesign::LinearPattern", Occurrences=1)
        other = types.SimpleNamespace(TypeId="PartDesign::Mirrored", Occurrences=2)
        print(json.dumps([[list(p.Base) for p in pls], feature.pattern_copies(one), feature.pattern_copies(other)]))
        ''')
        self.assertEqual(got[0], [[10.0, 0.0, 0.0], [20.0, 0.0, 0.0]])
        self.assertEqual(got[1:], [[], None])
        for n in ("pd_polar_pattern", "pd_linear_pattern"):
            self.assertIn("pattern_facts(b, f)", json.dumps(entries()[n]["answer"]))
        src = source("families", "feature.py")
        self.assertIn("360.0 / n if abs(ang - 360.0) < 1e-9 else ang / (n - 1)", src)  # FeaturePolarPattern.cpp's step
        self.assertIn('"copiesChanging": changed, "pairsSharingVolume": pairs', src)

    def test_4_the_advice_and_the_body_key_are_gone(self):
        texts = json.dumps(entries()) + source("families", "pd_common.py")
        for w in ("First use doc_save", "sketch_new makes one", "pd_pad something first", "pd_pad or pd_revolution first"):
            self.assertNotIn(w, texts, w)
        self.assertIn('FEATURE_KEY = {"part_primitive": "feature"}', source("families", "model.py"))
        self.assertIn("Answer: feature (the Part feature's label)", _cw(entries()["part_primitive"]))

    def test_5_check_geometry_stays_in_health(self):
        # 28 Nov: the finding is the answer's health facts; the result record does not say it again
        self.assertNotIn("def check_in_result", source("families", "pd_common.py"))

    def test_5_a_pipe_wire_failure_says_each_inputs_wires_and_a_fill_names_the_cut(self):
        pdc = source("families", "pd_common.py")
        self.assertIn("fact = pipe_wire_words(feat)", pdc)
        self.assertIn("Part.sortEdges(list(shape.Edges))", pdc)
        self.assertIn("fills = fills_cuts(feat, body, reg, tol)", pdc)
        got = child('''
        class R:
            def common(s, t): return types.SimpleNamespace(Volume=50.0 if t == "cut" else 0.0)
        pk = types.SimpleNamespace(TypeId="PartDesign::Pocket", Label="Pocket", AddSubShape=types.SimpleNamespace(isNull=lambda: False))
        pad = types.SimpleNamespace(TypeId="PartDesign::Pad", Label="Pad")
        me = types.SimpleNamespace(TypeId="PartDesign::Mirrored", Label="Mirrored")
        body = types.SimpleNamespace(Group=[pad, pk, me])
        pc.in_body_frame = lambda b, t: "cut"
        print(json.dumps(pc.fills_cuts(me, body, R())))
        ''')
        self.assertEqual(got, "the new material fills 50 mm³ of the cut of Pocket")


if __name__ == "__main__":
    unittest.main()
