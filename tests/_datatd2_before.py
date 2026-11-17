# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of each converted tool at the base commit (tests/test_datatd2_data.py
# checks it against git where the commit is there): name, description, schema, flags, group.
import json

BEFORE = json.loads(r"""
{
 "td_list": {
  "name": "td_list",
  "description": "A page's views (label, scale, size, edge count; a group's items), dimensions (name, refs, measured, text, tolerance), GD&T, other objects and title block. A document just opened holds each view's settings but not its lines (FreeCAD works them out at the view's first recompute): views without lines are computed here first and waited for (up to 20 s; computed says how many and how long), and the dimensions on them after. A view still without lines is marked notReady with no edge count, and a dimension on it has notReady in place of measured and text — never 0 as if measured; notReady at the top says which and what to do (recompute, then td_list again). Changes nothing in the model.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "page": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "techdraw"
 },
 "td_export": {
  "name": "td_export",
  "description": "Write a page out: formats [svg, pdf, dxf], name. DXF is TechDraw's own. SVG and PDF are drawn here from the page's objects (TechDraw's own PDF and SVG export needs the window): views, dimensions, symbols, notes, tables, centre marks, hatching and the title block's fields, without the template's artwork. Files go to the session's folder; notes says what was skipped.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "page": {
     "type": "string"
    },
    "formats": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "name": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "techdraw"
 },
 "td_cosmetic": {
  "name": "td_cosmetic",
  "description": "Cosmetic geometry on a view (FreeCAD's own cosmetic edges from 1.1, so in the window too; always in td_export): items [{ kind line (from, to: points on the part) | circle (center on the part, radius mm) | centerline (edges: a shaft's or hole's two side lines; extend mm) | thread (edges: the two outline lines of a side view, or circle: the end view's round edge; internal: true for a tapped hole; pitch, ISO coarse by default; length mm) , style thin | visible | hidden | center }]; clear: true drops the earlier ones. td_lines takes them by order, from 0.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "items": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "clear": {
     "type": "boolean"
    }
   },
   "required": [
    "view"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_view_more": {
  "name": "td_view_more",
  "description": "More views on a page: kind broken { view, breaks, gap } | draft { object (a Draft object) } | clip { width, height, frame } | clip_add / clip_remove { clip, view } | image { path, width, height } | symbol { path (an SVG), scale } | share { view } (the view also on this page, with its dimensions) | lock { view, locked } | stack { view, to top|bottom|up|down } | move { view, page } (to another page; a group's item takes its group), at [x, y].",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "broken",
      "draft",
      "clip",
      "clip_add",
      "clip_remove",
      "image",
      "symbol",
      "share",
      "lock",
      "stack",
      "move"
     ]
    },
    "locked": {
     "type": "boolean"
    },
    "to": {
     "type": "string",
     "enum": [
      "top",
      "bottom",
      "up",
      "down"
     ]
    },
    "page": {
     "type": "string"
    },
    "view": {
     "type": "string"
    },
    "object": {
     "type": "string"
    },
    "breaks": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "gap": {
     "type": "number"
    },
    "clip": {
     "type": "string"
    },
    "width": {
     "type": "number"
    },
    "height": {
     "type": "number"
    },
    "frame": {
     "type": "boolean"
    },
    "path": {
     "type": "string"
    },
    "scale": {
     "type": "number"
    },
    "direction": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "kind"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_lines": {
  "name": "td_lines",
  "description": "A view's lines: action align_h / align_v { refs two points or an edge } (the view turned so they line up) | style { refs edges, style solid|dashed|dotted|dashdot|dashdotdot|none, weight mm, color } | extend / shorten { items (td_cosmetic's lines by order from 0; all when left out), by mm, centerlines } | erase { items, tags } (cosmetic lines gone; all td_cosmetic's when items is left out).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "action": {
     "type": "string",
     "enum": [
      "align_h",
      "align_v",
      "style",
      "extend",
      "shorten",
      "erase"
     ]
    },
    "refs": {
     "type": "array",
     "items": {}
    },
    "style": {
     "type": "string"
    },
    "weight": {
     "type": "number"
    },
    "color": {},
    "items": {
     "type": "array",
     "items": {
      "type": "integer"
     }
    },
    "by": {
     "type": "number"
    },
    "centerlines": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "tags": {
     "type": "array",
     "items": {
      "type": "string"
     }
    }
   },
   "required": [
    "view",
    "action"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "cam_path": {
  "name": "cam_path",
  "description": "Other CAM path objects (job puts one in a job). kind: area { sources, workplane \"Body.Face3\", props } | from_shape { sources } (a path along wires, no tool controller) | edges { sources, job } (with one: not on 1.1 without its window) | compound { ops } | array { ops, props: Type, Copies, Offset … } | stop { mandatory } (M0, else M1) | fixture { fixture: G54 … }. Answers object, commands, first (G-code lines).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "area",
      "from_shape",
      "edges",
      "compound",
      "array",
      "stop",
      "fixture"
     ]
    },
    "job": {
     "type": "string"
    },
    "sources": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "workplane": {
     "type": "string"
    },
    "ops": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "props": {
     "type": "object"
    },
    "mandatory": {
     "type": "boolean"
    },
    "fixture": {
     "type": "string"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "kind"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "cam_more"
 },
 "cam_property_bag": {
  "name": "cam_property_bag",
  "description": "A CAM property bag of named values for operations' expressions: properties [{ name (no spaces), type Float | Length | Angle | Integer | String | Bool, value, group }]. Answers bag, name (expressions call it <name>.<property>).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    },
    "properties": {
     "type": "array",
     "items": {
      "type": "object"
     }
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "cam_more"
 },
 "cam_template_export": {
  "name": "cam_template_export",
  "description": "Write a CAM job as a template (job_<name>.json in the output folder unless path): tool controllers, stock, setup sheet, post settings; description. For FreeCAD's New Job dialog (cam_job does not read templates). Changes nothing in the document.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string"
    },
    "path": {
     "type": "string"
    },
    "description": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "cam_more"
 },
 "draft_fix": {
  "name": "draft_fix",
  "description": "Draft fixes: action flip_dimension { dimension } (text to the other side) | heal { objects } (old Draft objects rebuilt as new copies; left out: only those that need it, named ones regardless). Reply: normal; or healed, rebuilt, removed, now.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "action": {
     "type": "string",
     "enum": [
      "flip_dimension",
      "heal"
     ]
    },
    "dimension": {
     "type": "string"
    },
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    }
   },
   "required": [
    "action"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "cam_more"
 },
 "asm_rigid_group": {
  "name": "asm_rigid_group",
  "description": "Hold two or more parts of an assembly fixed to each other as one group (Assembly's rigid group joint, FreeCAD 1.2 and newer): parts by label, name. On FreeCAD 1.1 it answers unavailable — asm_joint kind fixed between each pair does the same there. Reply: joint, parts.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string"
    },
    "parts": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "parts"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "cam_more"
 },
 "asm_new_part": {
  "name": "asm_new_part",
  "description": "A new empty part to build in place (Assembly's New Part): an App::Part holding an empty PartDesign body, put in the assembly through an App::Link; name; at [x, y, z], axis and angle degrees place the link. Reply: part, body (sketch_new { body } and pd_pad build in it), inAssembly (the link's label). asm_check checks it where the link stands; asm_joint and asm_ground take bodies put in with asm_new or asm_add, not this link — to joint a part, build the body first and asm_add it.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string"
    },
    "name": {
     "type": "string"
    },
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "axis": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "angle": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "cam_more"
 },
 "scad_status": {
  "name": "scad_status",
  "description": "Whether the OpenSCAD program is on this computer (openscad: its path or null; version), and whether FreeCAD's CSG parser (ply) loads. Without OpenSCAD: .csg import (not a file's own hull, minkowski or text), CSG export and scad_op's hull work; .scad files, scad_code and minkowski do not. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "openscad"
 },
 "scad_import": {
  "name": "scad_import",
  "description": "Read an OpenSCAD file into the document (path; relative: the session's folder): .csg needs only FreeCAD, unless it uses hull, minkowski or text (those, and any .scad, go through the OpenSCAD program: refused unavailable when it is not installed — scad_status). Primitives, booleans, transforms and extrusions come in as FreeCAD's own parametric objects (Part::Box, Cut, Fuse …; one object per CSG node, so a small file makes many), hull and minkowski as meshes turned to shapes. Reply: objects (how many), top (the results nothing else uses — the bodies to work with), made [{ object, type, solids, volume }], health.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    }
   },
   "required": [
    "path"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "openscad"
 },
 "scad_code": {
  "name": "scad_code",
  "description": "Run OpenSCAD code into the document: code (e.g. \"difference() { cube(20, center=true); sphere(13); }\") goes through the OpenSCAD program to CSG and comes in as scad_import does. Needs OpenSCAD installed (scad_status); a syntax error is refused with OpenSCAD's message. name: the label of the result when there is one top object. Reply: top, objects, made.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "code": {
     "type": "string"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "code"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "openscad"
 },
 "scad_export": {
  "name": "scad_export",
  "description": "Write objects (the one body when left out) as OpenSCAD CSG (path: .csg or .scad, .csg added; relative: the session's folder): Part primitives, booleans, extrusions and placements as OpenSCAD's own, anything else (PartDesign bodies, fillets, imports) as polyhedra of triangles — the note counts them. Reply: path, bytes, lines. The document is not changed.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
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
  "group": "openscad"
 },
 "scad_op": {
  "name": "scad_op",
  "description": "OpenSCAD's hull (the convex shape stretched round the objects, like shrink-wrap) or minkowski (the first shape swept round by the second: rounded edges all over; slow, minutes on curved shapes) of objects [names]. Hull works without OpenSCAD (computed here from the shapes' points, faceted on curves: made says which); minkowski needs OpenSCAD. The inputs are kept. name: the result's label. Reply: object, made, volume, faces, health.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "op": {
     "type": "string",
     "enum": [
      "hull",
      "minkowski"
     ]
    },
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "objects"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "openscad"
 }
}
""")
