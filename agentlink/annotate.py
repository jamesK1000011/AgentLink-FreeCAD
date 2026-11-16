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
"""

import sys

TINT_TRANSPARENCY = 0.35
EDGE_WIDTH = 5.0
EDGE_POINTS = 64
TESS = 0.1  # mm: the face's triangulation tolerance
BADGE_FONT = 18


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

    def __init__(self, coin=None, scene=None):
        self._coin = coin
        self._scene_fn = scene or _scene
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
        [(sub, why)]}. badge: a number drawn at the first lit one's centre
        (over the model, facing the screen), so several targets read in
        order in the view too."""
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
                    root.addChild(self._badge(centre_of(el, k), badge, col))
                except Exception as e:  # noqa: BLE001  (the light stays; the number is a nicety)
                    sys.stderr.write(f"Agent Link: annotation badge not drawn ({type(e).__name__}: {e})\n")
            lit.append(sub)
        return {"lit": lit, "missing": missing}

    def _badge(self, at, n, col):
        """A filled dot and the number beside it at point at."""
        coin = self.coin()
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
            import FreeCADGui

            dot.markerIndex = FreeCADGui.getMarkerIndex("CIRCLE_FILLED", 13)
        except Exception:
            pass
        font = coin.SoFont()
        font.size = BADGE_FONT
        txt = coin.SoText2()
        txt.string = f"  {n}"
        for c in (mat, tr, co, dot, font, txt):
            node.addChild(c)
        return node

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
