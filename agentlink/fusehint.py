# SPDX-License-Identifier: LGPL-2.1-or-later
# What to say when an additive step leaves a shape invalid (bicycle test
# drive, 20 Nov, finding 7): a pad fused a solid lug onto several hollow tube
# ends that met at one point, and the body was invalid (unorientable), with
# and without Refine. The health check (agentlink/health.py) calls this only
# on a shape that isValid() calls invalid, so no call pays for it otherwise.
#
# It names the step (the Body's tip when that is a pad, pipe, revolution,
# loft or other additive feature; a Part fuse itself), gives the design rule,
# and, in a short time, finds the tube bores (inner cylinder faces) of one
# input whose open ends lie inside another input: the case that broke.
# Duck-typed (Shape, Face, Surface as FreeCAD gives them): no FreeCAD import.

import re
import time

RULE = "end the tubes at the shell surface, or cut the bore after the fuse"
FUSES = ("Part::Fuse", "Part::MultiFuse")
KINDS = {"PartDesign::Pad": "pad", "PartDesign::Revolution": "revolution", "PartDesign::AdditivePipe": "pipe",
         "PartDesign::AdditiveLoft": "loft", "PartDesign::AdditiveHelix": "helix"}
BUDGET_S = 0.25   # the bore search, after which it stops with what it found
MAX_FACES = 400   # faces read per input
ERROR_WORDS = re.compile(r"not (?:a )?valid|invalid|unorientable|not a solid|boolean|\bBOP\b", re.I)


def kind(o):
    """"pad", "pipe" … for an additive PartDesign feature, "fuse" for a Part
    fuse or a PartDesign Boolean fuse; else None."""
    t = getattr(o, "TypeId", "") or ""
    if t in KINDS:
        return KINDS[t]
    if t.startswith("PartDesign::Additive"):
        return t[len("PartDesign::Additive"):].lower()
    if t in FUSES or (t == "PartDesign::Boolean" and getattr(o, "Type", "") == "Fuse"):
        return "fuse"
    return None


def _step(o):
    """(the step, its kind) that made o's shape: a Body's tip, or o."""
    if getattr(o, "TypeId", "") == "PartDesign::Body":
        o = getattr(o, "Tip", None)
    k = kind(o) if o is not None else None
    return (o, k) if k else (None, None)


def _shape(x):
    try:
        s = x.Shape if hasattr(x, "Shape") else x
        return None if s is None or (hasattr(s, "isNull") and s.isNull()) else s
    except Exception:
        return None


def _inputs(f, k):
    """[(label, shape)] of what the step joined."""
    out = []
    if k == "fuse":
        objs = list(getattr(f, "Shapes", None) or []) or [getattr(f, "Base", None), getattr(f, "Tool", None)]
        if getattr(f, "TypeId", "") == "PartDesign::Boolean":
            objs = [getattr(f, "BaseFeature", None)] + list(getattr(f, "Group", None) or [])
        for x in objs:
            s = _shape(x) if x is not None else None
            if s is not None:
                out.append((getattr(x, "Label", "?"), s))
        return out
    base = getattr(f, "BaseFeature", None)
    s = _shape(base) if base is not None else None
    if s is not None:
        out.append((getattr(base, "Label", "?"), s))
    try:
        add = f.AddSubShape
    except Exception:
        add = None
    if add is not None and not (hasattr(add, "isNull") and add.isNull()):
        out.append((getattr(f, "Label", "?"), add))
    return out


def _t(v):
    return (float(v.x), float(v.y), float(v.z))


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def bore(face):
    """Whether a face is the inside of a tube: a cylinder whose normal
    points to its axis."""
    s = getattr(face, "Surface", None)
    if s is None or type(s).__name__ != "Cylinder":
        return False
    u0, u1, v0, v1 = face.ParameterRange
    um, vm = (u0 + u1) / 2, (v0 + v1) / 2
    p, n = _t(face.valueAt(um, vm)), _t(face.normalAt(um, vm))
    c, a = _t(s.Center), _t(s.Axis)
    w = tuple(p[i] - c[i] for i in range(3))
    aa = _dot(a, a) or 1.0
    k = _dot(w, a) / aa
    radial = tuple(w[i] - a[i] * k for i in range(3))
    return _dot(radial, n) < 0


def end_inside(face, solid):
    """Whether an end of the bore (its edge at either end of its length)
    lies inside the solid, not on its faces."""
    u0, u1, v0, v1 = face.ParameterRange
    for v in (v0, v1):
        for j in range(4):
            p = face.valueAt(u0 + (u1 - u0) * j / 4, v)
            try:
                if solid.isInside(p, 1e-4, False):
                    return True
            except Exception:
                return False
    return False


def bores_inside(inputs, deadline):
    """[{of, face, radius}] for each tube bore of one input that ends inside
    another input."""
    found = []
    for i, (label, sh) in enumerate(inputs):
        others = [s for j, (_l, s) in enumerate(inputs) if j != i]
        try:
            faces = list(sh.Faces)[:MAX_FACES]
        except Exception:
            continue
        for n, f in enumerate(faces, 1):
            if time.time() > deadline:
                return found
            try:
                if bore(f) and any(end_inside(f, o) for o in others):
                    found.append({"of": label, "face": f"Face{n}", "radius": round(float(f.Surface.Radius), 3)})
            except Exception:
                continue
    return found


def todo(feature, k, body):
    check = f'body_check {{ body: "{body}" }}' if body else "body_check"
    return (f"{feature} ({k}) left the shape invalid. Design rule: {RULE} (a pocket or a hole through the joint); "
            f"history_undo, change it, then {check} to confirm")


def for_invalid(o):
    """For a part (a Body or a Part fuse) whose shape is invalid: the step
    that made it and what to do, or None when that step is not additive.
    {feature, kind, bores, line, todo}."""
    if o is None:
        return None
    f, k = _step(o)
    if f is None:
        return None
    label = getattr(f, "Label", "?")
    try:
        found = bores_inside(_inputs(f, k), time.time() + BUDGET_S)
    except Exception:
        found = []
    line = f"after {label} ({k})"
    if found:
        groups = {}
        for b in found:
            groups.setdefault(b["of"], []).append(b["face"])
        where = "; ".join(f"{of} {', '.join(fs)}" for of, fs in groups.items())
        line += f": {len(found)} tube bore{'s' if len(found) != 1 else ''} ({where}) end inside the new solid of {label}"
    return {"feature": label, "kind": k, "bores": found, "line": line, "todo": todo(label, k, getattr(o, "Label", ""))}


def for_error(feature, error):
    """The rule for a failed additive step whose error says the result is
    not a valid solid; else None."""
    k = kind(feature)
    if not k or not ERROR_WORDS.search(error or ""):
        return None
    return todo(getattr(feature, "Label", "?"), k, "")


# Bicycle L5 build (21 Nov, finding 4): PartDesign Refine on every feature
# of a large pipe weldment made the body unorientable (FreeCAD's Check
# Geometry) after small parameter changes; Refine off on all of them fixed it.
REFINE_PIPES = 8   # pipes in one body past which Refine is named on an invalid shape
UNORIENTABLE = re.compile(r"unorientable", re.I)
PIPES = ("PartDesign::AdditivePipe", "PartDesign::SubtractivePipe")


def refined(body):
    """[labels] of the body's features with Refine on, in order."""
    out = []
    for f in list(getattr(body, "Group", None) or []):
        try:
            if "Refine" in (getattr(f, "PropertiesList", None) or ()) and bool(getattr(f, "Refine", False)):
                out.append(getattr(f, "Label", "?"))
        except Exception:
            continue
    return out


def refine_todo(body, said=""):
    """The todo for an invalid or unorientable PartDesign Body whose
    features have Refine on, when the words say unorientable or the body
    holds more than REFINE_PIPES pipes; else None."""
    if getattr(body, "TypeId", "") != "PartDesign::Body":
        return None
    on = refined(body)
    if not on:
        return None
    pipes = sum(1 for f in (getattr(body, "Group", None) or []) if getattr(f, "TypeId", "") in PIPES)
    if not (UNORIENTABLE.search(said or "") or pipes > REFINE_PIPES):
        return None
    names = ", ".join(on[:5]) + (f" and {len(on) - 5} more" if len(on) > 5 else "")
    return (f"Refine off on the features (object_set {{ object: \"{on[0]}\", values: {{ Refine: false }} }} on each: {names}), then rebuild "
            f"(recompute) and body_check {{ body: \"{getattr(body, 'Label', '')}\" }}: Refine on the features of a weldment of many pipes ({pipes}) can leave it unorientable after a change")
