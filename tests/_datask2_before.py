# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the tools of families/param.py, feature_more.py and
# sketch_more.py now kept as data, at the commit they were converted from
# (tests/test_datask2_data.py's BASE): name, description, inputSchema,
# changes, reads, group. Written by
#   python3 tests/test_datask2_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "param_set": {
  "name": "param_set",
  "description": "Set a named parameter in the Params spreadsheet (made when first needed): name (a letter, then letters, digits, _; not a cell address, a unit such as m, mm, s, N, or e / pi), value (a number with unit mm | deg | \"\", default mm; or an expression over others, \"width / 2\"), note. Everything bound to it recomputes; a value that does not evaluate or breaks a feature is refused with FreeCAD's error and nothing kept. Reply: value, unit, ref (Params.<name>), usedBy, bodies.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    },
    "value": {
     "type": [
      "number",
      "string"
     ]
    },
    "unit": {
     "type": "string"
    },
    "note": {
     "type": "string"
    }
   },
   "required": [
    "name",
    "value"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "param"
 },
 "param_list": {
  "name": "param_list",
  "description": "The parameters: name, value, unit, what they are set to, and which properties use them; varsets: each variable set's variables (name, value, unit, ref, usedBy). Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "param"
 },
 "varset_new": {
  "name": "varset_new",
  "description": "Make a variable set (App::VarSet, FreeCAD 1.0 on): name (its label), properties { size: \"55 mm\" (a length), angle: \"30 deg\", count: 3, ratio: 0.5, on: true, note: \"text\" } as its variables (names: letters, digits, _; not a unit or constant), group (Variables). Expressions read them as <object name>.size (the reply's refAs) — param_bind { target, expression: \"Dims.size\" } takes the label too.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    },
    "properties": {
     "type": "object"
    },
    "group": {
     "type": "string"
    }
   },
   "required": [
    "name"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "param"
 },
 "varset_set": {
  "name": "varset_set",
  "description": "Set or add variables of a variable set: varset (its label; may be left out when there is one), properties { name: value } as varset_new takes them (an existing one keeps its kind: a length takes \"60 mm\", not text). Everything bound to them recomputes; a value that breaks a feature is refused and nothing kept. Reply: variables, usedBy, bodies.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "varset": {
     "type": "string"
    },
    "properties": {
     "type": "object"
    },
    "group": {
     "type": "string"
    }
   },
   "required": [
    "properties"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "param"
 },
 "param_remove": {
  "name": "param_remove",
  "description": "Remove a parameter no property uses (param_list shows usedBy; unbind each with param_bind expression: null first).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    }
   },
   "required": [
    "name"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "param"
 },
 "param_bind": {
  "name": "param_bind",
  "description": "Bind a property or a named, driving sketch constraint to an expression: target \"Pad.Length\" | \"Sketch.width\" (the constraint's name, not its number), expression \"width\" (a parameter by its name), \"Params.width\", \"<Sheet>.<alias>\", \"Dims.size\" (a variable set's, by its label or name) or \"width / 2 + 1\"; null unbinds (the value stays). One that does not evaluate or breaks a feature is refused, nothing kept. A bound value is then changed by param_set, sheet_set or varset_set, not edited directly. Reply: expression as kept, value, bodies.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "target": {
     "type": "string"
    },
    "expression": {
     "type": [
      "string",
      "null"
     ]
    }
   },
   "required": [
    "target",
    "expression"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "param"
 },
 "pd_primitive": {
  "name": "pd_primitive",
  "description": "A PartDesign primitive: kind box | cylinder | sphere | cone | ellipsoid | torus | prism | wedge, size { … } (mm), at [x, y, z] (a box's corner, a round one's base centre) and rotate { axis, angle } from the body's origin; subtractive: true cuts it out (it must overlap the body). Parametric, attached to the body's XY plane. Reply as pd_pad's.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "kind": {
     "type": "string",
     "enum": [
      "box",
      "cylinder",
      "sphere",
      "cone",
      "ellipsoid",
      "torus",
      "prism",
      "wedge"
     ]
    },
    "size": {
     "type": "object",
     "description": "Sizes by kind: box length/width/height; cylinder radius/height/angle; sphere radius; cone radius1/radius2/height; ellipsoid radius1 (z)/radius2 (x)/radius3 (y; 0: as radius2); torus radius1/radius2; prism sides/circumradius/height; wedge xmin…zmax, x2min…z2max (its face at ymax)."
    },
    "subtractive": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "rotate": {
     "type": "object"
    }
   },
   "required": [
    "kind"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_gear": {
  "name": "pd_gear",
  "description": "An involute gear (kind gear: teeth, module, pressureAngle 20, shift, internal with rim mm of wall) or a roller-chain sprocket (kind sprocket: teeth, pitch 9.525 for #35 / 12.7 for #40, roller diameter) as a padded PartDesign feature on the body's XY plane: thickness, bore mm, at. Beside a solid already in the body it is a second solid. Answers the pitch and outside diameters.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "kind": {
     "type": "string",
     "enum": [
      "gear",
      "sprocket"
     ]
    },
    "teeth": {
     "type": "integer"
    },
    "module": {
     "type": "number"
    },
    "pressureAngle": {
     "type": "number"
    },
    "internal": {
     "type": "boolean"
    },
    "rim": {
     "type": "number"
    },
    "shift": {
     "type": "number"
    },
    "highPrecision": {
     "type": "boolean"
    },
    "pitch": {
     "type": "number"
    },
    "roller": {
     "type": "number"
    },
    "thickness": {
     "type": "number"
    },
    "bore": {
     "type": "number"
    },
    "at": {
     "type": "array",
     "items": {}
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
 "pd_helix": {
  "name": "pd_helix",
  "description": "Sweep a closed sketch's profile in a helix about an axis (default the sketch's V_Axis; H_Axis, x | y | z, a datum line, a line's id): two of pitch (mm per turn), height (mm), turns; taper (degrees) or growth (mm per turn, with height and turns: a spiral), leftHanded, reversed; subtractive: true cuts it (a thread, a groove). Keep the profile off the axis and under the pitch; many turns are slow. Reply adds helix.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "profile": {
     "type": "string"
    },
    "axis": {
     "type": [
      "string",
      "integer"
     ]
    },
    "pitch": {
     "type": "number"
    },
    "height": {
     "type": "number"
    },
    "turns": {
     "type": "number"
    },
    "taper": {
     "type": "number"
    },
    "growth": {
     "type": "number"
    },
    "leftHanded": {
     "type": "boolean"
    },
    "reversed": {
     "type": "boolean"
    },
    "subtractive": {
     "type": "boolean"
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
  "group": "feature"
 },
 "pd_multitransform": {
  "name": "pd_multitransform",
  "description": "Repeat features through a chain of steps, each on what the steps before made: steps [{ kind: mirror, plane } | { kind: linear, direction, occurrences, spacing } | { kind: polar, axis, angle, occurrences } | { kind: scale, factor, occurrences }] — a grid is two linear steps; a bolt circle mirrored is polar then mirror. The steps stay in the body (feature_list: stepOf) and go with it.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "features": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "steps": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "features",
    "steps"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_datum": {
  "name": "pd_datum",
  "description": "A datum: kind line (at, direction; along z by default), point (at) or lcs (a coordinate system: at, rotate { axis, angle }) placed from the body's origin; or on: { near: [x,y,z] } a round edge — its axis (line) or centre (point), attached so it follows the model. A line serves by name as an axis or direction. Reply: datum, at, direction.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "kind": {
     "type": "string",
     "enum": [
      "line",
      "point",
      "lcs"
     ]
    },
    "direction": {
     "type": "array",
     "items": {}
    },
    "on": {
     "type": "object"
    },
    "name": {
     "type": "string"
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "rotate": {
     "type": "object"
    }
   },
   "required": [
    "kind"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "pd_binder": {
  "name": "pd_binder",
  "description": "Bring another body's faces (or all of it) into this body as a shape binder (a SubShapeBinder), to sketch on or project from: from (body or feature), faces [{ at, normal } …] on it (none: the whole shape), frozen: true keeps it as it is now. Reply: binder, faces, next.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "from": {
     "type": "string"
    },
    "faces": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "frozen": {
     "type": "boolean"
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
  "group": "feature"
 },
 "pd_boolean": {
  "name": "pd_boolean",
  "description": "A boolean inside a body with other PartDesign bodies: op fuse (default) | cut | common, with [body names]. The tool bodies move inside the boolean, stay editable and are followed; a fuse or cut that changes nothing is refused.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "op": {
     "type": "string",
     "enum": [
      "fuse",
      "cut",
      "common"
     ]
    },
    "with": {
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
    "with"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "feature"
 },
 "sketch_copy": {
  "name": "sketch_copy",
  "description": "Copy geometry in a sketch (move: true moves it instead): geometry [ids] (default every non-construction one), and by [dx, dy] (clone: true keeps copies equal to the originals), rotate { center, angle deg ccw } or scale { center, factor }. by copies the constraints among them too; rotate and scale give plain geometry. Answers new: the copies' ids.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "geometry": {
     "type": "array",
     "items": {
      "type": "integer"
     }
    },
    "by": {
     "type": "array",
     "items": {}
    },
    "rotate": {
     "type": "object"
    },
    "scale": {
     "type": "object"
    },
    "move": {
     "type": "boolean"
    },
    "clone": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_array": {
  "name": "sketch_array",
  "description": "An array of geometry in a sketch: rows (along y), cols (along x) and spacing [dx, dy] mm, the original counted (constrain: true keeps the spacing as constraints; clone: true keeps copies equal), or polar { center, count, angle (default 360) }. Answers new: the ids added.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "geometry": {
     "type": "array",
     "items": {
      "type": "integer"
     }
    },
    "rows": {
     "type": "integer"
    },
    "cols": {
     "type": "integer"
    },
    "spacing": {
     "type": "array",
     "items": {}
    },
    "constrain": {
     "type": "boolean"
    },
    "clone": {
     "type": "boolean"
    },
    "polar": {
     "type": "object"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_extend": {
  "name": "sketch_extend",
  "description": "Lengthen (or shorten) a line or arc of a circle at one end: geo, end 1 | 2 (default 2), by mm (negative shortens; along the arc for an arc), or to: another curve's id a line should reach.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "geo": {
     "type": "integer"
    },
    "end": {
     "type": "integer"
    },
    "by": {
     "type": "number"
    },
    "to": {
     "type": "integer"
    }
   },
   "required": [
    "geo"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_join": {
  "name": "sketch_join",
  "description": "Join two open curves' ends into one B-spline: a [geo, vertex], b [geo, vertex] (vertex 1 | 2, different curves), continuity 0 (corner) or 1 (smooth). It replaces both: ids change; answers bspline, its id.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "a": {
     "type": "array",
     "items": {}
    },
    "b": {
     "type": "array",
     "items": {}
    },
    "continuity": {
     "type": "integer"
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
  "group": "sketch"
 },
 "sketch_carbon": {
  "name": "sketch_carbon",
  "description": "Copy another sketch's geometry and constraints into this one (Sketcher's carbon copy): from, construction: true brings it as construction. Its dimensions stay bound to the source's by expression. Answers new: the ids added.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "from": {
     "type": "string"
    },
    "construction": {
     "type": "boolean"
    }
   },
   "required": [
    "from"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_project": {
  "name": "sketch_project",
  "description": "Bring edges of a binder, datum or another sketch of the same body into this sketch as external geometry: from, edges [\"Edge3\" | { near, kind }] (default all), defining: true makes them part of the profile (FreeCAD 1.1 on). Answers ids (-3 down, in order) for sketch_constrain. The body's own solid: sketch_external.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "from": {
     "type": "string"
    },
    "edges": {
     "type": "array",
     "items": {}
    },
    "defining": {
     "type": "boolean"
    }
   },
   "required": [
    "from"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_to_bspline": {
  "name": "sketch_to_bspline",
  "description": "Convert geometry to B-splines in place (to reshape by poles, or join): geometry [ids]. Geometry ids stay; its constraints other than end-point coincidences are removed.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "geometry": {
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
 },
 "sketch_bspline": {
  "name": "sketch_bspline",
  "description": "Edit a B-spline in a sketch: geo, op degree (by: +1 raises, -1 lowers) | knot (param: insert a knot there, multiplicity; or knot: its index from 1 and by: raise/lower its multiplicity — a corner at 0 continuity). Answers degree, poles, knots, multiplicities.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string"
    },
    "geo": {
     "type": "integer"
    },
    "op": {
     "type": "string",
     "enum": [
      "degree",
      "knot"
     ]
    },
    "by": {
     "type": "integer"
    },
    "param": {
     "type": "number"
    },
    "knot": {
     "type": "integer"
    },
    "multiplicity": {
     "type": "integer"
    }
   },
   "required": [
    "geo",
    "op"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_merge": {
  "name": "sketch_merge",
  "description": "Merge sketches into a new one on the first's plane, geometry and constraints kept (not those to outside geometry): sketches [names]; remove: true deletes the originals. Answers sketch: its label.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketches": {
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
    "sketches"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_mirror": {
  "name": "sketch_mirror",
  "description": "A mirrored copy of a whole sketch as a new sketch on the same plane: about y (left-right) | x (up-down) | origin. Geometry only, no constraints. Answers sketch: its label.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string"
    },
    "about": {
     "type": "string",
     "enum": [
      "x",
      "y",
      "origin"
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
  "group": "sketch"
 },
 "sketch_attach": {
  "name": "sketch_attach",
  "description": "Move a sketch onto another plane (Sketcher's map/reorient): plane XY | XZ | YZ | a datum plane | \"Pad.Face3\", or face { at, normal, feature? }; offset mm along its normal, rotate deg in it, flip. A face is bound to the feature that made it (the earliest in the body that has it, or feature), not the tip; a sketch that sits before that feature is moved after it (refused when a feature is built from it).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string"
    },
    "plane": {
     "type": "string"
    },
    "face": {
     "type": "object"
    },
    "offset": {
     "type": "number"
    },
    "rotate": {
     "type": "number"
    },
    "flip": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sketch"
 },
 "sketch_validate": {
  "name": "sketch_validate",
  "description": "Check a sketch the way Sketcher's Validate does: degenerate geometry, ends that touch with no coincidence, invalid, redundant and conflicting constraints (precision mm); answers found. fix: true repairs what it can (not conflicts; a failed repair leaves the sketch as it was); autoconstrain: true also adds the obvious coincident/horizontal/vertical constraints.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "precision": {
     "type": "number"
    },
    "fix": {
     "type": "boolean"
    },
    "autoconstrain": {
     "type": "boolean"
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
  "group": "sketch"
 }
}
''')
