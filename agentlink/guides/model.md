# Modelling with Part
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

## Start here
A map of this guide. `guide_read { topic: "model", section: [...] }` reads the sections named.
- Before the first step: `workflow` (the order: block out, add and remove material, repeat and mirror, shell, round and bevel last) and `Parametric or plain` (which tools leave an object whose properties `object_set` can still change, how elements are numbered, where each primitive sits on `at`).
- Before the first boolean, fillet, shell or loft: `traps`. It is the longest section; most of it is about `part_loft`.
- At their own moment (the index lists them under later): `Wires, splitting, repair`, `Attachment`, `Heavy steps`, `Compounds`.

## workflow
1. Block the part out with `part_primitive` (box, cylinder …; `at` and `rotate` place it; `direction [x,y,z]` points the axis of a cylinder, cone, prism or tube) or `part_extrude` / `part_revolve` a profile (`{ points }`, `{ circle }`, a sketch, or a body's face "Box.Face6").
2. Add and remove material: `part_boolean { op, body, bodies }`, or in one call `part_extrude { profile, into, op: "cut" }` for a pocket or `op: "fuse"` for a boss.
3. Repeat and mirror with `part_transform` (linear, polar, mirror { fuse: true }).
4. Shell with `part_thickness`, then round and bevel last: `part_fillet` / `part_chamfer` with edges picked by `shape_query` or a `query`.
5. `body_check` after each change; `history_diff` says what it did.

## traps
- Face and edge numbers change after every modelling step: query again (`shape_query`) rather than reuse old references.
- A result keeps the label of `body`, so setups and specs follow it; `bodies` are removed (keep: true hides them, and a hidden body is still listed).
- A refusal for "changed nothing" means the pieces do not overlap: move them (`part_transform move`) and try again.
- `part_boolean` `common` with several `bodies` keeps what `body` shares with any of them (body ∩ bodies together), as FreeCAD's own common does; for the part shared by all, run `common` once for each of `bodies`.
- Fillets bigger than a face beside the edge, or shells thinner than a fillet, fail: smaller sizes, or the shell before the fillet.
- Loft profiles with different edge counts twist; start each at the matching corner. `part_loft` turns each profile to run the same way round and starts each at the point nearest the one before (`aligned` says what it changed). It keeps no loft that is invalid, open, inside out or bulges more than 15% beyond its profiles (measured on the surface itself, not its control points); the refusal gives the reason and names the spans that bulge (`profiles 11–12 by 37% along y`).
- A smooth loft through many real sections (a scan's, with local notches) can overshoot between them. `part_loft` tries again by itself: the profiles rebuilt as B-splines through the same points with one set of knots, then `maxDegree` 3 and 2 (stiffer), then span by span with the bulging spans ruled and sewn into one (kept only if sound; `segments: false` turns that off). `route` says what it did. Give `maxDegree: 3` up front for long runs of uneven sections.
- `ruled: true` turns each profile into a polygon of the same number of points (spread by arc length, seams lined up; `samples` sets how many), so a ruled loft always pairs up; B-splines given as they are failed it. Two profiles that OCC will not loft smoothly are ruled the same way, since a loft between two profiles is straight anyway.
- A loft of many profiles and points is heavy: its time grows about as the cube of its faces (91 profiles of 36 points ruled took 10 s; of 80 points over 2 min, and the watchdog stopped FreeCAD). `part_loft` estimates it first from profiles x points and, past a minute, refuses once with the estimate and the lighter way: split it into runs of profiles (each run starting on the profile the last ended on) and `part_boolean fuse` them, or fewer points a profile (`samples`). The same call again runs it, with a longer deadline. Past its time it stops and says so; a loft kept late answers `unchecked` — run `body_check` on it.
- `strays` in the answer is how far the result lies from the points it was built from (largest and mean, and which profile). Check it before you trust a rebuilt or ruled loft against a scan.
- For smooth cross-sections, use `part_wire { kind: "bspline", closed: true, points }`: one closed wire (`fit.maxDistance` is how far it lies from the points). Use 12 to 32 points for each section, and the same number for each section.
- Many sections: write the points to a file in the session's folder and pass the path, not the numbers. `part_loft { profiles_file: "sections.json", smooth: true }` takes every profile at once (a JSON list of `[[x,y,z] …]` lists, an object of them with `key` naming the list, or a CSV of x,y,z rows, profiles apart by blank lines or named in a first column); `part_wire` and each profile take `{ points_file, key }`. 26 sections of 24 points are about 12 KB of text, and roughly 4,000 tokens each time they are sent; a path is a few tokens. `batch { path: "calls.json" }` does the same for a long list of calls.
- "sound" means valid, closed and a volume above 0. Do not fuse a body that is not sound: `part_boolean` refuses it and keeps the tool.
- A boolean of many faces (a mesh made a solid) can take minutes, and the window does not respond until it is done. The first call gives the time and runs nothing; the same call again runs it. Use fewer faces first (`part_refine`), or do the boolean on the meshes (`meshobj_boolean`).

## Wires, splitting, repair
<!-- later: when the part needs a curve or a path (part_wire), a split, a section, slices, a repair or a solid from a mesh -->
- `part_wire` makes FreeCAD's own parametric curves: a helix as a sweep path (a spring, a thread), a spiral, a regular polygon (`polygon`: sides and radius), a polyline through your corners (`polyline`: points, closed), a plane to slice with, a B-spline through points. For a solid from corner points in one step, use `part_extrude { profile: { points } }`.
- `part_split { mode: "slice", bodies: [one], tools: [a plane or bodies] }` cuts a body into pieces; `explode: true` makes each its own body. `fragments` keeps every overlap region apart (for multi-material prints); `xor` keeps what is in an odd number.
- `part_compound` groups bodies without fusing them, or `explode`s a multi-solid body.
- `part_refine` merges faces split by booleans; `fix: true` also repairs tolerances and closes a shell into a solid.
- `part_attach` makes a primitive, wire or datum follow a face, edge, vertex or whole object (see Attachment below). `part_face` is a face from closed wires, `part_ruled` a surface between two edges, `part_project` puts a wire onto a face.
- `part_slices` gives a stack of cross-sections: outlines and areas. `part_from_mesh` turns a closed mesh into a solid. Curved areas stay faceted; for a clean model, fit features instead.
- `part_section` gives the curves where a body meets another body or a plane (face: true fills closed loops). `part_offset2d` grows or shrinks a flat outline in its plane (fill: true makes the band). `part_extract` copies faces, edges or whole shapes out as a body of their own, or builds a wire, face, shell or solid from them. `part_defeature` takes a hole, boss or fillet off a solid by all its faces. `part_fix` reverses, sews, closes into a solid or repairs. `part_datum` makes datum points, lines, planes and coordinate systems, attached so they follow.

## Parametric or plain
- Stay parametric (their properties can be changed later with `object_set`): `part_primitive` (Box Length / Width / Height; Cylinder Radius, Height, Angle; Cone Radius1 base, Radius2 top; Sphere Radius; Torus Radius1 ring, Radius2 tube; Prism Polygon, Circumradius, Height; Wedge Xmin … Z2max; tube OuterRadius, InnerRadius, Height), `part_wire` (all but bspline), `part_split`, `part_join`, `part_compound`, `compound_filter`, `compound_explode`, `part_ruled`, `part_section` with another body, `part_offset2d` of an open wire or a face, `part_datum`.
- Everything else works on the shape itself and leaves a plain shape (Part::Feature) with no history: booleans, fillets, chamfers, offset, shell, extrude, revolve, loft, sweep, mirror, scale, arrays, refine, fix, defeature. There is no Part::Cut, Part::Fillet or Part::Extrusion object to edit afterwards; `history_undo` takes a step back.
- Elements are numbered from 1 (`Face1`, `Edge1`, `Vertex1`), in the shape's own order. Any step that leaves a plain shape renumbers them. Ask `shape_query` again after each step; pick by `query` where a tool takes one.
- Where things sit: a box has a corner at `at`; a cylinder, cone, prism and tube stand on `at` (base centre) along +z or `direction`; a sphere and torus are centred on it; a `part_wire` plane has a corner at `at`, its other curves their centre. `rotate` turns about `at`.

## Attachment
<!-- later: when using part_attach or part_datum { to } -->
- `part_attach` and `part_datum { to }` take one reference. The modes FreeCAD's attacher has for one reference: a flat face `FlatFace`; an edge `NormalToEdge`, `FrenetNB`, `Concentric` (a circle or arc); a vertex `Translate`; a whole object `ObjectXY`, `ObjectXZ`, `ObjectYZ`. A datum line takes `TwoPointLine` (a straight edge) or `AxisOfCurvature` (a circle or arc); a datum point `Vertex`, `CenterOfCurvature`, `CenterOfMass`.
- Modes that need two or three references (`TangentPlane` and a line's `FaceNormal`: a face and a vertex; `ThreePointsPlane`) cannot be reached with one `to`. A line datum on a face therefore needs a `mode` of its own (`AxisOfInertia1` …) or no attachment (`at` and `normal`).
- An attachment names a face or edge by number. A boolean or fillet on the support renumbers it, and the attached object then follows another element: attach to datums or to primitives that stay parametric.

## Heavy steps
<!-- later: before a boolean of many faces, a loft of many profiles, part_from_mesh, or a fused array of many copies -->
- These freeze FreeCAD's window while OCC works and cannot run as a background job (jobs are for reads): booleans of many faces, lofts of many profiles and points, `part_from_mesh`, fused arrays of many copies, offsets and shells of free-form bodies.
- `part_boolean` and `part_loft` are estimated first; past a minute the first call answers with the estimate and runs nothing, and the same call again runs it.
- `part_from_mesh` makes a face of every triangle: it refuses a mesh over `maxFacets` (60000 by default), and far smaller ones are already slow in every later boolean. Reduce the mesh first (`meshobj_decimate`), do the boolean on the meshes (`meshobj_boolean`), or fit features to the scan instead.
- `part_transform` arrays: `fuse: false` keeps the copies apart in one body and is far quicker than fusing many.

## Compounds
<!-- later: when exploding or filtering a compound, or reading part_slices -->
- `part_compound { explode }` copies each solid out as a plain body. `compound_explode` is FreeCAD's Explode compound: filter objects that follow the compound.
- `compound_filter` keeps pieces by number from 0 (`items`), by touching a stencil or not (`collision-pass`, `collision-fail`), or by size as a percent of the largest piece (`window-volume`, `window-area`, `window-length`) or distance from a stencil (`window-distance`).
- `part_slices` measures `at` from the origin along the normal; `range` in its answer is the body's reach along it. Each slice's `area` is the material's: loops inside loops are holes.
