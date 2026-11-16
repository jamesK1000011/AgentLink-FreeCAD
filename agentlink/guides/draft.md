# Lettering and surfaces
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

## Lettering
- `draft_text { body, text, size, depth }` raises text from the largest face facing up; `face` picks another (`{ normal: [0, -1, 0] }` the front), `at` a place on it, `rotate` turns it, `mode: "engrave"` cuts it in.
- For printing: letters at least 5 mm tall, raised 0.6–1 mm or cut 0.4–0.6 mm. On a face that prints facing down (on the bed) emboss reads mirrored and engrave bridges: put text on top or on a wall.
- `draft_fonts` lists the fonts; a bold, simple face (sans) prints best. The answer warns when the strokes are thinner than a printed line, and when the text runs off the face.
- Look at it: `view_render { zoom: { at, size } }` on the answer's box.

## A logo or shape from a file
- `draft_outline { path, body, width, depth, mode }` — the closed outlines of an SVG or DXF (holes stay holes), scaled to `width` or `height` mm: `emboss` or `engrave` on a body's face (as lettering), or `extrude` into a part of its own (a sign, a stencil, a badge).
- Text in the file must be paths first (Inkscape: Path → Object to Path); images are not outlines (trace them first). Open curves are left out and counted — close them if they matter.
- `mirror: true` for artwork printed face down on the bed, or read through clear material.

## Surfaces
- `surface_fill { edges, thickness }` — a smooth surface across a closed boundary (edges of bodies, or a sketch's outline), thickened into a solid when `thickness` is given. Then `part_boolean` joins it to a part.
- `surface_loft { curves, thickness, side }` — a surface through curves in order: edges, sketches, or `{ points: [[x,y,z] …] }` for a smooth curve through them. Open curves make a sheet (a curved panel), closed ones a tube (a duct between two outlines). `ruled` for straight lines between them.
- `surface_points { rows, tolerance }` — a smooth surface through a grid of points, row by row: points measured off something, or a shape worked out from numbers. `farthestPoint` says how close it came; `tolerance` trades closeness for smoothness.
- `surface_thicken { surface, thickness, side }` — any surface (or a body's face) as a solid: `side` out along its normal, in, or both. At least 0.8 mm for a 0.4 mm nozzle; a surface bent tighter than the thickness cannot be thickened that way.
- A surface alone does not print: thicken it, then `body_check` it like any part.

## Copies of a part
- `draft_array { body, kind: "grid", count: [3, 2] }` — copies side by side with a `gap` (2 mm) between, or `spacing [dx, dy, dz]`; `polar { count, center, axis, angle }` round a circle; `path { path, count, align }` along a curve.
- Joined into the body by default (a wheel's spokes, a row of teeth); `separate: true` makes each copy its own body — a batch to lay out for printing. A feature repeated inside one parametric part is `pd_linear_pattern` / `pd_polar_pattern` instead: it stays editable.

## Draft's own objects
These make the Draft workbench's parametric objects, which the person can edit in Draft later. Draft draws in the active document on the working plane, XY unless the person set another in the window; these tools do not change it. Every changing reply may carry `health` (`ok`, `verdict`, `todo`).
- `draft_shape` makes 2D shapes (wire, rectangle, circle, arc, ellipse, polygon, B-spline, Bezier, point). A closed shape is a filled face by default (Draft's Make Face preference); `face: false` keeps the outline only, and `length` then still counts every edge. Wire, B-spline and Bezier points are where you give them; `at` and `normal` place the other kinds (a rectangle's corner, a circle's centre). Angles are degrees, counter-clockwise from x. Two points make a "Line"; a first point repeated as the last closes the curve.
- `draft_dimension` and `draft_label` annotate the model itself, not a drawing (for a drawing: TechDraw, `td_*`). They have no shape: the reply's `measures` and `text` are the reading. Vertex and edge numbers count from 1 (`Vertex1`, `Edge1`), as `shape_query` lists them, and change when the object's shape is rebuilt. A dimension made with `object` follows it; one made from two points does not. With FreeCAD's window up, Draft asks the active 3D view which way it looks: if a drawing page or spreadsheet tab is in front the call is refused and nothing is kept.
- `draft_style` keeps annotation styles in the document. Arrow types are Dot, Circle, Arrow, Tick, Tick-2, None; `ArrowSize` / `ArrowType` set both ends, `ArrowSizeStart` / `ArrowTypeEnd` … one. Colours are one number, 0xRRGGBBAA. A style is a view setting: it shows only in the window.
- `draft_link_array` makes ortho, polar, circular, path and point arrays as links: light, and they follow the original, which Draft hides. `count` includes the original; `spacing` runs from one copy to the next (pitch, not gap). Polar arrays turn about z through `center`. `link: false` makes real shapes that can be fused (`object_set { values: { Fuse: true } }`). `draft_clone` makes one copy that follows; `draft_array` makes plain solids of a whole body.
- `draft_layer` groups objects and sets how they are drawn; an object is on one layer at a time. `draft_hatch` draws a PAT pattern on flat faces as lines (FreeCAD's FCPAT.pat: Diamond, Diamond2, Diamond4, Diagonal4, Diagonal5, Square, Horizontal5, Vertical5).
- `draft_to_sketch` / `draft_from_sketch` convert between Draft and Sketcher. To a sketch: every object flat and all in one plane; constraints are only the coincident, horizontal and vertical ones that already hold. From a sketch: straight runs become Draft wires, a lone circle or arc a Draft circle; anything with curves joined to lines stays a plain shape.
- `draft_2d_view` is a 2D projection laid on XY, ready for DXF (`hidden: true` adds hidden lines). Cut faces (`section: true`) work only from a BIM section plane. `draft_facebinder` makes a surface that follows faces.
- `draft_plane` records a plane as an object; `draft_fix` flips a dimension's text or rebuilds Draft objects from an old file.

## draft_modify, op by op
- `move`, `rotate`, `scale`: in place, or `copy: true` for new objects. A Draft circle or rectangle scaled evenly stays parametric; scaled unevenly, or any non-Draft shape, it becomes a plain shape (the original is replaced).
- `mirror`: `from` and `to` are two points of the mirror line in the working plane (XY). Always a new Part Mirroring object that follows the original, which stays.
- `offset`: one object. `by` is a vector from the object's first edge: its length is the distance and its direction the side. A Draft circle takes the radius of the circle through its first vertex moved by `by`. Sketches and Part shapes are never changed: a copy is made. A Draft B-spline is refused (`part_offset2d` instead).
- `upgrade`: one stage a call, as Draft's Upgrade: edges that meet become one wire; an open Draft wire is closed; a closed wire becomes a face; faces that close a volume become a solid. `delete: false` keeps the inputs. `downgrade` goes back one stage. The results are plain shapes, no longer parametric.
- `join`: Draft wires whose end points coincide become the first wire; the others are removed. Refused when no two ends meet.
- `fillet`: two objects of one edge each (lines or arcs) that share an end point; a new Fillet object, `delete: true` removes the two.
- `split`: one Draft wire, `edge` the segment from 1; `at` is dropped onto that segment (default its middle). A closed wire gives that segment as a wire of its own and the rest as one open wire.
- `stretch`, `extend`, `to_bspline`, `to_wire`: on Draft wires, B-splines and Bezier curves, by their points.
