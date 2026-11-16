# SPDX-License-Identifier: LGPL-2.1-or-later
# gui_input: mouse and keyboard input for FreeCAD's own window, sent from
# inside FreeCAD as Qt events to the widget under the point, never through
# the system's cursor or keyboard, so the person keeps their screen while a
# GUI check drags a grip, paints with a brush, turns a gizmo ring or clicks
# a panel. The steps are checked here with no Qt or FreeCAD in sight
# (parse_steps, the y-flip and pixel-ratio maths, the answer's cap); Run
# delivers them with the Qt modules it is handed.
#
# Delivery copies what Qt does with a real event where sendEvent would not:
# a press gives focus by the widget's focus policy, the moves and the
# release of a drag go to the widget that took the press (Qt's implicit
# grab), a click lands on the deepest widget at the point. What it cannot
# copy: shortcuts (they are matched before an event reaches a widget) and
# QApplication.mouseButtons(), which only the system's events set.

import json
import math
import re
import time

from .protocol import ToolError, bad

MAX_STEPS = 60
MAX_WAIT = 3000      # ms, one wait step
MAX_TOTAL_WAIT = 20000  # ms, all of a call's waits (a client drops a call after about 80 s)
DRAG_STEPS = 12
MAX_DRAG_STEPS = 200
MOVE_GAP_MS = 8      # between the moves of a drag
MAX_NOTCHES = 50
MAX_TEXT = 2000
ANSWER_MAX = 3000    # characters of the answer's text
BUTTONS = ("left", "right", "middle")
MODIFIERS = ("shift", "ctrl", "alt", "meta")
TARGETS = ("view", "view_world", "widget", "window", "tab", "item")
WIDGET_KEYS = ("objectName", "text", "toolTip", "class", "under")
TAB_KEYS = ("text", "under")
ITEM_KEYS = ("text", "under", "column")
# Where a check box sits in an item's rect: its left edge plus this, in
# logical pixels (Qt's styles draw the indicator a few pixels in, about a
# line's height wide).
CHECK_INSET = 3
SHOT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
KEY_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,23}")
# Keys by the names people use, to Qt's Key_ names.
KEY_ALIASES = {
    "return": "Return", "enter": "Enter", "esc": "Escape", "escape": "Escape", "tab": "Tab", "backtab": "Backtab",
    "backspace": "Backspace", "del": "Delete", "delete": "Delete", "insert": "Insert", "space": "Space",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right", "home": "Home", "end": "End",
    "pageup": "PageUp", "pagedown": "PageDown", "pgup": "PageUp", "pgdown": "PageDown",
}
# The text a real key event of these carries.
KEY_TEXT = {"Return": "\r", "Enter": "\r", "Tab": "\t", "Escape": "\x1b", "Space": " ", "Backspace": "\b"}
# Step kinds and the fields each takes beside its own.
KINDS = {
    "click": ("button", "double", "modifiers"),
    "press": ("button", "modifiers"),
    "move": ("modifiers",),
    "release": ("button", "modifiers"),
    "drag": (),
    "scroll": ("dy", "modifiers"),
    "key": ("modifiers", "target"),
    "type": ("target",),
    "wait": (),
    "shot": (),
}
DRAG_KEYS = ("from", "to", "steps", "button", "modifiers")


# ---- the steps, checked (no Qt) ------------------------------------------------------------

def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _point(v, n, where):
    if not isinstance(v, list) or len(v) != n or not all(_num(x) for x in v):
        raise bad(f"{where}: a list of {n} numbers.")
    return [float(x) for x in v]


def parse_target(t, where):
    """A target as given, checked: { kind, value, at? }."""
    if not isinstance(t, dict):
        raise bad(f"{where}: an object — {{ view: [x, y] }}, {{ view_world: [x, y, z] }}, {{ widget: {{ objectName, text, toolTip, class, under }}, at?: [dx, dy] }} or {{ window: [x, y] }}.")
    kinds = [k for k in TARGETS if k in t]
    if len(kinds) != 1:
        raise bad(f"{where}: one of {', '.join(TARGETS)}.")
    kind = kinds[0]
    extra = [k for k in t if k not in (kind, "at", "check")] + (["at"] if "at" in t and kind != "widget" else []) + (["check"] if "check" in t and kind != "item" else [])
    if extra:
        why = {"at": " (at is for a widget target)", "check": " (check is for an item target)"}.get(extra[0], "")
        raise bad(f"{where}.{extra[0]}: not a field here{why}.")
    if kind in ("tab", "item"):
        keys = TAB_KEYS if kind == "tab" else ITEM_KEYS
        spec = t[kind]
        if not isinstance(spec, dict) or not isinstance(spec.get("text"), str) or not spec["text"].strip():
            raise bad(f"{where}.{kind}: {{ text, {', '.join('%s?' % k for k in keys[1:])} }} — text as the {'tab' if kind == 'tab' else 'row'} shows it.")
        for k, v in spec.items():
            if k not in keys:
                raise bad(f"{where}.{kind}.{k}: not a field — {', '.join(keys)}.")
            if k == "column":
                if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                    raise bad(f"{where}.{kind}.column: a column number, 0 the first.")
            elif not isinstance(v, str) or not v.strip():
                raise bad(f"{where}.{kind}.{k}: text.")
        out = {"kind": kind, "value": dict(spec)}
        if "check" in t:
            if not isinstance(t["check"], bool):
                raise bad(f"{where}.check: true or false.")
            out["check"] = t["check"]
        return out
    if kind == "widget":
        spec = t["widget"]
        if not isinstance(spec, dict) or not spec:
            raise bad(f"{where}.widget: an object with any of {', '.join(WIDGET_KEYS)}.")
        for k, v in spec.items():
            if k not in WIDGET_KEYS:
                raise bad(f"{where}.widget.{k}: not a field — {', '.join(WIDGET_KEYS)}.")
            if not isinstance(v, str) or not v.strip():
                raise bad(f"{where}.widget.{k}: text.")
        out = {"kind": "widget", "value": dict(spec)}
        if "at" in t:
            out["at"] = _point(t["at"], 2, f"{where}.at")
        return out
    n = 3 if kind == "view_world" else 2
    return {"kind": kind, "value": _point(t[kind], n, f"{where}.{kind}")}


def _mods(v, where):
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(m, str) for m in v):
        raise bad(f"{where}: a list of {', '.join(MODIFIERS)}.")
    out = []
    for m in v:
        m = m.lower()
        if m not in MODIFIERS:
            raise bad(f"{where}: {m!r} — one of {', '.join(MODIFIERS)} (ctrl is Qt's Control: ⌘ on the Mac, meta the Control key there).")
        if m not in out:
            out.append(m)
    return out


def _button(v, where):
    if v is None:
        return "left"
    if not isinstance(v, str) or v.lower() not in BUTTONS:
        raise bad(f"{where}: one of {', '.join(BUTTONS)}.")
    return v.lower()


def key_name(v, where="key"):
    """A key as Qt names it (Return, Escape, F2, A …) or one printable
    character: ("name", Key_ name) or ("char", c)."""
    if not isinstance(v, str) or not v:
        raise bad(f"{where}: a key's name (Return, Escape, Tab, Up, F2 …) or one character.")
    if len(v) == 1 and " " < v <= "~":
        return ("char", v)
    if v.lower() in KEY_ALIASES:
        return ("name", KEY_ALIASES[v.lower()])
    if not KEY_NAME.fullmatch(v):
        raise bad(f"{where}: {v!r} — a key's name (Return, Escape, Tab, Up, F2 …) or one character; type sends text.")
    return ("name", v[0].upper() + v[1:])


def parse_step(st, i):
    where = f"steps[{i}]"
    if not isinstance(st, dict):
        raise bad(f"{where}: an object, such as {{ click: {{ view: [200, 150] }} }}.")
    kinds = [k for k in KINDS if k in st]
    if len(kinds) != 1:
        raise bad(f"{where}: one of {', '.join(KINDS)}.")
    kind = kinds[0]
    for k in st:
        if k != kind and k not in KINDS[kind]:
            raise bad(f"{where}.{k}: not a field of a {kind} step — {', '.join(KINDS[kind]) or 'none'}.")
    out = {"do": kind}
    v = st[kind]
    if kind in ("click", "press", "move", "release", "scroll"):
        out["target"] = parse_target(v, f"{where}.{kind}")
        out["mods"] = _mods(st.get("modifiers"), f"{where}.modifiers")
        if kind in ("click", "press", "release"):
            out["button"] = _button(st.get("button"), f"{where}.button")
        if kind == "click":
            d = st.get("double", False)
            if not isinstance(d, bool):
                raise bad(f"{where}.double: true or false.")
            out["double"] = d
        if kind == "scroll":
            dy = st.get("dy")
            if not _num(dy) or dy == 0 or abs(dy) > MAX_NOTCHES:
                raise bad(f"{where}.dy: wheel notches, not 0 and at most {MAX_NOTCHES} either way (over 0 rolls away from you).")
            out["dy"] = float(dy)
    elif kind == "drag":
        if not isinstance(v, dict):
            raise bad(f"{where}.drag: {{ from: target, to: target, steps?, button? }}.")
        for k in v:
            if k not in DRAG_KEYS:
                raise bad(f"{where}.drag.{k}: not a field — {', '.join(DRAG_KEYS)}.")
        if "from" not in v or "to" not in v:
            raise bad(f"{where}.drag: from and to, each a target.")
        out["from"] = parse_target(v["from"], f"{where}.drag.from")
        out["to"] = parse_target(v["to"], f"{where}.drag.to")
        n = v.get("steps", DRAG_STEPS)
        if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_DRAG_STEPS:
            raise bad(f"{where}.drag.steps: moves between press and release, 1 to {MAX_DRAG_STEPS} ({DRAG_STEPS} by default).")
        out["steps"] = n
        out["button"] = _button(v.get("button"), f"{where}.drag.button")
        out["mods"] = _mods(v.get("modifiers"), f"{where}.drag.modifiers")
    elif kind == "key":
        out["key"] = key_name(v, f"{where}.key")
        out["mods"] = _mods(st.get("modifiers"), f"{where}.modifiers")
        out["target"] = parse_target(st["target"], f"{where}.target") if st.get("target") is not None else None
    elif kind == "type":
        if not isinstance(v, str) or not v or len(v) > MAX_TEXT:
            raise bad(f"{where}.type: the text, 1 to {MAX_TEXT} characters.")
        out["text"] = v
        out["target"] = parse_target(st["target"], f"{where}.target") if st.get("target") is not None else None
    elif kind == "wait":
        if isinstance(v, bool) or not _num(v) or not 0 <= v <= MAX_WAIT:
            raise bad(f"{where}.wait: milliseconds, 0 to {MAX_WAIT} — for longer, split it into several waits.")
        out["ms"] = int(v)
    elif kind == "shot":
        name = v[:-4] if isinstance(v, str) and v.lower().endswith(".png") else v
        if not isinstance(name, str) or not SHOT_NAME.fullmatch(name):
            raise bad(f"{where}.shot: a file name (letters, digits, _ . -, at most 64), saved as ~/AgentLink/gui_input/<name>.png.")
        out["name"] = name
    return out


def parse_steps(steps):
    if not isinstance(steps, list) or not steps:
        raise bad("steps: a list of steps, run in order — click, press, move, release, drag, scroll, key, type, wait, shot.")
    if len(steps) > MAX_STEPS:
        raise bad(f"steps: at most {MAX_STEPS} in one call.")
    out = [parse_step(s, i) for i, s in enumerate(steps)]
    if sum(s.get("ms", 0) for s in out) > MAX_TOTAL_WAIT:
        raise bad(f"steps: the waits come to over {MAX_TOTAL_WAIT} ms in one call — split it in two calls.")
    return out


# ---- the maths (no Qt) ---------------------------------------------------------------------

def coin_project(view, p):
    """A world point in the 3D view's Coin viewport (device pixels, origin
    bottom-left) as Coin draws it, and the viewport's size. A tall view
    widens the view volume by 1 / aspect, which FreeCAD's
    getPointOnViewport leaves out, so its points are off there."""
    from pivy import coin

    rm = view.getViewer().getSoRenderManager()
    cam, vp = rm.getCamera(), rm.getViewportRegion()
    a = vp.getViewportAspectRatio()
    vv = cam.getViewVolume(a)
    if 0 < a < 1.0:
        vv.scale(1.0 / a)
    src = coin.SbVec3f(*[float(c) for c in p])
    try:
        out = vv.projectToScreen(src)  # pivy returns the screen point
    except TypeError:
        out = coin.SbVec3f()
        vv.projectToScreen(src, out)
    w, h = vp.getViewportSizePixels().getValue()
    x, y = (out.getValue() if hasattr(out, "getValue") else tuple(out))[:2]
    return float(x) * w, float(y) * h, (w, h)


def view_point(px, py, width, height, coin_size=None, dpr=1.0):
    """A point from view.getPointOnViewport (Coin's viewport: device pixels,
    origin bottom-left) in the view widget's logical pixels from its
    top-left. The ratio is Coin's viewport over the widget's size when
    Coin's size is known (it is what the projection used), else dpr."""
    rx = ry = float(dpr or 1.0)
    if coin_size and width > 0 and height > 0 and coin_size[0] > 0 and coin_size[1] > 0:
        rx, ry = coin_size[0] / float(width), coin_size[1] / float(height)
    return (px / rx, height - py / ry)


def inside(x, y, width, height):
    return 0 <= x < width and 0 <= y < height


def lerp_points(a, b, n):
    """The n points of a drag's moves from a to b, b the last."""
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(1, n + 1)]


def notches_to_angle(dy):
    return int(round(dy * 120))


# ---- finding a widget by what it shows (no Qt: props are plain dicts) -----------------------

def _norm(s):
    return " ".join(str(s or "").replace("&", "").split()).lower()


def _plain(s):
    return _norm(re.sub(r"<[^>]+>", " ", str(s or "")))


def widget_match(props, spec, loose=False):
    """Whether a widget's props { objectName, text, toolTip, classes,
    under } fit spec. text matches whole, or as a part with loose."""
    if "objectName" in spec and props.get("objectName") != spec["objectName"]:
        return False
    if "text" in spec:
        want, have = _norm(spec["text"]), _norm(props.get("text"))
        if not have or (want not in have if loose else want != have):
            return False
    if "toolTip" in spec and _plain(spec["toolTip"]) not in _plain(props.get("toolTip")):
        return False
    if "class" in spec:
        want = spec["class"].lower()
        if not any(c.lower() == want or c.lower().endswith("::" + want) for c in props.get("classes") or ()):
            return False
    if "under" in spec:
        want = _norm(spec["under"])
        if not any(_norm(u) == want for u in props.get("under") or ()):
            return False
    return True


def pick(candidates, spec):
    """The first (widget, props) whose props fit spec: a whole-text match
    before a partial one."""
    cands = list(candidates)
    for loose in (False, True):
        for w, p in cands:
            if widget_match(p, spec, loose):
                return w
        if "text" not in spec:
            break
    return None


# ---- the answer (no Qt) --------------------------------------------------------------------

def _short(v, n):
    if isinstance(v, str) and len(v) > n:
        return v[: n - 1] + "…"
    if isinstance(v, dict):
        return {k: _short(x, n) for k, x in v.items()}
    if isinstance(v, list):
        return [_short(x, n) for x in v]
    return v


def _size(o):
    return len(json.dumps(o, ensure_ascii=False, separators=(",", ":")))


def cap_answer(answer, limit=ANSWER_MAX):
    """The answer within limit characters: long texts shortened, then steps
    from the middle left out (the first and the last kept), counted."""
    out = dict(answer)
    for n in (80, 40, 20):
        if _size(out) <= limit:
            return out
        out = _short(out, n)
    steps = list(out.get("steps") or [])
    dropped = 0
    while _size(out) > limit and len(steps) > 2:
        del steps[len(steps) // 2]
        dropped += 1
        out["steps"] = steps
        out["steps_left_out"] = dropped
    return out


# ---- delivery (Qt handed in) ---------------------------------------------------------------

def _enum(scope, group, name):
    """Qt's enum value by name, PySide6's scoped way first."""
    g = getattr(scope, group, None)
    v = getattr(g, name, None) if g is not None else None
    return v if v is not None else getattr(scope, name)


def _int(v):
    return int(getattr(v, "value", v))


def qt_buttons(qt, names):
    Qt = qt.QtCore.Qt
    flag = _enum(Qt, "MouseButton", "NoButton")
    for n in names:
        flag = flag | _enum(Qt, "MouseButton", {"left": "LeftButton", "right": "RightButton", "middle": "MiddleButton"}[n])
    return flag


def qt_mods(qt, names):
    Qt = qt.QtCore.Qt
    flag = _enum(Qt, "KeyboardModifier", "NoModifier")
    for n in names:
        flag = flag | _enum(Qt, "KeyboardModifier", {"shift": "ShiftModifier", "ctrl": "ControlModifier", "alt": "AltModifier", "meta": "MetaModifier"}[n])
    return flag


def qt_key(qt, key):
    """(key code, text) for a key_name() result."""
    kind, v = key
    if kind == "char":
        return ord(v.upper()), v
    scope = getattr(qt.QtCore.Qt, "Key", None)
    k = getattr(scope, "Key_" + v, None) if scope is not None else None
    if k is None:
        k = getattr(qt.QtCore.Qt, "Key_" + v, None)
    if k is None:
        raise ToolError("invalid_input", f"key: {v} is not a key Qt knows (Return, Escape, Tab, Backspace, Delete, Up, F2 …).")
    return _int(k), KEY_TEXT.get(v, "")


def _event_type(qt, name):
    return _enum(qt.QtCore.QEvent, "Type", name)


def mouse_event(qt, kind, w, x, y, button, buttons, mods):
    """A real QMouseEvent at (x, y) in w: local, window and global
    positions, as a system event carries them."""
    QtCore, QtGui = qt.QtCore, qt.QtGui
    lp = QtCore.QPointF(x, y)
    try:
        wp = QtCore.QPointF(w.mapTo(w.window(), lp))
    except TypeError:
        wp = QtCore.QPointF(w.mapTo(w.window(), QtCore.QPoint(int(round(x)), int(round(y)))))
    gp = global_point(qt, w, x, y)
    t = _event_type(qt, kind)
    try:
        return QtGui.QMouseEvent(t, lp, wp, gp, button, buttons, mods)
    except TypeError:
        return QtGui.QMouseEvent(t, lp, gp, button, buttons, mods)


def global_point(qt, w, x, y):
    QtCore = qt.QtCore
    try:
        return QtCore.QPointF(w.mapToGlobal(QtCore.QPointF(x, y)))
    except TypeError:
        g = w.mapToGlobal(QtCore.QPoint(int(round(x)), int(round(y))))
        return QtCore.QPointF(g.x() + (x - int(round(x))), g.y() + (y - int(round(y))))


def local_point(qt, w, gx, gy):
    QtCore = qt.QtCore
    try:
        p = w.mapFromGlobal(QtCore.QPointF(gx, gy))
        return p.x(), p.y()
    except TypeError:
        p = w.mapFromGlobal(QtCore.QPoint(int(round(gx)), int(round(gy))))
        return float(p.x()), float(p.y())


def wheel_event(qt, w, x, y, dy, buttons, mods):
    QtCore, QtGui = qt.QtCore, qt.QtGui
    gp = global_point(qt, w, x, y)
    phase = _enum(QtCore.Qt, "ScrollPhase", "NoScrollPhase")
    return QtGui.QWheelEvent(QtCore.QPointF(x, y), gp, QtCore.QPoint(0, 0), QtCore.QPoint(0, notches_to_angle(dy)), buttons, mods, phase, False)


def key_events(qt, key, mods):
    code, text = qt_key(qt, key)
    m = qt_mods(qt, mods)
    QtGui = qt.QtGui
    return [QtGui.QKeyEvent(_event_type(qt, "KeyPress"), code, m, text), QtGui.QKeyEvent(_event_type(qt, "KeyRelease"), code, m, text)]


def text_events(qt, text):
    QtGui = qt.QtGui
    out = []
    none = qt_mods(qt, [])
    for c in text:
        code = ord(c.upper()) if " " <= c <= "~" else 0
        m = qt_mods(qt, ["shift"]) if c.isalpha() and c.isupper() else none
        out.append(QtGui.QKeyEvent(_event_type(qt, "KeyPress"), code, m, c))
        out.append(QtGui.QKeyEvent(_event_type(qt, "KeyRelease"), code, m, c))
    return out


# Where the press is held between steps (and calls): the widget that took
# it and the buttons down, as Qt's implicit grab keeps them.
HELD = {"widget": None, "buttons": []}


def _alive(w):
    try:
        w.objectName()
        return True
    except (RuntimeError, AttributeError):
        return False


class Run:
    """The steps, delivered in the window. qt: a namespace of QtCore, QtGui,
    QtWidgets; gui: FreeCADGui; vector: FreeCAD.Vector; hooks: modal()
    (gui_link.modal_info), report() (report_watch.take), grab(widget)
    (a QPixmap), answer_now(body) (the reply sent while a step's dialog
    holds the call), shot_dir."""

    def __init__(self, qt, gui, vector, modal, report, grab, answer_now, shot_dir):
        self.qt, self.gui, self.vector = qt, gui, vector
        self.modal, self.report, self.grab, self.answer_now = modal, report, grab, answer_now
        self.shot_dir = shot_dir
        self.done = []
        self.cur = None
        self.answered = False
        self.pressed = None
        self.focus_at_press = None
        self.last_point = None
        self.shots = []
        self.level = 0
        self.front_at_start = None
        # What a tab or item target adds to its hit, by (widget, x, y).
        self.extra = {}
        # An item's check box clicked: (view, index, state before) until the
        # click is done and checked.
        self.checking = None

    # -- the window's parts --

    def app(self):
        return self.qt.QtWidgets.QApplication.instance()

    def mw(self):
        return self.gui.getMainWindow()

    def blocker(self):
        """The modal dialog or the popup (a menu) in front, if any."""
        app = self.app()
        return app.activePopupWidget() or app.activeModalWidget()

    def _send(self, w, ev):
        return self.qt.QtWidgets.QApplication.sendEvent(w, ev)

    def pump(self, ms):
        QtCore = self.qt.QtCore
        end = time.time() + ms / 1000.0
        flags = _enum(QtCore.QEventLoop, "ProcessEventsFlag", "AllEvents")
        while True:
            left = int((end - time.time()) * 1000)
            QtCore.QCoreApplication.processEvents(flags, max(1, min(left, 50)))
            if left <= 0 or self.answered:
                return
            time.sleep(min(0.005, left / 1000.0))

    def view(self):
        """(the 3D view's widget that takes mouse events, the view)."""
        QtW = self.qt.QtWidgets
        gd = self.gui.ActiveDocument
        view = gd.ActiveView if gd is not None else None
        if view is None or not hasattr(view, "getPointOnViewport"):
            raise ToolError("invalid_state", "No 3D view in front: a document's 3D view must be the window's active tab (doc_switch { front: true }).")
        gv = None
        try:
            gv = view.graphicsView()
        except Exception:
            gv = None
        if gv is None:
            area = self.mw().findChild(QtW.QMdiArea)
            sub = area.activeSubWindow() if area is not None else None
            kids = sub.findChildren(QtW.QWidget) if sub is not None else []
            gv = next((k for k in kids if k.isVisible() and isinstance(k, QtW.QAbstractScrollArea) and any(n in k.metaObject().className() for n in ("Quarter", "View3D"))), None)
            if gv is None:
                gv = next((k for k in kids if k.isVisible() and type(k).__name__ in ("QOpenGLWidget", "QGLWidget")), None)
        if gv is None:
            raise ToolError("unavailable", "The 3D view's widget was not found in the window.")
        vp = gv.viewport() if hasattr(gv, "viewport") and gv.viewport() is not None else gv
        return vp, view

    def _dpr(self, w):
        for f in ("devicePixelRatioF", "devicePixelRatio"):
            try:
                return float(getattr(w, f)())
            except Exception:
                pass
        return 1.0

    def _props(self, w):
        QtW = self.qt.QtWidgets
        classes = []
        try:
            mo = w.metaObject()
            while mo is not None:
                classes.append(mo.className())
                mo = mo.superClass()
        except Exception:
            pass
        classes.append(type(w).__name__)
        text = ""
        for g in ("text", "title"):
            try:
                v = getattr(w, g)()
                if isinstance(v, str) and v:
                    text = v
                    break
            except Exception:
                pass
        under = []
        p = w.parentWidget()
        while p is not None:
            if isinstance(p, QtW.QDockWidget) or p.isWindow():
                under.append(p.windowTitle())
            p = p.parentWidget()
        try:
            tip = w.toolTip()
        except Exception:
            tip = ""
        return {"objectName": w.objectName(), "text": text, "toolTip": tip, "classes": classes, "under": under}

    def _shown(self, w):
        try:
            return w.isVisible() and w.width() > 0 and w.height() > 0
        except Exception:
            return False

    def _tops(self):
        app = self.app()
        tops, seen = [], set()
        for t in [app.activePopupWidget(), app.activeModalWidget(), self.mw()] + list(app.topLevelWidgets()):
            if t is not None and id(t) not in seen and self._shown(t):
                seen.add(id(t))
                tops.append(t)
        return tops

    def _visible(self):
        """Every visible widget, the front ones first, with its props."""
        QtW = self.qt.QtWidgets
        for t in self._tops():
            for w in [t] + list(t.findChildren(QtW.QWidget)):
                if self._shown(w):
                    yield w, self._props(w)

    @staticmethod
    def _is(props, cls):
        return any(c == cls or c.endswith("::" + cls) for c in props.get("classes") or ())

    @staticmethod
    def _under(props, spec):
        if "under" not in spec:
            return True
        want = _norm(spec["under"])
        return any(_norm(u) == want for u in props.get("under") or ())

    def find_tab(self, spec):
        """(tab bar, index, text) of the first visible tab showing spec's text
        (whole before a part), in a dock or dialog titled under."""
        bars = [(w, p) for w, p in self._visible() if self._is(p, "QTabBar") and self._under(p, spec)]
        want = _norm(spec["text"])
        for loose in (False, True):
            for w, _p in bars:
                for i in range(w.count()):
                    have = _norm(w.tabText(i))
                    if have and (want in have if loose else want == have):
                        try:
                            if hasattr(w, "isTabVisible") and not w.isTabVisible(i):
                                continue
                        except Exception:
                            pass
                        return w, i, w.tabText(i).replace("&", "")
        raise ToolError("not_found", f"No visible tab {json.dumps(spec, ensure_ascii=False)}: window_snapshot shows what is there.")

    def _rows(self, model, parent, depth=0):
        """Every index of a model's column-0 rows, depth first (a tree's
        children after their parent)."""
        n = model.rowCount(parent) if parent is not None else model.rowCount()
        for r in range(n):
            ix = model.index(r, 0, parent) if parent is not None else model.index(r, 0)
            yield ix
            if depth < 12:
                try:
                    if model.rowCount(ix) > 0:
                        yield from self._rows(model, ix, depth + 1)
                except Exception:
                    pass

    def find_item(self, spec):
        """(view, index, text) of the first row of a visible list, tree or
        table whose shown text is spec's (whole before a part), in column
        (any column when left out)."""
        Qt = self.qt.QtCore.Qt
        role = _enum(Qt, "ItemDataRole", "DisplayRole")
        views = [(w, p) for w, p in self._visible() if self._is(p, "QAbstractItemView") and self._under(p, spec)]
        want = _norm(spec["text"])
        col = spec.get("column")
        for loose in (False, True):
            for v, _p in views:
                m = v.model()
                if m is None:
                    continue
                ncol = m.columnCount() if hasattr(m, "columnCount") else 1
                cols = [col] if col is not None else range(max(1, ncol))
                for ix in self._rows(m, None):
                    for c in cols:
                        cix = ix if c == 0 else ix.sibling(ix.row(), c)
                        try:
                            if hasattr(v, "isRowHidden") and v.isRowHidden(ix.row(), ix.parent()):
                                continue
                        except TypeError:
                            pass
                        have = _norm(m.data(cix, role))
                        if have and (want in have if loose else want == have):
                            return v, cix, str(m.data(cix, role))
        raise ToolError("not_found", f"No visible list, tree or table row {json.dumps(spec, ensure_ascii=False)}: window_snapshot shows what is there.")

    def _check_state(self, v, ix):
        Qt = self.qt.QtCore.Qt
        try:
            return _int(v.model().data(ix, _enum(Qt, "ItemDataRole", "CheckStateRole")))
        except Exception:
            return None

    def find_widget(self, spec):
        def cands():
            yield from self._visible()

        w = pick(cands(), spec)
        if w is None:
            raise ToolError("not_found", f"No visible widget with {json.dumps(spec, ensure_ascii=False)}: window_snapshot shows what is there.")
        return w

    def _deepest(self, w, x, y):
        """The widget a real event at (x, y) in w would reach: the deepest
        child there (a scroll area's viewport, a spin box's line edit)."""
        QtCore = self.qt.QtCore
        try:
            c = w.childAt(QtCore.QPoint(int(x), int(y)))
        except Exception:
            c = None
        if c is None:
            return w, x, y
        p = c.mapFrom(w, QtCore.QPoint(int(x), int(y)))
        return c, p.x() + (x - int(x)), p.y() + (y - int(y))

    def resolve(self, t):
        """(widget, x, y) in the widget's logical pixels."""
        QtCore = self.qt.QtCore
        kind, v = t["kind"], t["value"]
        if kind in ("view", "view_world"):
            vp, view = self.view()
            w, h = vp.width(), vp.height()
            if kind == "view":
                x, y = v
            else:
                coin, fallback = None, None
                try:
                    px, py, coin = coin_project(view, v)
                except Exception as e:  # no Coin render manager: FreeCAD's own call (off in tall views)
                    fallback = f"{type(e).__name__}: {e}"
                    px, py = view.getPointOnViewport(self.vector(*v))[:2]
                    try:
                        coin = tuple(view.getSize())[:2]
                    except Exception:
                        coin = None
                x, y = view_point(px, py, w, h, coin, self._dpr(vp))
                self.last_point = {"world": list(v), "viewport": [round(px, 1), round(py, 1)], "coinSize": list(coin) if coin else None,
                                   "widget": [w, h], "dpr": self._dpr(vp), "at": [round(x, 1), round(y, 1)],
                                   **({"fallback": fallback} if fallback else {})}
            if not inside(x, y, w, h):
                raise ToolError("invalid_input", f"{kind} {v} is at ({x:.0f}, {y:.0f}), outside the 3D view ({w}×{h} logical pixels).")
            return self._deepest(vp, x, y)
        if kind == "tab":
            bar, i, text = self.find_tab(v)
            r = bar.tabRect(i)
            x, y = r.x() + r.width() / 2.0, r.y() + r.height() / 2.0
            self.extra[(id(bar), x, y)] = {"class": "QTabBar", "tab": text}
            return bar, x, y
        if kind == "item":
            view, ix, text = self.find_item(v)
            try:
                p = ix.parent()
                while p is not None and p.isValid() and hasattr(view, "expand"):
                    view.expand(p)
                    p = p.parent()
            except Exception:
                pass
            view.scrollTo(ix)
            r = view.visualRect(ix)
            vp = view.viewport()
            y = r.y() + r.height() / 2.0
            extra = {"class": self._props(view)["classes"][0], "item": text, "row": ix.row()}
            if t.get("check"):
                x = r.x() + CHECK_INSET + min(r.height(), 20) / 2.0
                self.checking = (view, ix, self._check_state(view, ix))
            else:
                x = r.x() + r.width() / 2.0
            self.extra[(id(vp), x, y)] = extra
            return vp, x, y
        if kind == "widget":
            w = self.find_widget(v)
            if isinstance(w, self.qt.QtWidgets.QAbstractScrollArea) and "at" not in t:
                w = w.viewport()
            x, y = t.get("at") or (w.width() / 2.0, w.height() / 2.0)
            return self._deepest(w, x, y)
        mw = self.mw()
        x, y = v
        pt = QtCore.QPoint(int(x), int(y))
        w = mw.childAt(pt)
        if w is None:
            w = self.qt.QtWidgets.QApplication.widgetAt(mw.mapToGlobal(pt))
        if w is None:
            raise ToolError("not_found", f"window {v}: nothing of the FreeCAD window there ({mw.width()}×{mw.height()}).")
        p = w.mapFrom(mw, pt) if (w is mw or mw.isAncestorOf(w)) else w.mapFromGlobal(mw.mapToGlobal(pt))
        return w, p.x() + (x - int(x)), p.y() + (y - int(y))

    def hit(self, w, x, y):
        g = global_point(self.qt, w, x, y)
        extra = self.extra.pop((id(w), x, y), None)
        if extra is not None:
            return {**extra, "global": [int(round(g.x())), int(round(g.y()))]}
        p = self._props(w)
        out = {"class": p["classes"][0] if p["classes"] else type(w).__name__}
        if p["objectName"]:
            out["name"] = p["objectName"]
        t = p["text"] or (w.windowTitle() if w.isWindow() else "")
        if t:
            out["text"] = t[:60]
        place = next((u for u in p["under"] if u), "")
        if place:
            out["in"] = place[:40]
        out["global"] = [int(round(g.x())), int(round(g.y()))]
        return out

    def _check_front(self, w):
        b = self.blocker()
        if b is None:
            return
        if w is not None and (w is b or b.isAncestorOf(w)):
            return
        what = "a menu" if self.app().activePopupWidget() is b else f"the dialog \"{b.windowTitle()}\""
        raise ToolError("invalid_state", f"{what} is in front and holds the window: only targets inside it are taken (dialog_answer, or gui_input {{ steps: [{{ key: \"Escape\" }}] }}, closes it). This step was not run.")

    def _focus_for_press(self, w):
        """Focus by the widget's policy, as a real press gives it (Qt does
        it before the event, outside sendEvent)."""
        Qt = self.qt.QtCore.Qt
        click = _int(_enum(Qt, "FocusPolicy", "ClickFocus"))
        # Keys that follow go where this press went, even when the window is
        # in the background and Qt keeps no focus widget for it.
        self.pressed = w
        p = w
        try:
            self.focus_at_press = self.app().focusWidget() or self.mw().focusWidget()
        except Exception:
            self.focus_at_press = None
        while p is not None:
            try:
                if p.isEnabled() and _int(p.focusPolicy()) & click == click:
                    p.setFocus(_enum(Qt, "FocusReason", "MouseFocusReason"))
                    self.pressed = p
                    self.focus_at_press = self.app().focusWidget() or self.mw().focusWidget()
                    return
                if p.isWindow():
                    return
            except Exception:
                return
            p = p.parentWidget()

    def _focus_widget(self, target):
        if target is not None:
            w, _x, _y = self.resolve(target)
            self._check_front(w)
            try:
                w.setFocus(_enum(self.qt.QtCore.Qt, "FocusReason", "OtherFocusReason"))
            except Exception:
                pass
            return w
        b = self.blocker()
        if b is not None:
            if self.app().activePopupWidget() is b:
                return b
            return b.focusWidget() or b
        app = self.app()
        f = app.focusWidget() or self.mw().focusWidget()
        # The press's widget, unless focus moved on since (a field the
        # press opened and focused takes the typing).
        if self.pressed is not None and _alive(self.pressed) and self.pressed.isVisible() and (f is None or f is self.focus_at_press):
            return self.pressed
        return f or self.mw()

    # -- mouse --

    def _mouse(self, kind, w, x, y, button, mods, focus=True):
        Qt = self.qt.QtCore.Qt
        if kind in ("MouseButtonPress", "MouseButtonDblClick"):
            if button not in HELD["buttons"]:
                HELD["buttons"].append(button)
            HELD["widget"] = w
            if kind == "MouseButtonPress" and focus:
                self._focus_for_press(w)
        elif kind == "MouseButtonRelease":
            if button in HELD["buttons"]:
                HELD["buttons"].remove(button)
        b = qt_buttons(self.qt, [button]) if button else _enum(Qt, "MouseButton", "NoButton")
        held = qt_buttons(self.qt, HELD["buttons"])
        self._send(w, mouse_event(self.qt, kind, w, x, y, b, held, qt_mods(self.qt, mods)))
        if kind == "MouseButtonRelease" and not HELD["buttons"]:
            HELD["widget"] = None

    def _wheel(self, w, x, y, dy, mods):
        """The wheel on w, passed up to its parents while it is not taken (a
        button in a scroll area leaves it to the area), as the window does
        with a real wheel; a sent event is not passed on by Qt."""
        while w is not None:
            ev = wheel_event(self.qt, w, x, y, dy, qt_buttons(self.qt, HELD["buttons"]), qt_mods(self.qt, mods))
            ev.ignore()
            self._send(w, ev)
            try:
                if ev.isAccepted() or w.isWindow():
                    return
                p = w.mapToParent(self.qt.QtCore.QPoint(int(x), int(y)))
                x, y, w = p.x(), p.y(), w.parentWidget()
            except Exception:
                return

    def selected(self):
        """What FreeCAD's selection holds after a click: 'Object.Sub' for the
        first 3 sub-elements (the object alone when none), or None where
        there is no selection to read."""
        sel = getattr(self.gui, "Selection", None)
        if sel is None:
            return None
        try:
            got = []
            for s in sel.getSelectionEx():
                subs = list(getattr(s, "SubElementNames", ()) or ())
                name = getattr(s, "ObjectName", "") or getattr(getattr(s, "Object", None), "Name", "")
                got += [f"{name}.{x}" for x in subs] if subs else [name]
                if len(got) >= 3:
                    break
            return got[:3]
        except Exception:
            return None

    def _arrive(self, w, x, y, mods):
        """The pointer moved onto the spot before a press, as a real hand's
        does: what lights up under a hover (a grip, a pre-selection) is lit
        when the button goes down."""
        self._mouse("MouseMove", w, x, y, None, mods)
        self.pump(MOVE_GAP_MS)

    def _grabbed(self, w, x, y):
        """While a button is held, the press's widget takes the moves and the
        release (Qt's implicit grab), at the same point on the screen."""
        g = HELD["widget"]
        if not HELD["buttons"] or g is None or g is w:
            return w, x, y
        if not _alive(g):
            HELD["widget"], HELD["buttons"] = None, []
            return w, x, y
        gp = global_point(self.qt, w, x, y)
        lx, ly = local_point(self.qt, g, gp.x(), gp.y())
        return g, lx, ly

    def _target(self, t):
        w, x, y = self.resolve(t)
        self._check_front(w)
        return w, x, y

    def step(self, st):
        do = st["do"]
        out = {"do": do}
        self.last_point = None
        self.checking = None
        try:
            self._step(st, out)
            if self.checking is not None and do == "click" and not self.answered:
                self._checked(out)
            return out
        finally:
            self.checking = None
            if self.last_point is not None:
                out["point"] = self.last_point

    def _checked(self, out):
        """After a click on an item's check box: whether it took. If the
        click left the state as it was (a style that puts the box elsewhere),
        the model's check state is toggled instead, and the answer says so."""
        view, ix, before = self.checking
        Qt = self.qt.QtCore.Qt
        self.pump(MOVE_GAP_MS)
        after = self._check_state(view, ix)
        hit = out.setdefault("hit", {})
        if before is None and after is None:
            hit["check"] = "not checkable"
            return
        if after != before:
            hit["check"] = "clicked"
        else:
            checked = _int(_enum(Qt, "CheckState", "Checked"))
            new = _enum(Qt, "CheckState", "Unchecked" if before == checked else "Checked")
            view.model().setData(ix, new, _enum(Qt, "ItemDataRole", "CheckStateRole"))
            after = self._check_state(view, ix)
            hit["check"] = "set through the model (the click on its box did not take)"
        hit["checked"] = after == _int(_enum(Qt, "CheckState", "Checked"))

    def _step(self, st, out):
        do = st["do"]
        if do in ("click", "press", "release", "move", "scroll"):
            w, x, y = self._target(st["target"])
            out["hit"] = self.hit(w, x, y)
            if do == "click" and not HELD["buttons"]:
                # A tap as the 3D view's navigation styles read one: the
                # hand arrives and focus is given first, with the window
                # caught up; then press and release back to back, nothing
                # processed between them. Gesture (and the others) time a
                # press by the wall clock at each event: a redraw between
                # them read as tap-and-hold and opened the context menu.
                self._mouse("MouseMove", w, x, y, None, st["mods"])
                self._focus_for_press(w)
                self.pump(MOVE_GAP_MS)
            elif do == "press" and not HELD["buttons"]:
                self._arrive(w, x, y, st["mods"])
            if do == "click":
                self._mouse("MouseButtonPress", w, x, y, st["button"], st["mods"], focus=False)
                if self.answered:
                    return out
                gw, gx, gy = self._grabbed(w, x, y)
                self._mouse("MouseButtonRelease", gw, gx, gy, st["button"], st["mods"])
                if st["double"] and not self.answered:
                    self.pump(MOVE_GAP_MS)
                    self._mouse("MouseButtonDblClick", w, x, y, st["button"], st["mods"], focus=False)
                    gw, gx, gy = self._grabbed(w, x, y)
                    self._mouse("MouseButtonRelease", gw, gx, gy, st["button"], st["mods"])
                if not self.answered:
                    self.pump(MOVE_GAP_MS)
                    sel = self.selected()
                    if sel is not None:
                        out["selected"] = sel
            elif do == "press":
                self._mouse("MouseButtonPress", w, x, y, st["button"], st["mods"])
            elif do == "move":
                gw, gx, gy = self._grabbed(w, x, y)
                self._mouse("MouseMove", gw, gx, gy, None, st["mods"])
            elif do == "release":
                gw, gx, gy = self._grabbed(w, x, y)
                self._mouse("MouseButtonRelease", gw, gx, gy, st["button"], st["mods"])
            else:
                self._wheel(w, x, y, st["dy"], st["mods"])
        elif do == "drag":
            w, x, y = self._target(st["from"])
            tw, tx, ty = self._target(st["to"])
            out["hit"] = self.hit(w, x, y)
            out["to"] = self.hit(tw, tx, ty)
            if not HELD["buttons"]:
                self._arrive(w, x, y, st["mods"])
            self._mouse("MouseButtonPress", w, x, y, st["button"], st["mods"])
            a = global_point(self.qt, w, x, y)
            b = global_point(self.qt, tw, tx, ty)
            for gx, gy in lerp_points((a.x(), a.y()), (b.x(), b.y()), st["steps"]):
                self.pump(MOVE_GAP_MS)
                if self.answered:
                    return out
                lx, ly = local_point(self.qt, w, gx, gy)
                self._mouse("MouseMove", w, lx, ly, None, st["mods"])
            lx, ly = local_point(self.qt, w, b.x(), b.y())
            self._mouse("MouseButtonRelease", w, lx, ly, st["button"], st["mods"])
        elif do in ("key", "type"):
            w = self._focus_widget(st.get("target"))
            out["hit"] = {"class": self._props(w)["classes"][0], **({"name": w.objectName()} if w.objectName() else {})}
            evs = key_events(self.qt, st["key"], st["mods"]) if do == "key" else text_events(self.qt, st["text"])
            for ev in evs:
                self._send(w, ev)
                if self.answered:
                    return out
        elif do == "wait":
            self.pump(st["ms"])
        elif do == "shot":
            out.update(self.shot(st["name"]))
        return out

    def shot(self, name):
        import os

        os.makedirs(self.shot_dir, exist_ok=True)
        path = os.path.join(self.shot_dir, name + ".png")
        pix = self.grab(self.mw())
        if not pix.save(path, "PNG"):
            raise ToolError("failed", f"Could not write {path}")
        out = {"path": path, "size": [pix.width(), pix.height()]}
        b = self.blocker()
        if b is not None and b.isWindow():
            extra = os.path.join(self.shot_dir, name + "-front.png")
            if b.grab().save(extra, "PNG"):
                out["front"] = extra
        self.shots.append(path)
        return out

    # -- a step's dialog holding the call --

    def _front_info(self, b):
        if b is None:
            return None
        if self.app().activePopupWidget() is b:
            items = []
            try:
                items = [a.text().replace("&", "") for a in b.actions() if a.text() and a.isVisible()]
            except Exception:
                pass
            return {"menu": items[:20]}
        d = self.modal()
        if d is None:
            return {"dialog": {"title": b.windowTitle()}}
        return {"dialog": {k: d[k] for k in ("class", "title", "text", "buttons") if k in d}}

    def watch(self):
        """On a timer: a step whose dialog or menu runs its own event loop
        holds this call until it closes. Seen from inside that loop, the
        answer so far goes out at once, so the agent can read the dialog
        and answer it (dialog_answer, gui_input inside it)."""
        if self.answered or self.cur is None:
            return
        QtCore = self.qt.QtCore
        try:
            level = QtCore.QThread.currentThread().loopLevel()
        except Exception:
            return
        if level <= self.level:
            return
        b = self.blocker()
        if b is None or b is self.front_at_start:
            return
        cur = dict(self.cur)
        cur.update(self._front_info(b) or {})
        body = self.answer(self.done + [cur], note="This step opened what is in front, which holds the window: the steps after it were not run. dialog_answer, or gui_input with targets inside it, goes on.")
        if self.answer_now(body):
            self.answered = True
        else:
            self.cur = None  # not answerable early (in a batch): the call waits for it to close

    def answer(self, steps, note=None):
        out = {"steps": steps}
        if HELD["buttons"]:
            out["held"] = list(HELD["buttons"])
        if self.shots:
            out["shots"] = len(self.shots)
        if note:
            out["note"] = note
        return cap_answer(out)

    def run(self, steps):
        QtCore = self.qt.QtCore
        try:
            self.level = QtCore.QThread.currentThread().loopLevel()
        except Exception:
            self.level = 0
        timer = QtCore.QTimer()
        timer.setInterval(60)
        timer.timeout.connect(self.watch)
        timer.start()
        try:
            for i, st in enumerate(steps):
                self.front_at_start = self.blocker()
                before = self.modal()
                self.cur = {"i": i, "do": st["do"]}
                try:
                    out = self.step(st)
                except Exception as e:  # noqa: BLE001 - the steps before it are still answered
                    if self.answered:
                        break
                    msg = e.message if isinstance(e, ToolError) else f"{type(e).__name__}: {e}"
                    self.done.append({"i": i, "do": st["do"], "error": msg})
                    break
                if self.answered:
                    break
                out = {"i": i, **out}
                b = self.blocker()
                if b is not None and b is not self.front_at_start:
                    out.update(self._front_info(b) or {})
                elif before is None and self.modal() is not None:
                    out.update(self._front_info(self.blocker()) or {})
                if st["do"] not in ("wait", "shot"):
                    self.pump(MOVE_GAP_MS)
                lines = self.report()
                if lines:
                    out["report"] = lines
                self.done.append(out)
                self.cur = None
        finally:
            timer.stop()
            self.cur = None
        return self.answer(self.done)
