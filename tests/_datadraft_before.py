# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the Draft tools (and draft.py's surface tools) now kept as data, at the commit they
# were converted from (tests/test_datadraft_data.py's BASE): name,
# description, inputSchema, changes, reads, group. Written by
#   python3 tests/test_datadraft_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "surface_fill": {
  "name": "surface_fill",
  "description": "A plain surface filled across one closed boundary (Part's filled face; not parametric): edges (\"Body.Edge3\" …) or a sketch or wire whose outline bounds it, bent as smoothly as the edges allow; thickness mm makes it a solid (negative: the other side). Edges that leave a gap or form more than one loop are refused. Reply: object, area, solid, volume.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "edges": {
     "type": "array",
     "items": {}
    },
    "body": {
     "type": "string"
    },
    "thickness": {
     "type": "number"
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
  "group": "draft"
 },
 "surface_loft": {
  "name": "surface_loft",
  "description": "A plain surface through curves in order (Part's loft; not parametric): curves, each an edge (\"Body.Edge3\"), a sketch, or { points: [[x,y,z] …], closed } for a smooth curve through them; all open (a sheet) or all closed (a tube), running the same way. ruled: straight between; closed: true joins the last back to the first (3 or more); thickness mm makes it a solid (side out, in or both). Reply: object, area, solid, volume, size, through; warnings under 0.8 mm or when the solid is not valid.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "curves": {
     "type": "array",
     "items": {}
    },
    "body": {
     "type": "string"
    },
    "ruled": {
     "type": "boolean"
    },
    "closed": {
     "type": "boolean"
    },
    "thickness": {
     "type": "number"
    },
    "side": {
     "type": "string",
     "enum": [
      "out",
      "in",
      "both"
     ]
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "curves"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "draft"
 },
 "surface_points": {
  "name": "surface_points",
  "description": "A plain smooth surface through a grid of points, row by row (rows: [[[x,y,z] …] …], two or more rows of one length): through every point, or with tolerance mm within that of them for a smoother one. thickness and side make it a solid. Reply: grid, fitted, farthestPoint mm (how far the worst point is off it), area.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "rows": {
     "type": "array",
     "items": {}
    },
    "tolerance": {
     "type": "number"
    },
    "thickness": {
     "type": "number"
    },
    "side": {
     "type": "string",
     "enum": [
      "out",
      "in",
      "both"
     ]
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "rows"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "draft"
 },
 "surface_thicken": {
  "name": "surface_thicken",
  "description": "Make a surface a solid: surface an object (\"Surface\") or one face (\"Body.Face3\"), thickness mm over 0, side out (along its normal), in, or both (half each way). A new plain object; it cannot be thicker inward than its tightest bend. Reply: object, solid, volume, area, size; warnings under two printed lines (0.8 mm) or when the solid is not valid.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "surface": {
     "type": "string"
    },
    "body": {
     "type": "string"
    },
    "thickness": {
     "type": "number"
    },
    "side": {
     "type": "string",
     "enum": [
      "out",
      "in",
      "both"
     ]
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "surface",
    "thickness"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "draft"
 },
 "draft_text": {
  "name": "draft_text",
  "description": "Letter a flat face of a body: text from a TrueType font (font: a name or .ttf path; draft_fonts lists them), size mm (the font's size: capitals come out near 0.7 of it), depth mm, mode emboss (raised, default) or engrave (cut in), face (default the largest facing up), centred on it or at [x,y,z], rotate degrees, tracking. The body becomes the lettered solid (one boolean, not parametric; slow for long text on a detailed body). Reply: volumeChange, box (the real extent), font; warning when letters run off the face, printNote when strokes are under a printed line.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "text": {
     "type": "string"
    },
    "face": {
     "description": "The face: \"Face6\", or a query { normal, near, area … } as shape_query takes (the largest match, or the nearest with near). Default: the largest face facing up."
    },
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "size": {
     "type": "number"
    },
    "depth": {
     "type": "number"
    },
    "mode": {
     "type": "string",
     "enum": [
      "emboss",
      "engrave"
     ]
    },
    "font": {
     "type": "string"
    },
    "rotate": {
     "type": "number"
    },
    "tracking": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "text"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "draft"
 },
 "draft_outline": {
  "name": "draft_outline",
  "description": "Bring a logo or shape from an SVG or DXF file (closed outlines; holes kept; text must be paths): scaled to width or height mm (neither: the file's own size), then mode emboss (raised on a body's face, the largest facing up by default), engrave (cut in), or extrude (a part of its own, depth mm thick; the default without body). face, at, rotate as draft_text; mirror flips it. Reply: outlines, size, scale, openCurvesLeftOut, volume or volumeChange, printNote when strokes are under a printed line.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "body": {
     "type": "string"
    },
    "face": {
     "description": "The face: \"Face6\", or a query { normal, near, area … } as shape_query takes (the largest match, or the nearest with near). Default: the largest face facing up."
    },
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "width": {
     "type": "number"
    },
    "height": {
     "type": "number"
    },
    "depth": {
     "type": "number"
    },
    "mode": {
     "type": "string",
     "enum": [
      "emboss",
      "engrave",
      "extrude"
     ]
    },
    "rotate": {
     "type": "number"
    },
    "mirror": {
     "type": "boolean"
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
  "group": "draft"
 },
 "draft_array": {
  "name": "draft_array",
  "description": "Copies of a whole body as plain solids: kind grid (count [nx, ny, nz]; gap mm between them, 2, or spacing [dx, dy, dz] from one to the next), polar (count round center about axis; angle degrees, 360, a smaller one spans first to last), or path (count along a curve: an edge, a sketch or { points }; align turns each with it). Joined into the body by default (one boolean: slow past a few dozen detailed copies); separate: true makes each its own body. Reply: copies, solids, volume, size. Copies that follow the original: draft_link_array; inside one part: pd_linear_pattern, pd_polar_pattern.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "kind": {
     "type": "string",
     "enum": [
      "grid",
      "polar",
      "path"
     ]
    },
    "count": {},
    "gap": {
     "type": "number"
    },
    "spacing": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "angle": {
     "type": "number"
    },
    "center": {
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
    "path": {},
    "bodyOfPath": {
     "type": "string"
    },
    "align": {
     "type": "boolean"
    },
    "separate": {
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
  "group": "draft"
 },
 "draft_fonts": {
  "name": "draft_fonts",
  "description": "The TrueType fonts on this computer by file name (name filters; limit, 25; paths: true adds their paths), and the one draft_text takes by default. Reply: fonts, found, default.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    },
    "limit": {
     "type": "integer"
    },
    "paths": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "draft"
 }
}
''')
