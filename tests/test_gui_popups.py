# SPDX-License-Identifier: LGPL-2.1-or-later
# A gui_input step whose event starts a nested event loop (a toolbar
# button's ▾ arrow opening its menu with QMenu.exec, a button whose click
# runs QDialog.exec) never holds the call: with stand-in Qt objects whose
# "exec" runs a loop of their own (timers and queued calls), the answer goes
# out from inside that loop, says what is open, the steps after it act on
# the menu or dialog, and gui_unstick (a queued call from another thread)
# closes it. The window link answers calls it cannot take "busy" from its
# socket thread, naming what is open.
import io
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import test_gui_input as tg  # noqa: E402  (the stand-in Qt of the delivery tests)
from test_gui_link_dialog import gui_link  # noqa: E402

from agentlink import activity  # noqa: E402
from agentlink import gui_input as gi  # noqa: E402

ESC, RETURN = 0x01000000, 0x01000004


def nested(state, done, limit=0.6):
    """A nested event loop as QEventLoop.exec runs one: timers that are not
    already running fire (none where state["timers_dead"], as when every
    timer is held), queued calls are delivered, until done()."""
    end = time.time() + limit
    state["level"] += 1
    try:
        while not done() and time.time() < end:
            if not state.get("timers_dead"):
                for t in list(state["timers"]):
                    if t.active and not t.running:
                        t.fire()
            while state["posted"] and not done():
                state["posted"].pop(0)()
            time.sleep(0.002)
    finally:
        state["level"] -= 1
    state["loops"].append(done())


class Pix:
    def __init__(self, w=1200, h=800):
        self.w, self.h = w, h

    def save(self, path, fmt):
        return True

    def width(self):
        return self.w

    def height(self):
        return self.h


class Action:
    def __init__(self, text):
        self._t, self.fired = text, 0

    def text(self):
        return self._t

    def isVisible(self):
        return True

    def isEnabled(self):
        return True

    def isSeparator(self):
        return False

    def menu(self):
        return None

    def trigger(self):
        self.fired += 1


class Menu(tg.Widget):
    """A QMenu: a press makes the item under it current, the release on the
    same item hides the menu and triggers it; Escape hides it."""

    def __init__(self, state, items):
        super().__init__("", 130, 140, 160, 20 * len(items), cls="QMenu")
        self.state, self.acts, self.shown, self.current = state, [Action(t) for t in items], False, None

    def actions(self):
        return self.acts

    def title(self):
        return ""

    def isVisible(self):
        return self.shown

    def actionGeometry(self, a):
        return tg.Rect(0, 20 * self.acts.index(a), 160, 20)

    def _at(self, y):
        i = int(y // 20)
        return self.acts[i] if 0 <= i < len(self.acts) else None

    def setActiveAction(self, a):
        self.current = a

    def grab(self):
        return Pix(160, 40)

    def exec_(self):
        self.shown = True
        self.state["popup"] = self
        nested(self.state, lambda: self.state["popup"] is not self)

    def close(self):
        self.shown = False
        if self.state["popup"] is self:
            self.state["popup"] = None

    hide = close

    def on(self, ev):
        if ev.t == "MouseButtonPress":
            self.current = self._at(ev.lp.y())
        elif ev.t == "MouseButtonRelease":
            a = self._at(ev.lp.y())
            if a is not None and a is self.current:
                self.close()
                a.trigger()
        elif ev.t == "KeyPress" and ev.key == ESC:
            self.close()
        elif ev.t == "KeyPress" and ev.key == RETURN and self.current is not None:
            a = self.current
            self.close()
            a.trigger()


class ToolButton(tg.Widget):
    """A QToolButton, popupMode MenuButtonPopup: a press on its ▾ arrow (the
    right 12 px) runs its menu's exec inside the press."""

    def __init__(self, parent, menu):
        super().__init__("sketchgroup", 110, 60, 40, 24, parent=parent, cls="QToolButton")
        self.menu, self.clicked = menu, 0

    def on(self, ev):
        if ev.t == "MouseButtonPress" and ev.lp.x() >= self.w - 12:
            self.menu.exec_()
        elif ev.t == "MouseButtonRelease":
            self.clicked += 1


class Dialog(tg.Widget):
    def __init__(self, state):
        super().__init__("Attachment", 400, 300, 300, 120, cls="QDialog")
        self.state, self.shown, self.result = state, False, None
        self.ok = tg.Widget("ok", 420, 380, 60, 20, parent=self, cls="QPushButton")
        self.ok.text = lambda: "OK"
        self.ok.on = lambda ev: self.accept() if ev.t == "MouseButtonRelease" else None

    def isVisible(self):
        return self.shown

    def grab(self):
        return Pix(300, 120)

    def exec_(self):
        self.shown = True
        self.state["modal"] = self
        nested(self.state, lambda: self.state["modal"] is not self)
        return self.result

    def accept(self):
        self.result, self.shown = 1, False
        self.state["modal"] = None

    def reject(self):
        self.result, self.shown = 0, False
        self.state["modal"] = None


class Base(unittest.TestCase):
    def setUp(self):
        gi.HELD.update({"widget": None, "buttons": []})
        self.addCleanup(gi.HELD.update, {"widget": None, "buttons": []})
        self.sent, self.answers, self.painted = [], [], []
        st = self.state = {"modal": None, "popup": None, "timers": [], "posted": [], "level": 0, "loops": []}
        self.mw = tg.Widget("main", 100, 50, 1200, 800)
        self.mw.grab = lambda: Pix()
        self.menu = Menu(st, ["New Sketch", "Attach sketch"])
        self.button = ToolButton(self.mw, self.menu)
        self.dialog = Dialog(st)
        self.opener = tg.Widget("opener", 200, 60, 80, 24, parent=self.mw, cls="QPushButton")
        self.opener.text = lambda: "Attach…"
        self.opener.on = lambda ev: self.dialog.exec_() if ev.t == "MouseButtonRelease" else None
        st["app"] = types.SimpleNamespace(activePopupWidget=lambda: st["popup"], activeModalWidget=lambda: st["modal"],
                                          topLevelWidgets=lambda: [self.mw, self.dialog, self.menu], focusWidget=lambda: None)
        st["main"] = self.mw
        self.qt = tg.fake_qt(self.sent, st)
        sent = self.sent

        def send(w, ev):
            sent.append((w.name, ev))
            if hasattr(w, "on"):
                w.on(ev)
            return True
        self.qt.QtWidgets.QApplication.sendEvent = staticmethod(send)

        class Timer:
            def __init__(self):
                self.fns, self.active, self.running = [], False, False
                self.timeout = types.SimpleNamespace(connect=self.fns.append)

            def setInterval(self, ms):
                pass

            def start(self):
                self.active = True
                st["timers"].append(self)

            def stop(self):
                self.active = False
                if self in st["timers"]:
                    st["timers"].remove(self)

            def fire(self):
                self.running = True  # Qt never fires a timer whose handler is on the stack
                try:
                    for f in self.fns:
                        f()
                finally:
                    self.running = False

        painted = self.painted

        class Painter:
            def __init__(self, pix):
                pass

            def drawPixmap(self, at, pix):
                painted.append((at.x(), at.y(), pix.width()))

            def end(self):
                pass
        self.qt.QtCore.QTimer = Timer
        self.qt.QtGui.QPainter = Painter
        gui = types.SimpleNamespace(getMainWindow=lambda: self.mw, ActiveDocument=None)

        def modal():
            m = st["modal"]
            return {"class": "QDialog", "title": m.name, "text": "Pick a face", "buttons": ["OK"], "widget": m} if m else None
        self.shots = tempfile.mkdtemp()
        self.run = gi.Run(self.qt, gui, lambda *a: a, modal, list, lambda w: w.grab(), self.answer_now, self.shots,
                          ticker=self.ticker)

    def ticker(self, fn):
        """A thread's queued calls, delivered by the nested loop."""
        stop = threading.Event()

        def beat():
            while not stop.wait(0.005):
                self.state["posted"].append(fn)
        threading.Thread(target=beat, daemon=True).start()
        return stop.set

    def answer_now(self, body):
        self.answers.append(json.loads(json.dumps(body)))
        return True

    def steps(self, *steps):
        return gi.parse_steps(list(steps))


ARROW = {"click": {"widget": {"objectName": "sketchgroup"}, "at": [34, 12]}}


class MenuFromAButtonsArrow(Base):
    def check_menu_run(self):
        out = self.run.run(self.steps(ARROW, {"wait": 10}, {"shot": "ph2"}, {"click": {"menu_item": "New Sketch"}}))
        # The answer went out from inside the menu's loop, once.
        self.assertEqual(len(self.answers), 1)
        self.assertTrue(self.run.answered)
        a = self.answers[0]
        self.assertEqual(out, self.run.final)
        self.assertEqual([s["i"] for s in a["steps"]], [0, 1, 2, 3])
        self.assertEqual(a["steps"][0]["menu"], ["New Sketch", "Attach sketch"])
        # The shot shows the open menu, painted over the window where it is.
        self.assertEqual(a["steps"][2]["over"], 1)
        self.assertEqual(self.painted, [(30.0, 90.0, 160)])
        self.assertTrue(a["steps"][2]["front"].endswith("ph2-front.png"))
        self.assertEqual(a["steps"][3]["hit"]["menu_item"], "New Sketch")
        self.assertEqual(a["steps"][3]["hit"]["menu"], "clicked")
        self.assertEqual(self.menu.acts[0].fired, 1)
        self.assertNotIn("open", a)
        self.assertIsNone(self.state["popup"])
        self.assertEqual(gi.HELD["buttons"], [])  # the menu took the press
        # The stuck press did nothing more once its loop ended (no release).
        self.assertEqual(self.button.clicked, 0)
        self.assertEqual(self.state["loops"], [True])

    def test_steps_go_on_inside_the_menu(self):
        self.check_menu_run()

    def test_with_no_timer_firing_the_ticker_sees_it(self):
        """Where none of the call's timers fire inside the menu's loop, the
        ticker's queued calls still do."""
        self.state["timers_dead"] = True
        self.check_menu_run()

    def test_open_at_the_end_and_unstick_closes_it(self):
        st = self.state
        got = {}
        link = types.SimpleNamespace(_poster=types.SimpleNamespace(post=lambda fn: st["posted"].append(fn)), front=None)
        import agentlink_state

        old = getattr(agentlink_state, "link", None)
        agentlink_state.link = link
        self.addCleanup(setattr, agentlink_state, "link", old)
        old_qt = gui_link._qt
        gui_link._qt = lambda: (None, types.SimpleNamespace(QApplication=types.SimpleNamespace(instance=lambda: st["app"]),
                                                            QLabel=tg.Widget, QAbstractButton=tg.Widget))
        self.addCleanup(setattr, gui_link, "_qt", old_qt)

        def answer_now(body):
            self.answers.append(body)
            # The agent, on another connection: gui_unstick on the socket thread.
            th = threading.Thread(target=lambda: got.update(gui_link.unstick(wait=2.0)))
            th.start()
            got["thread"] = th
            return True
        self.run.answer_now = answer_now
        self.run.run(self.steps(ARROW))
        got["thread"].join(3)
        a = self.answers[0]
        self.assertEqual(a["open"], {"kind": "menu", "title": "a menu", "items": ["New Sketch", "Attach sketch"]})
        self.assertIn("gui_unstick", a["note"])
        self.assertEqual(got["closed"], [{"kind": "menu", "title": "a menu", "items": ["New Sketch", "Attach sketch"]}])
        self.assertIsNone(got["open"])
        self.assertIsNone(st["popup"])
        self.assertEqual(self.menu.acts[0].fired + self.menu.acts[1].fired, 0)
        self.assertIsNone(link.front)

    def test_escape_closes_it(self):
        self.run.run(self.steps(ARROW, {"key": "Escape"}, {"click": {"widget": {"objectName": "sketchgroup"}, "at": [5, 12]}}))
        a = self.answers[0]
        self.assertEqual(a["steps"][1]["hit"]["class"], "QMenu")
        self.assertNotIn("error", a["steps"][2])  # the window is free again
        self.assertEqual(self.button.clicked, 1)
        self.assertIsNone(self.state["popup"])
        self.assertEqual(self.state["loops"], [True])

    def test_menu_item_refusals(self):
        self.run.run(self.steps(ARROW, {"click": {"menu_item": "Bogus"}}, {"key": "Escape"}))
        a = self.answers[0]
        self.assertIn("New Sketch, Attach sketch", a["steps"][1]["error"])
        self.assertEqual(len(a["steps"]), 2)  # stopped there
        self.assertEqual(a["open"]["kind"], "menu")
        self.state["popup"] = None
        out = gi.Run(self.qt, self.run.gui, None, lambda: None, list, None, lambda b: False, self.shots).run(self.steps({"click": {"menu_item": "New Sketch"}}))
        self.assertIn("no menu is open", out["steps"][0]["error"])

    def test_click_that_does_not_take_falls_back_to_return(self):
        self.menu.on = lambda ev, real=self.menu.on: real(ev) if ev.t != "MouseButtonRelease" else None
        self.run.run(self.steps(ARROW, {"click": {"menu_item": "attach"}}))
        a = self.answers[0]
        self.assertEqual(a["steps"][1]["hit"]["menu"], "picked with Return (the click did not take)")
        self.assertEqual(self.menu.acts[1].fired, 1)


class DialogExecOnClick(Base):
    def test_steps_go_on_inside_the_dialog(self):
        out = self.run.run(self.steps({"click": {"widget": {"objectName": "opener"}}}, {"click": {"widget": {"text": "OK", "under": "Attachment"}}}))
        a = self.answers[0]
        self.assertEqual(out, a)
        self.assertEqual(a["steps"][0]["dialog"]["title"], "Attachment")
        self.assertEqual(a["steps"][1]["hit"]["text"], "OK")
        self.assertEqual(self.dialog.result, 1)
        self.assertNotIn("open", a)

    def test_left_open_is_reported(self):
        self.run.run(self.steps({"click": {"widget": {"objectName": "opener"}}}, {"shot": "d"}))
        a = self.answers[0]
        self.assertEqual(a["open"], {"kind": "dialog", "title": "Attachment", "text": "Pick a face", "buttons": ["OK"]})
        self.assertEqual(a["steps"][1]["over"], 1)
        # Its loop never ended here (no one closed it): the stand-in's ran out.
        self.assertEqual(self.state["loops"], [False])

    def test_no_nested_loop_answers_normally(self):
        out = self.run.run(self.steps({"click": {"widget": {"objectName": "sketchgroup"}, "at": [5, 12]}}))
        self.assertEqual(self.answers, [])
        self.assertEqual(self.button.clicked, 1)
        self.assertNotIn("open", out)


class Words(unittest.TestCase):
    def test_parse_and_words(self):
        self.assertEqual(gi.parse_target({"menu_item": "New Sketch"}, "t"), {"kind": "menu_item", "value": "New Sketch"})
        for bad in ({"menu_item": ""}, {"menu_item": 3}, {"menu_item": "x", "at": [1, 1]}):
            with self.assertRaises(gi.ToolError):
                gi.parse_target(bad, "t")
        self.assertEqual(activity.did("gui_input", {"steps": [ARROW, {"click": {"menu_item": "New Sketch"}}]}),
                         "Clicked a control, clicked New Sketch in the menu")

    def test_front_words(self):
        self.assertEqual(gi.front_words({"kind": "menu", "title": "a menu", "items": ["A", "B"]}), "a menu (items: A, B)")
        self.assertEqual(gi.front_words({"kind": "dialog", "title": "Attachment", "buttons": ["OK"]}), "the dialog \"Attachment\" (buttons: OK)")
        self.assertIn("most likely", gi.front_words(None))


def line_for(name, mid=5):
    line = gui_link._Line(json.dumps({"jsonrpc": "2.0", "id": mid, "method": "tools/call", "params": {"name": name, "arguments": {}}}))
    line.ticket = {"state": "queued", "t": time.time()}
    return line


class LinkBusy(unittest.TestCase):
    def link(self):
        link = gui_link.Link.__new__(gui_link.Link)
        link.calls, link.front, link.going = [], None, False
        return link

    def test_queued_call_answered_busy_naming_the_menu(self):
        link, f = self.link(), io.StringIO()
        link.calls.append({"id": 1, "name": "gui_input", "f": io.StringIO(), "answered": True})
        link.front = {"kind": "menu", "title": "a menu", "items": ["New Sketch"]}
        line = line_for("session_state")
        link._arm_busy(line, f, after=0.05, tick=0.01).join(2)
        reply = json.loads(f.getvalue())
        self.assertEqual(reply["id"], 5)
        self.assertTrue(reply["result"]["isError"])
        err = json.loads(reply["result"]["content"][0]["text"])["error"]
        self.assertEqual(err["code"], "busy")
        self.assertIn("New Sketch", err["message"])
        self.assertIn("gui_unstick", err["message"])
        self.assertEqual(line.ticket["state"], "busy")
        self.assertFalse(link._claim(line))  # the GUI thread drops it later

    def test_long_call_is_waited_for(self):
        link, f = self.link(), io.StringIO()
        link.calls.append({"id": 1, "name": "fem_run", "f": io.StringIO(), "answered": False})
        line = line_for("session_state")
        th = link._arm_busy(line, f, after=0.02, tick=0.01)
        time.sleep(0.15)
        self.assertEqual(f.getvalue(), "")
        self.assertTrue(link._claim(line))  # the GUI thread takes it in turn
        th.join(1)
        self.assertEqual(f.getvalue(), "")

    def test_call_in_hand_past_its_time(self):
        link, f = self.link(), io.StringIO()
        call = {"id": 9, "name": "gui_input", "f": f, "answered": False}
        link.calls.append(call)
        link.expect("gui_input", 0.03, tick=0.01).join(2)
        err = json.loads(json.loads(f.getvalue())["result"]["content"][0]["text"])["error"]
        self.assertEqual(err["code"], "busy")
        self.assertIn("may not have run", err["message"])
        self.assertTrue(call["answered"])
        self.assertFalse(link.answer_now("gui_input", {"steps": []}))  # one answer only
        self.assertEqual(len(f.getvalue().splitlines()), 1)

    def test_finished_in_time_is_not_answered(self):
        link, f = self.link(), io.StringIO()
        call = {"id": 9, "name": "gui_input", "f": f, "answered": False}
        link.calls.append(call)
        th = link.expect("gui_input", 0.05, tick=0.01)
        call["finished"] = True
        th.join(1)
        self.assertEqual(f.getvalue(), "")

    def test_unstick_without_a_link(self):
        import agentlink_state

        old = getattr(agentlink_state, "link", None)
        agentlink_state.link = None
        self.addCleanup(setattr, agentlink_state, "link", old)
        with self.assertRaises(gi.ToolError) as e:
            gui_link.unstick()
        self.assertEqual(e.exception.code, "unavailable")

    def test_unstick_when_nothing_takes_queued_calls(self):
        import agentlink_state

        old = getattr(agentlink_state, "link", None)
        agentlink_state.link = types.SimpleNamespace(_poster=types.SimpleNamespace(post=lambda fn: None))
        self.addCleanup(setattr, agentlink_state, "link", old)
        got = {}

        def socket_thread():
            try:
                gui_link.unstick(wait=0.05)
            except gi.ToolError as e:
                got["code"] = e.code
        th = threading.Thread(target=socket_thread)
        th.start()
        th.join(2)
        self.assertEqual(got["code"], "busy")


class LinkWindowSide(unittest.TestCase):
    """The window link's own handling of a menu: the heartbeat names it,
    calls are refused at once while it holds a call in hand, and a batch's
    gui_input answers the batch early."""

    def setUp(self):
        self.menu_state = {"modal": None, "popup": None, "timers": [], "posted": [], "level": 0, "loops": []}
        self.menu = Menu(self.menu_state, ["New Sketch", "Attach sketch"])
        self.menu.shown = True
        self.menu_state["popup"] = self.menu
        app = types.SimpleNamespace(activePopupWidget=lambda: self.menu_state["popup"], activeModalWidget=lambda: None)
        old_qt = gui_link._qt
        gui_link._qt = lambda: (None, types.SimpleNamespace(QApplication=types.SimpleNamespace(instance=lambda: app),
                                                            QLabel=tg.Widget, QAbstractButton=tg.Widget))
        self.addCleanup(setattr, gui_link, "_qt", old_qt)

    def link(self):
        link = gui_link.Link.__new__(gui_link.Link)
        link.calls, link.front, link.going, link.in_call, link.busy = [], None, False, False, None
        link.session, link._dialog = None, None
        import queue

        link.inbox = queue.Queue()
        return link

    def test_heartbeat_names_the_menu(self):
        home = tempfile.mkdtemp()
        old = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = home
        self.addCleanup(lambda: os.environ.pop("AGENTLINK_HOME") if old is None else os.environ.__setitem__("AGENTLINK_HOME", old))
        fc = gui_link.FreeCAD
        gui_link.FreeCAD = types.SimpleNamespace(listDocuments=lambda: {}, Version=lambda: ["1", "1", "3"], Console=fc.Console)
        self.addCleanup(setattr, gui_link, "FreeCAD", fc)
        link = self.link()
        link.port = 7318
        link._beat()
        hb = json.load(open(os.path.join(home, "heartbeat.json")))
        self.assertEqual(hb["popup"]["kind"], "menu")
        self.assertEqual(hb["popup"]["class"], "QMenu")
        self.assertEqual(hb["popup"]["items"], ["New Sketch", "Attach sketch"])
        since = hb["popup"]["since"]
        link._beat()  # the same menu: the same since
        self.assertEqual(json.load(open(os.path.join(home, "heartbeat.json")))["popup"]["since"], since)
        self.assertEqual(link.front["kind"], "menu")
        self.menu_state["popup"] = None
        link._beat()
        self.assertIsNone(json.load(open(os.path.join(home, "heartbeat.json")))["popup"])
        self.assertIsNone(link.front)

    def test_calls_refused_at_once_while_a_menu_holds_the_call_in_hand(self):
        """A batch's gui_input in a menu's loop (not answered early): another
        call is answered at once, not left waiting behind it."""
        link, f = self.link(), io.StringIO()
        link.in_call, link.busy = True, "batch"
        link.calls.append({"id": 1, "name": "batch", "f": io.StringIO(), "answered": False})
        old = gui_link.popup_info
        gui_link.popup_info = lambda: {"class": "QMenu", "kind": "menu", "title": "a menu", "text": "items: New Sketch", "items": ["New Sketch"], "buttons": [], "widget": self.menu}
        self.addCleanup(setattr, gui_link, "popup_info", old)
        old_modal = gui_link.modal_info
        gui_link.modal_info = lambda: None
        self.addCleanup(setattr, gui_link, "modal_info", old_modal)
        line = line_for("session_state", 4)
        link.inbox.put((line, f, None))
        link._handle_inbox()
        reply = json.loads(f.getvalue())
        self.assertEqual(reply["id"], 4)
        msg = json.loads(reply["result"]["content"][0]["text"])["error"]["message"]
        self.assertTrue(msg.startswith("Blocked by a menu in the FreeCAD window (items: New Sketch)"), msg)
        self.assertIn("gui_unstick", msg)
        self.assertNotIn("dialog_answer", msg)
        self.assertNotIn("app_force_restart", msg)
        self.assertEqual(line.ticket["state"], "taken")
        self.assertEqual(link.front["kind"], "menu")

    def test_batch_answered_early(self):
        link, f = self.link(), io.StringIO()
        link.session = types.SimpleNamespace(batch_now={"results": [{"tool": "cmd_run", "ok": True, "result": {"ran": "x"}}], "i": 1, "n": 3, "tool": "gui_input", "answered": False})
        link.calls.append({"id": 3, "name": "batch", "f": f, "answered": False})
        self.assertTrue(link.answer_now("gui_input", {"steps": [{"i": 0, "do": "click"}], "open": {"kind": "menu"}}))
        body = json.loads(json.loads(f.getvalue())["result"]["content"][0]["text"])
        self.assertEqual([r["tool"] for r in body["results"]], ["cmd_run", "gui_input"])
        self.assertEqual(body["results"][1]["result"]["open"], {"kind": "menu"})
        self.assertEqual((body["ran"], body["not_run"]), (2, 1))
        self.assertTrue(link.session.batch_now["answered"])
        self.assertFalse(link.answer_now("gui_input", {}))
        # Not a batch running gui_input now: no early answer.
        link2, f2 = self.link(), io.StringIO()
        link2.session = types.SimpleNamespace(batch_now={"results": [], "i": 0, "n": 1, "tool": "cmd_run", "answered": False})
        link2.calls.append({"id": 3, "name": "batch", "f": f2, "answered": False})
        self.assertFalse(link2.answer_now("gui_input", {}))
        self.assertEqual(f2.getvalue(), "")

    def test_batch_call_in_hand_gets_a_deadline(self):
        link, f = self.link(), io.StringIO()
        call = {"id": 2, "name": "batch", "f": f, "answered": False}
        link.calls.append(call)
        link.expect("gui_input", 0.02, tick=0.01).join(2)
        self.assertEqual(json.loads(json.loads(f.getvalue())["result"]["content"][0]["text"])["error"]["code"], "busy")


class UnstickThroughBatch(unittest.TestCase):
    """A client reaches a new tool through batch: gui_unstick in a batch is
    let through while a menu holds the window, and answered on the socket
    thread."""

    def test_front_calls(self):
        from test_gui_link_dialog import call

        self.assertTrue(gui_link._dialog_call(call("gui_unstick")))
        self.assertTrue(gui_link._dialog_call(call("batch", {"calls": [{"tool": "gui_unstick", "arguments": {}}]})))
        self.assertIsNotNone(gui_link._thread_batch(call("batch", {"calls": [{"tool": "gui_unstick"}]}), {"gui_unstick"}))
        self.assertIsNone(gui_link._thread_batch(call("batch", {"calls": [{"tool": "gui_unstick"}, {"tool": "doc_new"}]}), {"gui_unstick"}))
        self.assertIsNone(gui_link._thread_batch(call("gui_unstick"), {"gui_unstick"}))

    def test_batch_answered_on_the_socket_thread(self):
        from agentlink import hooks

        hooks.register_thread_tool("gui_unstick")
        seen = []

        def light(msg):
            seen.append((threading.current_thread() is threading.main_thread(), msg["params"]["name"]))
            text = json.dumps({"closed": [{"kind": "menu", "title": "a menu", "items": ["New Sketch"]}], "open": None})
            return {"jsonrpc": "2.0", "id": msg["id"], "result": {"content": [{"type": "text", "text": text}]}}
        link = gui_link.Link.__new__(gui_link.Link)
        link.server = types.SimpleNamespace(handle_light=light)
        f = io.StringIO()
        line = json.dumps({"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "batch", "arguments": {"calls": [{"tool": "gui_unstick", "arguments": {}}]}}})
        self.assertTrue(link._thread_call(line, f))
        for _ in range(100):
            if f.getvalue():
                break
            time.sleep(0.01)
        reply = json.loads(f.getvalue())
        self.assertEqual(reply["id"], 8)
        body = json.loads(reply["result"]["content"][0]["text"])
        self.assertEqual(body["ran"], 1)
        self.assertEqual(body["results"][0]["result"]["closed"][0]["kind"], "menu")
        self.assertEqual(seen, [(False, "gui_unstick")])

    def test_on_the_gui_thread_closes_at_once(self):
        """Run on the GUI thread (a batch inside the menu's loop): closed
        there, never waiting for a queued call it holds up itself."""
        import agentlink_state

        old = getattr(agentlink_state, "link", None)
        agentlink_state.link = types.SimpleNamespace(_poster=types.SimpleNamespace(post=lambda fn: None))
        self.addCleanup(setattr, agentlink_state, "link", old)
        real = gui_link.close_front
        gui_link.close_front = lambda all_=False: {"closed": [{"kind": "menu"}], "open": None}
        self.addCleanup(setattr, gui_link, "close_front", real)
        t0 = time.time()
        self.assertEqual(gui_link.unstick(wait=2.0)["closed"], [{"kind": "menu"}])
        self.assertLess(time.time() - t0, 0.5)

    def test_dialog_refusal_still_names_its_buttons(self):
        msg = gui_link.blocked_words({"class": "QMessageBox", "title": "Unsaved", "text": "Save changes?", "buttons": ["Save", "Discard"]})
        self.assertTrue(msg.startswith("Blocked by a dialog"))
        self.assertIn("buttons: Save, Discard", msg)


class ArrowHit(Base):
    """A click on a dropdown's arrow reports the button it belongs to (its
    current action's text), not the arrow's own label."""

    def tool_button(self, name, ox, oy, parent, action_text, own_text="", popup=0):
        b = tg.Widget(name, ox, oy, 24, 24, parent=parent, cls="QToolButton")
        b.defaultAction = lambda: types.SimpleNamespace(text=lambda: action_text) if action_text else None
        b.text = lambda: own_text
        b.toolTip = lambda: "<b>" + (action_text or own_text) + "</b>"
        b.popupMode = lambda: popup
        return b

    def test_arrow_inside_its_button(self):
        group = self.tool_button("PartDesign_CompSketches", 300, 60, self.mw, "New Sketch", popup=1)
        arrow = self.tool_button("qt_toolbutton_menubutton", 314, 60, group, None, own_text="Create Datum")
        out = self.run.run(self.steps({"click": {"widget": {"objectName": "qt_toolbutton_menubutton"}}}))
        hit = out["steps"][0]["hit"]
        self.assertEqual((hit["text"], hit["part"], hit["name"]), ("New Sketch", "menu arrow", "PartDesign_CompSketches"))
        self.assertTrue(arrow is not None)

    def test_arrow_beside_its_button(self):
        toolbar = tg.Widget("Part Design Helper", 280, 60, 400, 24, parent=self.mw, cls="QToolBar")
        geo = {}

        def at(w, x, y, wd, ht):
            geo[w.name] = tg.Rect(x, y, wd, ht)
            w.geometry = lambda: geo[w.name]
        datum = self.tool_button("PartDesign_CompDatums", 280, 60, toolbar, "Create Datum")
        sketch = self.tool_button("PartDesign_CompSketches", 330, 60, toolbar, "New Sketch")
        arrow = self.tool_button("qt_toolbutton_menubutton", 354, 60, toolbar, None, own_text="Create Datum")
        at(datum, 0, 0, 24, 24)
        at(sketch, 50, 0, 24, 24)
        at(arrow, 74, 0, 12, 24)
        self.qt.QtWidgets.QToolButton = tg.Widget
        out = self.run.run(self.steps({"click": {"widget": {"objectName": "qt_toolbutton_menubutton"}}}))
        hit = out["steps"][0]["hit"]
        self.assertEqual((hit["text"], hit["part"]), ("New Sketch", "menu arrow"))

    def test_own_arrow_and_plain_click(self):
        self.tool_button("PartDesign_CompSketches", 300, 60, self.mw, "New Sketch", own_text="Old label", popup=1)
        out = self.run.run(self.steps({"click": {"widget": {"objectName": "PartDesign_CompSketches"}, "at": [20, 12]}},
                                      {"click": {"widget": {"objectName": "PartDesign_CompSketches"}, "at": [4, 12]}}))
        a, b = out["steps"][0]["hit"], out["steps"][1]["hit"]
        self.assertEqual((a["text"], a["part"]), ("New Sketch", "menu arrow"))
        self.assertEqual(b["text"], "New Sketch")
        self.assertNotIn("part", b)


if __name__ == "__main__":
    unittest.main()
