# SPDX-License-Identifier: LGPL-2.1-or-later
# Found modelling a bike stem on the Mac (live test drive, 16 Nov 2026):
# param_bind refused a parameter by its bare name; sketch_constrain blamed
# the constraint the solver happened to name, not the two that clashed;
# each tool took faces and edges its own way (shape_query's references and
# filters were refused by pd_fillet, pd_chamfer, fea_hold, fea_load);
# view_snapshot's grid size; a DXF's closed 3D polyline lost its closing
# edge, a SPLINE by fit points failed, and the answer listed every layer.
import math
import os
import sys
import tempfile
import unittest

from _pd_base import HAVE, Base

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import dxfread  # noqa: E402
from agentlink.exprs import qualify  # noqa: E402


# ---- pure: no FreeCAD -------------------------------------------------------------------

class BareNames(unittest.TestCase):
    def test_bare_parameter_names_are_the_sheets(self):
        self.assertEqual(qualify("size", ["size"], "Params"), ("Params.size", {"size": "Params.size"}))
        self.assertEqual(qualify("size / 2 + 1", ["size"], "Params")[0], "Params.size / 2 + 1")
        self.assertEqual(qualify("size2 + size", ["size", "size2"], "Params")[0], "Params.size2 + Params.size")
        # Left as written: already qualified, a member, a function, quoted, a unit.
        for e in ("Params.size", "Box.size", "<<Params>>.size", "sin(1)", "5 mm", "BaseSketch.Constraints.size"):
            self.assertEqual(qualify(e, ["size", "sin", "mm"], "Params")[0], e)
        self.assertEqual(qualify("sin(size)", ["size"], "Params")[0], "sin(Params.size)")
        # The sheet's own alias is kept bare.
        self.assertEqual(qualify("size * 2", ["size"], "Params", keep=["size"])[0], "size * 2")


def polyline3d(n=40, closed=True, layer="Rail"):
    out = ["0", "POLYLINE", "8", layer, "66", "1", "70", str(8 | (1 if closed else 0))]
    for i in range(n):
        t = 2 * math.pi * i / n
        out += ["0", "VERTEX", "8", layer, "10", f"{20 * math.cos(t):.6f}", "20", f"{20 * math.sin(t):.6f}", "30", f"{i * 0.25:.6f}", "70", "32"]
    return out + ["0", "SEQEND"]


def spline_fit(layer="Curve"):
    pts = [(0, 0, 0), (10, 8, 0), (20, 0, 0), (30, -8, 0), (40, 0, 0)]
    out = ["0", "SPLINE", "8", layer, "70", "8", "71", "3", "72", "0", "73", "0", "74", str(len(pts))]
    for x, y, z in pts:
        out += ["11", str(x), "21", str(y), "31", str(z)]
    return out


def lw_slot(layer="Cut"):
    # A slot: two lines and two half circles by bulge, closed.
    return ["0", "LWPOLYLINE", "8", layer, "90", "4", "70", "1",
            "10", "0", "20", "0", "42", "0", "10", "20", "20", "0", "42", "1",
            "10", "20", "20", "10", "42", "0", "10", "0", "20", "10", "42", "1"]


def dxf(*ents, extra=()):
    body = [x for e in ents for x in e] + list(extra)
    return "\n".join(["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
                      "0", "SECTION", "2", "ENTITIES"] + body + ["0", "ENDSEC", "0", "EOF"]) + "\n"


class DxfParse(unittest.TestCase):
    def test_closed_3d_polyline_keeps_its_closing_edge(self):
        p = dxfread.parse(dxf(polyline3d(40)))
        e = p["entities"][0]
        self.assertEqual((e["type"], e["closed"], e["is3d"], len(e["points"])), ("POLYLINE", True, True, 40))
        self.assertEqual(len(dxfread.segments(e)), 40)
        self.assertEqual(len(dxfread.segments({**e, "closed": False})), 39)
        self.assertEqual(p["units"], 4)

    def test_spline_fit_points_and_bulges_and_what_is_left(self):
        p = dxfread.parse(dxf(spline_fit(), lw_slot(), extra=["0", "TEXT", "8", "Notes", "1", "hello", "0", "INSERT", "8", "0", "2", "B"]))
        kinds = [e["type"] for e in p["entities"]]
        self.assertEqual(kinds, ["SPLINE", "LWPOLYLINE"])
        self.assertEqual(len(p["entities"][0]["fit"]), 5)
        self.assertEqual(p["other"], {"TEXT": 1, "INSERT": 1})
        segs = dxfread.segments(p["entities"][1])
        self.assertEqual([s[0] for s in segs], ["line", "arc", "line", "arc"])
        # A bulge of 1 is a half circle: its middle 5 mm out to the right of 20,0 -> 20,10.
        self.assertEqual([round(c, 6) for c in segs[1][2]], [25.0, 5.0, 0.0])

    def test_ocs_of_a_mirrored_arc(self):
        self.assertEqual([round(c, 6) for c in dxfread.to_world([1, 2, 3], [0, 0, -1])], [-1.0, 2.0, -3.0])
        self.assertEqual(dxfread.to_world([1, 2, 3], [0, 0, 1]), [1, 2, 3])


# ---- the heavy gate: pictures are not refused on an estimate, nor any call in a batch -----

class _Shape:
    Faces = [0] * 400

    def isNull(self):
        return False


class _Obj:
    Name = Label = "Stem"
    Shape = _Shape()
    InList = []


class _Doc:
    Objects = [_Obj()]


class _Sess:
    doc = _Doc()


class _Tool:
    def __init__(self, name, changes=False):
        self.name, self.changes = name, changes


class EstimateGate(unittest.TestCase):
    def setUp(self):
        self.env = {k: os.environ.get(k) for k in ("AGENTLINK_HOME", "AGENTLINK_GATE")}
        os.environ["AGENTLINK_HOME"] = tempfile.mkdtemp(prefix="agentlink-gate-")
        os.environ["AGENTLINK_GATE"] = "1"
        from agentlink import heavy, keep

        self.heavy, self.keep = heavy, keep
        q = keep.queue_state()
        # One slow run each, as the timed-out render left: 6 min at this size.
        for t in ("view_render", "fea_solve"):
            keep.log_timing(q, t, 400, 360.0)
        keep.save_queue(q)

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_render_runs_on_the_first_call(self):
        g = self.heavy.Gate(_Sess())
        g.before(_Tool("view_render"), {"views": ["iso"]})  # not refused
        g.after(_Tool("view_render"), {}, True)

    def test_other_heavy_tools_run_at_once_in_and_out_of_a_batch(self):
        # No prejudging (18 Nov): no estimate asks first, alone or in a batch.
        g = self.heavy.Gate(_Sess())
        g.before(_Tool("fea_solve"), {"a": 1})
        g.after(_Tool("fea_solve"), {}, True)
        s = _Sess()
        s.batch_now = {"i": 0}
        g2 = self.heavy.Gate(s)
        g2.before(_Tool("fea_solve"), {"a": 2})
        g2.after(_Tool("fea_solve"), {}, True)


# ---- on FreeCAD ---------------------------------------------------------------------------

@unittest.skipUnless(HAVE, "FreeCAD with PartDesign and Sketcher is not importable here")
class StemFindings(Base):
    def test_1_param_bind_takes_a_bare_name(self):
        self.ok("doc_new", {"name": "Params1"})
        self.ok("pd_body_new", {"name": "Stem"})
        self.ok("sketch_new", {"plane": "XY", "name": "BaseSketch"})
        self.ok("sketch_add", {"sketch": "BaseSketch", "items": [{"kind": "rectangle", "corner": [0, 0], "size": [40, 20], "dims": True, "name": "reach"}]})
        self.ok("pd_pad", {"sketch": "BaseSketch", "length": 10})
        self.ok("param_set", {"name": "size", "value": 50})
        b = self.ok("param_bind", {"target": "BaseSketch.reach_width", "expression": "size"})
        self.assertEqual(b["value"], 50)
        self.assertTrue(b["expression"].endswith(".size") and b["expression"] != "size", b)
        self.assertIn("size", b["read"]["as"])
        b = self.ok("param_bind", {"target": "Pad.Length", "expression": "size / 5"})
        self.assertAlmostEqual(b["value"], 10, places=4)
        e = self.refused("param_bind", {"target": "Pad.Length", "expression": "nothere"})
        self.assertIn("size", e["message"])  # the names there are
        # A formula in another sheet takes the bare name too.
        self.ok("sheet_new", {"name": "Calc"})
        self.ok("sheet_set", {"sheet": "Calc", "cells": {"A1": "=size * 2"}})
        cell = self.ok("sheet_read", {"sheet": "Calc", "cells": ["A1"]})["cells"][0]
        self.assertAlmostEqual(float(cell["value"]), 100, places=4)

    def test_2_constrain_names_the_clash(self):
        self.ok("doc_new", {"name": "Clash"})
        self.ok("pd_body_new", {"name": "B"})
        self.ok("sketch_new", {"plane": "XY", "name": "S"})
        self.ok("sketch_add", {"sketch": "S", "items": [{"kind": "line", "from": [0, 5], "to": [30, 5]}, {"kind": "line", "from": [0, 20], "to": [30, 25]}]})
        self.ok("sketch_constrain", {"sketch": "S", "constraints": [{"type": "horizontal", "refs": [0]}]})
        e = self.refused("sketch_constrain", {"sketch": "S", "constraints": [
            {"type": "distance", "refs": [1], "value": 30},
            {"type": "parallel", "refs": [0, -1]},
        ]})
        m = e["message"]
        self.assertIn("horizontal", m)
        self.assertIn("parallel", m)
        self.assertIn("the x axis", m)
        self.assertNotIn("line 1", m)  # the length of the other line is no part of it
        self.assertEqual(len(self.ok("sketch_state", {"sketch": "S"})["constraints"]), 1)

    def test_3_one_reference_resolver(self):
        self.ok("doc_new", {"name": "Refs"})
        self.ok("pd_body_new", {"name": "Block"})
        self.ok("sketch_new", {"plane": "XY", "name": "R"})
        self.ok("sketch_add", {"sketch": "R", "items": [{"kind": "rectangle", "center": [0, 0], "size": [40, 20]}]})
        self.ok("pd_pad", {"sketch": "R", "length": 10})
        # shape_query's filters straight into pd_fillet: the two top edges along x.
        f = self.ok("pd_fillet", {"edges": {"type": "line", "axis": [1, 0, 0], "z": 10}, "radius": 1})
        self.assertEqual(len(f["on"]), 2)
        # Its references (bare, with the body, an item as it came) into pd_chamfer.
        q = self.ok("shape_query", {"body": "Block", "kind": "edge", "type": "line", "axis": [1, 0, 0], "z": 0})
        self.assertEqual(q["found"], 2)
        c = self.ok("pd_chamfer", {"edges": ["Block." + q["items"][0]["ref"], q["items"][1]], "size": 1})
        self.assertEqual(sorted(c["on"]), sorted(i["ref"] for i in q["items"]))
        # The older forms still work: { near } with kind.
        top = self.ok("shape_query", {"body": "Block", "kind": "face", "type": "plane", "normal": [0, 0, 1]})
        self.assertGreaterEqual(top["found"], 1)
        e = self.refused("pd_chamfer", {"edges": ["Other.Edge1"], "size": 1})
        self.assertIn("Other", e["message"])
        e = self.refused("pd_fillet", {"edges": "Edge999", "radius": 1})
        self.assertEqual(e["code"], "not_found")
        e = self.refused("pd_fillet", {"edges": {"type": "ellipse"}, "radius": 1})
        self.assertIn("shape_query", e["message"])

    def test_4_fea_takes_the_same_references(self):
        import FreeCAD
        import Part

        from _fc import add_body

        self.ok("doc_new", {"name": "Fea"})
        add_body(self.session, "Beam", Part.makeBox(100, 10, 10).cut(Part.makeCylinder(3, 10, FreeCAD.Vector(80, 5, 0))))
        self.ok("material_set", {"id": "pla"})
        self.ok("fea_setup", {"body": "Beam", "mesh": 3})
        end = self.ok("shape_query", {"body": "Beam", "kind": "face", "type": "plane", "normal": [-1, 0, 0]})
        h = self.ok("fea_hold", {"faces": end["items"][0]["ref"]})
        self.assertEqual(len(h["held"]), 1)
        h = self.ok("fea_hold", {"faces": ["Beam." + end["items"][0]["ref"]], "replace": True})
        self.assertEqual(len(h["held"]), 1)
        # A filter only shape_query had: the hole's wall by type and radius.
        ld = self.ok("fea_load", {"faces": {"type": "cylinder", "radius": 3}, "force": [0, 0, -10]})
        self.assertGreaterEqual(len(ld["on"]), 1)
        self.assertTrue(all("cylinder" in f for f in ld["on"]), ld)
        # The older forms are as they were.
        self.ok("fea_load", {"faces": {"near": [100, 5, 5]}, "force": [0, 0, -5]})
        e = self.refused("fea_hold", {"faces": {"type": "sphere"}})
        self.assertEqual(e["code"], "not_found")

    def test_5_dxf_import_reads_and_sums_up(self):
        self.ok("doc_new", {"name": "Dxf"})
        d = tempfile.mkdtemp()
        p = os.path.join(d, "rails.dxf")
        with open(p, "w") as f:
            f.write(dxf(*[polyline3d(40, layer=f"L{i % 3}") for i in range(20)], spline_fit(), lw_slot()))
        out = self.ok("import_file", {"path": p})
        self.assertEqual(out["count"], 22)
        self.assertEqual(out["read"]["entities"], {"POLYLINE": 20, "SPLINE": 1, "LWPOLYLINE": 1})
        self.assertNotIn("failed", out["read"])
        self.assertEqual(len(out["objects"]), 5)  # summed up, the first few listed
        self.assertEqual(out["byType"]["POLYLINE"], 20)
        self.assertEqual(out["layerCount"], 5)
        doc = self.session.doc
        rails = [o for o in doc.Objects if getattr(o, "DxfType", "") == "POLYLINE"]
        self.assertEqual(len(rails), 20)
        for o in rails:
            self.assertEqual(len(o.Shape.Edges), 40)
            self.assertTrue(o.Shape.Wires[0].isClosed())
        sp = next(o for o in doc.Objects if getattr(o, "DxfType", "") == "SPLINE")
        self.assertEqual(type(sp.Shape.Edges[0].Curve).__name__, "BSplineCurve")
        slot = next(o for o in doc.Objects if getattr(o, "DxfType", "") == "LWPOLYLINE")
        self.assertTrue(slot.Shape.Wires[0].isClosed())
        self.assertAlmostEqual(slot.Shape.Length, 40 + 2 * math.pi * 5, places=3)

    def test_7_attached_objects_leave_the_body_a_part(self):
        import FreeCAD
        import Part

        self.ok("doc_new", {"name": "Attached"})
        self.ok("pd_body_new", {"name": "Stem"})
        self.ok("sketch_new", {"plane": "XY", "name": "A"})
        self.ok("sketch_add", {"sketch": "A", "items": [{"kind": "rectangle", "center": [0, 0], "size": [20, 20]}]})
        self.ok("pd_pad", {"sketch": "A", "length": 5})
        doc = self.session.doc
        body = doc.getObjectsByLabel("Stem")[0]
        # A screw-like solid attached to the body (Fasteners' BaseObject; a
        # part's AttachmentSupport): it refers to the body, it is not built from it.
        screw = doc.addObject("Part::FeaturePython", "Screw")
        screw.addProperty("App::PropertyLinkSub", "BaseObject", "Fastener")
        screw.BaseObject = (body, ["Edge1"])
        screw.Shape = Part.makeCylinder(1.5, 10, FreeCAD.Vector(0, 0, 5))
        doc.recompute()
        names = [o.Label for o in self.session.bodies()]
        self.assertIn("Stem", names)
        self.assertIn("Screw", names)
        # A real consumer still hides its input.
        cut = doc.addObject("Part::Cut", "Cut")
        cut.Base, cut.Tool = body, screw
        doc.recompute()
        self.assertEqual([o.Label for o in self.session.bodies()], ["Cut"])

    def test_6_snapshot_sizes(self):
        from agentlink.families import view

        self.assertEqual(view.snap_size(800, 600, 2), (2, 1, 400, 600))
        self.assertEqual(view.snap_size(400, 300, 2, cell=True), (2, 1, 400, 300))
        self.assertEqual(view.snap_size(400, 300, 4, cell=True), (2, 2, 400, 300))
        p = os.path.join(tempfile.mkdtemp(), "x.png")
        from agentlink import render
        import numpy as np

        with open(p, "wb") as f:
            f.write(render.png(np.zeros((30, 50, 3))))
        self.assertEqual(view.png_size(p), (50, 30))
        self.assertIsNone(view.png_size(p + ".none"))


if __name__ == "__main__":
    unittest.main()
