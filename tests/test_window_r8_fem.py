# SPDX-License-Identifier: LGPL-2.1-or-later
# Window round 8, FEM (live 17 Nov, pictures 03-012…03-042, 00-033, 00-042):
# fea_heat's temperatures checked against the faces held (a run that does not
# hold them is not answered), FreeCAD's empty ±0.5 colour bars put away and
# each FEM read's field drawn with a scale in its unit, fea_native's
# unsolved analysis shown without an older result's colours, the FEM reads'
# words with their values, and the heavy queue's "is running" line gone
# when the job has ended (its file read and written under a lock). Without
# FreeCAD: stand-ins.
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agentlink import activity, ccx_io, echo, keep, render  # noqa: E402
from test_echo_maps import WithStandIns  # noqa: E402

MESH = ("*Node, NSET=Nall\n1, 0, 0, 0\n2, 2, 0, 0\n3, 0, 2, 0\n4, 0, 0, 2\n5, 1, 0, 0\n6, 1, 1, 0\n7, 0, 1, 0\n8, 0, 0, 1\n9, 1, 0, 1\n10, 0, 1, 1\n\n"
        "*Element, TYPE=C3D10, ELSET=Evolumes\n1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10\n")

FRD_HEAT = """    1C
  100CL  101 0.495000000           2                     0    1           1
 -4  NDTEMP      1    1
 -5  T           1    1    0    0
 -1         1 2.39600E+01
 -1         2 2.00000E+01
 -3
  100CL  101 1.000000000           2                     0    2           1
 -4  NDTEMP      1    1
 -5  T           1    1    0    0
 -1         1 1.00000E+02
 -1         2 2.00000E+01
 -3
 9999
"""


class HeatDeck(unittest.TestCase):
    def test_as_freecad_writes_a_heat_step(self):
        h = ccx_io.deck_heat(MESH, 50, {1: 100.0, 2: 20.0}, [], [], element="C3D10", elastic=(210000, 0.3))
        self.assertIn("TYPE=C3D10", h)
        self.assertNotIn("DC3D10", h)
        self.assertIn("*ELASTIC\n210000, 0.3", h)
        self.assertIn("*HEAT TRANSFER, STEADY STATE", h)
        self.assertIn("1, 11, 11, 100", h)
        self.assertIn("TYPE=DC3D10", ccx_io.deck_heat(MESH, 50, {1: 100.0}, [], []))  # the old default stays
        self.assertNotIn("*ELASTIC", ccx_io.deck_heat(MESH, 50, {1: 100.0}, [], []))
        self.assertEqual(ccx_io.HEAT_ELEMENTS[::-1][0], "C3D10")  # FreeCAD's way is tried first

    def test_times_and_the_held_check(self):
        self.assertEqual(ccx_io.frd_times(FRD_HEAT), [0.495, 1.0])
        self.assertEqual(ccx_io.read_temperatures(FRD_HEAT), {1: 100.0, 2: 20.0})
        rows, ok = ccx_io.held_check({1: 100.0, 2: 20.0}, {1: 100.0, 2: 20.0, 3: 60.0})
        self.assertTrue(ok)
        self.assertEqual(rows[0], {"celsius": 100.0, "nodes": 1, "read": [100.0, 100.0]})
        # The live answer: held at 100, read 23.96 — not held.
        rows, ok = ccx_io.held_check({1: 100.0, 2: 20.0}, {1: 23.96, 2: 20.0})
        self.assertFalse(ok)
        self.assertEqual(rows[0]["read"], [23.96, 23.96])
        rows, ok = ccx_io.held_check({1: 100.0, 7: 100.0}, {1: 100.0})
        self.assertFalse(ok)
        self.assertEqual(rows[0]["missing"], 1)


class HeatSolveSource(unittest.TestCase):
    def test_the_answer_carries_the_check(self):
        src = open(os.path.join(HERE, "..", "agentlink", "families", "strength.py"), encoding="utf-8").read()
        self.assertIn("ccx_io.held_check(temps, T)", src)
        self.assertIn('raise ToolError("failed", f"CalculiX\'s temperatures do not hold the faces given', src)
        tools = open(os.path.join(HERE, "..", "agentlink", "data", "tools.json"), encoding="utf-8").read()
        self.assertIn('"solveCheck": "=heat_facts(m)"', tools)
        self.assertIn("timeout, c)", tools)


class Queue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._home = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = self.tmp

    def tearDown(self):
        if self._home is None:
            os.environ.pop("AGENTLINK_HOME", None)
        else:
            os.environ["AGENTLINK_HOME"] = self._home

    def test_lock_is_reentrant_and_update_writes(self):
        with keep.queue_lock() as a:
            self.assertTrue(a.held)
            with keep.queue_lock() as b:
                self.assertTrue(b.held)
        keep.update_queue(lambda q: q.__setitem__("running", [{"tool": "fea_buckle", "start": 1.0}]))
        self.assertEqual(keep.queue_state()["running"][0]["tool"], "fea_buckle")
        keep.update_queue(lambda q: False)  # nothing written
        self.assertEqual(len(keep.queue_state()["running"]), 1)

    def test_the_hold_does_not_put_back_an_ended_job(self):
        from agentlink import supervise

        keep.save_queue({"running": [{"tool": "fea_buckle", "start": 100.0, "pid": os.getpid()}], "held": False, "timings": {}})
        supervise.queue_done("fea_buckle")  # its answer came back
        got = supervise.queue_hold(True, busy=False, now=200.0)  # the person active: read again under the lock
        self.assertIsNone(got)
        q = keep.queue_state()
        self.assertEqual(q["running"], [])
        self.assertFalse(q.get("held"))
        self.assertIsNone(keep.status_line(q))

    def test_a_leftover_is_taken_out_and_the_notice_settled(self):
        from agentlink import supervise

        keep.save_queue({"running": [{"tool": "fea_buckle", "start": 100.0}], "held": True,
                         "notice": "A heavy job is running (fea_buckle, since 13:06); new heavy jobs wait for your go", "timings": {}})
        self.assertIn("fea_buckle", keep.status_line(keep.queue_state()))
        got = supervise.queue_hold(False, busy=False, now=100.0 + keep.STALE_AFTER + 1)
        self.assertEqual(got["dropped"], ["fea_buckle"])
        q = keep.queue_state()
        self.assertEqual(q["notice"], keep.HELD_IDLE)
        self.assertIsNone(keep.status_line(q))

    def test_running_kept_while_a_call_is_in_hand(self):
        q = {"running": [{"tool": "fea_buckle", "start": 0.0}]}
        self.assertEqual(keep.stale_running(q, busy=True, now=1000.0), [])
        self.assertEqual(keep.stale_running({"running": [{"tool": "x", "start": 995.0}]}, busy=False, now=1000.0), [])
        other = {"running": [{"tool": "x", "start": 0.0, "pid": os.getpid() + 1}]}
        self.assertEqual(keep.stale_running(other, busy=False, now=1000.0), [])  # another supervisor's
        dead = {"running": [{"tool": "fea_heat", "job": "job-1", "t": 0.0, "pid": 2 ** 22 + 12345}]}
        self.assertEqual(len(keep.stale_running(dead, busy=True, now=1000.0)), 1)

    def test_status_line_skips_ended_jobs(self):
        q = {"held": True, "notice": "A heavy job is running (fea_buckle, since 13:06)", "running": [{"tool": "fea_buckle", "job": "job-x"}]}
        self.assertIsNotNone(keep.status_line(q))
        self.assertIsNone(keep.status_line(q, alive=lambda r: False))
        self.assertIsNotNone(keep.status_line(q, alive=lambda r: 1 / 0))  # a failing check keeps it


class Words(unittest.TestCase):
    def test_reads_say_their_values(self):
        probe = {"body": "Box", "points": [{"displacementMm": 87.91}, {"displacementMm": 0.0}],
                 "line": [{"displacementMm": 0.0}, {"displacementMm": 87.9}],
                 "faces": {"faces": ["Face2"], "displacementMm": {"max": 88.1}, "vonMisesMPa": {"max": 25.3}}}
        self.assertEqual(activity.outcome("fea_probe", True, probe),
                         "87.91 mm, 0 mm at 2 points; line 2 samples, 0 to 87.9 mm; Face2 up to 88.1 mm, 25.3 MPa")
        self.assertEqual(activity.outcome("fea_chart", True, {"body": "Box", "kind": "histogram", "field": "displacement", "unit": "mm", "nodes": 796, "min": 0.0, "max": 88.25}),
                         "Histogram of displacement 0 … 88.25 mm, 796 nodes")
        self.assertEqual(activity.outcome("fea_chart", True, {"kind": "line", "field": "vonMises", "unit": "MPa", "nodes": 796, "samples": 9, "max": 432.1}),
                         "Line of von Mises up to 432 MPa, 9 samples from the nearest nodes")
        self.assertEqual(activity.call_value("fem_linearize", {"membrane": 1.2, "bending": 215.7, "thickness": 1000, "points": 21}),
                         "membrane 1.2 MPa, bending 216 MPa through 1000 mm")
        self.assertEqual(activity.call_value("fea_native", {"analysis": "Box native", "solver": "calculix", "objects": ["a", "b", "c", "d", "e"]}),
                         "Box native, CalculiX, 5 objects, not solved")
        self.assertEqual(activity.fem_value({"hottest": {"celsius": 100.0}, "coolest": {"celsius": 20.0}}), "hottest 100 °C, coolest 20 °C")


class _VO:
    def __init__(self, field="None", visible=True):
        self.Field = field
        self.Visibility = visible
        self.colours = None

    def setNodeColorByScalars(self, ids, vals):
        self.colours = (list(ids), list(vals))


def _obj(name, type_id, label=None, **kw):
    o = types.SimpleNamespace(Name=name, Label=label or name, TypeId=type_id, Document=types.SimpleNamespace(Name="D"), **kw)
    if "ViewObject" not in kw:
        o.ViewObject = _VO()
    return o


def _doc(objs):
    return types.SimpleNamespace(Objects=objs, getObject=lambda n: next((o for o in objs if o.Name == n), None),
                                 getObjectsByLabel=lambda lb: [o for o in objs if o.Label == lb])


class Bars(WithStandIns):
    def test_empty_bars_away_and_all_when_ours_is_drawn(self):
        empty = _obj("Pipeline", "Fem::FemPostPipeline", "Pipeline_CCX_Results")
        shown = _obj("Pipeline001", "Fem::FemPostPipeline", ViewObject=_VO("von Mises Stress"))
        box = _obj("Box", "Part::Box")
        doc = _doc([empty, shown, box])
        self.assertEqual(echo.fem_bars_away(doc), ["Pipeline_CCX_Results (None)"])
        self.assertFalse(empty.ViewObject.Visibility)
        self.assertTrue(shown.ViewObject.Visibility and box.ViewObject.Visibility)
        self.assertEqual(echo.fem_bars_away(doc, True), ["Pipeline001 (von Mises Stress)"])

    def test_stops_and_labels(self):
        self.assertEqual(echo.fem_stops(0, 400), [(0.0, (0.0, 1.0, 0.0)), (0.5, (1.0, 1.0, 0.0)), (1.0, (1.0, 0.0, 0.0))])
        s = echo.fem_stops(-100, 300)
        self.assertEqual(s[0], (0.0, (0.0, 0.0, 1.0)))
        self.assertEqual(s[2], (0.25, (0.0, 1.0, 0.0)))
        self.assertEqual(echo._fem_labels("NodeStressXX"), ("STRESS XX", "MPa"))
        self.assertEqual(echo._fem_labels("von Mises Stress"), ("VON MISES", "MPa"))
        self.assertEqual(echo._fem_labels("displacement"), ("DISPLACEMENT", "mm"))


class Native(WithStandIns):
    def test_unsolved_analysis_draws_no_old_map(self):
        res_mesh = _obj("ResultMesh", "Fem::FemMeshObject", "CCX_Results_Mesh")
        res = _obj("CCX_Results", "Fem::FemResultObjectMechanical", Mesh=res_mesh, vonMises=[0.0, 430.0])
        pipe = _obj("Pipeline", "Fem::FemPostPipeline")
        old = _obj("Analysis", "Fem::FemAnalysis", "Box strength (fea_solve)", Group=[res, res_mesh, pipe])
        new = _obj("Analysis001", "Fem::FemAnalysis", "Box native", Group=[])
        doc = _doc([old, res, res_mesh, pipe, new])
        s = types.SimpleNamespace(_agentlink_fea={"body": "Box", "field": {"vonMises": [0.0, 430.0]}}, body=lambda n: None)
        got = echo.fem_result_shown(doc, {"analysis": "Box native", "solver": "calculix"}, s, "fea_native")
        self.assertEqual(got["map"], None)
        self.assertEqual(got["notSolved"], "Box native")
        self.assertEqual(sorted(got["hidden"]), ["CCX_Results_Mesh", "Pipeline"])
        self.assertFalse([c for c in self.svc.calls if c[0] in ("field", "legend")])
        # fea_native naming no analysis found: no fallback to the last solve's field either.
        self.assertIsNone(echo.fem_result_shown(_doc([]), {"analysis": "Gone"}, s, "fea_native"))

    def test_ring_is_on_the_analysis_button(self):
        # 03-033: the reviewer read FEM_Analysis's icon (a serif "A") as Draft Text.
        self.assertEqual(echo.COMMAND["fea_native"], "FEM_Analysis")


class ReadMaps(WithStandIns):
    def _with_map(self, name, fn):
        had = render.MAPS.get(name)
        render.MAPS[name] = (fn, "")
        self.addCleanup(lambda: render.MAPS.__setitem__(name, had) if had else render.MAPS.pop(name, None))

    def test_heat_drawn_from_20_to_100_in_celsius(self):
        V = [(0, 0, 0), (8000, 0, 0), (0, 1000, 0)]
        self._with_map("heat", lambda s_, a: {"layers": [{"V": V, "F": [(0, 1, 2)], "values": [100.0, 20.0, 100.0]}], "unit": "C", "label": "TEMPERATURE"})
        body = _obj("Box", "Part::Box")
        mesh = _obj("Mesh", "Fem::FemMeshObjectPython", "Mesh")
        s = types.SimpleNamespace(_agentlink_heat={"body": "Box", "field": {"points": [], "celsius": [100.0, 60.0, 20.0]}}, body=lambda n: body)
        got = echo.fem_read_map(_doc([body, mesh]), "fea_heat", {}, {"hottest": {"celsius": 100.0}}, s)
        self.assertEqual(got["range"], [20.0, 100.0])
        self.assertEqual(got["unit"], "°C")
        self.assertEqual(sorted(got["hidden"]), ["Box", "Mesh"])
        leg = [c for c in self.svc.calls if c[0] == "legend"][0]
        self.assertEqual(leg[1:5], ("TEMPERATURE", "°C", 20.0, 100.0))

    def test_probe_draws_the_displacement_in_mm(self):
        V = [(0, 0, 0), (8000, 0, 0), (0, 1000, 0)]
        self._with_map("stress", lambda s_, a: {"layers": [{"V": V, "F": [(0, 1, 2)], "values": [400.0, 0.0, 400.0]}], "unit": "MPa", "label": "VON MISES"})
        s = types.SimpleNamespace(_agentlink_fea={"body": "Box", "field": {"points": [(0, 0, 0), (8000, 0, 0)], "displacement": [(0, 0, 0), (0, 0, -87.9)],
                                                                         "vonMises": [432.0, 1.0]}}, body=lambda n: None)
        got = echo.fem_read_map(_doc([]), "fea_probe", {"points": [[8000, 500, 500]]}, {"points": [{"displacementMm": 87.9}]}, s)
        self.assertEqual(got["unit"], "mm")
        self.assertEqual(got["range"], [0.0, 87.9])
        got = echo.fem_read_map(_doc([]), "fea_chart", {"kind": "histogram"}, {"field": "vonMises"}, s)
        self.assertEqual((got["unit"], got["range"]), ("MPa", [0.0, 432.0]))

    def test_linearize_colours_the_result_with_freecads_colours(self):
        res_mesh = _obj("ResultMesh", "Fem::FemMeshObject", "CCX_Results_Mesh", ViewObject=_VO(visible=False))
        res = _obj("CCX_Results", "Fem::FemResultObjectMechanical", Mesh=res_mesh, vonMises=[1.0, 2.0], NodeNumbers=[1, 2],
                   NodeStressXX=[-216.0, 216.0])
        gm = _obj("Mesh", "Fem::FemMeshObjectPython", "Mesh")
        self.svc.marks = lambda owner, points=(), lines=(), colour="", labels=(): self.svc.calls.append(("marks", list(points), [t for _p, t in labels])) or len(points)
        got = echo.fem_read_map(_doc([res, res_mesh, gm]), "fem_linearize", {"result": "CCX_Results", "from": [4000, 500, 0], "to": [4000, 500, 1000]},
                                {"result": "CCX_Results", "field": "NodeStressXX"}, None)
        self.assertEqual(res_mesh.ViewObject.colours, ([1, 2], [-216.0, 216.0]))
        self.assertTrue(res_mesh.ViewObject.Visibility)
        self.assertEqual((got["label"], got["unit"], got["range"]), ("STRESS XX", "MPa", [-216.0, 216.0]))
        self.assertEqual(got["hidden"], ["Mesh"])
        self.assertIn(("marks", [(4000, 500, 0), (4000, 500, 1000)], ["from", "to"]), self.svc.calls)
        self.assertTrue(got["lineMarked"])


if __name__ == "__main__":
    unittest.main()


class HeatPeaks(unittest.TestCase):
    """Live 17 Nov: fea_heat said hottest 23.96 and coolest 100 for faces
    held at 100 and 20. In the data expressions T.get is not dict.get (a
    dotted name reads a key), so max(T, key=T.get) ranked node numbers."""

    def test_peaks_rank_temperatures(self):
        from agentlink import expr
        T = {1: 100.0, 2: 20.0, 5: 23.96}
        self.assertEqual(expr.evaluate("max(T, key=lambda n: T[n])", {"T": T}), 1)
        self.assertEqual(expr.evaluate("min(T, key=lambda n: T[n])", {"T": T}), 2)

    def test_heat_uses_the_lambda(self):
        import json, os
        here = os.path.join(os.path.dirname(__file__), "..", "agentlink", "data", "tools.json")
        text = open(here).read()
        import re
        self.assertEqual(re.findall(r"key=[A-Za-z_]+\.get\b", text), [], "a dotted name reads a key in the data expressions: key=lambda n: X[n]")
