# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of each converted tool at the base commit (tests/test_datacam_data.py
# checks it against git where the commit is there): name, description, schema, flags, group.
import json

BEFORE = json.loads(r"""
{
 "cam_job": {
  "name": "cam_job",
  "description": "Start a CAM job for a body (FreeCAD works on a clone of it, model): stock { margin mm each side (2), top (1), bottom (0) } round the part; tool { diameter mm, feed and plunge mm/min (600, 200), rpm (12000), number }, the job's first end mill (ask the person; the defaults are gentle). The stock's top is stock.max[2]. Then cam_op.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "tool": {
     "type": "object"
    },
    "stock": {
     "type": "object"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "tool"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "cam"
 },
 "cam_op": {
  "name": "cam_op",
  "description": "Add an operation to the job and compute it. kind: profile (the outline or the faces given; side outside | inside) | pocket (down to the faces given: a pocket's floor) | adaptive (side inside | outside; finish: true a profiling pass) | face | drill (every hole the tool fits when faces are left out) | helix | engrave, vcarve (follow base: letters, a sketch) | slot | deburr | thread | surface, waterline (need OpenCamLib) | pocket3d, tapping, probe, custom (props.Gcode); mill_facing, flute where this FreeCAD has them. faces: [\"Face6\"] or shape_query filters. tool: one of the job's by label. stepDown mm, stepOver %, finalDepth mm (a Z height, not a depth), stockToLeave mm; props { Property: value } for any other (object_get lists them). Answers cutMm, minutes, cutZ [low, high], cutBox, depths, and a warning when it cuts under the stock; refused with nothing kept when it makes no cutting moves. A big adaptive or 3D op can take a minute.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string",
     "description": "The job's label; may be left out when there is one."
    },
    "kind": {
     "type": "string",
     "enum": [
      "profile",
      "pocket",
      "adaptive",
      "face",
      "drill",
      "engrave",
      "helix",
      "slot",
      "deburr",
      "vcarve",
      "thread",
      "surface",
      "waterline",
      "pocket3d",
      "tapping",
      "mill_facing",
      "probe",
      "custom",
      "flute"
     ]
    },
    "faces": {
     "description": "The faces to work: [\"Face6\"] or queries [{ normal: [0,0,1], z: 12 }] as shape_query takes; left out, the whole part (profile: its outline; drill: every hole)."
    },
    "tool": {
     "type": "string"
    },
    "base": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "props": {
     "type": "object"
    },
    "body": {
     "type": "string"
    },
    "side": {
     "type": "string",
     "enum": [
      "outside",
      "inside"
     ]
    },
    "finish": {
     "type": "boolean"
    },
    "stepDown": {
     "type": "number"
    },
    "stepOver": {
     "type": "number"
    },
    "finalDepth": {
     "type": "number"
    },
    "stockToLeave": {
     "type": "number"
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
  "group": "cam"
 },
 "cam_list": {
  "name": "cam_list",
  "description": "The job: stock, tool (its first), ops in running order with type, active, cutMm, minutes, cutZ, and the total minutes (rapids at 3000 mm/min). Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string",
     "description": "The job's label; may be left out when there is one."
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "cam"
 },
 "cam_tool": {
  "name": "cam_tool",
  "description": "Change the job's first tool: diameter mm, feed, plunge mm/min, rpm, number. Every operation is computed again. A tool from cam_tool_add is changed with object_set.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string",
     "description": "The job's label; may be left out when there is one."
    },
    "diameter": {
     "type": "number"
    },
    "feed": {
     "type": "number"
    },
    "plunge": {
     "type": "number"
    },
    "rpm": {
     "type": "number"
    },
    "number": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "cam"
 },
 "cam_tool_add": {
  "name": "cam_tool_add",
  "description": "Add a tool to the job: shape endmill | ballend | bullnose | v-bit | chamfer | drill | thread-mill | radius | dovetail | reamer | tap | slittingsaw | taperedballnose, diameter mm, angle (v-bit, chamfer, a drill's tip), tipDiameter, cornerRadius, length, cuttingLength, flutes, feed, plunge, rpm, number, name. Ask the person which tools they have. Answers tool (its name is what cam_op { tool } takes) and skipped (sizes this shape does not have).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string",
     "description": "The job's label; may be left out when there is one."
    },
    "shape": {
     "type": "string"
    },
    "diameter": {
     "type": "number"
    },
    "angle": {
     "type": "number"
    },
    "tipDiameter": {
     "type": "number"
    },
    "cornerRadius": {
     "type": "number"
    },
    "flutes": {
     "type": "integer"
    },
    "length": {
     "type": "number"
    },
    "cuttingLength": {
     "type": "number"
    },
    "feed": {
     "type": "number"
    },
    "plunge": {
     "type": "number"
    },
    "rpm": {
     "type": "number"
    },
    "number": {
     "type": "integer"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "diameter"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "cam"
 },
 "cam_library": {
  "name": "cam_library",
  "description": "The person's tool set as a JSON file (Agent Link's own, not FreeCAD's .fctl): action export (the job's tools to path; cam-tools.json by default) | import (path's tools into the job; one already there by name is skipped unless replace: true).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string",
     "description": "The job's label; may be left out when there is one."
    },
    "action": {
     "type": "string",
     "enum": [
      "export",
      "import"
     ]
    },
    "path": {
     "type": "string"
    },
    "replace": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {
   "action": [
    null,
    "export"
   ]
  },
  "group": "cam"
 },
 "cam_dressup": {
  "name": "cam_dressup",
  "description": "Dress an operation's path (op; the dressup goes outermost and takes its place in the job). kind: tags (holding tabs on a profile: count, width, height, angle) | dogbone (inside corners: style) | boundary (moves kept inside the stock, or margin mm round the part) | array | ramp, leadinout (where FreeCAD has them without its window). props for the dressup's own. Answers before and after { cutMm, minutes }, tags; refused when it leaves no cutting.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string",
     "description": "The job's label; may be left out when there is one."
    },
    "op": {
     "type": "string"
    },
    "kind": {
     "type": "string"
    },
    "count": {
     "type": "integer"
    },
    "width": {
     "type": "number"
    },
    "height": {
     "type": "number"
    },
    "angle": {
     "type": "number"
    },
    "style": {
     "type": "string"
    },
    "margin": {
     "type": "number"
    },
    "props": {
     "type": "object"
    }
   },
   "required": [
    "op",
    "kind"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "cam"
 },
 "cam_setup": {
  "name": "cam_setup",
  "description": "The job's setup, any of: fixtures [\"G54\" …] (work offsets: the job is posted once in each), coolant none | flood | mist, safeHeight and clearance (mm above the stock's top), order [every op's label once].",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string",
     "description": "The job's label; may be left out when there is one."
    },
    "fixtures": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "coolant": {
     "type": "string"
    },
    "safeHeight": {
     "type": "number"
    },
    "clearance": {
     "type": "number"
    },
    "order": {
     "type": "array",
     "items": {
      "type": "string"
     }
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "cam"
 },
 "cam_edit": {
  "name": "cam_edit",
  "description": "Edit the job's operations. action: active { op, on } (off leaves it out of the G-code) | copy { op, props, name } | comment { text, after } | stop { text, optional, after } (M0, or M1 when optional) | start { op, at [x, y, z] } (left out clears it). Answers op and ops (the running order).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string",
     "description": "The job's label; may be left out when there is one."
    },
    "action": {
     "type": "string",
     "enum": [
      "active",
      "copy",
      "comment",
      "stop",
      "start"
     ]
    },
    "op": {
     "type": "string"
    },
    "on": {
     "type": "boolean"
    },
    "props": {
     "type": "object"
    },
    "text": {
     "type": "string"
    },
    "optional": {
     "type": "boolean"
    },
    "after": {
     "type": "string"
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
    "action"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "cam"
 },
 "cam_remove": {
  "name": "cam_remove",
  "description": "Remove an operation (op) from the job with every dressup stacked on it; naming a dressup removes the whole stack too.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string",
     "description": "The job's label; may be left out when there is one."
    },
    "op": {
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
  "group": "cam"
 },
 "cam_sim": {
  "name": "cam_sim",
  "description": "Simulate the job's active operations on the stock (Agent Link's own 3-axis height map from above, not FreeCAD's simulator): rapids through stock (crashes), cuts into the part (gouges) or under the stock, and what is left over the part. Answers verdict fix | clear, findings, ops, part { gouge, left }, picture (a PNG from above: blue gouged, green right, red left over). resolution mm per cell (a sixth of the smallest tool, about 250000 cells at most by default; finer costs time by its square). Undercuts cannot be seen. Before cam_post.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string",
     "description": "The job's label; may be left out when there is one."
    },
    "resolution": {
     "type": "number"
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
  "group": "cam"
 },
 "cam_post": {
  "name": "cam_post",
  "description": "Write the job's G-code with FreeCAD's post-processor: post grbl (default) | linuxcnc | mach3_mach4 | marlin | smoothie | centroid | generic, to path (<job>.nc in the output folder). Posted as FreeCAD's Post command does: each work offset, a tool change at each new tool (a comment for grbl and marlin), active ops in order; mm (G21), feeds per minute. Answers path, lines, units, tools, fixtures, minutes, warnings (cuts under or far outside the stock). Running it is the person's.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "job": {
     "type": "string",
     "description": "The job's label; may be left out when there is one."
    },
    "post": {
     "type": "string",
     "enum": [
      "grbl",
      "linuxcnc",
      "mach3_mach4",
      "marlin",
      "smoothie",
      "centroid",
      "generic"
     ]
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
  "group": "cam"
 },
 "points_structure": {
  "name": "points_structure",
  "description": "A structured copy of a point cloud (Points::Structured: the points in their order laid out as a grid): points, width (per row), height (rows; count / width when left out). width × height must equal the count, so it suits a cloud still in scan order. The original stays.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "string"
    },
    "width": {
     "type": "integer"
    },
    "height": {
     "type": "integer"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "points",
    "width"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 }
}
""")
