# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the tools of families/measure.py, inspection.py,
# notes.py, robot.py and ifc.py now kept as data, at the commit they were converted
# from (tests/test_datamisc_data.py's BASE): name, description, inputSchema,
# changes, reads, group. Written by
#   python3 tests/test_datamisc_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "measure_keep": {
  "name": "measure_keep",
  "description": "Keep a measurement in the document as one of FreeCAD's Measure objects (it follows the model and shows in the tree and the window). kind distance (two of: vertex, edge, flat or cylindrical face) | angle (two straight edges or flat faces) | length (one or more edges, summed) | area (one or more faces, summed) | radius (one circular edge, not a cylinder's face) | position (one vertex) | diameter (FreeCAD 1.1 has none: refused, use radius). of: the elements, [\"Body.Face3\", …] (a bare \"Face3\" when there is one body) — elements only, no points or whole objects. Trap: it is tied to face and edge numbers, which change after modelling steps; a measurement that then fails shows in health. Reply: measure (its label), value, unit. measure reads the same without keeping it.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "distance",
      "angle",
      "length",
      "area",
      "radius",
      "diameter",
      "position"
     ]
    },
    "of": {},
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
  "group": "measure"
 },
 "shape_query": {
  "name": "shape_query",
  "description": "Find a body's faces, edges or vertices by what they are; the refs it answers (\"Face12\", \"Edge3\", counted from 1) are what other tools take. kind face|edge|vertex; type plane, cylinder, cone, sphere, torus, bspline (faces) or line, circle, ellipse, bspline (edges); normal [x,y,z] (flat or curved faces, outward at the centre) or axis (a line's direction, a circle's or cylinder's axis, either way) within degrees (1); radius, area, length a number or [least, most]; x / y / z the centre's coordinate within tol (0.01); near [x,y,z] or { point, within } (nearest first); inside { min, max } (the centre in that box); of \"Face6\" that face's edges or vertices. sort area|radius|length|distance|x|y|z, -key largest first; limit (20; found counts all, more the rest). Reply items: ref, type, area / length, centroid / mid, normal, radius, axis, center. Trap: numbers change after any modelling step — query again rather than reuse old ones. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "kind": {
     "type": "string",
     "enum": [
      "face",
      "edge",
      "vertex"
     ]
    },
    "type": {},
    "normal": {},
    "axis": {},
    "within": {
     "type": "number"
    },
    "radius": {},
    "area": {},
    "length": {},
    "near": {},
    "inside": {
     "type": "object"
    },
    "x": {
     "type": "number"
    },
    "y": {
     "type": "number"
    },
    "z": {
     "type": "number"
    },
    "tol": {
     "type": "number"
    },
    "of": {
     "type": "string"
    },
    "sort": {
     "type": "string"
    },
    "limit": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "measure"
 },
 "measure": {
  "name": "measure",
  "description": "Measure one thing or between two. a alone: a face's area (radius, diameter, axis when round; normal when flat), an edge's length (radius for a circle), a body's volume, area and box. a and b: the least distance (mm) with its two points (from, to), the angle in degrees between flat faces (their outward normals: 180 for opposite faces of a plate) or straight edges (0–90), or a line and a face's plane; gap between parallel faces' planes; centers between round ones' centres. References: \"Face12\" with body, \"Box.Face12\", a body's name (the whole shape) or a point [x,y,z]. Changes nothing; measure_keep keeps one in the document.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "a": {
     "description": "\"Face12\" / \"Edge3\" (with body), \"Box.Face12\", a body's name, or a point [x, y, z]."
    },
    "b": {
     "description": "\"Face12\" / \"Edge3\" (with body), \"Box.Face12\", a body's name, or a point [x, y, z]."
    },
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    }
   },
   "required": [
    "a"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "measure"
 },
 "section": {
  "name": "section",
  "description": "Cut a body with a plane and read the cut: area mm², regions, and the outlines as [u, v] polylines in the plane (outer: false marks a hole; a point is origin + u·U + v·V, the reply's plane gives origin, normal, u, v). normal [x,y,z] or \"+z\" (default); at a point on the plane, or offset mm along the normal from the origin; tolerance the chord error (0.05 mm); maxPoints per outline (400). A plane that misses the body is refused with the body's box. Changes nothing (part_section makes the cut an object).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "normal": {},
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "offset": {
     "type": "number"
    },
    "tolerance": {
     "type": "number"
    },
    "maxPoints": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "measure"
 },
 "measure_mass": {
  "name": "measure_mass",
  "description": "Volume mm³, area, mass g, centre of mass and inertia (g·mm² about the centre of mass, document axes; principal moments and axes for one solid) of a body taken as solid through: FreeCAD's own shape mass is only the volume, so the density comes from material (pla, petg, abs, asa, pa6-cf, tpu-95a, nylon, pc, pom, acrylic, hdpe, steel, stainless, aluminium, aluminum, brass, copper, titanium, cast-iron, oak, pine, plywood, or a material_list id or name) or density g/cm³, else the material material_set recorded (a printed part with none is taken as PLA and says so). With neither given and an add-on that owns mass installed, its answer (as printed, inserts included) comes instead, marked from. Reply: density, densityFrom, volume, mass, centerOfMass, inertia. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "material": {
     "type": "string"
    },
    "density": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "measure"
 },
 "clearance": {
  "name": "clearance",
  "description": "The least distance between two bodies a and b (mm), with its two points (from, to); state clear | touching | interference — then interference is the overlapping volume in mm³ and interferenceBox its box. min mm: meets says whether they are clear by at least that. One boolean on the two bodies: slow on bodies of many thousands of faces. Changes nothing; asm_check covers a whole assembly.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "a": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "b": {
     "type": "string",
     "description": "A body's name or label; may be left out when there is one."
    },
    "min": {
     "type": "number"
    }
   },
   "required": [
    "a",
    "b"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "measure"
 },
 "insp_run": {
  "name": "insp_run",
  "description": "Inspect with FreeCAD's own Inspection feature (left in the document): actual — a mesh, points or a body — or file (a scan: stl, obj, ply, off, 3mf, amf, asc, pcd, xyz) against nominals [bodies, meshes, points]. Nothing is aligned: put the actual where the nominal is first (object_align). search_radius mm (1; FreeCAD's own default is 0.05): a point further than that from every nominal reads out of reach, so it must reach past the tolerance. tolerance ±t or [low, high] mm gives the verdict. Distances are signed: + outside a solid nominal (material added), − inside. A mesh or scan is measured at its vertices; a body is meshed first (deflection 0.1 mm, points every spacing mm, default 1% of its size, at most cap 60000) and that hidden mesh measured (how says so). thickness is stored but FreeCAD 1.1 does not use it. Cost grows with points × nominal faces: a free-form body against a big scan takes minutes — raise spacing first. Reply: points, measured, outOfReach, min, max, mean, rms, stdDev, inTolerancePercent, verdict (pass only when all are in tolerance and none out of reach), worst [{ at, distance }], health.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "actual": {
     "type": "string"
    },
    "file": {
     "type": "string"
    },
    "nominals": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "search_radius": {
     "type": "number"
    },
    "thickness": {
     "type": "number"
    },
    "tolerance": {
     "type": [
      "number",
      "array"
     ]
    },
    "deflection": {
     "type": "number"
    },
    "spacing": {
     "type": "number"
    },
    "cap": {
     "type": "integer"
    },
    "name": {
     "type": "string"
    },
    "worst": {
     "type": "integer"
    }
   },
   "required": [
    "nominals"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "inspection"
 },
 "insp_update": {
  "name": "insp_update",
  "description": "Change an inspection and measure again: search_radius, thickness, tolerance (±t or [low, high]; null clears), nominals — at least one; inspection may be left out when there is one. Checked before anything is set (a tolerance past the search radius is refused). Reply: as insp_run.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "inspection": {
     "type": "string"
    },
    "search_radius": {
     "type": "number"
    },
    "thickness": {
     "type": "number"
    },
    "tolerance": {
     "type": [
      "number",
      "array",
      "null"
     ]
    },
    "nominals": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "worst": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "inspection"
 },
 "insp_read": {
  "name": "insp_read",
  "description": "One inspection's numbers (the one there is when inspection is left out): points, measured, outOfReach, min, max, mean, rms, stdDev, p95abs, histogram, tolerance, inTolerancePercent, over, under, verdict, worst spots (worst: how many, 10). Distances in mm, + outside the nominal. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "inspection": {
     "type": "string"
    },
    "worst": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "inspection"
 },
 "insp_list": {
  "name": "insp_list",
  "description": "The inspections in the document, a line each: inspection, actual, nominals, points, rms, inTolerancePercent, verdict, outOfReachPercent. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "inspection"
 },
 "insp_faces": {
  "name": "insp_faces",
  "description": "An inspection split by the nominal body's faces: each face (\"Body.Face4\") with its points, mean offset (+ the actual sits outside there), min, max, rms and, with a tolerance, outOfTolerance and verdict — the faces that are off first; failing lists them. A face off evenly is displaced; one with min and max far apart is out of form. body: which body when the nominals hold several or none; reach mm (the search radius): how near a face a point must be to count for it; limit (30). Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "inspection": {
     "type": "string"
    },
    "body": {
     "type": "string"
    },
    "reach": {
     "type": "number"
    },
    "deflection": {
     "type": "number"
    },
    "limit": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "inspection"
 },
 "insp_export": {
  "name": "insp_export",
  "description": "Write an inspection out to the session's folder: <name>.csv with a row a point (x, y, z, distance_mm, status ok | over | under | out_of_reach) and <name>.json with insp_read's numbers. name: the files' base name (the inspection's label by default). Reply: files { csv { path, rows }, json { path } }, summary. The document is not changed.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "inspection": {
     "type": "string"
    },
    "name": {
     "type": "string"
    },
    "worst": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "inspection"
 },
 "note_add": {
  "name": "note_add",
  "description": "Pin a note to the part for the person — a question or a remark (text): at [x,y,z] mm, or on body + faces (\"Face6\", or shape_query's filters; pinned at the first face's centre and found again when faces renumber). It shows as a numbered pin in the window and in Agent Link's Notes tab; the person answers it there. Kept in the document (saved with doc_save). Reply: note { id, text, at, body, face, by: agent }, note_count.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "text": {
     "type": "string"
    },
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "body": {
     "type": "string"
    },
    "faces": {}
   },
   "required": [
    "text"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "notes"
 },
 "note_list": {
  "name": "note_list",
  "description": "The notes pinned to the parts — the person's and the agent's — each with id, text, by, at, face, answer and done. waiting lists the ids of the person's notes with no answer yet (answer them: note_answer, then note_done); followed says which notes moved to a renumbered face. open: true leaves out the done ones. Read it at the start of a session and after the person has worked in the window.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "open": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "notes"
 },
 "note_answer": {
  "name": "note_answer",
  "description": "Answer a note (the person's question or request): id (from note_list), text. The answer shows under the note in the window; a second answer replaces the first. note_done ticks it off once dealt with.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "id": {
     "type": "integer"
    },
    "text": {
     "type": "string"
    }
   },
   "required": [
    "id",
    "text"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "notes"
 },
 "note_done": {
  "name": "note_done",
  "description": "Tick a note off: id (done: false opens it again). It stays in the document; note_delete removes it.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "id": {
     "type": "integer"
    },
    "done": {
     "type": "boolean"
    }
   },
   "required": [
    "id"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "notes"
 },
 "note_delete": {
  "name": "note_delete",
  "description": "Take a note out of the document for good: id — the person's or the agent's (note_done only ticks it off; delete the person's only when they ask). Reply: deleted, left.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "id": {
     "type": "integer"
    }
   },
   "required": [
    "id"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "notes"
 },
 "steps_list": {
  "name": "steps_list",
  "description": "A PartDesign body's history in order (body may be left out when there is one): each feature's step number, name, label, type, its key value, the volume after it and what it added or took away (sketches: true lists the sketches too). The same list Agent Link's Steps tab plays. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "sketches": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "notes"
 },
 "steps_render": {
  "name": "steps_render",
  "description": "The build played back as pictures, drawn headless (not the window): a PNG a feature (step_01.png …), framed on the finished part so it grows in place, each captioned with its step, type and what it did, and a contact sheet steps.png of them all (sheet: false leaves it out; inline: false keeps it out of the reply). body; view (iso, or top, front, right …); width, height pixels a picture (480 × 360); path a folder (steps_<body> in the session's folder). Tessellates every step: seconds a step on a heavy body. Reply: folder, files, sheet, steps. The model is not changed.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "view": {
     "type": "string"
    },
    "width": {
     "type": "integer"
    },
    "height": {
     "type": "integer"
    },
    "path": {
     "type": "string"
    },
    "sheet": {
     "type": "boolean"
    },
    "inline": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "notes"
 },
 "robot_trajectory": {
  "name": "robot_trajectory",
  "description": "Combine or adjust trajectories as new objects that follow their sources (FreeCAD's compound and dress-up): op join (trajectories [names], in order) | dress (trajectory, with any of: speed mm/s and acceleration for every waypoint, cont true | false, move [x,y,z] added to every waypoint and/or ypr [yaw, pitch, roll] turned on top of each one's orientation — the same path at another place or angle; add: UseOrientation makes ypr replace the orientations instead). Reply: trajectory, waypoints, seconds, length_mm.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "op": {
     "type": "string",
     "enum": [
      "join",
      "dress"
     ]
    },
    "trajectories": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "trajectory": {
     "type": "string"
    },
    "speed": {
     "type": "number"
    },
    "acceleration": {
     "type": "number"
    },
    "cont": {
     "type": "boolean"
    },
    "move": {
     "type": "array",
     "items": {}
    },
    "ypr": {
     "type": "array",
     "items": {}
    },
    "add": {
     "type": "string"
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
  "group": "robot"
 },
 "robot_new": {
  "name": "robot_new",
  "description": "A six-axis robot (Robot::RobotObject): model kr16 | kr125 | kr210 | kr500 (KUKA kinematics and picture, where this FreeCAD ships the files) | puma (only a name for the built-in default below: no Puma's kinematics), or kinematics: a CSV of your own (a header line, then six lines of a, alpha, d, theta, rotDir, maxAngle, minAngle, velocity; mm and degrees). Without a file the robot is FreeCAD's built-in default, a KUKA IR 500 — the reply's model says which was used. tool { at, ypr }: the tool's point from the flange (a gripper's tip), which tcp in robot_move and robot_run then means. at, ypr are stored as its Base, but FreeCAD's kinematics do not use it: positions are always in the robot's own frame, origin at its foot. Reply: robot, axes [6 degrees], tcp { at, ypr }, model.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "model": {
     "type": "string"
    },
    "kinematics": {
     "type": "string"
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "ypr": {
     "type": "array",
     "items": {}
    },
    "tool": {
     "type": "object",
     "description": "{ at [x,y,z], ypr [yaw, pitch, roll] | axis + angle }"
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
  "group": "robot"
 },
 "robot_move": {
  "name": "robot_move",
  "description": "Move a robot (the one there is when robot is left out): axes [six degrees] (forward: tcp in the reply is where the tool point lands), tcp { at [x,y,z] mm, ypr [yaw, pitch, roll] degrees or axis + angle } (inverse kinematics from the pose it is in, within the axes' limits: reached false and off_mm when it could not get there, the axes then as they were), or home: true (the home pose set in FreeCAD, else all axes 0). An orientation left out means none (tool axes along the robot's) — usually unreachable: read tcp.ypr from the reply of an axes move and keep it. Reply: axes, tcp, reached.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "robot": {
     "type": "string"
    },
    "axes": {
     "type": "array",
     "items": {}
    },
    "tcp": {
     "type": "object",
     "description": "{ at [x,y,z], ypr [yaw, pitch, roll] | axis + angle }"
    },
    "home": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "robot"
 },
 "robot_path": {
  "name": "robot_path",
  "description": "A trajectory object: waypoints [{ at, ypr, type LIN | PTP | CIRC | WAIT (LIN by default), speed mm/s (1000), cont, name }], two or more, in the robot's frame — or edges [\"Body.Edge3\", …] (or an object for all its edges; one object only) to follow, deviation mm (0.5) from curved ones, useRotation for the edges' own orientation. Reply: trajectory, waypoints, length mm, seconds. robot_run checks a robot can follow it.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "waypoints": {
     "type": "array",
     "items": {}
    },
    "edges": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "deviation": {
     "type": "number"
    },
    "useRotation": {
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
  "group": "robot"
 },
 "robot_run": {
  "name": "robot_run",
  "description": "Check a trajectory on a robot without moving it for good: samples (100; 2 … 5000) points along it by time, each solved by inverse kinematics from the one before, the tool point (robot_new tool) on the path. Reply: verdict (reaches all | misses n of N), misses [{ t, at, off_mm }] (the first 20), worst_mm, each axis's range of angles used, seconds. A miss is a point out of reach or past an axis limit, or one the solver could not follow to. The robot's axes are put back as they were.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "robot": {
     "type": "string"
    },
    "trajectory": {
     "type": "string"
    },
    "samples": {
     "type": "integer"
    }
   },
   "required": [
    "trajectory"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "robot"
 },
 "robot_export": {
  "name": "robot_export",
  "description": "Write a trajectory as KUKA KRL (.src) with FreeCAD's exporter: path (relative: the session's folder; .src added); every waypoint is written as a LIN move with its speed, whatever its type (FreeCAD's compact form; full: true is refused where FreeCAD's full form writes nothing, as in 1.1). Positions are the waypoints as they are (no tool or base applied). Reply: path, lines, moves. Simulate it on the controller before running; running it is the person's.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "robot": {
     "type": "string"
    },
    "trajectory": {
     "type": "string"
    },
    "path": {
     "type": "string"
    },
    "full": {
     "type": "boolean"
    }
   },
   "required": [
    "trajectory"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "robot"
 },
 "ifc_open": {
  "name": "ifc_open",
  "description": "Open an IFC file (path) to edit in place with IfcOpenShell: nothing is added to the FreeCAD document, and GlobalIds and all that is untouched stay as they are. One file at a time. Answers schema, storeys (elevation in the file's unit), classes (counts). The ifc_ tools exist only when FreeCAD has IfcOpenShell.",
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
  "changes": false,
  "reads": {},
  "group": "bim"
 },
 "ifc_find": {
  "name": "ifc_find",
  "description": "Find elements in the open IFC, filters combined: class (IfcWall …; every product when left out), name (contains), storey (exact name), where { \"Pset_WallCommon.IsExternal\": true }, or ids (GlobalIds). limit (50); detail: true adds psets, quantities, material. Answers elements [{ id, class, name, storey }].",
  "inputSchema": {
   "type": "object",
   "properties": {
    "ids": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "class": {
     "type": "string"
    },
    "name": {
     "type": "string"
    },
    "storey": {
     "type": "string"
    },
    "where": {
     "type": "object"
    },
    "detail": {
     "type": "boolean"
    },
    "limit": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "bim"
 },
 "ifc_edit": {
  "name": "ifc_edit",
  "description": "Change elements of the open IFC, chosen by ifc_find's filters (one at least): attributes { Name, Description, ObjectType, Tag }, properties { \"Pset_WallCommon.FireRating\": \"REI60\" }, material (by name), storey_to (a storey's name), classification { system, code, title }. Over max (200) matches is refused. In memory until ifc_save.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "ids": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "class": {
     "type": "string"
    },
    "name": {
     "type": "string"
    },
    "storey": {
     "type": "string"
    },
    "where": {
     "type": "object"
    },
    "attributes": {
     "type": "object"
    },
    "properties": {
     "type": "object"
    },
    "material": {
     "type": "string"
    },
    "storey_to": {
     "type": "string"
    },
    "classification": {
     "type": "object"
    },
    "max": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "bim"
 },
 "ifc_remove": {
  "name": "ifc_remove",
  "description": "Remove elements from the open IFC by GlobalId (ids, from ifc_find), with their openings and relationships. In memory until ifc_save; outside undo.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "ids": {
     "type": "array",
     "items": {
      "type": "string"
     }
    }
   },
   "required": [
    "ids"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "bim"
 },
 "ifc_save": {
  "name": "ifc_save",
  "description": "Write the open IFC with its edits: path (default <name>_edited.ifc in the output folder), or overwrite: true to write over the file it came from.",
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
  "group": "bim"
 },
 "ifc_diff": {
  "name": "ifc_diff",
  "description": "Compare two IFC files (a old, b new) by GlobalId: elements added, removed and changed (attributes, property sets, material, storey; not geometry). limit (60). Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "a": {
     "type": "string"
    },
    "b": {
     "type": "string"
    },
    "limit": {
     "type": "integer"
    }
   },
   "required": [
    "a",
    "b"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "bim"
 }
}
''')
