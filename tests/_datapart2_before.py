# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the Part tools of families/model_more.py and
# part_more.py now kept as data, at the commit they were converted from
# (tests/test_datapart2_data.py's BASE): name, description, inputSchema,
# changes, reads, group. Written by
#   python3 tests/test_datapart2_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "part_wire": {
  "name": "part_wire",
  "description": "A wire, curve or flat face as FreeCAD's own parametric object: kind line (from, to) | circle (radius) | arc (radius, start, end: 0–360° counter-clockwise) | ellipse (major, minor: full sizes) | polygon (regular: sides, radius to corners) | polyline (points, the corners in place, closed) | helix (pitch, height, radius, taper, leftHanded) | spiral (growth per turn, turns, radius) | plane (length, width) | bspline (points it passes through; closed: a smooth periodic loop; fit.maxDistance is how far it lies from them). at and normal place it: its centre (a plane's corner, a helix's base) at at, its z along normal. polyline and bspline take points_file (a .json list of [x,y,z] or a .csv of x,y,z rows in the session's folder; key picks one list) instead of points, so long lists are not sent in the call. Profiles and paths for extrude, sweep, loft; a plane cuts in part_split.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string"
    },
    "from": {
     "type": "array",
     "items": {}
    },
    "to": {
     "type": "array",
     "items": {}
    },
    "radius": {
     "type": "number"
    },
    "start": {
     "type": "number"
    },
    "end": {
     "type": "number"
    },
    "major": {
     "type": "number"
    },
    "minor": {
     "type": "number"
    },
    "sides": {
     "type": "integer"
    },
    "pitch": {
     "type": "number"
    },
    "height": {
     "type": "number"
    },
    "taper": {
     "type": "number"
    },
    "leftHanded": {
     "type": "boolean"
    },
    "growth": {
     "type": "number"
    },
    "turns": {
     "type": "number"
    },
    "length": {
     "type": "number"
    },
    "width": {
     "type": "number"
    },
    "points": {
     "type": "array",
     "items": {}
    },
    "points_file": {
     "type": "string"
    },
    "key": {},
    "closed": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "normal": {
     "type": "array",
     "items": {}
    }
   },
   "required": [
    "kind"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_split": {
  "name": "part_split",
  "description": "Split bodies (Part's BOPTools, parametric; inputs hidden, not removed): mode slice (bodies [one], tools [objects by name that cut right through it: a part_wire plane, a face copied out by part_extract, bodies]) | fragments (bodies: every piece where they overlap, kept apart) | xor (bodies: what is in an odd number of them); explode: true makes each piece a body. Reply: object, pieces, solids [{ volume, center }]; note when a slice cut nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mode": {
     "type": "string",
     "enum": [
      "slice",
      "fragments",
      "xor"
     ]
    },
    "bodies": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "tools": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "split": {
     "type": "boolean"
    },
    "explode": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "bodies"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_compound": {
  "name": "part_compound",
  "description": "Group bodies into one compound (kept apart, not fused; it follows its parts): bodies [names] — or explode: the name of a body of several solids, each copied out as a body (the original hidden).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "bodies": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "explode": {
     "type": "string"
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
  "group": "model"
 },
 "part_refine": {
  "name": "part_refine",
  "description": "Merge a body's coplanar and co-cylindrical faces left by booleans (refine); a PartDesign Body gets its tip's Refine turned on and stays parametric. fix: true first repairs it (ShapeFix at tolerance mm, 0.001) and makes a closed shell a solid. Renumbers faces. Reply: faces { before, after }, done, sound.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "fix": {
     "type": "boolean"
    },
    "tolerance": {
     "type": "number"
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
  "group": "model"
 },
 "part_attach": {
  "name": "part_attach",
  "description": "Attach a primitive, wire or datum (not a plain modelling result) so it follows its support: to \"Body.Face6\", an edge, a vertex or a whole object; mode, a FreeCAD MapMode, by default FlatFace (flat face) | NormalToEdge (edge) | Translate (vertex) | ObjectXY (object); also Concentric, FrenetNB … (modes needing two references are not reachable). offset [x, y, z] and rotate degrees in the support's frame. Trap: a later boolean on the support renumbers its faces.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "to": {
     "type": "string"
    },
    "mode": {
     "type": "string"
    },
    "offset": {
     "type": "array",
     "items": {}
    },
    "rotate": {
     "type": "number"
    }
   },
   "required": [
    "body",
    "to"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_face": {
  "name": "part_face",
  "description": "A flat face from closed wires or sketches in one plane: from [object names], the outline and any holes inside it (found by nesting).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "from": {
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
    "from"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_ruled": {
  "name": "part_ruled",
  "description": "A ruled surface (parametric) of straight lines between two curves: a and b each an edge or wire by name, or one edge of a body as \"Box.Edge3\". reversed: true if it twists. A surface, not a solid (surface_thicken).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "a": {
     "type": "string"
    },
    "b": {
     "type": "string"
    },
    "reversed": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "a",
    "b"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_project": {
  "name": "part_project",
  "description": "Project a wire's, sketch's or body's edges onto one face: shape (a name), onto \"Body.Face6\", direction [x, y, z] from the shape towards the face (left out: along the face's normals). Lettering wrapped onto a curved face, an outline traced onto a surface. Reply: edges, length, missed (wires that did not land).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "shape": {
     "type": "string"
    },
    "onto": {
     "type": "string"
    },
    "direction": {
     "type": "array",
     "items": {}
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "shape",
    "onto"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_slices": {
  "name": "part_slices",
  "description": "Cross-sections of a body: normal [x, y, z] (default z), count (1–500, evenly through it) or at [distances along the normal from the origin]; each slice's wires, length and material area (inner loops are holes), kept as one compound; range is the body's reach along the normal. Layer outlines, laser-cut stacks.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "normal": {
     "type": "array",
     "items": {}
    },
    "count": {
     "type": "integer"
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
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_from_mesh": {
  "name": "part_from_mesh",
  "description": "A mesh made a solid, every triangle a face: mesh (an object) or file (STL, OBJ …); tolerance sews it, refine (default) merges flat triangles. For a closed, modest mesh: over maxFacets (60000) refused (meshobj_decimate first); thousands of faces already make it and every later boolean slow, the window frozen meanwhile. Of several pieces only the largest becomes the solid (note says so).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string"
    },
    "file": {
     "type": "string"
    },
    "tolerance": {
     "type": "number"
    },
    "refine": {
     "type": "boolean"
    },
    "maxFacets": {
     "type": "integer"
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
  "group": "model"
 },
 "part_section": {
  "name": "part_section",
  "description": "Section curves where a body meets another body (with: a parametric Part::Section; parametric: false for a plain shape) or a plane { normal, at }; face: true also fills the closed loops into a face. Refused when they do not meet. Reply: section, edges, length_mm, closedLoops, area_mm2. Cut-lines, outlines at a height.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "with": {
     "type": "string"
    },
    "plane": {
     "type": "object"
    },
    "face": {
     "type": "boolean"
    },
    "approximate": {
     "type": "boolean"
    },
    "parametric": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "body"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_offset2d": {
  "name": "part_offset2d",
  "description": "Offset a flat wire, sketch or face in its plane (Part::Offset2D; a closed wire goes through its face, as a plain shape): distance mm (+ out, − in), join arc | tangent | intersection, fill: true for the band between the two, intersection: true to offset several wires as one. Refused when the loop vanishes or is not flat. Kerf and clearance outlines, gasket bands.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "shape": {
     "type": "string"
    },
    "distance": {
     "type": "number"
    },
    "join": {
     "type": "string",
     "enum": [
      "arc",
      "tangent",
      "intersection"
     ]
    },
    "fill": {
     "type": "boolean"
    },
    "intersection": {
     "type": "boolean"
    },
    "parametric": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "shape",
    "distance"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_extract": {
  "name": "part_extract",
  "description": "Copy elements out as a plain body of their own (Part's element copy and shape builder): refs [\"Box.Face3\", \"Box.Edge2\", whole objects], numbered from 1; build copy (as they are) | wire (edges joined) | face (closed edge loops filled) | shell (faces sewn at tolerance mm, 0.01) | solid (a closed shell made a solid; refused with a gap). Reply: shape, counts, valid.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "refs": {
     "type": "array",
     "items": {}
    },
    "build": {
     "type": "string",
     "enum": [
      "copy",
      "wire",
      "face",
      "shell",
      "solid"
     ]
    },
    "tolerance": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "refs"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_defeature": {
  "name": "part_defeature",
  "description": "Take features off a solid by their faces (Part defeaturing): faces [\"Face12\", …] numbered from 1 — every face of a hole, boss or fillet together; the faces around grow over the gap. Renumbers faces; refused when OCC cannot close it. For simplifying imported bodies before FEA or CAM.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "faces": {
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
    "faces"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_fix": {
  "name": "part_fix",
  "description": "Repair a shape: op reverse (flip an inside-out solid) | solid (closed shells or faces made solids) | sew (faces joined within tolerance mm, 0.01) | fix (ShapeFix at tolerance, 0.001). Reply: valid, closed, solids, notes.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "op": {
     "type": "string",
     "enum": [
      "reverse",
      "solid",
      "sew",
      "fix"
     ]
    },
    "tolerance": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "body",
    "op"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_datum": {
  "name": "part_datum",
  "description": "A datum: kind point | line | plane | csys, at [x,y,z], normal (plane, line) or axis + angle; or attached by one reference (to \"Box.Face6\", an edge, a vertex), the placement then its offset. mode: a FreeCAD MapMode, by default by what to is (FlatFace, NormalToEdge, Translate; a line along a straight edge or a circle's axis; a point at a vertex or centre); a line on a face needs mode. Refused when it cannot attach.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "point",
      "line",
      "plane",
      "csys"
     ]
    },
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "normal": {},
    "axis": {},
    "angle": {
     "type": "number"
    },
    "to": {
     "type": "string"
    },
    "mode": {
     "type": "string"
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
  "group": "model"
 }
}
''')
