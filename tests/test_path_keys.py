# SPDX-License-Identifier: LGPL-2.1-or-later
# An add-on's own path fields, nested ones too (red team 3, R3-10), and the
# write fields of an add-on's tools that write (saveAs, export, path).
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentlink import paths  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402


class T:
    def __init__(self, name):
        self.name = name


class Base(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out, True)
        self.was = ({k: {a: set(b) for a, b in v.items()} for k, v in paths.DECLARED_KEYS.items()}, set(paths.WRITERS))

    def tearDown(self):
        paths.DECLARED_KEYS.clear()
        paths.DECLARED_KEYS.update(self.was[0])
        paths.WRITERS.clear()
        paths.WRITERS.update(self.was[1])

    def refused(self, tool, args):
        with self.assertRaises(ToolError, msg=args):
            paths.guard(T(tool), args, self.out)

    def fine(self, tool, args):
        paths.guard(T(tool), args, self.out)


class Nested(Base):
    def test_values_at(self):
        a = {"texture": {"file": "t.png"}, "profiles": {"machine": "m.json", "process": "p.json"}, "parts": [{"file": "a.stl"}, {"file": "b.stl"}]}
        self.assertEqual(paths.values_at(a, "texture.file"), [("texture.file", "t.png")])
        self.assertEqual(sorted(v for _, v in paths.values_at(a, "profiles.*")), ["m.json", "p.json"])
        self.assertEqual([v for _, v in paths.values_at(a, "parts.file")], ["a.stl", "b.stl"])
        self.assertEqual([v for _, v in paths.values_at(a, "parts.*.file")], ["a.stl", "b.stl"])
        self.assertEqual(paths.values_at(a, "nothing.here"), [])

    def test_declared_read_keys_are_checked(self):
        self.assertEqual(paths.declare_keys("standin_tex", read=["texture.file", "profiles.*", "kicadPcb"]), [])
        self.refused("standin_tex", {"texture": {"file": "~/.ssh/id_rsa"}})
        self.refused("standin_tex", {"profiles": {"machine": "~/.aws/credentials"}})
        self.refused("standin_tex", {"kicadPcb": "~/.gnupg/x.kicad_pcb"})
        self.refused("standin_tex", {"profiles": {"machine": ["ok.json", "~/.ssh/config"]}})
        # Reads stay open elsewhere: ~/Library (an app's presets), a file
        # outside the home.
        self.fine("standin_tex", {"texture": {"file": "/usr/share/t.png"}, "profiles": {"machine": "~/Library/Application Support/x/m.json"}})
        # Other tools are not changed by this declaration.
        self.fine("other_tool", {"texture": {"file": "~/.ssh/id_rsa"}})

    def test_declared_write_keys_are_checked_as_writes(self):
        paths.declare_keys("standin_out", write=["result.to", "sheets.*"])
        self.refused("standin_out", {"result": {"to": "/etc/x.json"}})
        self.refused("standin_out", {"sheets": ["a.pdf", "run.sh"]})
        self.fine("standin_out", {"result": {"to": "x.json"}, "sheets": ["a.pdf"]})

    def test_bad_keys_are_left_out(self):
        self.assertEqual(paths.declare_keys("standin_bad", read=["ok.key", "", "a..b", "a b", 3]), ["", "a..b", "a b", 3])
        self.assertEqual(paths.DECLARED_KEYS["standin_bad"]["read"], {"ok.key"})


class WriterFields(Base):
    """An add-on tool declared as a writer (a family's WRITERS, tools.json
    writes): path, saveAs and export are checked as writes."""

    def test_writer_path_save_as_and_export(self):
        paths.WRITERS.add("standin_project")
        for k in ("path", "saveAs"):
            self.refused("standin_project", {k: "/etc/x.3mf"})
            self.refused("standin_project", {k: "~/Library/LaunchAgents/x.3mf"})
            self.fine("standin_project", {k: "plate.3mf"})
        self.refused("standin_project", {"export": "/etc/x.gcode"})
        # An export format word is a name in the output folder: fine.
        self.fine("standin_project", {"export": "gcode"})

    def test_save_as_is_a_write_for_any_tool(self):
        self.refused("standin_reader", {"saveAs": "/etc/x.3mf"})
        self.refused("standin_reader", {"saveAs": "~/.ssh/x.3mf"})
        self.fine("standin_reader", {"path": "/usr/share/x.3mf", "saveAs": "copy.3mf"})


class Declarations(Base):
    def test_tools_json_path_keys(self):
        from agentlink import tooldata

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        entry = {"group": "standin", "description": "A stand-in tool with nested path fields.", "inputSchema": {"type": "object", "properties": {}},
                 "changes": False, "source": "test", "date": "2026-11-19", "pathKeys": ["texture.file", "profiles.*"], "writeKeys": ["report.to"]}
        doc = {"dataVersion": "1.0.0", "licence": "CC-BY-4.0", "about": "Stand-in.", "entries": {"standin_nested": entry}}
        with open(os.path.join(tmp, "tools.json"), "w") as f:
            json.dump(doc, f)
        tooldata.build(tmp, "standin", {"standin_nested": lambda a: 1})
        self.refused("standin_nested", {"texture": {"file": "~/.ssh/id_rsa"}})
        self.refused("standin_nested", {"report": {"to": "/etc/r.json"}})
        self.fine("standin_nested", {"texture": {"file": "t.png"}, "report": {"to": "r.json"}})
        bad = dict(doc, entries={"standin_nested": dict(entry, pathKeys=["a..b"])})
        self.assertTrue(any("pathKeys" in p for p in tooldata.check(bad)))

    def test_tools_json_with_a_hub_name_declares_nothing(self):
        from agentlink import tooldata

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        entry = {"group": "standin", "description": "A stand-in tool that takes the hub's name.", "inputSchema": {"type": "object", "properties": {}},
                 "changes": False, "source": "test", "date": "2026-11-19", "pathKeys": ["x.y"]}
        with open(os.path.join(tmp, "tools.json"), "w") as f:
            json.dump({"dataVersion": "1.0.0", "licence": "CC-BY-4.0", "about": "Stand-in.", "entries": {"import_file": entry}}, f)
        tooldata.build(tmp, "standin", {"import_file": lambda a: 1})
        self.assertNotIn("import_file", paths.DECLARED_KEYS)

    def test_family_path_keys_count_for_its_own_tools_only(self):
        from agentlink import families

        fam = types.SimpleNamespace(EXTERNAL=True, EXTENSION="standin.agentlink_families", WRITERS={"standin_slice"},
                                    PATH_KEYS={"standin_paint": ["texture.file"], "export": ["x"]}, WRITE_KEYS={"standin_slice": "out.file"})
        families.declared([fam])
        families.owned(fam, ["standin_paint", "standin_slice"])
        self.assertNotIn("export", paths.DECLARED_KEYS)
        self.refused("standin_paint", {"texture": {"file": "~/.ssh/id_rsa"}})
        self.refused("standin_slice", {"out": {"file": "/etc/a.gcode"}})
        self.refused("standin_slice", {"path": "/etc/a.3mf"})
        self.fine("standin_slice", {"path": "a.3mf", "out": {"file": "a.gcode"}})


if __name__ == "__main__":
    unittest.main()
