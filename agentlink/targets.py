# SPDX-License-Identifier: LGPL-2.1-or-later
"""Finding the window's controls a tool or a command stands for, for the
live echo and for any add-on that points at them (public, API 1):

    command_for(tool, args)      the FreeCAD command whose button does what a
                                 call does (echo's table and what add-ons
                                 declared), or None
    actions(cmd, mw=None)        the QActions named cmd (objectName), as
                                 flash_command finds them
    buttons(cmd, mw=None)        the QToolButtons that run cmd
    menus_of(cmd, mw=None)       the QMenus that hold cmd's item
    menu_path(titles, mw=None)   a menubar path by its titles (& and … left
                                 out, case ignored): {bar, chain: [(menu,
                                 action)], path, missing}
    native_menubar(mw=None)      True when the menubar is the system's
                                 (macOS): nothing can be drawn over it
    workbench_of(cmd)            the workbench a command's toolbar belongs
                                 to, from its prefix ("PartDesign_Pad" ->
                                 "PartDesignWorkbench"), or None

Nothing here clicks, opens a menu or takes focus: it only finds.
"""

import sys

# A command's prefix -> the workbench whose toolbars carry it (Std_ and the
# like are in every workbench: None).
BENCH_OF = {
    "PartDesign_": "PartDesignWorkbench", "Sketcher_": "SketcherWorkbench", "Part_": "PartWorkbench",
    "TechDraw_": "TechDrawWorkbench", "Draft_": "DraftWorkbench", "BIM_": "BIMWorkbench", "Arch_": "BIMWorkbench",
    "FEM_": "FemWorkbench", "Assembly_": "AssemblyWorkbench", "CAM_": "CAMWorkbench", "Mesh_": "MeshWorkbench",
    "MeshPart_": "MeshWorkbench", "Spreadsheet_": "SpreadsheetWorkbench", "Surface_": "SurfaceWorkbench",
    "Points_": "PointsWorkbench", "Robot_": "RobotWorkbench", "OpenSCAD_": "OpenSCADWorkbench",
    "Inspection_": "InspectionWorkbench", "Material_": "MaterialWorkbench", "Measure_": None, "Std_": None,
}


def command_for(name, args=None):
    from . import echo

    return echo.command_for(name, args or {})


def workbench_of(cmd):
    best, got = -1, None
    for k, v in BENCH_OF.items():
        if cmd.startswith(k) and len(k) > best:
            best, got = len(k), v
    return got


def norm(text):
    """A menu title as compared: no &, no trailing … or ..., spaces folded,
    case ignored."""
    t = str(text or "").replace("&&", "\0").replace("&", "").replace("\0", "&")
    t = t.split("\t")[0].strip().rstrip(".…").strip()
    return " ".join(t.split()).casefold()


def _qt():
    from PySide import QtCore, QtGui

    QtW = getattr(__import__("PySide", fromlist=["QtWidgets"]), "QtWidgets", QtGui)
    return QtCore, QtGui, QtW


def _mw(mw=None):
    if mw is not None:
        return mw
    import FreeCADGui

    return FreeCADGui.getMainWindow()


def _qaction(QtGui, QtW):
    return QtW.QAction if hasattr(QtW, "QAction") else QtGui.QAction


def actions(cmd, mw=None):
    """Every QAction of the window named cmd (a command's objectName)."""
    _QtCore, QtGui, QtW = _qt()
    QAction = _qaction(QtGui, QtW)
    return [a for a in _mw(mw).findChildren(QAction) if a.objectName() == cmd]


def associated(act):
    """The widgets an action shows in (its buttons, its menus)."""
    try:
        return list(act.associatedWidgets() if hasattr(act, "associatedWidgets") else act.associatedObjects())
    except RuntimeError:
        return []


def buttons(cmd, mw=None):
    _QtCore, _QtGui, QtW = _qt()
    out = []
    for a in actions(cmd, mw):
        for w in associated(a):
            if isinstance(w, QtW.QToolButton) and w not in out:
                out.append(w)
    return out


def menus_of(cmd, mw=None):
    _QtCore, _QtGui, QtW = _qt()
    out = []
    for a in actions(cmd, mw):
        for w in associated(a):
            if isinstance(w, QtW.QMenu) and w not in out:
                out.append(w)
    return out


def native_menubar(mw=None):
    try:
        bar = _mw(mw).menuBar()
        return bool(bar.isNativeMenuBar()) and sys.platform == "darwin"
    except Exception:
        return False


def find_titled(acts, title):
    """The action among acts whose text is title (norm()), or None."""
    want = norm(title)
    for a in acts:
        try:
            if not a.isSeparator() and norm(a.text()) == want:
                return a
        except RuntimeError:
            continue
    return None


def walk(bar_actions, titles):
    """(chain, missing): chain [(the menu the action is in, action)] down
    titles from the menubar's actions (the first's menu None: the bar); missing, the first title not found
    (or None). Plain: works on anything with text(), isSeparator() and
    menu()/actions()."""
    chain, acts, menu = [], list(bar_actions), None
    for t in titles:
        a = find_titled(acts, t)
        if a is None:
            return chain, t
        chain.append((menu, a))
        menu = a.menu() if hasattr(a, "menu") else None
        acts = list(menu.actions()) if menu is not None else []
    return chain, None


def menu_path(titles, mw=None):
    titles = [str(t) for t in (titles or [])]
    bar = _mw(mw).menuBar()
    chain, missing = walk(bar.actions(), titles)
    return {"bar": bar, "chain": chain, "path": " › ".join(titles), "missing": missing}
