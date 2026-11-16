# SPDX-License-Identifier: LGPL-2.1-or-later
# Helpers for the Agent Link panel's widgets (a quiet colour, a row that
# wraps), the panel's plain words (tab order, what each tab says when it is
# empty, the link line, the theme rules), and filling a tab as it comes up:
# an add-on's tab (hooks.register_tab) fills through its widget's own fill().
# The words and the order need no window, so they are tested headless.

try:
    from PySide import QtCore, QtGui

    QtWidgets = QtGui
    try:
        from PySide import QtWidgets  # noqa: F811  (Qt 6 builds)
    except ImportError:
        pass
except ImportError:  # pragma: no cover
    QtCore = QtGui = QtWidgets = None


from .theme import muted  # noqa: F401  (one copy: the theme's)

# Agent Link's own tabs and their places. Add-ons' tabs (register_tab, with
# their own order) fall between: 30-40 after Steps, 60-90 after Review, and
# Activity stays last.
CORE_TABS = (("Notes", 10), ("Steps", 20), ("Review", 50), ("Activity", 95))

# Agent Link's own workbench, and the tabs that show in every workbench.
HOME = "AgentLinkWorkbench"
ALWAYS = ("Notes", "Steps", "Activity")
# Tabs whose page carries its own credit line for Stefan Hermann's work:
# Agent Link's line is hidden while one is in front (one credit, not two).
OWN_CREDIT = ("ScanRuler", "Texture")

NO_REVIEWER = "No reviewer installed."

# What each of Agent Link's tabs is for, said where its list is empty.
EMPTY = {
    "Notes": "No notes yet. Pin a note to the part to leave it for the agent; the agent's questions to you show here too.",
    "Steps": "No PartDesign body in this document. Steps plays a body's build back, one feature at a time.",
    "Review": "Pick a body and press Check for the reviewer's verdict.",
    "Activity": "Nothing yet. Each thing the agent does in this window shows here as it happens.",
}


def tab_order(addon_tabs):
    """[(title, order, addon)] for the whole tab bar: Agent Link's own and
    the add-ons' (hooks.TABS rows) by order; at the same order Agent Link's
    comes first. An add-on tab with a core tab's title is left out."""
    core = {t for t, _ in CORE_TABS}
    rows = [(t, o, False) for t, o in CORE_TABS]
    rows += [(a["title"], a.get("order", 50), True) for a in addon_tabs if a.get("title") not in core]
    return sorted(rows, key=lambda r: (r[1], r[2]))


def tabs_for(rows, active, where, extra=()):
    """The titles of rows (tab_order's) that show while the workbench
    active is up: Notes, Steps and Activity always; an add-on's tab only in
    the workbenches it was registered for (where: hooks.TAB_WORKBENCHES),
    or everywhere when it named none; Review in Agent Link's own workbench
    and the reviewers' workbenches; extra: titles asked for by name (an
    add-on's Panel command), until the next switch."""
    out = []
    for title, _order, addon in rows:
        wbs = set(where.get(title, ()))
        if title == "Review":
            wbs.add(HOME)
        if title in ALWAYS or title in extra or active in wbs or (addon and title not in where):
            out.append(title)
    return out


# Shown under Pin a Note while it waits for the click on the part.
PIN_HINT = "Click the part where the note goes. Esc cancels."


def pin_event(ev):
    """What a 3D view event means while a note waits to be placed: "place"
    (the left button down), "cancel" (Esc down), else None."""
    if not isinstance(ev, dict) or ev.get("State") != "DOWN":
        return None
    if ev.get("Type") == "SoKeyboardEvent" or "Key" in ev:
        return "cancel" if str(ev.get("Key", "")).upper() in ("ESCAPE", "ESC") else None
    return "place" if ev.get("Button") == "BUTTON1" else None


def credit_shown(title, widget=None):
    """Whether Agent Link's credit line shows under the tab title: not while
    a page that credits Stefan Hermann itself is in front."""
    return not (title in OWN_CREDIT or getattr(widget, "own_credit", False))


def review_hint(has_reviewer):
    """The Review tab's line before any verdict."""
    if has_reviewer:
        return EMPTY["Review"]
    return NO_REVIEWER + " Body check gives the core soundness check: valid, closed, one solid."


def link_status(on, doc_label=None):
    """The line above the tabs: whether the link is on and which document
    the agent works in."""
    if not on:
        return "Link off. Start link lets an agent drive this window."
    if doc_label:
        return f"Link on. The agent works in {doc_label}."
    return "Link on. The agent works in the document in front when it starts."


def panel_qss(r):
    """The panel's accents (theme.roles) as rules on Agent Link's own
    widgets only, each scoped to the panel's object name. Colours only:
    shapes, fonts and surfaces stay FreeCAD's theme's."""
    return "\n".join((
        f"#AgentLinkPanel QLabel#AgentLinkStatus {{ color: {r['muted']}; }}",
        f"#AgentLinkPanel QLabel#AgentLinkStatus[on=\"true\"] {{ color: {r['accent']}; }}",
        f"#AgentLinkPanel QLabel#AgentLinkEmpty {{ color: {r['muted']}; }}",
        f"#AgentLinkPanel QLabel#AgentLinkCaption {{ color: {r['accent']}; }}",
        f"#AgentLinkPanel QPushButton#AgentLinkUsage {{ color: {r['muted']}; }}",
        f"#AgentLinkPanel QLabel#AgentLinkCredit {{ color: {r['muted']}; }}",
    ))


class FlowRow(QtWidgets.QWidget if QtWidgets else object):
    """Buttons in a row that wraps to the next line when the panel is narrow
    (the panel docks beside the model tree, often under 300 px)."""

    def __init__(self, widgets=(), spacing=4):
        super().__init__()
        self._items, self._sp = list(widgets), spacing
        for w in self._items:
            w.setParent(self)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)

    def addWidget(self, w):
        w.setParent(self)
        self._items.append(w)
        self.updateGeometry()

    def _place(self, width, move=True):
        x = y = line = 0
        for w in self._items:
            h = w.sizeHint()
            if x and x + h.width() > width:
                x, y = 0, y + line + self._sp
                line = 0
            if move:
                w.setGeometry(x, y, h.width(), h.height())
            x += h.width() + self._sp
            line = max(line, h.height())
        return y + line

    def resizeEvent(self, e):
        self._place(self.width())

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._place(width, move=False)

    def sizeHint(self):
        w = sum(x.sizeHint().width() + self._sp for x in self._items)
        return QtCore.QSize(min(w, 280), self._place(min(w, 280), move=False))

    def minimumSizeHint(self):
        return QtCore.QSize(max((x.sizeHint().width() for x in self._items), default=0), 0)


class Tabs:
    """Mixed into the Panel: the tabs' refresh as each comes up."""

    def fill_tab(self, title):
        try:
            # An add-on's tab (hooks.register_tab): its widget's fill(), if it has one.
            fill = getattr(getattr(self, "addon_tabs", {}).get(title), "fill", None) or (lambda: None)
            fill()
        except Exception as e:
            import FreeCAD

            FreeCAD.Console.PrintLog(f"Agent Link panel ({title}): {e}\n")
