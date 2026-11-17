# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the Part tools now kept as data, at the commit they
# were converted from (tests/test_datapart_data.py's BASE): name,
# description, inputSchema, changes, reads, group. Written by
#   python3 tests/test_datapart_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "part_primitive": {
  "name": "part_primitive",
  "description": "Add a FreeCAD Part primitive as a body (mm, degrees). kind: box { size [x,y,z] }: a corner at at. cylinder { radius, height }, cone { radius (base), radius2 (top); either may be 0 }, prism { sides, radius (centre to corner), height }, tube { radius, radius2 (bore), height }: base centred at at, axis +z or along direction. sphere { radius }, torus { radius (ring), radius2 (tube) }: centred at at. wedge { wedge: { xmin, ymin, zmin, x2min, z2min, xmax, ymax, zmax, x2max, z2max } }: front face at ymin, rear face (x2, z2) at ymax. rotate { axis, angle } turns it about at. Parametric until a boolean, fillet or other part_ step bakes it to a plain shape: till then object_set changes Length / Width / Height (box x, y, z), Radius, Radius1 / Radius2 (cone base / top; torus ring / tube), Polygon / Circumradius, Xmin … Z2max, OuterRadius / InnerRadius. Reply: body, volume, area, faces, solids, box, sound, type, placement.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "box",
      "cylinder",
      "sphere",
      "cone",
      "torus",
      "wedge",
      "prism",
      "tube"
     ]
    },
    "size": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "radius": {
     "type": "number"
    },
    "radius2": {
     "type": "number"
    },
    "height": {
     "type": "number"
    },
    "sides": {
     "type": "integer"
    },
    "wedge": {
     "type": "object"
    },
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "rotate": {
     "type": "object",
     "description": "{ axis: [x,y,z], angle: degrees } about at"
    },
    "direction": {
     "type": "array",
     "items": {
      "type": "number"
     },
     "description": "[x,y,z]: where a cylinder's, cone's, prism's or tube's axis points from at (+z when left out); rotate turns it further."
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
  "group": "model"
 },
 "part_boolean": {
  "name": "part_boolean",
  "description": "fuse, cut or common base with tools (solid bodies by name; base is the one kept, and must be named when more than one body is shown). common with several tools keeps what base shares with any of them. Done on the shapes, not as a Part::Cut feature: the result keeps base's label (name: a new one) as a plain shape with coplanar faces merged; the tools are removed (keep: true hides them; a hidden body is still a body to other tools). A PartDesign Body base gives a new Body on the result and the old one is hidden. Trap: faces and edges are renumbered; shape_query again. Refused, with the tools kept, when nothing would change (apart, or inside for fuse), common has no overlap, a tool is not a sound solid (invalid, open, inside out), or OCC drops a tool or makes an invalid result. Heavy with many faces (meshes made solids): past an estimated minute the first call answers with the time and runs nothing, the same call again runs it, and the window is frozen meanwhile. Reply: body, volume, box, sound (problems when not), op, volumeChange, removed or kept, hidden + hiddenNote (object_delete of the result shows the inputs again).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "op": {
     "type": "string",
     "enum": [
      "fuse",
      "cut",
      "common"
     ]
    },
    "base": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "tools": {
     "description": "A body or a list of them."
    },
    "keep": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "op",
    "tools"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_transform": {
  "name": "part_transform",
  "description": "Move or copy a solid body. move { by [dx,dy,dz] } and rotate { axis, angle degrees, about [x,y,z] (default: its box centre) } change its Placement in place (a primitive stays parametric); copy: true makes a new body instead. mirror { normal, about (box centre) } and scale { factor or [fx,fy,fz], about (origin) } make a new body and keep the original (mirror fuse: true joins both into the original). linear { count, step [dx,dy,dz] } and polar { count, axis, about (origin), angle (360 shares out evenly, less runs end to end) } array the body into itself, count with the original, fused (fuse: false keeps the copies apart in one body, quicker for many). Trap: all but move and rotate bake a plain shape and renumber faces and edges; shape_query again. Reply: body, volume, box, sound, op, and placement, from or count.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "op": {
     "type": "string",
     "enum": [
      "move",
      "rotate",
      "mirror",
      "scale",
      "linear",
      "polar"
     ]
    },
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "by": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "axis": {},
    "angle": {
     "type": "number"
    },
    "about": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "normal": {},
    "factor": {},
    "count": {
     "type": "integer"
    },
    "step": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "copy": {
     "type": "boolean"
    },
    "fuse": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "op"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_fillet": {
  "name": "part_fillet",
  "description": "Round edges of a solid body by radius mm. edges: [\"Edge3\", \"Face6\" (all its edges) …], numbered from 1 as shape_query lists them, or \"all\"; and/or query { type, axis, radius, near, inside, of: \"Face6\" … } as shape_query takes for edges. Done on the shape, not as a Part::Fillet feature: the body becomes a plain shape. Traps: every modelling step renumbers edges, so query again rather than reuse numbers; fillet last. Refused, nothing changed, when OCC fails or leaves a broken shape (a radius larger than a face beside the edge allows). Reply: body, volume, box, sound, edges (how many), volumeChange.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "radius": {
     "type": "number"
    },
    "edges": {},
    "query": {
     "type": "object"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "radius"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_chamfer": {
  "name": "part_chamfer",
  "description": "Bevel edges of a solid body by size mm (the same on both faces). Edges are picked, numbered and refused as part_fillet's (edges refs from 1, \"all\", or query); reply as part_fillet.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "size": {
     "type": "number"
    },
    "edges": {},
    "query": {
     "type": "object"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "size"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_offset": {
  "name": "part_offset",
  "description": "Grow (+) or shrink (-) a solid by distance mm all round (OCC's 3D offset, skin mode); join arc (rounded corners, default) or intersection (sharp). The body becomes a plain shape and its faces are renumbered. Refused, nothing changed, when OCC fails or no solid is left: shrunk past half the thinnest part or past a concave fillet's radius. Reply: body, volume, box, sound, distance.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "distance": {
     "type": "number"
    },
    "join": {
     "type": "string",
     "enum": [
      "arc",
      "intersection"
     ]
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "distance"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_thickness": {
  "name": "part_thickness",
  "description": "Shell one solid: open the faces named (open [\"Face6\"], numbered from 1, and/or query { normal: \"+z\", sort: \"-z\", limit: 1 }) and leave walls of thickness mm (above 0.002), inward by default (inward: false grows outward). join intersection (sharp, default) or arc. A body of several solids is refused (part_compound { explode } first). Traps: concave fillets smaller than the wall break an inward shell, so shell first and fillet after; faces are renumbered. Reply: body, volume, box, sound, thickness, inward, opened, volumeChange.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "thickness": {
     "type": "number"
    },
    "open": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "query": {
     "type": "object"
    },
    "inward": {
     "type": "boolean"
    },
    "join": {
     "type": "string",
     "enum": [
      "arc",
      "intersection"
     ]
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "thickness"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_extrude": {
  "name": "part_extrude",
  "description": "Extrude a profile into a solid: length mm along its normal (a face's outward one; a flat outline's plane normal, +z in XY; negative goes the other way), or direction [x,y,z] (its own length, or length given); symmetric: half each way. op new (default without into) | fuse (default with into) | cut | common with into: a boss or a pocket in one call, refused when it misses into. solid: false gives a surface from an open profile. Done on the shape, not as a Part::Extrusion feature (no taper). A sketch used as profile is hidden; into's faces are renumbered. Reply: body, volume, area, faces, box, sound; with into also op, volumeChange. A surface (solid: false) answers as one instead: body, surface: true, faces, area, box, valid, openEdges (edges on its border) and closed — no volume, sound or solids, and it is not among session_state's bodies.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "profile": {
     "description": "A sketch or wire's name, a face or edge (\"Box.Face6\"), { points: [[x,y,z] …], closed: true, smooth }, { points_file: \"<file>.json\"|\".csv\", key } (points read from a file in the session's folder, not sent in the call) or { circle: { center, radius, normal } }."
    },
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "length": {
     "type": "number"
    },
    "direction": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "symmetric": {
     "type": "boolean"
    },
    "solid": {
     "type": "boolean"
    },
    "into": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "op": {
     "type": "string",
     "enum": [
      "new",
      "fuse",
      "cut",
      "common"
     ]
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "profile"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_revolve": {
  "name": "part_revolve",
  "description": "Revolve a profile about an axis: axis [x,y,z] (default +z) through at [x,y,z] (default the origin), angle degrees (default 360; within -360 … 360, not 0). The profile must lie to one side of the axis (touching it is fine). solid: false gives a surface. profile, op / into and the reply as part_extrude (a surface's too: surface, faces, area, openEdges).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "profile": {
     "description": "A sketch or wire's name, a face or edge (\"Box.Face6\"), { points: [[x,y,z] …], closed: true, smooth }, { points_file: \"<file>.json\"|\".csv\", key } (points read from a file in the session's folder, not sent in the call) or { circle: { center, radius, normal } }."
    },
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "axis": {},
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "angle": {
     "type": "number"
    },
    "solid": {
     "type": "boolean"
    },
    "into": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "op": {
     "type": "string",
     "enum": [
      "new",
      "fuse",
      "cut",
      "common"
     ]
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "profile"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "model"
 },
 "part_loft": {
  "name": "part_loft",
  "description": "A solid (solid: false: a surface) through two or more profiles in order: each a sketch, wire, face, { points, closed, smooth } (smooth: a B-spline through them), { points_file, key } or { circle }; or all from profiles_file (many sections read from a file, not sent in the call). All closed or all open. They are lined up first (same way round, seams nearest: aligned says what changed). ruled: true is straight between profiles, each made a polygon of samples points, so it always pairs up. Smooth (default): when OCC refuses or the loft bulges over 15% beyond the profiles it tries again itself (matching B-splines, maxDegree 3 then 2; maxDegree 1–8, default 5), then span by span with the bulging spans ruled (segments: false: off); route says what was done, a refusal names the spans. closed: back to the first profile. Refused, nothing added, when invalid, open or inside out. Heavy: time grows about as the cube of its faces (91 profiles of 36 points ruled 10 s; of 80 points over 2 min); past an estimated minute the first call answers with the estimate and runs nothing, the same call again runs it; a loft kept late says unchecked (run body_check). Reply: body, volume, box, sound, aligned, route, maxDegree, strays (how far it lies from the given points); a surface (solid: false) answers surface: true, faces, area, box, valid, openEdges and closed in place of volume and sound. op / into as part_extrude. More: guide_read { topic: \"model\" }.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "profiles": {
     "type": "array",
     "items": {},
     "description": "Each a sketch or wire's name, a face (\"Box.Face6\"), { points: [[x,y,z] …], closed, smooth }, { points_file: \"<file>.json\"|\".csv\", key, closed, smooth } or { circle }."
    },
    "profiles_file": {
     "type": "string",
     "description": "A .json (a list of [[x,y,z] …] lists, or an object of them) or .csv (x,y,z rows; outlines apart by blank lines or named in a first column) holding every profile, in order. A relative path is in the session's folder."
    },
    "key": {
     "description": "With profiles_file: the name (or number from 0) of the list in the file that holds the profiles."
    },
    "smooth": {
     "type": "boolean",
     "description": "With profiles_file: B-splines through the points (else polygons)."
    },
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "ruled": {
     "type": "boolean"
    },
    "closed": {
     "type": "boolean"
    },
    "solid": {
     "type": "boolean"
    },
    "maxDegree": {
     "type": "integer",
     "minimum": 1,
     "maximum": 8
    },
    "samples": {
     "type": "integer",
     "minimum": 8,
     "maximum": 512
    },
    "segments": {
     "type": "boolean",
     "description": "false: no span-by-span loft when a smooth one bulges."
    },
    "into": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "op": {
     "type": "string",
     "enum": [
      "new",
      "fuse",
      "cut",
      "common"
     ]
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
 "part_sweep": {
  "name": "part_sweep",
  "description": "Sweep one closed profile (a face gives its outer outline) along a path: a wire or sketch, an edge \"Box.Edge3\", a helix from part_wire, or { points } (open by default). frenet: true keeps the profile from twisting along a helix; corners at sharp turns: right (default), round or none (FreeCAD's Transition Right corner, Round corner, Transformed). solid: false gives a surface, and then the profile may be open. Trap: the profile must already sit at the path's start, across it; it is not moved there. profile, op / into and the reply as part_extrude (a surface's too: surface: true, faces, area, box, valid, openEdges, closed — not a solid's sound and problems).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "profile": {
     "description": "A sketch or wire's name, a face or edge (\"Box.Face6\"), { points: [[x,y,z] …], closed: true, smooth }, { points_file: \"<file>.json\"|\".csv\", key } (points read from a file in the session's folder, not sent in the call) or { circle: { center, radius, normal } }."
    },
    "path": {
     "description": "A sketch or wire's name, a face or edge (\"Box.Face6\"), { points: [[x,y,z] …], closed: true, smooth }, { points_file: \"<file>.json\"|\".csv\", key } (points read from a file in the session's folder, not sent in the call) or { circle: { center, radius, normal } }."
    },
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "frenet": {
     "type": "boolean"
    },
    "corners": {
     "type": "string",
     "enum": [
      "right",
      "round",
      "none"
     ]
    },
    "solid": {
     "type": "boolean"
    },
    "into": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "op": {
     "type": "string",
     "enum": [
      "new",
      "fuse",
      "cut",
      "common"
     ]
    },
    "name": {
     "type": "string"
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
  "group": "model"
 },
 "part_container": {
  "name": "part_container",
  "description": "An App::Part container holding objects, moved together by its placement (Std Part): objects [names], at, axis + angle. Not a solid: booleans take the bodies inside it.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
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
  "group": "std_more"
 },
 "compound_explode": {
  "name": "compound_explode",
  "description": "Split a compound into its pieces (Part Explode compound): each a filter object that follows the compound, in a group; the compound is hidden. part_compound { explode } gives plain bodies instead.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "compound": {
     "type": "string"
    }
   },
   "required": [
    "compound"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 },
 "compound_filter": {
  "name": "compound_filter",
  "description": "Keep some pieces of a compound (Part Compound filter): keep items { items: [0, 2], from 0 } | collision-pass / collision-fail { stencil: touching it or not } | window-volume / -area / -length { from, to as percents of the largest piece } | window-distance { stencil, from, to }. Refused when nothing passes; the compound is hidden. Reply: filter, kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "compound": {
     "type": "string"
    },
    "keep": {
     "type": "string"
    },
    "items": {
     "type": "array",
     "items": {
      "type": "integer"
     }
    },
    "stencil": {
     "type": "string"
    },
    "from": {
     "type": "number"
    },
    "to": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "compound"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 },
 "part_join": {
  "name": "part_join",
  "description": "Join walled objects (Part join features; inputs hidden): kind connect { objects } fuses walls keeping the insides; embed { base, tool } sets tool into base; cutout { base, tool } cuts base to fit tool's wall. Pipes and tanks. Reply: valid, solids, volume.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "connect",
      "embed",
      "cutout"
     ]
    },
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "base": {
     "type": "string"
    },
    "tool": {
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
  "group": "std_more"
 },
 "part_import_curves": {
  "name": "part_import_curves",
  "description": "Import a curve network (the edges of a STEP, IGES or BREP; faces left out) as one object, for surface_fill or surface_sections: path (relative: in the session's folder).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "name": {
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
  "group": "std_more"
 },
 "surface_polynomial": {
  "name": "surface_polynomial",
  "description": "A polynomial (quadric) surface fitted by least squares to a mesh's or point cloud's points, as a 3 × 3 Bézier patch over their extent (as Reverse Engineering's Polynomial Surface): from, name. For a patch that is one smooth bowl or saddle; split a scan with meshobj_segments or meshobj_trim first. Reply: surface, points, rms and max mm off the points (along the fit plane's normal).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "from": {
     "type": "string"
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
  "group": "std_more"
 },
 "surface_sections": {
  "name": "surface_sections",
  "description": "A surface through curves in order (Surface Sections, parametric: it follows them): sections [\"Body.Edge3\" | a wire or sketch's name …], two or more, each one open curve, all running the same way; every edge of a named wire is a section of its own. Reply: object, sections, faces, area, closed.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sections": {
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
    "sections"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "surface"
 },
 "surface_boundary": {
  "name": "surface_boundary",
  "description": "A surface bounded by 2–4 curves meeting end to end, given going round (Surface GeomFillSurface, parametric): edges, fill stretched (default, flattest) | coons | curved (rounder). Lines and arcs are taken as B-splines. When coons or curved is refused for curves that do not match, a Surface Filling through the same edges is made instead (reply: note). Reply: object, fill, sides, area.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "edges": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "fill": {
     "type": "string"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "edges"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "surface"
 },
 "surface_extend": {
  "name": "surface_extend",
  "description": "Run a face on past its edges (Surface Extend, parametric): face \"Body.Face2\"; u and v, how far past each pair of opposite edges as a share of its size that way (0.05 = 5% at each end; -0.5 … 10). The result is a new four-sided B-spline surface within 0.1 mm of the face; holes and a trimmed outline are not kept. Reply: object, area.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "face": {
     "type": "string"
    },
    "u": {
     "type": "number"
    },
    "v": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "face"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "surface"
 },
 "surface_sew": {
  "name": "surface_sew",
  "description": "Sew surfaces into one shell (Surface Sewing, parametric): faces [surface objects (all their faces), or \"Body.Face3\"], two or more whose edges meet within tolerance mm (0.01). solid: true also makes a closed shell a solid body (a plain copy). Reply: faces, shells, closed, area; solid { body, volume }, or why not (the shell is open); warning when nothing joined.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "faces": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "tolerance": {
     "type": "number"
    },
    "solid": {
     "type": "boolean"
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
  "group": "surface"
 },
 "surface_cut": {
  "name": "surface_cut",
  "description": "Cut a surface by another object (Surface Cut, a boolean cut that follows both): surface, by. By a solid: what lies inside it is removed. By a surface: nothing is removed, the surface comes back split along where they cross (reply: note; part_extract takes a piece). Reply: object, of, by, faces, area.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "surface": {
     "type": "string"
    },
    "by": {
     "type": "string"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "surface",
    "by"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "surface"
 },
 "surface_blend": {
  "name": "surface_blend",
  "description": "A blend curve joining two edges smoothly (Surface BlendCurve, parametric): start / end { edge \"Body.Edge3\", at 0…1 along it (default: start 0, end 1), continuity 0…4 (1 tangent, 2 curvature, default), size (1; the tangent there is size × the distance between the two points, so 5 swings wide; negative leaves against the edge's direction) }. Reply: object, edges 1, length. Use it as a boundary for the next surface.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "start": {
     "type": "object"
    },
    "end": {
     "type": "object"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "start",
    "end"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "surface"
 }
}
''')
