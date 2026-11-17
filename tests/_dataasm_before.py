# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the Assembly tools of families/assembly.py and
# assembly_more.py now kept as data, at the commit they were converted from
# (tests/test_dataasm_data.py's BASE): name, description, inputSchema,
# changes, reads, group. Written by
#   python3 tests/test_dataasm_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "asm_new": {
  "name": "asm_new",
  "description": "Put bodies together in a new assembly (FreeCAD's Assembly workbench): parts by label — the bodies themselves move into it (not links), and a body is in one assembly only. The first is grounded (held fixed) unless ground names another or is false; with nothing grounded no joint solves. Reply: assembly, parts, grounded. Then asm_joint between them.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "parts": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "name": {
     "type": "string"
    },
    "ground": {}
   },
   "required": [
    "parts"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "assembly"
 },
 "asm_add": {
  "name": "asm_add",
  "description": "Put more bodies into an assembly: parts by label (moved in, not linked; ones already in are skipped). They float free until asm_joint ties them to a grounded part. Reply: added, parts.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "parts": {
     "type": "array",
     "items": {
      "type": "string"
     }
    }
   },
   "required": [
    "parts"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "assembly"
 },
 "asm_ground": {
  "name": "asm_ground",
  "description": "Hold a part fixed where it stands (grounded: true, the default) or let it move again (false). An assembly needs at least one grounded part: with none every solve answers \"no part is grounded\". Reply: grounded, every part held.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "part": {
     "type": "string"
    },
    "grounded": {
     "type": "boolean"
    }
   },
   "required": [
    "part"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "assembly"
 },
 "asm_joint": {
  "name": "asm_joint",
  "description": "Join two parts and solve (needs a grounded part): kind fixed (no motion), revolute (turns about the joint's axis), cylindrical (turns and slides), slider (slides only), ball, distance (distance mm between the elements; round faces count from their surface), parallel, perpendicular, angle (angle degrees, 90); couplings, which tie one motion to another for asm_sweep and need each part's own revolute or slider too: rackpinion (radius1, the pinion's pitch radius), screw (pitch mm a turn), gears and belt (radius1, radius2 — read off round edges when left out). a and b each a part and a face or edge on it — a flat face puts the joint at its middle along its normal; a round edge or cylindrical face, on its axis. offset mm along b's joint normal and rotate degrees about it; reverse: true turns the moved part over (false keeps FreeCAD's way; left out, it is turned over when that stops parts overlapping). Which part moves: the one not yet joined to a grounded part (a when neither is), with what is joined to it; a grounded part never. Reply: joint, solve, moved { part: from, to, by }, flipped, overlaps with a warning. Unsolved is refused, nothing kept. FreeCAD 1.1's solver answers only solved or solver error — not freedom left, nor a joint that repeats another: asm_check and asm_sweep show what still moves.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "kind": {
     "type": "string",
     "enum": [
      "fixed",
      "revolute",
      "cylindrical",
      "slider",
      "ball",
      "distance",
      "parallel",
      "perpendicular",
      "angle",
      "rackpinion",
      "screw",
      "gears",
      "belt"
     ]
    },
    "a": {
     "type": "object",
     "description": "{ part, element } — element \"Face6\" or a query { kind: face|edge, normal, near, radius, type } as shape_query takes; near picks the closest of several."
    },
    "b": {
     "type": "object",
     "description": "{ part, element } — element \"Face6\" or a query { kind: face|edge, normal, near, radius, type } as shape_query takes; near picks the closest of several."
    },
    "offset": {
     "type": "number"
    },
    "rotate": {
     "type": "number"
    },
    "distance": {
     "type": "number"
    },
    "angle": {
     "type": "number"
    },
    "radius1": {
     "type": "number"
    },
    "radius2": {
     "type": "number"
    },
    "pitch": {
     "type": "number"
    },
    "reverse": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "kind",
    "a",
    "b"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "assembly"
 },
 "asm_list": {
  "name": "asm_list",
  "description": "An assembly: parts [{ part, placement { at, axis, angle degrees }, grounded }], joints [{ joint, kind, a, b as Part.Element, suppressed }] and solve. It runs the solver to answer solve, which puts a part dragged off its joints back; nothing else changes.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "assembly"
 },
 "asm_joint_remove": {
  "name": "asm_joint_remove",
  "description": "Remove a joint (by label or object name; asm_list lists them) and solve again. Parts stay where they stand; one left joined to nothing grounded floats free (asm_check: notConnected). Reply: removed, solve.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "joint": {
     "type": "string"
    }
   },
   "required": [
    "joint"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "assembly"
 },
 "asm_sweep": {
  "name": "asm_sweep",
  "description": "Move a revolute joint through angles (from, to degrees; 0 to 90, or its asm_limits) or a slider or cylindrical one along its axis (mm; 0 to 10; turn: true turns a cylindrical) in steps (12, at most 72), checking every pair of parts for overlap at each (clearance mm also lists pairs closer). from and to count from where the joint stands now. The moving part carries the parts joined beyond it rigidly; gears, belt, rackpinion and screw drive theirs by ratio; a closed loop (a four-bar) is not followed. Reply: moves, driven, axis, steps [{ at, overlaps, closer }], verdict clear | collides, collidesAt, clearFromStart; every part is put back. Does the lid open fully, does the arm swing past the post. Each step cuts every pair of parts (a call is dropped after about 80 s): with many parts, fewer steps or a shorter range, not a job.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "joint": {
     "type": "string"
    },
    "from": {
     "type": "number"
    },
    "to": {
     "type": "number"
    },
    "steps": {
     "type": "integer"
    },
    "clearance": {
     "type": "number"
    },
    "turn": {
     "type": "boolean"
    }
   },
   "required": [
    "joint"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "assembly"
 },
 "asm_check": {
  "name": "asm_check",
  "description": "Check an assembly: every part of it, shown or hidden (hidden names those checked though hidden), inside App::Parts and sub-assemblies and through links too, each where it stands: solve; overlaps [{ parts, volume mm³, at }] (a screw's thread in a tapped hole is marked thread and not counted against the verdict); with clearance mm, closerThan pairs; notConnected, parts joined to nothing grounded (the solver leaves them and their joints out without a word). verdict clear | fix. Freedom left is not counted (FreeCAD 1.1 does not report it): asm_sweep shows what a joint lets move. Every pair of parts is cut against each other, so dozens of parts take a while. view_render shows it; section cuts it open at a fit.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "clearance": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "assembly"
 },
 "asm_fits": {
  "name": "asm_fits",
  "description": "Fits: for each joint (or joint, or pairs [{ a: { part, element }, b }] for parts with no joint), the hole and the shaft it puts together — found as cylindrical faces of about one size on the joint's axis — as fits [{ hole, shaft: { part, diameter }, clearance (minus: interference), engagement mm, axisOffset }]; with fit \"H7/g6\" (size: the nominal, else read off the parts to 0.05 mm) each held to ISO 286: the fit's type and clearanceRange, each part's limits and ok, verdict pass | fix. Flat faces: their gap and angle. A joint with nothing round is skipped with the reason. Parts drawn at nominal size fail a shaft band like g6: say so, do not hide it. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "joint": {
     "type": "string"
    },
    "pairs": {
     "type": "array",
     "items": {
      "type": "object",
      "properties": {
       "a": {
        "type": "object"
       },
       "b": {
        "type": "object"
       },
       "fit": {
        "type": "string"
       },
       "size": {
        "type": "number"
       }
      }
     }
    },
    "fit": {
     "type": "string"
    },
    "size": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "assembly"
 },
 "asm_motion": {
  "name": "asm_motion",
  "description": "Saved motions of an assembly, kept by Agent Link in the document (not FreeCAD's own Simulation object): action save (name, keys: two or more [{ joint: value, … }, …] in order, degrees or mm from each joint's own zero, as asm_pose) | play (name: steps between keys, 6; clearance; keep: true leaves it at the last frame, else every joint is put back; placements: true adds every part's place per frame; path writes the frames as JSON; limit: frames listed, 40) | list (the default) | delete. Play poses each joint in turn (asm_pose, so only revolute, slider and cylindrical joints) and answers frames, frameList [{ frame, poses, overlaps }], clashFrames and a verdict. Frames × pairs of parts is the cost: keep steps low on big assemblies.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "action": {
     "type": "string",
     "enum": [
      "save",
      "play",
      "list",
      "delete"
     ]
    },
    "name": {
     "type": "string"
    },
    "keys": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "steps": {
     "type": "integer"
    },
    "clearance": {
     "type": "number"
    },
    "keep": {
     "type": "boolean"
    },
    "placements": {
     "type": "boolean"
    },
    "path": {
     "type": "string"
    },
    "limit": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "assembly"
 },
 "asm_export": {
  "name": "asm_export",
  "description": "Write the assembly as its solver's own file (OndselSolver .asmt, FreeCAD's Export ASMT): path (relative goes in the session's folder; <assembly>.asmt when left out). Parts, grounded parts and joints as the solver reads them — for other solvers, and for reporting a solve problem. Reply: path, bytes. Changes nothing in the document.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
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
  "group": "assembly"
 },
 "asm_pose": {
  "name": "asm_pose",
  "description": "Move a revolute joint (degrees) or slider / cylindrical one (mm; turn: true turns a cylindrical) and leave it there: to (from the joint's own zero, where its two frames line up — the zero its limits use; angles wrap to -180 … 180), by (from where it is now, read off the parts), or home: true (to 0). The part and those joined beyond it are moved, then the assembly is solved: refused, nothing kept, when the solver moves it back (a closed loop or coupling holds it), when outside the joint's limits, or when parts would overlap (allowOverlap: true keeps it). Not while exploded. Reply: pose, was, unit, moved, parts' placements, solve.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "joint": {
     "type": "string"
    },
    "to": {
     "type": "number"
    },
    "by": {
     "type": "number"
    },
    "home": {
     "type": "boolean"
    },
    "turn": {
     "type": "boolean"
    },
    "allowOverlap": {
     "type": "boolean"
    }
   },
   "required": [
    "joint"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "assembly"
 },
 "asm_limits": {
  "name": "asm_limits",
  "description": "A joint's limits, FreeCAD's own (EnableAngleMin/AngleMin … EnableLengthMax/LengthMax): min and max — degrees for revolute, mm for slider and cylindrical (turn: true for a cylindrical's angle); null clears one; an end left out stays as it is. Counted from the joint's own zero (where its two frames line up), as asm_pose's to. Refused, nothing kept, when min is over max or the assembly no longer solves (the joint stands outside them). asm_sweep sweeps between them when from/to are left out. Reply: limits, unit, solve.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "joint": {
     "type": "string"
    },
    "min": {
     "type": [
      "number",
      "null"
     ]
    },
    "max": {
     "type": [
      "number",
      "null"
     ]
    },
    "turn": {
     "type": "boolean"
    }
   },
   "required": [
    "joint"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "assembly"
 },
 "asm_explode": {
  "name": "asm_explode",
  "description": "Spread an assembly's parts out to see how it goes together: factor (1.6: 60% further from the middle; over 1, at most 10), or along an axis \"x\" | \"y\" | \"z\" | [x,y,z] stacked in the order they sit with gap mm; parts (default every one not grounded). Made as FreeCAD's own Exploded View (Assembly: a move step a part) where this FreeCAD has it (by says which). The parts stay moved and the joints are suppressed until collapse: true puts both back (kept in the file) — do not asm_joint, asm_pose or asm_sweep in between. Reply: exploded { part: [dx, dy, dz] }, view, jointsOff.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "factor": {
     "type": "number"
    },
    "axis": {
     "type": [
      "string",
      "array"
     ]
    },
    "gap": {
     "type": "number"
    },
    "parts": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "collapse": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "assembly"
 },
 "asm_sub": {
  "name": "asm_sub",
  "description": "Put an assembly into another as a sub-assembly (FreeCAD's Assembly::AssemblyLink): sub (the assembly to put in), assembly (the one it goes into), rigid (true, the default: it moves as one part; false: its own joints still move), name. It is linked, not moved: the sub stays an assembly of its own. Reply: as (its label in the parent), type, rigid, solve. asm_check checks its parts where they stand; asm_bom itemises them. asm_joint and asm_ground do not take a sub-assembly as a part yet: place it with object_set (Placement).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "sub": {
     "type": "string"
    },
    "rigid": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "assembly",
    "sub"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "assembly"
 },
 "asm_bom": {
  "name": "asm_bom",
  "description": "The bill of materials: FreeCAD's own BOM object (Assembly::BomObject, a spreadsheet the workbench regenerates on recompute) with Index, Name, Quantity, and Material, Mass (g) and Volume (cm3) filled from the materials recorded (material_set); columns adds more (\"File Name\"; \".Label2\" — a name starting with a dot — reads that property off each part; any other name is a column FreeCAD keeps for values filled in by hand); name. Each call makes a new one. Reply: bom, sheet (the object's name for sheet_read and td_table { sheet }), native, parts [{ name, material, mass, volume }]; a part with no material has no mass.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "assembly": {
     "type": "string",
     "description": "The assembly's label; may be left out when there is one."
    },
    "columns": {
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
  "changes": true,
  "reads": {},
  "group": "assembly"
 }
}
''')
