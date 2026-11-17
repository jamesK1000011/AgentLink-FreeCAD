# SPDX-License-Identifier: LGPL-2.1-or-later
# Window round 7 (17 Nov), stand-ins for:
#   - meshobj_boundary: its rim drawn over the model; its caption with the
#     loops, the length and the area (mesh 12-013).
#   - meshobj_segments kind curvature: its regions coloured (mesh 12-035).
#   - an add-on read with a shape and no object (an answer's sceneMarks):
#     drawn and framed (make 04-085 fea_frame).
#   - a heavy read that ended within its call: not "in the background".
#   - job_start { wait: false }: says it did not wait; a short job's took to
#     the millisecond.
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentlink import activity, annotate, echo  # noqa: E402
from test_echo_maps import WithStandIns  # noqa: E402


class Words(unittest.TestCase):
    def test_boundary_caption_has_loops_length_area(self):
        b = {"mesh": "Half", "loops": 1, "openEdges": 4, "wires": "Half rim",
             "boundaries": [{"edges": 4, "length": 40.0, "closed": True, "centre": [5, 5, 5], "area": 100.0}]}
        self.assertEqual(echo.change_words("Mesh boundary on Half rim", b), "Mesh boundary on Half rim: 1 loop, 40 mm, closed, 100 mm²")
        self.assertEqual(activity.key_value({"mesh": "Cube", "loops": 0, "note": "No open edges: the mesh is closed."}), "0 loops")

    def test_segments_caption_has_the_count(self):
        b = {"mesh": "Cube", "kind": "curvature", "segments": 6, "largest": [{"facets": 2}]}
        self.assertEqual(echo.change_words("Mesh segments on curvature", b), "Mesh segments on curvature: 6 segments")
        self.assertEqual(activity.key_value({"mesh": "Cube", "kind": "planar", "segments": 1, "largest": []}), "1 segment")

    def test_section_rows_are_not_a_boundary(self):
        # meshobj_sections has loops inside its rows only.
        self.assertIsNone(activity.mesh_value({"rows": [{"at": 1, "loops": 2}]}))

    def test_a_finished_job_is_not_in_the_background(self):
        templates = ["Solving the frame in the background if {job}", "Solved the frame under {loadN} N: {verdict}"]
        done = {"job": "job-1a2b3c4d", "loadN": 10000, "verdict": "at most 15.1 MPa, no yield to judge"}
        self.assertEqual(activity.did("x_frame", {}, done, templates), "Solved the frame under 10000 N: at most 15.1 MPa, no yield to judge")
        running = {"job": "job-1a2b3c4d", "tool": "x_frame", "status": "running"}
        self.assertEqual(activity.did("x_frame", {}, running, templates), "Solving the frame in the background")
        # A CAM job's label is no job id: kept.
        self.assertFalse(activity.finished_job({"job": "Job001"}))


class _Edge:
    def __init__(self, p):
        self.Point = p


class _Wire:
    def __init__(self, pts, closed):
        self.OrderedVertexes = [_Edge(p) for p in pts]
        self.Vertexes = self.OrderedVertexes
        self._closed = closed

    def isClosed(self):
        return self._closed


class MarksSvc:
    def __init__(self):
        self.calls = []

    def marks(self, owner, points=(), lines=(), colour="", labels=()):
        self.calls.append(("marks", list(points), [list(x) for x in lines], colour, list(labels)))
        return len(points) + len(lines)

    def clear(self, owner=None):
        self.calls.append(("clear", owner))


class Drawn(WithStandIns):
    def setUp(self):
        super().setUp()
        self.svc = MarksSvc()
        annotate._SERVICE = self.svc
        del echo._view_props[:]

    def tearDown(self):
        del echo._view_props[:]
        super().tearDown()

    def test_rim_drawn_in_front_and_wider(self):
        rim = [(0.0, 0.0, 5.0), (10.0, 0.0, 5.0), (10.0, 10.0, 5.0), (0.0, 10.0, 5.0)]
        sh = types.SimpleNamespace(isNull=lambda: False, Faces=[], Wires=[_Wire(rim, True)])
        vo = types.SimpleNamespace(PropertiesList=["LineWidth"], LineWidth=2.0)
        b = types.SimpleNamespace(Name="Boundary", Label="Half rim", Shape=sh, ViewObject=vo, Document=types.SimpleNamespace(Name="D"))
        got = echo.boundary_drawn([b])
        self.assertEqual(got["loops"], 1)
        self.assertEqual(got["points"], 5)  # closed: back to its start
        self.assertTrue(got["inFront"])
        line = self.svc.calls[0][2][0]
        self.assertEqual(line[0], line[-1])
        self.assertEqual(vo.LineWidth, float(echo.BOUNDARY_WIDTH))
        self.assertIsNone(echo.boundary_drawn([types.SimpleNamespace(Shape=types.SimpleNamespace(isNull=lambda: False, Faces=[1], Wires=[]))]))

    def test_curvature_segments_coloured(self):
        class P:
            def __init__(self, x, y, z):
                self.Vector = types.SimpleNamespace(x=x, y=y, z=z)

        asked = []

        class Mesh:
            CountFacets = 2
            Points = [P(0, 0, 0), P(1, 0, 0), P(0, 1, 0), P(1, 1, 0)]
            Facets = [types.SimpleNamespace(PointIndices=(0, 1, 2)), types.SimpleNamespace(PointIndices=(1, 3, 2))]

            @staticmethod
            def getSegmentsByCurvature(spec):
                asked.append(spec)
                return [[0, 1]]

        o = types.SimpleNamespace(Name="Cube", Label="Cube", Mesh=Mesh)
        doc = types.SimpleNamespace(getObject=lambda n: o if n == "Cube" else None,
                                    getObjectsByLabel=lambda lb: [o] if lb == "Cube" else [], Objects=[o])
        fields = []
        self.svc.field = lambda owner, V, F, colours, per_face=False: fields.append(len(F)) or len(F)
        got = echo.segments_drawn(doc, {"mesh": "Cube", "kind": "curvature", "tolerance": 0.02, "minFacets": 2}, {"mesh": "Cube"})
        self.assertEqual(got["kind"], "curvature")
        self.assertEqual(got["regions"], 1)
        self.assertEqual(asked, [[(0.0, 0.0, 0.02, 0.02, 2)]])
        self.assertEqual(fields, [2])

    def test_an_answers_scene_marks_drawn(self):
        body = {"sceneMarks": {"lines": [[[0, 0, 0], [1000, 0, 0]], [[1, 2]]], "points": [[0, 0, 0], [1000, 0, 0]],
                               "labels": [[[500, 0, 0], "Beam: sags 0.156 mm"]]}}
        got = echo.scene_marks_shown(body)
        self.assertEqual(got["lines"], 1)
        self.assertEqual(got["points"], 2)
        self.assertEqual(got["labels"], ["Beam: sags 0.156 mm"])
        self.assertEqual(got["box"], [0.0, 0.0, 0.0, 1000.0, 0.0, 0.0])
        self.assertEqual(self.svc.calls[0], ("clear", echo.SCENE_OWNER))
        self.assertIsNone(echo.scene_marks_shown({"members": []}))
        self.assertIsNone(echo.scene_marks_shown(None))


class Jobs(unittest.TestCase):
    def test_wait_false_says_so_and_took_is_to_the_millisecond(self):
        home = tempfile.mkdtemp()
        body = textwrap.dedent(f'''
            import json, os, sys, time, types
            sys.path.insert(0, {HERE!r})
            os.environ["AGENTLINK_HOME"] = {home!r}
            from agentlink import jobs, protocol
            from agentlink.protocol import Tool

            class Doc:
                Name, Objects = "D", ()

            ses = types.SimpleNamespace(out_dir={home!r}, doc=Doc())

            def quick(a):
                time.sleep(0.2)
                return {{"read": 1}}

            fake = types.SimpleNamespace(session=ses)
            got = protocol.Server._as_job(fake, Tool("quick_read", "does", {{"type": "object"}}, quick), {{}}, wait=0)
            j = jobs.get(got["job"])
            jobs.wait_for(j, 5)
            print(json.dumps({{"note": got["note"], "status": got["status"], "took": jobs.summary(j)["took"]}}))
        ''')
        r = subprocess.run([sys.executable, "-c", body], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        got = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(got["status"], "running")
        self.assertIn("was not waited for (wait: false)", got["note"])
        self.assertNotIn("past", got["note"])
        self.assertGreater(got["took"], 0.1)
        self.assertLess(got["took"], 1.0)


if __name__ == "__main__":
    unittest.main()
