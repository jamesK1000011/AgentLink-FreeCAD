# SPDX-License-Identifier: LGPL-2.1-or-later
"""Window events for add-ons, on only while one watches
(hooks.watch_window): through hooks.emit,

    workbench_activated(name, by)   the main window's workbenchActivated
    command_used(name, by)          a command's QAction triggered (a toolbar
                                    button, a menu item, a shortcut)

by is "agent" while one of the agent's calls runs (hooks.agent_acting()),
else "person". An add-on needs no GUI internals for them. Read only: no
widget, action or setting is changed; QActions made by a later workbench
switch are joined as it happens. Everything runs on the GUI thread.
"""
import sys

_STATE = {"on": False, "mw": None, "bench": None, "acts": {}}


def _qt():
    from PySide import QtCore, QtGui

    QtW = getattr(__import__("PySide", fromlist=["QtWidgets"]), "QtWidgets", QtGui)
    return QtCore, QtGui, QtW


def by():
    from . import hooks

    return hooks.AGENT if hooks.agent_acting() else hooks.PERSON


def _emit(event, name):
    from . import hooks

    hooks.emit(event, name, by())


def name_of(act):
    """The command an action runs (objectName, else FreeCAD's CommandName)."""
    try:
        from .targets import command_name

        return command_name(act)
    except Exception:  # noqa: BLE001
        return ""


def join_actions(acts, connect):
    """Connect each action not joined yet: connect(act, name) -> its slot.
    Gone ones are forgotten. Plain: acts any objects with objectName()."""
    have = _STATE["acts"]
    for k in [k for k, (a, _n, _s) in have.items() if not _alive(a)]:
        have.pop(k, None)
    n = 0
    for a in acts:
        key = id(a)
        if key in have:
            continue
        name = name_of(a)
        if not name:
            continue
        try:
            slot = connect(a, name)
        except Exception:  # noqa: BLE001
            continue
        have[key] = (a, name, slot)
        n += 1
    return n


def _alive(a):
    try:
        a.objectName()
        return True
    except RuntimeError:
        return False


def _actions(mw):
    _QtCore, QtGui, QtW = _qt()
    QAction = QtW.QAction if hasattr(QtW, "QAction") else QtGui.QAction
    return mw.findChildren(QAction)


def _connect(a, name):
    def slot(*_x, n=name):
        _emit("command_used", n)

    a.triggered.connect(slot)
    return slot


def _bench(name=None):
    _emit("workbench_activated", str(name or ""))
    try:  # the new bench's toolbars and menus: their actions joined too
        join_actions(_actions(_STATE["mw"]), _connect)
    except Exception:  # noqa: BLE001
        pass


def attach():
    """Start (idempotent). False where there is no window."""
    if _STATE["on"]:
        return True
    try:
        import FreeCAD
        import FreeCADGui

        if not FreeCAD.GuiUp:
            return False
        mw = FreeCADGui.getMainWindow()
    except Exception:  # noqa: BLE001
        return False
    _STATE["mw"] = mw
    try:
        mw.workbenchActivated.connect(_bench)
        _STATE["bench"] = _bench
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"Agent Link: no workbench events ({e})\n")
    try:
        join_actions(_actions(mw), _connect)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"Agent Link: no command events ({e})\n")
    _STATE["on"] = True
    return True


def detach():
    """Stop: the workbench slot off and every action's slot off."""
    if not _STATE["on"]:
        return
    mw = _STATE["mw"]
    try:
        if _STATE["bench"] is not None:
            mw.workbenchActivated.disconnect(_STATE["bench"])
    except Exception:  # noqa: BLE001
        pass
    for a, _n, slot in list(_STATE["acts"].values()):
        try:
            a.triggered.disconnect(slot)  # ours only: FreeCAD's own slot stays
        except Exception:  # noqa: BLE001  (gone)
            pass
    _STATE.update(on=False, mw=None, bench=None, acts={})
