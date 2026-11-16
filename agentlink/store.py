# SPDX-License-Identifier: LGPL-2.1-or-later
# This add-on's own copy; it was AddonKit's addonkit.records, retired 14 Nov 2026.
# What the agent records about the parts, kept in the document itself so it
# is saved with the .FCStd: how each part is made (setups), what it is made
# of, the limits it must meet (the spec), and the findings accepted on
# purpose (waivers). Each record is JSON under its own name.
#
# The records live in one hidden object, AgentLinkRecords (a string property
# a record), so writing one happens inside the tool's undo step and undo
# takes it back with the rest (unattended use, B). Files from before kept
# them in the document's Meta, which is outside undo: those are read from
# there until the first write copies them over. Meta is left as it was — the
# state before the records object, which is what undoing its creation goes
# back to.

import json
import os
import re

# The names below are the file format's (documents written since Agent Link's
# first records carry them), not a reference to any add-on; keep them.
KEY = "AgentLink."
HOLDER = "AgentLinkRecords"


def _prop(name):
    return "R_" + re.sub(r"\W", "_", name)


def _objects(doc):
    # A document without objects of its own (a test double): Meta only.
    return hasattr(doc, "getObject") and hasattr(doc, "addObject")


def holder(doc, make=False):
    if not _objects(doc):
        return None
    o = doc.getObject(HOLDER)
    if o is None and make:
        o = doc.addObject("App::FeaturePython", HOLDER)
        o.Label = "Agent Link records"
        try:
            o.setPropertyStatus("Label", "ReadOnly")
        except Exception:
            pass
        try:
            o.Visibility = False
        except Exception:
            pass
        vo = getattr(o, "ViewObject", None)
        if vo is not None and hasattr(vo, "ShowInTree"):
            vo.ShowInTree = False
        for k, v in (doc.Meta or {}).items():
            if k.startswith(KEY):
                _set(o, k[len(KEY):], v)
    return o


def _set(o, name, raw):
    p = _prop(name)
    if p not in o.PropertiesList:
        o.addProperty("App::PropertyString", p, "AgentLink", f"Agent Link record: {name} (JSON)")
        try:
            o.setEditorMode(p, 2)
        except Exception:
            pass
    if getattr(o, p, None) != raw:
        setattr(o, p, raw)


def _raw(doc, name):
    o = doc.getObject(HOLDER) if _objects(doc) else None
    if o is not None:
        p = _prop(name)
        if p in o.PropertiesList:
            return getattr(o, p)
        return None
    return (doc.Meta or {}).get(KEY + name)


def read(doc, name, default):
    raw = _raw(doc, name)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        return default


def write(doc, name, value):
    raw = json.dumps(value, separators=(",", ":"))
    # The same value again changes nothing: the document is not touched (nor
    # the records object made) by a write that would leave it as it was.
    if _raw(doc, name) == raw:
        return
    o = holder(doc, make=True)
    if o is None:
        m = dict(doc.Meta or {})
        m[KEY + name] = raw
        doc.Meta = m
        return
    _set(o, name, raw)


def remove(doc, name):
    if not _objects(doc):
        m = dict(doc.Meta or {})
        m.pop(KEY + name, None)
        doc.Meta = m
        return
    o = holder(doc, make=(KEY + name) in (doc.Meta or {}))
    if o is not None and _prop(name) in o.PropertiesList:
        setattr(o, _prop(name), "")


# ---- setups: how each part is made --------------------------------------------------------
# One setup is one process and the bodies made by it, with that process's
# settings — as a setup is in Fusion's Manufacture workspace. A body is in
# one setup of a kind at most. Nothing chooses a process for a part: the
# person decides, and a setup records it.

TYPES = {
    "print": {
        "label": "Print",
        "settings": {
            "printer": "The printer profile: generic, bed-slinger, corexy, h2d.",
            "nozzle": "The nozzle, mm: 0.2, 0.4, 0.6 or 0.8.",
            "layerHeight": "The layer height, mm.",
            "firstLayer": "The first layer's height, mm.",
            "up": "Which way of the part stands up on the bed: +z as modelled (only +z in this build).",
            "walls": "Walls (perimeters).",
            "infill": "Infill, percent.",
            "topLayers": "Solid layers on top (5 to start).",
            "bottomLayers": "Solid layers at the bottom (4 to start).",
            "slicerPresets": "The person's own slicer presets, set by the slicing add-on's presets tool: { slicer, machine, process, filament } or { bundle }.",
        },
    },
    "cut": {"label": "Cut", "settings": {"machine": "laser, waterjet, plasma or router.", "thickness": "The sheet, mm.", "kerf": "The cut's width, mm.", "material": "The sheet's material, for the least feature.", "sheet": "The sheet's size, [width, height] mm."}},
    "mill": {"label": "Mill", "settings": {"axes": "\"3\" or \"3+2\".", "minTool": "The least end mill, mm.", "grade": "The ISO 286 IT grade, 5 to 14.", "directions": "Tool directions from the part to the spindle: \"+z\", \"-z\" or [x, y, z], one or more.", "material": "The stock's material.", "stock": "The stock's size [x, y, z], mm.", "reach": "How far the longest tool reaches below the top, mm."}},
}


def setups(doc):
    return read(doc, "setups", [])


def setup_of(doc, body, kind=None):
    for s in setups(doc):
        if body in s["bodies"] and (kind is None or s["type"] == kind):
            return s
    return None


# ---- per-part records ---------------------------------------------------------------------

def spec(doc):
    """{ minWall, minClearance, massMin, massMax, minSafety } for every part."""
    return read(doc, "spec", {})


def materials(doc):
    return read(doc, "materials", {})


def undo_on(doc):
    """FreeCAD's undo on in doc, set only when it is off: setting the
    document's UndoMode, even to the value it has, marks a saved document
    changed (opening an add-on's panel made the session, and the "*"
    and a recovered copy each time)."""
    try:
        if doc.UndoMode == 1:
            return
    except AttributeError:  # a stand-in document without the property
        doc.UndoMode = 1
        return
    # Turning undo on is no change to the model: a saved document (one
    # reopened after a restart has undo off) stays saved.
    was = _changed(doc)
    doc.UndoMode = 1
    if not was:
        _unchanged(doc)


# Headless, what was still marked touched when a document was last saved
# from here: its name -> (its file, those objects' names).
_AT_SAVE = {}


def touched_names(doc):
    """The objects FreeCAD still marks touched (waiting for a recompute), by
    name, from each one's State: the document answers isTouched(), an object
    has no such method."""
    out = []
    for o in getattr(doc, "Objects", None) or ():
        try:
            if "Touched" in o.State:
                out.append(o.Name)
        except Exception:
            pass
    return out


def note_saved(doc):
    """doc was just written to its file. FreeCAD's save clears no touched
    mark (src/App/Document.cpp: save() and saveToFile() purge nothing; only a
    recompute does), so an object still touched as the file was written — a
    frozen one, one whose input failed, a holder nothing recomputes — read as
    "changed since saved" for good where there is no window. What was
    touched at the save is kept, and only a mark that came after it counts
    (is_changed). The marks themselves are left: they are FreeCAD's note of
    what the next recompute must redo."""
    try:
        _AT_SAVE[doc.Name] = (doc.FileName, frozenset(touched_names(doc)))
    except Exception:
        pass


def touched_since_save(doc):
    """The objects touched now that were not when doc was last saved from
    here (all the touched ones when it was not, or was saved elsewhere)."""
    now = touched_names(doc)
    try:
        kept = _AT_SAVE.get(doc.Name)
        if kept is not None and kept[0] == doc.FileName:
            return [n for n in now if n not in kept[1]]
    except Exception:
        pass
    return now


def is_changed(doc):
    """Whether doc has changes since it was saved. With the window up, its
    own modified mark (the "*") says so: FreeCAD 1.1 reports a document
    touched as soon as it is opened, with no change at all (seen on the
    Mac after each restart), so touched alone kept a recovered copy each
    time. Headless, touched is all there is — less what was already touched
    when it was last saved from here (note_saved)."""
    g = _gui_doc(doc)
    if g is not None:
        try:
            return bool(g.Modified)
        except Exception:
            pass
    try:
        if not doc.isTouched():
            return False
    except Exception:
        return False
    try:
        kept = _AT_SAVE.get(doc.Name)
        if kept is not None and kept[0] == doc.FileName:
            return bool(touched_since_save(doc))
    except Exception:
        pass
    return True


def _changed(doc):
    return is_changed(doc)


def _unchanged(doc):
    try:
        doc.purgeTouched()
    except Exception:
        pass
    g = _gui_doc(doc)
    if g is not None:
        try:
            g.Modified = False
        except Exception:
            pass


def settle_opened(names):
    """Documents just opened from a saved copy (an add-on's recovered
    copies) marked unchanged: opening one renames it "(recovered …)" and
    recomputes it, which set the window's modified mark, so the heartbeat
    read every copy as changed for ever, the auto-save kept saving it and
    each restart recovered it again — a copy of a copy. A change made in it
    later marks it again. The names it settled."""
    import FreeCAD

    done = []
    for n in names or ():
        try:
            d = FreeCAD.getDocument(n)
        except Exception:
            d = None
        if d is None:
            continue
        _unchanged(d)
        done.append(n)
    return done


def copy_file(f):
    """A document file in a temporary folder: a saved copy opened beside the
    person's file (agentlink-recovered-…, agentlink-restore-…, or anywhere
    under the system's temporary folder), never the person's own."""
    import tempfile

    f = str(f or "")
    if not f:
        return False
    if os.path.basename(os.path.dirname(f)).startswith(("agentlink-recovered-", "agentlink-restore-")):
        return True
    try:
        tmp = os.path.realpath(tempfile.gettempdir())
        return os.path.realpath(f).startswith(tmp + os.sep)
    except Exception:
        return False


def settle_copies(before):
    """After a call: the documents it opened (not in before, the names open
    when it started) from a copy in a temporary folder, marked unchanged
    (settle_opened). The names settled."""
    import FreeCAD

    new = [n for n, d in FreeCAD.listDocuments().items() if n not in before and copy_file(getattr(d, "FileName", ""))]
    return settle_opened(new) if new else []


def _gui_doc(doc):
    try:
        import FreeCAD

        if not getattr(FreeCAD, "GuiUp", False):
            return None
        import FreeCADGui

        return FreeCADGui.getDocument(doc.Name)
    except Exception:
        return None
