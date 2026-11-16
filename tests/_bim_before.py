# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the BIM tools now kept as data, at the commit they
# were converted from (tests/test_bim_data.py's BASE): name, description,
# inputSchema, changes, reads, group. Written by
#   python3 tests/test_bim_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "bim_wall": {
  "name": "bim_wall",
  "description": "A wall along points [[x, y(, z)] …] mm (closed: true joins the last to the first) or a base sketch/wire: width (200), height (3000). align center | left (the line is the wall's left face going from the first point, so the wall lies to its right) | right. Answers length, box, min, volume_m3, base (the line bim_opening measures along).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "array",
     "items": {
      "type": "array",
      "items": {
       "type": "number"
      }
     }
    },
    "closed": {
     "type": "boolean"
    },
    "base": {
     "type": "string"
    },
    "width": {
     "type": "number"
    },
    "height": {
     "type": "number"
    },
    "align": {
     "type": "string",
     "enum": [
      "center",
      "left",
      "right"
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
  "group": "bim"
 },
 "bim_opening": {
  "name": "bim_opening",
  "description": "A window or door in a wall, its opening cut through: kind window | door, width, height, at (the opening's left edge, mm along the wall's line from its first point; one straight stretch only), sill (900 window, 0 door), frame (50), depth (100). Whatever preset says, it is a plain frame round a pane or a door panel. Answers wallCut_m3 (0 with a warning: nothing was cut), opening (the cutting box), box, min.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "wall": {
     "type": "string"
    },
    "kind": {
     "type": "string",
     "enum": [
      "window",
      "door"
     ]
    },
    "preset": {
     "type": "string"
    },
    "width": {
     "type": "number"
    },
    "height": {
     "type": "number"
    },
    "at": {
     "type": "number"
    },
    "sill": {
     "type": "number"
    },
    "frame": {
     "type": "number"
    },
    "depth": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "wall"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim"
 },
 "bim_structure": {
  "name": "bim_structure",
  "description": "Structure, mm: column { at (centre of its foot), width (X), depth (Y), height } | beam { from, to (centre line), width, depth (vertical) } | slab or footing { points (outline) or base (closed sketch/wire), thickness }: a slab rises from its outline, a footing hangs below. Answers box, min, volume_m3.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "column",
      "beam",
      "slab",
      "footing"
     ]
    },
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "from": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "to": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "points": {
     "type": "array",
     "items": {
      "type": "array",
      "items": {
       "type": "number"
      }
     }
    },
    "base": {
     "type": "string"
    },
    "width": {
     "type": "number"
    },
    "depth": {
     "type": "number"
    },
    "height": {
     "type": "number"
    },
    "thickness": {
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
  "group": "bim"
 },
 "bim_profiles": {
  "name": "bim_profiles",
  "description": "FreeCAD's section library (steel HEA/HEB/IPE/UPN/RHS/CHS …, timber): search (part of a name), category, limit (40). Answers profiles [{ name, category, type, dims }]. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "search": {
     "type": "string"
    },
    "category": {
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
  "group": "bim"
 },
 "bim_member": {
  "name": "bim_member",
  "description": "A library section between two points (its centre line): profile (\"HEB200\"; bim_profiles lists them), from, to, rotate degrees about its length, density kg/m³ (7850 steel, 500 timber). Answers length, mass_kg, kgPerM (root radii left out, so a little light).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "profile": {
     "type": "string"
    },
    "from": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "to": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "rotate": {
     "type": "number"
    },
    "density": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "profile",
    "from",
    "to"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim"
 },
 "bim_roof": {
  "name": "bim_roof",
  "description": "A pitched roof over a closed outline of straight edges at the eaves' height (points or base), a pane rising from each edge: angle degrees, one or a list per edge in the outline's order (90: a gable end); run mm from each edge to its ridge (half the outline's depth by default); thickness (150), overhang (300). Either way round works. Answers angles, runs, ridge (height above the eaves), box, volume_m3.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "array",
     "items": {
      "type": "array",
      "items": {
       "type": "number"
      }
     }
    },
    "base": {
     "type": "string"
    },
    "angle": {},
    "run": {},
    "thickness": {
     "type": "number"
    },
    "overhang": {
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
  "group": "bim"
 },
 "bim_stairs": {
  "name": "bim_stairs",
  "description": "A straight flight, mm: at (the foot, on its left side going up), direction [x, y], length (run, 4500), width (1000), height (3000), steps (risers; height / 175 by default). Answers riser, going, blondel (2 risers + going; 600–650 is comfortable). FreeCAD 1.1 may add Railing objects.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "direction": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "length": {
     "type": "number"
    },
    "width": {
     "type": "number"
    },
    "height": {
     "type": "number"
    },
    "steps": {
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
  "group": "bim"
 },
 "bim_space": {
  "name": "bim_space",
  "description": "A room from its floor outline (points, height 2600) or a base solid. use: one of FreeCAD's space types (Room, Office, Restrooms, Corridor / Transition …; a wrong one is refused with near names); a free name goes in name. Answers area_m2, use, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "array",
     "items": {
      "type": "array",
      "items": {
       "type": "number"
      }
     }
    },
    "base": {
     "type": "string"
    },
    "height": {
     "type": "number"
    },
    "use": {
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
  "group": "bim"
 },
 "bim_building": {
  "name": "bim_building",
  "description": "A building holding levels (labels from bim_level; make them first), on a site too (site: false for none; siteName). Answers levels, site.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "levels": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "site": {
     "type": "boolean"
    },
    "siteName": {
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
  "group": "bim"
 },
 "bim_curtain_wall": {
  "name": "bim_curtain_wall",
  "description": "A curtain wall along points, height mm (3000): a mullion about every vertical / horizontal mm (1500; each straight stretch gets the same count), mullion width (50) and depth (100), glass thickness (20). Answers length, stretches, set (what FreeCAD took).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "array",
     "items": {
      "type": "array",
      "items": {
       "type": "number"
      }
     }
    },
    "height": {
     "type": "number"
    },
    "vertical": {
     "type": "number"
    },
    "horizontal": {
     "type": "number"
    },
    "mullion": {
     "type": "number"
    },
    "depth": {
     "type": "number"
    },
    "glass": {
     "type": "number"
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
  "group": "bim"
 },
 "bim_rebar": {
  "name": "bim_rebar",
  "description": "Straight bars in a structure, laid out in its bounding box: along x | y | z (the bars' direction), layer bottom | top, diameter (12), cover (30), spacing mm (never wider than asked) or amount (4). Answers made (FreeCAD's rebar, or plain bars), bars, spacing, totalLength_m, mass_kg.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "structure": {
     "type": "string"
    },
    "along": {
     "type": "string",
     "enum": [
      "x",
      "y",
      "z"
     ]
    },
    "layer": {
     "type": "string",
     "enum": [
      "bottom",
      "top"
     ]
    },
    "diameter": {
     "type": "number"
    },
    "cover": {
     "type": "number"
    },
    "spacing": {
     "type": "number"
    },
    "amount": {
     "type": "integer"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "structure"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim"
 },
 "bim_panel": {
  "name": "bim_panel",
  "description": "A panel (sheet material), mm: an outline (points, flat) or length (1000) × width (500) centred on at; thickness (18). Answers box, volume_m3. bim_panel_out lays panels out for cutting.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "array",
     "items": {
      "type": "array",
      "items": {
       "type": "number"
      }
     }
    },
    "length": {
     "type": "number"
    },
    "width": {
     "type": "number"
    },
    "thickness": {
     "type": "number"
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
  "group": "bim"
 },
 "bim_grid": {
  "name": "bim_grid",
  "description": "Grid lines from the origin: spacing mm (one number with count lines, or a list of gaps) for both ways, or xSpacing (lines at x = 0, gap …, running along Y) and ySpacing each; length of the lines (10000). Answers axes (\"Grid X\", \"Grid Y\") and lines (where each stands).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "spacing": {},
    "xSpacing": {},
    "ySpacing": {},
    "count": {
     "type": "integer"
    },
    "length": {
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
  "group": "bim"
 },
 "bim_section": {
  "name": "bim_section",
  "description": "A section plane through objects (every BIM object not in a level when left out): at ([0, 0, 1200]), normal ([0, 0, 1]: a plan cut). It draws nothing itself: td_bim puts it on a page; export { section: z } writes a plan cut as DXF/SVG.",
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
    "normal": {
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
  "group": "bim"
 },
 "bim_material": {
  "name": "bim_material",
  "description": "A BIM material by name (made if new): density kg/m³ (what bim_quantities weighs with), description, color (\"#rrggbb\" or \"r, g, b\" 0 to 1); put on objects (BIM components). Answers material, data, on.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    },
    "density": {
     "type": "number"
    },
    "description": {
     "type": "string"
    },
    "color": {
     "type": "string"
    },
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    }
   },
   "required": [
    "name"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim"
 },
 "bim_schedule": {
  "name": "bim_schedule",
  "description": "Quantities read off the model (Agent Link's own, not an Arch schedule object): walls (length, height, width, area, volume), windows and doors, columns, beams, slabs, footings, roofs, stairs, rebar, spaces, as rows with totals by kind. sheet: true (or a name) also writes a spreadsheet (a change).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sheet": {}
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {
   "sheet": [
    null,
    false,
    ""
   ]
  },
  "group": "bim"
 },
 "bim_export": {
  "name": "bim_export",
  "description": "Write IFC (path, .ifc added; the output folder when relative): the site or building with all it holds, or objects. IFC lengths are metres. Answers path, bytes, schema, readBack (count by IFC class, read from the file). Without IfcOpenShell: refused 'unavailable' with the install step.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
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
  "group": "bim"
 },
 "bim_import": {
  "name": "bim_import",
  "description": "Read an IFC file (path) into the document as FreeCAD objects. Answers objects, byType, read (which reader). Thousands of elements can outlast the call; to edit a file in place, ifc_open instead. Needs IfcOpenShell.",
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
  "changes": true,
  "reads": {},
  "group": "bim"
 },
 "bim_frame": {
  "name": "bim_frame",
  "description": "A library section (profile; bim_profiles lists them) swept along a path (a wire or sketch by label) or points: portal frames, purlins, handrails. rotate degrees about the path; align: false keeps the section as drawn. Answers pathLength_mm, volume_m3, mass_kg.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "profile": {
     "type": "string"
    },
    "path": {
     "type": "string"
    },
    "points": {
     "type": "array",
     "items": {
      "type": "array",
      "items": {
       "type": "number"
      }
     }
    },
    "rotate": {
     "type": "number"
    },
    "align": {
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
  "group": "bim"
 },
 "bim_truss": {
  "name": "bim_truss",
  "description": "A truss between from and to, standing up +Z: height (1000; heightStart / heightEnd for a pitched one), strut (chord size, 100), rod (20), panels, pattern pratt | warren | howe, density (7850). Answers span_mm, set (what FreeCAD took), skipped, mass_kg.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "from": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "to": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "height": {
     "type": "number"
    },
    "heightStart": {
     "type": "number"
    },
    "heightEnd": {
     "type": "number"
    },
    "strut": {
     "type": "number"
    },
    "rod": {
     "type": "number"
    },
    "panels": {
     "type": "integer"
    },
    "pattern": {
     "type": "string",
     "enum": [
      "warren",
      "pratt",
      "howe"
     ]
    },
    "density": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "from",
    "to"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim"
 },
 "bim_fence": {
  "name": "bim_fence",
  "description": "A fence along a path (label) or points, mm: height (1200), post (square, 100), spacing (post centre to centre, 2000), panel (thickness, 20). The last panel is cut to fit. Answers pathLength_mm, NumberOfPosts, NumberOfSections, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "points": {
     "type": "array",
     "items": {
      "type": "array",
      "items": {
       "type": "number"
      }
     }
    },
    "height": {
     "type": "number"
    },
    "post": {
     "type": "number"
    },
    "spacing": {
     "type": "number"
    },
    "panel": {
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
  "group": "bim"
 },
 "bim_covering": {
  "name": "bim_covering",
  "description": "Cover a flat face (\"Slab.Face6\") with a finish thickness mm (10): finish tiles (tile [length, width] 300 × 300, joint 3; counted whole and cut) | solid. FreeCAD 1.1 has no covering object: tiles are solids made here (a boolean each, so thousands are slow; refused past 20000) and pattern / hatch become solid. Face numbers change when an object is rebuilt.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "face": {
     "type": "string"
    },
    "finish": {
     "type": "string",
     "enum": [
      "tiles",
      "solid",
      "pattern",
      "hatch"
     ]
    },
    "tile": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "thickness": {
     "type": "number"
    },
    "joint": {
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
  "group": "bim"
 },
 "bim_layers": {
  "name": "bim_layers",
  "description": "A layered build-up (multi-material): layers [{ material (name), thickness mm, density kg/m³ }] in order across the wall, put on objects (a wall takes the total as its width). Not written by FreeCAD 1.1's IFC export (the object goes out with no material). Answers layers (its label), total_mm, on, skipped.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "layers": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "objects": {
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
    "layers"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim"
 },
 "bim_ifc": {
  "name": "bim_ifc",
  "description": "Read or set BIM objects' IFC data (objects alone reads): type (FreeCAD's spaced names: Wall, Covering, \"Building Element Proxy\"; IfcWall is understood), classification (\"<system> <code>\", e.g. \"Uniclass Ss_25_10_30\": FreeCAD's IFC export needs the system's name, a space and the code, and a bare code is refused; \"\" clears it), properties { \"Pset_WallCommon.FireRating\": \"REI60\" } (set.property). Answers objects [{ object, ifc, classification, properties }].",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "type": {
     "type": "string"
    },
    "classification": {
     "type": "string"
    },
    "properties": {
     "type": "object"
    }
   },
   "required": [
    "objects"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim"
 },
 "bim_quantities": {
  "name": "bim_quantities",
  "description": "Take-off of the BIM model by type | material | both: groups { count, volume_m3, mass_kg (null when a density is missing) }, totalMass_kg; detail: true adds rows with areas and perimeter. Densities come from bim_material / bim_layers. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "by": {
     "type": "string",
     "enum": [
      "type",
      "material",
      "both"
     ]
    },
    "detail": {
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
 "bim_preflight": {
  "name": "bim_preflight",
  "description": "Check the model before bim_export (Agent Link's own checks): a site, building or storey; each object's IFC type, solid and valid shape, storey, material, host wall; duplicate labels. Answers ok, issues [{ object, issues }], blocking (fix these first). Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "bim"
 },
 "bim_edit": {
  "name": "bim_edit",
  "description": "Change BIM components. op add | subtract { object, with [labels] }: fuse them in or cut them out | cut { object, at, normal }: by a plane, removing the side the normal points to (answers removed_m3) | join { walls, delete }: walls of the same width, height and align into one, the last named kept | clone { object, move }.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "op": {
     "type": "string",
     "enum": [
      "add",
      "subtract",
      "cut",
      "join",
      "clone"
     ]
    },
    "object": {
     "type": "string"
    },
    "with": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "walls": {
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
    "normal": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "move": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "delete": {
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
  "group": "bim"
 },
 "bim_component": {
  "name": "bim_component",
  "description": "A generic BIM component: kind component { from (an object with a shape), ifcType } | clone { from, at, axis, angle } (follows the original) | unclone { from } (cut loose). Answers object, volume mm³, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "component",
      "clone",
      "unclone"
     ]
    },
    "from": {
     "type": "string"
    },
    "ifcType": {
     "type": "string"
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
   "required": [
    "from"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim_gaps"
 },
 "bim_reference": {
  "name": "bim_reference",
  "description": "An external reference: another file's objects shown here and updated with it, not copied. path: the full path of an .FCStd (or .ifc, .dxf); part: one of its parts. Answers reference, file, volume, box.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "part": {
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
  "group": "bim_gaps"
 },
 "bim_panel_out": {
  "name": "bim_panel_out",
  "description": "BIM panels for the cutter: kind cut (each panel's flat outline with its tag) | sheet { width, height } (the cuts on one stock sheet, not nested). export { format: \"dxf\" } writes them.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "cut",
      "sheet"
     ]
    },
    "panels": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "width": {
     "type": "number"
    },
    "height": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "panels"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim_gaps"
 },
 "bim_nest": {
  "name": "bim_nest",
  "description": "Nest flat pieces into a sheet: container (one flat face), pieces (objects of exactly one flat face each, the same way up; not solids), rotations to try ([0, 90, 180, 270]). The pieces are moved. margin is not applied (FreeCAD 1.1's nester has none). Slow with many pieces: start with a few.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "container": {
     "type": "string"
    },
    "pieces": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "rotations": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "margin": {
     "type": "number"
    }
   },
   "required": [
    "container",
    "pieces"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim_gaps"
 },
 "bim_ifc_brep": {
  "name": "bim_ifc_brep",
  "description": "Set whether BIM objects go to IFC as B-rep (plain faces) instead of extrusions: on true | false, toggled when left out.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "on": {
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
  "group": "bim_gaps"
 },
 "bim_views": {
  "name": "bim_views",
  "description": "2D plan views of levels (all storeys when left out): a section plane at cutHeight mm above each one's elevation (1100) and a flat Draft view of it; cutOnly: the cut faces alone. Slow on big levels.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "levels": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "cutHeight": {
     "type": "number"
    },
    "cutOnly": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim_gaps"
 },
 "bim_image_plane": {
  "name": "bim_image_plane",
  "description": "An image plane to trace over: path (the image's full path), width and/or height mm (one gives the other), at, axis, angle. Seen in the window only.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "width": {
     "type": "number"
    },
    "height": {
     "type": "number"
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
   "required": [
    "path"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim_gaps"
 },
 "bim_library": {
  "name": "bim_library",
  "description": "The objects library (the parts_library add-on, or folder): search words find files (answers found [{ name, path }]); insert: a found name or full path brings it into the document.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "search": {
     "type": "string"
    },
    "folder": {
     "type": "string"
    },
    "insert": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {
   "insert": [
    null,
    ""
   ]
  },
  "group": "bim_gaps"
 },
 "bim_reextrude": {
  "name": "bim_reextrude",
  "description": "Re-extrude a BIM object from one of its faces (\"Wall.Face3\"): a new wall, panel or structure standing on that face, as deep as the old one, with its material and IFC type; the old one is deleted unless delete: false. Face numbers change when an object is rebuilt.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "face": {
     "type": "string"
    },
    "delete": {
     "type": "boolean"
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
  "group": "bim_gaps"
 },
 "bim_rewire": {
  "name": "bim_rewire",
  "description": "Rebuild loose lines and wires (objects) as joined wires, one per connected run; the originals are deleted.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    }
   },
   "required": [
    "objects"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim_gaps"
 },
 "bim_glue": {
  "name": "bim_glue",
  "description": "Glue two or more objects' shapes into one plain compound (not fused, no longer parametric); the originals are deleted.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
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
    "objects"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim_gaps"
 },
 "bim_trash": {
  "name": "bim_trash",
  "description": "BIM's trash: action put { objects } (moved into a hidden Trash group, still in the document) | list | empty (deleted for good, with children nothing else uses).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "action": {
     "type": "string",
     "enum": [
      "put",
      "list",
      "empty"
     ]
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
  "reads": {
   "action": [
    "list"
   ]
  },
  "group": "bim_gaps"
 },
 "bim_reorder": {
  "name": "bim_reorder",
  "description": "Reorder a group's, level's or building's children in the tree: order [labels to put first], or sort: true by label.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "group": {
     "type": "string"
    },
    "order": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "sort": {
     "type": "boolean"
    }
   },
   "required": [
    "group"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "bim_gaps"
 }
}
''')
