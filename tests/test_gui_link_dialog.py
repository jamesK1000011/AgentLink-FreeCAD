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
        # A lean client reaches gui_input through batch: let through too.
        self.assertTrue(gui_link._dialog_call(call("batch", {"calls": [{"tool": "gui_input"}, {"tool": "dialog_answer"}]})))
        self.assertFalse(gui_link._dialog_call(call("batch", {"calls": [{"tool": "gui_input"}, {"tool": "doc_new"}]})))

    def test_batch_with_its_calls_as_a_string_of_json(self):
        """Live 56: a 4-tool client reaches gui_input only through batch; its
        batch (calls sent as a string of JSON) was refused behind the dialog
        that gui_input { as: person } had opened."""
        steps = {"steps": [{"type": "5 mm"}], "as": "person"}
        self.assertTrue(gui_link._dialog_call(call("batch", {"calls": json.dumps([{"tool": "gui_input", **steps}])})))
        self.assertTrue(gui_link._dialog_call(call("batch", {"calls": [json.dumps({"tool": "gui_input", **steps})]})))
        self.assertTrue(gui_link._dialog_call(call("batch", json.dumps({"calls": [{"tool": "gui_input"}]}))))
        # A picture of the window beside it; never on its own, never with another tool.
        self.assertTrue(gui_link._dialog_call(call("batch", {"calls": [{"tool": "gui_input"}, {"tool": "window_snapshot"}]})))
        self.assertFalse(gui_link._dialog_call(call("batch", {"calls": [{"tool": "window_snapshot"}]})))
        self.assertFalse(gui_link._dialog_call(call("batch", {"calls": json.dumps([{"tool": "gui_input"}, {"tool": "doc_new"}])})))
        self.assertFalse(gui_link._dialog_call(call("batch", {"calls": "not json"})))
        self.assertFalse(gui_link._dialog_call(call("batch", {"file": "x.json"})))
        from agentlink import supervise

        self.assertTrue(supervise._answers_dialog({"tool": "batch", "args": {"calls": json.dumps([{"tool": "gui_input", "arguments": {}}])}}))

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
        self.assertTrue(supervise._answers_dialog({"tool": "batch", "args": {"calls": [{"tool": "gui_input", "arguments": {}}]}}))


class Field:
    def __init__(self, visible=True, plain=False):
        self.visible, self.value = visible, None
        if plain:
            self.setPlainText = self._set

    def isVisible(self):
        return self.visible

    def isEnabled(self):
        return True

    def isReadOnly(self):
        return False

    def setText(self, t):
        self.value = t

    def _set(self, t):
        self.value = t


class Prompt:
    """A QInputDialog stand-in."""

    def __init__(self, items=()):
        self.value, self.items = "", list(items)

    def textValue(self):
        return self.value

    def setTextValue(self, v):
        self.value = v

    def comboBoxItems(self):
        return self.items


class Box:
    def __init__(self, fields):
        self.fields = fields

    def findChildren(self, cls):
        return [f for f in self.fields if cls is Field]


class Fill(unittest.TestCase):
    def setUp(self):
        import types

        self.orig = gui_link._qt
        gui_link._qt = lambda: (None, types.SimpleNamespace(QLineEdit=Field, QPlainTextEdit=object))

    def tearDown(self):
        gui_link._qt = self.orig

    def test_prompt_text(self):
        p = Prompt()
        self.assertEqual(gui_link.fill({"widget": p}, text="Wall 2 mm here"), {"text": "Wall 2 mm here"})
        self.assertEqual(p.value, "Wall 2 mm here")

    def test_prompt_item(self):
        p = Prompt(["PLA", "PETG"])
        self.assertEqual(gui_link.fill({"widget": p}, item="petg"), {"item": "PETG"})
        self.assertEqual(p.value, "PETG")
        with self.assertRaises(ValueError):
            gui_link.fill({"widget": p}, item="Nylon")

    def test_one_field(self):
        f = Field()
        gui_link.fill({"widget": Box([f, Field(visible=False)])}, text="yes")
        self.assertEqual(f.value, "yes")

    def test_none_or_several_refused(self):
        for fields in ([], [Field(), Field()]):
            with self.assertRaises(ValueError):
                gui_link.fill({"widget": Box(fields)}, text="x")
        with self.assertRaises(ValueError):
            gui_link.fill({"widget": Box([Field()])}, item="x")


class PinHint(unittest.TestCase):
    def test_events(self):
        from agentlink import panel_tabs

        self.assertTrue(panel_tabs.PIN_HINT.startswith("Click the part"))
        self.assertIn("Esc cancels", panel_tabs.PIN_HINT)
        self.assertEqual(panel_tabs.pin_event({"State": "DOWN", "Button": "BUTTON1"}), "place")
        self.assertIsNone(panel_tabs.pin_event({"State": "UP", "Button": "BUTTON1"}))
        self.assertIsNone(panel_tabs.pin_event({"State": "DOWN", "Button": "BUTTON2"}))
        self.assertEqual(panel_tabs.pin_event({"Type": "SoKeyboardEvent", "State": "DOWN", "Key": "ESCAPE"}), "cancel")
        self.assertIsNone(panel_tabs.pin_event({"Type": "SoKeyboardEvent", "State": "DOWN", "Key": "A"}))


if __name__ == "__main__":
    unittest.main()


# Live 98 / 102 (19 Nov): FreeCAD's Expression Editor over a task panel has
# its own OK. "OK" pressed the first OK found; now the editor's buttons are
# apart, and OK accepts the expression first, then the task.
class _Meta:
    def __init__(self, name):
        self.name = name

    def className(self):
        return self.name


class _W:
    def __init__(self, cls="QWidget", parent=None, text=""):
        self.cls, self.parent, self._text, self.kids, self.clicks = cls, parent, text, [], []
        if parent is not None:
            parent.kids.append(self)

    def metaObject(self):
        return _Meta(self.cls)

    def parentWidget(self):
        return self.parent

    def findChildren(self, _kind):
        out = []
        for k in self.kids:
            out.append(k)
            out += k.findChildren(_kind)
        return [k for k in out if k.cls == "QPushButton"]

    def isVisible(self):
        return True

    def isEnabled(self):
        return True

    def text(self):
        return self._text

    def click(self):
        PRESSED.append((self.parent.cls, self._text))


PRESSED = []


class ExpressionEditor(unittest.TestCase):
    def setUp(self):
        import types

        del PRESSED[:]
        app = types.SimpleNamespace(processEvents=lambda: None)
        widgets = types.SimpleNamespace(QAbstractButton=object, QApplication=app)
        self.qt = gui_link._qt
        gui_link._qt = lambda: (None, widgets)
        self.view = _W("Gui::TaskView::TaskView")
        box = _W("QDialogButtonBox", self.view)
        _W("QPushButton", box, "OK")
        _W("QPushButton", box, "Cancel")
        self.ed = _W(gui_link.EXPRESSION_CLASS, self.view)
        _W("QPushButton", self.ed, "OK")

    def tearDown(self):
        gui_link._qt = self.qt

    def test_ok_accepts_the_expression_then_the_task(self):
        d = {"widget": self.view, "expressionWidget": self.ed}
        self.assertTrue(gui_link.press_task(d, "OK"))
        self.assertEqual(PRESSED, [(gui_link.EXPRESSION_CLASS, "OK"), ("QDialogButtonBox", "OK")])

    def test_expression_ok_accepts_only_the_expression(self):
        d = {"widget": self.view, "expressionWidget": self.ed}
        self.assertTrue(gui_link.press_task(d, "Expression OK"))
        self.assertEqual(PRESSED, [(gui_link.EXPRESSION_CLASS, "OK")])

    def test_without_the_editor_ok_is_the_tasks(self):
        d = {"widget": self.view}
        self.assertTrue(gui_link.press_task(d, "OK"))
        self.assertEqual(PRESSED, [("QDialogButtonBox", "OK")])
        self.assertFalse(gui_link.press_task(d, "Expression OK"))

    def test_buttons_in_the_editor_are_known(self):
        b = self.ed.kids[0]
        self.assertTrue(gui_link._in_expression(b, self.view))
        self.assertFalse(gui_link._in_expression(self.view.kids[0].kids[0], self.view))
