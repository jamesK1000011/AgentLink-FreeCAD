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
# their own order) fall between: 15 between Notes and Steps (kept free for
# an add-on's tab there), 30-40 after Steps, 60-90 after Review, and
# Activity stays last.
CORE_TABS = (("Notes", 10), ("Steps", 20), ("Review", 50), ("Activity", 95))

# The Activity tab's "Follow agent" check box (agentlink/cowork.py
# FollowAgent): off by default; on until the person turns it off.
FOLLOW_LABEL = "Follow agent"
FOLLOW_TIP = ("Move the view to the agent's work after each change. Off: the view stays where you put it. "
              "The view also stays while you work in it.")


def follow_toggled(on):
    """The check box set: the FollowAgent preference, and the 3D view's input
    watch put on (cowork.watch_view)."""
    from . import cowork

    cowork.set_follow(on)
    if on:
        cowork.watch_view()


# Agent Link's own workbench, and the tabs that show in every workbench.
HOME = "AgentLinkWorkbench"
ALWAYS = ("Notes", "Steps", "Activity")
# A page that carries its own credit line (Stefan Hermann's work, CNC
# Kitchen): Agent Link's line is hidden while it is in front (one credit,
# not two). An add-on says so (register_tab(own_credit=True), or its
# widget's own_credit); a page of an add-on written before that is known by
# a label of its own that credits the work (page_credits).
CREDIT_WORDS = ("stefan hermann", "cnc kitchen")

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


def step_caption(r, count, what):
    """The Steps tab's line for a step: 'Step 1 of 3 — Pad (Length 20.00
    mm): added 24000 mm³.' — the type left out where the label is it."""
    inside = [x for x in (r.get("type") if r.get("type") != r.get("label") else None, r.get("key")) if x]
    return f"Step {r['step']} of {count} — {r['label']}" + (f" ({', '.join(inside)})" if inside else "") + f": {what}."


def activity_row(e):
    """(columns, tooltip) of an Activity entry: time, what was done
    (✗ when refused) and what came of it; the tooltip has the whole line and
    the call as sent, for the curious. Plain words only: any path shows as
    its file name (activity.plain), whatever wrote the entry."""
    from .activity import plain

    did = ("" if e.get("ok", True) else "✗ ") + plain(e.get("what", ""))
    cols = [e.get("time", ""), did, plain(e.get("result", ""))]
    tip = " — ".join(c for c in cols if c)
    if e.get("call"):
        tip += "\n\nCall: " + plain(e["call"])
    return cols, tip


# The Activity list's columns: the time as narrow as it reads, Did taking
# what the dock leaves, Result after it at this share of the width.
ACTIVITY_RESULT_SHARE = 0.38
ACTIVITY_RESULT_MIN = 70


def _enum(owner, group, name):
    """A Qt enum value by its short name, for Qt 5 and Qt 6 alike."""
    v = getattr(owner, name, None)
    if v is None:
        v = getattr(getattr(owner, group), name)
    return v


def setup_activity(tree, QtCore, QtWidgets):
    """The Activity list fitted to a narrow dock: no sideways scroll bar,
    lines cut at the right end (the start of a sentence is what reads; the
    whole line is in the tooltip), Time to its contents, Did stretching."""
    tree.setHeaderLabels(["Time", "Did", "Result"])
    tree.setRootIsDecorated(False)
    tree.setUniformRowHeights(True)
    tree.setWordWrap(False)
    tree.setTextElideMode(_enum(QtCore.Qt, "TextElideMode", "ElideRight"))
    tree.setHorizontalScrollBarPolicy(_enum(QtCore.Qt, "ScrollBarPolicy", "ScrollBarAlwaysOff"))
    head = tree.header()
    head.setStretchLastSection(False)
    head.setMinimumSectionSize(36)
    mode = QtWidgets.QHeaderView
    head.setSectionResizeMode(0, _enum(mode, "ResizeMode", "ResizeToContents"))
    head.setSectionResizeMode(1, _enum(mode, "ResizeMode", "Stretch"))
    head.setSectionResizeMode(2, _enum(mode, "ResizeMode", "Interactive"))
    fit_activity(tree)


def result_width(total):
    """The Result column's width in a list this wide."""
    return max(ACTIVITY_RESULT_MIN, int(total * ACTIVITY_RESULT_SHARE))


def fit_activity(tree):
    """Result's share of the list's width now (on show and on resize)."""
    try:
        w = tree.viewport().width()
    except Exception:
        return
    if w > 0:
        tree.setColumnWidth(2, result_width(w))


# Shown under Pin a note while it waits for the click on the part.
PIN_HINT = "Click the part where the note goes. Esc cancels."


def pin_event(ev):
    """What a 3D view event means while a note waits to be placed: "place"
    (the left button down), "cancel" (Esc down), else None."""
    if not isinstance(ev, dict) or ev.get("State") != "DOWN":
        return None
    if ev.get("Type") == "SoKeyboardEvent" or "Key" in ev:
        return "cancel" if str(ev.get("Key", "")).upper() in ("ESCAPE", "ESC") else None
    return "place" if ev.get("Button") == "BUTTON1" else None


def page_credits(widget):
    """True when the page widget shows a credit line of its own: a label
    under it whose text names the work credited (CREDIT_WORDS)."""
    if widget is None or QtWidgets is None:
        return False
    try:
        labels = widget.findChildren(QtWidgets.QLabel)
    except Exception:  # noqa: BLE001 — a stand-in, or a page already gone
        return False
    for lab in labels:
        try:
            text = str(lab.text()).lower()
        except Exception:  # noqa: BLE001
            continue
        if any(w in text for w in CREDIT_WORDS):
            return True
    return False


def credit_shown(title, widget=None, declared=False):
    """Whether Agent Link's credit line shows under the tab title: not while
    a page that credits the work itself is in front — declared by its
    add-on (register_tab's own_credit, passed as declared), the widget's
    own_credit, or a credit label on the page (page_credits)."""
    if declared or getattr(widget, "own_credit", False):
        return False
    return not page_credits(widget)


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
