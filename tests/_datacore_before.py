# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the hub's own core tools of families/view.py, dev.py,
# unattended.py and doc.py now kept as data, at the commit they were converted
# from (tests/test_datacore_data.py's BASE): name, description, inputSchema,
# changes, reads, group. Written by
#   python3 tests/test_datacore_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "view_maps": {
  "name": "view_maps",
  "description": "The maps and layers view_render can draw here (add-ons add theirs), and the views.",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "view"
 },
 "view_snapshot": {
  "name": "view_snapshot",
  "description": "Save the FreeCAD window's own 3D view as the person sees it (view: turn it to a standard view first, fit true) and look at it. views [..] (up to 6, or \"all\") gives one grid picture of them, each view's file in paths, and puts the person's view back. width and height (800 x 600) are the whole picture — the grid with several views, split among them; cell: true makes them each view's size instead. The answer gives the sizes as saved. When nothing with a shape is shown (an empty document, everything hidden), or the model lies outside the frame or is under 6 pixels across as the view stands, the answer is empty with the reason and what to do, and no picture is taken. fitted: false with fitNote says the view was not re-fitted (no view given: as the person left it; or fit: false), so parts may be cut off. Needs the window; view_render draws without one.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "cell": {
     "type": "boolean",
     "description": "width and height are each view's in the grid, not the whole grid's."
    },
    "view": {
     "type": "string"
    },
    "views": {
     "description": "A list of views (iso, top, bottom, front, rear, left, right), up to 6, or \"all\" (iso, top, front, right): one grid picture."
    },
    "fit": {
     "type": "boolean"
    },
    "width": {
     "type": "integer"
    },
    "height": {
     "type": "integer"
    },
    "background": {
     "type": "string"
    },
    "inline": {
     "type": "boolean"
    },
    "path": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "view"
 },
 "gui_unstick": {
  "name": "gui_unstick",
  "description": "Close the menu, drop-down list or dialog that holds the FreeCAD window (Escape's effect: a menu closes, a dialog is cancelled, nothing in it is accepted), even while it holds every other call (it is answered off the GUI thread). all: true closes each one in front, dialogs under a menu too. Reply: what was closed and what is still open (dialog_answer presses a named button instead; a window that stays stuck: app_force_restart). Window only.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "all": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "dev"
 },
 "addon_test": {
  "name": "addon_test",
  "description": "An installed add-on's own tests (its tests/ folder) run in the background in a separate FreeCAD command-line process, never this FreeCAD: documents, the window and settings are untouched, and the tests get a fresh ~/AgentLink. addon starts a run: its folder in FreeCAD's Mod folder (one the launcher installed) or AgentLink; folder: only this subfolder of tests/ (e.g. make); pattern: test files (test_*.py); select: only tests whose id holds it; timeout: seconds (600, at most 1800). It answers at once with the job (the result itself when it finishes within 20 s); job answers how it stands (counts so far, or the counts, the time and each failure's last traceback lines), waiting up to 30 s for the end — call it again while state is running. Neither: the recent jobs. The full log is under ~/AgentLink/tests; a run is stopped at its timeout or when FreeCAD quits.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "addon": {
     "type": "string"
    },
    "job": {
     "type": "string"
    },
    "folder": {
     "type": "string"
    },
    "pattern": {
     "type": "string"
    },
    "select": {
     "type": "string"
    },
    "timeout": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "dev"
 },
 "queue_go": {
  "name": "queue_go",
  "description": "The person's go for heavy jobs held while they worked in the window: call it only on their word in chat, never by yourself. It lifts the hold; nothing else changes. Reply: wasHeld, running (the heavy tools running now), machine (this computer's preset: heavySlots, memoryCeilingGB, fan).",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "unattended"
 },
 "doc_switch": {
  "name": "doc_switch",
  "description": "Which open document the agent works in. document (internal name, label or .FCStd path) switches the session to it; it stays there whatever the person brings to the front of the window. front: true also brings its 3D view to the front — needed before gui_input, cmd_run and menu_run, which act on the document in front. With no document: the session's one and open [{ name, label, file, modified }]. Reply: document, label, front, bodies. Changes no document; the session's undo steps start afresh in the new one.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "document": {
     "type": "string"
    },
    "front": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "unattended"
 },
 "crash_collect": {
  "name": "crash_collect",
  "description": "Copy crash evidence into ~/AgentLink/crash/<time>/: FreeCAD's document-recovery folders (from a FreeCAD that crashed or was stopped), its crash.log and the system's crash reports for FreeCAD (new ones only). Copies only, never removes. dialog_answer runs it by itself before Document Recovery's Cleanup.",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "unattended"
 },
 "dialog_answer": {
  "name": "dialog_answer",
  "description": "The modal dialog in the FreeCAD window, if any (title, text, buttons); button presses one by its text (Cancel also closes a file picker; Document Recovery's Cleanup keeps a copy in ~/AgentLink/crash first). With no dialog, the open task panel and its buttons (OK, Cancel …). You operate FreeCAD as the person would: read it and press what the job needs (Cancel backs out of anything you did not mean to open); say what you pressed. text: typed into a text prompt (or the dialog's one text field), item: picked from a prompt's list, before button. A stuck window: app_force_restart.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "button": {
     "type": "string"
    },
    "text": {
     "type": "string"
    },
    "item": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "unattended"
 },
 "doc_new": {
  "name": "doc_new",
  "description": "Start a new, empty FreeCAD document and work in it from now on. name becomes its label; FreeCAD makes the internal name from it (spaces and odd characters become _, a number is added when taken): the reply's document is that name, label the label. The document before stays open, unsaved changes and all (doc_switch returns to it). Not undoable, and not in a batch's rollback.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "doc"
 },
 "doc_close": {
  "name": "doc_close",
  "description": "Close open documents. documents: each by internal name, label or .FCStd path (the current one when left out); a label two documents share is refused with their names. A document changed since its save (or never saved and not empty) is refused and nothing is closed: doc_save first, or discard: true closes WITHOUT saving and the changes are lost (there is no save input here). Work moves to another open document (reply: document, label, open — the labels of the documents still open, each as \"Label (Name)\" where two share a label; discarded lists what lost changes). Not undoable.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "documents": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "discard": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "doc"
 },
 "doc_open": {
  "name": "doc_open",
  "description": "Open a FreeCAD document (path, .FCStd; relative: the session's folder) and work in it from now on. It is recomputed and each object's error listed (errors); a file just opened is left unmodified by that. A file already open is not read again: the open document is used with its unsaved changes (doc_revert goes back to the file). Other formats: import_file. recent: true lists the recent files instead. Reply: document (internal name), label, objects, bodies, errors. Not undoable.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "recent": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "doc"
 },
 "doc_save": {
  "name": "doc_save",
  "description": "Save the current document as .FCStd: path (relative goes in the session's folder; .FCStd added), else where it was saved, else <label>.FCStd there (\"<label> 2.FCStd\" … when taken). Saving under a new file name makes FreeCAD relabel the document after the file (reply: label, labelWas); its internal name stays. Never over another document's file unless overwrite: true — ask the person first. Materials, setups and notes the tools recorded are saved with it. Reply: path, bytes, touched / modified.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "overwrite": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "doc"
 },
 "object_list": {
  "name": "object_list",
  "description": "Every object in the document: name (internal, fixed for life, unique), label (what the person sees and may rename), type, visible, parents (what uses it) and its shape (volume mm³, area, faces, solids, size for a solid; faces and edges else) or mesh; error: true marks a failed one (recompute gives the reason). type: part of the type to keep (\"Part::\", \"Sketch\"). Tools take either name or label; the name wins when both match. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "type": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "doc"
 },
 "object_get": {
  "name": "object_get",
  "description": "One object's properties: value (mm, degrees; placements as { at, axis, angle }; links by label; a shape as its stats; lists cut at 50), type, readOnly (FreeCAD computes it: object_set refuses it), hidden (not shown in FreeCAD's property editor), choices for an enumeration. filter: a word in the property's name or group (\"Placement\", \"Base\"), or a list of exact names — use it, a feature has dozens. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "object": {
     "type": "string",
     "description": "An object's name or label."
    },
    "filter": {}
   },
   "required": [
    "object"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "doc"
 },
 "object_set": {
  "name": "object_set",
  "description": "Set properties of an object: values { Length: 20, Placement: { at, axis, angle } (or FreeCAD's Base, Axis, Angle, Rotation; what is left out is kept), Refine: true, Base: \"Box\" (a link, by name or label; null clears), Mode: \"…\" } — each converted to its type: numbers are mm and degrees, or a string with a unit (\"1 in\", \"30 deg\") for lengths, angles and other quantities (not plain floats); whole numbers for integers and percents; enumerations checked against their choices; vectors [x,y,z]. Read-only properties, links to faces or edges and property names it does not have are refused (object_get lists names, types, choices). Recomputes the object and what is built from it; refused with nothing kept when that fails. Reply: set { from, to }, unchanged, health. Trap: a plain shape (Part::Feature from a boolean or import) has no sizes, only Placement; Label is set with object_rename.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "object": {
     "type": "string",
     "description": "An object's name or label."
    },
    "values": {
     "type": "object"
    }
   },
   "required": [
    "object",
    "values"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "doc"
 },
 "object_delete": {
  "name": "object_delete",
  "description": "Delete objects (objects: names or labels). Refused, nothing deleted, while another object uses one — FreeCAD itself deletes without asking and leaves the users broken, which force: true allows. Recomputes and lists any error. A PartDesign Body goes with its own features and Origin, and a boolean's result with the helpers made for it alone (alongWith names them); the inputs it hid are shown again and given their names back (shownAgain, renamed). Reply: deleted, errors, health.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {},
    "force": {
     "type": "boolean"
    }
   },
   "required": [
    "objects"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "doc"
 },
 "object_rename": {
  "name": "object_rename",
  "description": "Give an object a new label; its internal name never changes (FreeCAD fixes it at creation), and both keep working as references. A label another object has is refused (FreeCAD would alter it to stay unique unless its duplicate-labels preference is on). Expressions that use the label follow it. Trap: setups, specs and waivers keep the old label. Reply: name, from, to.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "object": {
     "type": "string",
     "description": "An object's name or label."
    },
    "label": {
     "type": "string"
    }
   },
   "required": [
    "object",
    "label"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "doc"
 },
 "object_group": {
  "name": "object_group",
  "description": "Organise the document: action add | remove (objects into or out of group — made if new for add; kind folder (App::DocumentObjectGroup, placement-less) | part (App::Part: its Placement moves everything in it)) — an object sits in one group, so add takes it out of the one before; dissolve (the group goes, its objects stay); link (count App::Link copies of object, the first at, each step [dx,dy,dz] further — light copies that follow the original; at is the link's whole placement, not an offset from the original's); list (groups, parts and links with what they hold). visible: false hides a group's objects. Reply: group, type, holds.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "action": {
     "type": "string",
     "enum": [
      "add",
      "remove",
      "dissolve",
      "link",
      "list"
     ]
    },
    "group": {
     "type": "string"
    },
    "kind": {
     "type": "string",
     "enum": [
      "folder",
      "part"
     ]
    },
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "object": {
     "type": "string"
    },
    "count": {
     "type": "integer"
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "step": {
     "type": "array",
     "items": {}
    },
    "visible": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "doc"
 },
 "recompute": {
  "name": "recompute",
  "description": "Recompute the document and list each object that failed, with FreeCAD's reason (errors). Only touched objects and what is built from them are redone; force: true marks everything touched and recomputes it all, also past the document's skip-recompute switch (slow on a big model). Reply: recomputed (how many objects FreeCAD ran; 0 with nothing touched or with skip-recompute on, said in note), ok, errors, stillTouched. Tools that change the model recompute by themselves: this is for after object_freeze, an import or a doubt.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "force": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "doc"
 },
 "import_file": {
  "name": "import_file",
  "description": "Bring a file into the current document (path; relative: the session's folder), by its extension. STEP, IGES, BREP: one body with the file's whole shape (split: true a body per solid); colours, part names and assembly structure are not read. STL, OBJ, 3MF, PLY, OFF, AMF and glTF/GLB, Collada, VRML 2, 3DS (every mesh node flattened into one, mm, Z up; units and up override what the format says; read says what was taken): a mesh (Mesh::Feature) unless solid: true asks for a body of its triangles (up to 200000; slow past a few tens of thousands). DXF: wires, arcs, circles, splines by layer (Agent Link's reader; a drawing with blocks, text or dimensions through FreeCAD's) and SVG as Draft geometry — many objects come back counted, the first few listed. JT where this FreeCAD has its reader. PNG, JPG, BMP: an image plane width mm wide on XY, to trace over. PDF, DWG, IFC need the FreeCAD window; FBX: export it as glTF; .FCStd: doc_open (doc_merge to bring its objects in). name: the label. Reply: format, count, objects (name, label, type, volume or mesh), health.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "name": {
     "type": "string"
    },
    "split": {
     "type": "boolean"
    },
    "solid": {
     "type": "boolean"
    },
    "units": {
     "type": "string",
     "enum": [
      "mm",
      "cm",
      "m",
      "in"
     ]
    },
    "up": {
     "type": "string",
     "enum": [
      "x",
      "y",
      "z"
     ]
    },
    "width": {
     "type": "number"
    }
   },
   "required": [
    "path"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "doc"
 },
 "export": {
  "name": "export",
  "description": "Write objects (the one body when left out; several go as one compound) and read it back (verify). Meshes (Mesh::Feature) go as they are to the mesh and scene formats (STL by default). Solids: STEP, IGES, BREP. One mesh: STL, OBJ, 3MF, PLY, OFF, VRML (wrl), X3D. A scene, a mesh per object with colors {label: \"#rrggbb\"}: glTF (glb, gltf), Collada (dae) — metres, Y up. 2D: DXF (R12) or SVG of a view (top | bottom | front | back | right | left | iso; hidden: true adds hidden lines on their own layer) or of a section at z mm (section) — circles and arcs kept as such, for laser and plasma cutting. format, or from path's extension; tolerance: the chord error, 0.01 mm.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {},
    "format": {
     "type": "string",
     "enum": [
      "step",
      "iges",
      "brep",
      "stl",
      "obj",
      "3mf",
      "ply",
      "off",
      "wrl",
      "x3d",
      "glb",
      "gltf",
      "dae",
      "dxf",
      "svg"
     ]
    },
    "path": {
     "type": "string"
    },
    "tolerance": {
     "type": "number"
    },
    "colors": {
     "type": "object"
    },
    "view": {
     "type": "string",
     "enum": [
      "top",
      "bottom",
      "front",
      "back",
      "right",
      "left",
      "iso"
     ]
    },
    "hidden": {
     "type": "boolean"
    },
    "section": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "doc"
 }
}
''')
