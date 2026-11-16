<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Meshes in the document

These tools work on FreeCAD's mesh objects: an imported STL, a body meshed with `meshobj_from_shape`, a split piece. A scan kept in an add-on's session is measured with that add-on's own tools.

## workflow
1. Get a mesh: `import_file` an STL/OBJ/PLY/3MF (it comes in as a mesh unless you give `solid: true`), or `meshobj_from_shape { body, method }`. Use `mefisto` for even triangles (for FEM or textures), `standard` for a close fit.
2. `meshobj_info` evaluates it as the Mesh workbench does. If there are problems, `meshobj_repair`. `fix: ["holes"]` and `["islands"]` are opt-in, because filling and dropping change the shape.
   `meshobj_primitive` makes a mesh box, sphere, cylinder, cone or torus; `meshobj_merge` puts meshes into one object; `meshobj_boundary` gives the open edges (holes, rims) as wires.
3. Change it: `meshobj_decimate` (lighter), `meshobj_refine` (denser), `meshobj_smooth` (taubin keeps the size), `meshobj_offset`, `meshobj_trim` by a plane, `meshobj_transform`, `meshobj_boolean` (closed meshes only).
4. Read it: `meshobj_sections` for outlines along an axis, `meshobj_segments` for its flat regions (on a scan, where to put a sketch), `meshobj_curvature`, and `view_render { map: "curvature" }`.
5. `meshobj_export` or `export` writes it out; `part_from_mesh` turns a closed one into a solid.

## traps
- Each change replaces the mesh in place: `copy: true` keeps the original beside it. `meshobj_edit { action: "begin" }` works on a copy until `use`.
- A mesh boolean needs both meshes closed (`meshobj_info` → `solid: true`).
- `meshobj_trim` removes the side `normal` points to and leaves a hole where it cut: `close: true` caps it.
- `meshobj_refine` does not split a triangle in four: each round puts a point in the middle of every triangle (about three times as many) and swaps edges. The surface is the same; use it before smoothing or texturing, not to add detail.
- `meshobj_decimate`'s `tolerance` caps the error one collapse may add, so it can stop before the count you asked for. The reply says when; raise `tolerance` if shape matters less than size.
- `meshobj_offset` moves every point along its normal and collapses triangles that turn over. Inward past the tightest radius it damages the mesh: run `meshobj_info` after.
- `meshobj_transform` scales, turns and mirrors about the document's origin, also for a mesh that has a placement of its own. `meshobj_merge` joins meshes where they stand.
- `meshobj_segments { kind: "curvature" }` finds regions whose two curvatures are both within `tolerance` (1/mm) of 0, so flat ones, like `planar` but judged by curvature instead of distance from a plane.
- `meshobj_sections`' `at` distances run from the document's origin along `normal`, not from the mesh's end.

## numbers to expect
- The standard mesher gives two triangles for each flat four-sided face: a box is 8 points and 12 facets at any deflection. Curved faces grow as the deflection shrinks: a sphere's volume comes up towards 4/3 π r³ from below.
- `meshobj_primitive`: a box is 12 facets; a sphere, cylinder, cone and torus follow `segments`.
- A closed mesh obeys points − edges + facets = 2 for each piece without through-holes, so facets = 2 × points − 4.

## size and time
No timings were measured for these; treat them as order-of-magnitude guidance.
- Past about 200,000 triangles `meshobj_info` (the self-intersection test), `meshobj_repair` (it evaluates before and after), `meshobj_segments` (it walks every region) and `meshobj_boolean` get slow. A changing tool cannot run as a job, so decimate a copy first if the answer does not need the full mesh.
- The reads can run as jobs: `meshobj_info`, `meshobj_curvature` and `meshobj_export` take `background: true` (then `job_status`).
- `meshobj_refine` is refused past 2,000,000 triangles; `meshobj_split` past 100 pieces; `meshobj_unwrap` of a mesh past 50,000 triangles; `part_from_mesh` past 60,000.

## laid flat
`meshobj_unwrap { of: "Body.Face3" }` lays a surface flat as a cutting pattern (sheet metal, fabric, leather); `of` may also be an open mesh in one piece (a closed one is refused: trim or segment a patch off it first). Cylinder and cone sides roll out exactly: a cone frustum gives the two radii and the angle of its fan. Other surfaces go through FreeCAD's unwrapping where it works, which reports how much they stretch. `path` writes the pattern as SVG or DXF.
