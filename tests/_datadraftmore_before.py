# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of draft_more.py's tools now kept as data, at the commit they
# were converted from (tests/test_datadraftmore_data.py's BASE): name,
# description, inputSchema, changes, reads, group. Written by
#   python3 tests/test_datadraftmore_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "draft_plane": {
  "name": "draft_plane",
  "description": "A saved working plane (Draft's working-plane proxy): at [x,y,z] with normal, or on a flat face (\"Box.Face6\"); rotate degrees about the normal; name. It records the plane (reply: origin, normal, xAxis) and does not switch Draft's working plane. With the window up the 3D view must be the tab in front.",
  "inputSchema": {
   "type": "object",
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
    "face": {
     "type": "string"
    },
    "rotate": {
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
  "group": "draft"
 },
 "draft_style": {
  "name": "draft_style",
  "description": "Draft annotation styles, kept in the document as Draft keeps them: action list | set (name, values { FontSize, FontName, ArrowSize, ArrowType (Dot, Circle, Arrow, Tick, Tick-2, None), Decimals, ShowUnit, UnitOverride, LineWidth, TextColor, LineColor (0xRRGGBBAA numbers), ScaleMultiplier, ExtLines, ExtOvershoot, DimOvershoot, LineSpacing, TextSpacing, ShowLine }) | apply (name, objects: dimensions, labels) | delete. Styles show only in the window: without one, apply only records the name (reply: recorded).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "action": {
     "type": "string",
     "enum": [
      "list",
      "set",
      "apply",
      "delete"
     ]
    },
    "name": {
     "type": "string"
    },
    "values": {
     "type": "object"
    },
    "objects": {
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
  "group": "draft"
 },
 "draft_shape": {
  "name": "draft_shape",
  "description": "A Draft 2D shape (parametric: object_set edits it): kind wire | bspline | bezier (points where given, closed; at and normal do not move these) | rectangle (length along x, height along y, corner at `at`) | circle (radius) | arc (radius, start, end degrees counter-clockwise from x) | ellipse (major, minor: whole axes) | polygon (sides, radius; inscribed false: flats on the radius) | point (at). at and normal place it. A closed shape is a filled face unless face: false. Reply: object, type, length, area, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string"
    },
    "points": {
     "type": "array",
     "items": {}
    },
    "closed": {
     "type": "boolean"
    },
    "length": {
     "type": "number"
    },
    "height": {
     "type": "number"
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
    "inscribed": {
     "type": "boolean"
    },
    "face": {
     "type": "boolean"
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "normal": {
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
  "group": "draft"
 },
 "draft_dimension": {
  "name": "draft_dimension",
  "description": "A Draft dimension in the 3D model (on a drawing: td_dim): kind linear (from, to; or object and vertices [i, j], numbered from 1, following it) | radius / diameter (object, edge: a circle or arc's number from 1) | angular (center, angles [a, b] degrees counter-clockwise, normal); at: a point the dimension line passes through (left out: on the measured line). Reply: measures, unit. With the window up the 3D view must be the tab in front. Looks: draft_style.",
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
    "object": {
     "type": "string"
    },
    "vertices": {
     "type": "array",
     "items": {}
    },
    "edge": {
     "type": "integer"
    },
    "center": {
     "type": "array",
     "items": {}
    },
    "angles": {
     "type": "array",
     "items": {}
    },
    "normal": {
     "type": "array",
     "items": {}
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
  "group": "draft"
 },
 "draft_label": {
  "name": "draft_label",
  "description": "A Draft label: a leader from target [x,y,z] to text at [x,y,z]; show custom (text, \\n for lines) | name | area | length | position | material | tag of object (\"Body\", or \"Body.Face6\" / \"Body.Edge3\" for one element), which it follows. Reply: text.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "target": {
     "type": "array",
     "items": {}
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "object": {
     "type": "string"
    },
    "show": {
     "type": "string"
    },
    "text": {
     "type": "string"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "target"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "draft"
 },
 "draft_link_array": {
  "name": "draft_link_array",
  "description": "A Draft array of any object, parametric (the copies follow it; the original is hidden in the window): kind ortho (count [nx,ny,nz] including the original, spacing [dx,dy,dz] from one copy to the next) | polar (count, angle, center; about z) | circular (rings counting the original, ringSpacing, tangentSpacing, symmetry) | path (path, count, align) | points (points: an object whose points place the copies); link: false makes real shapes, not links. Reply: count, of, box. object_set changes it (NumberX, IntervalX, NumberPolar, Angle …).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "object": {
     "type": "string"
    },
    "kind": {
     "type": "string"
    },
    "count": {},
    "spacing": {
     "type": "array",
     "items": {}
    },
    "angle": {
     "type": "number"
    },
    "center": {
     "type": "array",
     "items": {}
    },
    "rings": {
     "type": "integer"
    },
    "ringSpacing": {
     "type": "number"
    },
    "tangentSpacing": {
     "type": "number"
    },
    "symmetry": {
     "type": "integer"
    },
    "path": {
     "type": "string"
    },
    "align": {
     "type": "boolean"
    },
    "points": {
     "type": "string"
    },
    "link": {
     "type": "boolean"
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
  "group": "draft"
 },
 "draft_clone": {
  "name": "draft_clone",
  "description": "A Draft clone: a copy that follows the original (it starts on top of it); scale (a factor or [x,y,z]), move [x,y,z]. Reply: object, of, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "object": {
     "type": "string"
    },
    "scale": {},
    "move": {
     "type": "array",
     "items": {}
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
  "group": "draft"
 },
 "draft_modify": {
  "name": "draft_modify",
  "description": "Draft's modify tools on objects: op move (by) | rotate (angle, center, axis) | scale (factor, center) | mirror (from, to: the mirror line in XY; a new Mirror object) | offset (one object; by: a vector from its first edge) | upgrade (edges → wire → face → solid, one stage a call) | downgrade | join (Draft wires sharing end points) | fillet (two single edges that meet: radius, chamfer) | split (a Draft wire on segment edge n, from 1, at point at or its middle) | stretch (the points inside box [[min], [max]] moved by) | extend (length mm at end start | end; negative trims) | to_bspline | to_wire; copy: true leaves the originals (move, rotate, scale, offset); delete: false keeps upgrade / downgrade inputs. Reply: op, each result's object, type, length, area, box. guide_read draft has each op's rules.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "op": {
     "type": "string"
    },
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "by": {
     "type": "array",
     "items": {}
    },
    "angle": {
     "type": "number"
    },
    "center": {
     "type": "array",
     "items": {}
    },
    "axis": {
     "type": "array",
     "items": {}
    },
    "factor": {},
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
    "chamfer": {
     "type": "boolean"
    },
    "copy": {
     "type": "boolean"
    },
    "delete": {
     "type": "boolean"
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "edge": {
     "type": "integer"
    },
    "box": {
     "type": "array",
     "items": {}
    },
    "length": {
     "type": "number"
    },
    "end": {
     "type": "string",
     "enum": [
      "start",
      "end"
     ]
    }
   },
   "required": [
    "op",
    "objects"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "draft"
 },
 "draft_layer": {
  "name": "draft_layer",
  "description": "A Draft layer (made if new) and objects put on it: name, objects (each leaves its old layer), lineWidth pixels. Without the window only the grouping happens. Reply: layer, made, objects.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    },
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "lineWidth": {
     "type": "number"
    }
   },
   "required": [
    "name"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "draft"
 },
 "draft_hatch": {
  "name": "draft_hatch",
  "description": "Hatch an object's flat faces with a PAT pattern, as lines in the model (a Hatch object that follows it): object, pattern (default Diagonal4; FreeCAD's FCPAT.pat lists them, or file: your own .pat), scale (1: the pattern's own mm spacing), rotation degrees. Reply: pattern, file, length; warning when no lines were drawn. A wrong pattern name is refused with the names.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "object": {
     "type": "string"
    },
    "pattern": {
     "type": "string"
    },
    "file": {
     "type": "string"
    },
    "scale": {
     "type": "number"
    },
    "rotation": {
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
  "group": "draft"
 },
 "draft_from_sketch": {
  "name": "draft_from_sketch",
  "description": "Sketches or shapes made Draft objects (Draft's draftify): objects; straight runs become Draft wires, a lone circle or arc a Draft circle, runs with curves stay plain shapes. block: true compounds the results; delete: true removes the originals.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "block": {
     "type": "boolean"
    },
    "delete": {
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
  "group": "draft"
 },
 "draft_2d_view": {
  "name": "draft_2d_view",
  "description": "A 2D view of a body projected along direction (Draft's Shape2DView, parametric; default from above, laid on XY): hidden: true adds hidden lines. section: true (cut faces only) needs object to be a BIM section plane (bim_section); for a body use part_section. Reply: object, length, box; warning when empty.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "object": {
     "type": "string"
    },
    "direction": {
     "type": "array",
     "items": {}
    },
    "hidden": {
     "type": "boolean"
    },
    "section": {
     "type": "boolean"
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
  "group": "draft"
 },
 "draft_facebinder": {
  "name": "draft_facebinder",
  "description": "A facebinder: faces [\"Body.Face6\" …] as a surface that follows them; extrusion mm makes it a skin, offset moves it off. Reply: object, area, volume, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "faces": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "extrusion": {
     "type": "number"
    },
    "offset": {
     "type": "number"
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
  "group": "draft"
 }
}
''')
