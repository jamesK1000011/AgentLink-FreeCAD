<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Point clouds (Points, Reverse Engineering)

Everything is mm, in the document's coordinates: a cloud that was moved is read where it stands. Only positions are kept (no colours or normals).

## workflow
1. `points_import` reads a cloud: .asc/.xyz/.txt/.csv (x y z a line), .pcd, .ply, .e57. `every` thins a huge file as it comes in; `scale` turns metres (1000) or inches (25.4) to mm.
2. `points_info` gives the count, extent, centre and typical spacing; `view_render` shows it.
3. `points_crop` isolates one feature before a fit: a `box`, a ball (`near` + `radius`), the side of a `plane`; `outside: true` keeps the rest instead; `specks` drops strays; `thin` (mm) keeps one point per cell. It cuts the cloud itself down unless `replace: false`.
4. `points_fit` through the cropped points:
   - `plane`: centre and normal (a face's flatness is its `max`);
   - `sphere`: centre and diameter;
   - `cylinder`: base, axis, diameter and length — a bore or a shaft; `axis` is a hint for a short one;
   - `surface`: a free B-spline sheet (Reverse Engineering), always kept as an object;
   - `curve`: a B-spline through a line of points (an edge scan); a loop round a centre closes itself.
   Read `rms` and `max`: the points' distance from the shape. A large `max` means the crop holds more than the one feature. `tolerance` gives a verdict; `make: true` keeps the shape as an object to model on.
5. `points_mesh` makes a mesh: `height` (one side, gridded), `hull`, or `poisson`. `points_merge` joins clouds.
6. `points_export` writes .ply (binary), .pcd, .asc/.xyz or .csv and reads the file back: `readBack` should equal `count`.

## testing a fit
`points_sample` spreads points over a body or mesh, with `noise` in mm, so a fit can be tried on a known shape first: a 20 mm cylinder sampled without noise fits back to radius 10 with `max` near the sampling `tolerance`.

## traps
- A cylinder fit needs the points of that cylinder only. A floor, an end cap or a chamfer left in pulls it off: sample or crop the wall alone.
- `points_sample` on a whole solid takes every face, the ends of a cylinder and the six sides of a box included: crop before a fit.
- `surface` fits one sheet seen from one side (a height field over the points' own plane). It cannot wrap round a part, and needs at least poles × poles points.
- `points_mesh { method: "height" }` is the same kind of thing: a mesh of one side. `poisson` needs a FreeCAD built with the Point Cloud Library and is refused `unavailable` without it.
- .ply is written as 32-bit floats (about 7 digits): far from the origin use .asc or .csv for full precision.
- `points_structure` suits only a cloud still in its scan order, rows × columns.
- A scan kept in an add-on's session, not in the document, is measured with that add-on's tools; export it as a cloud to use these.
