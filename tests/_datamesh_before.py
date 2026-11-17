# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of each converted tool at the base commit (tests/test_datamesh_data.py
# checks it against git where the commit is there): name, description, schema, flags, group.
import json

BEFORE = json.loads(r"""
{
 "meshobj_unwrap": {
  "name": "meshobj_unwrap",
  "description": "Lay a surface flat as a cutting pattern (sheet, fabric, leather): of a body's face \"Body.Face3\" or an open mesh in one piece. A plane, cylinder or cone face rolls out exactly; other faces and meshes go through FreeCAD's flatmesh (up to 50,000 triangles, run apart with a 5 minute limit; a closed mesh is refused). Reply: area3d, areaFlat, stretch { mean, max % }, outlines, size, pattern (the wire object; make: false keeps none); path .svg or .dxf writes it. tolerance mm tessellates a face (0.1).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "of": {
     "type": "string"
    },
    "path": {
     "type": "string"
    },
    "make": {
     "type": "boolean"
    },
    "tolerance": {
     "type": "number"
    },
    "iterations": {
     "type": "integer"
    },
    "weight": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "of"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "mesh"
 },
 "meshobj_from_shape": {
  "name": "meshobj_from_shape",
  "description": "Mesh a body (MeshPart) into a new mesh object: method standard (deflection mm off the surface, 0.05; angle deg, 15) | mefisto (maxLength mm: even triangles, but it can leave faces with small holes open: the reply warns) | netgen (fineness verycoarse … veryfine; unavailable where FreeCAD lacks it). A flat-sided body meshes to two triangles a face (a box: 12); a small deflection on a large curved body makes hundreds of thousands (reply: heavy). Reply: mesh, points, facets, solid, components, area, volume, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "method": {
     "type": "string"
    },
    "deflection": {
     "type": "number"
    },
    "angle": {
     "type": "number"
    },
    "maxLength": {
     "type": "number"
    },
    "fineness": {
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
  "group": "mesh"
 },
 "meshobj_info": {
  "name": "meshobj_info",
  "description": "A mesh's size and the Mesh workbench's evaluation: points, facets, solid (closed), components, area, volume, box; evaluation { nonManifolds, selfIntersections, flippedNormals, corruptedFacets, … }, problems, verdict clean or next. Changes nothing. The self-intersection test is slow on a dense mesh (not measured): background: true runs it as a job.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "mesh"
 },
 "meshobj_repair": {
  "name": "meshobj_repair",
  "description": "Repair a mesh as Evaluate & Repair does: fix any of normals, duplicates, nonmanifolds, selfintersections, degenerate, folds, indices, pointsonedges (default: those), holes (loops up to maxHoleEdges, 50, filled flat), islands (pieces of minFacets, 10, or fewer triangles dropped). Each step is kept only if it leaves no more open or overloaded edges (undone says which). Reply: did, fixed, problems (left), edges { open, overloaded }, before. In place; copy: true leaves the original. Evaluates twice: slow on a dense mesh, and a change cannot run as a job.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    },
    "fix": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "tolerance": {
     "type": "number"
    },
    "maxHoleEdges": {
     "type": "integer"
    },
    "minFacets": {
     "type": "integer"
    },
    "copy": {
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
  "group": "mesh"
 },
 "meshobj_decimate": {
  "name": "meshobj_decimate",
  "description": "Fewer triangles: reduction (share to remove, 0.5) or facets (how many to keep); tolerance (0.1) caps the error one collapse may add, so it can stop short of the count (the reply's note says so: raise tolerance). Reply: reduced \"n → m triangles\", the mesh's reading, before.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    },
    "reduction": {
     "type": "number"
    },
    "facets": {
     "type": "integer"
    },
    "tolerance": {
     "type": "number"
    },
    "copy": {
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
  "group": "mesh"
 },
 "meshobj_refine": {
  "name": "meshobj_refine",
  "description": "More triangles: rounds 1 … 3, each putting a point in the middle of every triangle (about three times as many; refused past 2,000,000); optimize: true swaps edges to even their shapes. The surface does not change. Reply: refined \"n → m triangles\".",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    },
    "rounds": {
     "type": "integer"
    },
    "optimize": {
     "type": "boolean"
    },
    "copy": {
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
  "group": "mesh"
 },
 "meshobj_smooth": {
  "name": "meshobj_smooth",
  "description": "Smooth a mesh: method taubin (default; shrinks far less than laplace, but a coarse mesh still loses volume; lambda 0.6307, mu 0.0424) | laplace (lambda; shrinks), iterations (3). Reply: volumeChange mm³ on a closed mesh, warning past 2%.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    },
    "method": {
     "type": "string"
    },
    "iterations": {
     "type": "integer"
    },
    "lambda": {
     "type": "number"
    },
    "mu": {
     "type": "number"
    },
    "copy": {
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
  "group": "mesh"
 },
 "meshobj_edit": {
  "name": "meshobj_edit",
  "description": "Edit a mesh on a copy, as ScanRuler's Mesh Tools do: action begin { mesh } (a copy made, the original hidden; every meshobj tool given the original's name then changes the copy) | use (the copy put in place of the original) | discard (the copy dropped) | state (default: what is being edited).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "action": {
     "type": "string",
     "enum": [
      "begin",
      "use",
      "discard",
      "state"
     ]
    },
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "mesh"
 },
 "meshobj_trim": {
  "name": "meshobj_trim",
  "description": "Cut a mesh with a plane: at [x,y,z] on it, normal (the side it points to is removed); close: true caps the cut flat (loops up to maxHoleEdges, 1000); preview: true answers wouldRemove / wouldCut / wouldKeep and changes nothing. Refused when nothing would be left. Reply: removed (triangles wholly on that side), cut (triangles the plane crossed, each kept in part), solid, warning when the cap did not close it.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "normal": {
     "type": "array",
     "items": {}
    },
    "close": {
     "type": "boolean"
    },
    "maxHoleEdges": {
     "type": "integer"
    },
    "preview": {
     "type": "boolean"
    },
    "copy": {
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
  "group": "mesh"
 },
 "meshobj_transform": {
  "name": "meshobj_transform",
  "description": "Scale (a factor or [x,y,z]), rotate { axis, angle degrees }, move [x,y,z], mirror \"x\" | \"y\" | \"z\" a mesh's points, in that order, about the document's origin and axes. A mirror keeps the triangles facing out. In place; copy: true makes a new mesh.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    },
    "scale": {
     "type": [
      "number",
      "array"
     ]
    },
    "rotate": {
     "type": "object"
    },
    "move": {
     "type": "array",
     "items": {}
    },
    "mirror": {
     "type": "string"
    },
    "copy": {
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
  "group": "mesh"
 },
 "meshobj_boolean": {
  "name": "meshobj_boolean",
  "description": "A boolean of two closed meshes (meshobj_info: solid true): a, b, op union | intersection | difference (a minus b); a new mesh, a and b kept. Dense scans as they are: only the triangles the other mesh crosses are cut (built for scans of 100,000 triangles and more; time not measured, and a change cannot run as a job). Reply: how (which engine made it), solid, volume.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "a": {
     "type": "string"
    },
    "b": {
     "type": "string"
    },
    "op": {
     "type": "string"
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
  "group": "mesh"
 },
 "meshobj_sections": {
  "name": "meshobj_sections",
  "description": "Cross-sections of a mesh as wires: normal (default z), count evenly spaced (5) or at [distances from the origin along normal], up to 500; tolerance mm joins cut ends (0.01). Reply: slices [{ at, loops, length }], sections (the wire compound; export writes DXF, part_face makes a face).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
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
     "items": {}
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
  "group": "mesh"
 },
 "meshobj_split": {
  "name": "meshobj_split",
  "description": "Split a mesh into its separate pieces, a mesh object each, largest first (minFacets leaves out smaller ones; over 100 pieces is refused: raise minFacets). The original is hidden, not removed. Reply: pieces, facets.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    },
    "minFacets": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "mesh"
 },
 "meshobj_segments": {
  "name": "meshobj_segments",
  "description": "Find a mesh's flat regions: kind planar (deviation mm off a fitted plane, 0.01; about the noise on a scan) | curvature (both curvatures within tolerance 1/mm of 0); minFacets (20). Reply: segments (count), largest [{ facets, area, center, normal }] up to top (12); keep: true makes those meshes. On a scan: where to put a sketch. Slow on a dense mesh (every region is walked; not measured).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    },
    "kind": {
     "type": "string"
    },
    "deviation": {
     "type": "number"
    },
    "tolerance": {
     "type": "number"
    },
    "minFacets": {
     "type": "integer"
    },
    "top": {
     "type": "integer"
    },
    "keep": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "mesh"
 },
 "meshobj_curvature": {
  "name": "meshobj_curvature",
  "description": "A mesh's curvature: flatPercent (points under flat, 0.001 1/mm), tightestRadius and medianRadius mm, meanCurvature { min, max }. view_render { map: \"curvature\" } colours it. Changes nothing; on a dense mesh background: true runs it as a job.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    },
    "flat": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "mesh"
 },
 "meshobj_project": {
  "name": "meshobj_project",
  "description": "Project a wire, sketch or body's edges onto a mesh along direction [x,y,z] (default down, [0,0,-1]); kept as wires on its surface. Reply: projection, wires, length.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    },
    "shape": {
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
    "shape"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "mesh"
 },
 "meshobj_primitive": {
  "name": "meshobj_primitive",
  "description": "A mesh primitive (the Mesh workbench's regular solids): kind box (size [x,y,z], a corner at at) | sphere (radius, centred) | cylinder | cone (radius at the base, radius2 at the top, height; base centre at at, up +z) | torus (radius, radius2 the tube; centred, axis z); segments round (48). Reply: mesh, facets, solid, volume, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "box",
      "sphere",
      "cylinder",
      "cone",
      "torus"
     ]
    },
    "size": {
     "type": "array",
     "items": {}
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
    "at": {
     "type": "array",
     "items": {}
    },
    "segments": {
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
  "group": "mesh"
 },
 "meshobj_merge": {
  "name": "meshobj_merge",
  "description": "Put meshes into one mesh object where they stand (not fused: components stay apart; meshobj_boolean union fuses): meshes [names]; remove: true drops the originals. Reply: components, facets.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "meshes": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "remove": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "meshes"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "mesh"
 },
 "meshobj_boundary": {
  "name": "meshobj_boundary",
  "description": "A mesh's open edges as wires (Reverse Engineering's mesh boundary): loops, openEdges, boundaries [{ edges, length, closed, centre, area }] longest first (20); keep (default) makes them a wire compound to fill, sweep or fit. A closed mesh answers loops 0.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
    },
    "keep": {
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
  "group": "mesh"
 },
 "meshobj_export": {
  "name": "meshobj_export",
  "description": "Write a document mesh to a file, the format by path's extension: stl (binary), ast, obj, ply, off, 3mf, amf, smf, wrl, x3d, iv, nas … (default <label>.stl in the out folder), where it stands, in mm. Reply: file, format, bytes, facets. Changes nothing; background: true runs a big one as a job.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "mesh": {
     "type": "string",
     "description": "The mesh's label; may be left out when there is one."
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
  "group": "mesh"
 },
 "points_import": {
  "name": "points_import",
  "description": "Read a point cloud file: path .asc / .xyz / .txt / .csv (x y z a line), .pcd, .ply, .e57 (where FreeCAD has the E57 library). every: keep every n-th point; scale: mm per file unit (1000 for metres). Positions only. The whole file is read into memory: thin a huge one with every. Answers object, points (kept), read, min, max, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "every": {
     "type": "integer"
    },
    "scale": {
     "type": "number"
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
  "group": "points"
 },
 "points_sample": {
  "name": "points_sample",
  "description": "A point cloud spread evenly over a body's, surface's or mesh's faces (object): count (5000; up to 2000000), noise mm (to try a fit as a scan would see it), seed, tolerance mm (faceting of curved faces, 0.01). Answers object, points, min, max, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "object": {
     "type": "string"
    },
    "count": {
     "type": "integer"
    },
    "noise": {
     "type": "number"
    },
    "seed": {
     "type": "integer"
    },
    "tolerance": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "object"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "points"
 },
 "points_info": {
  "name": "points_info",
  "description": "A point cloud's points (count), min, max, box (mm, where it stands in the document), centre and spacing (typical gap between neighbours). Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "string",
     "description": "The point cloud's label (the only one when left out)."
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "points"
 },
 "points_crop": {
  "name": "points_crop",
  "description": "Keep part of a cloud, filters combined: box [[min], [max]], near [x, y, z] with radius, plane { at, normal } (the side the normal points to); outside: true keeps the rest. specks { radius, least } drops points with fewer than least neighbours; thin mm keeps one point per cell. The cloud itself is cut down unless replace: false. Answers from, kept, min, max, box; refused, nothing changed, when no point is left.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "string",
     "description": "The point cloud's label (the only one when left out)."
    },
    "box": {
     "type": "array",
     "items": {}
    },
    "near": {
     "type": "array",
     "items": {}
    },
    "radius": {
     "type": "number"
    },
    "plane": {
     "type": "object"
    },
    "outside": {
     "type": "boolean"
    },
    "thin": {
     "type": "number"
    },
    "specks": {
     "type": "object"
    },
    "replace": {
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
  "group": "points"
 },
 "points_fit": {
  "name": "points_fit",
  "description": "Fit a shape through all of a cloud's points (crop to the one feature first): shape plane (centre, normal) | sphere (centre, diameter) | cylinder (base, axis, diameter, length; axis is a hint) | surface (a B-spline sheet over the points' own plane, one side only: degree 3, poles 6, smooth; 200000 points at most) | curve (a B-spline along a line of points; a loop closes itself: degree, tolerance). Answers rms and max (the points' distance from it, mm; a large max means the crop holds more than the feature); tolerance adds verdict fits | does not fit. make: true keeps the shape as an object (a surface or curve always is).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "string",
     "description": "The point cloud's label (the only one when left out)."
    },
    "shape": {
     "type": "string",
     "enum": [
      "plane",
      "sphere",
      "cylinder",
      "surface",
      "curve"
     ]
    },
    "axis": {
     "type": "array",
     "items": {}
    },
    "tolerance": {
     "type": "number"
    },
    "make": {
     "type": "boolean"
    },
    "degree": {
     "type": "integer"
    },
    "poles": {
     "type": "integer"
    },
    "smooth": {
     "type": "boolean"
    },
    "weight": {
     "type": "number"
    },
    "iterations": {
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
  "group": "points"
 },
 "points_merge": {
  "name": "points_merge",
  "description": "Join two or more point clouds into a new one: points [labels]; remove: true deletes the originals. Answers points (its label), count, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "remove": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "points"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "points"
 },
 "points_mesh": {
  "name": "points_mesh",
  "description": "A mesh through a point cloud: method height (one side of a surface: a height field on the points' own plane, one vertex per cell mm, about six points a cell by default) | hull (convex) | poisson (closed; only in a FreeCAD built with PCL; depth). Answers mesh, facets, area, closed. Then meshobj_repair / part_from_mesh.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "string",
     "description": "The point cloud's label (the only one when left out)."
    },
    "method": {
     "type": "string",
     "enum": [
      "height",
      "hull",
      "poisson"
     ]
    },
    "cell": {
     "type": "number"
    },
    "depth": {
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
  "group": "points"
 },
 "points_export": {
  "name": "points_export",
  "description": "Write a point cloud (mm, where it stands) to path: .ply (binary, 32-bit floats), .pcd, .asc / .xyz, .csv; <label>.ply in the output folder by default. Read back: answers count, readBack (should match), maxError. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "string",
     "description": "The point cloud's label (the only one when left out)."
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
  "group": "points"
 }
}
""")
