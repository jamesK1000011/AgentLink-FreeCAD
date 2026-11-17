# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of each converted tool at the base commit (tests/test_datatd_data.py
# checks it against git where the commit is there): name, description, schema, flags, group.
import json

BEFORE = json.loads(r"""
{
 "td_page": {
  "name": "td_page",
  "description": "TechDraw pages: action new { paper A4|A3|A2|A1|A0|Letter|ANSIB…, orientation landscape|portrait, standard iso|asme, blank, template (an SVG path, or a name from templates), projection first|third, scale (the page's: views take it unless given their own), name } on the build's own templates, sample title-block texts cleared; list; read { page } (views and title-block fields); templates. Page positions are mm from the paper's bottom-left corner, y up.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "action": {
     "type": "string",
     "enum": [
      "new",
      "list",
      "read",
      "templates"
     ]
    },
    "page": {
     "type": "string"
    },
    "paper": {
     "type": "string"
    },
    "orientation": {
     "type": "string"
    },
    "standard": {
     "type": "string"
    },
    "blank": {
     "type": "boolean"
    },
    "template": {
     "type": "string"
    },
    "projection": {
     "type": "string"
    },
    "scale": {
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
  "group": "techdraw"
 },
 "td_title": {
  "name": "td_title",
  "description": "The title block: fields { name: value } by the template's own field names, which differ by template (no fields: lists them; an unknown name is refused with the list); preset \"mine\" fills from a saved one, with save: true saves the page's as it (not its title, sheet number, scale or date, unless given in fields), delete: true removes it; import / export a presets file (JSON). Ask the person for names and numbers.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "page": {
     "type": "string"
    },
    "fields": {
     "type": "object"
    },
    "preset": {
     "type": "string"
    },
    "save": {
     "type": "boolean"
    },
    "delete": {
     "type": "boolean"
    },
    "import": {
     "type": "string"
    },
    "export": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_view": {
  "name": "td_view",
  "description": "Put a view of bodies on a page: bodies (all when left out), direction front|top|right|left|rear|bottom|iso or [x, y, z] (part toward viewer), scale (left out: the page's), at [x, y] page mm (its centre, bottom-left origin), hidden (dashed hidden lines), name. Answers its label (what other td_ tools take), size on the paper and edges — 0 edges: the bodies are empty or hidden. Its lines are waited for (up to 30 s in the window).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "page": {
     "type": "string"
    },
    "bodies": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "direction": {
     "type": [
      "string",
      "array"
     ]
    },
    "scale": {
     "type": "number"
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "hidden": {
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
  "group": "techdraw"
 },
 "td_centermarks": {
  "name": "td_centermarks",
  "description": "Centre marks (thin chain crosses) on the holes and round edges of views (all part views when left out): extend mm past each circle (2); on: false takes them off. Whole circles and arcs past a half turn only. Drawn by td_export, not in the window.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "views": {},
    "extend": {
     "type": "number"
    },
    "on": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_hatch": {
  "name": "td_hatch",
  "description": "Hatch faces of the part in a view (thin lines spacing mm apart at angle degrees; a section's cut is hatched by itself): view, faces [\"Face6\" …] (the part's own, from shape_query) — none takes it off. Drawn by td_export, not in the window; a face seen edge-on is warned of.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "faces": {},
    "spacing": {
     "type": "number"
    },
    "angle": {
     "type": "number"
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
 "td_weld": {
  "name": "td_weld",
  "description": "A weld symbol on a leader from a feature of a view (on, as td_dim takes it; at the leader's end on the page), drawn by td_export (the window shows the leader only): kind fillet, square, v, bevel, u, j, plug, spot, seam, flare-v, flare-bevel, backing, surfacing, size (left of it), length (right: \"50\" or \"50-100\" for pitch), side arrow | other | both, allAround, field (a site weld), tail (process, \"GMAW\").",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "on": {},
    "at": {
     "type": "array",
     "items": {}
    },
    "kind": {
     "type": "string",
     "enum": [
      "fillet",
      "square",
      "v",
      "bevel",
      "u",
      "j",
      "plug",
      "spot",
      "seam",
      "flare-v",
      "flare-bevel",
      "backing",
      "surfacing"
     ]
    },
    "size": {},
    "length": {},
    "side": {
     "type": "string",
     "enum": [
      "arrow",
      "other",
      "both"
     ]
    },
    "allAround": {
     "type": "boolean"
    },
    "field": {
     "type": "boolean"
    },
    "tail": {
     "type": "string"
    },
    "textSize": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "view",
    "kind"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_bim": {
  "name": "td_bim",
  "description": "A BIM section plane drawn on a page (a building plan or section): section (from bim_section), scale (0.02 = 1:50), at, render Wireframe | Solid, fill (cut faces hatched), spaces, hidden. Warns when it drew nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "page": {
     "type": "string"
    },
    "section": {
     "type": "string"
    },
    "scale": {
     "type": "number"
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "render": {
     "type": "string"
    },
    "fill": {
     "type": "boolean"
    },
    "spaces": {
     "type": "boolean"
    },
    "hidden": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "section"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_projection": {
  "name": "td_projection",
  "description": "A projection group (views kept aligned): views [front, top, right, left, rear, bottom, iso, isoLeft …] (front always; default front, top, right), projection first|third (default the page's), front (which way is front: a direction), bodies, scale, at. Answers items: each one's label (Front, Top, FrontTopRight …) is the view td_dim and td_section take.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "page": {
     "type": "string"
    },
    "bodies": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "views": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "projection": {
     "type": "string"
    },
    "front": {
     "type": [
      "string",
      "array"
     ]
    },
    "scale": {
     "type": "number"
    },
    "at": {
     "type": "array",
     "items": {}
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_section": {
  "name": "td_section",
  "description": "A section view cut from a view: normal of the cut plane, toward who looks at the section (\"x\" | \"-y\" | [x,y,z]; it lies across the base view, not along its direction), through [x, y, z] a point of the plane (default the part's middle), symbol (A …), at, hatch false. Answers its label (Section A) and edges; 0 edges: the plane misses the part.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "normal": {
     "type": [
      "string",
      "array"
     ]
    },
    "through": {
     "type": "array",
     "items": {}
    },
    "symbol": {
     "type": "string"
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "hatch": {
     "type": "boolean"
    }
   },
   "required": [
    "view",
    "normal"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_detail": {
  "name": "td_detail",
  "description": "A detail view: a circle of radius (mm on the part) around center [x, y, z] (a point on the part) or anchor [x, y] (td_geometry's view mm), drawn larger (scale, default twice the base), symbol (B …), at. 0 edges in the answer: the circle misses the part.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "center": {
     "type": "array",
     "items": {}
    },
    "anchor": {
     "type": "array",
     "items": {}
    },
    "radius": {
     "type": "number"
    },
    "scale": {
     "type": "number"
    },
    "symbol": {
     "type": "string"
    },
    "at": {
     "type": "array",
     "items": {}
    }
   },
   "required": [
    "view",
    "radius"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_geometry": {
  "name": "td_geometry",
  "description": "A view's geometry, to dimension against: kind edges | circles (each marked circle or arc) | lines | vertices, each with its ref (Edge3, Vertex5: zero-based), kind, ends or centre and diameter (mm on the part); limit (120). The numbers move when the part changes: read them just before use, or name geometry by the part (byPoint). Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "kind": {
     "type": "string"
    },
    "limit": {
     "type": "integer"
    }
   },
   "required": [
    "view"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "techdraw"
 },
 "td_dim": {
  "name": "td_dim",
  "description": "A dimension on a view, measured by TechDraw so it follows the part: type distance | horizontal | vertical (two points or one straight edge) | radius | diameter (one round edge) | angle (two straight edges); refs [\"Vertex1\", \"Vertex4\"] or by the part, which holds when numbers move: { point: [x,y,z] }, { circle: { diameter, near } }, { center: { diameter, near } }, { edge: { through: [p, q] } }. A diameter by { circle } takes whole circles only: an arc of that size (a slot's end) is refused — use radius. at [dx, dy] (its text from the view's centre, page mm); tolerance at once: plus/minus, fit \"H7\", basic, label, format \"%.1f\". Lengths in an iso view read foreshortened (td_dim_special axo_length). Answers dimension (its name), measured, text; unmeasurable is refused, nothing kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "type": {
     "type": "string"
    },
    "refs": {
     "type": "array",
     "items": {
      "type": [
       "string",
       "object"
      ]
     }
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "plus": {
     "type": "number"
    },
    "minus": {
     "type": "number"
    },
    "fit": {
     "type": "string"
    },
    "basic": {
     "type": "boolean"
    },
    "label": {
     "type": "string"
    },
    "format": {
     "type": "string"
    }
   },
   "required": [
    "view",
    "refs"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_dimset": {
  "name": "td_dimset",
  "description": "Several dimensions along one direction at once: style chain (each point to the next) or baseline (each from the first, stacked lanes); type horizontal | vertical; refs three or more points in order (as td_dim takes them); offset mm off the view (10), spacing between lanes (7), format. Answers each dimension and overall.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "refs": {
     "type": "array",
     "items": {}
    },
    "type": {
     "type": "string",
     "enum": [
      "horizontal",
      "vertical"
     ]
    },
    "style": {
     "type": "string",
     "enum": [
      "chain",
      "baseline"
     ]
    },
    "offset": {
     "type": "number"
    },
    "spacing": {
     "type": "number"
    },
    "format": {
     "type": "string"
    }
   },
   "required": [
    "view",
    "refs"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_tolerance": {
  "name": "td_tolerance",
  "description": "Tolerance a dimension (by its name or label): plus/minus (mm; equal = ±), fit \"H7\" | \"g6\" (ISO 286 deviations for its measured size), basic: true (a boxed theoretically exact size, for GD&T), label (text instead of the value), format \"%.2f\"; clear: true first resets it.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "dimension": {
     "type": "string"
    },
    "plus": {
     "type": "number"
    },
    "minus": {
     "type": "number"
    },
    "fit": {
     "type": "string"
    },
    "basic": {
     "type": "boolean"
    },
    "label": {
     "type": "string"
    },
    "format": {
     "type": "string"
    },
    "clear": {
     "type": "boolean"
    }
   },
   "required": [
    "dimension"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_gdt": {
  "name": "td_gdt",
  "description": "A feature control frame (ISO 1101 / ASME Y14.5): frame [{ characteristic (flatness, straightness, circularity, cylindricity, profile_line, profile_surface, parallelism, perpendicularity, angularity, position, concentricity, symmetry, circular_runout, total_runout), tolerance mm, diameter (⌀ zone), modifier M|L|…, datums [\"A\", \"B|M\"] }] (rows stack: composite); with a leader to on (a view ref) or under dimension; at. Form tolerances take no datum, orientation and runout need one (refused, saying which). Answers reads: the frame in words.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "on": {
     "type": [
      "string",
      "object"
     ]
    },
    "dimension": {
     "type": "string"
    },
    "frame": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "characteristic": {
     "type": "string"
    },
    "tolerance": {
     "type": "number"
    },
    "diameter": {
     "type": "boolean"
    },
    "modifier": {
     "type": "string"
    },
    "datums": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "height": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_datum": {
  "name": "td_datum",
  "description": "A datum feature symbol: view, letter, on the feature (\"Edge3\" or { edge: { through } }, { point }), at. The triangle stands on the feature, the letter outward.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "letter": {
     "type": "string"
    },
    "on": {
     "type": [
      "string",
      "object"
     ]
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "height": {
     "type": "number"
    }
   },
   "required": [
    "view",
    "letter",
    "on"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_note": {
  "name": "td_note",
  "description": "A note on the page: text (\\n splits lines), size (mm, 5), at [x, y] page mm. td_leader points one at a feature.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "page": {
     "type": "string"
    },
    "text": {
     "type": "string"
    },
    "size": {
     "type": "number"
    },
    "at": {
     "type": "array",
     "items": {}
    }
   },
   "required": [
    "text"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_balloon": {
  "name": "td_balloon",
  "description": "A balloon pointing at a feature of a view: view, on (a ref as td_dim takes), text (default the page's next number), at [dx, dy] from the view's centre.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "on": {
     "type": [
      "string",
      "object"
     ]
    },
    "text": {
     "type": "string"
    },
    "at": {
     "type": "array",
     "items": {}
    }
   },
   "required": [
    "view",
    "on"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_table": {
  "name": "td_table",
  "description": "A spreadsheet's cells as a table on the page (a parts list from asm_bom, a revision table): sheet, range (default its used cells), size, at. It follows the sheet; an empty sheet is refused.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "page": {
     "type": "string"
    },
    "sheet": {
     "type": "string"
    },
    "range": {
     "type": "string"
    },
    "size": {
     "type": "number"
    },
    "at": {
     "type": "array",
     "items": {}
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_section_position": {
  "name": "td_section_position",
  "description": "Line a section view up with its base view: straight across when it sits beside it, straight above or below when over it.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "section": {
     "type": "string"
    }
   },
   "required": [
    "section"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_leader": {
  "name": "td_leader",
  "description": "A leader line from a feature of a view (on: a ref as td_dim takes) to at [x, y] page mm, with text (\\n splits lines) at its end — a note pointing at something.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "on": {},
    "at": {
     "type": "array",
     "items": {}
    },
    "text": {
     "type": "string"
    },
    "size": {
     "type": "number"
    }
   },
   "required": [
    "view",
    "on"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_finish": {
  "name": "td_finish",
  "description": "A surface texture symbol (ISO 1302) on a surface's edge in a view (on): ra (\"1.6\" or \"Rz 6.3\"), removal required (machined) | prohibited | any, process (\"ground\"), lay = | perpendicular | crossed | multi | circular | radial | particulate, allowance mm; placed off the part on a leader (at [x, y] page mm to choose where; onSurface: true stands it on the edge itself).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "on": {},
    "ra": {
     "type": "string"
    },
    "removal": {
     "type": "string",
     "enum": [
      "required",
      "prohibited",
      "any"
     ]
    },
    "process": {
     "type": "string"
    },
    "lay": {
     "type": "string"
    },
    "allowance": {
     "type": "string"
    },
    "height": {
     "type": "number"
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "onSurface": {
     "type": "boolean"
    }
   },
   "required": [
    "view",
    "on"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_area": {
  "name": "td_area",
  "description": "Write a face's area on the drawing with a leader to it: face (\"Body.Face3\" on the part), view, unit mm2 | cm2 | m2, decimals, format (\"A = {value} {unit}\"), at. Written as text: it does not follow the part afterwards.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "face": {
     "type": "string"
    },
    "unit": {
     "type": "string",
     "enum": [
      "mm2",
      "cm2",
      "m2"
     ]
    },
    "decimals": {
     "type": "integer"
    },
    "format": {
     "type": "string"
    },
    "size": {
     "type": "number"
    },
    "at": {
     "type": "array",
     "items": {}
    }
   },
   "required": [
    "view",
    "face"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_dim_format": {
  "name": "td_dim_format",
  "description": "Dimension text: dims, then decimals n (0 to 9), more +1/−1, prefix diameter (⌀) | square (□) | count (n×, with count) | any text, removePrefix, format (a whole format, \"%.2f mm\"). A prefix is text only: it does not check what the dimension is on.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "dims": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "decimals": {
     "type": "integer"
    },
    "more": {
     "type": "integer"
    },
    "prefix": {
     "type": "string"
    },
    "count": {
     "type": "integer"
    },
    "removePrefix": {
     "type": "boolean"
    },
    "format": {
     "type": "string"
    }
   },
   "required": [
    "dims"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_dim_special": {
  "name": "td_dim_special",
  "description": "Special dimensions: kind extent_h / extent_v (the view's whole width or height, or refs edges'), chamfer_h / chamfer_v (refs a chamfer's two points: \"2 x45°\"), arc_length (refs one arc: ◠ its length), axo_length (refs [edge, extension-line edge] in an iso view: the true length, not the foreshortened one). at [dx, dy]. Arc and axo lengths are text, re-read from the part when a td_ tool changes the drawing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "kind": {
     "type": "string",
     "enum": [
      "extent_h",
      "extent_v",
      "chamfer_h",
      "chamfer_v",
      "arc_length",
      "axo_length"
     ]
    },
    "refs": {
     "type": "array",
     "items": {}
    },
    "at": {
     "type": "array",
     "items": {}
    },
    "decimals": {
     "type": "integer"
    }
   },
   "required": [
    "view",
    "kind"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_dim_align": {
  "name": "td_dim_align",
  "description": "Line dimensions' texts up: dims (the first sets the line), direction horizontal (all at the first's height) | vertical | oblique (three or more, on the line through the first two).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "dims": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "direction": {
     "type": "string",
     "enum": [
      "horizontal",
      "vertical",
      "oblique"
     ]
    }
   },
   "required": [
    "dims"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 },
 "td_dim_repair": {
  "name": "td_dim_repair",
  "description": "Point a dimension at new references (after the model changed and its numbers moved): refs as td_dim takes them, view to move it to another; the old ones are put back if TechDraw cannot measure the new.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "dimension": {
     "type": "string"
    },
    "view": {
     "type": "string"
    },
    "refs": {
     "type": "array",
     "items": {}
    }
   },
   "required": [
    "dimension",
    "refs"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "techdraw"
 }
}
""")
