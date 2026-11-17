# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the spreadsheet tools of families/sheet.py and the
# document-level tools of families/std_more.py now kept as data, at the commit
# they were converted from (tests/test_datasheet_data.py's BASE): name,
# description, inputSchema, changes, reads, group. Written by
#   python3 tests/test_datasheet_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "sheet_new": {
  "name": "sheet_new",
  "description": "Make an empty spreadsheet: name (its label). The reply's name is what expressions use: <name>.A1, <name>.<alias>, or <<label>>.<alias>.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sheet"
 },
 "sheet_list": {
  "name": "sheet_list",
  "description": "The spreadsheets (the Params sheet too): cells used, their range, aliases and what uses them, design tables. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "sheet"
 },
 "sheet_read": {
  "name": "sheet_read",
  "description": "Read a sheet's cells: content (\"=A1 * 2\"; text has a leading '), computed value and unit, alias, or error (FreeCAD's reason); empty: true for an empty cell. range \"A1:D20\" or cells [..] narrows (400 cells a call); format: true adds style, alignment, colours, display unit. Shows bound ranges and design tables. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sheet": {
     "type": "string"
    },
    "range": {
     "type": "string"
    },
    "cells": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "format": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "sheet"
 },
 "sheet_set": {
  "name": "sheet_set",
  "description": "Write cells as if typed in FreeCAD, then recompute: cells { A1: 12, B1: \"=A1 * 2\", C1: \"10 mm\", D1: \"text\", E1: null (clears) }, or rows [[…], …] from at (default A1); text: true keeps strings as text. aliases { B2: \"width\" } (\"\" removes) names a cell for expressions (<Sheet>.width): a letter, then letters, digits, _; not a cell address, a unit (m, mm, s, N, A …) or e, pi. A formula FreeCAD cannot parse, a failing cell or a feature it breaks is refused, nothing kept. Reply: cells; drives and bodies when an alias is in use.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sheet": {
     "type": "string"
    },
    "cells": {
     "type": "object",
     "additionalProperties": {
      "type": [
       "number",
       "string",
       "null"
      ]
     }
    },
    "at": {
     "type": "string"
    },
    "rows": {
     "type": "array",
     "items": {
      "type": "array",
      "items": {
       "type": [
        "number",
        "string",
        "null"
       ]
      }
     }
    },
    "text": {
     "type": "boolean"
    },
    "aliases": {
     "type": "object",
     "additionalProperties": {
      "type": "string"
     }
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sheet"
 },
 "sheet_clear": {
  "name": "sheet_clear",
  "description": "Clear a range, \"A1:C4\" (contents, alias, format; up to 20000 cells). Refused if an alias there is in use, unless force (then refused only if a user fails).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sheet": {
     "type": "string"
    },
    "range": {
     "type": "string"
    },
    "force": {
     "type": "boolean"
    }
   },
   "required": [
    "range"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sheet"
 },
 "sheet_format": {
  "name": "sheet_format",
  "description": "Format a range: style [bold, italic, underline] ([] clears), align [left|center|right, top|vcenter|bottom], color / background \"#rrggbb\" (null clears), displayUnit \"mm\" | \"in\" | \"deg\" … (how it shows; the value stays), width (column px), height (row px), merge true (the top-left cell stays, the rest are cleared) | false.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sheet": {
     "type": "string"
    },
    "range": {
     "type": "string"
    },
    "style": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "align": {
     "type": [
      "array",
      "string"
     ],
     "items": {
      "type": "string"
     }
    },
    "color": {
     "type": [
      "string",
      "null"
     ]
    },
    "background": {
     "type": [
      "string",
      "null"
     ]
    },
    "displayUnit": {
     "type": [
      "string",
      "null"
     ]
    },
    "width": {
     "type": "integer"
    },
    "height": {
     "type": "integer"
    },
    "merge": {
     "type": "boolean"
    }
   },
   "required": [
    "range"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sheet"
 },
 "sheet_rows": {
  "name": "sheet_rows",
  "description": "Insert or remove rows or columns: action insert | remove, rows (the first row's number, from 1; new rows go above it) or columns (the first column's letters), count. References and aliases move with the cells; removing a cell in use is refused.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sheet": {
     "type": "string"
    },
    "action": {
     "type": "string",
     "enum": [
      "insert",
      "remove"
     ]
    },
    "rows": {
     "type": "integer"
    },
    "columns": {
     "type": "string"
    },
    "count": {
     "type": "integer"
    }
   },
   "required": [
    "action"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sheet"
 },
 "sheet_import": {
  "name": "sheet_import",
  "description": "Read a CSV / TSV file into a sheet: path (in the out folder unless absolute), delimiter comma | tab | semicolon; sheet to fill one (replace: true if it holds cells: all of it goes), else a new sheet named after the file. Fields are taken as if typed (\"=…\" a formula).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "sheet": {
     "type": "string"
    },
    "delimiter": {
     "type": "string"
    },
    "replace": {
     "type": "boolean"
    }
   },
   "required": [
    "path"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sheet"
 },
 "sheet_export": {
  "name": "sheet_export",
  "description": "Write a sheet's computed values to a CSV / TSV file: path (default <sheet>.csv in the out folder), delimiter. No formulas, aliases or units (a quantity is its number in mm, deg, kg, s). Changes nothing in the document.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sheet": {
     "type": "string"
    },
    "path": {
     "type": "string"
    },
    "delimiter": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "sheet"
 },
 "sheet_chart": {
  "name": "sheet_chart",
  "description": "A chart of a sheet's columns, written as SVG: kind line | bar | scatter (needs x), x (a range of labels or numbers), y [ranges of values, \"B2:B20\"], names, title, xlabel, ylabel, path. Reply: path, series, points.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sheet": {
     "type": "string"
    },
    "kind": {
     "type": "string",
     "enum": [
      "line",
      "bar",
      "scatter"
     ]
    },
    "x": {
     "type": "string"
    },
    "y": {},
    "names": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "title": {
     "type": "string"
    },
    "xlabel": {
     "type": "string"
    },
    "ylabel": {
     "type": "string"
    },
    "path": {
     "type": "string"
    }
   },
   "required": [
    "y"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "sheet"
 },
 "sheet_table": {
  "name": "sheet_table",
  "description": "Design tables (configurations), FreeCAD's own kind: action make { params [names; alias rules as sheet_set], configs [{ name, values [..] | { param: value } }], units { param: \"mm\" | \"deg\" | \"\" } (numbers default mm), sheet (else a new one), at (the header cell; the active row is under it), owner (the object carrying the switch; default the one Body, else a group holding the sheet), property (default Configuration), active } — then bind properties to <Sheet>.<param> with param_bind; use { config } switches and answers the bodies; add { config, values } adds a row; list. guide_read sheet.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "action": {
     "type": "string",
     "enum": [
      "make",
      "use",
      "add",
      "list"
     ]
    },
    "sheet": {
     "type": "string"
    },
    "name": {
     "type": "string"
    },
    "at": {
     "type": "string"
    },
    "params": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "configs": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "units": {
     "type": "object",
     "additionalProperties": {
      "type": "string"
     }
    },
    "owner": {
     "type": "string"
    },
    "property": {
     "type": "string"
    },
    "active": {
     "type": "string"
    },
    "config": {
     "type": "string"
    },
    "values": {
     "type": [
      "array",
      "object"
     ]
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "sheet"
 },
 "doc_graph": {
  "name": "doc_graph",
  "description": "What is built from what in the document (Std Dependency graph): roots (objects nothing uses), uses { label: [its inputs] }, counts; path writes a GraphViz .dot (svg: true also draws it when GraphViz's dot is on this computer; the note says when it is not). Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "path": {
     "type": "string"
    },
    "svg": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "std_more"
 },
 "object_freeze": {
  "name": "object_freeze",
  "description": "Freeze objects (objects; frozen: false thaws) so recomputes leave their shapes as they are (Std Toggle freeze) — window only: FreeCAD 1.1 has no headless call for it, and the frozen state is not saved with the file. skipRecompute: true | false switches the whole document's recomputes off or on (works headless; recompute { force: true } still runs). Reply: frozen / unfrozen, not (those that did not take), skipRecompute. After thawing: recompute { force: true }.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "frozen": {
     "type": "boolean"
    },
    "skipRecompute": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 },
 "units_convert": {
  "name": "units_convert",
  "description": "A quantity in other units (FreeCAD's units calculator): value a number with its unit (\"2.5 in\", \"300 N*m\", \"45 deg\"), to a unit of the same kind (\"mm\", \"lbf*ft\", \"rad\"; * / ^ join units). Different kinds are refused. Reply: result (a number), text. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "value": {},
    "to": {
     "type": "string"
    }
   },
   "required": [
    "value",
    "to"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "std_more"
 },
 "object_align": {
  "name": "object_align",
  "description": "Place an object by point pairs (what Std Alignment does by clicking): pairs [[from: a point on it now, to: where that point should be] …] in mm, document coordinates. One or two pairs move it only; three or more (not in a line) turn it too, the least-squares rigid fit — no scaling. Reply: rms and worst miss in mm (near 0 when the pairs agree), placement. Changes Placement only.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "object": {
     "type": "string"
    },
    "pairs": {
     "type": "array",
     "items": {
      "type": "array"
     }
    }
   },
   "required": [
    "object",
    "pairs"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 },
 "link_make": {
  "name": "link_make",
  "description": "A link (App::Link) to an object: it shows the object again without copying it and follows every change. to: the object (or \"Box.Face3\" for one element); at, axis + angle: the link's placement, which stands in for the original's own, not added to it; count: an array of that many elements, all starting at the same place, each its own object to place with object_set (reply: elements). kind: group makes an App::LinkGroup of objects. Reply: link, name, to, placement.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "to": {
     "type": "string"
    },
    "kind": {
     "type": "string",
     "enum": [
      "link",
      "group"
     ]
    },
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
    "count": {
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
  "group": "std_more"
 },
 "link_edit": {
  "name": "link_edit",
  "description": "Change links: action replace { link, to } (point it at another object) | unlink { link, name } (a plain shape copy in its place, same placement; what used the link now uses the copy) | import { links } / import_all (objects linked from another document copied into this one). object_group { action: \"list\" } names the links.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "action": {
     "type": "string",
     "enum": [
      "replace",
      "unlink",
      "import",
      "import_all"
     ]
    },
    "link": {
     "type": "string"
    },
    "links": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "to": {
     "type": "string"
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
  "group": "std_more"
 },
 "object_duplicate": {
  "name": "object_duplicate",
  "description": "Copy objects in the document (Std Duplicate): each copy is independent but still built from the same inputs (a copied Pad uses the original's sketch); dependencies: true copies what each is built from too; simple: true copies the shape alone as a plain Part::Feature (no history, placement baked in). name: the copy's label (\"<label> copy\" by default). Reply: duplicated [{ from, copy }].",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "dependencies": {
     "type": "boolean"
    },
    "simple": {
     "type": "boolean"
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
  "group": "std_more"
 },
 "doc_merge": {
  "name": "doc_merge",
  "description": "Bring every object of another .FCStd into this document (File > Merge document): path (relative: the session's folder). Internal names that clash get a number (labels too, unless FreeCAD's duplicate-labels preference is on). Recomputes. Reply: count, objects, errors. import_file is for STEP, STL and other formats.",
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
  "group": "std_more"
 },
 "doc_info": {
  "name": "doc_info",
  "description": "The document's information (File > Document information): author, company, comment, license, licenseUrl, lastModifiedBy, label — the ones given are set (text), nothing given just reads. Reply: those, id, uid, created and modified dates, file, objects, bytes. Setting label renames the document as the person sees it; its internal name stays.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "author": {
     "type": "string"
    },
    "company": {
     "type": "string"
    },
    "comment": {
     "type": "string"
    },
    "license": {
     "type": "string"
    },
    "licenseUrl": {
     "type": "string"
    },
    "lastModifiedBy": {
     "type": "string"
    },
    "label": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "std_more"
 },
 "doc_revert": {
  "name": "doc_revert",
  "description": "Go back to the document's saved file, dropping every unsaved change (Std Revert): the document is closed and opened again, so the session's undo steps go too. Refused for a document never saved. Ask the person first unless the changes are only the agent's. Reply: document, reverted (the file), objects.",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "std_more"
 },
 "doc_save_all": {
  "name": "doc_save_all",
  "description": "Save every open document that has a file (Std Save all), each to its own file. Documents never saved are not touched and are listed in neverSaved: doc_save { path } for each. Reply: saved [paths].",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "std_more"
 },
 "text_document": {
  "name": "text_document",
  "description": "A text document kept in the file (App::TextDocument), for notes that travel with the model: name (found by label, made if new; \"Notes\" by default), text replaces what it holds, append: true adds a line instead; with no text it only reads the size. Reply: text (its label), chars, lines. It shows in the tree; the person reads it by double-clicking.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    },
    "text": {
     "type": "string"
    },
    "append": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 },
 "object_appearance": {
  "name": "object_appearance",
  "description": "Colour objects: color \"#rrggbb\" or [r,g,b] 0–1 (or random: true), transparency 0 (solid) – 100, faces { \"Face3\": \"#ff0000\" } a colour per face (the rest keep the object's colour; face numbers change after a modelling step: shape_query again). Shown at once in the window; headless they are kept on the object (AgentLinkColor …) and exports read them. Reply: set [{ object, color, transparency, faces, shown }].",
  "inputSchema": {
   "type": "object",
   "properties": {
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "color": {},
    "random": {
     "type": "boolean"
    },
    "transparency": {
     "type": "integer"
    },
    "faces": {
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
  "group": "std_more"
 },
 "scad_tidy": {
  "name": "scad_tidy",
  "description": "OpenSCAD workbench's tree tools on objects: action color_code (all shapes when no objects: coloured by validity and kind — the reply's key; as FreeCAD's own Color Shapes it recomputes nothing and leaves no object touched that was not before) | explode (a top-level Part::Fuse / MultiFuse / Compound deleted, its inputs kept, shown and moved by its placement) | expand_placements (placements pushed down to the leaves) | tolerance { vertex, edge, face mm } (a copy with tolerances raised to at least these, never lowered; the original hidden) | remove_subtree (objects and everything under them that nothing else uses — deleted for good) | replace { parent, old, new } (parent uses new where it used old). Reply by action: coloured, exploded, expanded, made, removed, replaced.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "action": {
     "type": "string",
     "enum": [
      "color_code",
      "explode",
      "expand_placements",
      "tolerance",
      "remove_subtree",
      "replace"
     ]
    },
    "objects": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "vertex": {
     "type": "number"
    },
    "edge": {
     "type": "number"
    },
    "face": {
     "type": "number"
    },
    "parent": {
     "type": "string"
    },
    "old": {
     "type": "string"
    },
    "new": {
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
  "group": "std_more"
 },
 "robot_tool": {
  "name": "robot_tool",
  "description": "Draw a tool shape on a robot's flange (Robot's Add tool shape): robot, tool (an object with a shape), at / axis + angle where on the shape the flange sits (ToolBase). Shown in the window only; it does not change the kinematics or the tool point (robot_new tool does).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "robot": {
     "type": "string"
    },
    "tool": {
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
    }
   },
   "required": [
    "robot",
    "tool"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 },
 "sheet_cells": {
  "name": "sheet_cells",
  "description": "Merge spreadsheet cells (merge \"A1:C1\": the top-left cell stays, the others are cleared with their aliases) or split a merged one (split \"A1\", any of its cells). sheet_format { merge } does the same and first checks for aliases in use.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sheet": {
     "type": "string"
    },
    "merge": {
     "type": "string"
    },
    "split": {
     "type": "string"
    }
   },
   "required": [
    "sheet"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "std_more"
 }
}
''')
