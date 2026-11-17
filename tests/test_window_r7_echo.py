# SPDX-License-Identifier: LGPL-2.1-or-later
# Window round 7 (the echo's words and views): every read says its own words
# with a value; words that claimed what was not done; the heavy-job line in
# the status bar; a trajectory framed on its waypoints with labels that do
# not overlap; fea_hold framed on its faces; a strength result only for the
# study in hand. Without FreeCAD: plain functions, and stand-ins for the echo.
import ast
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agentlink import activity, echo, keep  # noqa: E402
from test_echo_hold import Replay as _Replay, Tool, reply  # noqa: E402


def src(*parts):
    with open(os.path.join(HERE, "..", *parts), encoding="utf-8") as f:
        return f.read()


class ReadValues(unittest.TestCase):
    """Item 1: a read's words carry a value from its answer."""

    def words(self, name, body, args=None):
        return echo.read_words(activity.did(name, args or {}, body), activity.outcome(name, True, body, args or {}))

    def test_each_read_has_a_value(self):
        cases = [
            ("session_state", {"bodies": [{}, {}], "step": 14}, "Read the session: 2 bodies, step 14"),
            ("guide_read", {"topic": "bim", "text": "# BIM\n## A\n## B\n## C\n"}, {"topic": "bim"}, "Read the bim guide: 3 sections"),
            ("guide_read", {"guides": [{}] * 20}, "Read the guide index: 20 guides"),
            ("tool_groups", {"groups": [{"on": True}, {"on": False}], "listed": 40}, "Read the tool groups: 2 groups, 1 on, 40 tools listed"),
            ("tool_groups", {"tools": [{}, {}, {}]}, "Read the tool groups: 3 tools found"),
            ("usage_report", {"calls": 12, "tokens": 3400, "errors": 4}, "Read the usage report: 12 calls, 3400 tokens, 4 refusals"),
            ("report_read", {"found": True, "count": 120, "problems": 0}, "Read the Report view: 0 problems, 120 lines"),
            ("view_maps", {"maps": [{}] * 4, "layers": [{}]}, "Made a colour map: 4 maps, 1 layer"),
            ("snapshot_list", {"shots": []}, "Listed your screenshots: no screenshots"),
            ("note_list", {"notes": [{}]}, "Read the notes: 1 note"),
            ("job_status", {"job": "job-1", "tool": "scan_qa", "status": "done", "took": 12.5}, "scan_qa done in 12.5 s"),
            ("window_snapshot", {"path": "~/AgentLink/a/w.png", "width": 1400, "height": 852}, "1400 x 852 px, w.png"),
            ("crash_collect", {"note": "No recovery files from another FreeCAD and no new crash reports."}, "nothing new"),
        ]
        for case in cases:
            name, body, want = case[0], case[1], case[-1]
            args = case[2] if len(case) == 4 else {}
            got = self.words(name, body, args)
            self.assertIn(want, got, name)
            self.assertNotIn("AgentLink/", got)

    def test_view_render_with_no_data_says_so(self):
        got = self.words("view_render", {"empty": "The stress map has no data: no fea_solve in this session. Run fea_solve first.", "map": "stress"})
        self.assertIn("nothing drawn: the stress map has no data", got)

    def test_a_picture_with_no_size_still_says_wrote(self):
        self.assertEqual(activity.outcome("view_render", True, {"path": "~/AgentLink/shots/a.png"}), "Wrote a.png")


class WrongWords(unittest.TestCase):
    """Item 2: words that claimed what was not done."""

    def test_selection_read_is_not_a_clear(self):
        self.assertEqual(activity.did("selection", {"clear": False}, {"selected": ["Bracket"]}), "Read the selection: Bracket")
        self.assertEqual(activity.did("selection", {}, {"selected": []}), "Read the selection: nothing selected")
        self.assertEqual(activity.did("selection", {"clear": True}, {}), "Cleared the selection")
        self.assertEqual(activity.did("selection", {"objects": ["Bracket"]}, {}), "Selected Bracket")

    def test_show_names_what_was_done_and_what_was_not_found(self):
        got = activity.did("show", {"objects": ["Bracket", "Ghost"]}, {"visible": ["Bracket"], "unknown": ["Ghost"]})
        self.assertEqual(got, "Showed Bracket; Ghost not found")
        self.assertEqual(activity.did("show", {"objects": ["Bracket"], "visible": False}, {"hidden": ["Bracket"]}), "Hid Bracket")
        self.assertEqual(activity.did("show", {"objects": ["Ghost"]}, {"visible": [], "unknown": ["Ghost"]}), "Showed nothing; Ghost not found")

    def test_note_done_undone(self):
        self.assertEqual(activity.did("note_done", {"id": 1, "done": False}, {}), "Marked a note open again")
        self.assertEqual(activity.did("note_done", {"id": 1}, {}), "Marked a note done")

    def test_a_dry_run_did_not_tidy(self):
        self.assertEqual(activity.did("outputs_clean", {"dry_run": True}, {"dryRun": True}), "Listed what would go from the output folder")
        self.assertEqual(activity.did("outputs_clean", {"dry_run": False}, {"dryRun": False}), "Tidied the output folder")

    def test_reads_never_say_wrote(self):
        self.assertEqual(activity.outcome("pref_get", True, {"path": "BaseApp/Preferences/View", "values": {"a": {}}, "groups": []}), "1 value, 0 groups")
        self.assertEqual(activity.outcome("pref_get", True, {"path": "x", "name": "Probe", "type": "Integer", "value": 3}), "Probe = 3")
        got = activity.outcome("ifc_open", True, {"path": "~/models/house.ifc", "schema": "IFC4", "storeys": [{}, {}], "elements": 40})
        self.assertEqual(got, "IFC4, 2 storeys, 40 elements")
        self.assertEqual(activity.call_value("meshobj_import", {"file": "~/models/a.stl"}), "a.stl")
        self.assertEqual(activity.call_value("meshobj_export", {"file": "~/models/a.stl"}), "wrote a.stl")


class ChangeValues(unittest.TestCase):
    """Item 7: part_, mesh and robot changes with their figures."""

    def test_values(self):
        cases = [
            ("part_split", {"object": "Halves", "pieces": 2, "solids": [{"volume": 45819.383}, {"volume": 45819.383}], "bodies": ["Halves 1", "Halves 2"]},
             "2 pieces, 45819 mm³ each"),
            ("compound_explode", {"group": "Lattice parts", "pieces": [{"name": "a", "volume": 10}, {"name": "b", "volume": 12}]},
             "2 pieces in Lattice parts, 10, 12 mm³"),
            ("part_defeature", {"facesBefore": 7, "facesAfter": 6, "volumeBefore_mm3": 11214.6, "volume_mm3": 12000}, "7 → 6 faces, 11215 → 12000 mm³"),
            ("meshobj_decimate", {"reduced": "10596 → 5298 triangles", "volume": 4181, "facets": 10596}, "10596 → 5298 triangles"),
            ("meshobj_repair", {"mesh": "Rim", "changed": False, "volume": 500}, "unchanged"),
            ("robot_trajectory", {"trajectory": "Turned", "waypoints": 2, "length_mm": 200.0}, "2 waypoints, 200 mm"),
            ("robot_export", {"path": "~/AgentLink/stroke.src", "lines": 23, "moves": 2}, "2 moves, 23 lines"),
        ]
        for name, body, want in cases:
            self.assertEqual(activity.call_value(name, body), want, name)
            self.assertEqual(echo.change_words("Did it", body, name), "Did it: " + want, name)

    def test_robot_trajectory_words(self):
        self.assertEqual(activity.did("robot_trajectory", {"op": "dress", "trajectory": "Stroke", "ypr": [10, 0, 0], "name": "Turned"}),
                         "Made Turned from Stroke")
        self.assertEqual(activity.did("robot_trajectory", {"op": "join", "trajectories": ["Stroke", "Turned"], "name": "Both"}),
                         "Joined Stroke and Turned into Both")

    def test_a_raw_dict_is_never_said(self):
        self.assertTrue(echo.raw_words("Material set: Bracket {'note': \"FreeCAD's library has no card\"}"))
        self.assertTrue(echo.raw_words('Spec {"minWall": 1.2}'))
        self.assertFalse(echo.raw_words("Weighed Bracket: 17.1 g in PETG"))
        fn = lambda name, a, b: "Material set: Bracket {'note': 'x'}" if name == "part_spec" else None  # noqa: E731
        echo.WORDS_FNS.append(fn)
        try:
            self.assertIsNone(echo.declared_words("part_spec", {}, {}))
        finally:
            echo.WORDS_FNS.remove(fn)


class HeavyLine(unittest.TestCase):
    """Item 3: the status bar's heavy-job line only while a heavy job runs."""

    def test_status_line(self):
        q = {"held": True, "notice": "A heavy job is running (scan_qa, since 12:44); new heavy jobs wait for your go", "running": [{"tool": "scan_qa"}]}
        self.assertIn("scan_qa", keep.status_line(q))
        q["running"] = []
        self.assertIsNone(keep.status_line(q))
        self.assertTrue(keep.settled_notice(q))
        self.assertEqual(q["notice"], keep.HELD_IDLE)
        self.assertTrue(q["held"])  # the hold itself waits for queue_go
        self.assertFalse(keep.settled_notice(q))
        self.assertIsNone(keep.status_line({"held": False, "running": [{"tool": "x"}]}))

    def test_the_heartbeat_and_queue_ends_use_them(self):
        self.assertIn("line = keep.status_line(q)", src("agentlink", "gui_link.py"))
        self.assertIn("keep.settled_notice(q)", src("agentlink", "supervise.py"))
        self.assertIn("keep.settled_notice(q)", src("agentlink", "jobs.py"))


class Robot(unittest.TestCase):
    """Item 5: labels that would overlap said as one; a trajectory framed on
    its own waypoints."""

    def test_merged_labels(self):
        labels = [((0, 0, 0), "base Arm"), ((1800, 0, 2400), "tool point (Pin)"), ((1825, 0, 2400), "Stroke start"),
                  ((1825, 200, 2400), "Stroke end"), ((9000, 0, 0), "Too far start"), ((9000, 500, 0), "Too far end")]
        got = dict((t, p) for p, t in echo.merged_labels(labels, 0.07 * 9000))
        self.assertIn("Too far", got)
        self.assertNotIn("Too far start", got)
        self.assertIn("base Arm", got)
        self.assertTrue(any("tool point (Pin)" in t and "Stroke" in t for t in got))
        # Far apart: both kept as they are.
        self.assertEqual([t for _p, t in echo.merged_labels([((0, 0, 0), "a start"), ((500, 0, 0), "a end")], 10)], ["a start", "a end"])

    def test_box_size(self):
        self.assertEqual(echo._box_size((0, 0, 0, 10, 30, 5)), 30)
        self.assertEqual(echo._box_size(None), 0.0)

    def test_the_wiring(self):
        e = src("agentlink", "echo.py")
        self.assertIn("return self._track_frame(doc, tracks)", e)
        self.assertIn('self.tr["trackBox"]', e)
        self.assertIn('"robot_trajectory": {"did": ["Joined {trajectories} into {name} if {op=join}"', src("agentlink", "data", "activity.json"))


class HoldFrame(unittest.TestCase):
    """Item 6: the view turned to face a held face that looks away."""

    def test_facing_direction(self):
        iso = (-0.577, 0.577, -0.577)
        # The -X end of a beam, seen from the default isometric view: turned.
        d = echo.facing_direction((-1, 0, 0), iso)
        self.assertGreater(d[0], 0.7)  # looking along +x, onto the -x face
        self.assertAlmostEqual(sum(c * c for c in d), 1.0, places=6)
        # A face already toward the camera: the view kept.
        self.assertEqual(echo.facing_direction((1, -1, 1), iso), tuple(c / (sum(x * x for x in iso) ** 0.5) for c in iso))
        # Straight along the view: still a tilt, never a zero vector.
        d = echo.facing_direction((0, 0, 1), (0, 0, 1))
        self.assertLess(d[2], -0.7)

    def test_wired_after_the_marks(self):
        self.assertIn('self._step(tr, "holdFramed", hold_framed, doc, body)', src("agentlink", "echo.py"))


def _strength_fns():
    tree = ast.parse(src("agentlink", "families", "strength.py"))
    keep_ = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_same_study", "results_of")]
    ns = {}
    exec(compile(ast.Module(body=keep_, type_ignores=[]), "strength", "exec"), ns)
    return ns


class StudyResults(unittest.TestCase):
    """Item 6: a kept solve answers only for the study in hand."""

    def test_results_of(self):
        f = _strength_fns()["results_of"]
        kept = {"body": "Beam", "doc": "Hub", "study": {"body": "Beam", "holds": [1]}, "result": {"vonMisesMax": {"MPa": 460}}}
        self.assertIs(f(kept, {"body": "Beam", "holds": [1, 2]}, "Hub"), kept)  # the same study, changed since: stale, said
        self.assertIsNone(f(kept, None, "Hub"))  # no study here (00-228: before fea_setup)
        self.assertIsNone(f(kept, {"body": "Beam"}, "Other"))  # another document
        self.assertIsNone(f(kept, {"body": "Plate"}, "Hub"))  # another body
        self.assertIsNone(f(dict(kept, doc=None), {"body": "Beam"}, "Hub"))  # kept before the document was recorded
        self.assertIsNone(f(None, {"body": "Beam"}, "Hub"))

    def test_the_tools_refuse_and_name_it(self):
        t = json.loads(src("agentlink", "data", "tools.json"))["entries"]
        for name in ("fea_results", "fea_export"):
            steps = json.dumps(t[name]["steps"])
            self.assertIn("results_elsewhere()", steps, name)
            self.assertIn("an older study, not this one", steps, name)
            self.assertIn("solvedFor", json.dumps(t[name]["answer"]), name)
        s = src("agentlink", "families", "strength.py")
        self.assertIn('"doc": s.doc.Name', s)
        self.assertIn("strength._results(s)", src("agentlink", "families", "view.py"))


class Looks(_Replay):
    """Item 1 in the echo: a look says its own words and changes nothing
    else."""

    def test_session_state_says_its_words(self):
        self.call(Tool("pd_pad", True), {"sketch": "Profile"}, {"feature": "Pad"})
        trace = self.session.echo_trace
        del self.events[:]
        self.call(Tool("session_state", False), {}, {"bodies": [{}, {}], "step": 14})
        self.assertEqual([e[0] for e in self.events], ["caption", "status"])
        self.assertEqual(self.events[0][1], "Read the session: 2 bodies, step 14")
        self.assertIs(self.session.echo_trace, trace)
        self.assertEqual(self.session.echo_look, {"tool": "session_state", "words": "Read the session: 2 bodies, step 14"})

    def test_a_refused_look_says_refused(self):
        tool = Tool("guide_read", False)
        self.echo.before(tool, {"topic": "nope"})
        self.echo.after(tool, {"topic": "nope"}, {"isError": True, "content": [{"type": "text", "text": json.dumps({"error": {"code": "not_found", "message": "nope: no such guide"}})}]})
        self.assertEqual(self.events[0][0], "caption")
        self.assertIn(": refused (nope: no such guide)", self.events[0][1])

    def test_batch_says_nothing(self):
        self.call(Tool("batch", False), {"calls": []}, {"results": []})
        self.assertEqual(self.events, [])


class SplitAndReport(unittest.TestCase):
    """Item 4: a split's pieces selected and coloured; a selection of a gone
    face never sent; the echo's own Report lines in the trace."""

    def test_wiring(self):
        e = src("agentlink", "echo.py")
        self.assertIn('"part_split": ("bodies",)', e)
        self.assertIn('self._step(tr, "piecesColoured", pieces_coloured, made)', e)
        self.assertIn("if sub and not sub_exists(o, sub):", e)
        self.assertIn('report_facts(getattr(echo, "tr", None), name, (r0, r1), (r2, report_count()))', e)

    def test_out_names_take_the_pieces(self):
        body = {"object": "Halves", "pieces": 2, "bodies": ["Halves 1", "Halves 2"]}
        self.assertEqual(echo.out_names("part_split", {}, body), ["Halves 1", "Halves 2"])
        self.assertEqual(echo.out_names("part_split", {}, {"object": "Halves", "pieces": 2}), ["Halves"])

    def test_sub_exists(self):
        o = types.SimpleNamespace(TypeId="Part::Feature", getSubObject=lambda sub: None if sub == "Face9" else object())
        self.assertTrue(echo.sub_exists(o, "Face1"))
        self.assertFalse(echo.sub_exists(o, "Face9"))
        self.assertTrue(echo.sub_exists(o, "Constraint3"))  # not an element: left to the tree
        sk = types.SimpleNamespace(TypeId="Sketcher::SketchObject", getSubObject=lambda sub: None)
        self.assertTrue(echo.sub_exists(sk, "Edge9"))  # a sketch's new lines: before its recompute

    def test_report_facts(self):
        tr = {"tool": "part_split"}
        saved = echo.report_lines
        echo.report_lines = lambda a, b, most=3: [f"line {i}" for i in range(a, b)]
        try:
            echo.report_facts(tr, "part_split", (10, 10), (12, 13))
        finally:
            echo.report_lines = saved
        self.assertEqual(tr["reportDuringEcho"], {"after": ["line 12"]})
        other = {"tool": "pd_pad"}
        echo.report_facts(other, "part_split", (1, 5), (5, 9))
        self.assertEqual(other, {"tool": "pd_pad"})


if __name__ == "__main__":
    unittest.main()
