# SPDX-License-Identifier: LGPL-2.1-or-later
# Red team 4 on the hub (R4-1, 3, 5, 8, 10, 11 and the "gcode" kind):
# each test is the attack of the report, refused; and the legitimate use,
# still open. Plain Python, no FreeCAD.
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from agentlink import approvals, chain, hooks, meshformats, paths  # noqa: E402
from agentlink.protocol import Server, Tool, ToolError  # noqa: E402


class T:
    def __init__(self, name):
        self.name = name


class Reads(unittest.TestCase):
    """R4-1: reads are an allow list."""

    def setUp(self):
        self.out = tempfile.mkdtemp(prefix="agentlink-r4-")
        self.addCleanup(shutil.rmtree, self.out, True)

    def refused(self, p, tool="import_file", key="path"):
        with self.assertRaises(ToolError, msg=p):
            paths.guard(T(tool), {key: p}, self.out)

    def fine(self, p, tool="import_file", key="path"):
        paths.guard(T(tool), {key: p}, self.out)

    def test_the_claude_config_is_never_read(self):
        self.refused("~/Library/Application Support/Claude/claude_desktop_config.json")
        # by its name, in any folder (the session's folder too)
        p = os.path.join(self.out, "claude_desktop_config.json")
        self.refused(p)
        with self.assertRaises(ToolError):
            paths.check("export", "path", p, self.out, True)

    def test_library_is_refused_but_the_tools_own_folders(self):
        self.refused("~/Library/Application Support/Google/Chrome/Local State")
        self.refused("~/Library/Cookies/Cookies.binarycookies")
        self.refused("~/library/application support/claude/x.json")  # any case
        self.fine("~/Library/Application Support/FreeCAD/Mod/x/data.json")
        self.fine("~/Library/Application Support/OrcaSlicer/user/default/filament/PLA.json")
        self.fine("~/Library/Application Support/BambuStudio/system/x.json")
        self.fine("~/Library/Fonts/Inter.ttf", "draft_text", "font")

    def test_hidden_files_and_folders_in_the_home_are_refused(self):
        for p in ("~/.git-credentials", "~/.npmrc", "~/.pypirc", "~/.zsh_history", "~/.bash_history", "~/.ollama/id_ed25519",
                  "~/Documents/.secret/x.json", "~/.ssh/id_ed25519", "~/.aws/credentials", "~/.config/x/y.json"):
            self.refused(p)

    def test_outside_the_open_places_is_refused(self):
        self.refused("/etc/passwd")
        self.refused("/private/etc/master.passwd")
        self.refused("/var/root/x.json")

    def test_ordinary_reads_stay_open(self):
        self.fine("~/Documents/scan.stl")
        self.fine("~/Desktop/part.step")
        self.fine("part.stl")  # the session's folder
        self.fine(os.path.join(tempfile.gettempdir(), "x.stl"))
        self.fine("/Volumes/scans/part.stl")
        self.fine("/Applications/OrcaSlicer.app/Contents/Resources/profiles/x.json")
        self.fine("/System/Library/Fonts/Helvetica.ttc", "draft_text", "font")
        # the add-on's own folder (its data files)
        self.fine(os.path.join(os.path.dirname(HERE), "agentlink", "data", "tools.json"))

    def test_a_session_folder_of_the_home_opens_no_hidden_file(self):
        home = os.path.expanduser("~")
        with self.assertRaises(ToolError):
            paths.check("import_file", "path", "~/.zsh_history", home, False)

    def test_freecads_own_folders_are_open(self):
        d = tempfile.mkdtemp(prefix="agentlink-r4-fc-")
        self.addCleanup(shutil.rmtree, d, True)
        fc = type(sys)("FreeCAD")
        fc.getUserAppDataDir = lambda: d
        with mock.patch.dict(sys.modules, {"FreeCAD": fc}):
            self.assertIn(os.path.realpath(d), paths.freecad_dirs())


class FileRefs(unittest.TestCase):
    """R4-1: a batch $file uses the read check, and a miss lists a folder
    only when the read rule opens it."""

    def test_a_miss_lists_nothing_without_leave(self):
        d = tempfile.mkdtemp(prefix="agentlink-r4-")
        self.addCleanup(shutil.rmtree, d, True)
        chain.write_answer(os.path.join(d, "secret-token.json"), {})
        with self.assertRaises(chain.Miss) as e:
            chain.read_json(os.path.join(d, "want.json"), "want.json")
        self.assertNotIn("secret-token", e.exception.message)
        with self.assertRaises(chain.Miss) as e:
            chain.read_json(os.path.join(d, "want.json"), "want.json", may_list=lambda f: False)
        self.assertNotIn("secret-token", e.exception.message)
        with self.assertRaises(chain.Miss) as e:
            chain.read_json(os.path.join(d, "want.json"), "want.json", may_list=lambda f: True)
        self.assertIn("secret-token.json", e.exception.message)

    def test_the_batch_file_reference_is_refused_in_library(self):
        from test_hubfix2 import in_a_process
        from test_hubfix4 import SETUP

        out = tempfile.mkdtemp(prefix="agentlink-r4-")
        self.addCleanup(shutil.rmtree, out, True)
        got = in_a_process(SETUP + '''
    from agentlink import tools
    s = tools.Session(out_dir=%r)
    srv = tools.build_server(s, lean=False)
    def call(name, args):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
        return [r.get("isError", False), json.loads(r["content"][0]["text"])]
    ref = {"$file": "~/Library/Application Support/Claude/claude_desktop_config.json", "$at": "mcpServers"}
    a = call("batch", {"calls": [{"tool": "tool_find", "words": ref}], "rollback": False})
    b = call("batch", {"calls": [{"tool": "tool_find", "words": {"$file": "~/Library/Safari/nothere.json"}}], "rollback": False})
    c = call("tool_find", {"listing": True, "to": "~/Library/Application Support/Claude/x.json"})
    d = call("tool_find", {"listing": True, "to": "listing.json"})
    print(json.dumps({"a": a, "b": b, "c": c, "d": d}))
''' % out)
        text = json.dumps(got["a"])
        self.assertIn("claude_desktop_config.json", text)
        self.assertIn("Claude's own settings", text)
        self.assertNotIn("mcpServers\": {", text)
        self.assertIn("~/Library", json.dumps(got["b"]))
        # R4-3: tool_find { listing, to } is a write and gets the write check
        self.assertTrue(got["c"][0], got["c"])
        self.assertIn("Library", got["c"][1]["error"]["message"])
        self.assertFalse(got["d"][0], got["d"])
        self.assertTrue(os.path.isfile(os.path.join(out, "listing.json")))


def _gltf(folder, uri, n=3, byte_length=None):
    """A one-triangle glTF in folder whose buffer has this uri."""
    raw = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    doc = {"asset": {"version": "2.0"}, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": n, "type": "VEC3"}],
           "bufferViews": [{"buffer": 0, "byteLength": len(raw)}],
           "buffers": [{"uri": uri(raw) if callable(uri) else uri, "byteLength": len(raw) if byte_length is None else byte_length}]}
    p = os.path.join(folder, "m.gltf")
    with open(p, "w") as f:
        json.dump(doc, f)
    return p, raw


class GltfBuffers(unittest.TestCase):
    """R4-5: a glTF buffer is a file beside it or a data: URI, capped."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="agentlink-r4-gltf-")
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_a_buffer_beside_the_file_reads(self):
        p, raw = _gltf(self.d, "m.bin")
        with open(os.path.join(self.d, "m.bin"), "wb") as f:
            f.write(raw)
        V, F, _ = meshformats.read(p)
        self.assertEqual(len(V), 3)

    def test_a_data_uri_reads(self):
        import base64

        p, _ = _gltf(self.d, lambda raw: "data:application/octet-stream;base64," + base64.b64encode(raw).decode())
        V, F, _ = meshformats.read(p)
        self.assertEqual(len(V), 3)

    def test_absolute_dotdot_and_schemes_are_refused(self):
        outside = tempfile.mkdtemp(prefix="agentlink-r4-key-")
        self.addCleanup(shutil.rmtree, outside, True)
        key = os.path.join(outside, "id_ed25519")
        with open(key, "wb") as f:
            f.write(b"\x01" * 36)
        sub = os.path.join(self.d, "sub")
        os.makedirs(sub)
        rel = os.path.relpath(key, sub)
        for uri in (key, rel, "file://" + key, "%2E%2E/" + os.path.basename(outside) + "/id_ed25519", "~/.ssh/id_ed25519"):
            p, _ = _gltf(sub, uri)
            with self.assertRaises(meshformats.FormatError, msg=uri):
                meshformats.read(p)

    def test_a_link_out_of_the_folder_is_refused(self):
        outside = tempfile.mkdtemp(prefix="agentlink-r4-key-")
        self.addCleanup(shutil.rmtree, outside, True)
        with open(os.path.join(outside, "k.bin"), "wb") as f:
            f.write(b"\x01" * 36)
        os.symlink(os.path.join(outside, "k.bin"), os.path.join(self.d, "m.bin"))
        p, _ = _gltf(self.d, "m.bin")
        with self.assertRaises(meshformats.FormatError):
            meshformats.read(p)

    def test_the_size_is_capped(self):
        p, raw = _gltf(self.d, "m.bin", byte_length=meshformats.MAX_BUFFER + 1)
        with open(os.path.join(self.d, "m.bin"), "wb") as f:
            f.write(raw)
        with self.assertRaises(meshformats.FormatError):
            meshformats.read(p)
        with mock.patch.object(meshformats, "MAX_DATA_URI", 10):
            p, _ = _gltf(self.d, "data:application/octet-stream;base64,AAAAAAAAAAAAAAAAAAAA")
            with self.assertRaises(meshformats.FormatError):
                meshformats.read(p)


class ThreadTools(unittest.TestCase):
    """R4-10: a socket-thread tool gets the path guard too."""

    def test_handle_light_runs_the_guard(self):
        ran = []
        tool = Tool("standin_thread_read", "x", {"type": "object", "properties": {"path": {"type": "string"}}}, lambda a: ran.append(a) or {"ok": True})
        out = tempfile.mkdtemp(prefix="agentlink-r4-")
        self.addCleanup(shutil.rmtree, out, True)
        srv = Server("t", "0", [tool], guard=lambda t, a: paths.guard(t, a, out))
        r = srv.handle_light({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool.name, "arguments": {"path": "~/.ssh/id_rsa"}}})
        self.assertTrue(r["result"].get("isError"), r)
        self.assertEqual(ran, [])
        r = srv.handle_light({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool.name, "arguments": {"path": "x.stl"}}})
        self.assertFalse(r["result"].get("isError"), r)


class Hidden(unittest.TestCase):
    """R4-8: variation selectors and fillers are invisible too."""

    def setUp(self):
        approvals.reset()
        approvals.note_client(None, "claude-ai")  # a client that asks the person first
        self.addCleanup(approvals.reset)

    def test_the_new_characters(self):
        for c in ("️", "︀", "\U000e0100", "\U000e01ef", "͏", "ᅟ", "ᅠ", "ㅤ", "ﾠ", "᠋", "᠏", "⠀"):
            self.assertTrue(approvals.invisible(c), hex(ord(c)))
            self.assertNotIn(c, approvals.clean("a" + c + "b"))
        self.assertFalse(approvals.invisible("é"))

    def test_an_id_with_them_is_refused(self):
        with self.assertRaises(approvals.Refused):
            approvals.ask("cookbook", "my-cook️book", "Run it")
        with self.assertRaises(approvals.Refused):
            approvals.ask("cookbook", "myㅤcookbook", "Run it")

    def test_cookbook_text_with_them_is_refused(self):
        from agentlink import cookbook

        self.assertTrue(cookbook._chars_ok("Makes a box\U000e0101 quietly", "about"))
        self.assertTrue(cookbook._chars_ok("Makesᅟa box", "about"))
        self.assertEqual(cookbook._chars_ok("Makes a box", "about"), [])

    def test_a_non_ascii_host_shows_as_punycode(self):
        t = approvals.source_field("https://gіthub.com/owner/repo")  # Cyrillic і
        self.assertIn("xn--", t)
        self.assertIn("non-ASCII host", t)
        self.assertTrue(t.isascii() or "non-ASCII" in t)
        self.assertNotIn("gіthub", t)
        t = approvals.source_field("git@gіthub.com:owner/repo")
        self.assertIn("xn--", t)
        self.assertEqual(approvals.source_field("https://github.com/owner/repo"), "host: github.com, path: /owner/repo")

    def test_extend_tool_describe_is_cleaned(self):
        hooks.extend_tool("standin_r4_tool", describe="Adds x.‮evil⁦ ️more\U000e0041")
        try:
            d = hooks._EXTENSIONS["standin_r4_tool"][-1]["describe"]
            self.assertEqual(d, "Adds x.evil more")
        finally:
            hooks._EXTENSIONS.pop("standin_r4_tool", None)


def _approval_server():
    def approve(name):
        def fn(a):
            try:
                return approvals.approve(name, a)
            except approvals.Refused as e:
                raise ToolError(e.code, e.message)
        return fn

    def asks(a):
        return approvals.ask("cookbook", "box-maker", "Run the cookbook box-maker", fingerprint="sha256:abc")

    tools = [Tool(n, n, approvals.schema(n), approve(n)) for n in approvals.CLIENT_ONLY]
    tools.append(Tool("standin_asks", "x", {"type": "object", "properties": {}}, asks))
    return Server("t", "0", tools)


def _call(srv, name, args, client):
    r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}, client=client)["result"]
    return bool(r.get("isError")), json.loads(r["content"][0]["text"])


class Connections(unittest.TestCase):
    """R4-11: a pending approval is bound to the connection that asked."""

    def setUp(self):
        approvals.reset()
        approvals.note_client(None, "claude-ai")  # a client that asks the person first
        self.addCleanup(approvals.reset)
        self.srv = _approval_server()
        for conn in ("link-1", "link-2"):
            # each connection's client names itself, as an MCP client does
            self.srv.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"clientInfo": {"name": "claude-ai", "version": "1"}}}, client=conn)

    def test_another_connection_cannot_approve(self):
        err, got = _call(self.srv, "standin_asks", {}, "link-1")
        self.assertTrue(got.get("pending"), got)
        args = got["approve"]["arguments"]
        err, got = _call(self.srv, "approve_code", args, "link-2")
        self.assertTrue(err, got)
        self.assertEqual(got["error"]["code"], "not_allowed")
        self.assertIn("another client connection", got["error"]["message"])
        # the other connection does not see it as waiting either
        with approvals.connection_call("link-2"):
            self.assertEqual(approvals.waiting(), [])
        # the connection that asked approves, and uses its grant
        err, got = _call(self.srv, "approve_code", args, "link-1")
        self.assertFalse(err, got)
        err, got = _call(self.srv, "standin_asks", {}, "link-1")
        self.assertTrue(got.get("ok"), got)
        self.assertNotIn("pending", got)

    def test_a_grant_is_not_used_by_another_connection(self):
        err, got = _call(self.srv, "standin_asks", {}, "link-1")
        _call(self.srv, "approve_code", got["approve"]["arguments"], "link-1")
        err, got = _call(self.srv, "standin_asks", {}, "link-2")
        self.assertTrue(got.get("pending"), got)

    def test_stdio_is_one_connection(self):
        err, got = _call(self.srv, "standin_asks", {}, None)
        err, ok = _call(self.srv, "approve_code", got["approve"]["arguments"], None)
        self.assertFalse(err, ok)


class GcodeKind(unittest.TestCase):
    """OrcaLink asks with kind "gcode": approve_code approves it."""

    def setUp(self):
        approvals.reset()
        approvals.note_client(None, "claude-ai")  # a client that asks the person first
        self.addCleanup(approvals.reset)

    def test_gcode_is_a_code_kind(self):
        self.assertIn("gcode", approvals.KINDS)
        self.assertEqual(approvals.tool_for("gcode"), approvals.CODE_TOOL)
        got = approvals.ask("gcode", "part.3mf", "Write G-code with risky commands", fingerprint="sha256:g1")
        self.assertTrue(got["pending"], got)
        self.assertEqual(got["approve"]["tool"], "approve_code")
        with approvals.client_call("approve_code", got["approve"]["arguments"]):
            approvals.approve("approve_code", got["approve"]["arguments"])
        self.assertEqual(approvals.ask("gcode", "part.3mf", "Write G-code with risky commands", fingerprint="sha256:g1"), {"ok": True})


if __name__ == "__main__":
    unittest.main()
