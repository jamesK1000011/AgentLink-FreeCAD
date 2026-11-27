# SPDX-License-Identifier: LGPL-2.1-or-later
# The description and inputSchema of the six tools that were made flat on
# 27 Nov (sketch_add, sketch_constrain, pd_fillet, pd_chamfer, sketch_project,
# sketch_external), as they were made then. tests/_meant.py gives them to the
# data-tool snapshot tests in place of the handlers' words at the old commit.
# What the words say is checked in tests/test_flat_inputs_1127.py.
import json

FLAT = json.loads(r"""{
 "sketch_add": {
  "description": "Add one shape to a sketch: rectangle, circle, line, arc, slot, polygon, ellipse, point and more. Its x/y are the sketch's own, in mm. Angles are deg, counter-clockwise from +x. One call adds one shape: a rectangle or a circle is one call, not four lines. Several shapes are several calls: in a batch, or with each. kind is the shape, and its own inputs stand beside it. The kinds follow. line {from, to}. polyline {points, closed}. arc {center, radius, start, end}. arc3 {points}. circle {center, radius|diameter}. circle3 {points}. ellipse {center, major, minor, rotation}. parabola {vertex, focal, rotation, from, to}. hyperbola {center, major, minor, rotation, from, to}. bspline {points, closed}. Or bspline {interpolate: false, points, degree}. rectangle {center|corner, size}. rounded_rectangle {…, radius}. polygon {center, radius, sides, rotation}. slot {from, to, radius}. arc_slot {center, radius, width, start, end}. point {at}. Example: a plate on XY is centred: { \"tool\": \"sketch_add\", \"kind\": \"rectangle\", \"center\": [0, 0], \"size\": [50, 40] }, padded 4. On its top, sketch_new { face: { side: \"+z\" } } answers bodyExtent { x: [-25.0, 25.0], y: [-20.0, 20.0] }. A block on one corner takes corner [x min, y min]: kind rectangle, corner [-25, -20], size [10, 10]. Then pd_pad { length: 6 } makes the block. A shape comes with its own coincident/horizontal/vertical/tangent/equal constraints. The tool does not join separate shapes to each other; sketch_constrain coincident or tangent does that. A full circle is a closed wire of its own. sketch_constrain tangent on two end points [[line, v], [arc, v]] makes them coincident and smooth. With dims and name, param_bind binds the sizes. Answer: result (a one-line summary first), added [{ ids, constraints, dims }] and state. ids: the geometry ids of the shape, in the order made. The first shape of a sketch has ids from 0, and each next shape takes the next ids. The last id of a polygon is its construction circle. constraints: [first, last] ids. state: dof, wires, closedWires, openVertices, points, wiresMeet. Vertices: 1 start, 2 end, 3 centre.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "kind": {
     "type": "string",
     "enum": [
      "line",
      "polyline",
      "arc",
      "arc3",
      "circle",
      "circle3",
      "ellipse",
      "parabola",
      "hyperbola",
      "bspline",
      "rectangle",
      "rounded_rectangle",
      "polygon",
      "slot",
      "arc_slot",
      "point"
     ],
     "description": "The shape. Its own inputs stand beside it."
    },
    "from": {
     "anyOf": [
      {
       "type": "array",
       "items": {
        "type": "number"
       }
      },
      {
       "type": "number"
      }
     ],
     "description": "line, slot: the start point [x, y] (slot: the centre of one end). parabola, hyperbola: a number, where the curve starts."
    },
    "to": {
     "anyOf": [
      {
       "type": "array",
       "items": {
        "type": "number"
       }
      },
      {
       "type": "number"
      }
     ],
     "description": "line, slot: the end point [x, y] (slot: the centre of the other end). parabola, hyperbola: a number, where the curve ends."
    },
    "points": {
     "type": "array",
     "items": {
      "type": "array",
      "items": {
       "type": "number"
      }
     },
     "description": "[x, y] points. polyline: the corners. arc3: start, through, end. circle3: three points on it. bspline: the points it goes through (its poles when interpolate is false)."
    },
    "closed": {
     "type": "boolean",
     "description": "polyline, bspline: true joins the last point to the first."
    },
    "center": {
     "type": "array",
     "items": {
      "type": "number"
     },
     "description": "[x, y]: the middle of the shape. A shape at [0, 0] goes to the two sides of the sketch origin. A rectangle takes center or corner."
    },
    "corner": {
     "type": "array",
     "items": {
      "type": "number"
     },
     "description": "rectangle: [x, y] of its lower-left corner. Use it to start a shape at an edge of the body (sketch_new gives bodyExtent)."
    },
    "size": {
     "type": "array",
     "items": {
      "type": "number"
     },
     "description": "rectangle: [w, h], mm."
    },
    "radius": {
     "type": "number",
     "description": "mm. circle (or diameter), arc, rounded_rectangle (its corners), polygon (to the corners), slot (half its width), arc_slot (of its middle)."
    },
    "diameter": {
     "type": "number",
     "description": "circle: mm, in place of radius."
    },
    "start": {
     "type": "number",
     "description": "arc, arc_slot: deg. The arc runs ccw from start to end."
    },
    "end": {
     "type": "number",
     "description": "arc, arc_slot: deg."
    },
    "major": {
     "type": "number",
     "description": "ellipse: the full size, mm (the larger). hyperbola: the semi-axis, mm."
    },
    "minor": {
     "type": "number",
     "description": "ellipse: the full size, mm. hyperbola: the semi-axis, mm."
    },
    "rotation": {
     "type": "number",
     "description": "deg. ellipse, hyperbola, polygon: the turn about center. parabola: the way it opens (0 is +x)."
    },
    "sides": {
     "type": "integer",
     "description": "polygon: 3 or more."
    },
    "width": {
     "type": "number",
     "description": "arc_slot: mm, under twice the radius."
    },
    "at": {
     "type": "array",
     "items": {
      "type": "number"
     },
     "description": "point: [x, y]."
    },
    "vertex": {
     "type": "array",
     "items": {
      "type": "number"
     },
     "description": "parabola: [x, y]."
    },
    "focal": {
     "type": "number",
     "description": "parabola: mm from the vertex to the focus."
    },
    "interpolate": {
     "type": "boolean",
     "description": "bspline: false takes points as its poles. The default, true, goes through them."
    },
    "degree": {
     "type": "integer",
     "description": "bspline with interpolate false: 1 to 9."
    },
    "construction": {
     "type": "boolean",
     "description": "true makes the shape construction geometry."
    },
    "dims": {
     "type": "boolean",
     "description": "true adds the sizes of the shape as constraints. A kind with no size to dimension says so in dimsNote."
    },
    "name": {
     "type": "string",
     "description": "With dims: the name of the sizes. They are named <name>_width, _height, _d, _r, _length; param_bind binds these."
    }
   },
   "required": [
    "kind"
   ],
   "additionalProperties": false
  }
 },
 "sketch_constrain": {
  "description": "Constrain a sketch with one geometric or dimensional constraint for each call: type, refs, value, name. Several constraints are several calls: in a batch, or with each. Example: { \"tool\": \"sketch_constrain\", \"type\": \"tangent\", \"refs\": [0, 1] } makes line 0 tangent to circle 1. A ref is FreeCAD's: a geometry id g, a point p = [g, vertex], or \"origin\". Vertex: 1 start, 2 end, 3 centre. -1 is the horizontal axis, -2 the vertical axis, -3 down are outside edges. Each type and its refs follow. coincident [p, p]. point_on_object [p, g]. horizontal | vertical [g] or [p, p]. parallel | perpendicular | equal [g, g]. tangent [g, g] or end points [p, p]. symmetric [p, p, g] (about a line) or [p, p, p]. distance [g] (length), [p, p] or [p, g]. distance_x | distance_y [g], [p] (from the origin) or [p, p] (second minus first). radius | diameter [g]. All lengths are mm. angle [g] (from +x) or [g, g] (first to second, ccw), deg. fix [p]: holds a point where it is. fix [g]: blocked; add it last. name: lets you bind it to a parameter later. All or nothing: the tool refuses a constraint that conflicts or is redundant. It names what clashes, and adds nothing. Answer: result (a one-line summary first), added (constraint ids from 0) and state.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "type": {
     "type": "string",
     "description": "coincident, point_on_object, horizontal, vertical, parallel, perpendicular, equal, tangent, symmetric, distance, distance_x, distance_y, radius, diameter, angle or fix (the description gives the refs of each)."
    },
    "refs": {
     "type": "array",
     "description": "Ids g or points [g, vertex], in order. Line 0 tangent to circle 1: [0, 1]."
    },
    "value": {
     "type": "number",
     "description": "A size: mm, or deg for angle."
    },
    "name": {
     "type": "string",
     "description": "A name for param_bind."
    }
   },
   "required": [
    "type"
   ],
   "additionalProperties": false
  }
 },
 "pd_fillet": {
  "description": "Round edges of the body. edges: one selector. { near: [x,y,z] } is the edge nearest a point. { face: { side: \"+z\" } } or { face: { at, normal } } is every edge of a face. { all: true } is all edges. kind: line|circle filters them. Or give a reference that shape_query answers (\"Edge3\", \"Body.Edge3\"), or a list of such references. Or give shape_query's filters ({ type: circle, radius: 3 }): every such edge; with near, the nearest. { type: \"line\", axis: \"z\", outside: true } is the outside vertical corners. Without outside, { type: \"line\", axis: \"z\" } is every vertical edge, inside corners too. Add length or inside to keep fewer of them. radius: mm (default 1). References are good until the next change: query again after a change. The tool skips smooth (tangent) edges. An outside (convex) edge loses material; an inside (concave) edge gets material. outside: true keeps the outside edges, false the inside edges. The answer adds on: a count of the outside and inside edges. Then each edge with its direction, length, mid-point and side. Answer: result (a one-line summary first), feature, volume mm³, volumeChange, faces, solids, box, health. On a failure, it refuses with FreeCAD's error; nothing is kept. Prefer fillets last in the tree. Do not attach a sketch or a datum to a fillet face.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "edges": {
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
     "description": "One selector: { near: [x,y,z] } the edge nearest a point | { face: { side: \"+z\" } or { at, normal } } every edge of a face | { all: true }, kind: line|circle | shape_query's filters ({ type: circle, radius, axis, near, outside, … }); or a reference shape_query gives (\"Edge3\", \"Body.Edge3\"; a face's: its edges), or a list of references."
    },
    "radius": {
     "type": "number"
    }
   },
   "required": [
    "edges"
   ],
   "additionalProperties": false
  }
 },
 "pd_chamfer": {
  "description": "Bevel edges of the body. edges: as pd_fillet: one selector, or a list of references. { type: \"line\", axis: \"z\" } is every straight edge along z: the vertical edges. size: mm (default 1). size2 for two distances, or angle deg for a distance and an angle (one of them). On an inside corner it adds material; on an outside corner it removes material. outside: true keeps the outside edges, false the inside edges. The answer adds on: a count of the outside and inside edges. Then each edge with its direction, length, mid-point and side. Answer: result (a one-line summary first), feature, volume mm³, volumeChange, faces, solids, box, health. On a failure, it refuses with FreeCAD's error; nothing is kept.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string",
     "description": "The PartDesign body; may be left out when there is one."
    },
    "edges": {
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
     "description": "One selector: { near: [x,y,z] } the edge nearest a point | { face: { side: \"+z\" } or { at, normal } } every edge of a face | { all: true }, kind: line|circle | shape_query's filters ({ type: circle, radius, axis, near, outside, … }); or a reference shape_query gives (\"Edge3\", \"Body.Edge3\"; a face's: its edges), or a list of references."
    },
    "size": {
     "type": "number"
    },
    "size2": {
     "type": "number"
    },
    "angle": {
     "type": "number"
    }
   },
   "required": [
    "edges"
   ],
   "additionalProperties": false
  }
 },
 "sketch_project": {
  "description": "Bring edges of a binder, datum or another sketch of the same body into this sketch as external geometry. from: the source. edges: \"Edge3\", one selector { near, kind } or shape_query's filters, or a list of references [\"Edge3\", \"Edge5\"] (default all). defining: true makes them part of the profile (FreeCAD 1.1 and later). Answer: ids (-3 down, in order) for sketch_constrain. For the body's own solid: sketch_external.",
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
     "description": "\"Edge3\", one selector { near, kind } or shape_query's filters, or a list of references. Left out: every edge."
    },
    "defining": {
     "type": "boolean"
    }
   },
   "required": [
    "from"
   ],
   "additionalProperties": false
  }
 },
 "sketch_external": {
  "description": "Bring edges of the body's solid (its tip) into a sketch as outside geometry to constrain to. edges: \"Edge7\", one query { type: circle|line, radius, axis, near, inside } as shape_query takes, or a list of references [\"Edge7\", \"Edge9\"]. The query is safer, because edge numbers change with edits. Answer: ids (negative, -3 down, in order) for the refs of sketch_constrain. A constraint to them follows the part. The tool refuses when the tip is built from this sketch. From a datum, binder or other sketch: use sketch_project.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "sketch": {
     "type": "string",
     "description": "The sketch's name; may be left out when there is one."
    },
    "edges": {
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
     "description": "\"Edge7\", one query { type, radius, axis, near, inside } as shape_query takes, or a list of references."
    }
   },
   "required": [
    "edges"
   ],
   "additionalProperties": false
  }
 }
}""")
