# Modelling with Part
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

## workflow
1. Block the part out with `part_primitive` (box, cylinder …; `at` and `rotate` place it; `direction [x,y,z]` points the axis of a cylinder, cone, prism or tube) or `part_extrude` / `part_revolve` a profile (`{ points }`, `{ circle }`, a sketch, or a body's face "Box.Face6").
2. Add and remove material: `part_boolean { op, base, tools }`, or in one call `part_extrude { profile, into, op: "cut" }` for a pocket or `op: "fuse"` for a boss.
3. Repeat and mirror with `part_transform` (linear, polar, mirror { fuse: true }).
4. Shell with `part_thickness`, then round and bevel last: `part_fillet` / `part_chamfer` with edges picked by `shape_query` or a `query`.
5. `body_check` after each change; `history_diff` says what it did.

## traps
- Face and edge numbers change after every modelling step: query again (`shape_query`) rather than reuse old references.
- A result keeps the base body's label, so setups and specs follow it; the tools are removed (keep: true hides them, and a hidden body is still listed).
- A refusal for "changed nothing" means the pieces do not overlap: move them (`part_transform move`) and try again.
- Fillets bigger than a face beside the edge, or shells thinner than a fillet, fail: smaller sizes, or the shell before the fillet.
- Loft profiles with different edge counts twist; start each at the matching corner. `part_loft` turns each profile to run the same way round and starts each at the point nearest the one before (`aligned` says what it changed). It keeps no loft that is invalid, open, inside out or bulges more than 15% beyond its profiles (measured on the surface itself, not its control points); the refusal gives the reason and names the spans that bulge (`profiles 11–12 by 37% along y`).
- A smooth loft through many real sections (a scan's, with local notches) can overshoot between them. `part_loft` tries again by itself: the profiles rebuilt as B-splines through the same points with one set of knots, then `maxDegree` 3 and 2 (stiffer), then span by span with the bulging spans ruled and sewn into one (kept only if sound; `segments: false` turns that off). `route` says what it did. Give `maxDegree: 3` up front for long runs of uneven sections.
- `ruled: true` turns each profile into a polygon of the same number of points (spread by arc length, seams lined up; `samples` sets how many), so a ruled loft always pairs up; B-splines given as they are failed it. Two profiles that OCC will not loft smoothly are ruled the same way, since a loft between two profiles is straight anyway.
- `strays` in the answer is how far the result lies from the points it was built from (largest and mean, and which profile). Check it before you trust a rebuilt or ruled loft against a scan.
- For smooth cross-sections, use `part_wire { kind: "bspline", closed: true, points }`: one closed wire (`fit.maxDistance` is how far it lies from the points). Use 12 to 32 points for each section, and the same number for each section.
- Many sections: write the points to a file in the session's folder and pass the path, not the numbers. `part_loft { profiles_file: "sections.json", smooth: true }` takes every profile at once (a JSON list of `[[x,y,z] …]` lists, an object of them with `key` naming the list, or a CSV of x,y,z rows, profiles apart by blank lines or named in a first column); `part_wire` and each profile take `{ points_file, key }`. 26 sections of 24 points are about 12 KB of text, and roughly 4,000 tokens each time they are sent; a path is a few tokens. `batch { file: "calls.json" }` does the same for a long list of calls.
- "sound" means valid, closed and a volume above 0. Do not fuse a body that is not sound: `part_boolean` refuses it and keeps the tool.
- A boolean of many faces (a mesh made a solid) can take minutes, and the window does not respond until it is done. The first call gives the time and runs nothing; the same call again runs it. Use fewer faces first (`part_refine`), or do the boolean on the meshes (`meshobj_boolean`).

## Wires, splitting, repair
- `part_wire` makes FreeCAD's own parametric curves: a helix as a sweep path (a spring, a thread), a spiral, a regular polygon (`polygon`: sides and radius), a polyline through your corners (`polyline`: points, closed), a plane to slice with, a B-spline through points. For a solid from corner points in one step, use `part_extrude { profile: { points } }`.
- `part_split { mode: "slice", bodies: [one], tools: [a plane or bodies] }` cuts a body into pieces; `explode: true` makes each its own body. `fragments` keeps every overlap region apart (for multi-material prints); `xor` keeps what is in an odd number.
- `part_compound` groups bodies without fusing them, or `explode`s a multi-solid body.
- `part_refine` merges faces split by booleans; `fix: true` also repairs tolerances and closes a shell into a solid.
- `part_attach` makes a primitive follow a face. `part_face` is a face from closed wires, `part_ruled` a surface between two edges, `part_project` puts a wire onto a face.
- `part_slices` gives a stack of cross-sections: outlines and areas. `part_from_mesh` turns a closed mesh into a solid. Curved areas stay faceted; for a clean model, fit features instead.
- `part_section` gives the curves where a body meets another body or a plane (face: true fills closed loops). `part_offset2d` grows or shrinks a flat outline in its plane (fill: true makes the band). `part_extract` copies faces, edges or whole shapes out as a body of their own, or builds a wire, face, shell or solid from them. `part_defeature` takes a hole, boss or fillet off a solid by all its faces. `part_fix` reverses, sews, closes into a solid or repairs. `part_datum` makes datum points, lines, planes and coordinate systems, attached so they follow.
