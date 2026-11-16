# SPDX-License-Identifier: LGPL-2.1-or-later
# The tool index (agentlink/data/tool_index.json): current with its
# generator, covering every tool this repository defines, consistent with
# the live echo's tables, its commands real FreeCAD 1.1 commands; and the
# search and "fits now" ranking that read it (agentlink/toolindex.py).
# Plain Python: no FreeCAD.
import json
import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import tool_index  # noqa: E402
import tool_index_more as more  # noqa: E402

from agentlink import echo, tooldata, toolindex  # noqa: E402

DATA = os.path.join(ROOT, "agentlink", "data")


def _json(*p):
    with open(os.path.join(*p), encoding="utf-8") as f:
        return json.load(f)


def _known_commands():
    with open(os.path.join(ROOT, "docs", "hardening", "freecad-1.1.0-commands.txt"), encoding="utf-8") as f:
        return {ln.strip() for ln in f if ln.strip() and not ln.startswith("#")}


class Index(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(DATA, "tool_index.json")
        cls.entries = cls.doc["entries"]

    def test_current(self):
        with open(os.path.join(DATA, "tool_index.json"), encoding="utf-8") as f:
            self.assertEqual(f.read(), tool_index.render(), "run python3 scripts/tool_index.py")
        self.assertEqual(tool_index.main(["--check"]), 0)

    def test_every_tool_of_this_repository(self):
        self.assertEqual(sorted(self.entries), tool_index.tool_names())
        inv = _json(ROOT, "docs", "hardening", "inventory.json")
        here = set(tool_index.tool_names())
        # The inventory was read off a live server with add-ons installed:
        # what it files under this repository and is defined here is indexed.
        mine = {t for g in inv["groups"].values() if g["repo"] == "AgentLink-FreeCAD" for t in g["tools"]} & here
        self.assertGreater(len(mine), 380)
        self.assertEqual(sorted(mine - set(self.entries)), [])

    def test_schema(self):
        schema = _json(DATA, "tool_index.schema.json")
        props = schema["properties"]
        self.assertEqual(self.doc["$schema"], "tool_index.schema.json")
        self.assertEqual(self.doc["licence"], "CC-BY-4.0")
        for name, e in self.entries.items():
            self.assertEqual(sorted(e), sorted(schema["required"]), name)
            self.assertTrue(e["workbench"] is None or re.match(props["workbench"]["pattern"], e["workbench"]), name)
            self.assertTrue(e["workbench"] is None or e["workbench"] in toolindex.WORKBENCHES, f"{name}: {e['workbench']}")
            for c in e["commands"]:
                self.assertRegex(c, props["commands"]["items"]["pattern"], name)
            for w in e["words"]:
                self.assertRegex(w, props["words"]["items"]["pattern"], name)
                self.assertNotIn(w, name.split("_"), f"{name}: {w} is already in the name")
            self.assertEqual(len(e["commands"]), len(set(e["commands"])), name)
            self.assertEqual(len(e["words"]), len(set(e["words"])), name)

    def test_commands_are_freecads(self):
        known = _known_commands()
        self.assertGreater(len(known), 1000)
        bad = sorted({f"{n}: {c}" for n, e in self.entries.items() for c in e["commands"] if c not in known})
        self.assertEqual(bad, [], "not a FreeCAD 1.1 command (docs/hardening/freecad-1.1.0-commands.txt)")

    def test_the_echo_is_the_source(self):
        known = _known_commands()
        for name, cmd in echo.COMMAND.items():
            self.assertIn(cmd, known, f"echo.COMMAND[{name!r}]")
            if name in self.entries:
                self.assertEqual(self.entries[name]["commands"][0], cmd, name)
        for cmd in list(echo.CAM_OP.values()) + list(echo.CAM_DRESSUP.values()):
            self.assertIn(cmd, known)
        self.assertLessEqual(set(echo.CAM_OP.values()), set(self.entries["cam_op"]["commands"]))
        self.assertLessEqual(set(echo.CAM_DRESSUP.values()), set(self.entries["cam_dressup"]["commands"]))
        self.assertIn("Assembly_CreateJointRackPinion", self.entries["asm_joint"]["commands"])
        for name, e in self.entries.items():
            wb = echo._workbench_for(name)
            if wb:
                self.assertEqual(e["workbench"], wb, name)

    def test_additions_name_real_tools(self):
        names = set(tool_index.tool_names())
        self.assertEqual(sorted(set(more.TOOLS) - names), [])
        self.assertEqual(sorted(names - set(more.TOOLS)), [], "a new tool: give it a line in scripts/tool_index_more.py")

    def test_samples(self):
        e = self.entries
        self.assertEqual(e["pd_fillet"]["workbench"], "PartDesignWorkbench")
        self.assertEqual(e["pd_fillet"]["commands"], ["PartDesign_Fillet"])
        self.assertIn("round", e["pd_fillet"]["words"])
        self.assertIn("drawing", e["td_dim"]["words"])
        self.assertIn("TechDraw_LengthDimension", e["td_dim"]["commands"])
        self.assertIsNone(e["session_state"]["workbench"])
        self.assertEqual(e["bim_wall"]["commands"], ["Arch_Wall"])


class AddOnFields(unittest.TestCase):
    def _doc(self, **more_fields):
        return {"dataVersion": "1.0.0", "entries": {"mesh_thin": {
            "group": "meshtools", "description": "Thin a mesh down to fewer triangles.", "inputSchema": {"type": "object", "properties": {}},
            "changes": True, "source": "test", "date": "2026-11-16", **more_fields}}}

    def test_optional_fields(self):
        self.assertEqual(tooldata.check(self._doc()), [])
        self.assertEqual(tooldata.check(self._doc(workbench="MeshWorkbench", commands=["Mesh_Decimating"], words=["reduce"])), [])
        self.assertTrue(tooldata.check(self._doc(workbench=["MeshWorkbench"])))
        self.assertTrue(tooldata.check(self._doc(commands="Mesh_Decimating")))
        self.assertTrue(tooldata.check(self._doc(words=["ok", 3])))
        props = _json(DATA, "tools.schema.json")["properties"]["entries"]["additionalProperties"]["properties"]
        for k in toolindex.FIELDS:
            self.assertIn(k, props)
            self.assertIn(k, tooldata.OPTIONAL)

    def test_declared_entry_and_fallback(self):
        saved = dict(toolindex.EXTRA)
        try:
            toolindex.declare("mesh_thin", {"workbench": "MeshWorkbench", "commands": ["Mesh_Decimating"], "words": ["Reduce"], "group": "x"})
            self.assertEqual(toolindex.entry("mesh_thin"), {"workbench": "MeshWorkbench", "commands": ["Mesh_Decimating"], "words": ["reduce"]})
            toolindex.declare("mesh_plain", {"group": "x"})
            self.assertNotIn("mesh_plain", toolindex.EXTRA)
            # Nothing declared: what the family told the echo, when given.
            self.assertEqual(toolindex.entry("zz_other"), {"workbench": None, "commands": [], "words": []})
            self.assertEqual(toolindex.entry("zz_other", lambda n: ("MeshWorkbench", "Mesh_Smoothing")),
                             {"workbench": "MeshWorkbench", "commands": ["Mesh_Smoothing"], "words": []})

            def boom(_n):
                raise RuntimeError("an add-on's callable")

            self.assertEqual(toolindex.entry("zz_other", boom)["commands"], [])
            # The index wins for Agent Link's own tools.
            self.assertEqual(toolindex.entry("pd_fillet", lambda n: ("X", "Y"))["commands"], ["PartDesign_Fillet"])
        finally:
            toolindex.EXTRA.clear()
            toolindex.EXTRA.update(saved)

    def test_missing_index_is_no_error(self):
        self.assertEqual(toolindex.load(os.path.join(DATA, "no_such_index.json")), {})


def _rows():
    """Every tool of this repository with its description, read from the
    source as the README's table is (no FreeCAD)."""
    import ast

    pkg = os.path.join(ROOT, "agentlink")
    out = {}

    def text(node, consts):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return "".join(v.value if isinstance(v, ast.Constant) else "…" for v in node.values)
        if isinstance(node, ast.BinOp):
            return (text(node.left, consts) or "") + (text(node.right, consts) or "")
        if isinstance(node, ast.Name):
            return consts.get(node.id)
        return None

    for folder in (pkg, os.path.join(pkg, "families")):
        for f in sorted(os.listdir(folder)):
            if not f.endswith(".py"):
                continue
            with open(os.path.join(folder, f), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            consts = {}
            for n in ast.walk(tree):
                if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                    got = text(n.value, consts)
                    if got:
                        consts[n.targets[0].id] = got
            group = consts.get("GROUP", "core")
            for n in ast.walk(tree):
                fn = getattr(n, "func", None)
                if isinstance(n, ast.Call) and (getattr(fn, "id", None) == "Tool" or getattr(fn, "attr", None) == "Tool") and len(n.args) > 1:
                    if isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                        out[n.args[0].value] = {"description": text(n.args[1], consts) or "", "group": group}
    for name, e in _json(DATA, "tools.json")["entries"].items():
        out[name] = {"description": e["description"], "group": e["group"]}
    return [{"name": k, "about": "", "entry": toolindex.entry(k), **v} for k, v in sorted(out.items()) if k != "export_file"]


class Find(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()

    def names(self, find, n=5):
        return [r["name"] for r, _m, _s in toolindex.rank(self.rows, find)[:n]]

    def test_the_live_findings(self):
        # "fillet edges" put two unrelated tools above pd_fillet; "drawing
        # dimension" missed td_dim (nothing in its name says drawing).
        self.assertEqual(sorted(self.names("fillet edges", 2)), ["part_fillet", "pd_fillet"])
        self.assertEqual(self.names("drawing dimension", 1), ["td_dim"])
        self.assertEqual(self.names("techdraw dimension", 1), ["td_dim"])

    def test_plain_words(self):
        for find, want in (("round edge", "pd_fillet"), ("mesh decimate", "meshobj_decimate"), ("simplify stl", "meshobj_decimate"),
                           ("extrude sketch", "pd_pad"), ("hole", "pd_hole"), ("bill of materials", "asm_bom"), ("undo", "history_undo"),
                           ("sketch constraint", "sketch_constrain"), ("sweep along path", "pd_pipe"), ("gcode", "cam_post"),
                           ("bim wall", "bim_wall"), ("save", "doc_save"), ("linear pattern", "pd_linear_pattern")):
            self.assertIn(want, self.names(find, 3), find)

    def test_freecads_own_names(self):
        self.assertEqual(self.names("PartDesign_Pad", 1), ["pd_pad"])
        self.assertEqual(self.names("Sketcher_CarbonCopy", 1), ["sketch_carbon"])
        self.assertEqual(self.names("TechDraw_Balloon", 1), ["td_balloon"])
        self.assertEqual(self.names("Mesh_Decimating", 1), ["meshobj_decimate"])

    def test_a_workbench_word_lifts_its_tools(self):
        for find, prefix in (("drawing section", "td_"), ("sketch mirror", "sketch_"), ("mesh smooth", "meshobj_"), ("bim pipe", "bim_")):
            self.assertTrue(self.names(find, 1)[0].startswith(prefix), f"{find}: {self.names(find)}")
        self.assertEqual(toolindex.workbenches_named({"drawing"}), {"TechDrawWorkbench"})
        self.assertEqual(toolindex.workbenches_named({"sketch", "mesh"}), {"SketcherWorkbench", "MeshWorkbench"})

    def test_every_word_counts(self):
        hits = toolindex.rank(self.rows, "fillet edges")
        counts = [m for _r, m, _s in hits]
        self.assertEqual(counts, sorted(counts, reverse=True))
        self.assertEqual(hits[0][1], 2)
        self.assertEqual(toolindex.rank(self.rows, "zzqqxx"), [])
        self.assertEqual(toolindex.rank(self.rows, "  "), [])
        self.assertEqual(toolindex.query_words("how to fillet the edges"), ["fillet", "edge"])
        self.assertEqual(toolindex.query_words("to"), ["to"])

    def test_bonus(self):
        plain = self.names("fillet edges", 2)
        lifted = [r["name"] for r, _m, _s in toolindex.rank(self.rows, "fillet edges", bonus=lambda r: 50 if r["name"] == "part_chamfer" else 0)[:1]]
        self.assertEqual(lifted, ["part_chamfer"])
        self.assertNotIn("part_chamfer", plain)


class FirstSentence(unittest.TestCase):
    def test_not_cut_at_a_colon(self):
        s = toolindex.first_sentence("Round edges of the body: edges [{ near: [x,y,z] }], radius mm (1). Reply: feature, volume.")
        self.assertEqual(s, "Round edges of the body: edges [{ near: [x,y,z] }], radius mm (1).")

    def test_decimals_and_abbreviations(self):
        self.assertEqual(toolindex.first_sentence("Sew faces within 0.01 mm, e.g. Two shells. Then check."), "Sew faces within 0.01 mm, e.g. Two shells.")
        self.assertEqual(toolindex.first_sentence("Redo what was undone (steps: how many)."), "Redo what was undone (steps: how many).")
        self.assertEqual(toolindex.first_sentence(""), "")
        self.assertEqual(toolindex.first_sentence(None), "")

    def test_long_ones_are_cut_at_a_word(self):
        s = toolindex.first_sentence("word " * 80 + ". Next.")
        self.assertLessEqual(len(s), 162)
        self.assertTrue(s.endswith(" …"))
        for r in _rows():
            self.assertLessEqual(len(toolindex.first_sentence(r["description"])), 162, r["name"])
            self.assertGreater(len(toolindex.first_sentence(r["description"])), 15, r["name"])


class FitsNow(unittest.TestCase):
    def setUp(self):
        self.e = toolindex.load()

    def state(self, **kw):
        return {"window": True, "workbench": None, "editing": None, "selBenches": set(), "selSubs": set(), "docBenches": set(), "active": {}, **kw}

    def test_workbench_and_command(self):
        st = self.state(workbench="PartDesignWorkbench", active={"PartDesign_Fillet": True, "PartDesign_Pad": False})
        fillet, why = toolindex.fits(self.e["pd_fillet"], st)
        pad, why_pad = toolindex.fits(self.e["pd_pad"], st)
        dim, _ = toolindex.fits(self.e["td_dim"], st)
        self.assertGreater(fillet, pad)
        self.assertGreater(pad, dim)
        self.assertIn("command active", why)
        self.assertIn("command inactive", why_pad)
        self.assertEqual(dim, 0)

    def test_unknown_commands_count_for_nothing(self):
        st = self.state(workbench="TechDrawWorkbench", active={})
        self.assertEqual(toolindex.fits(self.e["td_dim"], st), (4, ["workbench"]))
        self.assertEqual(toolindex.fits({"workbench": None, "commands": ["No_SuchCommand"], "words": []}, st), (0, []))

    def test_sketch_in_edit(self):
        st = self.state(workbench="SketcherWorkbench", editing="sketch")
        self.assertIn("sketch open", toolindex.fits(self.e["sketch_add"], st)[1])
        self.assertGreater(toolindex.fits(self.e["sketch_add"], st)[0], toolindex.fits(self.e["pd_pad"], st)[0])

    def test_selection(self):
        st = self.state(selBenches={"MeshWorkbench"}, selSubs={"edge"})
        self.assertIn("selection", toolindex.fits(self.e["meshobj_decimate"], st)[1])
        self.assertIn("edge picked", toolindex.fits(self.e["pd_fillet"], st, {"edges": {}, "radius": {}})[1])
        self.assertEqual(toolindex.fits(self.e["pd_pad"], st, {"sketch": {}})[0], 0)

    def test_headless_goes_by_the_document(self):
        st = self.state(window=False, docBenches={"MeshWorkbench"})
        self.assertEqual(toolindex.fits(self.e["meshobj_decimate"], st), (3, ["document"]))
        self.assertEqual(toolindex.fits(self.e["td_dim"], st)[0], 0)
        none = self.state(window=False, docBenches=None)
        self.assertIn("no document", toolindex.fits(self.e["doc_new"], none)[1])
        self.assertEqual(toolindex.fits(self.e["pd_pad"], none)[0], 0)

    def test_bench_of(self):
        self.assertEqual(toolindex.bench_of("Sketcher::SketchObject"), "SketcherWorkbench")
        self.assertEqual(toolindex.bench_of("PartDesign::Pad"), "PartDesignWorkbench")
        self.assertEqual(toolindex.bench_of("Part::FeaturePython", "draftobjects.wire"), "DraftWorkbench")
        self.assertEqual(toolindex.bench_of("Part::FeaturePython", "ArchWall"), "BIMWorkbench")
        self.assertEqual(toolindex.bench_of("Part::FeaturePython", "builtins"), "PartWorkbench")
        self.assertEqual(toolindex.bench_of("Mesh::Feature"), "MeshWorkbench")
        self.assertIsNone(toolindex.bench_of("App::DocumentObjectGroup"))
        self.assertIsNone(toolindex.bench_of(None))


if __name__ == "__main__":
    unittest.main()
