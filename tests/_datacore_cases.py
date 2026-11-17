# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datacore_data.py runs through the old handler and the
# new data entry of each converted core tool of families/view.py, dev.py,
# unattended.py and doc.py, on the stand-in FreeCAD
# (tests/_datacore_standin.py): its normal paths and each of its refusals.
import json
import os

# The family files whose tools were converted (unattended before dev, which imports from it).
FILES = ("view", "unattended", "dev", "doc")
# Each converted tool and its family file's group.
CONVERTED = {**{k: "view" for k in ("view_maps", "view_snapshot")}, **{k: "dev" for k in ("gui_unstick", "addon_test")},
             **{k: "unattended" for k in ("queue_go", "doc_switch", "crash_collect", "dialog_answer")},
             **{k: "doc" for k in ("doc_new", "doc_close", "doc_open", "doc_save", "object_list", "object_get", "object_set", "object_delete", "object_rename", "object_group",
                                   "recompute", "import_file", "export")}}
# Tools of those files kept as code, and why.
KEPT = {
    "view_render": "the picture itself: numpy over every layer's triangles, a render sized and timed against past renders, marked heavy for the watchdog and "
                   "unmarked in a finally, an image answered",
    "gui_input": "one algorithm over Qt widgets (gui_input.Run): events sent step by step inside the window's event loop, the link's deadline set and "
                 "lifted around it, the person's input stood in for inside a context manager with a finally",
    "live_run": "a replay that calls the server's own tools from closures, with a guard ticking inside nested Qt event loops and state put back in a finally",
    "addon": "installs code: the Addon Manager's installer run with the add-on moved aside and put back when the install or the smoke test fails, and its "
             "refusal for a missing confirm has the code not_allowed, which a refuse step does not take",
}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ("view_maps", "what there is"): {"layers": [], "views": ["iso", "iso-front-left", "iso-rear-left", "iso-rear-right", "top", "bottom", "front", "rear", "left", "right"]},
    ("view_snapshot", "headless"): ["refused", "unavailable", "view_snapshot is the FreeCAD window's own view: there is no window (headless). view_render draws the parts without one."],
    ("view_snapshot", "a view, fitted"): {"view": "front", "width": 800, "height": 600},
    ("view_snapshot", "as the person left it"): {"view": "as the person left it", "fitted": False,
                                                 "fitNote": "Not re-fitted: the view is as the person left it (its zoom and pan), so parts may be cut off or out of frame."},
    ("view_snapshot", "saved at another size"): {"width": 1600, "height": 1200, "warning": "Asked 800 x 600; FreeCAD saved 1600 x 1200 and it could not be resized here."},
    ("view_snapshot", "all, in one picture"): {"views": ["iso", "top", "front", "right"], "width": 800, "height": 600, "grid": [2, 2], "cell": [400, 300],
                                               "sizeIs": "the whole grid (cell: true makes it each view's)", "note": "The person's own view is put back."},
    ("view_snapshot", "all, no picture of them"): {"warning": "The views could not be put in one picture here: each view's own file is in paths."},
    ("view_snapshot", "cells too big"): ["refused", "invalid_input", "cell 4096 x 4096 in a 3 x 2 grid is 12288 x 8192 px: 8192 at most each way."],
    ("gui_unstick", "all"): {"closed": ["a menu"], "open": None},
    ("addon_test", "a run with everything given"): {"job": "t1", "addon": "Workshop", "state": "running"},
    ("addon_test", "timeout too long"): ["refused", "invalid_input", "timeout: seconds, over 0 and at most 1800 (600 by default)."],
    ("queue_go", "held, one running"): {"go": True, "wasHeld": True, "running": ["fea_solve"], "machine": {"heavySlots": 2, "memoryCeilingGB": 12, "fan": "quiet"}},
    ("crash_collect", "nothing"): {"note": "No recovery files from another FreeCAD and no new crash reports."},
    ("dialog_answer", "a dialog's button"): {"pressed": "Yes", "dialog": {"title": "Save?", "text": "Save changes?", "buttons": ["Yes", "No"], "class": "QMessageBox"}},
    ("dialog_answer", "recovery's cleanup, nothing to keep"): {"pressed": "Cleanup", "kept": {"note": "No recovery files or crash reports were found to keep."}},
    ("dialog_answer", "a prompt that will not take it"): ["refused", "invalid_input", "item: one of Top, Front — not that."],
    ("dialog_answer", "a task's button it has not"): ["refused", "invalid_input", "button: one of OK, Cancel (Cancel closes the task)."],
    ("doc_switch", "to another, by label in any case"): {"document": "Other", "label": "Other part", "front": False, "bodies": [],
                                                         "note": "The agent works here from now on, whatever is in front of the window. front: true also brings it to the front."},
    ("doc_switch", "not open"): ["refused", "not_found", "Nowhere: not open — open, as label (name): Model, Other part (Other). doc_open { path } opens a file."],
    ("doc_new", "named with a space"): {"document": "My_part", "label": "My part", "previous": "Model"},
    ("doc_close", "a label two share"): ["refused", "invalid_input", "'Twin': 2 open documents have that label — give the name in brackets: Twin (A), Twin (B)."],
    ("doc_close", "changed, with marks"): ["refused", "invalid_state", "Changed since saved: Other part (objects marked changed — Other part: Pad, Sketch) — nothing was closed. doc_save first "
                                           "(doc_switch { document } to each, then doc_save), or doc_close { documents, discard: true } closes without saving and the changes are lost."],
    ("doc_close", "the current one, back where it came from"): {"closed": ["Model"], "document": "Other", "label": "Other part", "open": ["Other part", "Third"]},
    ("doc_close", "two of one label left open"): {"closed": ["Model"], "open": ["Twin (A)", "Twin (B)"]},
    ("doc_open", "a file"): {"document": "bracket", "label": "bracket", "objects": 0, "bodies": [], "errors": []},
    ("doc_save", "never saved, the name taken"): {"label": "Model 2", "labelWas": "Model",
                                                  "note": "Saved under a new file name, so FreeCAD relabelled the document 'Model 2' (it was 'Model'); its name 'Model' stays."},
    ("object_list", "everything"): {"document": "Model", "count": 4},
    ("object_get", "a filter that matches nothing"): ["refused", "not_found", "filter 'zzz': no property of Block matches — object_get { object } without filter lists them all."],
    ("object_set", "a length and a placement"): {"object": "Block", "step": 1},
    ("object_set", "no such property"): ["refused", "not_found", "values.Lenght: Block has no such property — did you mean Length. object_get lists them."],
    ("object_set", "read-only visibility"): ["refused", "invalid_input", "values.Visibility: read-only on Block (FreeCAD computes it). show { objects, visible } shows or hides it."],
    ("object_set", "the recompute fails"): ["refused", "failed", "The recompute failed after setting it: Block: Valid — nothing was kept."],
    ("object_delete", "used by another"): ["refused", "invalid_state", "Block (in Cut) is used by Cut: name those in objects too, or force: true deletes it and leaves them broken "
                                           "(FreeCAD removes it without asking; they fail at the next recompute). Nothing was deleted."],
    ("object_delete", "a result with its helper, inputs shown again"): {"deleted": ["Cut"], "alongWith": ["Helper"], "shownAgain": ["Block"], "renamed": {"Block (in Cut)": "Block"}},
    ("object_rename", "a label FreeCAD changes"): {"from": "Block", "to": "Base001", "warning": "FreeCAD changed the label to 'Base001' (not 'Base') to keep it apart from another."},
    ("object_rename", "the same label"): {"from": "Block", "to": "Block", "unchanged": True},
    ("object_group", "three links"): {"links": ["Peg", "Peg 2", "Peg 3"], "of": "Block"},
    ("object_group", "a new part with two"): {"group": "Kit", "type": "App::Part", "holds": ["Block", "Pin"]},
    ("object_group", "dissolve"): {"dissolved": "Bin", "kept": ["Block"]},
    ("object_group", "no such group to remove from"): ["refused", "not_found", "group 'Nope': no such group to remove — the groups: Bin."],
    ("recompute", "frozen"): {"recomputed": 0, "ok": True, "note": "Nothing was recomputed: the document's skip-recompute switch is on (object_freeze { skipRecompute: false } turns it off; "
                                                                   "force: true recomputes anyway)."},
    ("recompute", "forced, on a FreeCAD that takes no force"): {"recomputed": 2, "ok": True},
    ("import_file", "a STEP, a body per solid"): {"format": "step", "count": 2, "step": 1},
    ("import_file", "an STL as a mesh"): {"format": "stl", "count": 1},
    ("import_file", "a JT where the reader is left out"): ["refused", "unavailable", "JT needs FreeCAD's JtReader, which this build leaves out: export STEP from the program that made it."],
    ("import_file", "an SVG of many paths"): {"format": "svg", "count": 14, "more": "9 more (14 Part::Feature): doc_list or session_state lists them all."},
    ("import_file", "a glTF by FreeCAD's own reader"): {"format": "gltf", "read": {"reader": "FreeCAD's glTF reader (Import)"}, "count": 1},
    ("export", "one body, STEP"): {"objects": ["Block"], "format": "step", "verify": {"volume": 1000.0, "volumeDiff": 0.0, "solids": 1, "faces": 6}},
    ("export", "a mesh, as it is"): {"objects": ["Scan"], "meshes": ["Scan"], "format": "stl", "verify": {"triangles": 12, "trianglesWritten": 12, "closed": True, "volume": 1000.0}},
    ("export", "a mesh as STEP"): ["refused", "invalid_input", "Scan: a mesh, written as stl, obj, 3mf, ply, off, wrl, x3d, glb, gltf, dae — not STEP. For STEP, import_file the mesh again with "
                                   "solid: true (a body of its triangles) first."],
    ("export", "a tolerance of nothing"): ["refused", "invalid_input", "tolerance: the chord error, above 0 mm."],
}
# Refusals written in the data that no case here reaches: none.
UNREACHED = []


def cases(fc, tmp, old, new):
    ns = fc.ns
    kept = {m: {k: getattr(mods[m], k) for k in ("snap_combine", "_snap_empty")} for mods in (old, new) for m in ("view",)}
    first = {id(mods["view"]): {k: getattr(mods["view"], k) for k in ("snap_combine", "_snap_empty")} for mods in (old, new)}
    del kept

    def prep(*fns, gui=False, **flags):
        def prepare(s):
            fc.fc.GuiUp = gui
            fc.state["flags"].update(flags)
            for mods in (old, new):  # what a case before this one put in a family's place
                for k, v in first[id(mods["view"])].items():
                    setattr(mods["view"], k, v)
            for fn in fns:
                fn(s)
        return prepare

    def in_view(k, fn):
        """A case's own stand-in for one of view.py's Qt functions, in the old module and the new."""
        def put(s):
            for mods in (old, new):
                setattr(mods["view"], k, fn)
        return put

    def block(s):
        b = block_(s)
        b.Placement  # its placement is a property it has
        return b

    def block_(s):
        return fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10), volume=1000.0), ViewObject=ns(Visibility=True),
                       Length=10.0, Mode="Solid", types={"Length": "App::PropertyLength", "Mode": "App::PropertyEnumeration", "Placement": "App::PropertyPlacement",
                                                         "Visibility": "App::PropertyBool", "Shape": "Part::PropertyPartShape"},
                       choices={"Mode": ["Solid", "Shell"]}, groups={"Length": "Box"})

    def pin(s):
        return fc.body("Pin", fc.solid("pin", (2, 2, 0), (4, 4, 30), volume=120.0), name="Pin", ViewObject=ns(Visibility=True))

    def scan(s, label="Scan", **kw):
        return s.doc.new("Mesh::Feature", "Scan", Mesh=fc.MeshData(None, 12), **kw).__dict__.update(Label=label)

    def other(s, changed=False, touched=(), file="", name="Other", label="Other part"):
        d = fc.docs()[name] = fc.Doc(name, label, file)
        d.changed, d.touched = changed, list(touched)
        return d

    def file(name, text="x"):
        def write(s):
            with open(os.path.join(s.out_dir, name), "w") as f:
                f.write(text)
        return write

    def picture(name, w=200, h=100):
        return lambda s: fc.png(os.path.join(s.out_dir, name), w, h)

    out = []

    def add(tool, case, prepare, args):
        out.append((tool, case, prepare, args))

    # ---- view ------------------------------------------------------------------------------------
    add("view_maps", "what there is", prep(), {})
    V = "view_snapshot"
    add(V, "headless", prep(block), {"view": "front"})
    add(V, "views not a list", prep(block, gui=True), {"views": 5})
    add(V, "a view there is not", prep(block, gui=True), {"view": "upside"})
    add(V, "one of the views there is not", prep(block, gui=True), {"views": ["top", "inside"]})
    add(V, "seven views", prep(block, gui=True), {"views": ["top", "front", "left", "right", "rear", "bottom", "iso"]})
    add(V, "too wide", prep(block, gui=True), {"width": 5000})
    add(V, "too low", prep(block, gui=True), {"height": 8})
    add(V, "bad size, headless", prep(block), {"height": 8})
    add(V, "no 3D view", prep(block, gui=True, no_view=True), {})
    add(V, "no window for the document", prep(block, gui=True, no_gui_doc=True), {})
    add(V, "a view that saves no pictures", prep(block, gui=True, odd_view=True), {"view": "top"})
    add(V, "as the person left it", prep(block, gui=True), {})
    add(V, "a view, fitted", prep(block, gui=True), {"view": "front"})
    add(V, "a view by its other name, not fitted, to a path", prep(block, gui=True), {"view": "Back", "fit": False, "path": "rear", "inline": False, "background": "White"})
    add(V, "views of one", prep(block, gui=True), {"views": "isometric", "width": 320, "height": 240})
    add(V, "an empty list of views", prep(block, gui=True), {"views": []})
    add(V, "saved at another size", prep(block, gui=True, saved_size=(1600, 1200)), {"view": "top"})
    add(V, "nothing in the view", prep(block, in_view("_snap_empty", lambda s, view: "Nothing of the model is in the view."), gui=True), {"view": "top"})
    add(V, "nothing in the view as it was left", prep(block, in_view("_snap_empty", lambda s, view: "Nothing of the model is in the view."), gui=True), {})
    add(V, "crash: the view will not save", prep(block, gui=True, fail=("saveImage",)), {"view": "top"})
    add(V, "all, no picture of them", prep(block, gui=True), {"views": "all"})

    def combine(size=None):
        def fn(files, names, cols, rows, cw, ch, p):
            fc.log("snap_combine", [os.path.basename(f) for f in files], names, cols, rows, cw, ch, os.path.basename(p))
            fc.png(p, *(size or (cw * cols, ch * rows)))
            return True
        return in_view("snap_combine", fn)

    add(V, "all, in one picture", prep(block, combine(), gui=True), {"views": "all"})
    add(V, "five, each its own size, not fitted, not sent", prep(block, combine(), gui=True),
        {"views": ["top", "front", "left", "right", "rear"], "cell": True, "width": 200, "height": 100, "fit": False, "inline": False, "path": "five"})
    add(V, "the grid saved at another size", prep(block, combine((1600, 1200)), gui=True), {"views": ["top", "front"]})
    add(V, "cells too big", prep(block, gui=True), {"views": ["top", "front", "left", "right", "rear"], "cell": True, "width": 4096, "height": 4096})
    add(V, "several, nothing shown", prep(gui=True), {"views": ["top", "front"]})
    add(V, "several, everything hidden", prep(lambda s: block(s).__dict__.update(Visibility=False, ViewObject=ns(Visibility=False)), gui=True), {"views": "all"})
    add(V, "several, no camera to put back", prep(block, combine(), gui=True, no_camera=True), {"views": ["top", "front"]})
    add(V, "crash: one of several will not save", prep(block, gui=True, fail=("saveImage",)), {"views": ["top", "front"]})

    # ---- dev -------------------------------------------------------------------------------------
    add("gui_unstick", "the one in front", prep(gui=True), {})
    add("gui_unstick", "all", prep(gui=True, closed=["a menu"]), {"all": True})
    T = "addon_test"

    def installed(s):
        mod = os.path.join(s.out_dir, "Mod")
        for n in ("AgentLink", "Workshop", "Texturizer"):
            os.makedirs(os.path.join(mod, n))
        with open(os.path.join(mod, "AgentLink", ".installed-names"), "w") as f:
            json.dump(["AgentLink", "Workshop", "Texturizer", "Gone"], f)

    add(T, "both", prep(), {"addon": "Workshop", "job": "t1"})
    add(T, "a job", prep(), {"job": "t1"})
    add(T, "a job, the window painting", prep(gui=True), {"job": "t1"})
    add(T, "a job there is not", prep(), {"job": "t9"})
    add(T, "neither", prep(), {})
    add(T, "a run", prep(), {"addon": "Workshop"})
    add(T, "a run with everything given", prep(installed), {"addon": "Workshop", "pattern": "test_make*.py", "select": "fits", "timeout": 120, "folder": "make/deep"})
    add(T, "a pattern with a folder", prep(), {"addon": "Workshop", "pattern": "make/test_*.py"})
    add(T, "a select with a space", prep(), {"addon": "Workshop", "select": "two words"})
    add(T, "timeout too long", prep(), {"addon": "Workshop", "timeout": 100000})
    add(T, "timeout nothing", prep(), {"addon": "Workshop", "timeout": 0})
    add(T, "timeout true", prep(), {"addon": "Workshop", "timeout": True})
    add(T, "timeout in words", prep(), {"addon": "Workshop", "timeout": "long"})
    add(T, "a folder that climbs", prep(), {"addon": "Workshop", "folder": "../etc"})
    add(T, "an add-on not installed", prep(), {"addon": "Nope"})
    add(T, "no command-line FreeCAD", prep(no_cmd=True), {"addon": "Workshop"})

    # ---- unattended ------------------------------------------------------------------------------
    add("queue_go", "nothing held", prep(), {})
    add("queue_go", "held, one running", prep(queue={"held": True, "notice": "held for the person", "running": [{"tool": "fea_solve"}]}), {})
    add("crash_collect", "nothing", prep(), {})
    add("crash_collect", "some", prep(crash={"folder": "crash/1", "files": 3}), {})
    A = "dialog_answer"
    dlg = {"title": "Save?", "text": "Save changes?", "buttons": ["Yes", "No"], "class": "QMessageBox", "widget": object()}
    rec = {"title": "Document Recovery", "text": "", "buttons": ["Finish", "Cleanup"], "class": "Gui::Dialog::DocumentRecoveryPriv", "widget": object()}
    task = {"title": "Pad", "buttons": ["OK", "Cancel"], "widget": object()}
    add(A, "headless", prep(dialog=dlg), {"button": "Yes"})
    add(A, "nothing open", prep(gui=True), {})
    add(A, "a task read", prep(gui=True, task=task), {})
    add(A, "a task given text", prep(gui=True, task=task), {"text": "5", "button": "OK"})
    add(A, "a task given an item", prep(gui=True, task=task), {"item": "Top"})
    add(A, "a task's button", prep(gui=True, task=task), {"button": "OK"})
    add(A, "a task's button it has not", prep(gui=True, task=task), {"button": "Apply"})
    add(A, "a dialog read", prep(gui=True, dialog=dlg, task=task), {})
    add(A, "a dialog's button", prep(gui=True, dialog=dlg), {"button": "Yes"})
    add(A, "a dialog's button in another case", prep(gui=True, dialog=dlg), {"button": "no"})
    add(A, "a button it has not", prep(gui=True, dialog=dlg), {"button": "Maybe"})
    add(A, "a button where it has none", prep(gui=True, dialog={**dlg, "buttons": []}), {"button": "OK"})
    add(A, "backed out of", prep(gui=True, dialog={**dlg, "buttons": []}), {"button": "Cancel"})
    add(A, "text with no button", prep(gui=True, dialog=dlg), {"text": "12"})
    add(A, "an item with no button", prep(gui=True, dialog=dlg), {"item": "Top"})
    add(A, "text typed, then pressed", prep(gui=True, dialog=dlg), {"text": "12", "button": "Yes"})
    add(A, "an item picked, then pressed", prep(gui=True, dialog=dlg), {"item": "Top", "button": "Yes"})
    add(A, "a prompt that will not take it", prep(gui=True, dialog=dlg, fill_fails=True), {"item": "Side", "button": "Yes"})
    add(A, "a button that will not press", prep(gui=True, dialog=dlg, press_fails=True), {"button": "Yes"})
    add(A, "recovery's cleanup, kept first", prep(gui=True, dialog=rec, crash={"folder": "crash/1"}), {"button": "Cleanup"})
    add(A, "recovery's cleanup, nothing to keep", prep(gui=True, dialog=rec, crash={}), {"button": "Cleanup"})
    add(A, "recovery's finish", prep(gui=True, dialog=rec, crash={"folder": "crash/1"}), {"button": "Finish"})
    S = "doc_switch"
    add(S, "the open ones", prep(block, lambda s: other(s, changed=True, touched=["Pad"]).__dict__.update(UndoNames=["Pad", "Sketch", "Body", "New"]), lambda s: other(s, name="Saved", label="Saved", file="/x/saved.FCStd")), {})
    add(S, "a number", prep(other), {"document": 3})
    add(S, "not open", prep(other), {"document": "Nowhere"})
    add(S, "to another, by name", prep(other, lambda s: fc.body("Peg", fc.solid("peg", (0, 0, 0), (1, 1, 1), volume=1.0)).__dict__.update()), {"document": "Other"})
    add(S, "to another, by label in any case", prep(other), {"document": "other PART"})
    add(S, "to another, by its file", prep(lambda s: other(s, file=os.path.join(tmp, "o.FCStd"))), {"document": os.path.join(tmp, "o.FCStd")})
    add(S, "a file not open", prep(other), {"document": os.path.join(tmp, "gone.FCStd")})
    add(S, "to another, to the front", prep(other, gui=True), {"document": "Other", "front": True})
    add(S, "to another, front asked headless", prep(other), {"document": "Other", "front": True})
    add(S, "already on it", prep(other), {"document": "Model"})
    add(S, "already on it, to the front", prep(other, gui=True), {"document": "Model", "front": True})

    # ---- documents -------------------------------------------------------------------------------
    add("doc_new", "unnamed", prep(), {})
    add("doc_new", "named with a space", prep(), {"name": "My part"})
    add("doc_new", "a name taken", prep(gui=True), {"name": "Model"})
    C = "doc_close"
    add(C, "the current one, empty", prep(), {})
    add(C, "the current one, another open", prep(other), {})
    add(C, "not names", prep(), {"documents": [1]})
    add(C, "an empty name", prep(), {"documents": ["Model", ""]})
    add(C, "none by that name", prep(other), {"documents": ["Nope"]})
    add(C, "a label two share", prep(lambda s: other(s, name="A", label="Twin"), lambda s: other(s, name="B", label="Twin")), {"documents": ["Twin"]})
    add(C, "two of one label left open", prep(lambda s: other(s, name="A", label="Twin"), lambda s: other(s, name="B", label="Twin")), {})
    add(C, "changed", prep(lambda s: other(s, changed=True)), {"documents": ["Other"]})
    add(C, "changed, with marks", prep(lambda s: other(s, changed=True, touched=["Pad", "Sketch"])), {"documents": "Other part"})
    add(C, "never saved and not empty", prep(block), {})
    add(C, "discarded", prep(block, other), {"discard": True})
    add(C, "another, by its file", prep(lambda s: other(s, file=os.path.join(s.out_dir, "o.FCStd"))), {"documents": ["o.FCStd"]})
    add(C, "two, one named twice", prep(other, lambda s: other(s, name="Third", label="Third")), {"documents": ["Other", "other", "Third"]})

    def came_from(s):
        other(s)
        other(s, name="Third", label="Third")
        s.doc_trail = ["Third", "Other", "Model"]

    add(C, "the current one, back where it came from", prep(came_from), {})
    add(C, "the session's own, no longer listed", prep(lambda s: fc.docs().pop("Model"), other), {"documents": ["Model"]})
    O = "doc_open"
    add(O, "the recent files", prep(file("a.FCStd"), recent=["/nowhere/b.FCStd"]), {"recent": True})
    add(O, "no recent files", prep(), {"recent": True})
    add(O, "no path", prep(), {})
    add(O, "a path that is not text", prep(), {"path": 5})
    add(O, "no such file", prep(), {"path": "gone.FCStd"})
    add(O, "not a document", prep(file("part.step")), {"path": "part.step"})
    add(O, "a file", prep(file("bracket.FCStd")), {"path": "bracket.FCStd", "recent": True})
    add(O, "a file FreeCAD will not open", prep(file("bad.FCStd"), fail=("openDocument",)), {"path": "bad.FCStd"})
    add(O, "open already, changed", prep(file("o.FCStd"), lambda s: other(s, changed=True, file=os.path.join(s.out_dir, "o.FCStd")), gui=True), {"path": "o.FCStd"})
    add(O, "open already, as saved", prep(file("o.FCStd"), lambda s: other(s, file=os.path.join(s.out_dir, "o.FCStd"))), {"path": "o.FCStd"})
    W = "doc_save"
    add(W, "to a path", prep(block), {"path": "out/bracket"})
    add(W, "over another's file", prep(file("taken.FCStd")), {"path": "taken.FCStd"})
    add(W, "over another's file, allowed", prep(file("taken.FCStd")), {"path": "taken.FCStd", "overwrite": True})
    add(W, "where it was saved", prep(file("m.FCStd"), lambda s: s.doc.__dict__.update(FileName=os.path.join(s.out_dir, "m.FCStd"), touched=["Pad"]), gui=True), {})
    add(W, "to its own file by path", prep(file("m.FCStd"), lambda s: s.doc.__dict__.update(FileName=os.path.join(s.out_dir, "m.FCStd"))), {"path": "m.FCStd"})
    add(W, "never saved", prep(), {})
    add(W, "never saved, the name taken", prep(file("Model.FCStd")), {})
    add(W, "never saved, the name taken twice", prep(file("Model.FCStd"), file("Model 2.FCStd"), relabel=False), {})
    add(W, "never saved, the name taken, written over", prep(file("Model.FCStd")), {"overwrite": True})

    # ---- objects ---------------------------------------------------------------------------------
    def furniture(s):
        b = block(s)
        fc.body("Outline", fc.wire("outline", [(0, 0, 0), (10, 0, 0), (10, 10, 0)]), name="Outline")
        scan(s)
        s.doc.new("App::FeaturePython", "AgentLinkRecords")
        bad = fc.body("Broken", fc.Shape(), name="Broken", State=["Touched", "Invalid"])
        bad.InList.extend([b, b])
        return b

    L = "object_list"
    add(L, "everything", prep(furniture), {})
    add(L, "by type", prep(furniture), {"type": "mesh::"})
    add(L, "an empty document", prep(), {"type": ""})
    G = "object_get"

    def detailed(s):
        b = block(s)
        b.__dict__.update(modes={"Length": ["ReadOnly"], "Mode": ["Hidden"]}, status={"Mode": ["Hidden"], "Shape": ["Output"]}, Proxy=object(), Many=list(range(60)))
        return b

    add(G, "all of it", prep(detailed), {"object": "Block"})
    add(G, "a word", prep(detailed), {"object": "Block", "filter": "leng"})
    add(G, "a group's name", prep(detailed), {"object": "Block", "filter": "box"})
    add(G, "exact names", prep(detailed), {"object": "block", "filter": ["Mode", "Placement", "Nope"]})
    add(G, "a filter that matches nothing", prep(detailed), {"object": "Block", "filter": "zzz"})
    add(G, "names that match nothing", prep(detailed), {"object": "Block", "filter": ["Nope"]})
    add(G, "an empty filter", prep(detailed), {"object": "Block", "filter": ""})
    add(G, "no such object", prep(detailed), {"object": "Sphere"})
    add(G, "no object", prep(detailed), {})
    P = "object_set"
    add(P, "a length and a placement", prep(block), {"object": "Block", "values": {"Length": 20, "Placement": {"at": [1, 2, 3]}}})
    add(P, "a length with its unit, a choice", prep(block), {"object": "Block", "values": {"Length": "1 in", "Mode": "Shell"}})
    add(P, "the value it has", prep(block), {"object": "Block", "values": {"Length": 10, "Mode": "Shell"}})
    add(P, "no values", prep(block), {"object": "Block", "values": {}})
    add(P, "values not an object", prep(block), {"object": "Block", "values": [1]})
    add(P, "no such object", prep(block), {"object": "Sphere", "values": {"Length": 1}})
    add(P, "no such property", prep(block), {"object": "Block", "values": {"Lenght": 20}})
    add(P, "no such property, nothing near", prep(block), {"object": "Block", "values": {"Length": 20, "Qqq": 1}})
    add(P, "read-only", prep(lambda s: block(s).__dict__.update(modes={"Length": ["ReadOnly"]})), {"object": "Block", "values": {"Length": 20}})
    add(P, "read-only visibility", prep(lambda s: block(s).__dict__.update(status={"Visibility": ["Immutable"]})), {"object": "Block", "values": {"Visibility": False}})
    add(P, "not a choice", prep(block), {"object": "Block", "values": {"Mode": "Hollow"}})
    add(P, "a placement key there is not", prep(block), {"object": "Block", "values": {"Length": 5, "Placement": {"where": [0, 0, 0]}}})
    add(P, "a shape", prep(block), {"object": "Block", "values": {"Shape": "a box"}})
    add(P, "a value FreeCAD refuses", prep(lambda s: block(s).__dict__.update(refuses=("Length",))), {"object": "Block", "values": {"Mode": "Shell", "Length": -5}})
    add(P, "the recompute fails", prep(lambda s: block(s).__dict__.update(breaks=("Length",))), {"object": "Block", "values": {"Length": 0.001}})
    add(P, "others failed before", prep(block, pin, objects_invalid=True), {"object": "Block", "values": {"Length": 12}})
    X = "object_delete"

    def cut(s):
        from agentlink.families import picks

        b, p = block(s), pin(s)
        helper = fc.body("Helper", fc.solid("helper", (0, 0, 0), (1, 1, 1), volume=1.0), name="Helper")
        c = fc.body("Cut", fc.solid("cut", (0, 0, 0), (10, 10, 10), volume=900.0), name="Cut")
        b.InList.append(c)
        helper.InList.append(c)
        b.__dict__.update(Visibility=False, Label="Block (in Cut)")
        c.__dict__.update({picks.MADE_PROP: ["Helper", "Gone"], picks.HID_PROP: ["Body", "Gone"], picks.LABEL_PROP: ["Body=Block", "=x"]})
        return c

    def pd_body(s):
        f = s.doc.new("PartDesign::Pad", "Pad")
        origin = s.doc.new("App::Origin", "Origin")
        plane = s.doc.new("App::Plane", "XY_Plane")
        origin.__dict__["OriginFeatures"] = [plane]
        b = fc.body("Housing", fc.solid("housing", (0, 0, 0), (5, 5, 5), volume=125.0), type_="PartDesign::Body", name="Housing", Group=[f], Origin=origin, BaseFeature=None)
        for x in (f, origin):
            x.InList.append(b)
        plane.InList.append(origin)
        return b

    add(X, "nothing named", prep(block), {"objects": []})
    add(X, "one", prep(block, pin), {"objects": "Pin"})
    add(X, "two", prep(block, pin), {"objects": ["Pin", "Block"]})
    add(X, "one there is not", prep(block), {"objects": ["Block", "Sphere"]})
    add(X, "used by another", prep(cut), {"objects": ["Block (in Cut)"]})
    add(X, "used by another, forced", prep(cut), {"objects": ["Block (in Cut)"], "force": True})
    add(X, "with what uses it", prep(cut), {"objects": ["Block (in Cut)", "Cut"]})
    add(X, "a result with its helper, inputs shown again", prep(cut), {"objects": ["Cut"]})
    add(X, "a result, the old label taken", prep(cut, lambda s: fc.body("Block", fc.solid("b2", (0, 0, 0), (1, 1, 1), volume=1.0), name="Block2")), {"objects": ["Cut"]})
    add(X, "a body with its features and origin", prep(pd_body, block), {"objects": ["Housing"]})
    add(X, "what is left is broken", prep(block, pin, objects_invalid=True), {"objects": ["Pin"]})
    R = "object_rename"
    add(R, "a new label", prep(block, lambda s: s.meta.update({"Block": {"material": "PLA"}})), {"object": "Block", "label": "Base"})
    add(R, "no label", prep(block), {"object": "Block"})
    add(R, "a blank label", prep(block), {"object": "Block", "label": "  "})
    add(R, "a label taken", prep(block, pin), {"object": "Block", "label": "Pin"})
    add(R, "the same label", prep(block), {"object": "Block", "label": "Block"})
    add(R, "a label FreeCAD changes", prep(lambda s: block(s).__dict__.update(relabels=True)), {"object": "Block", "label": "Base"})
    add(R, "no such object", prep(block), {"object": "Sphere", "label": "Ball"})
    Q = "object_group"

    def binned(s):
        b, p = block(s), pin(s)
        g = s.doc.new("App::DocumentObjectGroup", "Group", Group=[b])
        g.__dict__["Label"] = "Bin"
        b.InList.append(g)
        s.doc.new("App::Origin", "Origin", Group=[])
        ln = s.doc.new("App::Link", "Link", LinkedObject=p)
        ln.__dict__["Label"] = "Pin link"
        return g

    add(Q, "the groups", prep(binned), {"action": "list"})
    add(Q, "three links", prep(block), {"action": "link", "object": "Block", "count": 3, "at": [0, 0, 5], "step": [20, 0, 0], "name": "Peg"})
    add(Q, "one link", prep(block), {"action": "link", "object": "Block"})
    add(Q, "links of nothing", prep(block), {"action": "link"})
    add(Q, "no links", prep(block), {"action": "link", "object": "Block", "count": 0})
    add(Q, "true links", prep(block), {"action": "link", "object": "Block", "count": True})
    add(Q, "links stepped by words", prep(block), {"action": "link", "object": "Block", "step": "far"})
    add(Q, "an action there is not", prep(block), {"action": "move", "group": "Bin"})
    add(Q, "no group", prep(block), {"objects": ["Block"]})
    add(Q, "a kind there is not", prep(block), {"group": "Kit", "kind": "box"})
    add(Q, "a new folder", prep(block, pin), {"group": "Kit", "objects": ["Block"]})
    add(Q, "a new part with two", prep(block, pin), {"action": "add", "group": "Kit", "kind": "part", "objects": ["Block", "Pin"]})
    add(Q, "an object there is not", prep(block), {"group": "Kit", "objects": ["Sphere"]})
    add(Q, "from one group to another", prep(binned), {"group": "Kit", "objects": ["Block", "Pin"]})
    add(Q, "into the group it is in, and the group itself", prep(binned), {"group": "Bin", "objects": ["Block", "Bin"]})
    add(Q, "no such group to remove from", prep(binned), {"action": "remove", "group": "Nope", "objects": ["Block"]})
    add(Q, "no such group to dissolve", prep(block), {"action": "dissolve", "group": "Nope"})
    add(Q, "nothing to take out", prep(binned), {"action": "remove", "group": "Bin"})
    add(Q, "taken out", prep(binned), {"action": "remove", "group": "Bin", "objects": ["Block"]})
    add(Q, "not in it", prep(binned), {"action": "remove", "group": "Bin", "objects": ["Block", "Pin"]})
    add(Q, "hidden", prep(binned), {"action": "remove", "group": "Bin", "visible": False})
    add(Q, "added and shown, one that cannot be", prep(binned, lambda s: s.doc.getObject("Pin").__dict__.update(refuses=("Visibility",))), {"group": "Bin", "objects": "Pin", "visible": True})
    add(Q, "dissolve", prep(binned), {"action": "dissolve", "group": "Bin"})
    N = "recompute"
    add(N, "plain", prep(block, pin), {})
    add(N, "forced", prep(block, pin), {"force": True})
    add(N, "forced, on a FreeCAD that takes no force", prep(block, pin, old_recompute=True), {"force": True})
    add(N, "frozen", prep(block, lambda s: s.doc.__dict__.update(RecomputesFrozen=True), recomputed=0), {})
    add(N, "frozen, forced, still touched", prep(lambda s: block(s).__dict__.update(State=["Touched"]), lambda s: s.doc.__dict__.update(RecomputesFrozen=True), recomputed=0), {"force": True})
    add(N, "still touched, with errors", prep(lambda s: block(s).__dict__.update(State=["Touched", "Invalid"]), pin, objects_invalid=True), {})

    # ---- files in --------------------------------------------------------------------------------
    M = "import_file"
    add(M, "no path", prep(), {})
    add(M, "no such file", prep(), {"path": "gone.step"})
    add(M, "a STEP", prep(file("bracket.step")), {"path": "bracket.step"})
    add(M, "a STEP, a body per solid", prep(file("pair.stp"), file_solids=2), {"path": "pair.stp", "split": True, "name": "Half"})
    add(M, "a STEP of two, kept whole, the name taken", prep(file("Block.STEP"), block, file_solids=2), {"path": "Block.STEP"})
    add(M, "an IGES of faces", prep(file("skin.igs"), file_solids=0), {"path": "skin.igs", "split": True})
    add(M, "a BREP that will not read", prep(file("bad.brep"), fail=("Shape.read",)), {"path": "bad.brep"})
    add(M, "an STL as a mesh", prep(file("scan.stl")), {"path": "scan.stl"})
    add(M, "an STL as a body", prep(file("scan.stl")), {"path": "scan.stl", "solid": True, "name": "Scan body"})
    add(M, "an STL as a body, the shell will not close", prep(file("scan.stl"), fail=("makeShell",), missing=("Part.Shell",)), {"path": "scan.stl", "solid": True})
    add(M, "an OBJ too big for a body", prep(file("big.obj"), facets=300000), {"path": "big.obj", "solid": True})
    add(M, "a big OBJ as a mesh", prep(file("big.obj"), facets=300000), {"path": "big.obj", "solid": False})
    add(M, "a PLY of nothing", prep(file("empty.ply"), facets=0), {"path": "empty.ply"})
    add(M, "a 3MF that will not read", prep(file("bad.3mf"), fail=("Mesh",)), {"path": "bad.3mf"})
    add(M, "a glTF by FreeCAD's own reader", prep(file("toy.glb")), {"path": "toy.glb"})
    add(M, "a glTF with units, by Agent Link's reader", prep(file("toy.glb")), {"path": "toy.glb", "units": "m"})
    add(M, "a glTF FreeCAD's reader reads nothing of", prep(file("toy.gltf", "{}"), inserted=0), {"path": "toy.gltf"})
    add(M, "a VRML that is not one", prep(file("toy.wrl")), {"path": "toy.wrl", "up": "y"})
    add(M, "a DXF nothing here reads", prep(file("plan.dxf")), {"path": "plan.dxf"})
    add(M, "a document", prep(file("m.FCStd")), {"path": "m.FCStd"})
    add(M, "an SVG", prep(file("logo.svg")), {"path": "logo.svg"})
    add(M, "an SVG of many paths", prep(file("logo.svg"), inserted=14), {"path": "logo.svg"})
    add(M, "an SVG of nothing", prep(file("logo.svg"), inserted=0), {"path": "logo.svg"})
    add(M, "an SVG that will not read", prep(file("logo.svg"), fail=("importSVG.insert",)), {"path": "logo.svg"})
    add(M, "an SVG with no importer", prep(file("logo.svg"), missing=("importSVG",)), {"path": "logo.svg"})
    add(M, "a JT", prep(file("part.jt")), {"path": "part.jt"})
    add(M, "a JT where the reader is left out", prep(file("part.jt"), missing=("JtReader",)), {"path": "part.jt"})
    add(M, "a JT that will not read", prep(file("part.jt"), fail=("JtReader.insert",)), {"path": "part.jt"})
    add(M, "a picture", prep(picture("photo.png")), {"path": "photo.png", "width": 250})
    add(M, "a picture that is not one", prep(file("photo.jpg")), {"path": "photo.jpg", "name": "Trace"})
    add(M, "a picture of no width", prep(picture("photo.png")), {"path": "photo.png", "width": 0})
    add(M, "a picture where there are no image planes", prep(picture("photo.bmp"), no_image_planes=True), {"path": "photo.bmp"})
    add(M, "a PDF", prep(file("plan.pdf")), {"path": "plan.pdf"})
    add(M, "an IFC", prep(file("house.IFC")), {"path": "house.IFC"})
    add(M, "an FBX", prep(file("toy.fbx")), {"path": "toy.fbx"})
    add(M, "a file with no extension", prep(file("README")), {"path": "README"})
    add(M, "a file named for a kind", prep(file("x.solid")), {"path": "x.solid"})

    # ---- files out -------------------------------------------------------------------------------
    Z = "export"
    add(Z, "no body", prep(), {})
    add(Z, "which body", prep(block, pin), {})
    add(Z, "one body, STEP", prep(block), {})
    add(Z, "an object there is not", prep(block), {"objects": ["Sphere"]})
    add(Z, "an object with no shape", prep(block, lambda s: s.doc.new("App::FeaturePython", "Note")), {"objects": "Note"})
    add(Z, "a format there is not", prep(block), {"format": "FBX"})
    add(Z, "the format from the path", prep(block), {"path": "out/block.BRP"})
    add(Z, "IGES, faces read back", prep(block, file_solids=0), {"format": "iges", "objects": "Block"})
    add(Z, "IGES, solids read back", prep(block), {"format": "IGES", "path": "b.igs"})
    add(Z, "two as one compound, a path with another ending", prep(block, pin), {"objects": ["Block", "Pin"], "format": "step", "path": "pair.v2"})
    add(Z, "an STL of a body", prep(block), {"format": "stl", "tolerance": 0.05})
    add(Z, "a VRML FreeCAD cannot read back", prep(block), {"format": "wrl"})
    add(Z, "an X3D that will not read back", prep(block, fail=("Mesh",)), {"format": "x3d"})
    add(Z, "a tolerance of nothing", prep(block), {"format": "stl", "tolerance": 0})
    add(Z, "a tolerance in words", prep(block), {"format": "obj", "tolerance": "fine"})
    add(Z, "a tolerance of nothing, for a scene", prep(block), {"format": "glb", "tolerance": -1})
    add(Z, "a scene with a colour that is not one", prep(block), {"format": "glb", "colors": {"Block": "red"}})
    add(Z, "a mesh, as it is", prep(scan), {"objects": "Scan"})
    add(Z, "a mesh in a scene", prep(scan), {"objects": ["Scan"], "format": "glb", "colors": {"Scan": "#ff0000"}})
    add(Z, "a body in a scene", prep(block), {"format": "gltf", "colors": {"Body": [0, 1, 0]}})
    add(Z, "a view as a drawing", prep(block), {"format": "dxf", "view": "front", "hidden": True})
    add(Z, "a view as a picture, from the top", prep(block), {"format": "svg", "path": "top"})
    add(Z, "a view that comes out empty", prep(block, projected=False), {"format": "svg"})
    add(Z, "a view there is not", prep(block), {"format": "svg", "view": "under"})
    add(Z, "a section", prep(block), {"format": "svg", "section": 5})
    add(Z, "a mesh as STEP", prep(scan), {"format": "step", "objects": ["Scan"]})
    add(Z, "a mesh as a drawing", prep(scan, block), {"path": "flat.dxf", "objects": ["Block", "Scan"]})
    add(Z, "a mesh and a body, merged", prep(scan, block), {"objects": ["Scan", "Block"], "format": "obj", "path": "both"})
    add(Z, "a mesh, open when read back", prep(scan, mesh_closed=False), {"objects": ["Scan"], "format": "ply"})
    add(Z, "a moved mesh, written where it stands", prep(scan, moved=True), {"objects": ["Scan"], "format": "off", "path": "moved.off"})
    add(Z, "a mesh that will not read back", prep(scan, fail=("Mesh",)), {"objects": ["Scan"], "format": "3mf"})
    add(Z, "a mesh as VRML", prep(scan), {"objects": ["Scan"], "format": "wrl"})
    add(Z, "a mesh at a tolerance of nothing", prep(scan), {"objects": ["Scan"], "tolerance": 0})
    add(Z, "a mesh at a tolerance in words", prep(scan), {"objects": ["Scan"], "tolerance": "fine"})
    add(Z, "a mesh in a scene, a colour that is not one", prep(scan), {"objects": ["Scan"], "format": "gltf", "colors": {"Scan": [2, 0, 0]}})
    add(Z, "a section where there is nothing", prep(block, slices=0), {"format": "svg", "section": 50})
    add(Z, "a section at a height in words", prep(block), {"format": "dxf", "section": "mid"})
    return out
