<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Sketches in a PartDesign body

## workflow
1. `pd_body_new`, then `sketch_new { plane: "XY" }` — or on a face of the body: `face: { at: [x,y,z], normal: [0,0,1] }`. The answer's `frame` says where sketch x/y lie in the world.
2. `sketch_add` the profile: rectangle, rounded_rectangle, circle, polygon, slot, polyline … Shapes come with their own coincident/horizontal/vertical constraints (a polyline's sides that run along x or y are held horizontal or vertical). `dims: true, name: "plate"` adds their sizes as named constraints (`plate_width`).
   - Where a shape goes: a first plate on XY is centred, `rectangle { center: [0, 0], size: [50, 40] }`. A shape at an edge of the body takes `corner`, its lower-left corner, from the `bodyExtent` that `sketch_new` answers.
   - Example, a block on one corner of that plate (padded 4): `sketch_new { face: { side: "+z" } }` answers `bodyExtent { x: [-25.0, 25.0], y: [-20.0, 20.0] }`. On this face the sketch x/y are the world x/y.
     The block is `rectangle { corner: [-25, -20], size: [10, 10] }`, corner `[x min, y min]`. Then `pd_pad { length: 6 }` makes it. At `center: [0, 0]` the same block would be in the middle of the plate, not on its corner.
3. `sketch_constrain` the rest: refs are FreeCAD's — geometry id, `[id, vertex]` (1 start, 2 end, 3 centre), `"origin"`; -1 the horizontal axis, -2 the vertical.
4. `sketch_state` before a feature: `readyForFeature`, `dof`, conflicts, open vertices.

## traps
- A constraint that over-constrains the sketch is refused, and nothing is added. The refusal names each constraint that clashes, new and existing, with what it holds. Drop one of them.
- A pad works on a sketch with dof > 0, but the profile can slide when a value changes. Fix it to the origin and dimension it for a parametric part.
- Every id counts from 0: geometry ids, constraint ids, and the conflicting / redundant lists (FreeCAD's own lists count from 1; the tools convert them). `"health"` on a changing call's reply says the same in words ("2 DoF left on line 3").
- `sketch_add` joins a shape's own pieces, never two separate items: a line drawn to where an arc ends still needs `coincident` (or `tangent` on the two end points, which joins them smoothly) from `sketch_constrain`.
- Round ends joined by straight sides (a crank arm, a lever, a link): draw arcs, not full circles. A full circle is a closed loop of its own. Lines that touch it do not close an outline with it: `sketch_state` says the wire branches. Recipe for ends at x 0 (radius 10) and x 80 (radius 6); it is also the example on the `sketch_add` card:
  `sketch_add` items `arc { center: [0, 0], radius: 10, start: 90, end: 270 }` (id 0), `arc { center: [80, 0], radius: 6, start: -90, end: 90 }` (id 1), `line { from: [0, -10], to: [80, -6] }` (id 2), `line { from: [80, 6], to: [0, 10] }` (id 3).
  Then `sketch_constrain` `tangent` on the end points at each joint: `[[2, 1], [0, 2]]`, `[[2, 2], [1, 1]]`, `[[1, 2], [3, 1]]`, `[[3, 2], [0, 1]]`. Each one joins the two ends and makes the joint smooth. For two equal ends, `slot` is one item.
- An arc always runs counter-clockwise from its start (vertex 1) to its end (vertex 2); vertex 3 is its centre. A line has no vertex 3.
- `distance_x` / `distance_y` are signed, second point minus first: `[[0, 1], [0, 2]]` with 30 puts the end 30 mm to the right of the start.
- `angle` on two lines `[g1, g2]` is measured from the first line's direction (start to end) to the second's, counter-clockwise. Lines drawn from a shared centre outwards give the angle between them.
- `fix` on a point is Sketcher's Lock (a distance_x and a distance_y from the origin, named `<name>_x`, `<name>_y`); on a whole geometry it is Block, which should be the last constraint added to that geometry.
- Not offered by `sketch_constrain`: tangent or perpendicular through a point of a third curve, an end point tangent to a curve's side, an angle at a chosen pair of ends, distance between two circles. Use coincident / point_on_object plus the two-curve forms.
- Deleting geometry renumbers every later id. Read `sketch_state` again before you constrain more.
- A sketch on a face follows that face. If an edit removes the face, the sketch breaks: `feature_list` shows it invalid.
- Angles are in degrees, counter-clockwise from +x. Lengths are in mm.

## Curves, offsets, outside edges
- Free curves: `bspline { points }` passes through the points (`closed: true` for a loop); `interpolate: false` takes them as control poles with `degree`. `ellipse { center, major, minor, rotation }`.
- `sketch_offset { distance }` — the profile moved out (negative: in) as new geometry: a wall's inside, a lid's lip, a clearance band. Round corners by default; `join: "intersection"` keeps them sharp. The offset does not follow later edits unless constrained.
- `sketch_external { edges }` brings the body's own edges in (negative ids from -3, in the order brought in) so a new profile is constrained to what is already there — a hole on a boss's axis, a rib off a wall — and follows when the part changes. It reads the body's tip: a sketch the tip is built from cannot take its edges (make a new sketch on the solid). Outside geometry is never part of the profile unless brought in with `sketch_project { defining: true }`.

## Editing what is drawn
- `sketch_edit { fillet: { at: [g, v], radius } }` rounds a corner where two curves meet (the curves are trimmed to the arc); `geometry [g1, g2]` with `near` points rounds between two curves that do not share an end.
- `trim { geometry, at: [x, y] }` cuts off the piece of a curve between the crossings round that point; `split { geometry, at }` breaks it in two there.
- `mirror { geometry, about }` adds mirrored copies about `"x"`, `"y"`, `"origin"` or a line's id — draw one side, mirror the other. The copies carry the constraints among themselves but are not tied to the originals: add `symmetric` constraints with `sketch_constrain` if they must follow.
- Ids shift after a delete, a fillet, a trim, a split or a join: read `sketch_state` before using ids again. Deleting an ellipse or a B-spline takes its construction axes / poles with it.
- `set` refuses a value the sketch cannot solve with and leaves the old one; a radius or diameter must be over 0, a distance not 0.

## More sketch tools
- `sketch_copy { geometry, by }` copies (or moves) geometry; `rotate { center, angle }` and `scale { center, factor }` likewise. `sketch_array` makes a grid — `cols` copies along x at `spacing[0]`, `rows` along y at `spacing[1]`, the original counted — or a `polar` ring (`count` with the original, over `angle`).
- `sketch_extend { geometry, end, by | to }` lengthens a line by mm or to another curve, an arc of a circle by mm along the arc; `sketch_join` replaces two open curves by one B-spline through the two ends named.
- `sketch_carbon { from }` copies another sketch in, as it lies in its own x/y; each copied dimension is bound to the source's by expression, so `sketch_edit set` on the copy is refused (change the source). `sketch_project { from: "<binder>" }` brings a binder's, datum's or sibling sketch's edges in to constrain to (another body: pd_binder first); its ids continue the same -3, -4 … run as `sketch_external`'s.
- `sketch_validate` is Sketcher's Validate. Run it when a pad says the profile is open: `fix: true` closes gaps that should be coincident and drops degenerate or redundant pieces; `autoconstrain: true` adds the obvious constraints.
- `sketch_add` also takes arc3 and circle3 (through three points), parabola and hyperbola. `sketch_bspline` raises or lowers a B-spline's degree and inserts or changes knots. `sketch_merge` joins sketches into one, `sketch_mirror` makes a mirrored copy, `sketch_attach` moves a sketch onto another plane or face; a face is bound to the feature that made it (or `face: { at, normal, feature }`, or `plane: "Pad.Face3"`), so the sketch does not hang on the tip, and a sketch that sits before that feature is moved after it.
