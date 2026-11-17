# SPDX-License-Identifier: LGPL-2.1-or-later
"""The overlay painter: rings, numbered badges and a callout drawn over the
FreeCAD window, for any add-on that points at something and for the live
echo's lit buttons. Offered as hooks.service("overlay").

One transparent child of the main window, sized to it, that takes no mouse,
no keys and no focus (WA_TransparentForMouseEvents, WA_NoSystemBackground,
WA_TranslucentBackground, Qt.NoFocus). Nothing is styled: a widget's own
stylesheet is never touched, so a theme's rules stay as they are. A ring is
a 3 px line in the theme's accent (ThemeAccentColor1, else the palette's
highlight) with a 2 px halo, black on a light window and white on a dark
one; a badge numbers the targets so a highlight never rests on colour
alone; the callout wraps at 320 px in the app font (13 px at least), stays
inside the window, off its target, and never over the 3D view: a native GL
surface paints over the overlay, so the callout goes to the docks or the
toolbar area beside it, narrowing to 180 px with more lines if it must; it
keeps off tab bars and the menubar where it can.

Rects follow their widgets: an event filter on each (Move, Resize, Show,
Hide) and a 250 ms timer while anything is drawn. A widget that is hidden,
covered or in another window is reported, not painted. Geometry is in
logical pixels, so a Retina screen needs nothing more.

A menu is ringed at its title in the menubar (QMenuBar.actionGeometry); when
the person opens it, a ring is drawn inside the menu itself on the next
title or item (QMenu.actionGeometry). The native macOS menubar cannot be
drawn over: menu() says so, and the caller gives the path in words.

Never here: moving the cursor, synthetic input, taking focus, opening a
menu (popup/exec), raising or activating the window, full screen. The
overlay itself is raised among its siblings so it is drawn above the docks;
that is not the window.

    ov = hooks.service("overlay")
    h = ov.show([{"widget": w}, {"widget": tree, "rect": lambda: tree.visualItemRect(it), "viewport": tree.viewport()}],
                say="Press Pad.", ms=8000, owner="mine")
    ov.flash(button, 1300)                  # echo's lit button
    ov.menu(["Part Design", "Pad"], badge=2, owner="mine")
    ov.clear("mine")

The plain parts (colours, where a callout goes, the marks and their
expiry) need no Qt and are tested headless.
"""

import sys
import time

THEME = "User parameter:BaseApp/Preferences/MainWindow"
RING, HALO, PAD = 3, 2, 3
BADGE = 18
WRAP, FONT_MIN, BUBBLE_PAD, GAP, MARGIN = 320, 13, 8, 10, 6
TICK_MS = 250
# Colour-blind-safe stand-ins (Okabe-Ito orange, blue) when the theme's
# accent is too close to the window's colour (contrast under 3:1).
SAFE = ("#e69f00", "#0072b2")
CONTRAST_MIN = 3.0
FLASH_ALPHA = 90


# ---- colours (no Qt) --------------------------------------------------------

def rgb(hex_):
    h = str(hex_).lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(c):
    """WCAG relative luminance of an (r, g, b) or #rrggbb colour, 0..1."""
    r, g, b = rgb(c) if isinstance(c, str) else c

    def ch(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def is_light(window_lum):
    return window_lum >= 0.5


def halo(window_lum):
    """The halo around a ring: black on a light window, white on a dark one."""
    return "#000000" if is_light(window_lum) else "#ffffff"


def ring_colour(accent, window):
    """The accent, or the safe stand-in that reads best on window when the
    accent is under 3:1 against it."""
    if contrast(accent, window) >= CONTRAST_MIN:
        return accent
    return max(SAFE, key=lambda c: contrast(c, window))


def ink(fill):
    """Text on fill: black or white, whichever reads."""
    return "#000000" if contrast("#000000", fill) >= contrast("#ffffff", fill) else "#ffffff"


def bubble(window_lum):
    """(fill, text) of the callout: light on a light window, dark on a dark."""
    return ("#ffffff", "#1d1f23") if is_light(window_lum) else ("#26292e", "#f2f2f2")


def theme_is(name):
    """"light", "dark" or None from a theme's or stylesheet's name."""
    n = str(name or "").lower()
    if "light" in n:
        return "light"
    if "dark" in n:
        return "dark"
    return None


def window_luminance(palette_window=None, params=None):
    """How light the window is, 0..1. FreeCAD's light themes are stylesheets
    over a palette that may stay dark, so the theme's name (MainWindow
    Theme, then StyleSheet) decides when it says light or dark; else the
    palette's Window colour; else dark."""
    if params is None:
        try:
            import FreeCAD

            params = FreeCAD.ParamGet(THEME)
        except Exception:
            params = None
    for key in ("Theme", "StyleSheet"):
        try:
            got = theme_is(params.GetString(key, "")) if params is not None else None
        except Exception:
            got = None
        if got:
            return 0.9 if got == "light" else 0.08
    if palette_window is not None:
        return luminance(palette_window)
    return 0.08


# ---- geometry (no Qt): rects are (x, y, w, h) in the host's logical px -----

def grow(r, d):
    x, y, w, h = r
    return (x - d, y - d, w + 2 * d, h + 2 * d)


def clamp_rect(r, area):
    """r moved (not resized, unless it is bigger) to lie inside area."""
    x, y, w, h = r
    ax, ay, aw, ah = area
    w, h = min(w, aw), min(h, ah)
    x = min(max(x, ax), ax + aw - w)
    y = min(max(y, ay), ay + ah - h)
    return (x, y, w, h)


def overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    w = min(ax + aw, bx + bw) - max(ax, bx)
    h = min(ay + ah, by + bh) - max(ay, by)
    return max(0, w) * max(0, h)


def badge_at(r, area):
    """The badge's square at the ring's top-left corner, inside area."""
    x, y, _w, _h = grow(r, PAD + RING)
    return clamp_rect((x - BADGE // 2, y - BADGE // 2, BADGE, BADGE), area)


CALLOUT_MIN = 180  # px: the narrowest a callout gets, wrapping more lines
WIDTHS = (WRAP + 2 * BUBBLE_PAD, 280, 240, 210, CALLOUT_MIN)
HARD, SOFT, NEAR = 1000.0, 20.0, 1000.0


def _side(r, t):
    x, y, w, h = r
    tx, ty, tw, th = t
    if y >= ty + th:
        return "below"
    if y + h <= ty:
        return "above"
    return "right" if x >= tx + tw else "left" if x + w <= tx else "over"


def place_callout(target, size, area, forbid=(), soft=(), measure=None):
    """(x, y, w, h, side) of a callout next to target (a rect, or None).

    size (w, h) is its natural size; measure(w) -> h, when given, lets it
    narrow (down to CALLOUT_MIN, more lines) to fit. forbid: rects it must
    not cover, where the overlay cannot draw (the 3D view: a native GL
    surface paints over it); soft: rects it had better not cover (tab bars,
    the menubar, the rings). It is kept inside area and off its target; of
    the places beside the target, slid clear of what is forbidden, and the
    free columns beside each forbidden rect (the docks), the one that
    covers least, then is nearest, wins. With no target: the top centre,
    unless that is forbidden."""
    ax, ay, aw, ah = area
    inner = (ax + MARGIN, ay + MARGIN, aw - 2 * MARGIN, ah - 2 * MARGIN)
    forbid, soft = [tuple(f) for f in forbid or ()], [tuple(f) for f in soft or ()]
    if measure is None:  # the same text over less width: as many more lines
        def measure(w, w0=size[0], h0=size[1]):
            return h0 if w >= w0 else int(-(-h0 * w0 // max(1, w)))
    sizes = []
    for w in sorted({min(size[0], x) for x in WIDTHS} | {size[0]}, reverse=True):
        if w >= min(CALLOUT_MIN, size[0]):
            sizes.append((w, size[1] if w == size[0] else measure(w)))
    t = grow(target, PAD + RING) if target is not None else None
    if t is not None:
        tx, ty, tw, th = t
        cx, cy = tx + tw / 2.0, ty + th / 2.0
    else:
        cx, cy = ax + aw / 2.0, ay + MARGIN + 40
    best = None
    for bw, bh in sizes:
        bw, bh = min(bw, aw - 2 * MARGIN), min(bh, ah - 2 * MARGIN)
        spots = []
        if t is None:
            spots.append((ax + (aw - bw) // 2, ay + MARGIN + 40))
        else:
            xs = [tx + (tw - bw) // 2, tx, tx + tw - bw] + [f[0] - GAP - bw for f in forbid] + [f[0] + f[2] + GAP for f in forbid]
            ys = [ty + (th - bh) // 2, ty, ty + th - bh] + [f[1] - GAP - bh for f in forbid] + [f[1] + f[3] + GAP for f in forbid]
            spots += [(x, ty + th + GAP) for x in xs] + [(x, ty - GAP - bh) for x in xs]
            spots += [(tx + tw + GAP, y) for y in ys] + [(tx - GAP - bw, y) for y in ys]
        # The free columns and rows beside each forbidden rect (a dock).
        for fx, fy, fw, fh in forbid:
            yy = int(cy - bh / 2)
            xx = int(cx - bw / 2)
            spots += [(fx - GAP - bw, yy), (fx + fw + GAP, yy), (xx, fy - GAP - bh), (xx, fy + fh + GAP)]
        for x, y in spots:
            r = clamp_rect((int(x), int(y), bw, bh), inner)
            score = sum(overlap(r, f) for f in forbid) * HARD + sum(overlap(r, f) for f in soft) * SOFT
            if t is not None:
                score += overlap(r, t) * NEAR
            rx, ry = r[0] + r[2] / 2.0, r[1] + r[3] / 2.0
            score += abs(rx - cx) + abs(ry - cy)
            score += (WRAP - bw) * 0.2  # wider and fewer lines, other things equal
            if best is None or score < best[0]:
                best = (score, r)
    r = best[1]
    return r + (_side(r, t) if t is not None else "top",)


# ---- the marks (no Qt) ------------------------------------------------------

class Mark:
    """One thing drawn: a ring (or a flash) round a widget's rect."""

    __slots__ = ("id", "owner", "widget", "rect", "viewport", "badge", "style", "host", "until", "handle")

    def __init__(self, id, owner, widget, rect=None, viewport=None, badge=None, style="ring", host=None, until=None, handle=None):
        self.id, self.owner, self.widget, self.rect, self.viewport = id, owner, widget, rect, viewport
        self.badge, self.style, self.host, self.until, self.handle = badge, style, host, until, handle


class Board:
    """The marks and callouts in hand, by owner; each show() a handle that
    expires together. Hosts: None the main window, else a menu."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.marks = []
        self.says = {}  # handle -> (owner, text, until)
        self._n = 0

    def _id(self):
        self._n += 1
        return self._n

    def add(self, owner, specs, say=None, ms=None):
        h = self._id()
        until = self.clock() + ms / 1000.0 if ms else None
        made = []
        for s in specs:
            m = Mark(self._id(), owner, s.get("widget"), s.get("rect"), s.get("viewport"), s.get("badge"), s.get("style", "ring"),
                     s.get("host"), until, h)
            self.marks.append(m)
            made.append(m)
        if say:
            self.says[h] = (owner, str(say), until)
        return h, made

    def add_marks(self, handle, owner, specs):
        """More marks for a handle already shown (a menu opened later)."""
        until = next((m.until for m in self.marks if m.handle == handle), None)
        made = [Mark(self._id(), owner, s.get("widget"), s.get("rect"), s.get("viewport"), s.get("badge"), s.get("style", "ring"),
                     s.get("host"), until, handle) for s in specs]
        self.marks += made
        return made

    def drop(self, pred):
        gone = [m for m in self.marks if pred(m)]
        self.marks = [m for m in self.marks if not pred(m)]
        return gone

    def clear(self, owner=None, handle=None):
        def hit(m):
            return (owner is None or m.owner == owner) and (handle is None or m.handle == handle)

        gone = self.drop(hit)
        for h in [h for h, (o, _t, _u) in self.says.items() if (owner is None or o == owner) and (handle is None or h == handle)]:
            del self.says[h]
        return gone

    def expire(self):
        now = self.clock()
        gone = self.drop(lambda m: m.until is not None and m.until <= now)
        for h in [h for h, (_o, _t, u) in self.says.items() if u is not None and u <= now]:
            del self.says[h]
        return gone

    def empty(self):
        return not self.marks and not self.says

    def scene(self, host, mapper, area):
        """What to paint on host: ([(rect, badge, style)], [(callout rect,
        side, text)], [hidden marks]). mapper(mark) -> rect in host px, or
        None when it cannot be seen."""
        items, hidden, first = [], [], {}
        for m in self.marks:
            if m.host is not host:
                continue
            r = mapper(m)
            if r is None:
                hidden.append(m)
                continue
            items.append((r, m.badge, m.style))
            first.setdefault(m.handle, r)
        calls = []
        if host is None:
            for h, (_o, text, _u) in self.says.items():
                calls.append((first.get(h), text))
        return items, calls, hidden


def paint_key(board, host, mapper):
    """What a painter on host draws, as a value to compare: its marks'
    rects, badges and styles and its callouts' words. Plain Python."""
    marks = []
    for m in board.marks:
        if m.host is not host:
            continue
        try:
            marks.append((mapper(m), m.badge, m.style))
        except Exception:  # noqa: BLE001
            marks.append((None, m.badge, m.style))
    says = tuple(sorted(str(t) for _o, t, _u in board.says.values())) if host is None else ()
    return (tuple(marks), says)


# ---- the service ------------------------------------------------------------

class Overlay:
    """hooks.service("overlay"). Every method is safe without a window
    (headless: nothing drawn, reasons say so) and logs instead of raising."""

    def __init__(self, gui=None):
        self.board = Board()
        self._gui = gui  # FreeCADGui, or a stand-in in tests
        self._painters = {}  # host -> painter widget
        self._watch = None
        self._timer = None
        self._menus = []  # (menu, signal, slot) connected for menu()

    # -- reading
    def gui(self):
        if self._gui is None:
            try:
                import FreeCAD

                if not FreeCAD.GuiUp:  # before importing FreeCADGui: headless, a windowless one
                    return None
                import FreeCADGui

                self._gui = FreeCADGui
            except Exception:
                return None
        return self._gui

    def window(self):
        g = self.gui()
        try:
            return g.getMainWindow() if g is not None else None
        except Exception:
            return None

    def colours(self, widget=None):
        """{accent, halo, window_lum, bubble, bubble_text} for painting."""
        from . import theme

        w = widget or self.window()
        pal_win = None
        try:
            from PySide import QtGui

            c = w.palette().color(QtGui.QPalette.Window)
            pal_win = (c.red(), c.green(), c.blue())
        except Exception:
            pal_win = None
        lum = window_luminance(pal_win)
        accent = theme.roles(w)["accent"] if w is not None else "#3f93e0"
        win = "#f0f0f0" if is_light(lum) else "#2a2a2a"
        fill, text = bubble(lum)
        return {"accent": ring_colour(accent, win), "halo": halo(lum), "window_lum": lum, "bubble": fill, "bubble_text": text}

    def visible(self, widget):
        """None when widget can be ringed, else why not (plain words)."""
        mw = self.window()
        if mw is None:
            return "no window (FreeCAD runs without its GUI)"
        try:
            if widget is None:
                return "not found"
            if not alive(widget):
                return "gone"
            if not widget.isVisible():
                return "hidden"
            if widget.window() is not mw and not _is_menu(widget):
                return "in another window"
            if widget.visibleRegion().isEmpty() and not self._hit(widget, mw):
                return "covered"
        except RuntimeError:
            return "gone"
        return None

    @staticmethod
    def _hit(widget, mw):
        """True when the main window's widget under widget's middle is widget
        or inside it. childAt passes over widgets transparent to the mouse,
        so the overlay and its callout never count as covering."""
        try:
            r = widget.rect()
            mid = r.center() if hasattr(r, "center") else _point(r[0] + r[2] // 2, r[1] + r[3] // 2)
            at = mw.childAt(widget.mapTo(mw, mid))
        except Exception:  # noqa: BLE001
            return False
        while at is not None:
            if at is widget:
                return True
            try:
                at = at.parentWidget()
            except Exception:  # noqa: BLE001
                return False
        return False

    def watch_menu(self, menu, action, owner="", handle=None, badge=None):
        """Ring action inside menu whenever the person opens it (a toolbar
        button's dropdown), as menu() does for the menubar's menus."""
        if menu is None or action is None:
            return
        self._watch_menu(menu, action, handle, owner, badge)

    # Where the overlay cannot draw (hard): the 3D views and any other native
    # GL surface, painted over the overlay by the system. Where a callout had
    # better not go (soft): tab bars and the menubar. Widget class names.
    NO_GO = ("QMdiArea", "QOpenGLWidget", "QGLWidget", "QQuickWidget", "Gui::View3DInventorViewer", "View3DInventor")
    SOFT = ("QTabBar", "QMenuBar")
    NO_GO_MS = 1.0

    def no_go(self, host=None):
        """([hard rects], [soft rects]) in the main window's px, kept a
        second (the window is walked at most once a second)."""
        now = time.monotonic()
        got = getattr(self, "_no_go", None)
        if got is not None and now - got[0] < self.NO_GO_MS:
            return got[1], got[2]
        hard, soft = [], []
        mw = self.window()
        try:
            _QtCore, _QtGui, QtW = _qt()
            for w in mw.findChildren(QtW.QWidget):
                try:
                    cls = w.metaObject().className()
                except Exception:
                    cls = type(w).__name__
                kind = "hard" if cls in self.NO_GO else "soft" if cls in self.SOFT else None
                if kind is None or not w.isVisible() or w.window() is not mw:
                    continue
                r = self._map({"widget": w})
                if r is None:
                    continue
                (hard if kind == "hard" else soft).append(r)
        except Exception as e:  # noqa: BLE001
            _log("overlay: no-go areas not read", e)
        # A GL view inside the MDI area is inside its rect: one rect is enough.
        hard = [r for r in hard if not any(o != r and _inside(r, o) for o in hard)]
        self._no_go = (now, hard, soft)
        return hard, soft

    # -- drawing
    def show(self, specs, say=None, ms=None, owner=""):
        """Ring each spec ({widget, rect?, viewport?, badge?}) with say in a
        callout; ms: gone after that long (None: until clear). Returns
        {"handle", "shown": [i], "hidden": [(i, why)]} by spec index."""
        if self.window() is None:
            return {"handle": None, "shown": [], "hidden": [(i, "no window (FreeCAD runs without its GUI)") for i in range(len(specs))]}
        hidden, shown, keep = [], [], []
        for i, s in enumerate(specs):
            why = self.visible(s.get("widget"))
            if why is None and s.get("rect") is not None and self._map(s) is None:
                why = "scrolled out of view" + self._why_unmapped(s)
            if why:
                hidden.append((i, why))
            else:
                shown.append(i)
            keep.append(s)
        h, _made = self.board.add(owner, keep, say=say, ms=ms)
        self._refresh()
        return {"handle": h, "shown": shown, "hidden": hidden}

    def flash(self, widget, ms=1300, owner="echo"):
        """A button lit for ms, filled with the accent under its ring."""
        if not alive(widget) or self.visible(widget) is not None:
            return False
        self.board.add(owner, [{"widget": widget, "style": "flash"}], ms=ms)
        self._refresh()
        return True

    def clear(self, owner=None, handle=None):
        self.board.clear(owner, handle)
        if handle is None:
            self._unwatch_menus(owner)
        self._refresh()

    def menu(self, titles, badge=None, owner="", handle=None, say=None, ms=None):
        """Ring a menu's title in the menubar and, as the person opens each
        menu on the way, the next title inside it. {"native": True} when the
        menubar is the system's (macOS) and cannot be drawn over; {"missing":
        title} for the first title not found; else {"handle"}."""
        from . import targets

        mw = self.window()
        if mw is None:
            return {"missing": titles[0] if titles else None, "why": "no window (FreeCAD runs without its GUI)"}
        found = targets.menu_path(titles, mw)
        if found.get("missing") is not None:
            return {"missing": found["missing"], "path": found.get("path")}
        bar, chain = found["bar"], found["chain"]
        if targets.native_menubar(mw):
            return {"native": True, "path": found.get("path"), "action": chain[-1][1] if chain else None}
        top = chain[0][1]
        spec = {"widget": bar, "rect": (lambda b=bar, a=top: _rect(b.actionGeometry(a))), "badge": badge}
        if handle is None:
            h, _ = self.board.add(owner, [spec], say=say, ms=ms)
        else:
            h = handle
            self.board.add_marks(h, owner, [spec])
        # Each menu on the way rings the next title (or the item) inside it
        # while it is open; the person opens it, never this.
        for menu, act in chain[1:]:
            if menu is not None:
                self._watch_menu(menu, act, h, owner, badge)
        self._refresh()
        return {"handle": h, "path": found.get("path")}

    # -- the Qt side (only with a window)
    def _watch_menu(self, menu, action, handle, owner, badge):
        def opened(m=menu, a=action):
            try:
                self.board.drop(lambda x: x.host is m and x.handle == handle)
                self.board.add_marks(handle, owner, [{"widget": m, "rect": (lambda m=m, a=a: _rect(m.actionGeometry(a))), "badge": badge, "host": m}])
                self._refresh()
            except Exception as e:  # noqa: BLE001
                _log("overlay: a menu ring failed", e)

        def closed(m=menu):
            self.board.drop(lambda x: x.host is m)
            p = self._painters.pop(m, None)
            if p is not None and alive(p):
                try:
                    p.deleteLater()
                except RuntimeError:
                    pass

        try:
            menu.aboutToShow.connect(opened)
            menu.aboutToHide.connect(closed)
            self._menus.append((menu, opened, closed, owner))
        except Exception as e:  # noqa: BLE001
            _log("overlay: a menu could not be watched", e)

    def _unwatch_menus(self, owner=None):
        keep = []
        for menu, opened, closed, who in self._menus:
            if owner is not None and who != owner:
                keep.append((menu, opened, closed, who))
                continue
            if alive(menu):
                try:
                    menu.aboutToShow.disconnect(opened)
                    menu.aboutToHide.disconnect(closed)
                except Exception:
                    pass
            p = self._painters.pop(menu, None)
            if p is not None and alive(p):
                try:
                    p.deleteLater()
                except RuntimeError:
                    pass
        self._menus = keep

    def _map(self, m):
        """A mark's rect in its host's logical px, or None when unseen."""
        host = m.get("host") if isinstance(m, dict) else m.host
        w = m.get("widget") if isinstance(m, dict) else m.widget
        rect = m.get("rect") if isinstance(m, dict) else m.rect
        port = (m.get("viewport") if isinstance(m, dict) else m.viewport) or w
        if not alive(w) or not alive(port) or (host is not None and not alive(host)):
            return None
        try:
            if w is None or not w.isVisible():
                return None
            target = host if host is not None else self.window()
            if host is None and w.window() is not target:
                return None
            r = rect() if callable(rect) else _rect(w.rect())
            if r is None:
                return None
            x, y, rw, rh = r
            if rw <= 0 or rh <= 0:
                return None
            # Off the part of its viewport that shows (a tree row scrolled away).
            if callable(rect):
                pr = _rect(port.rect())
                if overlap((x, y, rw, rh), pr) == 0:
                    return None
            if port is target:
                return (int(x), int(y), int(rw), int(rh))
            px, py = _xy(port.mapTo(target, _point(int(x), int(y))))
            return (px, py, int(rw), int(rh))
        except RuntimeError:
            return None
        except Exception as e:  # noqa: BLE001
            _log("overlay: a rect could not be mapped", e)
            return None

    def _why_unmapped(self, m):
        """Which of _map's reasons it was, in a few words after "scrolled out
        of view" (that one phrase stood for a row with no rect, a row of no
        size and a row off its viewport alike, and could not be told apart
        from outside)."""
        try:
            w, rect = m.get("widget"), m.get("rect")
            port = m.get("viewport") or w
            r = rect() if callable(rect) else None
            if r is None:
                return " (its row is no longer there)"
            x, y, rw, rh = r
            pr = _rect(port.rect())
            if rw <= 0 or rh <= 0:
                return f" (its row has no size yet: {int(rw)} x {int(rh)} at {int(x)}, {int(y)}; the view is {int(pr[2])} x {int(pr[3])})"
            return f" (its row is at {int(x)}, {int(y)}, {int(rw)} x {int(rh)}; the view shows 0, 0 to {int(pr[2])}, {int(pr[3])})"
        except Exception as e:  # noqa: BLE001
            import traceback

            at = traceback.extract_tb(e.__traceback__)[-1]
            return f" ({type(e).__name__}: {str(e)[:120]} at {at.name}:{at.lineno})"

    def gone(self):
        """Marks whose widget, viewport or host (a menu) was destroyed (a
        workbench change deletes its toolbars' buttons and its menus), and
        painters whose host or self is gone, dropped without touching them.
        The marks dropped."""
        dead = self.board.drop(lambda m: (m.widget is not None and not alive(m.widget)) or (m.viewport is not None and not alive(m.viewport))
                               or (m.host is not None and not alive(m.host)))
        for host in list(self._painters):
            p = self._painters[host]
            if (host is not None and not alive(host)) or not alive(p):
                self._painters.pop(host, None)
        self._menus = [x for x in self._menus if alive(x[0])]
        return dead

    def _refresh(self):
        try:
            self.board.expire()
            self.gone()
            mw = self.window()
            if mw is None or not alive(mw):
                return
            hosts = {None} | {m.host for m in self.board.marks}
            for host in list(self._painters):
                if host not in hosts:
                    p = self._painters.pop(host)
                    if not alive(p):
                        continue
                    try:
                        p.hide()
                        p.deleteLater() if host is not None else None
                    except RuntimeError:
                        pass
            for host in hosts:
                p = self._painter(host if host is not None else mw, host)
                if p is None:
                    continue
                if self.board.empty() and host is None:
                    p.hide()
                    continue
                p.sync()
            self._watch_widgets()
            self._tick(not self.board.empty())
        except Exception as e:  # noqa: BLE001
            _log("overlay: refresh failed", e)

    def _painter(self, widget, host):
        p = self._painters.get(host)
        if p is not None and alive(p):
            return p
        cls = _painter_class()
        if cls is None:
            return None
        p = cls(widget, self, host)
        self._painters[host] = p
        return p

    def _watch_widgets(self):
        cls = _watcher_class()
        if cls is None:
            return
        if self._watch is None:
            self._watch = cls(self)
        want = {id(m.widget): m.widget for m in self.board.marks if m.widget is not None}
        mw = self.window()
        if mw is not None:
            want[id(mw)] = mw
        self._watch.follow(want)

    def _tick(self, on):
        try:
            from PySide import QtCore

            if self._timer is None:
                self._timer = QtCore.QTimer(timer_owner())  # ours, never a ringed widget's
                self._timer.setInterval(TICK_MS)
                self._timer.timeout.connect(self._refresh)
            if on and not self._timer.isActive():
                self._timer.start()
            elif not on and self._timer.isActive():
                self._timer.stop()
        except Exception:
            pass


def _is_menu(w):
    try:
        _QtCore, _QtGui, QtW = _qt()
        return isinstance(w, QtW.QMenu)
    except Exception:
        return type(w).__name__ == "QMenu"


def _inside(a, b):
    """a lies wholly in b."""
    return a[0] >= b[0] and a[1] >= b[1] and a[0] + a[2] <= b[0] + b[2] and a[1] + a[3] <= b[1] + b[3]


def _point(x, y):
    try:
        from PySide import QtCore

        return QtCore.QPoint(x, y)
    except Exception:  # no Qt (tests): a stand-in's mapTo takes a pair
        return (x, y)


def _xy(p):
    return (p.x(), p.y()) if hasattr(p, "x") and callable(p.x) else (int(p[0]), int(p[1]))


def _rect(q):
    """(x, y, w, h) of a QRect, or None."""
    if q is None:
        return None
    if isinstance(q, tuple):
        return q
    return (q.x(), q.y(), q.width(), q.height())


def _log(what, e):
    sys.stderr.write(f"Agent Link: {what} ({type(e).__name__}: {e})\n")
    try:
        import FreeCAD

        FreeCAD.Console.PrintLog(f"Agent Link: {what} ({type(e).__name__}: {e})\n")
    except Exception:
        pass


_SERVICE = None


# ---- Qt objects that may be gone, and timers that outlive nothing ---------------
#
# A ringed toolbar button dies when the workbench changes, a caption's 3D
# view when its document closes, a menu when its bench goes. A timer whose
# receiver died, or a callback that touches a widget C++ already deleted,
# crashed FreeCAD (SIGBUS in QTimerInfoList::activateTimers, inside an
# updateGui() of window_snapshot). So: every check goes through alive(),
# every deferred call through later(): its QTimer is owned by one long-lived
# QObject of ours (never the target), stopped when the target is destroyed,
# and its callback runs only when the target is still alive.

_SHIBOKEN = []


def _shiboken():
    if not _SHIBOKEN:
        mod = None
        for name in ("shiboken6", "shiboken2"):
            try:
                mod = __import__(name)
                break
            except Exception:  # noqa: BLE001
                continue
        _SHIBOKEN.append(mod)
    return _SHIBOKEN[0]


PARENTS_MOST = 64


def alive(obj, valid=None):
    """Whether a Qt object can be touched: its C++ object is there (shiboken's
    isValid), and so is every parent up its chain. None is not alive. A
    non-Qt stand-in counts as alive. valid: the check for one object (tests).
    Never raises."""
    if obj is None:
        return False
    if valid is None:
        sh = _shiboken()

        def valid(o):
            if sh is None:
                return True
            try:
                return bool(sh.isValid(o))
            except Exception:  # noqa: BLE001  (not a Qt object)
                return True
    try:
        o = obj
        for _ in range(PARENTS_MOST):
            if not valid(o):
                return False
            fn = getattr(o, "parent", None)
            if not callable(fn):
                return True
            o = fn()
            if o is None:
                return True
        return True
    except RuntimeError:  # "Internal C++ object already deleted"
        return False
    except Exception:  # noqa: BLE001
        return False


class Later:
    """Deferred calls: later(ms, fn, target). Each is a single-shot QTimer
    owned by this object's own QObject (made once, parented to nothing that
    goes away), stopped when target is destroyed, and fn runs only while
    target is alive(). Plain enough to drive with stand-ins: qt is
    (QtCore,) or None (made on first use)."""

    def __init__(self, qt=None):
        self._qt = qt
        self._owner = None
        self.pending = {}  # id -> (timer, target, connection)
        self._n = 0

    def owner(self):
        if self._owner is None or not alive(self._owner):
            QtCore = self._qt[0] if self._qt else _qt()[0]
            self._owner = QtCore.QObject()
            self._owner.setObjectName("AgentLinkTimers")
        return self._owner

    def later(self, ms, fn, target=None):
        """fn() after ms, unless target (a Qt object) is gone by then. The
        handle, or None (no Qt). Never raises."""
        try:
            QtCore = self._qt[0] if self._qt else _qt()[0]
            t = QtCore.QTimer(self.owner())
            t.setSingleShot(True)
            self._n += 1
            key = self._n
            conn = None
            if target is not None:
                try:
                    conn = target.destroyed.connect(lambda *_a, k=key: self.cancel(k))
                except Exception:  # noqa: BLE001  (not a QObject: checked with alive() at the time)
                    conn = None
            self.pending[key] = (t, target, conn)
            t.timeout.connect(lambda k=key: self._fire(k, fn))
            t.start(max(0, int(ms)))
            return key
        except Exception as e:  # noqa: BLE001
            _log("overlay: a deferred call was not set", e)
            return None

    def _drop(self, key):
        t, target, conn = self.pending.pop(key, (None, None, None))
        if conn is not None and target is not None and alive(target):
            try:
                target.destroyed.disconnect(conn)
            except Exception:  # noqa: BLE001
                pass
        if t is not None and alive(t):
            try:
                t.stop()
                t.deleteLater()
            except Exception:  # noqa: BLE001
                pass
        return t

    def cancel(self, key):
        """A pending call dropped (its target was destroyed)."""
        self._drop(key)

    def _fire(self, key, fn):
        if key not in self.pending:
            return
        _t, target, _c = self.pending[key]
        self._drop(key)
        if target is not None and not alive(target):
            return
        try:
            fn()
        except RuntimeError:  # gone in the meantime
            pass
        except Exception as e:  # noqa: BLE001
            _log("overlay: a deferred call failed", e)


_LATER = []


def later(ms, fn, target=None):
    """The one Later of this FreeCAD: fn() after ms while target lives."""
    if not _LATER:
        _LATER.append(Later())
    return _LATER[0].later(ms, fn, target)


def timer_owner():
    """The long-lived QObject our own timers belong to."""
    if not _LATER:
        _LATER.append(Later())
    return _LATER[0].owner()


def service():
    """The one overlay of this FreeCAD (what hooks.service("overlay") gives)."""
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = Overlay()
    return _SERVICE


# ---- the Qt classes, made on first use --------------------------------------

_CLASSES = {}


def _qt():
    from PySide import QtCore, QtGui

    QtW = getattr(__import__("PySide", fromlist=["QtWidgets"]), "QtWidgets", QtGui)
    return QtCore, QtGui, QtW


def _flag(QtCore, name):
    """A Qt enum by its short name, in PySide2 and PySide6 alike."""
    q = QtCore.Qt
    v = getattr(q, name, None)
    if v is not None:
        return v
    for group in ("WidgetAttribute", "FocusPolicy", "RenderHint", "AlignmentFlag", "TextFlag", "PenStyle", "BrushStyle", "GlobalColor"):
        g = getattr(q, group, None)
        if g is not None and hasattr(g, name):
            return getattr(g, name)
    return None


def _painter_class():
    if "painter" in _CLASSES:
        return _CLASSES["painter"]
    try:
        QtCore, QtGui, QtW = _qt()
    except Exception:
        _CLASSES["painter"] = None
        return None

    class Painter(QtW.QWidget):
        """The transparent layer on one host (the main window, or an open menu)."""

        def __init__(self, parent, ov, host):
            super().__init__(parent)
            self.ov, self.host = ov, host
            self.setObjectName("AgentLinkOverlay")
            for a in ("WA_TransparentForMouseEvents", "WA_NoSystemBackground", "WA_TranslucentBackground", "WA_ShowWithoutActivating"):
                f = _flag(QtCore, a)
                if f is not None:
                    self.setAttribute(f, True)
            nf = _flag(QtCore, "NoFocus")
            if nf is not None:
                self.setFocusPolicy(nf)
            self.setGeometry(parent.rect())

        def sync(self):
            if not alive(self):
                return
            par = self.parentWidget()
            moved = False
            if par is not None and self.geometry() != par.rect():
                self.setGeometry(par.rect())
                moved = True
            if not self.isVisible():
                self.show()
                moved = True
            try:
                kids = [k for k in par.children() if hasattr(k, "isWidgetType") and k.isWidgetType()] if par is not None else []
                on_top = bool(kids) and kids[-1] is self
            except Exception:  # noqa: BLE001
                on_top = False
            if not on_top:
                self.raise_()  # above the docks, inside its own window only
                moved = True
            # Painted again only when what it draws moved or changed: this
            # layer covers the whole window, and each repaint of it repaints
            # the window under it — four times a second for as long as a
            # ring stayed lit, the 3D view's scene included.
            sig = paint_key(self.ov.board, self.host, self.ov._map)
            if moved or sig != getattr(self, "_sig", None):
                self._sig = sig
                self.update()

        def paintEvent(self, _ev):
            try:
                self._paint()
            except Exception as e:  # noqa: BLE001
                _log("overlay: paint failed", e)

        def _paint(self):
            ov = self.ov
            area = (0, 0, self.width(), self.height())
            items, calls, _hidden = ov.board.scene(self.host, ov._map, area)
            if not items and not calls:
                return
            col = ov.colours()
            p = QtGui.QPainter(self)
            aa = getattr(QtGui.QPainter, "Antialiasing", None) or QtGui.QPainter.RenderHint.Antialiasing
            p.setRenderHint(aa, True)
            accent, halo_c = QtGui.QColor(col["accent"]), QtGui.QColor(col["halo"])
            nobrush = _flag(QtCore, "NoBrush")
            centre = int(_flag(QtCore, "AlignCenter"))
            for r, badge, style in items:
                x, y, w, h = grow(r, PAD)
                if style == "flash":
                    fill = QtGui.QColor(accent)
                    fill.setAlpha(FLASH_ALPHA)
                    p.fillRect(QtCore.QRect(x, y, w, h), fill)
                p.setBrush(QtGui.QBrush(nobrush) if nobrush is not None else QtGui.QBrush())
                p.setPen(QtGui.QPen(halo_c, RING + 2 * HALO))
                p.drawRoundedRect(QtCore.QRect(x, y, w, h), 5, 5)
                p.setPen(QtGui.QPen(accent, RING))
                p.drawRoundedRect(QtCore.QRect(x, y, w, h), 5, 5)
                if badge is not None:
                    bx, by, bw, bh = badge_at(r, area)
                    p.setPen(QtGui.QPen(halo_c, HALO))
                    p.setBrush(QtGui.QBrush(accent))
                    p.drawEllipse(QtCore.QRect(bx, by, bw, bh))
                    p.setPen(QtGui.QColor(ink(col["accent"])))
                    f = QtGui.QFont(self.font())
                    f.setBold(True)
                    f.setPixelSize(11)
                    p.setFont(f)
                    p.drawText(QtCore.QRect(bx, by, bw, bh), centre, str(badge))
            self._items = items
            for target, text in calls:
                self._callout(p, target, text, area, col)
            p.end()

        def _callout(self, p, target, text, area, col):
            f = QtGui.QFont(QtW.QApplication.font())
            px = f.pixelSize() if f.pixelSize() > 0 else int(round(f.pointSizeF() * 96 / 72.0)) if f.pointSizeF() > 0 else FONT_MIN
            f.setPixelSize(max(FONT_MIN, px))
            p.setFont(f)
            fm = QtGui.QFontMetrics(f)
            wrap = int(_flag(QtCore, "TextWordWrap"))
            br = fm.boundingRect(QtCore.QRect(0, 0, WRAP, 4000), wrap, text)
            size = (min(WRAP, br.width()) + 2 * BUBBLE_PAD, br.height() + 2 * BUBBLE_PAD)

            def measure(w):
                inner = max(20, w - 2 * BUBBLE_PAD)
                return fm.boundingRect(QtCore.QRect(0, 0, inner, 4000), wrap, text).height() + 2 * BUBBLE_PAD

            hard, soft = self.ov.no_go(self.host) if self.host is None else ([], [])
            soft = soft + [grow(r, PAD + RING) for r, _b, _s in getattr(self, "_items", [])]
            x, y, w, h, _side = place_callout(target, size, area, forbid=hard, soft=soft, measure=measure)
            p.setPen(QtGui.QPen(QtGui.QColor(col["accent"]), 2))
            p.setBrush(QtGui.QBrush(QtGui.QColor(col["bubble"])))
            p.drawRoundedRect(QtCore.QRect(x, y, w, h), 6, 6)
            p.setPen(QtGui.QColor(col["bubble_text"]))
            p.drawText(QtCore.QRect(x + BUBBLE_PAD, y + BUBBLE_PAD, w - 2 * BUBBLE_PAD, h - 2 * BUBBLE_PAD), wrap, text)

    _CLASSES["painter"] = Painter
    return Painter


def _watcher_class():
    if "watcher" in _CLASSES:
        return _CLASSES["watcher"]
    try:
        QtCore, _QtGui, _QtW = _qt()
    except Exception:
        _CLASSES["watcher"] = None
        return None
    E = QtCore.QEvent
    kinds = {getattr(E, n, None) or getattr(getattr(E, "Type", E), n, None) for n in ("Move", "Resize", "Show", "Hide")}

    class Watcher(QtCore.QObject):
        """Move, Resize, Show and Hide of a ringed widget (or the window)
        repaint the overlay."""

        def __init__(self, ov):
            super().__init__()
            self.ov = ov
            self.on = {}

        def follow(self, widgets):
            for k in list(self.on):
                w = self.on[k]
                if not alive(w):
                    # Destroyed: Qt took its filters with it; never touched
                    # (an id can be used again by a new widget).
                    self.on.pop(k)
                elif k not in widgets or widgets[k] is not w:
                    self.on.pop(k)
                    try:
                        w.removeEventFilter(self)
                    except RuntimeError:
                        pass
            for k, w in widgets.items():
                if not alive(w):
                    continue
                if k not in self.on:
                    try:
                        w.installEventFilter(self)
                        self.on[k] = w
                    except RuntimeError:
                        pass

        def eventFilter(self, obj, ev):
            try:
                if ev.type() in kinds:
                    for p in list(self.ov._painters.values()):
                        if not alive(p):
                            continue
                        try:
                            p.sync()
                        except RuntimeError:
                            pass
            except Exception:
                pass
            return False

    _CLASSES["watcher"] = Watcher
    return Watcher
