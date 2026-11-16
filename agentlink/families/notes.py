# SPDX-License-Identifier: LGPL-2.1-or-later
# Notes pinned to the parts, between the person and the agent, and the build
# played back step by step. Both inspired by Stefan Hermann's ScanRuler (CNC
# Kitchen): its Reverse engineer panel pins notes to the part — the person
# writes and ticks them off, the agent answers them and pins questions of
# its own — and plays the feature list from the top with a caption a step,
# so a recording shows how the part was built. Here the same ideas over a
# FreeCAD document; the window's panel (agentlink/panel.py) shows them.
#
# A note is no step of the model and no step of the undo history: it lives
# in the document's Meta (store.py), saved with the .FCStd.

import datetime
import os

from .. import facepick, render, store
from .. import paths
from ..protocol import Tool, ToolError
from ..tools import obj

GROUP = "notes"
INFO = "Notes pinned to the parts between the person and the agent; the build played back step by step, a picture a step (inspired by Stefan Hermann's ScanRuler, CNC Kitchen)."

KEY_PARAMS = ("Length", "Depth", "Radius", "Size", "Occurrences", "Angle", "Offset", "Value")


# ---- notes -------------------------------------------------------------------------------

def notes_of(doc):
    return store.read(doc, "notes", {"next": 1, "notes": []})


def save_notes(doc, data):
    store.write(doc, "notes", data)


def note_view(n):
    out = {"id": n["id"], "by": n["by"], "text": n["text"], "at": n["at"], "done": bool(n.get("done"))}
    for k in ("body", "face", "answer", "made", "lost"):
        if n.get(k):
            out[k] = n[k]
    return out


def add_note(doc, at, text, by, body=None, face=None, face_on=None):
    """face_on: the object the face name belongs to, when it is not body (a
    PartDesign feature picked in the window): the face is then found on the
    body by its point at the next re-find."""
    data = notes_of(doc)
    n = {"id": data["next"], "by": by, "text": str(text), "at": [round(float(x), 4) for x in at], "done": False,
         "made": datetime.datetime.now().isoformat(timespec="seconds")}
    if body:
        n["body"] = body
    if face:
        n["face"] = face
        if face_on and face_on != body:
            n["anchor"], n["_rebodied"] = {"point": list(n["at"])}, True
        else:
            try:
                shape = _shape_of(doc, body) if body else None
                if shape is not None:
                    n["anchor"] = anchor(shape, face, n["at"])
            except Exception:  # noqa: BLE001 - no anchor: the note keeps its face name
                pass
    data["notes"].append(n)
    data["next"] += 1
    save_notes(doc, data)
    return n


# ---- a note's face across recomputes --------------------------------------------------------
# A later feature (a hole, a fillet) renumbers the faces: "Face6" may then be
# a side. A note pinned on a face keeps FreeCAD 1.x's mapped (toponaming)
# name of it, and its point and normal as the fallback; it is found again
# after each change, and flagged (lost) rather than guessed when neither
# finds it. The same approach as a linked texture mask's.

NORMAL_COS = 0.8     # within about 37 degrees of the old normal
# How far a face may have moved from a note's point (a pad made longer):
# this many mm, or this share of the part's size, whichever is more.
MOVE_MM, MOVE_SHARE = 3.0, 0.1


def mapped_name(shape, face):
    """FreeCAD 1.x's mapped name of a face ("Face6" → its toponaming name), or None."""
    try:
        rev = shape.ElementReverseMap
    except Exception:  # noqa: BLE001 - an older FreeCAD, a mesh, a stand-in
        return None
    got = rev.get(face) if isinstance(rev, dict) else None
    if isinstance(got, (list, tuple)):
        got = got[0] if got else None
    return got or None


def indexed_name(shape, mapped):
    """The face ("Face9") a mapped name stands for now, or None."""
    if not mapped:
        return None
    try:
        m = shape.ElementMap
    except Exception:  # noqa: BLE001
        return None
    got = m.get(mapped) if isinstance(m, dict) else None
    return got if isinstance(got, str) and got.startswith("Face") else None


def _sig(shape):
    try:
        return [round(float(shape.Volume), 4), round(float(shape.Area), 4), len(shape.Faces)]
    except Exception:  # noqa: BLE001
        return None


class Geo:
    """The geometry a note's face is found by (FreeCAD's Part); tests hand
    in their own."""

    @staticmethod
    def face(shape, name):
        try:
            return shape.getElement(name)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def faces(shape):
        return [(f"Face{i + 1}", f) for i, f in enumerate(shape.Faces)]

    @staticmethod
    def project(face, p):
        """(distance, point): p projected onto the face's surface along its
        normal, when it lands on the face itself; None when it lands off it."""
        import FreeCAD

        v = FreeCAD.Vector(*p)
        u, w = face.Surface.parameter(v)
        q = face.Surface.value(u, w)
        if not face.isInside(q, 1e-3, True):
            return None
        return (q - v).Length, [q.x, q.y, q.z]

    @staticmethod
    def size(shape):
        try:
            return float(shape.BoundBox.DiagonalLength)
        except Exception:  # noqa: BLE001
            return 0.0

    @staticmethod
    def dist(face, p):
        import FreeCAD
        import Part

        d, pairs, _info = face.distToShape(Part.Vertex(FreeCAD.Vector(*p)))
        q = pairs[0][0] if pairs else FreeCAD.Vector(*p)
        return d, [q.x, q.y, q.z]

    @staticmethod
    def normal(face, p):
        import FreeCAD

        u, v = face.Surface.parameter(FreeCAD.Vector(*p))
        n = face.normalAt(u, v)
        if getattr(face, "Orientation", "Forward") == "Reversed":
            n = -n
        return [n.x, n.y, n.z]


def anchor(shape, face, at, geo=Geo):
    """What finds a note's face again: its mapped name, its point and
    normal, and the shape it was on (to skip unchanged shapes)."""
    out = {"mapped": mapped_name(shape, face), "point": [round(float(x), 4) for x in at], "sig": _sig(shape)}
    f = geo.face(shape, face)
    if f is not None:
        try:
            out["normal"] = [round(float(x), 5) for x in geo.normal(f, at)]
        except Exception:  # noqa: BLE001
            pass
    return out


def _dot(a, b):
    la = sum(x * x for x in a) ** 0.5
    lb = sum(x * x for x in b) ** 0.5
    return sum(x * y for x, y in zip(a, b)) / (la * lb) if la and lb else 0.0


def refind(shape, n, geo=Geo):
    """(face, how, point) for a note on this shape: by its mapped name, else
    the face its point projects onto (along that face's normal, landing on
    it, within MOVE_MM or MOVE_SHARE of the part) facing the way it did —
    its own face first when that still fits, else the nearest; (None, why,
    None) when nothing does. A note made before anchors (no normal) takes
    the nearest face its point projects onto."""
    an = n.get("anchor") or {}
    p = an.get("point") or n.get("at")
    name = indexed_name(shape, an.get("mapped"))
    if name:
        f = geo.face(shape, name)
        q = None
        if f is not None and p:
            try:
                q = geo.dist(f, p)[1]
            except Exception:  # noqa: BLE001
                q = None
        return name, "mapped", q
    if not p:
        return None, "no point to find it by", None
    reach = max(MOVE_MM, MOVE_SHARE * geo.size(shape))
    fits = []
    for nm, f in geo.faces(shape):
        try:
            got = geo.project(f, p)
        except Exception:  # noqa: BLE001
            got = None
        if got is None or got[0] > reach:
            continue
        d, q = got
        if an.get("normal"):
            try:
                if _dot(geo.normal(f, q), an["normal"]) < NORMAL_COS:
                    continue
            except Exception:  # noqa: BLE001
                continue
        fits.append((d, nm, q))
    if not fits:
        return None, "no face is where it was, facing the same way", None
    fits.sort(key=lambda t: t[0])
    own = next((t for t in fits if t[1] == n.get("face") and t[0] <= fits[0][0] + 1e-6), None)
    d, nm, q = own or fits[0]
    return nm, "point", q


def _shape_of(doc, label):
    objs = doc.getObjectsByLabel(label) if doc is not None and label else []
    return objs[0].Shape if objs else None


def _body_of(doc, label):
    """The label a note's part goes by: a PartDesign feature's body (the
    whole part as shown, its Tip) rather than the feature itself — a note
    pinned in the window on the top of a Pad named the Pad, whose own faces
    keep their numbers while the body's change; else the label as it is."""
    objs = doc.getObjectsByLabel(label) if doc is not None and label else []
    if not objs:
        return label
    o = objs[0]
    try:
        if o.TypeId != "PartDesign::Body":
            b = o.getParentGeoFeatureGroup() if hasattr(o, "getParentGeoFeatureGroup") else None
            if b is not None and b.TypeId == "PartDesign::Body":
                return b.Label
    except Exception:  # noqa: BLE001
        pass
    return label


def follow(doc, shape_of=_shape_of, geo=Geo, body_of=_body_of):
    """Each note on a face found again on its body as it is now: the face
    renamed (and the pin moved onto it) where a later step renumbered the
    faces, lost (flagged, the face name left as it was) where it cannot be
    found. Answers the notes it changed."""
    data = notes_of(doc)
    changed = []
    for n in data["notes"]:
        if not (n.get("face") and n.get("body")):
            continue
        # A note from before anchors: found by its point the first time, its
        # anchor (mapped name, normal) kept from then on.
        n.setdefault("anchor", {"point": list(n["at"])})
        # On a PartDesign feature: followed on its body from now on, its face
        # name and mapped name looked for afresh there.
        moved_to = None
        try:
            moved_to = body_of(doc, n["body"])
        except Exception:  # noqa: BLE001
            moved_to = None
        if moved_to and moved_to != n["body"]:
            n["body"] = moved_to
            n["anchor"] = {"point": list(n["at"]), **({"normal": n["anchor"]["normal"]} if n["anchor"].get("normal") else {})}
            n["_rebodied"] = True
        try:
            shape = shape_of(doc, n["body"])
        except Exception:  # noqa: BLE001
            shape = None
        if shape is None:
            continue
        sig = _sig(shape)
        rebodied = n.pop("_rebodied", False)
        if sig is not None and sig == n["anchor"].get("sig") and not n.get("lost") and not rebodied:
            continue
        face, how, q = refind(shape, n, geo)
        if face is None:
            lost = f"{n['face']} is not found on {n['body']} any more ({how}): pin the note again"
            if n.get("lost") != lost:
                n["lost"] = lost
                changed.append(n["id"])
            continue
        was = (n["face"], list(n["at"]), n.get("lost"))
        n["face"] = face
        n.pop("lost", None)
        if q:
            n["at"] = [round(float(x), 4) for x in q]
        n["anchor"] = anchor(shape, face, n["at"], geo) if how == "point" else dict(n["anchor"], sig=sig, point=n["at"])
        if (n["face"], list(n["at"]), n.get("lost")) != was or rebodied:
            changed.append(n["id"])
            # Said at the next note_list, whoever re-found it (the panel's
            # refresh often comes first).
            n["movedFrom"] = {"face": was[0], "at": was[1]}
    if changed:
        save_notes(doc, data)
    return changed


def find_note(data, nid):
    for n in data["notes"]:
        if n["id"] == int(nid):
            return n
    raise ToolError("not_found", f"No note {nid}: note_list shows them.")


# ---- steps -------------------------------------------------------------------------------

def steps_of(body, sketches=False):
    """The body's history in order: each feature (and, asked, each sketch),
    with the volume after it and what it changed."""
    out, prev = [], 0.0
    for o in body.Group:
        sketch = o.isDerivedFrom("Sketcher::SketchObject")
        if sketch and not sketches:
            continue
        if not sketch and not o.isDerivedFrom("PartDesign::Feature"):
            continue
        row = {"name": o.Name, "label": o.Label, "type": o.TypeId.split("::")[-1]}
        if not sketch:
            sh = o.Shape
            vol = sh.Volume if not sh.isNull() and sh.Solids else 0.0
            row["volume"] = round(vol, 2)
            row["change"] = round(vol - prev, 2)
            prev = vol
            if o.isDerivedFrom("PartDesign::Feature") and getattr(o, "isValid", lambda: True)() is False:
                row["failed"] = True
        for k in KEY_PARAMS:
            if hasattr(o, k) and k in o.PropertiesList:
                v = getattr(o, k)
                row["key"] = f"{k} {getattr(v, 'UserString', v)}"
                break
        if body.Tip == o:
            row["tip"] = True
        out.append(row)
    for i, r in enumerate(out):
        r["step"] = i + 1
    return out


def _follow_after(session, _tool=None):
    try:
        follow(session.doc)
    except Exception:  # noqa: BLE001 - never in the way of the change
        pass


def caption(step, total, row):
    """The caption a step carries: its number, what it is and what it did."""
    did = ""
    if "change" in row:
        c = row["change"]
        did = f"+{c:.0f} MM3" if c > 0.5 else f"{c:.0f} MM3" if c < -0.5 else "NO CHANGE"
    return f"{step}/{total}  {row['type']}  {did}".strip()


def tools(session):
    s = session
    from .. import hooks

    # A note's face found again after every change (a hole renumbers faces).
    hooks.on("after_change", _follow_after)

    def _body_pd(ref):
        if ref is None:
            pds = [o for o in s.doc.Objects if o.TypeId == "PartDesign::Body"]
            if len(pds) == 1:
                return pds[0]
            raise ToolError("invalid_input", "body: which PartDesign body — " + (", ".join(o.Label for o in pds) or "there is none") + ".")
        for o in s.doc.Objects:
            if o.TypeId == "PartDesign::Body" and (o.Label == ref or o.Name == ref):
                return o
        raise ToolError("not_found", f"No PartDesign body '{ref}'.")

    # -- notes --

    def note_add(a):
        if not str(a.get("text", "")).strip():
            raise ToolError("invalid_input", "text: what the note says (a question to the person, or a remark).")
        body, face = None, None
        if a.get("faces") is not None:
            o = s.body(a.get("body"))
            picked = facepick.pick(o.Shape, a["faces"], "faces")
            name, f = picked[0]
            c = f.CenterOfMass
            at, body, face = [c.x, c.y, c.z], o.Label, name
        elif a.get("at") is not None:
            at = a["at"]
            if not (isinstance(at, list) and len(at) == 3):
                raise ToolError("invalid_input", "at: [x, y, z] in mm.")
            if a.get("body"):
                body = s.body(a["body"]).Label
        else:
            raise ToolError("invalid_input", "at [x, y, z], or body and faces (the note pinned at the face's centre).")
        n = add_note(s.doc, at, a["text"], "agent", body, face)
        return {"note": note_view(n), "note_count": len(notes_of(s.doc)["notes"])}

    def note_list(a):
        # Each note's face found again first (a step may have renumbered
        # them); a failure here is said, the notes answered as they were.
        followed, why = [], None
        try:
            follow(s.doc)
        except Exception as e:  # noqa: BLE001
            why = f"{type(e).__name__}: {e}"
        data = notes_of(s.doc)
        for n in data["notes"]:
            m = n.pop("movedFrom", None)
            if m:
                followed.append({"id": n["id"], "from": m["face"], "to": n.get("face"), "at": n.get("at"), **({"body": n["body"]} if n.get("body") else {})})
        if followed:
            save_notes(s.doc, data)
        rows = [note_view(n) for n in data["notes"] if not (a.get("open") and n.get("done"))]
        waiting = [n["id"] for n in data["notes"] if n["by"] == "person" and not n.get("done") and not n.get("answer")]
        out = {"notes": rows}
        if followed:
            out["followed"] = followed
        if why:
            out["notFollowed"] = f"The notes' faces were not looked for again ({why}): faces may have moved."
        if waiting:
            out["waiting"] = waiting
            out["next"] = "The person's notes waiting for an answer: note_answer { id, text }, and note_done when it is dealt with."
        return out

    def note_answer(a):
        data = notes_of(s.doc)
        n = find_note(data, a.get("id"))
        n["answer"] = str(a.get("text", "")).strip()
        if not n["answer"]:
            raise ToolError("invalid_input", "text: the answer.")
        save_notes(s.doc, data)
        return {"note": note_view(n)}

    def note_done(a):
        data = notes_of(s.doc)
        n = find_note(data, a.get("id"))
        n["done"] = bool(a.get("done", True))
        save_notes(s.doc, data)
        return {"note": note_view(n)}

    def note_delete(a):
        data = notes_of(s.doc)
        n = find_note(data, a.get("id"))
        data["notes"].remove(n)
        save_notes(s.doc, data)
        return {"deleted": n["id"], "left": len(data["notes"])}

    # -- steps --

    def steps_list(a):
        b = _body_pd(a.get("body"))
        rows = steps_of(b, bool(a.get("sketches")))
        return {"body": b.Label, "steps": rows, "count": len(rows)}

    def steps_render(a):
        b = _body_pd(a.get("body"))
        rows = steps_of(b, False)
        if not rows:
            raise ToolError("invalid_state", f"{b.Label} has no features yet.")
        view = str(a.get("view", "iso")).lower()
        if view not in render.VIEWS:
            raise ToolError("invalid_input", "view: " + ", ".join(render.VIEWS) + ".")
        w, h = int(a.get("width", 480)), int(a.get("height", 360))
        folder = paths.local(s, a.get("path") or f"steps_{''.join(ch if ch.isalnum() else '_' for ch in b.Label)}")
        os.makedirs(folder, exist_ok=True)
        # Framed on the finished part, so the camera holds still and the part grows in it.
        bb = b.Shape.BoundBox if not b.Shape.isNull() else None
        frame = {"at": [bb.Center.x, bb.Center.y, bb.Center.z], "size": bb.DiagonalLength * 1.05} if bb and bb.isValid() else None
        files, sheet = [], []
        total = len(rows)
        for r in rows:
            o = s.doc.getObject(r["name"])
            sh = o.Shape
            if sh.isNull():
                continue
            pts, tris = sh.tessellate(0.05)
            import numpy as np

            layer = {"name": o.Label, "V": np.array([[p.x, p.y, p.z] for p in pts], float),
                     "F": np.array(tris, np.int64).reshape(-1, 3), "color": render.PALETTE[0], "creases": True}
            img, _, _ = render.draw([layer], view, w, h, frame=frame, bottom=26)
            render.text(img, caption(r["step"], total, r), 10, h - 22, scale=2)
            p = os.path.join(folder, f"step_{r['step']:02d}.png")
            with open(p, "wb") as f:
                f.write(render.png(img))
            files.append(p)
            sheet.append(img)
        out = {"body": b.Label, "folder": folder, "files": files, "steps": rows}
        if a.get("sheet", True) and sheet:
            import math

            import numpy as np

            cols = min(4, len(sheet))
            nrows = math.ceil(len(sheet) / cols)
            big = np.tile(render.BG, (nrows * h, cols * w, 1))
            for k, im in enumerate(sheet):
                rr, cc = divmod(k, cols)
                big[rr * h:(rr + 1) * h, cc * w:(cc + 1) * w] = im
            p = os.path.join(folder, "steps.png")
            data = render.png(big)
            with open(p, "wb") as f:
                f.write(data)
            out["sheet"] = p
            if a.get("inline", True):
                out["_png"] = data
        return out

    return [
        Tool("note_add", "Pin a note to the part for the person: a question or a remark, at [x,y,z] or on body + faces (a query as fea_hold takes). It shows as a pin in the window; the person answers it there.",
             obj({"text": {"type": "string"}, "at": {"type": "array", "items": {"type": "number"}}, "body": {"type": "string"}, "faces": {}}, ["text"]), note_add, changes=True),
        Tool("note_list", "The notes pinned to the parts — the person's and the agent's — with answers and which are done; waiting lists the person's notes with no answer yet. open: true leaves out the done ones.",
             obj({"open": {"type": "boolean"}}), note_list),
        Tool("note_answer", "Answer a note (the person's question or request): id, text.", obj({"id": {"type": "integer"}, "text": {"type": "string"}}, ["id", "text"]), note_answer, changes=True),
        Tool("note_done", "Tick a note off (done: false opens it again).", obj({"id": {"type": "integer"}, "done": {"type": "boolean"}}, ["id"]), note_done, changes=True),
        Tool("note_delete", "Take a note out of the document, the person's or the agent's (note_done only ticks it off).", obj({"id": {"type": "integer"}}, ["id"]), note_delete, changes=True),
        Tool("steps_list", "A PartDesign body's history in order: each feature with its key value, the volume after it and what it added or took away (sketches: true lists the sketches too).",
             obj({"body": {"type": "string"}, "sketches": {"type": "boolean"}}), steps_list),
        Tool("steps_render", "The build played back as pictures: a picture a feature, framed on the finished part so it grows in place, each captioned with its step, type and what it did; a contact sheet of them (sheet: false leaves it out). view (iso), width, height, path (a folder).",
             obj({"body": {"type": "string"}, "view": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"}, "path": {"type": "string"}, "sheet": {"type": "boolean"}, "inline": {"type": "boolean"}}), steps_render),
    ]
