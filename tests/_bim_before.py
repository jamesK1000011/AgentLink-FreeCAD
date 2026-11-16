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
 }
}
''')
