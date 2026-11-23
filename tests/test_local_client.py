# SPDX-License-Identifier: LGPL-2.1-or-later
# Live findings of 22 Nov: a local model in an MCP client that runs every tool
# without asking the person (OpenCode) on Agent Link.
#   1. Fields that only answers carry (ms, around, saidBefore …), sent back as
#      inputs, are left out and said in readAs, not refused; in a batch's
#      calls too. Empty text for tool_find / tool_groups' optional fields is
#      read as left out.
#   2. approve_file / approve_code approve only from a client known to ask
#      the person first (clientInfo.name in initialize). Any other client:
#      the person approves in FreeCAD's window, or, headless, not at all.
#   3. --own (AGENTLINK_OWN=1): the server never uses the window's link and
#      keeps its run marks apart.
# Plain Python, with stand-ins: no FreeCAD.
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from agentlink import approvals, keep, paths, person_ok, protocol, supervise  # noqa: E402
from agentlink.protocol import Server, Tool, ToolError, check_input  # noqa: E402


def obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


def init(srv, name, conn=None):
    """The MCP client's initialize, as it sends it."""
    return srv.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"clientInfo": {"name": name, "version": "1"}}}, client=conn)


def call(srv, name, args, conn=None):
    r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}, client=conn)["result"]
    return bool(r.get("isError")), json.loads(r["content"][0]["text"])


# ---- 1. answer fields and empty text ---------------------------------------------------------

class AnswerFields(unittest.TestCase):
    def setUp(self):
        got = []

        def echo(a):
            got.append(dict(a))
            return {"got": a}

        def batch(a):
            out = []
            for c in a.get("calls") or []:
                r = srv.call({"name": c["tool"], "arguments": c.get("arguments") or {}})
                out.append(json.loads(r["content"][0]["text"]))
            return {"results": out}

        srv = Server("t", "0", [Tool("echo", "e", obj({"x": {"type": "integer"}}), echo),
                                Tool("stepper", "s", obj({"step": {"type": "integer"}, "ms": {"type": "number"}}), echo),
                                Tool("batch", "b", obj({"calls": {"type": "array"}}), batch)])
        self.srv, self.got = srv, got

    def test_ms_is_left_out_and_said(self):
        err, r = call(self.srv, "echo", {"x": 1, "ms": 0})
        self.assertFalse(err, r)
        self.assertEqual(self.got[-1], {"x": 1})
        self.assertEqual(r["readAs"], "ignored ms (an answer field)")

    def test_several_answer_fields(self):
        err, r = call(self.srv, "echo", {"x": 1, "around": {}, "saidBefore": ["note"], "record": "r.json", "appliesNow": "x", "health": {}, "readAs": "x", "step": 2})
        self.assertFalse(err, r)
        self.assertEqual(self.got[-1], {"x": 1})
        self.assertIn("answer fields", r["readAs"])
        for k in ("around", "saidBefore", "record", "appliesNow", "health", "readAs", "step"):
            self.assertIn(k, r["readAs"])

    def test_a_real_input_of_that_name_is_kept(self):
        err, r = call(self.srv, "stepper", {"step": 3, "ms": 5})
        self.assertFalse(err, r)
        self.assertEqual(self.got[-1], {"step": 3, "ms": 5})
        self.assertNotIn("readAs", r)

    def test_a_batch_and_its_calls(self):
        err, r = call(self.srv, "batch", {"calls": [{"tool": "echo", "arguments": {"x": 2, "ms": 0}}], "ms": 0})
        self.assertFalse(err, r)
        self.assertEqual(r["readAs"], "ignored ms (an answer field)")
        self.assertEqual(self.got[-1], {"x": 2})
        self.assertEqual(r["results"][0]["readAs"], "ignored ms (an answer field)")

    def test_other_unknown_fields_are_still_refused(self):
        err, r = call(self.srv, "echo", {"x": 1, "colour": "red"})
        self.assertTrue(err)
        self.assertIn("not a known field", r["error"]["message"])

    def test_alias_and_ignored_together(self):
        a = {"set": {"Length": 2}, "ms": 0}
        said = check_input(obj({"values": {"type": "object"}}), a, "object_set")
        self.assertEqual(a, {"values": {"Length": 2}})
        self.assertEqual(protocol.read_as_words(said), "read set as values; ignored ms (an answer field)")
        self.assertEqual(protocol.read_as_words(["set as values"]), "read set as values")

    def test_empty_text_for_tool_find_is_left_out(self):
        schema = obj({"words": {"type": "string"}, "group": {"type": "string"}, "tool": {"anyOf": [{"type": "string"}]}})
        a = {"group": "", "tool": ""}
        said = check_input(schema, a, "tool_find")
        self.assertEqual(a, {})
        self.assertEqual(said, ["ignored group, tool (empty: read as left out)"])
        a = {"group": "", "find": "fillet"}
        check_input(obj({"group": {"type": "string"}, "find": {"type": "string"}}), a, "tool_groups")
        self.assertEqual(a, {"find": "fillet"})

    def test_empty_text_elsewhere_is_unchanged(self):
        a = {"x": ""}
        check_input(obj({"x": {"type": "string"}}), a, "doc_new")
        self.assertEqual(a, {"x": ""})
        a = {"words": ""}  # a required field is never dropped
        check_input(obj({"words": {"type": "string"}}, ["words"]), a, "tool_find")
        self.assertEqual(a, {"words": ""})

    BATCH = obj({"calls": {"type": "array", "items": {"type": "object"}}, "file": {"type": "string"}, "read": {"type": "string"}, "at": {"type": "string"}})

    def test_batch_at_without_read_is_left_out(self):
        for at in ("./", "", "results.0"):
            a = {"at": at, "calls": [{"tool": "echo"}]}
            said = check_input(self.BATCH, a, "batch")
            self.assertEqual(a, {"calls": [{"tool": "echo"}]})
            self.assertEqual(protocol.read_as_words(said), "ignored at (it goes with read, which was not given)")
        a = {"read": "batches/x.json", "at": "results.0"}
        self.assertEqual(check_input(self.BATCH, a, "batch"), [])
        self.assertEqual(a, {"read": "batches/x.json", "at": "results.0"})
        with open(os.path.join(ROOT, "agentlink", "tools.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn('a.get("at") is not None:\n            return _batch_read(a)', src)
        self.assertIn('if a.get("read") is not None:\n            return _batch_read(a)', src)

    def test_batch_commands_and_steps_are_read_as_calls(self):
        for k in ("commands", "steps"):
            a = {k: [{"tool": "echo"}], "ms": 0}
            said = check_input(self.BATCH, a, "batch")
            self.assertEqual(a, {"calls": [{"tool": "echo"}]})
            self.assertEqual(protocol.read_as_words(said), f"read {k} as calls; ignored ms (an answer field)")
        a = {"calls": [], "commands": [{"tool": "x"}]}
        with self.assertRaises(ToolError):  # both given: commands is not read over calls
            check_input(self.BATCH, a, "batch")

    def test_no_answer_field_is_a_real_input_of_the_hub_in_its_answers_sense(self):
        # The list names only riders that answers carry; each is plain text.
        for k in protocol.ANSWER_FIELDS:
            self.assertTrue(k.isidentifier(), k)
        for k in ("ms", "around", "saidBefore", "record", "appliesNow", "health", "readAs", "step"):
            self.assertIn(k, protocol.ANSWER_FIELDS)


# ---- 2. approvals only from a client that asks the person -------------------------------------

def approval_server():
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


class ClientAsks(unittest.TestCase):
    def setUp(self):
        approvals.reset()
        self.addCleanup(approvals.reset)
        self.shown = []
        person_ok.SHOW = None
        self.addCleanup(setattr, person_ok, "SHOW", None)
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        # The person named these clients in ApproveInWindowFor (opt-in; empty by default).
        env = mock.patch.dict(os.environ, {"AGENTLINK_HOME": self.home, "AGENTLINK_WINDOW_OK": "",
                                           "AGENTLINK_APPROVE_IN_WINDOW_FOR": "opencode,(unnamed)"})
        env.start()
        self.addCleanup(env.stop)
        self.srv = approval_server()

    def window(self):
        """A stand-in for the FreeCAD window's Approve dialog."""
        person_ok.SHOW = self.shown.append

    def test_claude_clients_approve_as_before(self):
        for name in ("claude-ai", "claude-code", "Claude Desktop"):
            approvals.reset()
            init(self.srv, name)
            err, got = call(self.srv, "standin_asks", {})
            self.assertTrue(got["pending"], got)
            self.assertNotIn("approveIn", got)
            err, ok = call(self.srv, "approve_code", got["approve"]["arguments"])
            self.assertFalse(err, ok)
            self.assertTrue(ok["approved"])
            err, got = call(self.srv, "standin_asks", {})
            self.assertTrue(got.get("ok"), name)

    def test_by_default_every_client_approves_as_it_is_set_up(self):
        # Owner, 22 Nov: OpenCode asks the person through its own permission
        # setting ("agentlink_approve_*": "ask"); Agent Link does not judge it by name.
        with mock.patch.dict(os.environ, {"AGENTLINK_APPROVE_IN_WINDOW_FOR": ""}):
            for name in ("opencode", None):
                approvals.reset()
                if name:
                    init(self.srv, name)
                err, got = call(self.srv, "standin_asks", {})
                self.assertNotIn("approveIn", got)
                err, ok = call(self.srv, "approve_code", got["approve"]["arguments"])
                self.assertFalse(err, ok)
                self.assertTrue(ok["approved"])

    def test_a_client_that_does_not_ask_headless_is_refused(self):
        init(self.srv, "opencode")
        err, got = call(self.srv, "standin_asks", {})
        self.assertTrue(got["pending"])
        self.assertEqual(got["approveIn"], "none")
        self.assertIn("opencode", got["next"])
        err, r = call(self.srv, "approve_code", got["approve"]["arguments"])
        self.assertTrue(err)
        self.assertEqual(r["error"]["code"], "not_allowed")
        self.assertIn("Nothing was approved", r["error"]["message"])
        err, got = call(self.srv, "standin_asks", {})
        self.assertTrue(got.get("pending"), "never approved by itself")

    def test_no_name_counts_as_a_client_that_does_not_ask(self):
        err, got = call(self.srv, "standin_asks", {})
        err, r = call(self.srv, "approve_code", got["approve"]["arguments"])
        self.assertTrue(err)
        self.assertIn("gave no name", r["error"]["message"])

    def test_made_up_arguments_stay_refused(self):
        init(self.srv, "opencode")
        err, r = call(self.srv, "approve_code", {"kind": "cookbook", "id": "x", "fingerprint": "y"})
        self.assertTrue(err)
        self.assertEqual(r["error"]["code"], "not_found")

    def test_with_a_window_the_person_approves_there(self):
        self.window()
        init(self.srv, "opencode")
        err, got = call(self.srv, "standin_asks", {})
        self.assertEqual(got["approveIn"], "window")
        self.assertIn("FreeCAD's window", got["next"])
        self.assertEqual(len(self.shown), 1, "the dialog shows whatever the WindowApprove setting")
        err, r = call(self.srv, "approve_code", got["approve"]["arguments"])
        self.assertFalse(err, r)
        self.assertFalse(r["approved"])
        self.assertTrue(r["pending"])
        self.assertEqual(r["approveIn"], "window")
        err, again = call(self.srv, "standin_asks", {})
        self.assertTrue(again.get("pending"), "the client's call gave no approval")
        req = self.shown[-1]
        self.assertTrue(person_ok.pressed(req, spontaneous=True, now=req["opened"] + 5))
        err, got = call(self.srv, "standin_asks", {})
        self.assertTrue(got.get("ok"), got)

    def test_the_window_needs_a_real_press(self):
        self.window()
        init(self.srv, "opencode")
        call(self.srv, "standin_asks", {})
        req = self.shown[-1]
        self.assertFalse(person_ok.pressed(req, spontaneous=False, now=req["opened"] + 5))
        err, got = call(self.srv, "standin_asks", {})
        self.assertTrue(got.get("pending"))

    def test_each_connection_has_its_own_client(self):
        init(self.srv, "claude-ai", "link-1")
        init(self.srv, "opencode", "link-2")
        self.assertTrue(approvals.asks_first("link-1"))
        self.assertFalse(approvals.asks_first("link-2"))
        self.assertFalse(approvals.asks_first(None))

    def test_the_supervisors_word_on_the_window_link(self):
        line = supervise.client_line({"name": "opencode", "version": "1"})
        msg = json.loads(line)
        self.assertEqual(msg["method"], protocol.CLIENT_METHOD)
        r = self.srv.handle(msg, client="link-3")
        self.assertEqual(r["result"], {})
        self.assertEqual(approvals.client_name("link-3"), "opencode")
        self.assertIsNone(supervise.client_line({}))

    def test_a_restarted_freecad_hears_the_same_client(self):
        msg = json.loads(supervise.restart_initialize({"name": "claude-ai", "version": "2"}))
        self.assertEqual(msg["params"]["clientInfo"]["name"], "claude-ai")
        msg = json.loads(supervise.restart_initialize(None))
        self.assertEqual(msg["params"]["clientInfo"]["name"], "agentlink-supervisor")
        self.assertNotIn("agentlink-supervisor", approvals.ASKING_CLIENTS)

    def test_the_window_link_is_told_the_client(self):
        sent = []
        w = supervise.Window(lambda line: None)
        w._send = lambda line, forward=True: sent.append(line) or True
        w.note_client({"name": "opencode"})
        self.assertEqual(sent, [], "not connected: told at the next connection")
        w.f = object()
        w._tell_client()
        self.assertEqual(json.loads(sent[-1])["params"]["clientInfo"]["name"], "opencode")


# ---- 3. --own -------------------------------------------------------------------------------

class Own(unittest.TestCase):
    def test_flag_and_env(self):
        with mock.patch.dict(os.environ, {"AGENTLINK_OWN": ""}):
            self.assertFalse(supervise.own_mode([]))
            self.assertTrue(supervise.own_mode(["--own"]))
        with mock.patch.dict(os.environ, {"AGENTLINK_OWN": "1"}):
            self.assertTrue(supervise.own_mode([]))

    def test_own_never_uses_the_window(self):
        with mock.patch.dict(os.environ, {"AGENTLINK_OWN": "1", "AGENTLINK_WINDOW": "1"}):
            w = supervise.Window(lambda line: None)
            self.assertTrue(w.off)
            self.assertFalse(w.call(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "session_state", "arguments": {}}})))
            self.assertIn("--own", w.open_window()["note"])
        with mock.patch.dict(os.environ, {"AGENTLINK_OWN": "", "AGENTLINK_WINDOW": "1"}):
            self.assertFalse(supervise.Window(lambda line: None).off, "the default is unchanged")

    def test_set_own_gives_an_id_for_the_child(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENTLINK_OWN", None)
            os.environ.pop("AGENTLINK_OWN_ID", None)
            self.assertFalse(supervise.set_own([]))
            self.assertNotIn("AGENTLINK_OWN_ID", os.environ)
            self.assertTrue(supervise.set_own(["--own"]))
            self.assertEqual(os.environ["AGENTLINK_OWN"], "1")
            self.assertEqual(os.environ["AGENTLINK_OWN_ID"], str(os.getpid()))

    def test_run_marks_are_apart(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        with mock.patch.dict(os.environ, {"AGENTLINK_HOME": home, "AGENTLINK_OWN_ID": ""}):
            self.assertEqual(keep.runtime(".hidden-restart"), os.path.join(home, ".hidden-restart"))
            self.assertEqual(keep.heavy_call_mark(), os.path.join(home, "heavy-call.json"))
        with mock.patch.dict(os.environ, {"AGENTLINK_HOME": home, "AGENTLINK_OWN_ID": "4242"}):
            self.assertEqual(keep.runtime(".hidden-restart"), os.path.join(home, "own", "4242", ".hidden-restart"))
            self.assertEqual(keep.call_checkpoint_mark(), os.path.join(home, "own", "4242", "call-checkpoint.json"))
            keep.mark_heavy_call("mesh_thickness", 5, 1)
            self.assertTrue(os.path.isfile(os.path.join(home, "own", "4242", "heavy-call.json")))
        with mock.patch.dict(os.environ, {"AGENTLINK_HOME": home, "AGENTLINK_OWN_ID": "../x"}):
            self.assertEqual(keep.runtime("heavy-call.json"), os.path.join(home, "heavy-call.json"), "an id that is not plain is not a path")
        self.assertIn("own", paths.STATE_DIRS)


if __name__ == "__main__":
    unittest.main()
