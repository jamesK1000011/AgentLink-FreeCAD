# SPDX-License-Identifier: LGPL-2.1-or-later
"""Input shapes whose meaning is clear are read, not refused (owner, 22 Nov):
- a direct call's inputs wrapped as a batch step wraps them ({arguments: {…}});
- tool_find's queries as objects, words as a list, one query as a string;
- a client's prefixed tool name (agentlink_pd_pad);
- a pure read ignores, and names, a field it does not have.
A tool that changes things, and the approval tools, still refuse."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from agentlink.protocol import (FIND_FORMS, FORGIVING_READS, Server, Tool, check_input, close_names,  # noqa: E402
                                find_queries, plain_name)

READ = {"type": "object", "properties": {"launcher": {"type": "boolean"}}, "additionalProperties": False}
CHANGE = {"type": "object", "properties": {"length": {"type": "number"}}, "additionalProperties": False}


class Stub:
    tools = {n: None for n in ("pd_pad", "pd_pocket", "pd_body_new", "session_state", "tool_find", "pad", "sketch_new")}


class Unwrap(unittest.TestCase):
    def test_arguments_wrapper_is_unwrapped(self):
        args = {"arguments": {"launcher": True}}
        read_as = check_input(READ, args, "session_state")
        self.assertEqual(args, {"launcher": True})
        self.assertTrue(any("inside arguments" in r for r in read_as))

    def test_empty_wrapper(self):
        args = {"arguments": {}}
        check_input(CHANGE, args, "pd_pad")
        self.assertEqual(args, {})

    def test_approvals_keep_their_exact_shape(self):
        schema = {"type": "object", "properties": {"id": {"type": "string"}}, "additionalProperties": False}
        for name in ("approve_code", "approve_file"):
            with self.assertRaises(Exception):
                check_input(schema, {"arguments": {"id": "Gears"}}, name)

    def test_not_unwrapped_with_other_keys(self):
        with self.assertRaises(Exception):
            check_input(CHANGE, {"arguments": {"length": 4}, "length": 4}, "pd_pad")

    def test_not_unwrapped_when_arguments_is_a_field(self):
        schema = {"type": "object", "properties": {"arguments": {"type": "object"}}, "additionalProperties": False}
        args = {"arguments": {"x": 1}}
        check_input(schema, args, "needs")
        self.assertEqual(args, {"arguments": {"x": 1}})


class Reads(unittest.TestCase):
    def test_read_ignores_and_names(self):
        args = {"session": "?", "name": "LocalSmoke"}
        read_as = check_input(READ, args, "session_state")
        self.assertEqual(args, {})
        self.assertTrue(any("ignored session, name" in r for r in read_as))

    def test_change_refuses(self):
        with self.assertRaises(Exception) as e:
            check_input(CHANGE, {"lenght": 4}, "pd_pad")
        self.assertIn("lenght", str(e.exception))

    def test_approvals_are_not_reads(self):
        self.assertNotIn("approve_code", FORGIVING_READS)
        self.assertNotIn("approve_file", FORGIVING_READS)
        with self.assertRaises(Exception):
            check_input(CHANGE, {"button": "Save"}, "approve_code")


class Find(unittest.TestCase):
    def test_objects(self):
        qs, read_as = find_queries({"queries": [{"words": "pad sketch"}, {"query": "hole"}]})
        self.assertEqual(qs, ["pad sketch", "hole"])
        self.assertTrue(read_as)

    def test_words_list_and_string_queries(self):
        self.assertEqual(find_queries({"words": ["a", "b"]})[0], ["a", "b"])
        self.assertEqual(find_queries({"queries": "fillet"})[0], ["fillet"])
        self.assertEqual(find_queries({"words": "fillet"}), (["fillet"], []))

    def test_unreadable(self):
        self.assertEqual(find_queries({"queries": [{"x": 1}]})[0], [])
        self.assertIn('queries: ["pad sketch", "hole"]', FIND_FORMS)


class Names(unittest.TestCase):
    def test_prefixes(self):
        s = Stub()
        self.assertEqual(plain_name(s, "agentlink_pd_pad"), "pd_pad")
        self.assertEqual(plain_name(s, "agentlink-freecad_pd_pad"), "pd_pad")
        self.assertEqual(plain_name(s, "mcp__remote-devices__FreeCAD_Agent_Link__session_state"), "session_state")
        self.assertEqual(plain_name(s, "pd_pad"), "pd_pad")

    def test_only_its_own_prefix(self):
        # "other_pad" is not "pad": an unknown prefix stays as it was.
        self.assertEqual(plain_name(Stub(), "other_pad"), "other_pad")

    def test_close(self):
        self.assertEqual(close_names(Stub(), "pd_pad_create")[0], "pd_pad")
        self.assertIn("pd_body_new", close_names(Stub(), "pd_body_create"))


class DirectCall(unittest.TestCase):
    def call(self, srv, name, args):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
        return bool(r.get("isError")), json.loads(r["content"][0]["text"])

    def server(self):
        return Server("t", "0", [Tool("session_state", "state", READ, lambda a: {"launcher": a.get("launcher", False)}),
                                 Tool("pd_pad", "pad", CHANGE, lambda a: {"padded": a.get("length")}, changes=True)])

    def test_prefixed_name_and_wrapper(self):
        err, out = self.call(self.server(), "agentlink_session_state", {"arguments": {"launcher": True}})
        self.assertFalse(err, out)
        self.assertTrue(out.get("launcher"))

    def test_read_with_extra_field(self):
        err, out = self.call(self.server(), "session_state", {"name": "x"})
        self.assertFalse(err, out)
        self.assertIn("readAs", out)

    def test_change_with_extra_field_refuses(self):
        err, out = self.call(self.server(), "pd_pad", {"length": 4, "plane": "XY"})
        self.assertTrue(err, out)


if __name__ == "__main__":
    unittest.main()
