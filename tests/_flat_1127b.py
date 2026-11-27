# SPDX-License-Identifier: LGPL-2.1-or-later
# The description and inputSchema of the five more tools that were made flat
# on 27 Nov (td_cosmetic, asm_fits, cam_property_bag, sheet_table, pd_binder),
# as they were made then: one item for each call, no list of objects.
# tests/_meant.py gives them to the data-tool snapshot tests in place of the
# handlers' words at the old commit. What the words say is checked in
# tests/test_flat_lists_1127.py.
import json

FLAT = json.loads(r"""{
 "td_cosmetic": {
  "description": "Add cosmetic geometry to a view. From 1.1 these are FreeCAD's own cosmetic edges, so they also show in the window; td_export always draws them. One call adds one figure: kind and its inputs stand beside tool. Several figures are several calls: in a batch, or with each. kind line: from, to, points on the part. kind circle: center on the part, radius mm. kind centerline: edges, the two side lines of a shaft or hole; extend mm. kind thread: edges, the two outline lines of a side view. Or circle: the round edge of the end view. internal: true for a tapped hole. pitch: ISO coarse by default. length: mm. style: thin | visible | hidden | center. clear: true removes the earlier ones. td_lines takes them by order, from 0.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "view": {
     "type": "string"
    },
    "kind": {
     "type": "string",
     "enum": [
      "line",
      "circle",
      "centerline",
      "thread"
     ],
     "description": "The figure. Its own inputs stand beside it."
    },
    "style": {
     "type": "string",
     "enum": [
      "thin",
      "visible",
      "hidden",
      "center"
     ],
     "description": "line, circle: the line style. The default is thin."
    },
    "from": {
     "type": "array",
     "items": {
      "type": "number"
     },
     "description": "line: [x, y, z], the start, a point on the part."
    },
    "to": {
     "type": "array",
     "items": {
      "type": "number"
     },
     "description": "line: [x, y, z], the end, a point on the part."
    },
    "center": {
     "type": "array",
     "items": {
      "type": "number"
     },
     "description": "circle: [x, y, z], a point on the part."
    },
    "radius": {
     "type": "number",
     "description": "circle: mm on the part."
    },
    "edges": {
     "type": "array",
     "items": {},
     "description": "centerline: the two side lines of a shaft or hole, [\"Edge1\", \"Edge3\"]. thread: the two outline lines of a side view. Each is an edge of the view (td_geometry lists them)."
    },
    "extend": {
     "type": "number",
     "description": "centerline: mm past the two ends (3)."
    },
    "circle": {
     "description": "thread: the round edge of the end view, \"Edge4\"."
    },
    "internal": {
     "type": "boolean",
     "description": "thread: true for a tapped hole."
    },
    "pitch": {
     "type": "number",
     "description": "thread: mm. ISO coarse by default."
    },
    "length": {
     "type": "number",
     "description": "thread: mm along a side view. The default is the full length."
    },
    "clear": {
     "type": "boolean",
     "description": "true removes the earlier figures of the view first."
    }
   },
   "required": [
    "view"
   ],
   "additionalProperties": false
  }
 },
 "asm_fits": {
  "description": "Read the fits: the hole and the shaft that each joint puts together. Give joint for one joint. For parts with no joint, give a { part, element } and b. One call reads one pair. Several pairs are several calls: in a batch, or with each. The tool finds them as cylindrical faces of about one size on the axis of the joint. Answer: fits [{ hole, shaft: { part, diameter }, clearance, engagement mm, axisOffset }]. A minus clearance is interference. fit: \"H7/g6\" holds each fit to ISO 286. size: the nominal; else the tool reads it from the parts to 0.05 mm. With fit, the answer adds the type of fit, clearanceRange, the limits of each part and ok. verdict: pass | fix. For flat faces: their gap and angle. The tool skips a joint with nothing round, and gives the reason. Parts drawn at nominal size fail a shaft band such as g6. Changes nothing.",
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
    "a": {
     "type": "object",
     "description": "{ part, element }: one end of the pair, for parts with no joint. element is a face of the part, as asm_joint takes it."
    },
    "b": {
     "type": "object",
     "description": "{ part, element }: the other end of the pair."
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
  }
 },
 "cam_property_bag": {
  "description": "Make a CAM property bag of named values for the expressions of operations. One call adds one value: property (its name, no spaces), type Float | Length | Angle | Integer | String | Bool, value, group. name: the bag. If a bag has that name, the tool adds the value to it. Several values are several calls with the same name: in a batch, or with each. Answer: bag, name. Expressions call a value <name>.<property>.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string",
     "description": "The bag's label. A bag that has this label gets the property; else the tool makes a new bag."
    },
    "property": {
     "type": "string",
     "description": "The name of the value: letters and digits, no spaces."
    },
    "type": {
     "type": "string",
     "enum": [
      "Float",
      "Length",
      "Distance",
      "Angle",
      "Integer",
      "String",
      "Bool",
      "Percent",
      "Speed"
     ],
     "description": "The kind of the value. The default is Float."
    },
    "value": {
     "description": "The value. It must fit the type."
    },
    "group": {
     "type": "string",
     "description": "The group of the property in FreeCAD's property editor. The default is Custom."
    },
    "info": {
     "type": "string",
     "description": "The tooltip of the property."
    }
   },
   "required": [],
   "additionalProperties": false
  }
 },
 "sheet_table": {
  "description": "Make and use design tables (configurations), FreeCAD's own kind. action make { params, config, values, units, sheet, at, owner, property, active }. params: [names; alias rules as sheet_set]. config: the name of the first configuration. values: [..] | { param: value }, one for each param. action add makes each next configuration. units: { param: \"mm\" | \"deg\" | \"\" } (numbers default to mm). sheet: the sheet to use; if no sheet has that label, the tool makes a new sheet with it. No sheet: a new sheet. at: the header cell; the active row is under it. owner: the object that holds the switch; default the one Body, else a group that holds the sheet. property: default Configuration. Then bind properties to <Sheet>.<param> with param_bind. use { config }: switches, and answers the bodies. add { config, values }: adds a row. list: the tables. guide_read sheet tells more.",
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
  }
 },
 "pd_binder": {
  "description": "Bring faces of another body (or all of it) into this body as a shape binder (a SubShapeBinder). Use it to sketch on or to project from. from: body or feature. faces: one face on it, \"Face3\" or { at, normal }, or a list of references [\"Face3\", \"Face5\"]; none gives the whole shape. frozen: true keeps it as it is now. A source at document level gets Relative false. Then the binder moves with this body when an assembly places it. relative: true keeps FreeCAD's default. Answer: binder, faces, relative, next.",
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
     "anyOf": [
      {
       "type": "string"
      },
      {
       "type": "object"
      },
      {
       "type": "array",
       "items": {
        "type": "string"
       }
      }
     ],
     "description": "One face: a reference \"Face3\" (shape_query gives them), or by where it is, { at: [x, y, z], normal: [x, y, z] } or { side: \"+z\" }. Or a list of references, [\"Face3\", \"Face5\"]. Left out: the whole shape."
    },
    "frozen": {
     "type": "boolean"
    },
    "relative": {
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
  }
 }
}""")
