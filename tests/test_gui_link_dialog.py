# SPDX-License-Identifier: LGPL-2.1-or-later
# While a modal dialog holds the window, dialog_answer runs, alone or as a
# batch of nothing but dialog_answer calls (a client with only the lean
# groups listed reaches it through batch); anything else waits or is refused.
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



def _gui_link():
    """agentlink.gui_link with a stand-in FreeCAD where none is importable
    (as test_link_token does); the modules swapped are put back."""
    import types

    had = {k: sys.modules.get(k) for k in ("FreeCAD", "agentlink.tools", "agentlink.gui_link")}
    try:
        import FreeCAD  # noqa: F401
    except ImportError:
        fake = types.ModuleType("FreeCAD")
        fake.Console = types.SimpleNamespace(PrintWarning=lambda *a: None, PrintMessage=lambda *a: None)
        sys.modules["FreeCAD"] = fake
    if had["agentlink.tools"] is None:
        tools = types.ModuleType("agentlink.tools")
        tools.Session = tools.build_server = None
        sys.modules["agentlink.tools"] = tools
    sys.modules.pop("agentlink.gui_link", None)
    try:
        from agentlink import gui_link

        return gui_link
    finally:
        for k, v in had.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


gui_link = _gui_link()


def call(name, args=None):
    return json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}})


class DialogCall(unittest.TestCase):
    def test_dialog_answer_alone(self):
        self.assertTrue(gui_link._dialog_call(call("dialog_answer", {"press": "OK"})))

    def test_batch_of_only_dialog_answers(self):
        self.assertTrue(gui_link._dialog_call(call("batch", {"calls": [{"tool": "dialog_answer", "arguments": {"press": "OK"}}]})))

    def test_batch_with_anything_else_is_not(self):
        self.assertFalse(gui_link._dialog_call(call("batch", {"calls": [{"tool": "dialog_answer"}, {"tool": "doc_new"}]})))
        self.assertFalse(gui_link._dialog_call(call("batch", {"calls": []})))
        self.assertFalse(gui_link._dialog_call(call("doc_new")))
        self.assertFalse(gui_link._dialog_call("not json"))


class GuiInputInFront(unittest.TestCase):
    """gui_input runs while a dialog is in front (it takes only targets inside
    it), and its answer can go out while a dialog its step opened holds it."""

    def test_runs_with_a_dialog(self):
        self.assertTrue(gui_link._dialog_call(call("gui_input", {"steps": [{"key": "Escape"}]})))
        self.assertFalse(gui_link._dialog_call(call("batch", {"calls": [{"tool": "gui_input"}]})))

    def link(self):
        import io

        link = gui_link.Link.__new__(gui_link.Link)
        link.calls = []
        return link, io.StringIO()

    def test_answer_now_once(self):
        link, f = self.link()
        link.calls.append({"id": 7, "name": "gui_input", "f": f, "answered": False})
        self.assertTrue(link.answer_now("gui_input", {"steps": [{"i": 0, "do": "click"}]}))
        reply = json.loads(f.getvalue())
        self.assertEqual(reply["id"], 7)
        self.assertEqual(json.loads(reply["result"]["content"][0]["text"])["steps"][0]["do"], "click")
        self.assertTrue(link.calls[0]["answered"])
        self.assertFalse(link.answer_now("gui_input", {}))  # once only
        self.assertEqual(len(f.getvalue().splitlines()), 1)

    def test_not_inside_a_batch_or_with_no_call(self):
        link, f = self.link()
        self.assertFalse(link.answer_now("gui_input", {}))
        link.calls.append({"id": 1, "name": "batch", "f": f, "answered": False})
        self.assertFalse(link.answer_now("gui_input", {}))
        self.assertEqual(f.getvalue(), "")


class SupervisorLetsItThrough(unittest.TestCase):
    """The supervisor answers a call stuck behind an old dialog; the call
    that answers the dialog is not one of those."""

    def test_answers_dialog(self):
        from agentlink import supervise

        self.assertTrue(supervise._answers_dialog({"tool": "dialog_answer", "args": {"button": "Cancel"}}))
        self.assertTrue(supervise._answers_dialog({"tool": "batch", "args": {"calls": [{"tool": "dialog_answer", "arguments": {}}]}}))
        self.assertFalse(supervise._answers_dialog({"tool": "batch", "args": {"calls": [{"tool": "dialog_answer"}, {"tool": "cmd_run"}]}}))
        self.assertFalse(supervise._answers_dialog({"tool": "cmd_run", "args": {}}))
        self.assertTrue(supervise._answers_dialog({"tool": "gui_input", "args": {"steps": []}}))


if __name__ == "__main__":
    unittest.main()
