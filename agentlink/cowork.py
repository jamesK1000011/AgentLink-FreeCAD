# SPDX-License-Identifier: LGPL-2.1-or-later
"""Co-work in one window: the camera and the selection stay the person's.

Follow the agent (Mod/AgentLink FollowAgent, a bool, off by default; the
Activity tab's "Follow agent" check box). Off: the echo never moves the
camera (no fit, no frame, no turn). The captions, the lit buttons and the
workbench switch stay. On: the echo frames the agent's work, but it skips
a frame while a mouse button is down on the 3D view, or for
FollowAgentQuiet seconds (3 by default) after the person's last input on
the 3D view (a click, the wheel, a pinch, a key). It stays on until the
person turns it off.

What the echo shows (Mod/AgentLink EchoSelects: "highlight", the default,
or "select"). highlight: what a call made or read is drawn in the 3D view's
scene in FreeCAD's selection colour (View/SelectionColor); FreeCAD's
selection is never changed, so "use my selection" reads what the person
picked. The drawing goes at the next changing call and at the next
highlight. select: the echo sets the selection, as before.

Every selection write of the echo goes through sel_clear and sel_add here.

A command that needs a selection (cmd_run with select, a data tool's
command runner): held(objs) sets the selection for the run only; the
person's selection is saved first and put back after, with
hooks.selection_muted() on all that time.

Everything here is safe without FreeCAD's window: no GUI, nothing done.
"""
import sys
import time

PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
VIEW_PREFS = "User parameter:BaseApp/Preferences/View"
FOLLOW_KEY = "FollowAgent"
QUIET_KEY = "FollowAgentQuiet"
QUIET_S = 3.0
SELECTS_KEY = "EchoSelects"
MODES = ("highlight", "select")
# FreeCAD's own default selection colour (View/SelectionColor, 0xRRGGBBAA):
# 28, 173, 28.
SELECTION_COLOUR = 0x1CAD1C00
OWNER = "echo-highlight"
FACES_MOST = 400       # faces of one whole object drawn at most
EDGES_MOST = 800       # edges of one whole object drawn at most
TRIANGLES_MOST = 200000  # triangles of all the highlight at most
TINT_TRANSPARENCY = 0.45
EDGE_WIDTH = 3.0
# The tint of a whole object pulled this far towards the camera
# (SoPolygonOffset factor, units), so it shows over the object's own faces.
TINT_OFFSET = (-1.0, -4.0)


def _log(text):
    try:
        import FreeCAD

        FreeCAD.Console.PrintLog(text)
    except Exception:  # noqa: BLE001
        sys.stderr.write(text)


def _get(kind, key, default, group=PREFS):
    """A preference, or default when it cannot be read. Never raises."""
    try:
        import FreeCAD

        fn = getattr(FreeCAD.ParamGet(group), "Get" + kind, None)
        return fn(key, default) if callable(fn) else default
    except Exception:  # noqa: BLE001
        return default


# ---- follow the agent ---------------------------------------------------------------------

def follow_on():
    """The person's FollowAgent preference (off by default)."""
    return bool(_get("Bool", FOLLOW_KEY, False))


def set_follow(on):
    import FreeCAD

    FreeCAD.ParamGet(PREFS).SetBool(FOLLOW_KEY, bool(on))


def quiet_s():
    """FollowAgentQuiet, seconds (3): how long after the person's last input
    on the 3D view the echo leaves the camera alone."""
    try:
        return max(0.0, float(_get("Float", QUIET_KEY, QUIET_S)))
    except (TypeError, ValueError):
        return QUIET_S


_input = {"down": False, "last": 0.0, "filter": None, "on": {}}
WATCHED_MOST = 16  # widgets watched at most (3D views open at once)


def busy(now, down, last, quiet):
    """Whether the person works the view now: a button down, or input less
    than quiet seconds ago. Plain Python."""
    if down:
        return True
    return bool(last) and (now - last) < quiet


def note_input(kind, buttons=0, now=None):
    """One event on the 3D view, by kind: "press", "release", "move" (with
    buttons: how many are still down), "wheel", "key", "gesture". Plain
    Python: the event filter calls it."""
    now = time.time() if now is None else now
    if kind == "press":
        _input["down"] = True
    elif kind == "release":
        _input["down"] = bool(buttons)
    elif kind == "move" and not buttons:
        return  # the pointer passing over the view is not work on it
    _input["last"] = now


def _buttons_down_anywhere():
    """Whether Qt says a mouse button is down (a release the view missed
    leaves "down" standing). None when it cannot tell."""
    try:
        from PySide import QtGui

        app = QtGui.QGuiApplication if hasattr(QtGui, "QGuiApplication") else QtGui.QApplication
        return _flag(app.mouseButtons()) != 0
    except Exception:  # noqa: BLE001
        return None


def _flag(x):
    try:
        return int(x)
    except Exception:  # noqa: BLE001
        try:
            return int(x.value)
        except Exception:  # noqa: BLE001
            return 0


def view_busy(now=None):
    """Whether the person works the 3D view now (busy()). Never raises."""
    now = time.time() if now is None else now
    if _input["down"] and _buttons_down_anywhere() is False:
        _input["down"] = False
    return busy(now, _input["down"], _input["last"], quiet_s())


def follows():
    """Whether the echo may move the camera now: FollowAgent on and the
    person not working the view. The view's input watch is put on here
    (once per view)."""
    if not follow_on():
        return False
    watch_view()
    return not view_busy()


def _filter():
    """The one event filter (made once; needs Qt)."""
    if _input["filter"] is not None:
        return _input["filter"]
    from PySide import QtCore

    T = QtCore.QEvent.Type if hasattr(QtCore.QEvent, "Type") else QtCore.QEvent
    kinds = {}
    for name, kind in (("MouseButtonPress", "press"), ("MouseButtonDblClick", "press"), ("MouseButtonRelease", "release"),
                       ("MouseMove", "move"), ("Wheel", "wheel"), ("KeyPress", "key"), ("NativeGesture", "gesture"),
                       ("Gesture", "gesture"), ("TouchBegin", "press"), ("TouchEnd", "release"), ("TouchUpdate", "move")):
        t = getattr(T, name, None)
        if t is not None:
            kinds[t] = kind

    class _ViewInput(QtCore.QObject):
        def eventFilter(self, obj, ev):  # noqa: N802 (Qt)
            # A dict look-up and two numbers: the cost of each event.
            try:
                kind = kinds.get(ev.type())
                if kind is not None:
                    b = 0
                    if kind in ("release", "move"):
                        fn = getattr(ev, "buttons", None)
                        b = _flag(fn()) if callable(fn) else 0
                        if kind == "move" and not b:
                            return False
                    note_input(kind, b)
            except Exception:  # noqa: BLE001
                pass
            return False

    _input["filter"] = _ViewInput()
    return _input["filter"]


def _view_widgets():
    """The active 3D view's widgets that take the person's input: its
    graphics view and that view's viewport. Empty without a 3D view."""
    import FreeCADGui

    gd = FreeCADGui.ActiveDocument
    v = getattr(gd, "ActiveView", None) if gd is not None else None
    fn = getattr(v, "graphicsView", None)
    if not callable(fn):
        return []
    gv = fn()
    if gv is None:
        return []
    out = [gv]
    try:
        vp = gv.viewport()
        if vp is not None:
            out.append(vp)
    except Exception:  # noqa: BLE001
        pass
    return out


def watch_view(widgets=None):
    """The input watch put on the active 3D view (each widget once; gone
    ones forgotten). How many widgets are watched. Never raises; nothing
    without a window."""
    try:
        import FreeCAD

        if not getattr(FreeCAD, "GuiUp", False) and widgets is None:
            return 0
        from .overlay import alive

        on = _input["on"]
        for k in [k for k, w in on.items() if not alive(w)]:
            on.pop(k, None)
        for w in (widgets if widgets is not None else _view_widgets()):
            if id(w) in on or len(on) >= WATCHED_MOST:
                continue
            w.installEventFilter(_filter())
            on[id(w)] = w
        return len(on)
    except Exception as e:  # noqa: BLE001
        _log(f"Agent Link co-work (view watch): {e}\n")
        return 0


# ---- the selection is the person's ----------------------------------------------------------

def mode():
    """EchoSelects: "highlight" (the default) or "select"."""
    v = str(_get("String", SELECTS_KEY, MODES[0]) or "").strip().lower()
    return v if v in MODES else MODES[0]


def selection_rgb(packed=None):
    """FreeCAD's selection colour (View/SelectionColor, 0xRRGGBBAA) as
    (r, g, b) 0..1; its default green when it cannot be read."""
    if packed is None:
        packed = _get("Unsigned", "SelectionColor", SELECTION_COLOUR, VIEW_PREFS)
    try:
        c = int(packed) & 0xFFFFFFFF
    except (TypeError, ValueError):
        c = SELECTION_COLOUR
    return tuple(((c >> s) & 0xFF) / 255.0 for s in (24, 16, 8))


def selection_hex(packed=None):
    return "#%02x%02x%02x" % tuple(int(round(x * 255)) for x in selection_rgb(packed))


# The highlight: [(document, object, sub)] as a selection would hold them,
# and the scene it was drawn in.
_hl = {"entries": [], "triangles": 0}


def _sel():
    import FreeCADGui

    return FreeCADGui.Selection


def sel_clear(doc=None):
    """The echo's selection cleared: FreeCAD's (select) or the highlight
    (highlight). doc: only that document's."""
    if mode() == "select":
        if doc is None:
            _sel().clearSelection()
            return
        try:
            _sel().clearSelection(doc)
        except TypeError:
            _sel().clearSelection()
        return
    clear_highlight(doc)


def _entry(args):
    """(document, object, sub) of addSelection's arguments: (doc, name[,
    sub]) or (obj[, sub]). ValueError when the object is not there."""
    if not args:
        raise ValueError("nothing to select")
    if isinstance(args[0], str):
        doc, name = args[0], args[1] if len(args) > 1 else ""
        sub = args[2] if len(args) > 2 else ""
        try:
            try:
                import FreeCAD
            except ImportError:  # no FreeCAD (tests): taken as given
                return (str(doc), str(name), str(sub or ""))
            get = getattr(FreeCAD, "getDocument", None)
            if callable(get):
                d = get(doc)
                if d is None or d.getObject(name) is None:
                    raise ValueError(f"no object {name} in {doc}")
        except ValueError:
            raise
        except Exception as e:  # noqa: BLE001  (no such document)
            raise ValueError(str(e))
        return (str(doc), str(name), str(sub or ""))
    o = args[0]
    sub = args[1] if len(args) > 1 and isinstance(args[1], str) else ""
    try:
        return (o.Document.Name, o.Name, sub)
    except Exception as e:  # noqa: BLE001
        raise ValueError(str(e))


def sel_add(*args):
    """One entry added to the echo's selection, with addSelection's
    arguments. select: FreeCAD's selection (its errors go up, as before).
    highlight: drawn in the scene; ValueError when the object is not
    there. True when taken."""
    if mode() == "select":
        _sel().addSelection(*args)
        return True
    e = _entry(args)
    if e not in _hl["entries"]:
        _hl["entries"].append(e)
        _draw(e)
    return True


def sel_rows():
    """[(document, object, sub)] the echo's selection holds now: FreeCAD's
    selection (select), else the highlight's entries."""
    if mode() != "select":
        return list(_hl["entries"])
    rows = []
    for x in _sel().getSelectionEx("", 0) or ():
        subs = [str(n) for n in (getattr(x, "SubElementNames", None) or ()) if n]
        for sub in subs or [""]:
            rows.append((x.DocumentName, x.ObjectName, sub))
    return rows


def sel_names():
    """The names of the objects in the echo's selection, in order, once each."""
    if mode() == "select":
        return [x.Name for x in _sel().getSelection()]
    out = []
    for _d, o, _s in _hl["entries"]:
        if o not in out:
            out.append(o)
    return out


def sel_count():
    if mode() == "select":
        return len(_sel().getSelectionEx() or ())
    return len(sel_names())


def _leaf(e):
    """The object an entry names: its sub-object for a path ("Pad.Face6"
    of Body: Pad), else the object itself. None when gone."""
    import FreeCAD

    doc, name, sub = e
    o = FreeCAD.getDocument(doc).getObject(name)
    if o is None:
        return None
    path = sub.rsplit(".", 1)[0] + "." if "." in sub else ""
    if path:
        try:
            got = o.getSubObject(path, retType=1)
            if got is not None:
                return got
        except Exception:  # noqa: BLE001
            pass
    return o


def sel_objects():
    """The objects of the echo's selection (their sub-objects for paths)."""
    if mode() == "select":
        return list(_sel().getSelection())
    out = []
    for e in _hl["entries"]:
        try:
            o = _leaf(e)
        except Exception:  # noqa: BLE001
            o = None
        if o is not None and o not in out:
            out.append(o)
    return out


def element_of(sub):
    """("Face6", "face") of "Pad.Face6"; ("", None) for a whole object
    ("", "Pad."); (name, "other") for a part that is no shape element (a
    sketch's "Constraint1"). Plain Python."""
    from .annotate import kind_of

    last = str(sub or "").rsplit(".", 1)[-1]
    if not last:
        return "", None
    k = kind_of(last)
    return last, (k or "other")


def _shape(e):
    """(kind, shape) to draw for an entry: ("face" | "edge" | "vertex", the
    element where it is drawn) or ("whole", the object's shape there); None
    when there is nothing to draw."""
    import FreeCAD
    import Part

    doc, name, sub = e
    o = FreeCAD.getDocument(doc).getObject(name)
    if o is None:
        return None
    el, kind = element_of(sub)
    if kind == "other":
        return None
    if kind is not None:
        return kind, Part.getShape(o, sub, needSubElement=True, transform=True)
    sh = Part.getShape(o, sub, needSubElement=False, transform=True)
    if sh is None or sh.isNull():
        return None
    return "whole", sh


def whole_node(coin, shape, rgb, tol=None, budget=TRIANGLES_MOST):
    """One object drawn whole: its faces tinted (pulled towards the camera
    over its own faces, depth-tested so its far side stays hidden) and its
    edges as lines, in rgb. (node, triangles). The faces and edges past
    FACES_MOST and EDGES_MOST, and triangles past budget, are left out."""
    from .annotate import edge_line, face_mesh

    sep = coin.SoSeparator()
    try:
        ps = coin.SoPickStyle()
        ps.style = getattr(coin.SoPickStyle, "UNPICKABLE", 2)
        sep.addChild(ps)
    except Exception:  # noqa: BLE001
        pass
    if tol is None:
        try:
            tol = max(0.1, float(shape.BoundBox.DiagonalLength) / 400.0)
        except Exception:  # noqa: BLE001
            tol = 0.1
    pts, idx, tris = [], [], 0
    for f in list(getattr(shape, "Faces", None) or ())[:FACES_MOST]:
        try:
            p, ix = face_mesh(f, tol)
        except Exception:  # noqa: BLE001
            continue
        n = len(ix) // 4
        if tris + n > budget:
            break
        base = len(pts)
        pts += p
        idx += [i if i < 0 else i + base for i in ix]
        tris += n
    if idx:
        mat = coin.SoMaterial()
        mat.diffuseColor = rgb
        mat.emissiveColor = rgb
        mat.transparency = TINT_TRANSPARENCY
        off = coin.SoPolygonOffset()
        off.factor, off.units = TINT_OFFSET
        co = coin.SoCoordinate3()
        co.point.setValues(0, len(pts), pts)
        fs = coin.SoIndexedFaceSet()
        fs.coordIndex.setValues(0, len(idx), idx)
        for c in (mat, off, co, fs):
            sep.addChild(c)
    lines, counts = [], []
    for ed in list(getattr(shape, "Edges", None) or ())[:EDGES_MOST]:
        try:
            p = edge_line(ed, 24)
        except Exception:  # noqa: BLE001
            continue
        if len(p) >= 2:
            lines += p
            counts.append(len(p))
    if counts:
        emat = coin.SoMaterial()
        emat.diffuseColor = rgb
        emat.emissiveColor = rgb
        st = coin.SoDrawStyle()
        st.lineWidth = EDGE_WIDTH
        co = coin.SoCoordinate3()
        co.point.setValues(0, len(lines), lines)
        ls = coin.SoLineSet()
        ls.numVertices.setValues(0, len(counts), counts)
        for c in (emat, st, co, ls):
            sep.addChild(c)
    return sep, tris


def _draw(e):
    """One entry drawn in the active 3D view's scene (the annotation
    layer's owner OWNER). True when drawn. Never raises."""
    try:
        import FreeCAD

        if not getattr(FreeCAD, "GuiUp", False):
            return False
        from . import annotate

        got = _shape(e)
        if got is None:
            return False
        kind, shape = got
        ann = annotate.service()
        colour = selection_hex()
        if kind != "whole":
            # A face, an edge or a vertex: the annotation layer's own
            # drawing (an SoAnnotation, over the model), in the selection's
            # colour.
            el, _k = element_of(e[2])
            holder = _Single(shape, el)
            r = ann.light(_leaf(e), [el], owner=OWNER, colour=colour, shape=holder)
            return bool(r.get("lit"))
        root = ann.root(OWNER)
        if root is None:
            return False
        node, tris = whole_node(ann.coin(), shape, selection_rgb(), budget=max(0, TRIANGLES_MOST - _hl["triangles"]))
        _hl["triangles"] += tris
        root.addChild(node)
        return True
    except Exception as e2:  # noqa: BLE001
        _log(f"Agent Link co-work (highlight): {type(e2).__name__}: {e2}\n")
        return False


class _Single:
    """A shape that holds one element under its own name (the element is
    already placed where it is drawn)."""

    def __init__(self, el, name):
        self.el, self.name = el, name

    def getElement(self, name):
        if name != self.name:
            raise ValueError(name)
        return self.el


def clear_highlight(doc=None):
    """The highlight taken away (doc: only that document's entries; the
    rest drawn again). How many entries went. Never raises."""
    n = 0
    try:
        keep = [e for e in _hl["entries"] if doc is not None and e[0] != doc]
        n = len(_hl["entries"]) - len(keep)
        _hl["entries"] = []
        _hl["triangles"] = 0
        try:
            from . import annotate

            if annotate._SERVICE is not None or n:
                annotate.service().clear(OWNER)
        except Exception:  # noqa: BLE001
            pass
        for e in keep:
            _hl["entries"].append(e)
            _draw(e)
    except Exception as e:  # noqa: BLE001
        _log(f"Agent Link co-work (highlight clear): {e}\n")
    return n


def redraw():
    """The highlight drawn again (after the view's scene changed). Its
    entries as "Object.Sub", or None."""
    rows = list(_hl["entries"])
    if not rows:
        return None
    clear_highlight()
    for e in rows:
        _hl["entries"].append(e)
        _draw(e)
    return [f"{o}.{s}" if s else o for _d, o, s in rows]


def highlight(items, doc=None):
    """What is shown lit, in place of the last highlight: items objects,
    (object, sub) pairs, "Object" or "Object.Face6" names (doc: their
    document; the active one when None). FreeCAD's selection is not
    touched. {"lit": ["Object.Sub"...], "missing": [...]}. Never raises."""
    clear_highlight()
    lit, missing = [], []
    for it in items or ():
        try:
            o, sub = it if isinstance(it, tuple) else (it, "")
            if isinstance(o, str):
                name, sub2 = (o.rsplit(".", 1) if "." in o and element_of(o)[1] not in (None, "other") else (o, ""))
                sub = sub or sub2
                import FreeCAD

                d = FreeCAD.getDocument(doc) if doc else FreeCAD.ActiveDocument
                found = d.getObject(name) if d is not None else None
                if found is None and d is not None:
                    byl = d.getObjectsByLabel(name)
                    found = byl[0] if byl else None
                if found is None:
                    missing.append(o)
                    continue
                o = found
            e = _entry((o, sub))
            if e not in _hl["entries"]:
                _hl["entries"].append(e)
                _draw(e)
            lit.append(f"{e[1]}.{sub}" if sub else e[1])
        except Exception as e:  # noqa: BLE001
            missing.append(f"{it} ({type(e).__name__})")
    return {"lit": lit, "missing": missing}


# ---- a command's own selection, for its run only ----------------------------------------------

_held = []  # [(the person's selection rows, the mute)], innermost last


def depth():
    return len(_held)


def saved_rows():
    """FreeCAD's selection now as [(document, object, sub)]. Never raises."""
    try:
        rows = []
        for x in _sel().getSelectionEx("", 0) or ():
            subs = [str(n) for n in (getattr(x, "SubElementNames", None) or ()) if n]
            for sub in subs or [""]:
                rows.append((x.DocumentName, x.ObjectName, sub))
        return rows
    except Exception:  # noqa: BLE001
        return []


def put_back(rows):
    """FreeCAD's selection set to rows again. How many were taken."""
    S = _sel()
    S.clearSelection()
    n = 0
    for d, o, s in rows:
        try:
            if s:
                S.addSelection(d, o, s)
            else:
                S.addSelection(d, o)
            n += 1
        except Exception:  # noqa: BLE001  (gone since: left out)
            continue
    return n


def hold(objs):
    """FreeCAD's selection set to objs (objects, or (object, sub) pairs)
    for a command's run, the person's saved first; hooks.selection_muted
    on until restore_to(). The mark to restore to. Without a window:
    nothing is done."""
    from . import hooks

    mark = len(_held)
    try:
        S = _sel()
    except Exception:  # noqa: BLE001  (no window)
        return mark
    rows = saved_rows()
    mute = hooks.selection_muted()
    mute.__enter__()
    _held.append((rows, mute))
    S.clearSelection()
    for x in objs or ():
        o, sub = x if isinstance(x, tuple) else (x, "")
        if sub:
            S.addSelection(o, sub)
        else:
            S.addSelection(o)
    return mark


def restore_to(mark=0):
    """Every selection held since mark put back, innermost first. How many."""
    n = 0
    while len(_held) > max(0, int(mark)):
        rows, mute = _held.pop()
        try:
            put_back(rows)
        except Exception as e:  # noqa: BLE001
            _log(f"Agent Link co-work (selection back): {e}\n")
        finally:
            mute.__exit__(None, None, None)
        n += 1
    return n


class held:
    """with held(objs): FreeCAD's selection is objs inside, the person's
    after (hold, restore_to)."""

    def __init__(self, objs):
        self.objs = objs
        self.mark = None

    def __enter__(self):
        self.mark = len(_held)
        try:
            hold(self.objs)
        except BaseException:
            restore_to(self.mark)
            raise
        return self

    def __exit__(self, *exc):
        restore_to(self.mark)
        return False
