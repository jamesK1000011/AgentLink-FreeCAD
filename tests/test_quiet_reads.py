# SPDX-License-Identifier: LGPL-2.1-or-later
# Opening an add-on's panel is not the agent's work: a changing tool's read
# (setup action list) is no undo step and marks nothing changed, and a
# panel's own refresh (quiet) shows nothing and adds nothing to Activity.
# Found live: opening Workshop Make's panel turned the document "1*" and
# echoed "Agent: setup — action list" each time.
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentlink import echo, tooldata  # noqa: E402
from agentlink.protocol import Server, Tool  # noqa: E402

SCHEMA = {"type": "object", "properties": {"action": {"type": "string", "default": "list"}, "id": {"type": "string"}}}


def setup_tool(seen):
    return Tool("setup", "Setups: how each part is made.", SCHEMA, lambda a: seen.append(dict(a)) or {"setups": []},
                changes=True, reads={"action": ["list", "of"]})


class Reads(unittest.TestCase):
    def test_a_read_of_a_changing_tool(self):
        t = setup_tool([])
        self.assertFalse(t.changes_for({"action": "list"}))
        self.assertFalse(t.changes_for({}))  # the schema's default: list
        self.assertTrue(t.changes_for({"action": "add"}))
        self.assertIs(t.for_call({"action": "add"}), t)
        self.assertFalse(t.for_call({"action": "of"}).changes)
        self.assertTrue(t.changes)  # the tool itself unchanged

    def test_no_undo_step_for_a_read(self):
        """The server runs a read as a read: the session opens no
        transaction (Session.execute only wraps tool.changes)."""
        ran = []
        srv = Server("t", "0", [setup_tool([])], run=lambda tool, fn: (ran.append(tool.changes), fn())[1])
        srv.call({"name": "setup", "arguments": {"action": "list"}})
        srv.call({"name": "setup", "arguments": {"action": "remove", "id": "S1"}})
        self.assertEqual(ran, [False, True])

    def test_reads_in_the_tool_data_format(self):
        doc = {"dataVersion": "1.0.0", "entries": {"setup": {
            "group": "make", "description": "Setups: how each part is made.", "inputSchema": SCHEMA, "changes": True,
            "source": "own", "date": "2026-11-15", "reads": {"action": ["list", "of"]}}}}
        self.assertEqual(tooldata.check(doc), [])


class Quiet(unittest.TestCase):
    def test_a_panels_own_refresh_is_not_shown(self):
        session = types.SimpleNamespace(quiet_call=True, doc=None)
        e = echo.Echo(session)
        before = len(echo.log())
        tool = setup_tool([])
        e.before(tool, {"action": "list"})
        e.after(tool, {"action": "list"}, {"content": [{"type": "text", "text": json.dumps({"setups": []})}]})
        self.assertEqual(len(echo.log()), before)

    def test_a_click_still_shows_in_activity(self):
        session = types.SimpleNamespace(quiet_call=False, doc=None)
        e = echo.Echo(session)
        before = len(echo.log())
        tool = setup_tool([]).for_call({"action": "list"})
        from unittest import mock

        with mock.patch.object(echo, "enabled", lambda: False):  # no window here
            e.after(tool, {"action": "list"}, {"content": [{"type": "text", "text": json.dumps({"setups": []})}]})
        self.assertEqual(len(echo.log()), before + 1)


class Writes:
    """A stand-in saved document: every property set is recorded, and set
    marks it touched, as FreeCAD's does even for the same value."""

    def __init__(self):
        object.__setattr__(self, "log", [])
        object.__setattr__(self, "touched", False)
        object.__setattr__(self, "UndoMode", 1)
        object.__setattr__(self, "Meta", {})
        object.__setattr__(self, "objects", {})

    def __setattr__(self, k, v):
        self.log.append(k)
        object.__setattr__(self, "touched", True)
        object.__setattr__(self, k, v)

    def isTouched(self):  # noqa: N802
        return self.touched


class Untouched(unittest.TestCase):
    """Opening a panel and refreshing it leave a saved document untouched:
    the session sets undo on only when it is off (the "*" after opening
    Workshop Make's panel on the Mac), and a record written with the value
    it has changes nothing."""

    def test_undo_set_only_when_off(self):
        from agentlink.store import undo_on

        d = Writes()
        undo_on(d)
        self.assertEqual(d.log, [])
        self.assertFalse(d.isTouched())
        object.__setattr__(d, "UndoMode", 0)
        undo_on(d)
        self.assertEqual(d.log, ["UndoMode"])

    def test_same_record_again_writes_nothing(self):
        from agentlink import store

        d = Writes()  # no objects: the records go in Meta
        store.write(d, "notes", {"next": 1, "notes": []})
        self.assertEqual(d.log, ["Meta"])
        store.write(d, "notes", {"next": 1, "notes": []})
        self.assertEqual(d.log, ["Meta"])
        self.assertEqual(store.read(d, "notes", None), {"next": 1, "notes": []})
        self.assertEqual(store.read(d, "steps", "none"), "none")  # a read makes nothing
        self.assertEqual(d.log, ["Meta"])


if __name__ == "__main__":
    unittest.main()
