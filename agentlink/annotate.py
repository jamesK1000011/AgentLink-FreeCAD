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
"""

import sys

TINT_TRANSPARENCY = 0.35
EDGE_WIDTH = 5.0
EDGE_POINTS = 64
TESS = 0.1  # mm: the face's triangulation tolerance
BADGE_FONT = 22  # logical pixels; times the screen's pixel ratio
BADGE_DISC = 21  # logical pixels across, likewise
BADGE_SAMPLES = 48  # points of a face or edge tried for a visible one


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

    def coin(self):
        if self._coin is None:
            from pivy import coin

            self._coin = coin
        return self._coin

    def _root(self, owner):
        coin = self.coin()
        sg = self._scene_fn()
        got = self.roots.get(owner)
        if got is not None and got[0] is sg:
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

    def marks(self, owner, points=(), lines=(), colour="#e8a33d", size=9):
        """Scene-only marks (round 6): a marker at each point (x, y, z) and a
        line through each list of points, drawn over the model. For what has
        no drawing of its own (a robot with no model file: its base and
        tool point, the trajectory). The count drawn, 0 with no 3D view."""
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
        # Drawn a hair in front of the surface it lies on (the body or mesh
        # it colours stays shown under it), as the face tint is.
        sep.addChild(coin.SoPolygonOffset())
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
        return len(F)

    def clear(self, owner=None):
        for k in [k for k in self.roots if owner is None or k == owner]:
            sg, sep = self.roots.pop(k)
            try:
                sg.removeChild(sep)
            except Exception as e:  # noqa: BLE001  (a closed view)
                sys.stderr.write(f"Agent Link: annotations not removed ({type(e).__name__}: {e})\n")


_SERVICE = None


def service():
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = Annotations()
    return _SERVICE
