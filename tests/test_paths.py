# SPDX-License-Identifier: LGPL-2.1-or-later
# Where the agent may read and write: credentials, hidden settings, scripts
# and places outside the home and session folders are refused.
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentlink import paths  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402


class T:
    def __init__(self, name):
        self.name = name


class Paths(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()

    def refused(self, tool, args):
        with self.assertRaises(ToolError):
            paths.guard(T(tool), args, self.out)

    def fine(self, tool, args):
        paths.guard(T(tool), args, self.out)

    def test_writes(self):
        self.fine("export", {"path": "part.step"})
        self.fine("export", {"path": os.path.join(self.out, "sub", "part.stl")})
        self.fine("cam_post", {"path": "~/Desktop/part.nc"})
        self.refused("export", {"path": "~/.zshrc"})
        self.refused("export", {"path": "~/.ssh/authorized_keys"})
        self.refused("export", {"path": "run.sh"})
        self.refused("doc_save", {"path": "/etc/hosts"})
        self.refused("export", {"path": "~/Library/LaunchAgents/x.plist"})
        self.refused("view_render", {"path": "~/.hidden/x.png"})
        self.refused("td_title", {"export": "~/.config/x.json"})
        self.refused("cam_library", {"action": "export", "path": "tools.py"})

    def test_session_files(self):
        # Relative paths, given or made from a default, land in the session's
        # folder; in_file and out_file refuse what guard refuses.
        s = type("S", (), {"out_dir": self.out})()
        out = os.path.realpath(self.out)
        for rel in ("part.stl", "sub/part.stl", "render_iso"):
            for p in (paths.local(s, rel), paths.out_file(s, "view_render", rel, ".png"), paths.in_file(s, "insp_run", rel, "file")):
                self.assertTrue(os.path.realpath(p).startswith(out + os.sep), p)
        self.assertEqual(paths.out_file(s, "view_render", "a.PNG", ".png"), os.path.join(self.out, "a.PNG"))
        self.assertEqual(paths.out_file(s, "view_render", "a", ".png"), os.path.join(self.out, "a.png"))
        self.assertEqual(paths.local(s, "~/x.stl"), os.path.expanduser("~/x.stl"))
        # "~/x" is home here too: paths.check reads it so (bim_export, 17 Nov).
        self.assertEqual(paths.local(s, "~/x.stl", expand=False), os.path.expanduser("~/x.stl"))
        with self.assertRaises(ToolError):
            paths.out_file(s, "view_render", "~/.ssh/x", ".png")
        with self.assertRaises(ToolError):
            paths.in_file(s, "insp_run", "~/.aws/credentials", "file")
        with self.assertRaises(ToolError):
            paths.out_file(s, "meshobj_export", "/etc/x.stl")

    def test_reads(self):
        self.fine("import_file", {"path": "/Volumes/scans/part.stl"})
        self.fine("draft_text", {"font": "/System/Library/Fonts/Helvetica.ttc"})
        self.refused("sheet_import", {"path": "~/.ssh/id_rsa"})
        self.refused("import_file", {"path": "~/.aws/credentials"})

    def test_geometric_paths_pass(self):
        self.fine("part_sweep", {"path": "Helix"})
        self.fine("bim_frame", {"path": ".weird label"})


if __name__ == "__main__":
    unittest.main()


class TildeAlways(unittest.TestCase):
    def test_tilde_is_home_even_without_expand(self):
        import types
        from agentlink import paths
        s = types.SimpleNamespace(out_dir="/tmp/out")
        got = paths.local(s, "~/AgentLink/x.ifc", expand=False)
        self.assertEqual(got, os.path.expanduser("~/AgentLink/x.ifc"))
        self.assertEqual(paths.local(s, "x.ifc", expand=False), "/tmp/out/x.ifc")


class AgentLinkState(unittest.TestCase):
    """Red team 2, R2-13: no tool writes Agent Link's own state files in its
    home; port drafts and the output folder stay open."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self._env = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = self.home

    def tearDown(self):
        if self._env is None:
            os.environ.pop("AGENTLINK_HOME", None)
        else:
            os.environ["AGENTLINK_HOME"] = self._env

    def test_a_json_writer_cannot_write_the_state(self):
        for out in (self.home, tempfile.mkdtemp()):
            for name in ("settings.json", "approvals.log", "memory-stop.json", "addon-sources.json", "hidden.json",
                         "launch.json", "extensions.json", "SETTINGS.JSON", "usage/x.jsonl", "cookbooks/a.json"):
                with self.assertRaises(ToolError, msg=(out, name)):
                    paths.guard(T("sheet_export"), {"path": os.path.join(self.home, name)}, out)
                with self.assertRaises(ToolError, msg=(out, name)):
                    paths.guard(T("td_title"), {"export": os.path.join(self.home, name)}, out)

    def test_ports_and_the_output_folder_stay_open(self):
        paths.guard(T("export"), {"path": os.path.join(self.home, "part.step")}, self.home)
        paths.guard(T("export"), {"path": os.path.join(self.home, "sub", "data.json")}, self.home)
        paths.guard(T("export"), {"path": os.path.join(self.home, "ports", "x", "cookbook.json")}, tempfile.mkdtemp())
        # An output folder elsewhere: the rest of the home is closed.
        with self.assertRaises(ToolError):
            paths.guard(T("export"), {"path": os.path.join(self.home, "part.step")}, tempfile.mkdtemp())
        # Reading the state stays open.
        paths.guard(T("import_file"), {"path": os.path.join(self.home, "settings.json")}, self.home)

    def test_ordinary_output_at_the_top_of_the_home_is_open(self):
        # outDir ~/AgentLink (the Mac): exports, batch "to" files, reports
        # and chained JSON at the top of the output folder are written.
        out = self.home
        for name in ("part.step", "part.stl", "plate.3mf", "view.png", "qa-r213-to.json", "report.json",
                     "chain.json", "notes.log", "data.jsonl", "settings-copy.json", "my-settings.json"):
            paths.guard(T("export"), {"path": os.path.join(out, name)}, out)
            paths.check("batch", "calls.1.to", name, out, True)
            paths.check("batch", "to", os.path.join(out, name), out, True)

    def test_state_names_and_their_copies_are_refused(self):
        out = self.home
        for name in ("settings.json.tmp", "queue.lock", "heartbeat.json", "printers.json", "outputs.jsonl",
                     ".outputs-clean.json", "watchdog.log", "settings/a.json", "Settings-Log.jsonl"):
            with self.assertRaises(ToolError, msg=name):
                paths.check("batch", "to", os.path.join(out, name), out, True)

    def test_the_output_record_is_refused_in_any_output_folder(self):
        out = tempfile.mkdtemp()
        for name in ("outputs.jsonl", ".outputs-clean.json"):
            with self.assertRaises(ToolError, msg=name):
                paths.check("batch", "to", name, out, True)
        paths.check("batch", "to", os.path.join("sub", "outputs.jsonl"), out, True)

    def test_printer_keys_are_never_read(self):
        # The printers file (API keys): no tool reads, packs, imports
        # or exports it; writes are refused too.
        for args in ({"path": os.path.join(self.home, "printers.json")}, {"file": os.path.join(self.home, "PRINTERS.JSON")},
                     {"files": [os.path.join(tempfile.mkdtemp(), ".agentlink-printers.json")]},
                     {"path": "~/.agentlink-printers.json"}):
            with self.assertRaises(ToolError, msg=args):
                paths.guard(T("import_file"), args, self.home)
            with self.assertRaises(ToolError, msg=args):
                paths.guard(T("export"), args, self.home)
        # A printers.json elsewhere (an add-on's own data) stays readable.
        paths.guard(T("import_file"), {"path": os.path.join(tempfile.mkdtemp(), "printers.json")}, self.home)

    def test_cookbook_probes_is_not_a_state_folder(self):
        self.assertNotIn("cookbook-probes", paths.STATE_DIRS)
