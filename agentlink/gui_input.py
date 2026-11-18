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
BUSY_AFTER = 10.0    # s past a call's own waits: the link answers it "busy" from its socket thread
DRAG_STEPS = 12
MAX_DRAG_STEPS = 200
MOVE_GAP_MS = 8      # between the moves of a drag
SHOT_SETTLE_MS = 40  # a shot with a dialog or menu up: its layout and paint events run first
MAX_NOTCHES = 50
MAX_TEXT = 2000
ANSWER_MAX = 3000    # characters of the answer's text
# Said with "open" in an answer: what still holds the window, and how to close it.
OPEN_NOTE = ("A menu or dialog is still open and holds the window: more gui_input steps act inside it ({menu_item: \"text\"}, "
             "{item: {text}} in a drop-down list, {key: \"Escape\"}), dialog_answer presses a dialog's button, gui_unstick closes it.")
BUTTONS = ("left", "right", "middle")
MODIFIERS = ("shift", "ctrl", "alt", "meta")
TARGETS = ("view", "view_world", "widget", "window", "tab", "item", "menu_item")
WIDGET_KEYS = ("objectName", "text", "toolTip", "class", "under")
TAB_KEYS = ("text", "under")
ITEM_KEYS = ("text", "under", "column")
# Where a check box sits in an item's rect: its left edge plus this, in
# logical pixels (Qt's styles draw the indicator a few pixels in, about a
# line's height wide).
CHECK_INSET = 3
# What an item view opens to edit a value (Qt's and FreeCAD's subclasses).
EDITORS = ("QLineEdit", "QAbstractSpinBox", "QComboBox", "QTextEdit", "QPlainTextEdit")
# The width of a MenuButtonPopup tool button's arrow part, from its right
# edge, in logical pixels (Qt's PM_MenuButtonIndicator plus a margin).
ARROW_W = 14
SHOT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
SHORTCUT = re.compile(r"[A-Za-z0-9+,. \-=/\\';\[\]`]{1,40}")
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
    "shortcut": (),
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
        raise bad(f"{where}: an object — {{ view: [x, y] }}, {{ view_world: [x, y, z] }}, {{ widget: {{ objectName, text, toolTip, class, under }}, at?: [dx, dy] }}, {{ menu_item: \"text\" }} or {{ window: [x, y] }}.")
    kinds = [k for k in TARGETS if k in t]
    if len(kinds) != 1:
        raise bad(f"{where}: one of {', '.join(TARGETS)}.")
    kind = kinds[0]
    extra = [k for k in t if k not in (kind, "at", "check")] + (["at"] if "at" in t and kind != "widget" else []) + (["check"] if "check" in t and kind != "item" else [])
    if extra:
        why = {"at": " (at is for a widget target)", "check": " (check is for an item target)"}.get(extra[0], "")
        raise bad(f"{where}.{extra[0]}: not a field here{why}.")
    if kind == "menu_item":
        v = t["menu_item"]
        if not isinstance(v, str) or not v.strip():
            raise bad(f"{where}.menu_item: an item's text as the open menu shows it.")
        return {"kind": "menu_item", "value": v}
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
    elif kind == "shortcut":
        if not isinstance(v, str) or not SHORTCUT.fullmatch(v.strip()):
            raise bad(f"{where}.shortcut: a key sequence as FreeCAD shows it, such as \"Shift+V\", \"Ctrl+Shift+S\" or \"V, D\".")
        out["keys"] = v.strip()
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
        raise bad("steps: a list of steps, run in order — click, press, move, release, drag, scroll, key, type, wait, shot, shortcut.")
    if len(steps) > MAX_STEPS:
        raise bad(f"steps: at most {MAX_STEPS} in one call.")
    out = [parse_step(s, i) for i, s in enumerate(steps)]
    if sum(s.get("ms", 0) for s in out) > MAX_TOTAL_WAIT:
        raise bad(f"steps: the waits come to over {MAX_TOTAL_WAIT} ms in one call — split it in two calls.")
    return out


def unmark_modified(gui, name):
    """The window's Gui::Document marked unmodified (its Python Modified,
    which FreeCAD's canClose reads): a close then asks nothing. True when
    done. Never raises."""
    try:
        gd = gui.getDocument(name)
    except Exception:  # noqa: BLE001
        return False
    if gd is None:
        return False
    try:
        if getattr(gd, "Modified", False):
            gd.Modified = False
        return True
    except Exception:  # noqa: BLE001
        return False


def target_kinds(steps):
    """The kinds of the targets parsed steps aim at (view, window, item …)."""
    out = set()
    for st in steps or ():
        for k in ("target", "from", "to"):
            t = st.get(k)
            if isinstance(t, dict) and t.get("kind"):
                out.add(t["kind"])
    return out


def acts(steps):
    """True when parsed steps send input (anything but shots and waits)."""
    return any(st.get("do") not in ("shot", "wait") for st in steps or ())


def leave_edit(gui, name):
    """Before a document closes: its edit left (a sketch open in edit) and
    the task panel of that edit closed, as a person's Close does. Closing
    four documents, one with a sketch in edit, hung FreeCAD for over 60 s
    (live 59). gui: FreeCADGui. Answers what was done ([] for nothing)."""
    did = []
    try:
        gd = gui.getDocument(name)
    except Exception:
        return did
    if gd is None:
        return did
    try:
        if gd.getInEdit() is not None:
            gd.resetEdit()
            did.append("edit left")
    except Exception:
        pass
    try:
        ctl = getattr(gui, "Control", None)
        if ctl is not None and ctl.activeDialog() and getattr(gui, "ActiveDocument", None) is gd:
            ctl.closeDialog()
            did.append("task panel closed")
    except Exception:
        pass
    return did


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


# ---- what is open in front: a menu, a drop-down list, a dialog (duck-typed, no Qt) ---------

def _classes(w):
    out = []
    try:
        mo = w.metaObject()
        while mo is not None:
            out.append(mo.className())
            mo = mo.superClass()
    except Exception:
        pass
    out.append(type(w).__name__)
    return out


def _same(a, b):
    """One Qt object: the same wrapper, or the same C++ object behind two."""
    if a is None or b is None:
        return False
    if a is b:
        return True
    for mod in ("shiboken6", "shiboken2"):
        try:
            sh = __import__(mod)
            return sh.getCppPointer(a) == sh.getCppPointer(b)
        except Exception:  # noqa: BLE001 — not that binding, or not Qt objects
            continue
    return False


def _has_class(w, name):
    return w is not None and any(c == name or c.endswith("::" + name) for c in _classes(w))


# ---- what no step reaches (red team, 2026-11-18) ---------------------------------------
# FreeCAD's Python console and macro editor run the text typed in them as
# code; the dialogs below change what code FreeCAD runs (macros, settings,
# add-ons); the person's OK dialog (agentlink/person_ok.py) is the person's
# alone. A step's event to any of them, or to a widget inside one, is
# refused before it is sent.
CODE_CLASSES = ("PythonConsole", "PythonEditor", "PythonEditorView", "EditorView", "DlgMacroExecuteImp", "DlgMacroRecordImp",
                "DlgParameterImp", "DlgPreferencesImp", "DlgCustomizeImp", "AddonManager", "AddonManagerDialog")
CODE_NAMES = ("Python console", "AgentLinkPersonOK")


def forbidden_widget(w, most=64):
    """Why an input step may not reach w (w or a widget that holds it), or None."""
    from . import person_ok

    seen = 0
    while w is not None and seen < most:
        try:
            name = w.objectName() if hasattr(w, "objectName") else ""
        except Exception:
            name = ""
        if name == person_ok.OBJECT_NAME:
            return "the person's OK dialog: only the person presses it"
        if name in CODE_NAMES:
            return f"{name}: what is typed there runs as code"
        for c in _classes(w):
            short = c.split("::")[-1]
            if short in CODE_CLASSES:
                return f"{short}: it runs code or changes what code FreeCAD runs"
        try:
            up = getattr(w, "parentWidget", None) or getattr(w, "parent", None)
            w = up() if callable(up) else up
        except Exception:
            w = None
        seen += 1
    return None


def refused_command(name):
    """Why the command of a menu item, tool button or shortcut is not run
    from a step (the same list as cmd_run's), or None."""
    if not name:
        return None
    try:
        from .families.app import refused
    except Exception:  # noqa: BLE001 — no FreeCAD (tests): the list's patterns
        import re as _re

        return "it runs a macro or opens a dialog of the person's" if _re.match(r"^(Std_Dlg|Std_Macro|Std_RecentMacros|Std_AddonMgr|Std_Quit)", name) else None
    return refused(name)


def menu_items(menu, most=30):
    """The texts of a menu's visible items, separators left out."""
    out = []
    try:
        acts = list(menu.actions())
    except Exception:
        return out
    for a in acts:
        try:
            if (hasattr(a, "isSeparator") and a.isSeparator()) or not a.isVisible():
                continue
            t = (a.text() or "").replace("&", "")
        except Exception:
            continue
        if t:
            out.append(t)
        if len(out) >= most:
            break
    return out


def describe_popup(p):
    """{ kind: menu|combo|popup, title, items? } of a popup widget."""
    try:
        par = p.parentWidget()
    except Exception:
        par = None
    if _has_class(par, "QComboBox") or _has_class(p, "QComboBoxPrivateContainer"):
        combo = par if _has_class(par, "QComboBox") else None
        items, title = [], ""
        if combo is not None:
            try:
                items = [combo.itemText(i) for i in range(min(combo.count(), 30))]
                title = combo.objectName() or combo.currentText()
            except Exception:
                pass
        return {"kind": "combo", "title": title or "a list", "items": items}
    if _has_class(p, "QMenu"):
        try:
            title = (p.title() or "").replace("&", "")
        except Exception:
            title = ""
        return {"kind": "menu", "title": title or "a menu", "items": menu_items(p)}
    try:
        title = p.windowTitle()
    except Exception:
        title = ""
    return {"kind": "popup", "title": title or _classes(p)[0]}


def describe_front(app, modal=None):
    """What holds the window in front: the popup (a menu, a drop-down list),
    else the modal dialog, as { kind, title, items | text, buttons }; None
    when nothing is open. modal: gui_link.modal_info, for a dialog's words."""
    if app is None:
        return None
    p = app.activePopupWidget()
    m = app.activeModalWidget()
    if p is not None:
        info = describe_popup(p)
        if m is not None:
            try:
                info["over"] = m.windowTitle()
            except Exception:
                pass
        return info
    if m is None:
        return None
    try:
        cls = m.metaObject().className()
        if "ProgressDialog" in cls or "ProgressBar" in cls or not m.isVisible():
            # A progress dialog (a job's own; it closes by itself) or one
            # not shown: no dialog that holds the person's window.
            return {"kind": "progress", "title": m.windowTitle()}
    except Exception:
        pass
    d = None
    try:
        d = modal() if modal is not None else None
    except Exception:
        d = None
    info = {"kind": "dialog", "title": (d or {}).get("title") or m.windowTitle()}
    for k in ("text", "buttons"):
        if d and d.get(k):
            info[k] = d[k]
    return info


def front_words(info):
    """A front's description in words, for a refusal."""
    if not info:
        return "a menu or dialog (most likely one that a gui_input step opened)"
    kind = {"menu": "a menu", "combo": "a drop-down list", "dialog": "the dialog", "popup": "a pop-up"}.get(info.get("kind"), "a window")
    title = str(info.get("title") or "")
    words = kind if not title or title in ("a menu", "a list") else f"{kind} \"{title}\""
    if info.get("items"):
        words += " (items: " + ", ".join(str(x) for x in info["items"][:12]) + ")"
    elif info.get("buttons"):
        words += " (buttons: " + ", ".join(str(x) for x in info["buttons"][:8]) + ")"
    return words


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
    (a QPixmap), answer_now(body) (the reply sent while a step's menu or
    dialog holds the call), shot_dir; ticker(fn) (optional): calls fn on
    the GUI thread every ~100 ms through queued events from a thread of its
    own, and answers a function that stops it; seen(info) (optional): told
    what is open in front when a step opened it and at the end.

    A step whose event starts a nested event loop (QMenu.exec from a
    toolbar button's arrow, QDialog.exec, a message box) cannot return
    until that loop ends. The watch (a timer of each level, and the ticker)
    sees it from inside that loop: the stuck step is set aside (its frame
    does nothing more when it comes back), and the steps after it run from
    there, so they can act on the menu or dialog; the answer goes out from
    there too (answer_now) and says what is still open."""

    def __init__(self, qt, gui, vector, modal, report, grab, answer_now, shot_dir, ticker=None, seen=None):
        self.qt, self.gui, self.vector = qt, gui, vector
        self.modal, self.report, self.grab, self.answer_now = modal, report, grab, answer_now
        self.shot_dir = shot_dir
        self.ticker, self.seen = ticker, seen
        self.done = []
        self.answered = False
        self.pressed = None
        self.focus_at_press = None
        self.last_point = None
        self.shots = []
        # The steps in hand, innermost last: { i, do, out, front, sending,
        # detached }. A frame is detached when the watch took the steps on
        # from inside the nested loop its event started.
        self.frames = []
        self.steps = []
        self.next = 0
        self.final = None
        # A menu item's (menu, action), for the click's fallback.
        self.menu_pick = None
        self.menu_fired, self.menu_watch = None, None
        # What a tab or item target adds to its hit, by (widget, x, y).
        self.extra = {}
        # An item's check box clicked: (view, index, state before) until the
        # click is done and checked.
        self.checking = None
        # gui_input's as: "person" (hooks.person_input, dev only): its steps'
        # input counts as the person's until the answer is decided, then
        # it is closed (even while a step's menu or dialog still holds the
        # call, and on an error); as_ is echoed in the answer.
        self.person = None
        self.as_ = None

    def _release_person(self):
        p, self.person = self.person, None
        if p is not None:
            try:
                p.close()
            except Exception:
                pass

    # -- the window's parts --

    def app(self):
        return self.qt.QtWidgets.QApplication.instance()

    def mw(self):
        return self.gui.getMainWindow()

    def blocker(self):
        """The modal dialog or the popup (a menu) in front, if any."""
        app = self.app()
        return app.activePopupWidget() or app.activeModalWidget()

    def _guard(self, w, ev):
        """Refuse an event to a widget that no step reaches, or one that
        would run a refused command (a menu item, a tool button)."""
        why = forbidden_widget(w)
        cmd = None
        if why is None:
            try:
                if _has_class(w, "QMenu"):
                    # A click picks the item under it; a key (Return) the active one.
                    Qt = self.qt.QtCore.Qt
                    picks = tuple(getattr(Qt, k, None) for k in ("Key_Return", "Key_Enter", "Key_Space"))
                    act = w.actionAt(ev.pos()) if hasattr(ev, "pos") else w.activeAction() if hasattr(ev, "key") and ev.key() in picks else None
                    cmd = act.objectName() if act is not None else None
                elif _has_class(w, "QToolButton") and w.defaultAction() is not None:
                    cmd = w.defaultAction().objectName()
            except Exception:  # noqa: BLE001
                cmd = None
            r = refused_command(cmd)
            if r:
                why = f"{cmd}: {r}"
        if why:
            raise ToolError("refused", f"gui_input does not send input there — {why}. This step was not run.")

    def _send(self, w, ev):
        self._guard(w, ev)
        fr = self.frames[-1] if self.frames else None
        if fr is not None:
            fr["sending"] += 1
        try:
            return self.qt.QtWidgets.QApplication.sendEvent(w, ev)
        finally:
            if fr is not None:
                fr["sending"] -= 1

    def _detached(self):
        """The step in hand was set aside (its event's nested loop ended and
        the steps after it ran already): do nothing more."""
        return bool(self.frames) and self.frames[-1]["detached"]

    def pump(self, ms):
        QtCore = self.qt.QtCore
        end = time.time() + ms / 1000.0
        flags = _enum(QtCore.QEventLoop, "ProcessEventsFlag", "AllEvents")
        while True:
            left = int((end - time.time()) * 1000)
            QtCore.QCoreApplication.processEvents(flags, max(1, min(left, 50)))
            if left <= 0 or self._detached():
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

    def _count(self, model, what, parent=None):
        """A model's rowCount or columnCount under parent (the root when
        None). A list model (QAbstractListModel) takes only the form with
        a parent, a tree model takes both (live 80: "columnCount() takes
        exactly one argument"). 1 column when the model does not say."""
        fn = getattr(model, what, None)
        if fn is None:
            return 1 if what == "columnCount" else 0
        if parent is not None:
            return int(fn(parent))
        try:
            return int(fn(self.qt.QtCore.QModelIndex()))
        except Exception:  # noqa: BLE001 - a model that takes no parent
            pass
        try:
            return int(fn())
        except Exception:  # noqa: BLE001
            return 1 if what == "columnCount" else 0

    def _rows(self, model, parent, depth=0):
        """Every index of a model's column-0 rows, depth first (a tree's
        children after their parent)."""
        n = self._count(model, "rowCount", parent)
        for r in range(n):
            ix = model.index(r, 0, parent) if parent is not None else model.index(r, 0)
            yield ix
            if depth < 12:
                try:
                    if self._count(model, "rowCount", ix) > 0:
                        yield from self._rows(model, ix, depth + 1)
                except Exception:
                    pass

    def _active_doc_label(self):
        try:
            gd = self.gui.ActiveDocument
            return str(gd.Document.Label) if gd is not None else None
        except Exception:
            return None

    def _ancestors(self, m, ix, role):
        """[(index, text)] of a row's parents, nearest first."""
        out, p = [], ix.parent()
        while p is not None and p.isValid() and len(out) < 16:
            out.append((p, _norm(m.data(p, role)) if m is not None else ""))
            p = p.parent()
        return out

    def _on_screen(self, v, ix, ups):
        """The row shows now: every parent unfolded and its rect inside the
        view's viewport."""
        try:
            if hasattr(v, "isExpanded") and any(not v.isExpanded(p) for p, _t in ups):
                return False
            r = v.visualRect(ix)
            vp = v.viewport()
            return r.height() > 0 and r.y() + r.height() > 0 and r.y() < vp.height() and r.x() < vp.width()
        except Exception:
            return False

    def find_item(self, spec):
        """(view, index, text) of the row of a visible list, tree or table
        whose shown text is spec's (whole before a part), in column (any
        column when left out). Several rows match (two documents each with a
        Sketch): the active document's rows first, then a row that shows now
        (its branch unfolded, inside the view) before one that must be
        unfolded or scrolled to, then the first. self.found_in says where."""
        Qt = self.qt.QtCore.Qt
        role = _enum(Qt, "ItemDataRole", "DisplayRole")
        views = [(w, p) for w, p in self._visible() if self._is(p, "QAbstractItemView") and self._under(p, spec)]
        want = _norm(spec["text"])
        col = spec.get("column")
        active = _norm(self._active_doc_label() or "")
        self.found_in = None
        for loose in (False, True):
            best = None
            n = 0
            for v, _p in views:
                m = v.model()
                if m is None:
                    continue
                ncol = self._count(m, "columnCount")
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
                        if not (have and (want in have if loose else want == have)):
                            continue
                        ups = self._ancestors(m, ix, role)
                        texts = [t for _p, t in ups]
                        score = (0 if active and active in texts else 1, 0 if self._on_screen(v, ix, ups) else 1, n)
                        n += 1
                        if best is None or score < best[0]:
                            path = [str(m.data(p, role)) for p, _t in reversed(ups)]
                            best = (score, v, cix, str(m.data(cix, role)), path)
            if best is not None:
                _s, v, cix, text, path = best
                self.found_in = {"path": path[-3:], **({"document": path[0]} if path else {}), "matches": n}
                return v, cix, text
        raise ToolError("not_found", f"No visible list, tree or table row {json.dumps(spec, ensure_ascii=False)}: window_snapshot shows what is there.")

    def find_menu_item(self, text):
        """(menu, action, text) of the open menu's item showing text (whole
        before a part)."""
        p = self.app().activePopupWidget()
        if p is None or not _has_class(p, "QMenu"):
            what = describe_popup(p)["kind"] if p is not None else None
            raise ToolError("invalid_state", "menu_item: no menu is open" + (f" (a {what} is in front)" if what else "") + " — click what opens it first (a toolbar button's arrow, a right-click).")
        want = _norm(text)
        acts = []
        for a in p.actions():
            try:
                if (hasattr(a, "isSeparator") and a.isSeparator()) or not a.isVisible():
                    continue
            except Exception:
                continue
            acts.append(a)
        for loose in (False, True):
            for a in acts:
                have = _norm(a.text())
                if have and (want in have if loose else want == have):
                    try:
                        if not a.isEnabled() and not self._enabled_now(a):
                            raise ToolError("invalid_state", f"menu_item: \"{a.text().replace('&', '')}\" is greyed out in this menu"
                                            + self._why_greyed(a) + ". A click on a greyed item does nothing: no command runs, the menu stays open.")
                    except AttributeError:
                        pass
                    return p, a, a.text().replace("&", "")
        raise ToolError("not_found", f"menu_item: no item {text!r} in the open menu — its items: {', '.join(menu_items(p)) or 'none'}.")

    @staticmethod
    def _command_of(a):
        """The FreeCAD command a menu's action runs, or None: a group's item
        carries it as its CommandName property, a command's own action as its
        objectName."""
        try:
            v = a.property("CommandName") if hasattr(a, "property") else None
            name = bytes(v).decode() if isinstance(v, (bytes, bytearray)) else (str(v) if v else "")
            if not name and hasattr(v, "data"):
                name = bytes(v.data()).decode()
        except Exception:
            name = ""
        if not name:
            try:
                name = a.objectName() or ""
            except Exception:
                name = ""
        return name or None

    def _enabled_now(self, a):
        """A greyed item read again after FreeCAD's commands are tested now
        (Gui.Command.update: the window's own timer refreshes them later,
        live 61: a TechDraw dimension in the Dimension drop-down read greyed
        with a view's edge selected)."""
        cmd = getattr(self.gui, "Command", None)
        upd = getattr(cmd, "update", None)
        if not callable(upd):
            return False
        try:
            upd()
            self.pump(MOVE_GAP_MS)
            return bool(a.isEnabled())
        except Exception:
            return False

    def _why_greyed(self, a):
        """What FreeCAD says of the item's command: (the command, isActive)."""
        name = self._command_of(a)
        cmd = getattr(self.gui, "Command", None)
        if not name or cmd is None or not hasattr(cmd, "get"):
            return ""
        try:
            c = cmd.get(name)
            if c is None:
                return f" ({name})"
            return f" ({name}: FreeCAD's isActive is {bool(c.isActive())} now)"
        except Exception:
            return f" ({name})"

    def _menu_fallback(self, out):
        """After a click on a menu item: a menu that is still open on the
        same item (a style or platform that wants a real hover first) gets
        the item made current and Return, as the keyboard picks it. An item
        that opens a submenu is left as it is."""
        menu, act = self.menu_pick
        self.menu_pick = None
        fired = getattr(self, "menu_fired", None)  # None: not known
        hit = out.setdefault("hit", {})
        hit.setdefault("menu_item", _plain(act.text()) if hasattr(act, "text") else None)
        try:
            sub = act.menu() if hasattr(act, "menu") else None
        except Exception:
            sub = None
        if sub is not None:
            hit["menu"] = "submenu opened"
            return
        if fired:
            hit["menu"] = "clicked"
            return
        if self.app().activePopupWidget() is menu and menu.isVisible():
            menu.setActiveAction(act)
            for ev in key_events(self.qt, ("name", "Return"), []):
                self._send(menu, ev)
                if self._detached():
                    return
            if getattr(self, "menu_fired", None) is False:
                self._trigger(menu, act)
            hit["menu"] = "picked with Return (the click did not take)"
            return
        if fired is False:
            # The click closed the menu and ran nothing: the item is run
            # as the menu runs it (live 82).
            if self._trigger(menu, act):
                hit["menu"] = "item run (the click closed the menu and did not run it)"
                return
        hit["menu"] = "clicked"

    def _trigger(self, menu, act):
        """The item run as a menu runs it: the menu closed, then the action
        triggered. False when it is greyed out."""
        try:
            if not act.isEnabled():
                return False
            if menu.isVisible():
                menu.hide()
            act.trigger()
            return True
        except Exception:  # noqa: BLE001
            return False

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
            found = getattr(self, "found_in", None) or {}
            if found.get("path"):
                extra["under"] = " › ".join(found["path"])
            if found.get("document"):
                extra["document"] = found["document"]
            if found.get("matches", 1) > 1:
                extra["matches"] = found["matches"]
            if t.get("check"):
                x = r.x() + CHECK_INSET + min(r.height(), 20) / 2.0
                self.checking = (view, ix, self._check_state(view, ix))
            else:
                x = r.x() + r.width() / 2.0
            self.extra[(id(vp), x, y)] = extra
            return vp, x, y
        if kind == "menu_item":
            menu, act, text = self.find_menu_item(v)
            r = menu.actionGeometry(act)
            x, y = r.x() + r.width() / 2.0, r.y() + r.height() / 2.0
            self._pick_menu(menu, act)
            self.extra[(id(menu), x, y)] = {"class": "QMenu", "menu_item": text}
            return menu, x, y
        if kind == "widget":
            w = self.find_widget(v)
            if isinstance(w, self.qt.QtWidgets.QAbstractScrollArea) and "at" not in t:
                w = w.viewport()
            x, y = t.get("at") or (w.width() / 2.0, w.height() / 2.0)
            return self._deepest(w, x, y)
        mw = self.mw()
        x, y = v
        pt = QtCore.QPoint(int(x), int(y))
        over = self._over_at(mw.mapToGlobal(pt))
        if over is not None:
            # A dialog or menu drawn over the window there (as a shot paints
            # it, live 55): the point is in that window, not under it.
            g = mw.mapToGlobal(pt)
            lp = over.mapFromGlobal(g)
            w, lx, ly = self._deepest(over, lp.x() + (x - int(x)), lp.y() + (y - int(y)))
            return w, lx, ly
        w = mw.childAt(pt)
        if w is None:
            w = self.qt.QtWidgets.QApplication.widgetAt(mw.mapToGlobal(pt))
        if w is None:
            raise ToolError("not_found", f"window {v}: nothing of the FreeCAD window there ({mw.width()}×{mw.height()}).")
        p = w.mapFrom(mw, pt) if (w is mw or mw.isAncestorOf(w)) else w.mapFromGlobal(mw.mapToGlobal(pt))
        return w, p.x() + (x - int(x)), p.y() + (y - int(y))

    @staticmethod
    def _button_text(b):
        """What a tool button shows: its current (default) action's text,
        else its own text, else its tooltip."""
        t = ""
        try:
            d = b.defaultAction() if hasattr(b, "defaultAction") else None
            t = d.text() if d is not None else ""
        except Exception:
            t = ""
        if not t:
            try:
                t = b.text()
            except Exception:
                t = ""
        if not t:
            try:
                t = _plain(b.toolTip())
            except Exception:
                t = ""
        return (t or "").replace("&", "")

    def _arrow_owner(self, w):
        """The tool button a dropdown's arrow part belongs to (Qt's
        qt_toolbutton_menubutton, a tool button inside the one it opens the
        menu of, or beside it in the toolbar), or None for any other widget.
        The arrow's own text is not the group's: a neighbouring or default
        label was reported for Part Design's New Sketch group."""
        try:
            name = w.objectName() or ""
        except Exception:
            return None
        if not _has_class(w, "QToolButton"):
            return None
        par = w.parentWidget()
        if _has_class(par, "QToolButton"):
            return par
        if not name.startswith("qt_toolbutton_menubutton") or par is None:
            return None
        QtW = self.qt.QtWidgets
        try:
            sibs = [b for b in par.findChildren(QtW.QToolButton)
                    if b is not w and _has_class(b, "QToolButton") and b.isVisible()
                    and not (b.objectName() or "").startswith("qt_toolbutton_menubutton")]
        except Exception:
            return None
        return self._nearest_left(w, sibs)

    def _grect(self, w):
        """w's rect in global px (x, y, width, height): one frame for
        widgets of different parents."""
        g = w.mapToGlobal(self.qt.QtCore.QPoint(0, 0))
        return (g.x(), g.y(), w.width(), w.height())

    def _nearest_left(self, arrow, buttons):
        """Of buttons, the one whose rect holds the arrow's middle, else the
        one immediately left of it on its row (right edge at most 6 px from
        the arrow's left), by global rects."""
        try:
            ax, ay, aw, ah = self._grect(arrow)
        except Exception:
            return None
        mx, my = ax + aw / 2.0, ay + ah / 2.0
        best = None
        for b in buttons:
            try:
                x, y, bw, bh = self._grect(b)
            except Exception:
                continue
            if x <= mx < x + bw and y <= my < y + bh:
                return b
            gap = abs(x + bw - ax)
            overlap = min(y + bh, ay + ah) - max(y, ay)
            if gap <= 6 and overlap > 0 and (best is None or gap < best[0]):
                best = (gap, b)
        return best[1] if best else None

    def _menu_owner(self, menu, gx, gy):
        """The tool button whose dropdown menu is the one now open: its
        menu(), its default action's menu, or (an action group's button)
        its default action among the menu's items. More than one: the one
        under (gx, gy), else the one immediately left of it."""
        try:
            acts = list(menu.actions())
        except Exception:
            acts = []
        found = []
        try:
            buttons = self.mw().findChildren(self.qt.QtWidgets.QToolButton)
        except Exception:
            return None
        for b in buttons:
            try:
                if not _has_class(b, "QToolButton") or not b.isVisible():
                    continue
                m = getattr(b, "menu", None)
                m = m() if callable(m) and not _has_class(m, "QMenu") else m
                d = b.defaultAction() if hasattr(b, "defaultAction") else None
                dm = d.menu() if d is not None and hasattr(d, "menu") else None
                if _same(m, menu) or _same(dm, menu) or (d is not None and any(_same(d, a) for a in acts)):
                    found.append(b)
            except Exception:
                continue
        own = [b for b in found if not (b.objectName() or "").startswith("qt_toolbutton_menubutton")] or found
        if len(own) <= 1:
            return own[0] if own else None
        best = None
        for b in own:
            try:
                x, y, bw, bh = self._grect(b)
            except Exception:
                continue
            if x <= gx < x + bw and y <= gy < y + bh:
                return b
            if x + bw <= gx + 6 and y <= gy < y + bh and (best is None or x + bw > best[0]):
                best = (x + bw, b)
        return best[1] if best else own[0]

    def _arrow_hit(self, b, g):
        out = {"class": self._props(b)["classes"][0], "text": self._button_text(b)[:60], "part": "menu arrow"}
        try:
            tip = _plain(b.toolTip())
            if tip and _norm(tip) != _norm(out["text"]):
                out["toolTip"] = tip[:80]
        except Exception:
            pass
        if b.objectName():
            out["name"] = b.objectName()
        place = next((u for u in self._props(b)["under"] if u), "")
        if place:
            out["in"] = place[:40]
        out["global"] = list(g)
        return out

    def _arrow_by_menu(self, out, front):
        """A click on a dropdown's arrow that opened a menu: the hit is the
        button that menu belongs to (geometry alone named the button to its
        left on FreeCAD 1.1.3)."""
        hit = out.get("hit")
        if not isinstance(hit, dict) or hit.get("part") != "menu arrow" or not _has_class(front, "QMenu"):
            return
        gx, gy = (hit.get("global") or [0, 0])[:2]
        b = self._menu_owner(front, gx, gy)
        if b is not None:
            out["hit"] = self._arrow_hit(b, (gx, gy))

    def _arrow_menu(self, w, x):
        """(tool button, its menu) when a click at x in w is on a dropdown's
        arrow: an InstantPopup button anywhere, a MenuButtonPopup button's
        arrow part (its right ARROW_W px, or a child arrow widget inside
        it); else (None, None)."""
        for b in (w, w.parentWidget() if hasattr(w, "parentWidget") else None):
            try:
                if b is None or not _has_class(b, "QToolButton"):
                    continue
                menu = b.menu() if callable(getattr(b, "menu", None)) else None
                if menu is None and hasattr(b, "defaultAction") and b.defaultAction() is not None:
                    menu = b.defaultAction().menu()
                if menu is None:
                    continue
                mode = _int(b.popupMode())
                if mode == 2 or (mode == 1 and (b is not w or x >= b.width() - ARROW_W)):
                    return b, menu
            except Exception:
                continue
        return None, None

    def _open_arrow_menu(self, w, x, out):
        """A click on a dropdown's arrow that opened no menu (sent events on
        macOS, live 48: TechDraw's Dimension button): its menu opened as the
        press would (QMenu.popup under the button, which does not wait), so
        a {menu_item} step after it works. Said in the hit as menu: opened."""
        b, menu = self._arrow_menu(w, x)
        if menu is None or self.blocker() is not None:
            return
        try:
            menu.popup(b.mapToGlobal(self.qt.QtCore.QPoint(0, b.height())))
        except Exception as e:
            out.setdefault("hit", {})["menu"] = f"not opened ({type(e).__name__}: {e})"[:120]
            return
        self.pump(MOVE_GAP_MS)
        hit = out.setdefault("hit", {})
        if self.app().activePopupWidget() is menu:
            hit["menu"] = "opened (popup: the click alone opened none)"
            out["menu"] = menu_items(menu, 20)
            self._tell(self.open_info())
        else:
            hit["menu"] = "not opened: no menu came to the front"

    def _arrow_part(self, w, x):
        """True when x falls on a MenuButtonPopup tool button's own arrow."""
        try:
            if not _has_class(w, "QToolButton") or _int(w.popupMode()) != 1:
                return False
            return x >= w.width() - ARROW_W
        except Exception:
            return False

    def hit(self, w, x, y):
        g = global_point(self.qt, w, x, y)
        extra = self.extra.pop((id(w), x, y), None)
        if extra is not None:
            return {**extra, "global": [int(round(g.x())), int(round(g.y()))]}
        owner = self._arrow_owner(w)
        if owner is not None or self._arrow_part(w, x):
            return self._arrow_hit(owner or w, (int(round(g.x())), int(round(g.y()))))
        p = self._props(w)
        out = {"class": p["classes"][0] if p["classes"] else type(w).__name__}
        if p["objectName"]:
            out["name"] = p["objectName"]
        t = (self._button_text(w) if _has_class(w, "QToolButton") else p["text"]) or (w.windowTitle() if w.isWindow() else "")
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

    def _focus_now(self):
        """The widget that has the keyboard focus now, or None."""
        try:
            return self.app().focusWidget()
        except Exception:
            return None

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
            return self._dialog_focus(b)
        app = self.app()
        f = app.focusWidget() or self.mw().focusWidget()
        # A focus widget that is no longer shown (the list of a drop-down
        # that closed, live 47) takes no keys: the nearest shown widget it
        # sits in does (the combo box).
        if f is not None and not self._really_shown(f):
            f = self._shown_ancestor(f)
            if f is self.focus_at_press:
                f = None
        p = self.pressed if self.pressed is not None and _alive(self.pressed) else None
        if p is not None and not self._really_shown(p):
            p = self._shown_ancestor(p)
        # An editor the press opened in a list, tree or table (a Property
        # view value double-clicked, live 60) takes the typing, as a
        # person's double-click puts focus there.
        ed = self._open_editor(p) if p is not None else None
        if ed is not None:
            return ed
        # The press's widget, unless focus moved on since (a field the
        # press opened and focused takes the typing).
        if p is not None and (f is None or f is self.focus_at_press):
            return p
        return f or self.mw()

    def _dialog_focus(self, b):
        """Where a key or text with no target goes while the dialog b is in
        front, as a person's typing goes: the application's focus widget
        when it is inside b, else b's own focus widget, else b's first shown
        and enabled field (a line edit, spin box, editable combo box, text
        edit), else b. Live 69: keys went to the QDialog of Sketcher's
        Insert Radius, not to its value field (Gui::QuantitySpinBox), with
        the window in the background (Qt then keeps no focus widget)."""
        def inside(w):
            try:
                return w is not None and w is not b and _alive(w) and b.isAncestorOf(w) and self._really_shown(w)
            except Exception:
                return False

        try:
            f = self.app().focusWidget()
        except Exception:
            f = None
        if inside(f):
            return f
        try:
            f = b.focusWidget()
        except Exception:
            f = None
        if inside(f):
            return f
        try:
            kids = b.findChildren(self.qt.QtWidgets.QWidget)
        except Exception:
            kids = []
        for k in kids:
            if not any(_has_class(k, c) for c in EDITORS) or not inside(k):
                continue
            try:
                if not k.isEnabled() or (hasattr(k, "isReadOnly") and k.isReadOnly()):
                    continue
                if _has_class(k, "QComboBox") and hasattr(k, "isEditable") and not k.isEditable():
                    continue
            except Exception:
                continue
            try:
                k.setFocus(_enum(self.qt.QtCore.Qt, "FocusReason", "OtherFocusReason"))
            except Exception:
                pass
            return k
        return b

    def _really_shown(self, w):
        """w and the window it is in are shown."""
        try:
            return bool(w.isVisible()) and (not hasattr(w, "window") or w.window() is None or w.window().isVisible())
        except Exception:
            return False

    def _shown_ancestor(self, w):
        """The nearest shown widget w sits in (parents, across a popup's own
        window), or None."""
        try:
            p = w.parentWidget()
        except Exception:
            return None
        n = 0
        while p is not None and n < 40:
            if self._really_shown(p):
                return p
            try:
                p = p.parentWidget()
            except Exception:
                return None
            n += 1
        return None

    def _open_editor(self, w):
        """The shown editor (a line edit, spin box, combo box or text edit,
        their FreeCAD subclasses too) inside the item view w is in or is,
        or None."""
        view, n = w, 0
        while view is not None and n < 6 and not _has_class(view, "QAbstractItemView"):
            try:
                view = view.parentWidget()
            except Exception:
                return None
            n += 1
        if view is None or not _has_class(view, "QAbstractItemView"):
            return None
        try:
            kids = view.findChildren(self.qt.QtWidgets.QWidget)
        except Exception:
            return None
        for k in kids:
            if any(_has_class(k, c) for c in EDITORS) and self._really_shown(k):
                return k
        return None

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
        if self.menu_pick is None and t.get("kind") != "menu_item":
            self._menu_under(w, x, y)
        self._check_front(w)
        return w, x, y

    def _pick_menu(self, menu, act):
        """The menu item a click aims at: kept for the click's fallback, and
        its triggered signal watched, so the fallback knows whether the
        click ran it."""
        self.menu_pick = (menu, act)
        self.menu_fired = None
        try:
            def fired(*_a):
                self.menu_fired = True

            act.triggered.connect(fired)
            self.menu_fired = False
            self.menu_watch = (act, fired)
        except Exception:  # noqa: BLE001 - not known: the fallback reads the menu
            self.menu_watch = None

    def _unwatch_menu(self):
        w, self.menu_watch = getattr(self, "menu_watch", None), None
        if w is not None:
            try:
                w[0].triggered.disconnect(w[1])
            except Exception:  # noqa: BLE001
                pass

    def _menu_under(self, w, x, y):
        """A point target (window, global, widget) that lands on an open
        menu's item: that item is picked as a menu_item target picks it,
        so the click runs it reliably (live 82: a window-point click on an
        item sometimes closed the menu and ran nothing)."""
        try:
            if not _has_class(w, "QMenu") or not w.isVisible():
                return
            act = w.actionAt(self.qt.QtCore.QPoint(int(x), int(y)))
            if act is None or (hasattr(act, "isSeparator") and act.isSeparator()) or not act.isVisible():
                return
        except Exception:  # noqa: BLE001
            return
        self._pick_menu(w, act)

    def step(self, st, out=None):
        do = st["do"]
        out = {"do": do} if out is None else out
        self.last_point = None
        self.checking = None
        self.menu_pick = None
        try:
            self._step(st, out)
            if self.checking is not None and do == "click" and not self._detached():
                self._checked(out)
            if self.menu_pick is not None and do == "click" and not self._detached():
                self._menu_fallback(out)
            return out
        finally:
            self._unwatch_menu()
            self.menu_pick = None
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
                if self._detached():
                    return out
                gw, gx, gy = self._grabbed(w, x, y)
                self._mouse("MouseButtonRelease", gw, gx, gy, st["button"], st["mods"])
                if st["double"] and not self._detached():
                    self.pump(MOVE_GAP_MS)
                    self._mouse("MouseButtonDblClick", w, x, y, st["button"], st["mods"], focus=False)
                    gw, gx, gy = self._grabbed(w, x, y)
                    self._mouse("MouseButtonRelease", gw, gx, gy, st["button"], st["mods"])
                if not self._detached():
                    self.pump(MOVE_GAP_MS)
                    if st["button"] == "left" and not st["double"] and self.menu_pick is None and not _has_class(w, "QMenu"):
                        # Not on a menu's item: a menu that closed is not
                        # its tool button's arrow to open again (live 82).
                        self._open_arrow_menu(w, x, out)
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
                if self._detached():
                    return out
                lx, ly = local_point(self.qt, w, gx, gy)
                self._mouse("MouseMove", w, lx, ly, None, st["mods"])
            lx, ly = local_point(self.qt, w, b.x(), b.y())
            self._mouse("MouseButtonRelease", w, lx, ly, st["button"], st["mods"])
        elif do in ("key", "type"):
            w = self._focus_widget(st.get("target"))
            out["hit"] = {"class": self._props(w)["classes"][0], **({"name": w.objectName()} if w.objectName() else {})}
            evs = key_events(self.qt, st["key"], st["mods"]) if do == "key" else text_events(self.qt, st["text"])
            before = None
            for i, ev in enumerate(evs):
                if do == "type" and i % 2 == 0:
                    before = self._focus_now()
                self._send(w, ev)
                if self._detached():
                    return out
                # A key that moves the focus sends the rest of the text to
                # the new focus, as a person's keys go: "=" in a quantity
                # field opens FreeCAD's expression line, and "2*3" belongs
                # there (live 98: the rest went to the spin box).
                if do == "type" and i % 2 == 1 and i + 1 < len(evs):
                    self.pump(0)
                    f = self._focus_now()
                    if f is not None and f is not before and f is not w and _alive(f) and self._really_shown(f):
                        w = f
                        out.setdefault("followed", []).append({"class": self._props(w)["classes"][0], **({"name": w.objectName()} if w.objectName() else {})})
        elif do == "shortcut":
            self._shortcut(st["keys"], out)
        elif do == "wait":
            self.pump(st["ms"])
        elif do == "shot":
            out.update(self.shot(st["name"]))
        return out

    def _actions(self):
        QtGui, QtW = self.qt.QtGui, self.qt.QtWidgets
        cls = getattr(QtGui, "QAction", None) or getattr(QtW, "QAction", None)
        try:
            return list(self.mw().findChildren(cls)) if cls is not None else []
        except Exception:
            return []

    @staticmethod
    def _in_sight(a):
        """An action shown in the window now: on a shown toolbar button or
        in a menu (FreeCAD's active workbench puts its commands there)."""
        try:
            objs = a.associatedObjects() if hasattr(a, "associatedObjects") else a.associatedWidgets()
        except Exception:
            return False
        for o in objs or ():
            try:
                if _has_class(o, "QMenu") or (hasattr(o, "isVisible") and o.isVisible()):
                    return True
            except Exception:
                continue
        return False

    def _shortcut(self, keys, out):
        """The opt-in shortcut step (live 49): the enabled action whose
        shortcut is keys triggered, as the key press would, and the command
        that ran named. Sent key events never reach Qt's shortcut map."""
        QtGui = self.qt.QtGui
        b = self.blocker()
        if b is not None:
            raise ToolError("invalid_state", "shortcut: a dialog or menu is in front and takes the keys: close it first (Escape, dialog_answer, gui_unstick). This step was not run.")
        want = QtGui.QKeySequence(keys)
        text = want.toString()
        if not text:
            raise ToolError("invalid_input", f"shortcut: {keys!r} is not a key sequence Qt reads (\"Shift+V\", \"V, D\").")
        found = {}
        for a in self._actions():
            try:
                if not a.isEnabled() or not any(sq.toString() == text for sq in (a.shortcuts() or [])):
                    continue
                name = a.objectName() or a.text().replace("&", "")
            except Exception:
                continue
            found.setdefault(name, (a, self._in_sight(a)))
        shown = {n: v for n, v in found.items() if v[1]} or found
        if not shown:
            raise ToolError("not_found", f"shortcut: no enabled command has {text} in this workbench. cmd_run runs a command by its name.")
        if len(shown) > 1:
            raise ToolError("invalid_state", f"shortcut: {text} belongs to more than one command ({', '.join(sorted(shown))}): Qt runs none of them. Use cmd_run.")
        name, (a, _s) = next(iter(shown.items()))
        why = refused_command(name)
        if why:
            raise ToolError("refused", f"shortcut: {text} runs {name} — {why}. This step was not run.")
        out["hit"] = {"shortcut": text, "command": name, "text": (a.text() or "").replace("&", "")[:60]}
        fr = self.frames[-1] if self.frames else None
        if fr is not None:
            fr["sending"] += 1  # a dialog the command opens is seen by the watch
        try:
            a.trigger()
        finally:
            if fr is not None:
                fr["sending"] -= 1
        if not self._detached():
            self.pump(MOVE_GAP_MS)

    def _over(self):
        """The windows that float over the main window in front, bottom
        first: the modal dialog, then the open popups (a menu and its
        submenus, a drop-down list), the active popup last."""
        app, mw = self.app(), self.mw()
        out = []
        m = app.activeModalWidget()
        if m is not None and m is not mw and self._shown(m):
            out.append(m)
        p = app.activePopupWidget()
        try:
            popup = _int(_enum(self.qt.QtCore.Qt, "WindowType", "Popup"))
            mask = _int(_enum(self.qt.QtCore.Qt, "WindowType", "WindowType_Mask"))
            for t in app.topLevelWidgets():
                if t is not p and t is not mw and t not in out and self._shown(t) and _int(t.windowType()) & mask == popup:
                    out.append(t)
        except Exception:
            pass
        if p is not None and p is not mw and self._shown(p) and p not in out:
            out.append(p)
        return out

    def _over_at(self, g):
        """The window over the main window (a dialog, a menu) whose rect
        holds the global point g, the front one first, or None."""
        for w in reversed(self._over()):
            try:
                o = w.mapToGlobal(self.qt.QtCore.QPoint(0, 0))
                if o.x() <= g.x() < o.x() + w.width() and o.y() <= g.y() < o.y() + w.height():
                    return w
            except Exception:
                continue
        return None

    def _paint_over(self, pix, ws):
        """Each window in ws painted over the main window's picture where it
        is on the screen (a widget grab of the main window leaves out the
        menus and dialogs over it, which are windows of their own)."""
        QtCore, QtGui = self.qt.QtCore, self.qt.QtGui
        mw = self.mw()
        painter = QtGui.QPainter(pix)
        n = 0
        try:
            for w in ws:
                try:
                    g = w.mapToGlobal(QtCore.QPoint(0, 0))
                    o = mw.mapFromGlobal(g)
                    painter.drawPixmap(QtCore.QPoint(int(o.x()), int(o.y())), w.grab())
                    n += 1
                except Exception:
                    continue
        finally:
            painter.end()
        return n

    def _settle(self, ws):
        """Before a shot: each window over the main one laid out and its
        pending events run, so a dialog that just came up is drawn whole
        (live 86: a shot of a new dialog had no OK and Cancel at the
        bottom; the next shot had them)."""
        for w in ws:
            try:
                lay = w.layout() if hasattr(w, "layout") else None
                if lay is not None:
                    lay.activate()
            except Exception:  # noqa: BLE001
                pass
        if ws and not self._detached():
            self.pump(SHOT_SETTLE_MS)

    def shot(self, name):
        import os

        os.makedirs(self.shot_dir, exist_ok=True)
        path = os.path.join(self.shot_dir, name + ".png")
        self._settle(self._over())
        pix = self.grab(self.mw())
        over = self._over()
        painted = self._paint_over(pix, over) if over else 0
        if not pix.save(path, "PNG"):
            raise ToolError("failed", f"Could not write {path}")
        out = {"path": path, "size": [pix.width(), pix.height()]}
        if painted:
            out["over"] = painted  # menus and dialogs painted in where they are
        b = self.blocker()
        if b is not None and b.isWindow():
            extra = os.path.join(self.shot_dir, name + "-front.png")
            if b.grab().save(extra, "PNG"):
                out["front"] = extra
        self.shots.append(path)
        return out

    # -- a step's menu or dialog holding the call --

    def _front_info(self, b):
        if b is None:
            return None
        if self.app().activePopupWidget() is b:
            return {"menu": menu_items(b, 20)} if _has_class(b, "QMenu") else {"popup": describe_popup(b)}
        d = self.modal()
        if d is None:
            return {"dialog": {"title": b.windowTitle()}}
        return {"dialog": {k: d[k] for k in ("class", "title", "text", "buttons") if k in d}}

    def open_info(self):
        return describe_front(self.app(), self.modal)

    def watch(self):
        """From a timer, or the ticker's queued call: a step whose event
        started a nested loop (its sendEvent has not returned, and a menu or
        dialog it opened is in front) holds the call until that loop ends.
        Seen from inside the loop, the step is set aside and the steps after
        it run from here, so they act on what it opened."""
        if self.final is not None or not self.frames:
            return
        fr = self.frames[-1]
        if fr["detached"] or fr["sending"] <= 0:
            return
        b = self.blocker()
        if b is None or b is fr["front"]:
            return
        fr["detached"] = True
        # The press went to what opened the menu, and the menu took the
        # mouse (as a real one does): no button is held for later steps.
        HELD.update({"widget": None, "buttons": []})
        out = {"i": fr["i"], **fr["out"]}
        self._arrow_by_menu(out, b)
        out.update(self._front_info(b) or {})
        self.done.append(out)
        self._tell(self.open_info())
        self._go()
        if self.blocker() is not b:
            # The steps run here closed what the stuck step opened: its
            # loop is woken so it ends now (live 70).
            self._wake()

    def _wake(self):
        """The GUI thread's event loop interrupted and woken (gui_link.wake)."""
        try:
            QtCore = self.qt.QtCore
            app = QtCore.QCoreApplication.instance()
            d = QtCore.QAbstractEventDispatcher.instance(app.thread())
            d.interrupt()
            d.wakeUp()
        except Exception:  # noqa: BLE001 - no dispatcher: nothing to wake
            pass

    def _tell(self, info):
        if self.seen is not None:
            try:
                self.seen(info)
            except Exception:
                pass

    def answer(self, steps, note=None, open_=None):
        out = {"steps": steps}
        if self.as_:
            out["as"] = self.as_
        if HELD["buttons"]:
            out["held"] = list(HELD["buttons"])
        if self.shots:
            out["shots"] = len(self.shots)
        if open_:
            out["open"] = open_
            note = (note + " " if note else "") + OPEN_NOTE
        if note:
            out["note"] = note
        return cap_answer(out)

    def _go(self):
        """Run the steps from self.next on; called by run() and again by the
        watch from inside a step's nested loop."""
        QtCore = self.qt.QtCore
        timer = QtCore.QTimer()
        timer.setInterval(60)
        timer.timeout.connect(self.watch)
        timer.start()
        try:
            while self.next < len(self.steps):
                i = self.next
                self.next += 1
                st = self.steps[i]
                fr = {"i": i, "do": st["do"], "out": {"do": st["do"]}, "front": self.blocker(), "sending": 0, "detached": False}
                before = self.modal()
                self.frames.append(fr)
                err = None
                try:
                    self.step(st, fr["out"])
                except Exception as e:  # noqa: BLE001 - the steps before it are still answered
                    err = e
                finally:
                    self.frames = [f for f in self.frames if f is not fr]
                if fr["detached"]:
                    return  # the steps after it ran inside its loop, and answered
                if err is not None:
                    msg = err.message if isinstance(err, ToolError) else f"{type(err).__name__}: {err}"
                    self.done.append({"i": i, "do": st["do"], "error": msg})
                    break
                out = {"i": i, **fr["out"]}
                b = self.blocker()
                if b is not None and b is not fr["front"]:
                    self._arrow_by_menu(out, b)
                    out.update(self._front_info(b) or {})
                elif before is None and self.modal() is not None:
                    out.update(self._front_info(self.blocker()) or {})
                if st["do"] not in ("wait", "shot"):
                    self.pump(MOVE_GAP_MS)
                lines = self.report()
                if lines:
                    out["report"] = lines
                self.done.append(out)
            self._finish()
        finally:
            timer.stop()

    def _finish(self):
        if self.final is not None:
            return
        info = self.open_info()
        self.final = self.answer(self.done, open_=info)
        self._release_person()  # the steps are over: what follows is not theirs
        self._tell(info)
        # Inside a step's nested loop (the steps it held were set aside):
        # the answer goes out now, while the menu or dialog stays open.
        if self.frames and self.answer_now(self.final):
            self.answered = True

    def run(self, steps):
        self.steps, self.next, self.final, self.frames, self.done = list(steps), 0, None, [], []
        stop = None
        if self.ticker is not None:
            try:
                stop = self.ticker(self.watch)
            except Exception:
                stop = None
        try:
            self._go()
        finally:
            self._release_person()
            if stop is not None:
                try:
                    stop()
                except Exception:
                    pass
        return self.final if self.final is not None else self.answer(self.done)
