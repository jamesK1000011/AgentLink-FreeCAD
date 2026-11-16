<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Surfaces (the Surface workbench)

Two kinds of tool share this group. `surface_sections`, `surface_boundary`, `surface_extend`, `surface_sew`, `surface_cut` and `surface_blend` make the Surface workbench's parametric features: each follows the edges it was made from, and its properties can be changed with `object_set`. `surface_fill`, `surface_loft`, `surface_points`, `surface_polynomial` and `surface_thicken` make plain surfaces (a shape with no history). Every changing reply may carry `health` (`ok`, `verdict`, `todo`).

## workflow
1. Draw the curves: `draft_shape { kind: "bspline" }`, `part_wire` (B-spline, arc …), sketches, or a body's edges (`"Body.Edge3"`; `shape_query` finds them).
2. Make the surface: `surface_sections` through curves in order, `surface_boundary` from 2–4 edges that meet end to end (`fill: "coons"` is smoothest), `surface_fill` across any closed boundary, or `surface_extend` to run a face on past its edges.
3. Close it up: `surface_sew` sews the pieces into a shell, and `solid: true` makes a closed shell a body. For a single open surface, `surface_thicken` or `part_thickness` gives it a wall.
4. `surface_blend` joins two edges with a smooth curve (`continuity` 1 for tangent, 2 for curvature), which then becomes a boundary for the next surface. `surface_cut` trims a surface by a solid.

## what each feature takes (FreeCAD 1.1)
- **Sections** (`Surface::Sections`, property `NSections`): two or more curves, each one edge. A wire or sketch named whole gives one section per edge. The curves must run the same way and not cross; a twist means one is backwards.
- **Boundary** (`Surface::GeomFillSurface`: `BoundaryList`, `ReversedList`, `FillType` Stretched | Coons | Curved): two, three or four edges in all. List them going round. Lines, arcs and circles are converted to B-splines. Coons and Curved want opposite curves that match; when FreeCAD refuses them the tool makes a `Surface::Filling` through the same edges and says so in `note`.
- **Extend** (`Surface::Extend`: `Face`, `ExtendUNeg` / `ExtendUPos` / `ExtendVNeg` / `ExtendVPos`, `Tolerance`, `SampleU` / `SampleV`): the face is sampled 32 × 32 over its whole u, v range, run on by the given share at each end, and refitted as one B-spline surface to within `Tolerance` (0.1 mm). So the result is an approximation, always four-sided: holes and a trimmed outline are lost. `object_set` can set the four ends apart once `ExtendUSymetric` / `ExtendVSymetric` are false.
- **Sewing** (`Surface::Sewing`: `ShapeList`, `Tolerance`, `SewingOption`, `DegenerateShape`, `CutFreeEdges`, `Nonmanifold`): only the faces listed are sewn; an object named whole brings all its faces. FreeCAD's own default tolerance is 1e-7 mm; the tool sets 0.01.
- **Cut** (`Surface::Cut`: `ShapeList` of exactly two): a boolean cut of the first by the second. A solid removes what lies inside it. A second surface removes nothing: the first comes back split where they cross.
- **Blend curve** (`Surface::FeatureBlendCurve`: `StartEdge`, `StartParameter`, `StartContinuity`, `StartSize`, and the same for `End`): `at` is a share of the edge's parameter range, not of its length. A blend that loops back on itself wants a negative `size` at that end (the wiki's own example uses -5 at both).

## traps
- Boundary edges must meet end to end within FreeCAD's tolerance. A gap reads as a failure ("Curves are disjoint"): snap the ends first, or use `surface_fill`, which says how far apart the ends are.
- A sewn shell is solid only if it is closed. The answer says when it is open (a missing face, or a gap wider than `tolerance`).
- Edge and face numbers (`Edge3`, `Face2`) change when the object they belong to is rebuilt: find them again with `shape_query`.
- `surface_polynomial` fits one quadric: right for a patch that is a single bowl or saddle, wrong for a whole part.
