# SPDX-License-Identifier: LGPL-2.1-or-later
# Which sketch a tool takes when none is named (local fixes, 23 Nov,
# decision 4; rule R2: no other guess): (1) the sketch open in edit in the
# window, (2) the sketch this session's agent made last, (3) the only one,
# else a refusal that lists them, unused first and newest first, each
# marked. A sketch taken so is said in the answer's filled. D-b: a change to
# the geometry of a sketch that a feature uses, while its body has an unused
# sketch, gets the sketchNote.
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from test_hubfix2 import in_a_process  # noqa: E402
from test_hubfix4 import SETUP  # noqa: E402

# Body: Sketch→Pad, Sketch 2→Pad 2 (Name Pad001), Sketch 3 and Sketch 4 not used.
DOC = SETUP + '''
    import types
    from agentlink.families import pd_common as pc
    from agentlink.protocol import ToolError
    D = new("Part")
    def mk(name, label, type_id, **kw):
        o = Obj(D, name)
        o.Label, o.TypeId = label, type_id
        o.__dict__.update(kw)
        D.Objects.append(o)
        return o
    class Body(Obj):
        TypeId = "PartDesign::Body"
        def hasObject(self, o):
            return any(o is x for x in self.Group)
    body = Body(D, "Body")
    D.Objects.append(body)
    sk1 = mk("Sketch", "Sketch", "Sketcher::SketchObject")
    pad1 = mk("Pad", "Pad", "PartDesign::Pad")
    sk2 = mk("Sketch001", "Sketch 2", "Sketcher::SketchObject")
    pad2 = mk("Pad001", "Pad 2", "PartDesign::Pad")
    sk3 = mk("Sketch002", "Sketch 3", "Sketcher::SketchObject")
    sk4 = mk("Sketch003", "Sketch 4", "Sketcher::SketchObject")
    body.Group = [sk1, pad1, sk2, pad2, sk3, sk4]
    sk1.InList, sk2.InList = [pad1, body], [pad2, body]
    sk3.InList, sk4.InList = [body], [body]
    for o in body.Group:
        o.getParentGeoFeatureGroup = lambda b=body: b
    def refuse(f):
        try:
            f()
        except ToolError as e:
            return [e.code, e.message]
        return None
'''

# A server on the stand-in FreeCAD with probes that take a sketch as the
# sketch tools do (pc.sketch_of with the session).
SERVER = DOC + '''
    from agentlink import tools
    from agentlink.protocol import Tool
    import tempfile
    s = tools.Session(doc=D, out_dir=tempfile.mkdtemp(prefix="agentlink-1124-"))
    srv = tools.build_server(s, lean=False)
    s.server = srv
    SCH = {"type": "object", "properties": {"sketch": {"type": "string"}}, "additionalProperties": False}
    def take(a):
        sk = pc.sketch_of(s.doc, a.get("sketch"), body, s)
        return {"sketch": sk.Label}
    srv.tools["probe_take"] = Tool("probe_take", "Take a sketch.", SCH, take, changes=False)
    srv.tools["sketch_add"] = Tool("sketch_add", "Add geometry.", SCH, take, changes=False, group="sketch")
    srv.tools["sketch_state"] = Tool("sketch_state", "Read a sketch.", SCH, take, changes=False, group="sketch")
    def call(name, args):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
        return [r.get("isError", False), json.loads(r["content"][0]["text"])]
'''


class TheRule(unittest.TestCase):
    def test_in_edit_then_made_last_then_refusal(self):
        got = in_a_process(DOC + '''
    out = {}
    s = types.SimpleNamespace(by="agent", filled_now=[])
    # (3) nothing in edit, nothing made: the ordered list
    out["refused"] = refuse(lambda: pc.sketch_of(D, None, body, s))
    out["refusedNoBody"] = refuse(lambda: pc.sketch_of(D, None, None, s))
    # (2) the sketch this session's agent made last
    pc.note_made_sketch(s, sk2)
    out["made"] = pc.sketch_of(D, None, body, s).Label
    # (1) the sketch open in edit wins
    fc.GuiUp = True
    sys.modules["FreeCADGui"] = types.SimpleNamespace(ActiveDocument=types.SimpleNamespace(getInEdit=lambda: types.SimpleNamespace(Object=sk3)))
    out["edit"] = pc.sketch_of(D, None, body, s).Label
    # a sketch in edit of another document is not this one's
    other = new("Other")
    sk3.Document = other
    out["editOther"] = pc.sketch_of(D, None, body, s).Label
    sk3.Document = D
    out["filled"] = list(s.filled_now)
    # the person's own sketch_new is not the agent's
    p = types.SimpleNamespace(by="person", filled_now=[])
    pc.note_made_sketch(p, sk4)
    out["person"] = getattr(p, "made_sketch", None)
    # a named sketch is taken as named, with nothing filled
    s.filled_now = []
    out["named"] = pc.sketch_of(D, "sketch 4", body, s).Label
    out["namedFilled"] = s.filled_now
    # no session (a path, another field): no default but the only one
    fc.GuiUp = False
    out["noSession"] = refuse(lambda: pc.sketch_of(D, None, body))
    one = Body(D, "Body001")
    one.Label = "Body 2"
    only = mk("Sketch004", "Sketch 5", "Sketcher::SketchObject")
    one.Group = [only]
    s.filled_now = []
    out["only"] = pc.sketch_of(D, None, one, s).Label
    out["onlyFilled"] = s.filled_now
    empty = Body(D, "Body002")
    empty.Label, empty.Group = "Body 3", []
    out["none"] = refuse(lambda: pc.sketch_of(D, None, empty, s))
    # a dry reading (needs.py) takes the same sketch and notes nothing
    from agentlink import needs
    s.filled_now, s.sketch_now = [], None
    needs.DRY[0] += 1
    out["dry"] = pc.sketch_of(D, None, one, s).Label
    needs.DRY[0] -= 1
    out["dryNoted"] = [s.filled_now, s.sketch_now]
    print(json.dumps(out))
''')
        self.assertEqual(got["refused"], ["invalid_input", "sketch: say which. No sketch is open in edit, and you made none here. The sketches in Body, "
                                                           "unused first and newest first: Sketch 4 (not used), Sketch 3 (not used), "
                                                           "Sketch 2 (used by Pad 2), Sketch (used by Pad)."])
        self.assertIn("The sketches, unused first", got["refusedNoBody"][1])
        self.assertEqual(got["made"], "Sketch 2")
        self.assertEqual(got["edit"], "Sketch 3")
        self.assertEqual(got["editOther"], "Sketch 2")
        self.assertEqual(got["filled"], ["sketch=Sketch 2 (you made it last)", "sketch=Sketch 3 (open in edit in the window)",
                                         "sketch=Sketch 2 (you made it last)"])
        self.assertIsNone(got["person"])
        self.assertEqual((got["named"], got["namedFilled"]), ("Sketch 4", []))
        self.assertEqual(got["noSession"][1], "sketch: say which. The sketches in Body, unused first and newest first: Sketch 4 (not used), "
                                              "Sketch 3 (not used), Sketch 2 (used by Pad 2), Sketch (used by Pad).")
        self.assertEqual(got["only"], "Sketch 5")
        self.assertEqual(got["onlyFilled"], ["sketch=Sketch 5 (the only sketch in Body 2)"])
        self.assertEqual(got["none"], ["invalid_input", "sketch: there is no sketch in Body 3 yet. sketch_new makes one."])
        self.assertEqual((got["dry"], got["dryNoted"]), ("Sketch 5", [[], None]))

    def test_sketch_of_stays_a_reader_for_dry_readings(self):
        with open(os.path.join(ROOT, "agentlink", "data", "readers.json"), encoding="utf-8") as f:
            fams = json.load(f)
        fams = fams["entries"]
        for fam in ("sketch", "sketch_more", "feature", "feature_more"):
            self.assertIn("sketch_of", fams[fam]["readers"], fam)
        self.assertIn("broken", fams["sketch"]["readers"])
        self.assertIn("status_words", fams["sketch"]["readers"])

    def test_sketch_new_records_and_the_families_pass_the_session(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            steps = json.load(f)["entries"]["sketch_new"]["steps"]
        self.assertEqual(steps[-1], {"do": "=note_sketch(sk, a.get('name'))"})
        for fam in ("sketch", "sketch_more", "feature", "feature_more"):
            with open(os.path.join(ROOT, "agentlink", "families", fam + ".py"), encoding="utf-8") as f:
                self.assertIn("pc.sketch_of(doc(), ref, b, s)" if fam != "sketch_more" else "pc.sketch_of(doc(), ref, None, s)", f.read(), fam)


class FilledInTheAnswer(unittest.TestCase):
    def test_the_answer_says_which_sketch_was_taken(self):
        got = in_a_process(SERVER + '''
    out = {}
    out["refused"] = call("probe_take", {})
    pc.note_made_sketch(s, sk3)
    out["made"] = call("probe_take", {})
    out["named"] = call("probe_take", {"sketch": "Sketch 4"})
    out["batch"] = call("batch", {"calls": [{"tool": "probe_take"}]})
    print(json.dumps(out))
''')
        err, r = got["refused"]
        self.assertTrue(err)
        self.assertIn("unused first and newest first: Sketch 4 (not used)", r["error"]["message"])
        err, r = got["made"]
        self.assertFalse(err)
        self.assertEqual((r["sketch"], r["filled"]), ("Sketch 3", ["probe_take.sketch=Sketch 3 (you made it last)"]))
        self.assertNotIn("filled", got["named"][1])
        row = got["batch"][1]["results"][0]
        self.assertEqual(row["result"]["filled"], ["probe_take.sketch=Sketch 3 (you made it last)"])


class UsedSketchNote(unittest.TestCase):
    def test_a_change_to_a_used_sketch_while_an_unused_one_waits(self):
        got = in_a_process(SERVER + '''
    out = {}
    out["used"] = call("sketch_add", {"sketch": "Sketch 2"})
    out["unused"] = call("sketch_add", {"sketch": "Sketch 3"})
    out["read"] = call("sketch_state", {"sketch": "Sketch 2"})
    sk3.InList, sk4.InList = [mk("Pocket", "Pocket", "PartDesign::Pocket"), body], [mk("Pocket001", "Pocket 2", "PartDesign::Pocket"), body]
    out["allUsed"] = call("sketch_add", {"sketch": "Sketch 2"})
    pad2.Profile = (sk2, [""])
    out["profile"] = call("sketch_add", {"sketch": "Sketch 2"})
    out["profileRead"] = call("sketch_state", {"sketch": "Sketch 2"})
    print(json.dumps(out))
''')
        err, r = got["used"]
        self.assertFalse(err)
        self.assertEqual(r["sketchNote"], "Sketch 2 is used by Pad 2, so this change also changes Pad 2. Body also has a sketch that is not used: "
                                          "Sketch 4, Sketch 3. If you meant Sketch 4, use history_undo, then give sketch: \"Sketch 4\".")
        self.assertNotIn("sketchNote", got["unused"][1])
        self.assertNotIn("sketchNote", got["read"][1])  # a read changes nothing
        # Blind QA, 24 Nov: holes went into a Pad's own sketch, then that sketch was pocketed. Every used sketch gets the note.
        self.assertEqual(got["allUsed"][1]["sketchNote"], "Note: Sketch 2 is used by Pad 2; adding to it changes Pad 2.")
        self.assertEqual(got["profile"][1]["sketchNote"], "Note: Sketch 2 is the profile of Pad 2; adding to it changes Pad 2.")
        self.assertNotIn("sketchNote", got["profileRead"][1])


if __name__ == "__main__":
    unittest.main()
