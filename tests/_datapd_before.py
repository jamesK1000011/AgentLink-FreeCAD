# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the Part Design and Sketcher tools now kept as data,
# at the commit they were converted from (tests/test_datapd_data.py's BASE):
# name, description, inputSchema, changes, reads, group. Written by
#   python3 tests/test_datapd_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "pd_pad": {
  "name": "pd_pad",
  "description": "Pad a closed sketch into the body, along its normal: type length (length mm) | up_to_last | up_to_first | up_to_face (upToFace { at, normal } or \"Face8\"); sides one | two (length2 the other way) | symmetric; reversed; taper deg. The first pad takes a length. An open sketch (sketch_state first) or a pad inside the body is refused. Faces and edges are renumbered: query again. Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "sketch": {
     "type": "string",
     "description": "The sketch, in the body."
    },
    "type": {
     "type": "string"
    },
    "length": {
     "type": "number"
    },
    "length2": {
     "type": "number"
    },
    "sides": {
     "type": "string",
     "enum": [
      "one",
      "two",
      "symmetric"
     ]
    },
    "reversed": {
     "type": "boolean"
    },
    "upToFace": {
     "description": "The face to go up to: { at, normal }, \"Face8\", or shape_query's filters."
    },
    "taper": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_pocket": {
  "name": "pd_pocket",
  "description": "Pocket a closed sketch out of the body: type length | through_all | up_to_first | up_to_face (upToFace); sides one | two (length2) | symmetric; reversed; taper. It cuts against the sketch's normal: one that cuts nothing is refused — reversed: true, or sketch on the face it enters. A cut that splits the body leaves 2 solids (allowed by its AllowCompound; health says so). Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "sketch": {
     "type": "string",
     "description": "The sketch, in the body."
    },
    "type": {
     "type": "string"
    },
    "length": {
     "type": "number"
    },
    "length2": {
     "type": "number"
    },
    "sides": {
     "type": "string",
     "enum": [
      "one",
      "two",
      "symmetric"
     ]
    },
    "reversed": {
     "type": "boolean"
    },
    "upToFace": {
     "description": "The face to go up to: { at, normal }, \"Face8\", or shape_query's filters."
    },
    "taper": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_revolution": {
  "name": "pd_revolution",
  "description": "Revolve a closed sketch about an axis: axis V_Axis (default) | H_Axis (the sketch's) | x | y | z (the body's) | a datum line | a line's geometry id (from 0); angle deg (360); sides one | symmetric; reversed. The profile must not cross the axis. Two angles: feature_edit { Type: \"TwoAngles\", Angle2 }. Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "sketch": {
     "type": "string",
     "description": "The sketch, in the body."
    },
    "axis": {
     "type": [
      "string",
      "integer"
     ]
    },
    "angle": {
     "type": "number"
    },
    "sides": {
     "type": "string"
    },
    "reversed": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_groove": {
  "name": "pd_groove",
  "description": "Cut by revolving a closed sketch about an axis (inputs as pd_revolution). A groove that cuts nothing is refused. Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "sketch": {
     "type": "string",
     "description": "The sketch, in the body."
    },
    "axis": {
     "type": [
      "string",
      "integer"
     ]
    },
    "angle": {
     "type": "number"
    },
    "sides": {
     "type": "string"
    },
    "reversed": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_hole": {
  "name": "pd_hole",
  "description": "Holes at the centre of every circle of a sketch (FreeCAD 1.1: at its points too; not construction geometry) on the face they enter, drilled against its normal: diameter mm, or thread \"M5\" (ISO coarse; \"M8x1\" fine) — threaded (default true: tap-drill size, cosmetic unless modelThread) or a clearance hole (threaded: false, fit close|normal|loose); depth mm | \"through\"; drillPoint flat|angled; cut counterbore|countersink|counterdrill with cutDiameter, cutDepth, countersinkAngle (a thread size gives standard ones). Reply adds holes, diameter, thread, cut. Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "sketch": {
     "type": "string",
     "description": "The sketch, in the body."
    },
    "diameter": {
     "type": "number"
    },
    "thread": {
     "type": "string"
    },
    "threaded": {
     "type": "boolean"
    },
    "modelThread": {
     "type": "boolean"
    },
    "fit": {
     "type": "string"
    },
    "depth": {
     "type": [
      "number",
      "string"
     ]
    },
    "drillPoint": {
     "type": "string"
    },
    "cut": {
     "type": "string"
    },
    "cutDiameter": {
     "type": "number"
    },
    "cutDepth": {
     "type": "number"
    },
    "countersinkAngle": {
     "type": "number"
    },
    "reversed": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_fillet": {
  "name": "pd_fillet",
  "description": "Round edges of the body: edges [{ near: [x,y,z] } the edge nearest a point | { face: { at, normal } } every edge of a face | { all: true }, kind: line|circle to filter], or what shape_query answers (\"Edge3\", \"Body.Edge3\", a list, its items) or its filters ({ type: circle, radius: 3 } every such edge; with near, the nearest); radius mm (default 1). References are good until the next change: query again after one. Smooth (tangent) edges are skipped. An inside corner gains material, an outside one loses it: both are right. Reply adds on (the edges). Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "edges": {
     "description": "edges: [{ near: [x,y,z] } the edge nearest a point | { face: { at, normal } } every edge of a face | { all: true }, kind: line|circle], a reference shape_query gives (\"Edge3\", \"Body.Edge3\"; a face's: its edges) or a list of them, or shape_query's filters ({ type: circle, radius, axis, near, … })"
    },
    "radius": {
     "type": "number"
    }
   },
   "required": [
    "edges"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_chamfer": {
  "name": "pd_chamfer",
  "description": "Bevel edges of the body: edges as pd_fillet; size mm (default 1); size2 for two distances or angle deg for distance and angle (one of them). On an inside corner it adds material, on an outside one it removes it: only a chamfer that changes nothing is refused. Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "edges": {
     "description": "edges: [{ near: [x,y,z] } the edge nearest a point | { face: { at, normal } } every edge of a face | { all: true }, kind: line|circle], a reference shape_query gives (\"Edge3\", \"Body.Edge3\"; a face's: its edges) or a list of them, or shape_query's filters ({ type: circle, radius, axis, near, … })"
    },
    "size": {
     "type": "number"
    },
    "size2": {
     "type": "number"
    },
    "angle": {
     "type": "number"
    }
   },
   "required": [
    "edges"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_draft": {
  "name": "pd_draft",
  "description": "Taper faces for moulding: faces [{ at, normal }] (or shape_query's references or filters), angle deg (1.5), neutral plane the faces pivot on (XY default, a datum plane, or a face; they must meet it), pull direction x|y|z (z) or a datum line, reversed. Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "faces": {
     "description": "faces: [{ at, normal }] by where they are, a reference shape_query gives (\"Face8\", \"Body.Face8\") or a list of them, or shape_query's filters ({ type, normal, near, x, y, z, … })"
    },
    "angle": {
     "type": "number"
    },
    "neutral": {
     "description": "XY | XZ | YZ, a datum plane's name, or a face { at, normal }"
    },
    "pull": {
     "type": "string"
    },
    "reversed": {
     "type": "boolean"
    }
   },
   "required": [
    "faces"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_thickness": {
  "name": "pd_thickness",
  "description": "Shell the body: faces [{ at, normal }] (or shape_query's references or filters) to open (removed), thickness mm of the wall (1), inward unless outward: true; join arc|intersection. A wall thicker than an inside fillet fails: shell before filleting. Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "faces": {
     "description": "faces: [{ at, normal }] by where they are, a reference shape_query gives (\"Face8\", \"Body.Face8\") or a list of them, or shape_query's filters ({ type, normal, near, x, y, z, … })"
    },
    "thickness": {
     "type": "number"
    },
    "outward": {
     "type": "boolean"
    },
    "join": {
     "type": "string"
    }
   },
   "required": [
    "faces"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_mirrored": {
  "name": "pd_mirrored",
  "description": "Mirror features (by name) across a plane: XY | XZ | YZ (default), a datum plane, or a face query; features: \"all\" mirrors the whole body (FreeCAD 1.1's TransformMode \"Whole shape\", else every pad and pocket up to the tip). A copy that misses the body makes a second solid (health says so). Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "features": {
     "description": "[feature names], or \"all\": the whole body (every feature up to the tip)",
     "anyOf": [
      {
       "type": "array",
       "items": {
        "type": "string"
       }
      },
      {
       "type": "string",
       "enum": [
        "all"
       ]
      }
     ]
    },
    "plane": {
     "description": "XY | XZ | YZ, a datum plane's name, or a face { at, normal }"
    }
   },
   "required": [
    "features"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_linear_pattern": {
  "name": "pd_linear_pattern",
  "description": "Repeat features in a line: direction x|y|z (x) or a datum line, occurrences (2 or more, the original counted), spacing mm between copies or length mm first to last, reversed; features: \"all\" repeats the whole body. A grid: pd_multitransform. Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "features": {
     "description": "[feature names], or \"all\": the whole body (every feature up to the tip)",
     "anyOf": [
      {
       "type": "array",
       "items": {
        "type": "string"
       }
      },
      {
       "type": "string",
       "enum": [
        "all"
       ]
      }
     ]
    },
    "direction": {
     "type": "string"
    },
    "occurrences": {
     "type": "integer"
    },
    "spacing": {
     "type": "number"
    },
    "length": {
     "type": "number"
    },
    "reversed": {
     "type": "boolean"
    }
   },
   "required": [
    "features"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_polar_pattern": {
  "name": "pd_polar_pattern",
  "description": "Repeat features around an axis: axis x|y|z (the body's; z) or a datum line (pd_datum), occurrences (the original counted), angle deg (360 spreads them evenly round; less is first to last), reversed; features: \"all\" repeats the whole body. Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "features": {
     "description": "[feature names], or \"all\": the whole body (every feature up to the tip)",
     "anyOf": [
      {
       "type": "array",
       "items": {
        "type": "string"
       }
      },
      {
       "type": "string",
       "enum": [
        "all"
       ]
      }
     ]
    },
    "axis": {
     "type": "string"
    },
    "occurrences": {
     "type": "integer"
    },
    "angle": {
     "type": "number"
    },
    "reversed": {
     "type": "boolean"
    }
   },
   "required": [
    "features"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_loft": {
  "name": "pd_loft",
  "description": "Loft through closed sketches: profile (the first), sections [the rest, in order, each on its own plane], ruled, closed; subtractive: true cuts it. Sketches should have the same edge count and matching start corners, or it twists. Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "profile": {
     "type": "string",
     "description": "The sketch, in the body."
    },
    "sections": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "ruled": {
     "type": "boolean"
    },
    "closed": {
     "type": "boolean"
    },
    "subtractive": {
     "type": "boolean"
    }
   },
   "required": [
    "profile",
    "sections"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_pipe": {
  "name": "pd_pipe",
  "description": "Sweep a closed profile sketch along a path sketch (all its edges, joined end to end); subtractive: true cuts it. The profile should sit across the path's start. Orientation, corners: feature_edit { Mode: \"Frenet\", Transition: \"Round corner\" }. Reply: feature, volume mm³, volumeChange, faces, solids, box, health. A failure is refused with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "profile": {
     "type": "string",
     "description": "The sketch, in the body."
    },
    "path": {
     "type": "string",
     "description": "The sketch, in the body."
    },
    "subtractive": {
     "type": "boolean"
    }
   },
   "required": [
    "profile",
    "path"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_datum_plane": {
  "name": "pd_datum_plane",
  "description": "A datum plane in the body, on XY | XZ | YZ | a flat face query, offset mm along its normal, rotate { axis [x,y,z] (its own), angle deg }, name: for sketches off the body's planes (sketch_new { plane: its name }). Reply: plane, origin, normal.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "on": {
     "description": "XY | XZ | YZ, a datum plane's name, or a face { at, normal }"
    },
    "offset": {
     "type": "number"
    },
    "rotate": {
     "type": "object"
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
  "group": "feature"
 },
 "feature_list": {
  "name": "feature_list",
  "description": "The body's features in order: type, key values (lengths mm, angles deg, FreeCAD's type strings), what each is bound to, valid or not with FreeCAD's error, the tip, a MultiTransform's steps (stepOf); sketches with their dof. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "feature"
 },
 "feature_edit": {
  "name": "feature_edit",
  "description": "Change a feature's properties by FreeCAD's names: set { Length: 20, Type: \"ThroughAll\", Reversed: true, Radius: 2, Occurrences: 4, Refine: true, … } (feature_list shows them; a wrong enumeration value lists the right ones); recomputes. Links (sketch, edges, axis) are not edited: remove and remake. A change that breaks it or a later feature is refused and undone; fillets whose edges it renumbered are found again (refsFound). A property bound to a parameter is changed with param_set.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "feature": {
     "type": "string"
    },
    "set": {
     "type": "object"
    }
   },
   "required": [
    "feature",
    "set"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "feature_remove": {
  "name": "feature_remove",
  "description": "Remove a feature (and its sketch unless keepSketch, when nothing else uses it; a MultiTransform's steps too). One that others use (a sketch on its face, a fillet of its edges, a pattern of it) is refused unless force. Later features that break are refused and nothing kept. Reply: removed, tip.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "feature": {
     "type": "string"
    },
    "keepSketch": {
     "type": "boolean"
    },
    "force": {
     "type": "boolean"
    }
   },
   "required": [
    "feature"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "feature_suppress": {
  "name": "feature_suppress",
  "description": "Suppress a feature (suppressed: false brings it back): the body is computed as if it were not there, and it stays in the history. Refused when a later feature needs its faces or edges.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "feature": {
     "type": "string"
    },
    "suppressed": {
     "type": "boolean"
    }
   },
   "required": [
    "feature"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_move_feature": {
  "name": "pd_move_feature",
  "description": "Move a PartDesign feature (with its sketch, re-attached to the same origin plane) to another body: feature, to. It goes after that body's tip. Refused, with nothing moved, when it or what is left behind then fails (a pocket needs a solid to cut). Reply: moved, from, to, tip.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "feature": {
     "type": "string"
    },
    "to": {
     "type": "string"
    }
   },
   "required": [
    "feature",
    "to"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 },
 "pd_reorder": {
  "name": "pd_reorder",
  "description": "Move a feature or sketch in its body's history: after or before another one of the same body. Refused, with nothing moved, when something would then use what comes after it. Put after the tip, it becomes the tip. Reply: order, tip, afterTip (solid features past the tip, left out of the shape), volume.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "feature": {
     "type": "string"
    },
    "after": {
     "type": "string"
    },
    "before": {
     "type": "string"
    }
   },
   "required": [
    "feature"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 },
 "pd_tip": {
  "name": "pd_tip",
  "description": "Read (no feature) or set a body's tip: the solid feature its shape stops at, and after which new features go in. A sketch or datum given: the solid feature before it. Features past the tip are kept but left out (afterTip) — set it back to the last one when done. Reply: tip, tipWas, afterTip, volume.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "feature": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 },
 "pd_shaft": {
  "name": "pd_shaft",
  "description": "A stepped shaft (the shaft wizard's geometry) as one plain Part solid, not in a PartDesign body: segments [{ length, diameter, diameterEnd (a taper) }] mm, from one end along axis x (or y, z); at, name. Reply: shaft, length, volume. part_fillet its shoulders; pd_clone brings it into a body.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "segments": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "axis": {
     "type": "string",
     "enum": [
      "x",
      "y",
      "z"
     ]
    },
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "segments"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 },
 "pd_body_new": {
  "name": "pd_body_new",
  "description": "Make an empty PartDesign body: the container a parametric part's features go in, with its own XY/XZ/YZ planes and x/y/z axes. Answers body: its label (name, made unique) to pass on. Next: sketch_new on one of its planes.",
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
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_new": {
  "name": "sketch_new",
  "description": "A new sketch in a body, on plane XY | XZ | YZ | a datum plane's name | \"Pad.Face3\", or on a face of the solid found by face { at: a point on it, normal: its outward normal } — never by face index, which changes after edits. One of plane or face. offset mm along the normal; flip reverses it. A face sketch is lined up with the world: its x along the world axis that lies most in the face. Answers sketch (its label) and frame: where sketch x/y and its origin lie in the world.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body's name; may be left out when there is one."
    },
    "plane": {
     "type": "string"
    },
    "face": {
     "type": "object",
     "description": "{ at: [x,y,z] a point on the face, normal: [x,y,z] its outward normal }",
     "properties": {
      "at": {
       "type": "array",
       "items": {
        "type": "number"
       }
      },
      "normal": {
       "type": "array",
       "items": {
        "type": "number"
       }
      },
      "tol": {
       "type": "number"
      }
     },
     "required": [
      "at"
     ],
     "additionalProperties": false
    },
    "offset": {
     "type": "number"
    },
    "flip": {
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
  "group": "sketch"
 },
 "sketch_add": {
  "name": "sketch_add",
  "description": "Add geometry to a sketch, in its own x/y (mm; angles deg, counter-clockwise from +x): items [{ kind, …, construction, dims, name }]. kinds: line {from, to}; polyline {points, closed}; arc {center, radius, start, end} (always ccw from start to end); arc3 {points: start, through, end}; circle {center, radius|diameter}; circle3 {points: three on it}; ellipse {center, major, minor (full sizes), rotation}; parabola {vertex, focal, rotation, from, to}; hyperbola {center, major, minor (semi-axes), rotation, from, to}; bspline {points it passes through, closed — or interpolate: false, points its poles, degree}; rectangle {center|corner, size [w,h]}; rounded_rectangle {…, radius}; polygon {center, radius (to corners), sides, rotation}; slot {from, to (end centres), radius}; arc_slot {center, radius (its middle), width, start, end}; point {at}. A shape comes with its own coincident/horizontal/vertical/tangent/equal constraints; separate items are not joined to each other (sketch_constrain coincident or tangent does that). dims: true adds its sizes as constraints (named <name>_width, _height, _d, _r, _length when named — what param_bind binds). Answers added [{ ids: geometry ids from 0 in the order made (a polygon's last is its construction circle), constraints: [first, last] ids, dims }] and state (dof, closedWires, openVertices, readyForFeature). Vertices: 1 start, 2 end, 3 centre.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "items": {
     "type": "array",
     "items": {
      "type": "object"
     }
    }
   },
   "required": [
    "items"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_offset": {
  "name": "sketch_offset",
  "description": "Offset a sketch's profile by distance mm (out; negative in): its geometry ids (all but construction when left out), joined end to end; join arc (round corners, the default), tangent or intersection (sharp). Answers added: the new geometry's ids. The offset is plain geometry with no constraints: it does not follow later edits unless constrained (sketch_constrain; sketch_validate fix joins its pieces).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "distance": {
     "type": "number"
    },
    "geometry": {
     "type": "array",
     "items": {
      "type": "integer"
     }
    },
    "join": {
     "type": "string",
     "enum": [
      "arc",
      "tangent",
      "intersection"
     ]
    },
    "construction": {
     "type": "boolean"
    }
   },
   "required": [
    "distance"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_external": {
  "name": "sketch_external",
  "description": "Bring edges of the body's solid (its tip) into a sketch as outside geometry to constrain to: edges [\"Edge7\" or a query { type: circle|line, radius, axis, near, inside } as shape_query takes — safer: edge numbers change with edits]. Answers ids (negative, -3 down, in order) for sketch_constrain's refs; a constraint to them follows the part. Refused when the tip is built from this sketch. From a datum, binder or other sketch: sketch_project.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "edges": {
     "type": "array",
     "items": {}
    }
   },
   "required": [
    "edges"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_constrain": {
  "name": "sketch_constrain",
  "description": "Constrain a sketch: constraints [{ type, refs, value, name }]. A ref is FreeCAD's: a geometry id g, a point p = [g, vertex] (1 start, 2 end, 3 centre) or \"origin\"; -1 the horizontal axis, -2 the vertical, -3 down outside edges. types and their refs: coincident [p, p]; point_on_object [p, g]; horizontal | vertical [g] or [p, p]; parallel | perpendicular | equal [g, g]; tangent [g, g] or end points [p, p]; symmetric [p, p, g] (about a line) or [p, p, p]; distance [g] (length), [p, p] or [p, g]; distance_x | distance_y [g], [p] (from the origin) or [p, p] (second minus first); radius | diameter [g], all mm; angle [g] (from +x) or [g, g] (first to second, ccw), deg; fix [p] (a point held where it is) or [g] (blocked: add it last). name it to bind it to a parameter later. All or nothing: one that conflicts or is redundant is refused, naming what clashes, and nothing added. Answers added (constraint ids from 0) and state.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "constraints": {
     "type": "array",
     "items": {
      "type": "object"
     }
    }
   },
   "required": [
    "constraints"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_state": {
  "name": "sketch_state",
  "description": "The solver's reading of a sketch — check it before a feature: dof (0 is fully constrained), conflicting / redundant / malformed constraint ids, closed wires and open vertices, readyForFeature with todo when not; its frame in the world; detail (default true) lists geometry and constraints with ids, values (mm; deg for angles) and refs [g, vertex]. Ids count from 0 in every sketch tool. A pad on a sketch with dof > 0 works but moves when edited.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "detail": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "sketch"
 },
 "sketch_edit": {
  "name": "sketch_edit",
  "description": "Edit a sketch; several keys may go in one call, done in this order: move { geo, vertex (0 the whole curve, 1/2/3), to [x,y] } (drags it as far as its constraints let it), set [{ constraint: id|name, value mm|deg }], construction { geo, on }, rename { constraint, name }, deleteConstraints [id|name], delete [geometry ids — their constraints go too], fillet { at: [g, v] a corner, or geos [g1, g2] near [[x,y],[x,y]]; radius; chamfer: true cuts it straight } (the curves trimmed to it), trim { geo, at [x,y] } (cuts off the piece there, between crossings), split { geo, at }, mirror { geos, about: \"x\" | \"y\" | \"origin\" | a line id } (free mirrored copies: no symmetric constraints are added), group [geos] (held as one, FreeCAD 1.2), text { text, at, height, font, construction } (letters as geometry), exposeInternal [geos] (an ellipse's axes or a B-spline's poles back as construction geometry), removeAxesAlignment [geos]. delete, fillet, trim and split renumber geometry: read sketch_state before using ids again. Answers done, state, geometryCount, and bodyAfter when features are built on it; an edit that breaks one is refused with FreeCAD's error and nothing kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "move": {
     "type": "object"
    },
    "set": {},
    "construction": {
     "type": "object"
    },
    "rename": {
     "type": "object"
    },
    "deleteConstraints": {
     "type": "array",
     "items": {}
    },
    "delete": {
     "type": "array",
     "items": {
      "type": "integer"
     }
    },
    "fillet": {
     "type": "object"
    },
    "trim": {
     "type": "object"
    },
    "split": {
     "type": "object"
    },
    "mirror": {
     "type": "object"
    },
    "group": {
     "type": "array",
     "items": {
      "type": "integer"
     }
    },
    "text": {
     "type": "object"
    },
    "exposeInternal": {
     "type": "array",
     "items": {
      "type": "integer"
     }
    },
    "removeAxesAlignment": {
     "type": "array",
     "items": {
      "type": "integer"
     }
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 }
}
''')
