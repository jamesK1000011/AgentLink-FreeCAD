# SPDX-License-Identifier: LGPL-2.1-or-later
# The Surface workbench's own parametric features, beside draft.py's plain
# surfaces: a surface through sections, one bounded by edges (stretched,
# Coons, curved), a surface extended past its edges, faces sewn into a shell
# (and a closed one made a solid), surfaces cut by one another, and blend
# curves joining two edges smoothly. Each follows the edges it was made from.

import Part
import Surface  # noqa: F401 — loads the Surface features; the family is left out without it

from .. import geometry as geo
from .. import runners
from ..protocol import bad
from . import picks

GROUP = "surface"
INFO = "Surface workbench features (parametric): sections, boundary surfaces (stretched/Coons/curved), extend, sewing into shells and solids, surface cuts, blend curves; surfaces filled across edges, lofted through curves, fitted to points or a polynomial, thickened into solids."


def reading(o):
    sh = o.Shape
    out = {"object": o.Label, "type": o.TypeId.split("::")[-1], "faces": len(sh.Faces), "edges": len(sh.Edges)}
    if sh.Faces:
        out["area"] = round(sh.Area, 3)
    if sh.Solids:
        out["volume"] = round(sh.Volume, 3)
    elif sh.Edges:
        out["length"] = round(sum(e.Length for e in sh.Edges), 3)
    out["shells"] = len(sh.Shells)
    out["closed"] = bool(sh.Shells and all(x.isClosed() for x in sh.Shells))
    return out


def chained(edges, closed=True, tol=1e-4):
    """Which boundary edges run backwards, so that each starts where the one
    before ends (the feature takes them as given): (flags, None). Where they
    do not chain: (None, why) — "open" (they meet, but the last does not
    come back to where the first starts), "corner" (two curves that share
    no end) or "order" (they do not meet end to end as listed)."""
    def ends(e):
        # The curve's own ends: the feature reverses the curve under the edge
        # (ReversedList), whichever way the edge is turned in its body.
        return e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)

    for first in (False, True):
        a0, a1 = ends(edges[0])
        start, cur = (a1, a0) if first else (a0, a1)
        flags, ok = [first], True
        for e in edges[1:]:
            b0, b1 = ends(e)
            if (b0 - cur).Length <= tol:
                flags.append(False)
                cur = b1
            elif (b1 - cur).Length <= tol:
                flags.append(True)
                cur = b0
            else:
                ok = False
                break
        if ok:
            if closed and (cur - start).Length > tol:
                return None, "open"
            return flags, None
    return None, "order" if closed else "corner"


def free_edges(sh):
    """The edges of a sewn shape with a face on one side only (where its shell is open); none when it has no shell."""
    return [e for e in sh.Edges if len(sh.ancestorsOfType(e, Part.Face)) < 2] if sh.Shells else []


def tools(session):
    s = session
    doc = lambda: s.doc

    def new(kind, label):
        lab = s.unique(label)
        o = doc().addObject(kind, label.replace(" ", ""))
        o.Label = lab
        return o

    def done(o, tool, extra=None, hint=""):
        return picks.finish(s, tool, lambda: reading(o), objs=[o], broken=lambda o: not o.isValid() or o.Shape.isNull(),
                            refuse="{kind} failed: {msg} — nothing was kept." + (" " + hint if hint else ""), extra=extra)

    def edge_ref(r, what):
        """"Body.Edge3", or a whole wire/sketch by name (all its edges)."""
        if not isinstance(r, str):
            raise bad(f"{what}: \"Body.Edge3\" or a wire's name.")
        label, sub, _ = picks.resolve(s, r)
        o = picks.find(doc(), label)
        if sub:
            if not sub.startswith("Edge"):
                raise bad(f"{what}: an edge, not {sub}.")
            return o, [sub]
        n = len(o.Shape.Edges)
        if not n:
            raise bad(f"{what}: {o.Label} has no edges.")
        return o, [f"Edge{i + 1}" for i in range(n)]

    # The tools themselves are data (agentlink/data/tools.json, run by
    # agentlink/runners.py's steps runner: docs/data-tools.md). What their
    # entries call by name:
    helpers = {"doc": doc, "new": new, "done": done, "edge_ref": edge_ref, "unique": lambda label, *own: s.unique(label, *own),
               "resolve": lambda ref: picks.resolve(s, ref), "find": lambda ref: picks.find(doc(), ref),
               "shaped": lambda ref, what: picks.shaped(doc(), ref, what), "num": picks.num, "clean": geo.clean,
               # FreeCAD's own
               "make_solid": Part.makeSolid,
               # the family's
               "chained": chained, "free_edges": free_edges}
    return runners.tools(GROUP, s, helpers)
