# SPDX-License-Identifier: LGPL-2.1-or-later
"""The 3D view's annotation layer: coin nodes drawn in the scene graph
beside the model, never in the document and never through FreeCAD's
selection (the person's picks stay theirs). The panel's note pins and its
Steps stage draw here; add-ons light a face, an edge or a vertex through
the service hooks.service("annotations"):

    ann = hooks.service("annotations")
    ann.light(obj, ["Face6", "Edge3"], owner="mine", colour="#3f93e0", badge=2)
        -> {"lit": ["Face6", "Edge3"], "missing": []}
    ann.clear("mine")

A face is its triangulation tinted under an SoAnnotation (drawn over the
model, offset so it never flickers into it); an edge a thick line; a
vertex a marker. Shapes are taken where they sit in the scene (the body's
placement included).

A badge is drawn in screen space at the screen's pixel density (a disc and
a bold number, legible at any zoom on a Retina screen), at a point of the
element the person can see from where the camera is when it is drawn: the
point nearest the element's centre whose pixel shows that element, not one
hidden under another part (a screw over the face's middle). Without a view
to ask, the point of the element nearest its centre.

A result's colour map (field) is drawn pulled in front of the surface it
lies on and never picked; its colour scale (legend) in screen space at the
right of the view, as FreeCAD's colour bar sits, left out of Fit all.
"""

import sys

TINT_TRANSPARENCY = 0.35
EDGE_WIDTH = 5.0
EDGE_POINTS = 64
TESS = 0.1  # mm: the face's triangulation tolerance
BADGE_FONT = 22  # logical pixels; times the screen's pixel ratio
BADGE_DISC = 21  # logical pixels across, likewise
BADGE_SAMPLES = 48  # points of a face or edge tried for a visible one
# A field drawn this far in front of its surface (SoPolygonOffset factor,
# units; negative pulls towards the camera).
FIELD_OFFSET = (-1.0, -4.0)
LEGEND_TICKS = 5
LEGEND_FONT = 13  # logical pixels; times the screen's pixel ratio
LEGEND_GAP = 0.12  # screen units (10 the view's height) between bar and words
LEGEND_RATIO = 1.6  # a view's width / height when none tells
LEGEND_HEIGHT_PX = 800
LEGEND_PANEL_TRANSPARENCY = 0.15
LEGEND_INK = (0.08, 0.08, 0.08)


def _view():
    import FreeCADGui

    gd = FreeCADGui.ActiveDocument
    return gd.activeView() if gd else None


def _scene():
    v = _view()
    return v.getSceneGraph() if v and hasattr(v, "getSceneGraph") else None


def rgbf(hex_):
    h = str(hex_).lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def kind_of(sub):
    """"face", "edge", "vertex" or None for a sub-element's name."""
    for k, n in (("Face", "face"), ("Edge", "edge"), ("Vertex", "vertex")):
        if str(sub).startswith(k) and str(sub)[len(k):].isdigit():
            return n
    return None


def face_mesh(face, tol=TESS):
    """(points, indices) of a face's triangulation: coin's flat index list,
    each triangle closed with -1."""
    pts, tris = face.tessellate(tol)
    points = [(p.x, p.y, p.z) if hasattr(p, "x") else tuple(p) for p in pts]
    idx = []
    for t in tris:
        idx += [int(t[0]), int(t[1]), int(t[2]), -1]
    return points, idx


def edge_line(edge, n=EDGE_POINTS):
    pts = edge.discretize(Number=n) if hasattr(edge, "discretize") else []
    return [(p.x, p.y, p.z) if hasattr(p, "x") else tuple(p) for p in pts]


def centre_of(el, kind):
    """Where a sub-element's badge goes: a face's or edge's centre of mass
    (an edge's middle when it has none), a vertex's point."""
    if kind == "vertex":
        p = el.Point
    else:
        p = getattr(el, "CenterOfMass", None)
        if p is None and kind == "edge":
            a, b = el.FirstParameter, el.LastParameter
            p = el.valueAt((a + b) / 2.0)
    return (p.x, p.y, p.z)


def candidates(el, kind, n=BADGE_SAMPLES):
    """Points of a sub-element where its badge may go, nearest its centre
    first: a face's triangle middles (always on the face, unlike the centre
    of mass of a ring or an L), an edge's points along it, a vertex's point."""
    if kind == "vertex":
        return [centre_of(el, kind)]
    c = centre_of(el, kind)
    if kind == "edge":
        pts = edge_line(el, max(n, 2))
    else:
        points, idx = face_mesh(el)
        pts = []
        for i in range(0, len(idx), 4):
            a, b, d = (points[j] for j in idx[i:i + 3])
            pts.append(tuple((a[k] + b[k] + d[k]) / 3.0 for k in range(3)))
    if not pts:
        return [c]
    pts.sort(key=lambda p: sum((p[k] - c[k]) ** 2 for k in range(3)))
    if len(pts) > n:  # the nearest half, then the rest evenly spread
        head, rest = pts[:n // 2], pts[n // 2:]
        k = n - len(head)
        pts = head + [rest[int(i * len(rest) / k)] for i in range(k)]
    return pts if kind == "face" else [c] + pts


def _names(obj):
    """obj's name and the names the view may report for its pixels: its
    body's, and the body's tip."""
    out = {getattr(obj, "Name", None)}
    for o in [obj] + list(getattr(obj, "InList", None) or []):
        out.add(getattr(o, "Name", None))
        out.add(getattr(getattr(o, "Tip", None), "Name", None))
    out.discard(None)
    return out


BADGE_CLEAR = 14  # logical pixels around the badge's point that should show the element too
PICKS_MAX = 160  # pixels asked of the view at most, per badge


def visible_point(view, obj, sub, points, clear=BADGE_CLEAR):
    """The first of points whose pixel, and the pixels clear away from it on
    four sides, show obj's sub in view (room for the badge, not hard by a
    screw's rim); else the first whose own pixel does; else None.
    view: FreeCAD's 3D view (getPointOnScreen, getObjectInfo, getSize)."""
    if view is None or not points:
        return None
    try:
        import FreeCAD

        vec = FreeCAD.Vector
    except ImportError:
        vec = None
    names = _names(obj)
    try:
        w, h = view.getSize()
    except Exception:
        w = h = None
    picks = [0]

    def shows(x, y):
        if w is not None and not (0 <= x < w and 0 <= y < h):
            return False
        picks[0] += 1
        try:
            info = view.getObjectInfo((int(x), int(y)))
        except Exception:
            return False
        return bool(info) and info.get("Component") == sub and info.get("Object") in names

    first = None
    for p in points:
        if picks[0] >= PICKS_MAX:
            break
        try:
            x, y = view.getPointOnScreen(vec(*p) if vec else p)
        except Exception:
            continue
        if not shows(x, y):
            continue
        if first is None:
            first = p
        if all(shows(x + dx, y + dy) for dx, dy in ((clear, 0), (-clear, 0), (0, clear), (0, -clear))):
            return p
    return first


def _ratio():
    """The screen's pixel ratio (2 on a Retina screen), 1 when unknown."""
    try:
        import FreeCADGui

        mw = FreeCADGui.getMainWindow()
        r = float(mw.devicePixelRatioF() if hasattr(mw, "devicePixelRatioF") else mw.devicePixelRatio())
        return r if r >= 1 else 1.0
    except Exception:
        return 1.0


def _disc(want):
    """FreeCAD's filled-circle marker of the largest size it has up to want
    pixels (it falls back to 9 for a size it lacks)."""
    import FreeCADGui

    small = FreeCADGui.getMarkerIndex("CIRCLE_FILLED", 9)
    size = int(want) | 1
    while size > 9:
        got = FreeCADGui.getMarkerIndex("CIRCLE_FILLED", size)
        if got != small:
            return got
        size -= 2
    return small


def global_shape(obj):
    """obj's shape where it is drawn (its placement and its body's)."""
    try:
        import Part

        sh = Part.getShape(obj, "", needSubElement=False, transform=True)
        if sh is not None and not sh.isNull():
            return sh
    except Exception:
        pass
    return getattr(obj, "Shape", None)


class Annotations:
    """hooks.service("annotations"). coin and scene are given in tests."""

    def __init__(self, coin=None, scene=None, view=None, ratio=None):
        self._coin = coin
        self._scene_fn = scene or _scene
        self._view_fn = view or (_view if scene is None else (lambda: None))
        self._ratio_fn = ratio or _ratio
        self.roots = {}  # owner -> (scene graph, separator)
        self.fields = {}  # owner -> the last field's nodes (field_facts)

    def coin(self):
        if self._coin is None:
            from pivy import coin

            self._coin = coin
        return self._coin

    def _root(self, owner):
        coin = self.coin()
        sg = self._scene_fn()
        got = self.roots.get(owner)
        if got is not None and holds(sg, got[0], got[1]):
            return got[1]
        if got is not None:
            self.clear(owner)
        if sg is None:
            return None
        sep = coin.SoSeparator()
        sep.setName("AgentLinkAnnotations")
        sg.addChild(sep)
        self.roots[owner] = (sg, sep)
        return sep

    def root(self, owner):
        """The owner's group in the active view's scene (made when there is
        none), or None without a 3D view."""
        return self._root(owner)

    def light(self, obj, subs, owner="", colour="#3f93e0", shape=None, badge=None):
        """Draw each of subs (Face6, Edge3, Vertex1) of obj. {lit, missing:
        [(sub, why)]}. badge: a number drawn on the first lit one, at a
        point of it the person can see (badge_at), over the model and facing
        the screen, so several targets read in order in the view too."""
        lit, missing = [], []
        try:
            shape = shape if shape is not None else global_shape(obj)
            root = self._root(owner)
        except Exception as e:  # noqa: BLE001
            return {"lit": [], "missing": [(s, f"no 3D view ({type(e).__name__})") for s in subs]}
        if root is None:
            return {"lit": [], "missing": [(s, "no 3D view open") for s in subs]}
        coin = self.coin()
        col = rgbf(colour)
        for sub in subs:
            k = kind_of(sub)
            if k is None:
                missing.append((sub, "not a face, edge or vertex name"))
                continue
            try:
                el = shape.getElement(sub)
            except Exception:
                missing.append((sub, f"{getattr(obj, 'Label', '?')} has no {sub}"))
                continue
            node = coin.SoAnnotation()
            mat = coin.SoMaterial()
            mat.diffuseColor = col
            mat.emissiveColor = col
            node.addChild(mat)
            if k == "face":
                points, idx = face_mesh(el)
                mat.transparency = TINT_TRANSPARENCY
                off = coin.SoPolygonOffset()
                co = coin.SoCoordinate3()
                co.point.setValues(0, len(points), points)
                fs = coin.SoIndexedFaceSet()
                fs.coordIndex.setValues(0, len(idx), idx)
                for c in (off, co, fs):
                    node.addChild(c)
            elif k == "edge":
                points = edge_line(el)
                st = coin.SoDrawStyle()
                st.lineWidth = EDGE_WIDTH
                co = coin.SoCoordinate3()
                co.point.setValues(0, len(points), points)
                ls = coin.SoLineSet()
                ls.numVertices.setValue(len(points))
                for c in (st, co, ls):
                    node.addChild(c)
            else:
                p = el.Point
                co = coin.SoCoordinate3()
                co.point.setValue(p.x, p.y, p.z)
                ms = coin.SoMarkerSet()
                for c in (co, ms):
                    node.addChild(c)
            root.addChild(node)
            if badge is not None and not lit:
                try:
                    root.addChild(self._badge(self.badge_at(obj, sub, el, k), badge, col))
                except Exception as e:  # noqa: BLE001  (the light stays; the number is a nicety)
                    sys.stderr.write(f"Agent Link: annotation badge not drawn ({type(e).__name__}: {e})\n")
            lit.append(sub)
        return {"lit": lit, "missing": missing}

    def badge_at(self, obj, sub, el, kind):
        """Where the badge goes: the point of the element nearest its centre
        that the view shows (not under another part), else the nearest on it."""
        pts = candidates(el, kind)
        try:
            view = self._view_fn()
        except Exception:
            view = None
        return visible_point(view, obj, sub, pts) or pts[0]

    def _badge(self, at, n, col):
        """A filled disc and the bold number beside it at point at, both in
        screen pixels times the screen's pixel ratio."""
        coin = self.coin()
        try:
            ratio = float(self._ratio_fn())
        except Exception:
            ratio = 1.0
        node = coin.SoAnnotation()
        mat = coin.SoMaterial()
        mat.diffuseColor = col
        mat.emissiveColor = col
        tr = coin.SoTranslation()
        tr.translation = tuple(at)
        co = coin.SoCoordinate3()
        co.point.setValue(0, 0, 0)
        dot = coin.SoMarkerSet()
        try:
            dot.markerIndex = _disc(BADGE_DISC * ratio)
        except Exception:
            pass
        font = coin.SoFont()
        font.name = "Arial:Bold"
        font.size = round(BADGE_FONT * ratio)
        txt = coin.SoText2()
        txt.string = f"  {n}"
        for c in (mat, tr, co, dot, font, txt):
            node.addChild(c)
        return node

    def marks(self, owner, points=(), lines=(), colour="#e8a33d", size=9, labels=()):
        """Scene-only marks (round 6): a marker at each point (x, y, z) and a
        line through each list of points, drawn over the model, and a word
        beside each point of labels [((x, y, z), text)] (a line and dots
        alone did not say what they were: core 0081-0092). For what has
        no drawing of its own (a robot with no model file: its base and
        tool point, the trajectory). The count drawn (labels not counted),
        0 with no 3D view."""
        root = self._root(owner)
        if root is None:
            return 0
        coin = self.coin()
        col = rgbf(colour)
        node = coin.SoAnnotation()
        mat = coin.SoMaterial()
        mat.diffuseColor = col
        mat.emissiveColor = col
        node.addChild(mat)
        st = coin.SoDrawStyle()
        st.lineWidth = EDGE_WIDTH
        st.pointSize = size
        node.addChild(st)
        n = 0
        for line in lines or ():
            pts = [tuple(float(c) for c in p) for p in line]
            if len(pts) < 2:
                continue
            sep = coin.SoSeparator()
            co = coin.SoCoordinate3()
            co.point.setValues(0, len(pts), pts)
            ls = coin.SoLineSet()
            ls.numVertices.setValue(len(pts))
            sep.addChild(co)
            sep.addChild(ls)
            node.addChild(sep)
            n += 1
        pts = [tuple(float(c) for c in p) for p in points or ()]
        if pts:
            sep = coin.SoSeparator()
            co = coin.SoCoordinate3()
            co.point.setValues(0, len(pts), pts)
            ms = coin.SoMarkerSet()
            try:
                ms.markerIndex = coin.SoMarkerSet.CIRCLE_FILLED_9_9
            except Exception:  # noqa: BLE001
                pass
            sep.addChild(co)
            sep.addChild(ms)
            node.addChild(sep)
            n += len(pts)
        try:
            ratio = float(self._ratio_fn())
        except Exception:  # noqa: BLE001
            ratio = 1.0
        for at, text in labels or ():
            try:
                sep = coin.SoSeparator()
                tr = coin.SoTranslation()
                tr.translation = tuple(float(c) for c in at)
                font = coin.SoFont()
                font.name = "Arial:Bold"
                font.size = round(BADGE_FONT * 0.7 * ratio)
                txt = coin.SoText2()
                txt.string = "  " + str(text)
                for c in (tr, font, txt):
                    sep.addChild(c)
                node.addChild(sep)
            except Exception:  # noqa: BLE001
                continue
        root.addChild(node)
        return n

    def field(self, owner, V, F, colours, per_face=False):
        """A coloured triangle mesh drawn in the scene only (round 6): V
        (n, 3) points, F (m, 3) triangles, colours (n, 3) per point, or
        (m, 3) per triangle with per_face. A result's colour map shown on
        the model in the window, never as a property of a document object.
        The triangles drawn, 0 with no 3D view."""
        root = self._root(owner)
        if root is None:
            return 0
        coin = self.coin()
        V = [tuple(float(c) for c in p) for p in V]
        F = [tuple(int(i) for i in t) for t in F]
        cols = [tuple(float(c) for c in x) for x in colours]
        if not V or not F:
            return 0
        sep = coin.SoSeparator()
        sep.addChild(_unpickable(coin))
        # Pulled in front of the surface it lies on (round 7). A plain
        # SoPolygonOffset (factor 1, units 1) pushes polygons away from the
        # camera: under a mesh in Shaded mode (no offset) the map was never
        # seen (mesh 009, 012), and on a Part body or a mesh in Flat Lines
        # (the same 1, 1: ViewProviderExt.cpp 504, Mesh ViewProvider.cpp 466)
        # it fought the faces and the selection's green in stripes (fem 034).
        off = coin.SoPolygonOffset()
        off.factor = FIELD_OFFSET[0]
        off.units = FIELD_OFFSET[1]
        sep.addChild(off)
        mat = coin.SoMaterial()
        mat.diffuseColor.setValues(0, len(cols), cols)
        bind = coin.SoMaterialBinding()
        bind.value = coin.SoMaterialBinding.PER_FACE if per_face else coin.SoMaterialBinding.PER_VERTEX_INDEXED
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.COUNTERCLOCKWISE
        co = coin.SoCoordinate3()
        co.point.setValues(0, len(V), V)
        fs = coin.SoIndexedFaceSet()
        idx = []
        for t in F:
            idx += [t[0], t[1], t[2], -1]
        fs.coordIndex.setValues(0, len(idx), idx)
        if not per_face:
            fs.materialIndex.setValues(0, len(idx), idx)
        for c in (mat, bind, hints, co, fs):
            sep.addChild(c)
        root.addChild(sep)
        self.fields[owner] = {"sep": sep, "off": off, "mat": mat, "bind": bind, "co": co, "fs": fs, "perFace": bool(per_face)}
        return len(F)

    def field_facts(self, owner, hidden=()):
        """Where the last field of owner sits and how it is drawn, read from
        the scene (round 8: a map made of 19998 triangles was not seen). The
        chain of nodes from the view's top to the field (type and name),
        each switch's whichChild on it, whether a hidden object's node
        (hidden: those objects' RootNode) is on it, how many of our roots
        hang in the scene graph, the material binding, the colour, point
        and index counts, the polygon offset. Never raises."""
        out = {}
        try:
            got = self.fields.get(owner)
            if not got:
                return {"field": None}
            sg = self._scene_fn()
            top = self._full_scene() or sg
            out["annotationRoots"] = sum(1 for k in _kids(sg) if _name_of(k) == "AgentLinkAnnotations") if sg is not None else 0
            have = self.roots.get(owner)
            out["rootInScene"] = bool(have and holds(sg, have[0], have[1]))
            path = _path_to(self.coin(), top, got["sep"])
            out["inScene"] = path is not None
            path = path or []
            out["chain"] = [f"{_type_of(n)}:{_name_of(n)}" if _name_of(n) else _type_of(n) for n in path]
            out["switches"] = [{"node": f"{_type_of(n)}:{_name_of(n)}", "whichChild": _which(n)} for n in path if "Switch" in _type_of(n)]
            out["throughHidden"] = [str(lb) for lb, rn in hidden if rn is not None and any(_same(n, rn) for n in path)]
            out["binding"] = _value(got["bind"].value)
            out["perFace"] = got["perFace"]
            out["colours"] = _count(got["mat"].diffuseColor)
            out["points"] = _count(got["co"].point)
            out["indices"] = _count(got["fs"].coordIndex)
            out["materialIndex"] = _count(got["fs"].materialIndex)
            out["offset"] = [_value(got["off"].factor), _value(got["off"].units)]
            out["children"] = len(_kids(got["sep"]))
        except Exception as e:  # noqa: BLE001
            out["error"] = f"{type(e).__name__}: {e}"
        return out

    def _full_scene(self):
        """The scene the view renders, with its camera and lights (the
        render manager's), or None."""
        try:
            v = self._view_fn()
            return v.getViewer().getSoRenderManager().getSceneGraph()
        except Exception:  # noqa: BLE001
            return None

    def legend(self, owner, title, unit, lo, hi, stops, ticks=LEGEND_TICKS):
        """A colour scale drawn in screen space at the right of the 3D view,
        as FreeCAD's own colour bar sits (SoFCColorBar.cpp: the foreground's
        orthographic camera, height 10): the bar in the map's colours (stops:
        [(t 0..1, (r, g, b))], low at the bottom), ticks values from lo to hi
        beside it, the title and the unit above it, on a pale panel. Scene
        only (round 7, fem 034: no colour scale): left out of the view's
        bounding box (FreeCAD's SoSkipBoundingGroup, so Fit all ignores it),
        never picked, over the model. {labels, title} drawn, or None with no
        3D view."""
        root = self._root(owner)
        if root is None:
            return None
        coin = self.coin()
        w, h = self._size()
        lay = legend_layout(w / float(h) if h else LEGEND_RATIO)
        heading = f"{title} ({unit})" if unit else str(title)
        labels = legend_labels(lo, hi, ticks)
        font = round(LEGEND_FONT * self._ratio())
        per_px = 10.0 / float(h or LEGEND_HEIGHT_PX)
        chars = max([len(t) for _y, t in labels] + [1])
        left = lay["x0"] - LEGEND_GAP - chars * 0.6 * font * per_px - 0.15
        left = min(left, lay["x1"] - len(heading) * 0.6 * font * per_px - 0.15)
        hud = coin.SoAnnotation()
        for c in (_unpickable(coin), self._hud_camera(), _base_colour_light(coin)):
            hud.addChild(c)
        # the pale panel behind it all
        hud.addChild(_quad(coin, left, lay["y0"] - 0.3, lay["x1"] + 0.15, lay["title_y"] + 0.45, [(0.97, 0.97, 0.97)] * 4, LEGEND_PANEL_TRANSPARENCY))
        # the bar: a strip of quads, colours per vertex, low at the bottom
        stops = sorted((float(t), tuple(float(c) for c in rgb)) for t, rgb in stops) or [(0.0, (0, 0, 1)), (1.0, (1, 0, 0))]
        pts, cols, idx = [], [], []
        for i, (t, rgb) in enumerate(stops):
            y = lay["y0"] + (lay["y1"] - lay["y0"]) * t
            pts += [(lay["x0"], y, 0.0), (lay["x1"], y, 0.0)]
            cols += [rgb, rgb]
            if i:
                a = 2 * (i - 1)
                idx += [a, a + 1, a + 3, a + 2, -1]
        bar = coin.SoSeparator()
        mat = coin.SoMaterial()
        mat.diffuseColor.setValues(0, len(cols), cols)
        bind = coin.SoMaterialBinding()
        bind.value = getattr(coin.SoMaterialBinding, "PER_VERTEX_INDEXED", 0)
        co = coin.SoCoordinate3()
        co.point.setValues(0, len(pts), pts)
        fs = coin.SoIndexedFaceSet()
        fs.coordIndex.setValues(0, len(idx), idx)
        fs.materialIndex.setValues(0, len(idx), idx)
        for c in (mat, bind, co, fs):
            bar.addChild(c)
        hud.addChild(bar)
        # the words, dark on the pale panel
        ink = coin.SoBaseColor()
        ink.rgb = LEGEND_INK
        hud.addChild(ink)
        f = coin.SoFont()
        f.name = "Arial"
        f.size = font
        hud.addChild(f)
        right = getattr(coin.SoText2, "RIGHT", 1)
        for t, text in labels:
            y = lay["y0"] + (lay["y1"] - lay["y0"]) * t
            hud.addChild(_text(coin, (lay["x0"] - LEGEND_GAP, y - 0.5 * font * per_px * 0.7, 0.0), text, right))
        hud.addChild(_text(coin, (lay["x1"], lay["title_y"], 0.0), heading, right))
        group = _skip_bounding(coin)
        group.addChild(hud)
        root.addChild(group)
        return {"labels": [t for _y, t in labels], "title": heading}

    def _size(self):
        """The 3D view's size in pixels, (LEGEND_RATIO x 1) x LEGEND_HEIGHT_PX
        when no view tells."""
        try:
            v = self._view_fn()
            w, h = v.getSize()
            if w > 0 and h > 0:
                return int(w), int(h)
        except Exception:  # noqa: BLE001
            pass
        return int(LEGEND_HEIGHT_PX * LEGEND_RATIO), LEGEND_HEIGHT_PX

    def _ratio(self):
        try:
            return float(self._ratio_fn())
        except Exception:  # noqa: BLE001
            return 1.0

    def _hud_camera(self):
        """The camera FreeCAD's foreground uses (View3DInventorViewer.cpp
        527-531): screen y from -5 to 5, x as far as the view is wide."""
        cam = self.coin().SoOrthographicCamera()
        cam.position = (0.0, 0.0, 5.0)
        cam.height = 10.0
        cam.nearDistance = 0.0
        cam.farDistance = 10.0
        return cam

    def clear(self, owner=None):
        for k in [k for k in self.fields if owner is None or k == owner]:
            self.fields.pop(k, None)
        for k in [k for k in self.roots if owner is None or k == owner]:
            sg, sep = self.roots.pop(k)
            try:
                sg.removeChild(sep)
            except Exception as e:  # noqa: BLE001  (a closed view)
                sys.stderr.write(f"Agent Link: annotations not removed ({type(e).__name__}: {e})\n")


# ---- the colour scale (round 7) --------------------------------------------



def legend_value(v):
    """A scale's number, short: 444, 12.3, 0.0123, 1.2e-05."""
    v = float(v)
    a = abs(v)
    if a == 0:
        return "0"
    if a >= 100:
        return f"{v:.0f}"
    if a >= 1e-3:
        return f"{v:.3g}"
    return f"{v:.2g}"


def legend_labels(lo, hi, n=LEGEND_TICKS):
    """[(t 0..1 up the bar, words)] for n ticks from lo to hi (at least 2)."""
    n = max(2, int(n))
    lo, hi = float(lo), float(hi)
    return [(i / (n - 1.0), legend_value(lo + (hi - lo) * i / (n - 1.0))) for i in range(n)]


def legend_layout(ratio):
    """Where the bar goes in the foreground camera's units (the view's height
    is 10, from -5 to 5; its width 10 x ratio): at the right edge, below the
    navigation cube's corner, as FreeCAD's colour bar (SoFCColorBar.cpp
    getBounds). {x0, x1, y0, y1, title_y}."""
    r = float(ratio) if ratio and ratio > 0 else LEGEND_RATIO
    half_w = 5.0 * r if r >= 1 else 5.0
    half_h = 5.0 if r >= 1 else 5.0 / r
    x1 = half_w - 0.35
    y1 = min(2.4, half_h - 2.4)
    y0 = max(-3.4, -half_h + 0.8)
    return {"x0": x1 - 0.35, "x1": x1, "y0": y0, "y1": y1, "title_y": y1 + 0.35}


def holds(sg, kept, sep):
    """Whether sg, the scene graph now, is the one sep was put in (kept). A
    pivy proxy is made anew at every getSceneGraph(): "is" was never true
    there, so each drawing for an owner took away the one before it (round
    8: the colour scale took away the stress and curvature maps; a map
    alone, the segments, was seen). The same scene when it still has sep
    as a child. Never raises."""
    if sg is None:
        return False
    if sg is kept:
        return True
    try:
        return sg.findChild(sep) >= 0
    except Exception:  # noqa: BLE001
        return False


def _same(a, b):
    """The same scene node behind two proxies. Never raises."""
    if a is b:
        return True
    try:
        return int(a.this) == int(b.this)
    except Exception:  # noqa: BLE001
        return False


def _kids(node):
    try:
        if hasattr(node, "getNumChildren"):
            return [node.getChild(i) for i in range(node.getNumChildren())]
    except Exception:  # noqa: BLE001
        return []
    return list(getattr(node, "children", None) or ())


def _type_of(node):
    try:
        return node.getTypeId().getName().getString()
    except Exception:  # noqa: BLE001
        return str(getattr(node, "kind", type(node).__name__))


def _name_of(node):
    try:
        return node.getName().getString()
    except Exception:  # noqa: BLE001
        return str(getattr(node, "name", "") or "")


def _value(field):
    try:
        return field.getValue()
    except Exception:  # noqa: BLE001
        return field


def _count(field):
    try:
        return int(field.getNum())
    except Exception:  # noqa: BLE001
        vals = getattr(field, "vals", None)
        return len(vals) if isinstance(vals, (list, tuple)) else None


def _which(node):
    try:
        return int(node.whichChild.getValue())
    except Exception:  # noqa: BLE001
        pass
    try:
        return str(node.getField("whichChild").get())
    except Exception:  # noqa: BLE001
        return getattr(node, "whichChild", None)


PATH_LOOK_MOST = 50000


def _path_to(coin, top, node):
    """The nodes from top down to node, or None. Coin's SoSearchAction on
    a real scene; a walk of children on stand-ins."""
    if top is None:
        return None
    if hasattr(top, "getNumChildren"):
        try:
            sa = coin.SoSearchAction()
            sa.setNode(node)
            sa.setInterest(coin.SoSearchAction.FIRST)
            sa.setSearchingAll(True)  # into switches that are off, too
            sa.apply(top)
            p = sa.getPath()
            if p is None:
                return None
            return [p.getNode(i) for i in range(p.getLength())]
        except Exception:  # noqa: BLE001
            pass
    seen = [0]

    def walk(n, trail):
        seen[0] += 1
        if seen[0] > PATH_LOOK_MOST:
            return None
        trail = trail + [n]
        if _same(n, node):
            return trail
        for k in _kids(n):
            got = walk(k, trail)
            if got is not None:
                return got
        return None

    return walk(top, [])


def _unpickable(coin):
    ps = coin.SoPickStyle()
    ps.style = getattr(coin.SoPickStyle, "UNPICKABLE", 2)
    return ps


def _base_colour_light(coin):
    lm = coin.SoLightModel()
    lm.model = getattr(coin.SoLightModel, "BASE_COLOR", 0)
    return lm


def _quad(coin, x0, y0, x1, y1, cols, transparency=0.0):
    sep = coin.SoSeparator()
    mat = coin.SoMaterial()
    mat.diffuseColor.setValues(0, len(cols), cols)
    mat.transparency = transparency
    co = coin.SoCoordinate3()
    pts = [(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0)]
    co.point.setValues(0, 4, pts)
    fs = coin.SoIndexedFaceSet()
    fs.coordIndex.setValues(0, 5, [0, 1, 2, 3, -1])
    for c in (mat, co, fs):
        sep.addChild(c)
    return sep


def _text(coin, at, words, justification):
    sep = coin.SoSeparator()
    tr = coin.SoTranslation()
    tr.translation = tuple(at)
    t = coin.SoText2()
    t.string = str(words)
    t.justification = justification
    sep.addChild(tr)
    sep.addChild(t)
    return sep


def _skip_bounding(coin):
    """FreeCAD's SoSkipBoundingGroup set to leave its children out of the
    bounding box (Fit all, the clipping planes), else a plain group. The
    legend's coordinates are the screen's, not the model's."""
    try:
        t = coin.SoType.fromName("SoSkipBoundingGroup")
        if not t.isBad():
            g = t.createInstance()
            g.getField("mode").set("EXCLUDE_BBOX")
            return g
    except Exception:  # noqa: BLE001
        pass
    return coin.SoGroup()


_SERVICE = None


def service():
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = Annotations()
    return _SERVICE
