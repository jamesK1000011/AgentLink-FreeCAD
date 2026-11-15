# SPDX-License-Identifier: LGPL-2.1-or-later
# Helpers for the Agent Link panel's widgets (a quiet colour, a row that
# wraps), and filling a tab as it comes up: an add-on's tab
# (hooks.register_tab) fills through its widget's own fill().

try:
    from PySide import QtCore, QtGui

    QtWidgets = QtGui
    try:
        from PySide import QtWidgets  # noqa: F811  (Qt 6 builds)
    except ImportError:
        pass
except ImportError:  # pragma: no cover
    QtCore = QtGui = QtWidgets = None


def muted(widget):
    """A quiet colour that still reads in light and dark themes: the text
    colour blended two thirds of the way towards the background (palette's
    mid is near the background in some dark themes)."""
    pal = widget.palette()
    t, b = pal.color(QtGui.QPalette.WindowText), pal.color(QtGui.QPalette.Window)
    mix = [int(t.red() * 0.6 + b.red() * 0.4), int(t.green() * 0.6 + b.green() * 0.4), int(t.blue() * 0.6 + b.blue() * 0.4)]
    return "#%02x%02x%02x" % tuple(mix)


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
