# SPDX-License-Identifier: LGPL-2.1-or-later
# The agent's work, shown as it happens in the FreeCAD window — as the
# ScanRuler fork shows it in the browser: for each call the workbench it
# belongs to comes up, the toolbar button that does the same job lights,
# what it works on is selected, a caption on the 3D view says what is being
# done, and afterwards what it made is selected and the body made active.
# Every call goes into an activity list (the Agent Link panel's Activity
# tab). Paced so the person can follow (Mod/AgentLink EchoDelay, ms;
# Echo off for none), and never in the way of the result: a failure here is
# logged, the call goes on.

import datetime
import time

try:
    import FreeCAD
except ImportError:  # the tables below are read without FreeCAD (tests)
    FreeCAD = None

PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"

# Tool families → the workbench a person would be in.
WORKBENCH = [
    ("pd_", "PartDesignWorkbench"), ("sketch_", "SketcherWorkbench"), ("feature_", "PartDesignWorkbench"),
    ("part_", "PartWorkbench"), ("bim_", "BIMWorkbench"), ("ifc_", "BIMWorkbench"), ("fea_", "FemWorkbench"),
    ("td_", "TechDrawWorkbench"), ("draft_", "DraftWorkbench"),
    ("asm_", "AssemblyWorkbench"), ("cam_", "CAMWorkbench"), ("meshobj_", "MeshWorkbench"),
    ("sheet_", "SpreadsheetWorkbench"), ("insp_", "InspectionWorkbench"), ("points_", "PointsWorkbench"),
    ("surface_", "SurfaceWorkbench"), ("robot_", "RobotWorkbench"), ("scad_", "OpenSCADWorkbench"),
    ("material_", "MaterialWorkbench"),
]
# Tools that work on a drawing page: the page opens in its tab and the 3D
# view is not reframed after them.
PAGES = ["td_"]

# Tools → the FreeCAD command whose button does the same job.
COMMAND = {
    "pd_body_new": "PartDesign_Body", "sketch_new": "PartDesign_NewSketch", "pd_pad": "PartDesign_Pad",
    "pd_pocket": "PartDesign_Pocket", "pd_revolution": "PartDesign_Revolution", "pd_groove": "PartDesign_Groove",
    "pd_hole": "PartDesign_Hole", "pd_fillet": "PartDesign_Fillet", "pd_chamfer": "PartDesign_Chamfer",
    "pd_draft": "PartDesign_Draft", "pd_thickness": "PartDesign_Thickness", "pd_mirrored": "PartDesign_Mirrored",
    "pd_linear_pattern": "PartDesign_LinearPattern", "pd_polar_pattern": "PartDesign_PolarPattern",
    "pd_multitransform": "PartDesign_MultiTransform", "pd_loft": "PartDesign_AdditiveLoft", "pd_pipe": "PartDesign_AdditivePipe",
    "pd_helix": "PartDesign_AdditiveHelix", "pd_boolean": "PartDesign_Boolean", "pd_datum_plane": "PartDesign_Plane",
    "pd_binder": "PartDesign_ShapeBinder", "pd_primitive": "PartDesign_CompPrimitiveAdditive",
    "part_primitive": "Part_Primitives", "part_boolean": "Part_Boolean", "part_fillet": "Part_Fillet",
    "part_chamfer": "Part_Chamfer", "part_extrude": "Part_Extrude", "part_revolve": "Part_Revolve",
    "part_loft": "Part_Loft", "part_sweep": "Part_Sweep", "part_offset": "Part_Offset", "part_thickness": "Part_Thickness",
    "part_section": "Part_Section", "part_mirror": "Part_Mirror", "part_compound": "Part_Compound",
    # BIM's makers kept their Arch_ command names (FreeCAD 1.1: src/Mod/BIM/bimcommands).
    "bim_wall": "Arch_Wall", "bim_structure": "Arch_Structure", "bim_roof": "Arch_Roof", "bim_stairs": "Arch_Stairs",
    "bim_opening": "Arch_Window", "bim_space": "Arch_Space", "bim_level": "Arch_Level",
    "fea_setup": "FEM_Analysis", "fea_hold": "FEM_ConstraintFixed", "fea_load": "FEM_ConstraintForce",
    "fea_solve": "FEM_SolverRun", "fea_native": "FEM_Analysis",
    "td_page": "TechDraw_PageDefault", "td_view": "TechDraw_View", "td_projection": "TechDraw_ProjectionGroup",
    "td_section": "TechDraw_SectionView", "td_detail": "TechDraw_DetailView", "td_dim": "TechDraw_LengthDimension",
    "draft_text": "Draft_Text", "draft_array": "Draft_OrthoArray", "draft_clone": "Draft_Clone",
    "draft_dimension": "Draft_Dimension", "draft_label": "Draft_Label",
    "asm_new": "Assembly_CreateAssembly", "asm_add": "Assembly_InsertLink", "asm_joint": "Assembly_CreateJointFixed",
    "asm_explode": "Assembly_CreateView", "asm_bom": "Assembly_CreateBom",
    "cam_job": "CAM_Job", "cam_post": "CAM_Post", "cam_sim": "CAM_SimulatorGL",
    "measure": "Std_Measure", "section": "Part_Section", "doc_save": "Std_Save", "export_file": "Std_Export", "export": "Std_Export",
    "history_undo": "Std_Undo", "history_redo": "Std_Redo", "recompute": "Std_Refresh",
}

COMMAND.update({
    "asm_ground": "Assembly_ToggleGrounded", "asm_sub": "Assembly_InsertLink", "asm_motion": "Assembly_CreateJointRevolute",
    "bim_building": "Arch_Building", "bim_section": "Arch_SectionPlane", "bim_grid": "Arch_AxisSystem", "bim_member": "BIM_Beam",
    "bim_frame": "Arch_Frame", "bim_equipment": "Arch_Equipment", "bim_panel": "Arch_Panel", "bim_rebar": "Arch_Rebar",
    "bim_truss": "Arch_Truss", "bim_curtain_wall": "Arch_CurtainWall", "bim_fence": "Arch_Fence", "bim_pipe": "Arch_Pipe",
    # bim_covering: FreeCAD 1.1 has no covering command.
    "bim_schedule": "Arch_Schedule", "bim_material": "BIM_Material",
    "cam_tool": "CAM_ToolController", "cam_tool_add": "CAM_ToolBitDock", "cam_setup": "CAM_Job",
})

# Tools whose button depends on what kind was asked for.
CAM_OP = {"profile": "CAM_Profile", "pocket": "CAM_Pocket_Shape", "adaptive": "CAM_Adaptive", "face": "CAM_MillFace",
          "drill": "CAM_Drilling", "engrave": "CAM_Engrave", "helix": "CAM_Helix", "slot": "CAM_Slot", "deburr": "CAM_Deburr",
          "vcarve": "CAM_Vcarve", "thread": "CAM_ThreadMilling", "surface": "CAM_Surface", "waterline": "CAM_Waterline"}
CAM_DRESSUP = {"dogbone": "CAM_DressupDogbone", "tag": "CAM_DressupTag", "tags": "CAM_DressupTag", "ramp": "CAM_DressupRampEntry",
               "boundary": "CAM_DressupPathBoundary", "leadinout": "CAM_DressupLeadInOut", "axismap": "CAM_DressupAxisMap", "zcorrect": "CAM_DressupZCorrect"}


def command_for(name, args):
    """The command whose button does what this call does."""
    # An add-on's NO_BUTTON (exact name or prefix): no button, whatever matches.
    if _longest(name, ((k, True) for k in NO_BUTTON)):
        return None
    kind = str((args or {}).get("kind") or "").lower().replace("-", "").replace("_", "")
    if name == "asm_joint" and kind:
        return "Assembly_CreateJoint" + {"rackpinion": "RackPinion", "slider": "Slider", "ball": "Ball"}.get(kind, kind.capitalize())
    if name == "cam_op" and kind in CAM_OP:
        return CAM_OP[kind]
    if name == "cam_dressup" and kind in CAM_DRESSUP:
        return CAM_DRESSUP[kind]
    if name in COMMAND:
        return COMMAND[name]
    # What add-ons declared (declare()): their own callables first, then
    # COMMANDS by exact name or longest prefix.
    for fn in list(COMMAND_FNS):
        try:
            got = fn(name, args or {})
        except Exception:
            got = None
        if isinstance(got, str) and got:
            return got
    return _longest(name, COMMANDS.items())


# Add-ons' own buttons, declared on their family modules (declare()):
# {tool or prefix: command}, and command_for(name, args) callables.
COMMANDS = {}
COMMAND_FNS = []
# Tools (names or prefixes) whose calls light no button, even where a
# COMMANDS prefix would match them.
NO_BUTTON = set()


def _longest(name, pairs):
    """The value of the longest key that is name or a prefix of it."""
    best, got = -1, None
    for k, v in pairs:
        if isinstance(k, str) and name.startswith(k) and len(k) > best:
            best, got = len(k), v
    return got


# Tools never shown as they run (no bench, button, caption or selection;
# still listed in Activity): the server's own, and what add-ons declare as
# NO_ECHO (names or prefixes), such as tools that draw in the window
# themselves.
SKIP = {"batch", "session_state", "tool_groups", "guide_read"}
NO_ECHO = set()


def skipped(name):
    """Whether a call of this tool is left out of the echo."""
    return name in SKIP or bool(_longest(name, ((k, True) for k in NO_ECHO)))


# Read-only tools that still show something (a view, a picture).
SHOWN = ("view_", "measure", "clearance", "section", "body_check", "steps_render", "note_")
# Read-only tools that open a panel or dialog all the same, and so bring up
# their workbench (add-ons declare theirs as OPENS). Every other read leaves
# the bench as the person has it.
OPENS = ()


def switches_bench(tool):
    """Whether a call brings up its workbench: one that changes the document
    (its tool's changes flag, after for_call, so a changing tool's read
    action counts as a read) or opens a panel; a read never does."""
    if tool is None:
        return False
    return bool(getattr(tool, "changes", False)) or bool(OPENS) and tool.name.startswith(OPENS)

# What a tool's arguments and answer name: the objects to select.
ARG_KEYS = ("body", "sketch", "object", "base", "target", "feature", "page", "op", "joint")
OUT_KEYS = ("feature", "sketch", "object", "body", "created", "page", "view", "joint", "op", "sub")

_log = []
_listeners = []
LOG_MAX = 200


def enabled():
    return FreeCAD.GuiUp and FreeCAD.ParamGet(PREFS).GetBool("Echo", True)


def delay_ms():
    return FreeCAD.ParamGet(PREFS).GetInt("EchoDelay", 350)


# A batch in the window: its first calls are shown at the full pace, so the
# person sees what kind of run it is; from the fourth changing call on the
# pause before each call is short and the paints that only let the window
# settle are skipped (the bench still comes up, the button lights, the
# result is selected); the batch's last call is shown at the full pace
# again, so the window ends on a state that can be read. Measured live, a
# changing call cost 0.35 to 2.5 s of echo, a 20-call batch 6 to 67 s.
BATCH_FULL = 3         # changing calls of a batch shown at the full pace
BATCH_DELAY_MS = 60    # the pause from then on (EchoBatchDelay)


def batch_delay_ms():
    """Mod/AgentLink EchoBatchDelay, ms: the pause before a batch's later
    calls. 0: no wait. -1: the same as EchoDelay (a batch is then paced as
    single calls are)."""
    return FreeCAD.ParamGet(PREFS).GetInt("EchoBatchDelay", BATCH_DELAY_MS)


def pace(batch, changing, full_ms, batch_ms, count=True):
    """How one call is shown: (mode, ms) — mode "full" (the pause full_ms
    and every settle paint) or "short" (the pause ms, no settle paints).
    batch: the session's batch_now ({ i, n, lastChange, … }; None for a
    call on its own); changing: whether this call changes the document
    (only those count towards BATCH_FULL; a read shown after them is short
    too); batch_ms: EchoBatchDelay. count: note this call in the batch
    (its "echoed": changing calls shown so far). Plain Python."""
    full_ms = max(0, int(full_ms or 0))
    if not isinstance(batch, dict):
        return "full", full_ms
    try:
        batch_ms = int(batch_ms)
    except (TypeError, ValueError):
        batch_ms = BATCH_DELAY_MS
    seen = int(batch.get("echoed") or 0)
    if changing and count:
        batch["echoed"] = seen + 1
    if batch_ms < 0:  # the same as EchoDelay
        return "full", full_ms
    i, n = batch.get("i"), batch.get("n")
    last = batch.get("lastChange")
    if isinstance(i, int) and ((isinstance(n, int) and i >= n - 1) or (isinstance(last, int) and i == last)):
        return "full", full_ms
    if seen < BATCH_FULL:
        return "full", full_ms
    # Never slower than a call on its own.
    return "short", min(batch_ms, full_ms)


def fit_animated(batch, mode):
    """Whether the view fit after a change may run FreeCAD's fit animation.
    A call on its own, and a batch's last shown call at the full pace: yes.
    Any other call of a batch: no — the view jumps to the same framing.

    FreeCAD's fit with animations on (the default) is ten nested event
    loops of 20 ms, each with a full redraw of the scene (FreeCAD 1.1
    source: src/Gui/View3DInventorViewer.cpp, viewAll and animatedViewAll
    (10, 20)): in a document of heavy shapes that was seconds a call,
    outside the call's own ms. Plain Python."""
    if mode != "full":
        return False
    if not isinstance(batch, dict):
        return True
    i, n, last = batch.get("i"), batch.get("n"), batch.get("lastChange")
    return isinstance(i, int) and ((isinstance(n, int) and i >= n - 1) or (isinstance(last, int) and i == last))


def log():
    return list(_log)


def listen(fn):
    _listeners.append(fn)


def _note(entry):
    _log.append(entry)
    del _log[:-LOG_MAX]
    for fn in list(_listeners):
        try:
            fn(entry)
        except Exception:
            pass


def _qt():
    from PySide import QtCore, QtGui

    QtW = getattr(__import__("PySide", fromlist=["QtWidgets"]), "QtWidgets", QtGui)
    return QtCore, QtGui, QtW


def _paint_flags(QtCore):
    f = getattr(QtCore.QEventLoop, "ExcludeUserInputEvents", None)
    if f is None:
        f = QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
    return f


def _paint(ms=0):
    """Let the window paint (and timers run) for ms, without taking the
    person's clicks and keys while a call is in hand (M7): no nested event
    loop that would let input change the document mid-call. The link's own
    timer will not start another call meanwhile (gui_link's in_call)."""
    import time as _t

    QtCore, _QtGui, _QtW = _qt()
    flags = _paint_flags(QtCore)
    end = _t.time() + max(0, ms) / 1000.0
    while True:
        try:
            QtCore.QCoreApplication.processEvents(flags, 30)
        except TypeError:
            QtCore.QCoreApplication.processEvents(flags)
        if _t.time() >= end:
            return
        _t.sleep(0.01)


def _wait(ms):
    """Let the window paint for ms without blocking it."""
    if ms <= 0:
        return
    _paint(ms)


PREFIX_NAME = {"pd": "Part Design", "part": "Part", "sketch": "Sketch", "bim": "BIM", "ifc": "IFC", "fea": "FEM",
               "td": "TechDraw", "draft": "Draft", "asm": "Assembly", "cam": "CAM", "meshobj": "Mesh", "sheet": "Spreadsheet",
               "insp": "Inspection", "points": "Points", "surface": "Surface", "note": "Note", "steps": "Steps", "view": "View",
               "doc": "Document", "object": "Object", "material": "Material",
               # Agent Link's own tools, by the part of FreeCAD they act on.
               "gui": "Window", "window": "Window", "report": "Report", "session": "Session", "dialog": "Dialog",
               "history": "History", "usage": "Usage", "tool": "Tools", "guide": "Guide", "batch": "Batch",
               "crash": "Crash", "queue": "Queue", "addon": "Add-ons", "app": "FreeCAD", "cmd": "Command",
               "menu": "Menu", "body": "Body", "export": "Export", "outputs": "Outputs", "measure": "Measure",
               "fem": "FEM", "scad": "OpenSCAD", "param": "Parameter", "robot": "Robot", "link": "Link"}


def declare(fam):
    """What an add-on's family says of its own tools, so no table here names
    them (read where families load: agentlink/families/__init__.py
    declared()). All optional, on the family module: SHOWN, names or name
    prefixes of read-only tools that still show something; OPENS, those of
    read-only tools that open a panel or dialog (they bring their bench up,
    as changing tools do; other reads never switch it); AREAS, {prefix:
    name} for the Activity list ('slice' gives 'Slice › …'); WORKBENCHES,
    {tool or prefix: workbench} to bring up for its tools (the longest
    match wins, so an add-on's "part_check" can go to another bench than core's
    "part_"); COMMANDS, {tool or prefix: command} whose button lights for
    its tools, or command_for(name, args) -> command or None; NO_BUTTON,
    names or prefixes of its tools that light no button at all; NO_ECHO,
    names or prefixes of its tools never shown as they run (no bench,
    button, caption or selection; still in Activity); PAGES,
    prefixes of its tools that work on a drawing page; PHRASES, {tool or
    prefix: template or templates} of what its calls did, in the Activity
    tab's words (agentlink/activity.py: "Sliced {object}")."""
    global SHOWN, OPENS
    shown = tuple(x for x in (getattr(fam, "SHOWN", ()) or ()) if isinstance(x, str) and x not in SHOWN)
    SHOWN = SHOWN + shown
    opens = tuple(x for x in (getattr(fam, "OPENS", ()) or ()) if isinstance(x, str) and x and x not in OPENS)
    OPENS = OPENS + opens
    for k, v in dict(getattr(fam, "AREAS", None) or {}).items():
        PREFIX_NAME.setdefault(k, v)
    for k, v in dict(getattr(fam, "WORKBENCHES", None) or {}).items():
        if not any(k == p for p, _ in WORKBENCH):
            WORKBENCH.append((k, v))
    for k, v in dict(getattr(fam, "COMMANDS", None) or {}).items():
        if isinstance(k, str) and isinstance(v, str):
            COMMANDS.setdefault(k, v)
    NO_BUTTON.update(k for k in (getattr(fam, "NO_BUTTON", None) or ()) if isinstance(k, str) and k)
    NO_ECHO.update(k for k in (getattr(fam, "NO_ECHO", None) or ()) if isinstance(k, str) and k)
    from . import activity

    activity.declare(fam)
    fn = getattr(fam, "command_for", None)
    if callable(fn) and fn not in COMMAND_FNS:
        COMMAND_FNS.append(fn)
    for k in getattr(fam, "PAGES", ()) or ():
        if isinstance(k, str) and k not in PAGES:
            PAGES.append(k)


def _area(name):
    """(area, what) for a tool's name: the longest declared key that fits
    (a whole name an add-on declares, or a prefix: 'note_', 'gui'), else
    its first word."""
    best = None
    for k in PREFIX_NAME:
        stem = k.rstrip("_")
        if name == stem or name.startswith(stem + "_"):
            if best is None or len(stem) > len(best):
                best = stem
    if best is None:
        head, _, rest = name.partition("_")
        return head.replace("-", " ").title(), rest
    key = best if best in PREFIX_NAME else best + "_"
    rest = name[len(best):].lstrip("_") if name != best else ""
    if not rest and "_" in name:  # a whole name declared: its verb is the last word
        rest = name.partition("_")[2]
    return PREFIX_NAME[key], rest


def did_name(name):
    """A tool's name as the Activity list shows it: 'Area › What', the
    what with a capital, the same way for every tool ('Window › Input',
    'Document › Save')."""
    area, rest = _area(name)
    what = rest.replace("_", " ").strip()
    return f"{area} › {what[:1].upper() + what[1:]}" if what else area


def _describe(name, args):
    """A tool call in words a person reads at a glance, the same as the
    Activity tab says it ("Padded Sketch by 20 mm", "Clicked Pin a Note"):
    agentlink/activity.py, never raw arguments or a folder."""
    from . import activity

    try:
        return activity.did(name, args)
    except Exception:
        return did_name(name)


def _view_widget():
    import FreeCADGui

    QtCore, _QtGui, QtW = _qt()
    mw = FreeCADGui.getMainWindow()
    area = mw.findChild(QtW.QMdiArea)
    # currentSubWindow too: activeSubWindow is None while FreeCAD is not the
    # application in front (the agent works in the background), and the
    # caption then went nowhere.
    sub = (area.activeSubWindow() or area.currentSubWindow()) if area else None
    return sub.widget() if sub else None


_caption = None
CAPTION_MARGIN, CAPTION_MAX, SLIDE_ROOM = 14, 420, 300


def caption_box(view_w, view_h, cap_w, cap_h):
    """(max width, x, y) of the caption in a 3D view this big: bottom right,
    clear of the left edge where the panel slides out (SLIDE_ROOM) and of
    the corners' view cube and axes above it; as wide as fits."""
    m = CAPTION_MARGIN
    most = max(160, min(CAPTION_MAX, view_w - SLIDE_ROOM - 2 * m))
    w = min(cap_w, most)
    x = max(m, view_w - w - m)
    y = max(m, view_h - cap_h - m)
    return most, x, y


def caption(text, ms=2600):
    """A line of text over the 3D view, bottom right, fading after ms."""
    global _caption
    QtCore, _QtGui, QtW = _qt()
    host = _view_widget()
    if host is None:
        return
    if _caption is None or _caption.parent() is not host:
        _caption = QtW.QLabel(host)
        _caption.setStyleSheet("QLabel { background: rgba(20,22,26,200); color: #f2f2f2; border-radius: 6px; padding: 6px 10px; font-size: 13px; }")
        _caption.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
    _caption.setText("✦ Agent: " + text)
    _caption.setWordWrap(True)
    most, _x, _y = caption_box(host.width(), host.height(), host.width(), 0)
    _caption.setMaximumWidth(most)
    _caption.adjustSize()
    _most, x, y = caption_box(host.width(), host.height(), _caption.width(), _caption.height())
    _caption.move(x, y)
    _caption.show()
    _caption.raise_()
    lbl = _caption
    QtCore.QTimer.singleShot(ms, lambda: _hide_later(lbl, text))


def _hide_later(lbl, text):
    """Hide the caption after its moment, unless it shows newer words or is
    gone: closing a document deletes the 3D view and the label with it, and
    the timer then raised "Internal C++ object already deleted" in the
    Report view (as _later guards the lit buttons)."""
    try:
        if lbl.isVisible() and lbl.text().endswith(text):
            lbl.hide()
    except RuntimeError:
        pass


def flash_command(cmd, ms=1300, settle=False):
    """Light the toolbar button and the menu item that run cmd. settle:
    the bench was just switched, so one paint first, for its toolbars and
    menus to exist before their button can light. The button is lit on the
    overlay (agentlink/overlay.py), never by its stylesheet, so a theme's
    rules stay as they are."""
    from . import overlay, targets

    QtCore, QtGui, QtW = _qt()
    if settle:
        _paint()
    lit = []
    painter = overlay.service()
    flashed = False
    for act in targets.actions(cmd):
        for w in targets.associated(act):
            if isinstance(w, QtW.QToolButton):
                flashed = painter.flash(w, ms) or flashed
            elif isinstance(w, QtW.QMenu):
                # The menu item and its menu's title in bold for a moment
                # (no menu is opened: that would take the person's input).
                lit += [act, w.menuAction()]
    if not flashed:
        # Inside a toolbar dropdown (a group command): its button lights.
        try:
            for b, _m, _a in targets.group_buttons(cmd):
                painter.flash(b, ms)
        except Exception:  # noqa: BLE001  (a nicety; the call has run)
            pass
    for a in dict.fromkeys(x for x in lit if x is not None):
        old = QtGui.QFont(a.font())
        f = QtGui.QFont(old)
        f.setBold(True)
        a.setFont(f)
        QtCore.QTimer.singleShot(ms, lambda a=a, old=old: _later(a, "setFont", old))


def _later(obj, method, value):
    """Put a button or menu item back after its moment lit, unless it is gone:
    a workbench switch in the meantime deletes its toolbars' actions, and
    calling into one raised "Internal C++ object already deleted" in the
    Report view (GUI pass on the Mac)."""
    try:
        getattr(obj, method)(value)
    except RuntimeError:
        pass


def fit(animate=True):
    """Frame the part in the 3D view in front — only a live 3D view of an
    open document, and not while a restart is reopening documents (a view
    being made or torn down then crashes FreeCAD in its fit animation).
    animate: False frames it at once: the view's animation is switched off
    for the fit and put back as it was (fit_animated says when)."""
    try:
        import FreeCADGui

        from . import restart_mark

        if restart_mark.read() is not None:
            return False
        gd = FreeCADGui.ActiveDocument
        if gd is None or FreeCAD.ActiveDocument is None or gd.Document.Name not in FreeCAD.listDocuments():
            return False
        v = gd.ActiveView
        if v is None or not hasattr(v, "getSceneGraph") or not hasattr(v, "fitAll"):
            return False
        was = None
        if not animate:
            try:
                was = bool(v.isAnimationEnabled())
                if was:
                    v.setAnimationEnabled(False)
            except Exception:
                was = None
        try:
            v.fitAll()
        finally:
            if was:
                try:
                    v.setAnimationEnabled(True)
                except Exception:
                    pass
        return True
    except Exception as e:
        FreeCAD.Console.PrintLog(f"Agent Link fit: {e}\n")
        return False


def _objects(doc, names):
    out = []
    for n in names:
        if not isinstance(n, str):
            continue
        o = doc.getObject(n) or next((x for x in doc.Objects if x.Label == n), None)
        if o is not None and o not in out:
            out.append(o)
    return out


# Counts the selections made here: a result's "lit for a moment" timer
# clears the selection only while it is still that result's (at a batch's
# short pace the next call's selection is there before the timer fires).
_selected = [0]


def _clear_if(mark):
    """Clear the selection unless a newer one was made here since mark."""
    if _selected[0] != mark:
        return False
    try:
        import FreeCADGui

        FreeCADGui.Selection.clearSelection()
    except Exception:  # noqa: BLE001 - the window is closing
        return False
    return True


def _select(objs):
    import FreeCADGui

    if not objs:
        return
    _selected[0] += 1
    FreeCADGui.Selection.clearSelection()
    for o in objs:
        try:
            FreeCADGui.Selection.addSelection(o)
        except Exception:
            pass


def _workbench_for(name):
    """The bench for a tool: the longest WORKBENCH key that is its name or
    a prefix of it (core's prefixes and what add-ons declared)."""
    return _longest(name, WORKBENCH)


# Declared benches not loaded in this window, logged once each.
UNKNOWN_BENCHES = set()


def bench_to_switch(name, loaded, active):
    """The bench to bring up for this call, or None: none declared, already
    in front, or not loaded in this window (an add-on's bench when the
    add-on is not here) — that last logged once, never an error."""
    wb = _workbench_for(name)
    if not wb or wb == active:
        return None
    if wb not in loaded:
        if wb not in UNKNOWN_BENCHES:
            UNKNOWN_BENCHES.add(wb)
            if FreeCAD is not None:
                FreeCAD.Console.PrintLog(f"Agent Link echo: {wb} (for {name}) is not loaded here; the bench stays as it is.\n")
        return None
    return wb


def bench_ready(wb):
    """Before a workbench is brought up from here: what must be in place so
    its first start cannot stop the window. OpenSCAD's start looks for the
    OpenSCAD program when FreeCAD's preference for it is empty — on a Mac by
    asking Finder through AppleScript, with no time limit, behind a permission
    prompt (FreeCAD 1.1: src/Mod/OpenSCAD/InitGui.py, OpenSCADUtils.py): the
    plain search is put in its place first. Never raises."""
    if wb != "OpenSCADWorkbench":
        return
    try:
        from .families import openscad

        openscad.plain_search()
    except Exception as e:  # noqa: BLE001
        if FreeCAD is not None:
            FreeCAD.Console.PrintLog(f"Agent Link: OpenSCAD's search was not replaced ({e})\n")


class Echo:
    def __init__(self, session):
        self.s = session
        self.t0 = None
        # How the call in hand is shown (pace()): set in before, used by
        # after and the waits between.
        self.mode, self.ms = "full", None

    def _pace(self, tool):
        """This call's pace, from where its batch is (session.batch_now)."""
        try:
            self.mode, self.ms = pace(getattr(self.s, "batch_now", None), bool(getattr(tool, "changes", False)), delay_ms(), batch_delay_ms())
        except Exception:  # noqa: BLE001 - a preference that cannot be read: the full pace
            self.mode, self.ms = "full", None

    def _pause(self):
        """The pause of the call in hand."""
        _wait(delay_ms() if self.ms is None else self.ms)

    def live(self):
        """Shown in the window, unless an extension asks for the window to
        be left alone (session.window_quiet, agentlink/ext.py)."""
        return not getattr(self.s, "window_quiet", False)

    def quiet(self):
        """A panel's own refresh (Panel._call quiet=True): not the agent's
        work, so nothing shown and nothing in Activity."""
        return bool(getattr(self.s, "quiet_call", False))

    def before(self, tool, args):
        self.t0 = time.time()
        self.mode, self.ms = "full", None
        if self.quiet():
            return
        if tool is None or skipped(tool.name):
            return
        if not enabled() or not self.live():
            return
        switch = switches_bench(tool)
        shown = switch or tool.name.startswith(SHOWN)
        if not shown:
            return
        self._pace(tool)
        short = self.mode == "short"
        try:
            import FreeCADGui

            wb = None
            if switch:
                act = FreeCADGui.activeWorkbench()
                wb = bench_to_switch(tool.name, FreeCADGui.listWorkbenches(), act.name() if act else None)
                if wb:
                    bench_ready(wb)
                    FreeCADGui.activateWorkbench(wb)
                self._mode(tool.name, args)
            caption(_describe(tool.name, args))
            # Which document the agent is on (K), when it is not the one in front.
            where = ""
            try:
                if FreeCAD.ActiveDocument is not None and self.s.doc is not None and FreeCAD.ActiveDocument.Name != self.s.doc.Name:
                    where = f" (in {self.s.doc.Label})"
            except Exception:
                pass
            FreeCADGui.getMainWindow().statusBar().showMessage("Agent" + where + ": " + _describe(tool.name, args), 4000)
            cmd = command_for(tool.name, args) if switch else None
            if cmd:
                # settle: after a bench switch its toolbars must exist before
                # a button can light — kept at the short pace too (one
                # paint, and only when the bench did switch): without it the
                # button would not light at all.
                flash_command(cmd, settle=bool(wb))
            doc = self.s.doc
            _select(_objects(doc, [args.get(k) for k in ARG_KEYS if args.get(k)]))
            if short and self.ms > 0:
                self._pause()  # its paints show the selection and the lit button
            else:
                _paint()
                if not short:
                    self._pause()
        except Exception as e:
            FreeCAD.Console.PrintLog(f"Agent Link echo (before {tool.name}): {e}\n")

    def _views(self, name, args, body):
        """The window a person would be looking at: a TechDraw tool's page
        open in its tab, everything else in the 3D view; a FEM analysis
        made active."""
        import FreeCADGui

        QtCore, _QtGui, QtW = _qt()
        doc = self.s.doc
        page_ref = (body or {}).get("page") or (args or {}).get("page")
        if name.startswith(tuple(PAGES)) and isinstance(page_ref, str):
            page = _objects(doc, [page_ref])
            if page and page[0].ViewObject:
                try:
                    page[0].ViewObject.doubleClicked()
                except Exception:
                    pass
            return
        an = (body or {}).get("analysis")
        if an:
            obj = _objects(doc, [an])
            if obj:
                try:
                    import FemGui

                    FemGui.setActiveAnalysis(obj[0])
                except Exception:
                    pass
        # Back to the 3D view when a drawing page is in front.
        area = FreeCADGui.getMainWindow().findChild(QtW.QMdiArea)
        if area is None:
            return
        cur = area.activeSubWindow()
        if cur is not None and type(cur.widget()).__name__ != "View3DInventor":
            for sub in area.subWindowList():
                if type(sub.widget()).__name__ == "View3DInventor":
                    area.setActiveSubWindow(sub)
                    break
        self._container(name, args or {}, body or {})

    def _container(self, name, args, body):
        """What a person would have made active for the work: an assembly
        (as Assembly's "Activate assembly" does, its joints then going into
        it), a BIM level or building (the active container new BIM objects
        go into), a CAM job's operation shown with its stock; a joint's two
        faces lit."""
        import FreeCADGui

        doc = self.s.doc
        gd = FreeCADGui.ActiveDocument
        view = getattr(gd, "ActiveView", None) if gd else None
        if view is None:
            return
        if name.startswith("asm_"):
            asm = _objects(doc, [body.get("assembly") or args.get("assembly")])
            if asm:
                try:
                    if view.getActiveObject("part") is not asm[0]:
                        view.setActiveObject("part", asm[0])
                except Exception:
                    pass
            if name == "asm_joint":
                ends = [body.get("a"), body.get("b")]
                lit = []
                for end in ends:
                    if not isinstance(end, str) or "." not in end:
                        continue
                    label, el = end.rsplit(".", 1)
                    o = _objects(doc, [label])
                    if o:
                        lit.append((o[0], el))
                if lit:
                    FreeCADGui.Selection.clearSelection()
                    for o, el in lit:
                        try:
                            FreeCADGui.Selection.addSelection(o, el)
                        except Exception:
                            pass
                    # The joint's two faces lit for the pause; at a batch's
                    # short pace they stay lit and the call's last paint
                    # shows them.
                    if self.mode != "short":
                        self._pause()
        elif name.startswith("bim_") and name in ("bim_level", "bim_building"):
            made = _objects(doc, [body.get("object")])
            if made:
                try:
                    view.setActiveObject("Arch", made[0])
                except Exception:
                    pass
        elif name.startswith("bim_") and isinstance(args.get("level"), str):
            lv = _objects(doc, [args["level"]])
            if lv:
                try:
                    view.setActiveObject("Arch", lv[0])
                except Exception:
                    pass
        elif name.startswith("cam_"):
            job = _objects(doc, [body.get("job") or args.get("job")])
            op = _objects(doc, [body.get("op")])
            if job:
                j = job[0]
                stock = getattr(j, "Stock", None)
                for o in [stock] + op:
                    vo = getattr(o, "ViewObject", None) if o is not None else None
                    if vo is not None:
                        try:
                            vo.Visibility = True
                        except Exception:
                            pass
                if stock is not None and getattr(stock, "ViewObject", None) is not None:
                    try:
                        stock.ViewObject.Transparency = max(int(stock.ViewObject.Transparency or 0), 70)
                    except Exception:
                        pass

    def _mode(self, name, args):
        """The mode a person would be in: a sketch's tools work with the
        sketch open in the Sketcher; anything else closes it first."""
        import FreeCADGui

        gd = FreeCADGui.ActiveDocument
        if gd is None:
            return
        editing = gd.getInEdit()
        sk = args.get("sketch") if name.startswith("sketch_") and name not in ("sketch_new", "sketch_state") else None
        target = _objects(self.s.doc, [sk])[0] if sk and _objects(self.s.doc, [sk]) else None
        if target is not None:
            if editing is None or editing.Object is not target:
                if editing is not None:
                    gd.resetEdit()
                gd.setEdit(target.Name)
        elif editing is not None and not name.startswith(("sketch_", "view_", "note_", "measure", "cmd_", "menu_")):
            # (A command or a menu entry acts in the mode the window is in,
            # as when a person pushes it: closing the sketch first left
            # Sketcher_LeaveSketch greyed out and refused.)
            # FreeCAD turns the camera back to where it was before the
            # sketch, animated. Inside a batch the next fit cut that turn off
            # at its first frame and the view stayed flat on the sketch: the
            # turn is made at once there (animation off for this one step).
            v, was = None, None
            if getattr(self.s, "batch_now", None):
                try:
                    v = gd.ActiveView
                    was = bool(v.isAnimationEnabled())
                    if was:
                        v.setAnimationEnabled(False)
                except Exception:
                    v, was = None, None
            try:
                gd.resetEdit()
            finally:
                if v is not None and was:
                    try:
                        v.setAnimationEnabled(True)
                    except Exception:
                        pass
            self._left_sketch = True

    def after(self, tool, args, reply):
        if self.quiet():
            return
        name = tool.name if tool is not None else "?"
        ok = not (reply or {}).get("isError")
        try:
            import json

            body = json.loads(reply["content"][0]["text"]) if reply and reply.get("content") else {}
        except Exception:
            body = {}
        if name != "batch":
            from . import activity

            try:
                what = activity.did(name, args, body, getattr(tool, "activity", None))
                result = activity.outcome(name, ok, body, args)
                call = activity.raw_call(name, args)
            except Exception as e:  # the words never stop a call
                what, result, call = name, "" if ok else "Refused", name
                if FreeCAD is not None:
                    FreeCAD.Console.PrintLog(f"Agent Link activity words ({name}): {e}\n")
            _note({"time": datetime.datetime.now().strftime("%H:%M:%S"), "tool": name, "ok": ok, "what": _tag(self.s) + what,
                   "result": result, "call": call, "ms": int((time.time() - (self.t0 or time.time())) * 1000)})
        if not (enabled() and ok and tool is not None and tool.changes and self.live()) or name == "batch":
            return
        try:
            import FreeCADGui

            doc = self.s.doc
            made = _objects(doc, [body.get(k) for k in OUT_KEYS if isinstance(body.get(k), str)])
            # The window's view effects only where the agent's document is
            # the one in front (K): the person's own document is left alone.
            if FreeCAD.ActiveDocument is None or doc is None or FreeCAD.ActiveDocument.Name != doc.Name:
                _paint()
                return
            self._views(name, args, body)
            if name == "sketch_new" and made and FreeCADGui.ActiveDocument:
                FreeCADGui.ActiveDocument.setEdit(made[0].Name)
            if made:
                _select(made)
                # Lit for a moment, then the part shows in its own colours again.
                QtCore, _QtGui, _QtW = _qt()
                QtCore.QTimer.singleShot(1800, lambda mark=_selected[0]: _clear_if(mark))
                body_obj = next((o for o in made if o.TypeId == "PartDesign::Body"), None)
                if body_obj is None:
                    body_obj = next((p for o in made for p in o.InList if p.TypeId == "PartDesign::Body"), None)
                gv = FreeCADGui.ActiveDocument.ActiveView if FreeCADGui.ActiveDocument else None
                if body_obj is not None and gv is not None:
                    gv.setActiveObject("pdbody", body_obj)
            # Follow the work: the view framed on the part after each change
            # (Mod/AgentLink Follow; the Activity tab's check box).
            if FreeCAD.ParamGet(PREFS).GetBool("Follow", True) and not name.startswith(tuple(PAGES)):
                from . import around

                # The sketch was closed for this call and the camera still
                # looks straight down on it: a pad then shows as a flat
                # outline and nobody sees that it is a solid. Turned to the
                # isometric view once, as a person turns it to look.
                self._left_sketch = False
                tr = {"mode": self.mode, "made": [getattr(o, "Name", "?") for o in made]}
                try:
                    self.s.echo_trace = tr
                    tr["inEdit"] = FreeCADGui.ActiveDocument.getInEdit() is not None
                    d0 = FreeCADGui.ActiveDocument.ActiveView.getViewDirection()
                    tr["dir"] = [round(d0.x, 3), round(d0.y, 3), round(d0.z, 3)]
                    tr["solids"] = [len(o.Shape.Solids) if getattr(o, "Shape", None) is not None else None for o in made]
                except Exception as e:  # noqa: BLE001
                    tr["error"] = f"{type(e).__name__}: {e}"
                # (Whenever a solid was made or changed and no sketch is
                # open: the sketch may have been closed by an earlier call.)
                if FreeCADGui.ActiveDocument is not None and FreeCADGui.ActiveDocument.getInEdit() is None:
                    try:
                        if made and any(getattr(o, "Shape", None) is not None and o.Shape.Solids for o in made):
                            # Set, not animated: viewIsometric starts a turn
                            # that the fit just below cut off at its first
                            # frame inside a batch (the view stayed flat).
                            # Only when the camera still looks straight
                            # along an axis (a person's own tilted view is
                            # left as it is).
                            gv2 = FreeCADGui.ActiveDocument.ActiveView
                            d = gv2.getViewDirection()
                            if max(abs(d.x), abs(d.y), abs(d.z)) > 0.999:
                                # At once, animation off for this one
                                # step: with it on the turn only begins
                                # here (the direction read just after was
                                # unchanged, live) and the fit cut it off.
                                was_anim = None
                                try:
                                    was_anim = bool(gv2.isAnimationEnabled())
                                    if was_anim:
                                        gv2.setAnimationEnabled(False)
                                except Exception:
                                    was_anim = None
                                try:
                                    gv2.viewIsometric()
                                finally:
                                    if was_anim:
                                        gv2.setAnimationEnabled(True)
                                d1 = gv2.getViewDirection()
                                tr["turnedTo"] = [round(d1.x, 3), round(d1.y, 3), round(d1.z, 3)]
                    except Exception as e:  # noqa: BLE001
                        tr["turnError"] = f"{type(e).__name__}: {e}"
                _model_tab_back()

                with around.part("fit"):
                    fit(animate=fit_animated(getattr(self.s, "batch_now", None), self.mode))
            # What was done, said again now that it is done: at a batch's
            # pace the words set before the call were gone from the view and
            # the status bar by the time the result showed.
            try:
                words = _describe(name, args)
                caption(words)
                FreeCADGui.getMainWindow().statusBar().showMessage("Agent: " + words, 4000)
            except Exception:
                pass
            _paint()
        except Exception as e:
            FreeCAD.Console.PrintLog(f"Agent Link echo (after {name}): {e}\n")


def _model_tab_back():
    """The Model tab in front again when the Tasks tab shows nothing: FreeCAD
    raises Tasks for a task dialog or a sketch and leaves it up, empty, when
    that ends, with the tree (and what was just made in it) behind it. Left
    alone while a dialog or an edit is open, and when the person's own tab
    (any other than Tasks) is in front."""
    try:
        import FreeCADGui

        if FreeCADGui.Control.activeDialog() or (FreeCADGui.ActiveDocument and FreeCADGui.ActiveDocument.getInEdit() is not None):
            return False
        _QtCore, _QtGui, QtW = _qt()
        mw = FreeCADGui.getMainWindow()
        for tabs in mw.findChildren(QtW.QTabWidget):
            titles = [tabs.tabText(i).replace("&", "") for i in range(tabs.count())]
            if "Model" in titles and "Tasks" in titles and tabs.currentIndex() == titles.index("Tasks"):
                tabs.setCurrentIndex(titles.index("Model"))
                return True
    except Exception:
        pass
    return False


def _tag(session):
    """An extension's text before each call (session.activity_tag), plain."""
    from . import activity

    t = activity.plain(getattr(session, "activity_tag", "") or "")
    return t + " " if t else ""


def wrap(server, session):
    """Show each call the server runs in the window — batches' calls one by one."""
    echo = Echo(session)
    plain = server.call

    def call(params):
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = server.tools.get(name)
        if tool is not None:
            tool = tool.for_call(args)  # a changing tool's read shows as a read
        from . import around

        with around.part("echoBefore"):
            echo.before(tool, args)
        reply = plain(params)
        with around.part("echoAfter"):  # its view fit is in "fit" as well
            echo.after(tool, args, reply)
        return reply

    server.call = call
    return echo
