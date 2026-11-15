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


if __name__ == "__main__":
    unittest.main()
