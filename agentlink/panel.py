# SPDX-License-Identifier: LGPL-2.1-or-later
# The Agent Link panel in the FreeCAD window: Notes and Steps, inspired by
# the Reverse engineer panel of Stefan Hermann's ScanRuler (CNC Kitchen) —
# notes pinned to the part between the person and the agent, and the
# feature list played back with a caption a step. Agent Link's own code;
# extensions that port ScanRuler's tools credit him where they load. The records are the notes
# family's (families/notes.py), kept in the document; this panel only shows
# and edits them, so the agent and the person see the same notes.
#
# Nothing here changes the model: a pin and a played step are drawn in the
# 3D view's own scene, apart from the document, and taken away after.

import FreeCAD
import FreeCADGui

from .families import notes as nf
from . import layout
from .panel_tabs import (EMPTY, HOME, NO_REVIEWER, PIN_HINT, FlowRow, Tabs, activity_row, credit_shown, link_status, panel_qss, pin_event,
                         review_hint, step_caption, tab_order, tabs_for)

try:
    from PySide import QtCore, QtGui

    QtWidgets = QtGui
    try:
        from PySide import QtWidgets  # noqa: F811  (Qt 6 builds)
    except ImportError:
        pass
except ImportError:  # pragma: no cover
    QtCore = QtGui = QtWidgets = None

# Agent Link's own panel, its own code: the idea credited, not the code.
CREDIT = "Inspired by ScanRuler by Stefan Hermann (CNC Kitchen)."
PIN_AGENT = (0.85, 0.45, 0.15)


def hooks_reviewers():
    from . import hooks

    return bool(hooks.REVIEWERS)


def credit_text():
    """Agent Link's line, then each loaded extension's own credit and
    licence (an extension porting ScanRuler's tools names Stefan Hermann
    there, where his work loads)."""
    from . import families

    lines = [CREDIT]
    for e in getattr(families, "EXTENSIONS", []):
        if e.get("credit"):
            lines.append(e["credit"] + (f" ({e['license']})" if e.get("license") else ""))
    return "\n".join(lines)


from .usage import strip as usage_strip, text as usage_text  # noqa: E402
PIN_PERSON = (0.25, 0.55, 0.85)
PIN_DONE = (0.55, 0.55, 0.55)


def _doc():
    return FreeCAD.ActiveDocument


def _check_geometry(label):
    """Part Check Geometry on the body labelled label: selected, then the
    command run, as the person would from the Part menu."""
    doc = _doc()
    objs = doc.getObjectsByLabel(label) if doc is not None else []
    if not objs:
        return False
    try:
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(objs[0])
        FreeCADGui.runCommand("Part_CheckGeometry", 0)
        return True
    except Exception as e:
        FreeCAD.Console.PrintLog(f"Agent Link: Part_CheckGeometry did not open: {e}\n")
        return False


def _view():
    gd = FreeCADGui.ActiveDocument
    return gd.activeView() if gd else None


def _scene():
    v = _view()
    return v.getSceneGraph() if v and hasattr(v, "getSceneGraph") else None


class Pins:
    """The notes' pins in the 3D view: a marker each, coloured by who wrote
    it and greyed when done, with its number beside it."""

    def __init__(self):
        from pivy import coin

        self.coin = coin
        self.root = coin.SoSeparator()
        self.root.setName("AgentLinkPins")
        self.attached = None

    def show(self, notes, shown=True):
        coin = self.coin
        self.root.removeAllChildren()
        sg = _scene()
        if sg is not self.attached:
            if self.attached is not None:
                self.attached.removeChild(self.root)
            if sg is not None:
                sg.addChild(self.root)
            self.attached = sg
        if not shown:
            return
        for n in notes:
            sep = coin.SoSeparator()
            mat = coin.SoMaterial()
            col = PIN_DONE if n.get("done") else PIN_AGENT if n["by"] == "agent" else PIN_PERSON
            mat.diffuseColor = col
            mat.emissiveColor = col
            tr = coin.SoTranslation()
            tr.translation = tuple(n["at"])
            style = coin.SoMarkerSet()
            co = coin.SoCoordinate3()
            co.point.setValue(0, 0, 0)
            style.markerIndex = FreeCADGui.getMarkerIndex("CIRCLE_FILLED", 15)
            font = coin.SoFont()
            font.size = 20
            txt = coin.SoText2()
            txt.string = f"  {n['id']}"
            for c in (mat, tr, co, style, font, txt):
                sep.addChild(c)
            self.root.addChild(sep)

    def remove(self):
        if self.attached is not None:
            self.attached.removeChild(self.root)
            self.attached = None


class Stage:
    """One step of a body drawn in the view in place of the body: the
    feature's own shape (PartDesign keeps the solid as it stood after each
    feature), with the body hidden while it plays and shown again after."""

    def __init__(self):
        from pivy import coin

        self.coin = coin
        self.root = None
        self.body = None
        self.was = None

    def show(self, body, feature):
        coin = self.coin
        self.clear_node()
        if self.body is None:
            self.body, self.was = body, body.ViewObject.Visibility
            body.ViewObject.Visibility = False
        sh = feature.Shape
        if sh.isNull():
            return
        inp = coin.SoInput()
        inp.setBuffer(sh.writeInventor())
        node = coin.SoDB.readAll(inp)
        if node is None:
            return
        self.root = coin.SoSeparator()
        mat = coin.SoMaterial()
        mat.diffuseColor = (0.72, 0.45, 0.30)
        self.root.addChild(mat)
        self.root.addChild(node)
        sg = _scene()
        if sg is not None:
            sg.addChild(self.root)

    def clear_node(self):
        if self.root is not None:
            sg = _scene()
            if sg is not None:
                sg.removeChild(self.root)
            self.root = None

    def stop(self):
        self.clear_node()
        if self.body is not None:
            try:
                self.body.ViewObject.Visibility = self.was
            except Exception:
                pass
        self.body = self.was = None


class Panel(Tabs, QtWidgets.QDockWidget if QtWidgets else object):
    def __init__(self):
        super().__init__("Agent Link")
        self.setObjectName("AgentLinkPanel")
        self.pins = Pins()
        self.stage = Stage()
        self.placing = False
        self.callback = None
        self.seen = None
        self.steps, self.at = [], -1
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.play_timer = QtCore.QTimer(self)
        self.play_timer.timeout.connect(self.next_step)

        # Add-ons are loaded first (if no session has loaded them yet), so
        # their tabs and reviewers are known before the tabs are built.
        import importlib

        from . import families, hooks

        for n in families._discovered():
            try:
                importlib.import_module(n)
            except Exception as e:
                FreeCAD.Console.PrintLog(f"Agent Link panel: {n} left out ({e})\n")
        tabs = QtWidgets.QTabWidget()
        # Narrow docks: the tab bar scrolls rather than squeezing the panel
        # wide, and each tab keeps its whole name (eliding cut all eleven to
        # "Not…", "Ste…" in the GUI pass on the Mac).
        tabs.setUsesScrollButtons(True)
        tabs.setElideMode(QtCore.Qt.ElideNone)
        tabs.tabBar().setExpanding(False)
        # Agent Link's tabs and the add-ons' (hooks.register_tab) in one
        # order, each built once: fill() on an add-on's widget, if it has
        # one, each time its tab comes up. Only the tabs that matter in the
        # workbench in front are in the bar (filter_tabs, at each switch).
        own = {"Notes": self._notes_tab, "Steps": self._steps_tab, "Review": self._review_tab, "Activity": self._activity_tab}
        factories = {t["title"]: t["factory"] for t in hooks.TABS}
        self.addon_tabs = {}
        self.pages = {}
        self.rows = []
        for title, order, addon in tab_order(list(hooks.TABS)):
            if not addon:
                self.pages[title] = own[title]()
            else:
                try:
                    wdg = factories[title](self)
                except Exception as e:
                    FreeCAD.Console.PrintLog(f"Agent Link panel: the {title} tab of an add-on was left out ({e})\n")
                    continue
                self.pages[title] = wdg
                self.addon_tabs[title] = wdg
            self.rows.append((title, order, addon))
        # Pages not in the bar stay children of the panel, hidden (never a
        # window of their own).
        self._shelf = QtWidgets.QWidget(self)
        self._shelf.hide()
        for page in self.pages.values():
            page.setParent(self._shelf)
        self.extra = set()
        self.tabs = tabs
        tabs.currentChanged.connect(self._tab_changed)
        self.filter_tabs(layout.active_workbench())
        box = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(6, 6, 6, 6)
        # The link: on or off, and the document the agent works in.
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("AgentLinkStatus")
        self.status.setWordWrap(True)
        self.link_key = QtWidgets.QPushButton("")
        self.link_key.setToolTip("Start or stop the agent's link to this window")
        self.link_key.clicked.connect(self.toggle_link)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.status, 1)
        row.addWidget(self.link_key)
        lay.addLayout(row)
        # Extensions' widgets above the tabs (agentlink/ext.py).
        from . import ext

        self.extras = []
        for make in ext.panel_widgets:
            try:
                wdg = make(self)
                lay.addWidget(wdg)
                self.extras.append(wdg)
            except Exception as e:
                FreeCAD.Console.PrintLog(f"Agent Link panel extension: {e}\n")
        lay.addWidget(tabs)
        # What the agent's work here has cost, apart from any credit:
        # Agent Link's own estimate, not a bill.
        self.usage = QtWidgets.QPushButton("")
        self.usage.setObjectName("AgentLinkUsage")
        self.usage.setFlat(True)
        self.usage.setStyleSheet("text-align: left; font-size: 10px; padding: 0;")
        self.usage.setToolTip("Tokens through Agent Link, estimated here; not your bill. Click for where they went.")
        self.usage.clicked.connect(self.usage_breakdown)
        lay.addWidget(self.usage)
        self._usage_seen = 0.0
        credit = self.credit = QtWidgets.QLabel(credit_text())
        credit.setObjectName("AgentLinkCredit")
        credit.setWordWrap(True)
        credit.setStyleSheet("font-size: 10px;")
        lay.addWidget(credit)
        self.setWidget(box)
        # Accents from FreeCAD's theme on these widgets only, again whenever
        # the palette changes (a Studio pack applied restyles the panel).
        from . import theme

        theme.follow(self, panel_qss)
        self._tab_changed(tabs.currentIndex())
        self.refresh()

    def filter_tabs(self, active, extra=()):
        """The tab bar for the workbench active: tabs_for's titles in order,
        the tab in front kept when it stays. extra: titles asked for by name
        (until the next switch)."""
        from . import hooks

        self.extra = set(extra)
        want = tabs_for(self.rows, active, hooks.TAB_WORKBENCHES, self.extra)
        t = self.tabs
        have = [t.tabText(i) for i in range(t.count())]
        if have == want:
            return want
        cur = t.tabText(t.currentIndex()) if t.count() else None
        t.blockSignals(True)
        while t.count():
            t.removeTab(0)
        for title in want:
            t.addTab(self.pages[title], title)
        # The first time a workbench with its own tab opens, that tab comes
        # forward; after that the tab in front stays.
        seen = self.__dict__.setdefault("seen_wb", set())
        own = [x for x in want if x in self.addon_tabs and active in hooks.TAB_WORKBENCHES.get(x, ())]
        if own and active not in seen:
            t.setCurrentIndex(want.index(own[0]))
        elif cur in want:
            t.setCurrentIndex(want.index(cur))
        seen.add(active)
        t.blockSignals(False)
        self._tab_changed(t.currentIndex())
        return want

    def show_tab(self, title):
        """title's tab in front, put in the bar for now if this workbench
        does not show it. False when no such tab was built."""
        if title not in self.pages:
            return False
        if self.tabs.indexOf(self.pages[title]) < 0:
            self.filter_tabs(layout.active_workbench(), self.extra | {title})
        self.tabs.setCurrentWidget(self.pages[title])
        return True

    def fronts(self):
        """The workbenches whose own content this panel holds: Agent Link's,
        and those an add-on's tab is registered for."""
        from . import hooks

        out = {HOME}
        for title in self.addon_tabs:
            out |= set(hooks.TAB_WORKBENCHES.get(title, ()))
        return out

    def _tab_changed(self, k):
        title = self.tabs.tabText(k) if k >= 0 else ""
        if hasattr(self, "credit"):
            self.credit.setVisible(credit_shown(title, self.pages.get(title)))
        if title:
            self.fill_tab(title)

    def showEvent(self, e):
        if not self.timer.isActive():  # closed with its X before
            self.timer.start(1000)
        super().showEvent(e)

    def _empty(self, tab):
        """The tab's plain line on what it is for, shown while it is empty."""
        lab = QtWidgets.QLabel(EMPTY[tab])
        lab.setObjectName("AgentLinkEmpty")
        lab.setWordWrap(True)
        lab.setVisible(False)
        return lab

    def refresh_status(self):
        import agentlink_state

        link = agentlink_state.link
        on = link is not None
        doc = getattr(getattr(link, "session", None), "doc", None) if on else None
        try:
            label = doc.Label if doc is not None else None
        except Exception:  # the document was closed under the link
            label = None
        text = link_status(on, label)
        self.link_key.setText("Stop link" if on else "Start link")
        if text != self.status.text():
            self.status.setText(text)
            self.status.setProperty("on", on)
            # The [on] rule takes effect only once the label is polished again.
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)

    def toggle_link(self):
        """Start link or Stop link, as the workbench's buttons do."""
        import agentlink_state

        # The commands' own code: they may not be registered yet (the link
        # autostarts before the Agent Link workbench is ever opened).
        from .commands import _StartLink, _StopLink

        try:
            (_StopLink() if agentlink_state.link is not None else _StartLink()).Activated()
        except OSError as e:  # the port is taken
            FreeCAD.Console.PrintWarning(f"Agent Link: link not started ({e})\n")
            agentlink_state.link = None
        self.refresh_status()

    # -- notes --

    def _notes_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        row = QtWidgets.QHBoxLayout()
        self.pin_key = QtWidgets.QPushButton("Pin a Note")
        self.pin_key.setCheckable(True)
        self.pin_key.setToolTip("Click the part to pin a note there")
        self.pin_key.toggled.connect(self.set_placing)
        self.show_pins = QtWidgets.QCheckBox("Pins")
        self.show_pins.setChecked(True)
        self.show_pins.setToolTip("Show the pins on the part (hide them for a picture)")
        self.show_pins.toggled.connect(lambda _: self.refresh(force=True))
        row.addWidget(self.pin_key)
        row.addStretch(1)
        row.addWidget(self.show_pins)
        lay.addLayout(row)
        # What to do next, while Pin a Note waits for the click.
        self.pin_hint = QtWidgets.QLabel(PIN_HINT)
        self.pin_hint.setWordWrap(True)
        self.pin_hint.setVisible(False)
        lay.addWidget(self.pin_hint)
        self.notes_empty = self._empty("Notes")
        lay.addWidget(self.notes_empty)
        self.note_list = QtWidgets.QTreeWidget()
        self.note_list.setHeaderLabels(["#", "Note", "Answer"])
        self.note_list.setRootIsDecorated(False)
        self.note_list.setColumnWidth(0, 52)
        self.note_list.setColumnWidth(1, 150)
        self.note_list.itemChanged.connect(self.tick)
        self.note_list.itemDoubleClicked.connect(self.edit_note)
        lay.addWidget(self.note_list)
        # Delete sits at the right at its own size, and only works with a
        # note picked (a full-width button under an empty table, in the GUI pass).
        dele = QtWidgets.QPushButton("Delete")
        dele.setToolTip("Take the picked note out")
        dele.clicked.connect(self.delete_note)
        dele.setEnabled(False)
        self.note_list.itemSelectionChanged.connect(lambda: dele.setEnabled(bool(self.note_list.selectedItems())))
        drow = QtWidgets.QHBoxLayout()
        drow.addStretch(1)
        drow.addWidget(dele)
        lay.addLayout(drow)
        return w

    def set_placing(self, on):
        self.placing = on
        hint = getattr(self, "pin_hint", None)
        if hint is not None:
            hint.setVisible(bool(on))
        v = _view()
        if v is None:
            return
        if on and self.callback is None:
            self.callback = v.addEventCallback("SoMouseButtonEvent", self.clicked)
            self.key_callback = v.addEventCallback("SoKeyboardEvent", self.key)
        elif not on and self.callback is not None:
            for kind, cb in (("SoMouseButtonEvent", self.callback), ("SoKeyboardEvent", getattr(self, "key_callback", None))):
                try:
                    if cb is not None:
                        v.removeEventCallback(kind, cb)
                except Exception:
                    pass
            self.callback = self.key_callback = None

    def key(self, ev):
        if pin_event(dict(ev, Type="SoKeyboardEvent")) == "cancel":
            self.pin_key.setChecked(False)

    def clicked(self, ev):
        if pin_event(ev) != "place":
            return
        v = _view()
        info = v.getObjectInfo(ev["Position"]) if v else None
        if not info:
            return
        at = [info["x"], info["y"], info["z"]]
        doc = _doc()
        obj = doc.getObject(info.get("Object", "")) if doc else None
        # The click is made: the hint goes before the prompt comes up.
        self.pin_key.setChecked(False)
        text, ok = QtWidgets.QInputDialog.getText(self, "Note", "What the note says:")
        if ok and text.strip():
            nf.add_note(doc, at, text.strip(), "person", obj.Label if obj else None, info.get("Component"))
            self.refresh(force=True)

    def tick(self, item, col):
        if col != 0 or self._filling:
            return
        doc = _doc()
        data = nf.notes_of(doc)
        n = nf.find_note(data, int(item.data(0, QtCore.Qt.UserRole)))
        n["done"] = item.checkState(0) == QtCore.Qt.Checked
        nf.save_notes(doc, data)
        self.refresh(force=True)

    def edit_note(self, item, col):
        doc = _doc()
        data = nf.notes_of(doc)
        n = nf.find_note(data, int(item.data(0, QtCore.Qt.UserRole)))
        if n["by"] == "agent":
            # The agent's question: the person's words go in as its answer.
            text, ok = QtWidgets.QInputDialog.getText(self, "Answer", n["text"], text=n.get("answer", ""))
            key = "answer"
        else:
            text, ok = QtWidgets.QInputDialog.getText(self, "Note", "What the note says:", text=n["text"])
            key = "text"
        if ok:
            n[key] = text.strip()
            nf.save_notes(doc, data)
            self.refresh(force=True)

    def delete_note(self):
        item = self.note_list.currentItem()
        if item is None:
            return
        doc = _doc()
        data = nf.notes_of(doc)
        data["notes"] = [n for n in data["notes"] if n["id"] != int(item.data(0, QtCore.Qt.UserRole))]
        nf.save_notes(doc, data)
        self.refresh(force=True)

    _filling = False

    def refresh_usage(self):
        import time

        if time.time() - self._usage_seen < 30:
            return
        self._usage_seen = time.time()
        try:
            from . import usage

            u = usage_strip(usage.report(7))
        except Exception as e:  # noqa: BLE001 — the strip is a convenience
            FreeCAD.Console.PrintLog(f"Agent Link usage strip: {e}\n")
            return
        self.usage.setText(u)

    def usage_breakdown(self):
        try:
            from . import usage

            r = usage.report(7)
        except Exception as e:  # noqa: BLE001
            r = {"error": str(e)}
        box = QtWidgets.QMessageBox(self)
        from .commands import set_box_text

        set_box_text(box, "Agent Link Usage", usage_text(r))
        box.exec_() if hasattr(box, "exec_") else box.exec()

    def refresh(self, force=False):
        if hasattr(self, "usage"):
            self.refresh_usage()
        if hasattr(self, "status"):
            self.refresh_status()
        for wdg in getattr(self, "extras", []):
            try:
                if hasattr(wdg, "refresh"):
                    wdg.refresh()
            except Exception:
                pass
        doc = _doc()
        notes = nf.notes_of(doc)["notes"] if doc else []
        key = (doc.Name if doc else None, repr(notes), self.show_pins.isChecked())
        if key == self.seen and not force:
            return
        self.seen = key
        self._filling = True
        self.note_list.clear()
        for n in notes:
            who = "Agent: " if n["by"] == "agent" else ""
            it = QtWidgets.QTreeWidgetItem([str(n["id"]), who + n["text"], n.get("answer", "")])
            it.setData(0, QtCore.Qt.UserRole, n["id"])
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(0, QtCore.Qt.Checked if n.get("done") else QtCore.Qt.Unchecked)
            it.setToolTip(1, n["text"])
            self.note_list.addTopLevelItem(it)
        self._filling = False
        self.notes_empty.setVisible(not notes)
        try:
            self.pins.show(notes, self.show_pins.isChecked())
        except Exception as e:  # a view without a scene (a TechDraw page in front)
            FreeCAD.Console.PrintLog(f"Agent Link pins: {e}\n")
        self.fill_bodies()

    # -- review: the part's verdict, as ScanRuler's review panel --

    def _review_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        row = QtWidgets.QHBoxLayout()
        self.review_pick = QtWidgets.QComboBox()
        self.review_pick.setToolTip("The body to review")
        go = QtWidgets.QPushButton("Check")
        go.setToolTip("The installed reviewer's verdict on the body" if hooks_reviewers() else NO_REVIEWER)
        go.setEnabled(hooks_reviewers())
        go.clicked.connect(self.review)
        # With no reviewer installed: the core soundness check.
        self.sound_btn = QtWidgets.QPushButton("Body check")
        self.sound_btn.setToolTip("FreeCAD's Check Geometry on the body (Part workbench), with Agent Link's sliver and short-edge findings listed here")
        self.sound_btn.clicked.connect(self.body_check)
        row.addWidget(self.review_pick, 1)
        row.addWidget(go)
        row.addWidget(self.sound_btn)
        lay.addLayout(row)
        self.verdict = QtWidgets.QLabel(review_hint(hooks_reviewers()))
        self.verdict.setWordWrap(True)
        self.verdict.setStyleSheet("font-weight: 600; font-size: 14px; padding: 4px;")
        lay.addWidget(self.verdict)
        self.findings = QtWidgets.QTreeWidget()
        self.findings.setHeaderLabels(["", "Finding", "Do"])
        self.findings.setRootIsDecorated(False)
        self.findings.setColumnWidth(0, 28)
        self.findings.itemClicked.connect(self._finding_picked)
        lay.addWidget(self.findings, 1)
        self.figures = QtWidgets.QLabel("")
        self.figures.setWordWrap(True)
        lay.addWidget(self.figures)
        return w

    def _call(self, name, args, quiet=False):
        """A tool, run as the agent's would be (so it is shown and logged).
        quiet: a panel's own refresh, not a click: nothing shown, nothing in
        Activity (the session's quiet_call, read by echo)."""
        import json

        import agentlink_state

        if quiet and agentlink_state.link is None and _doc() is None:
            # A refresh with no document open makes none (a new "AgentLink"
            # document appeared just from opening a panel).
            return False, {"error": {"code": "invalid_state", "message": "No document open."}}
        from . import layout

        # A refresh leaves the window's modified marks as they were.
        with (layout.keep_marks() if quiet else _Nothing()):
            session, server = self._server()
            was = getattr(session, "quiet_call", False)
            session.quiet_call = bool(quiet)
            from .hooks import as_person

            # A click here is the person's call, not the agent's.
            try:
                with as_person(session):
                    r = server.call({"name": name, "arguments": args})
            finally:
                session.quiet_call = was
        return not r.get("isError"), json.loads(r["content"][0]["text"])

    _call.quiet_ok = True  # an add-on may pass quiet=True

    def _server(self):
        """(session, server): the link's, or with no link on the panel's own."""
        import agentlink_state

        link = agentlink_state.link
        if link is None or link.server is None:
            import os

            from .tools import Session, build_server

            # No link on: a server of the panel's own, kept, its files where
            # the link's go.
            out = os.path.expanduser("~/AgentLink")
            os.makedirs(out, exist_ok=True)
            own = getattr(self, "_own", None)
            if own is None or own[0].doc is not _doc():
                sess = Session(doc=_doc(), out_dir=out)
                own = self._own = (sess, build_server(sess))
            return own
        link._ready()
        return link.session, link.server

    def review(self):
        """The verdict of the reviewers add-ons registered
        (hooks.register_reviewer), the first that answers; none names a tool
        here."""
        from . import hooks

        body = self.review_pick.currentText()
        if not body:
            return
        self.findings.clear()
        out = hooks.review(self._server()[0], body) if hooks.REVIEWERS else None
        if out is None:
            self.verdict.setText(NO_REVIEWER)
            self.figures.setText("")
            return
        if not isinstance(out, dict) or out.get("error"):
            err = out.get("error") if isinstance(out, dict) else None
            self.verdict.setText("Could not review: " + ((err or {}).get("message", "") if isinstance(err, dict) else str(err or out)))
            return
        v = out.get("verdict", "?")
        r = self._roles()
        colour = {"pass": r["ok"], "warn": r["warn"], "fail": r["bad"]}.get(v, "palette(text)")
        self.verdict.setText(f"<span style='color:{colour}'>{v.upper()}</span> — {body}, made by {out.get('process', 'unknown')}")
        self._last_findings = out.get("findings") or []
        for f in self._last_findings:
            sev = {"error": "✗", "warning": "!", "info": "·"}.get(str(f.get("severity", "")).lower(), "·")
            it = QtWidgets.QTreeWidgetItem([sev, str(f.get("message") or f.get("what") or f.get("id", "")), str(f.get("fix") or f.get("do") or "")])
            it.setToolTip(1, it.text(1))
            it.setToolTip(2, it.text(2))
            self.findings.addTopLevelItem(it)
        if not self._last_findings:
            self.findings.addTopLevelItem(QtWidgets.QTreeWidgetItem(["", "Nothing found", ""]))
        fig = out.get("figures") or {}
        self.figures.setText("  ·  ".join(f"{k} {v}" for k, v in fig.items()) + (f"\n{out.get('processFrom')}" if out.get("processFrom") else ""))

    def body_check(self):
        """FreeCAD's own Check Geometry opened on the body (its task panel),
        and Agent Link's extras (slivers, short edges) as the Review tab's
        findings."""
        body = self.review_pick.currentText()
        if not body:
            return
        _check_geometry(body)
        ok, out = self._call("body_check", {"body": body})
        self.findings.clear()
        if not ok:
            self.verdict.setText("Could not check: " + (out.get("error") or {}).get("message", ""))
            return
        sound = out.get("ok")
        colour = self._roles()["ok" if sound else "bad"]
        self.verdict.setText(f"<span style='color:{colour}'>{'SOUND' if sound else 'NOT SOUND'}</span> — {body}" + ("" if hooks_reviewers() else f" ({NO_REVIEWER})"))
        self._last_findings = []
        for msg in out.get("problems") or []:
            self.findings.addTopLevelItem(QtWidgets.QTreeWidgetItem(["✗", str(msg), ""]))
        if not out.get("problems"):
            self.findings.addTopLevelItem(QtWidgets.QTreeWidgetItem(["", "Nothing found", ""]))
        self.figures.setText("  ·  ".join(f"{k} {out[k]}" for k in ("solids", "volume", "area") if k in out))

    def _roles(self):
        from . import theme

        return theme.roles(self)

    def _finding_picked(self, item, _col):
        """A finding with a place: point the view at it."""
        k = self.findings.indexOfTopLevelItem(item)
        f = (getattr(self, "_last_findings", None) or [None] * (k + 1))[k] if k >= 0 else None
        at = (f or {}).get("at")
        if isinstance(at, list) and len(at) == 3:
            v = FreeCADGui.ActiveDocument.activeView() if FreeCADGui.ActiveDocument else None
            if v is not None and hasattr(v, "viewPosition"):
                try:
                    cam = v.getCameraNode()
                    cam.focalDistance.getValue()
                    from pivy import coin

                    cam.pointAt(coin.SbVec3f(*at), coin.SbVec3f(0, 0, 1))
                except Exception:
                    pass

    # -- activity: what the agent did, call by call --

    def _activity_tab(self):
        from . import echo

        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        row = QtWidgets.QHBoxLayout()
        prefs = FreeCAD.ParamGet(echo.PREFS)
        self.echo_on = QtWidgets.QCheckBox("Agent's steps")
        self.echo_on.setToolTip("Show the agent's steps: workbench, button, selection and a caption for each thing the agent does")
        self.echo_on.setChecked(prefs.GetBool("Echo", True))
        self.echo_on.toggled.connect(lambda on: prefs.SetBool("Echo", on))
        self.pace = QtWidgets.QComboBox()
        self.pace.setToolTip("How long each step stays up before the agent goes on")
        paces = [("Fast", 0), ("Normal", 350), ("Slow", 900)]
        for label, _ms in paces:
            self.pace.addItem(label)
        cur = prefs.GetInt("EchoDelay", 350)
        self.pace.setCurrentIndex(min(range(3), key=lambda i: abs(paces[i][1] - cur)))
        self.pace.currentIndexChanged.connect(lambda i: prefs.SetInt("EchoDelay", paces[i][1]))
        row.addWidget(self.echo_on)
        self.follow = QtWidgets.QCheckBox("Follow")
        self.follow.setToolTip("Frame the part in the view after each change the agent makes")
        self.follow.setChecked(prefs.GetBool("Follow", True))
        self.follow.toggled.connect(lambda on: prefs.SetBool("Follow", on))
        row.addWidget(self.follow)
        row.addStretch(1)
        row.addWidget(self.pace)
        lay.addLayout(row)
        self.activity_empty = self._empty("Activity")
        self.activity_empty.setVisible(True)
        lay.addWidget(self.activity_empty)
        self.activity = QtWidgets.QTreeWidget()
        self.activity.setHeaderLabels(["Time", "Did", "Result"])
        self.activity.setRootIsDecorated(False)
        # A narrow dock cuts the lines: cut in the middle (both ends read),
        # the last column takes what is left, the whole line in the tooltip.
        self.activity.setTextElideMode(QtCore.Qt.ElideMiddle)
        head = self.activity.header()
        head.setStretchLastSection(True)
        self.activity.setColumnWidth(0, 64)
        self.activity.setColumnWidth(1, 150)
        lay.addWidget(self.activity)
        for e in echo.log():
            self._add_activity(e)
        echo.listen(self._add_activity)
        return w

    def _add_activity(self, e):
        cols, whole = activity_row(e)
        it = QtWidgets.QTreeWidgetItem(cols)
        for c in range(3):
            it.setToolTip(c, whole)
        self.activity.addTopLevelItem(it)
        self.activity.scrollToItem(it)
        self.activity_empty.setVisible(False)

    # -- steps --

    def _steps_tab(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        self.body_pick = QtWidgets.QComboBox()
        self.body_pick.setToolTip("The PartDesign body to play")
        self.body_pick.currentIndexChanged.connect(lambda _: self.load_steps())
        lay.addWidget(self.body_pick)
        self.steps_empty = self._empty("Steps")
        lay.addWidget(self.steps_empty)
        self.step_list = QtWidgets.QListWidget()
        self.step_list.currentRowChanged.connect(self.go_to)
        lay.addWidget(self.step_list)
        self.caption = QtWidgets.QLabel("")
        self.caption.setObjectName("AgentLinkCaption")
        self.caption.setWordWrap(True)
        self.caption.setStyleSheet("font-weight: 600; padding: 4px;")
        lay.addWidget(self.caption)
        keys = FlowRow()
        for label, tip, fn in (("Play", "Play the build from the top", self.play), ("Pause", "Hold on this step", self.pause),
                               ("Step", "The next step", self.next_step), ("Stop", "End the playback and show the part again", self.stop)):
            b = QtWidgets.QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            keys.addWidget(b)
        lay.addWidget(keys)
        save = QtWidgets.QPushButton("Save as Macro…")
        save.setToolTip("Keep this session's steps as a FreeCAD macro to run again (it runs once you approve it)")
        save.clicked.connect(self.save_macro)
        lay.addWidget(save)
        return w

    def save_macro(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Save as Macro", "Macro name:")
        if not ok or not name.strip():
            return
        done, r = self._call("macro_save", {"name": name.strip()})
        from .commands import info

        info(self, "Agent Link", (f"Saved {r.get('path') or name}." + (" It runs once you approve it." if done else ""))
                                          if done else (r.get("error") or {}).get("message", str(r)))

    def fill_bodies(self):
        doc = _doc()
        names = [o.Label for o in doc.Objects if o.TypeId == "PartDesign::Body"] if doc else []
        have = [self.body_pick.itemText(i) for i in range(self.body_pick.count())]
        solids = [o.Label for o in doc.Objects if hasattr(o, "Shape") and o.TypeId in ("PartDesign::Body", "Part::Feature", "Part::Box", "Part::Cylinder") and not any(p.TypeId == "PartDesign::Body" for p in o.InList)] if doc else []
        if [self.review_pick.itemText(i) for i in range(self.review_pick.count())] != solids:
            keep = self.review_pick.currentText()
            self.review_pick.clear()
            self.review_pick.addItems(solids)
            if keep in solids:
                self.review_pick.setCurrentIndex(solids.index(keep))
        self.steps_empty.setVisible(not names)
        if names != have:
            cur = self.body_pick.currentText()
            self.body_pick.blockSignals(True)
            self.body_pick.clear()
            self.body_pick.addItems(names)
            if cur in names:
                self.body_pick.setCurrentIndex(names.index(cur))
            self.body_pick.blockSignals(False)
            self.load_steps()

    def _body(self):
        doc = _doc()
        lab = self.body_pick.currentText()
        return next((o for o in doc.Objects if o.TypeId == "PartDesign::Body" and o.Label == lab), None) if doc else None

    def load_steps(self):
        b = self._body()
        self.steps = nf.steps_of(b) if b else []
        self.step_list.blockSignals(True)
        self.step_list.clear()
        for r in self.steps:
            self.step_list.addItem(f"{r['step']}. {r['label']}" + (f"  ({r['key']})" if r.get("key") else ""))
        self.step_list.blockSignals(False)

    def go_to(self, k):
        b = self._body()
        if b is None or not (0 <= k < len(self.steps)):
            return
        self.at = k
        r = self.steps[k]
        self.stage.show(b, _doc().getObject(r["name"]))
        did = r.get("change", 0)
        what = f"added {did:.0f} mm³" if did > 0.5 else f"took away {-did:.0f} mm³" if did < -0.5 else "no change to the volume"
        self.caption.setText(step_caption(r, len(self.steps), what))
        FreeCADGui.updateGui()

    def play(self):
        self.load_steps()
        if not self.steps:
            return
        self.step_list.setCurrentRow(0)
        self.go_to(0)
        self.play_timer.start(1200)

    def pause(self):
        self.play_timer.stop()

    def next_step(self):
        if self.at + 1 >= len(self.steps):
            self.play_timer.stop()
            return
        self.step_list.setCurrentRow(self.at + 1)

    def stop(self):
        self.play_timer.stop()
        self.stage.stop()
        self.caption.setText("")
        self.at = -1

    def closeEvent(self, e):
        self.stop()
        self.set_placing(False)
        self.pins.remove()
        self.timer.stop()
        super().closeEvent(e)


class _Nothing:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Caller:
    """Runs a tool as the panel does (shown and logged as the agent's are)
    with no panel built: Panel's own _call and _server."""


_Caller._call = Panel.__dict__["_call"]
_Caller._server = Panel.__dict__["_server"]
_CALLER = []


def caller():
    """What runs an add-on's clicks through Agent Link: the panel, once it is
    built (its session shared), else a caller of its own."""
    if _panel is not None:
        return _panel
    if not _CALLER:
        _CALLER.append(_Caller())
    return _CALLER[0]


class CallerService:
    """The service "panel_caller": an add-on's own dock runs its tools
    through Agent Link with it (_call), and reads the session the panel's
    own server works in (_own) when no link is on."""

    def _call(self, tool, args, quiet=False):
        return caller()._call(tool, args, quiet=quiet)

    _call.quiet_ok = True

    @property
    def _own(self):
        # Only what is there: reading it never makes a session (nor, with
        # no document open, a new "AgentLink" document).
        return getattr(caller(), "_own", None)


_panel = None
KEY = "AgentLinkPanel"


def _switched(name):
    """A workbench switch: the tabs that matter there, then the panel placed
    by the layout setting (agentlink/layout.py)."""
    if _panel is None:
        return
    try:
        with layout.keep_marks():
            _panel.filter_tabs(str(name))
        e = layout.own().entries.get(KEY)
        if e is not None:
            e["fronts"] = _panel.fronts()
    except RuntimeError:  # the panel was deleted
        pass


def show(tab=None):
    """Open the panel where the layout setting puts it (a Combo View tab by default);
    a second call brings it forward. tab: that tab in front, put in the bar
    for now if this workbench does not show it."""
    global _panel
    mw = FreeCADGui.getMainWindow()
    first = _panel is None
    if first:
        _panel = Panel()
        # Before the placer's own handler, so the tabs are right when it
        # places the panel.
        mw.workbenchActivated.connect(_switched)
        from .echo import fit

        QtCore.QTimer.singleShot(400, fit)
        try:  # the Report view kept out of the way from the first placement
            from . import report_watch

            report_watch.start_auto()
        except Exception as e:  # noqa: BLE001
            FreeCAD.Console.PrintLog(f"Agent Link Report view watch: {e}\n")
    p = layout.own()
    p.show(KEY, _panel, layout.EVERYWHERE, "Agent Link", force=True, fronts=_panel.fronts())
    if tab:
        _panel.show_tab(tab)
    p.reveal(KEY)
    return _panel
