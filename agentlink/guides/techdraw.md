<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# TechDraw, piece by piece

These tools build a TechDraw page one object at a time, so the drawing says exactly what the person asks and they can carry on with it in the GUI.

## workflow
1. Ask about the projection first: first angle (ISO, Europe) or third angle (ASME, North America). Then `td_page { action: "new", paper: "A3", projection: "first" }`. `td_page { action: "templates" }` lists the build's templates; `template` takes any SVG.
2. Fill in the title block with `td_title { fields }`. With no fields it lists the template's own field names. Ask the person for the names, numbers and dates; nothing is filled in for them. A preset saves their usual fields: `td_title { preset: "mine", save: true }`, then `{ preset: "mine" }` on the next page. `export` and `import` move presets between machines as JSON.
3. Put the part on with `td_projection { views: ["front", "top", "right", "iso"] }`, or a single view with `td_view { direction, scale, at }`. A view with no `scale` takes the page's (`td_page { scale }`). Each answer carries the view's label — the name every other `td_` tool takes — and its edge count.
4. Add sections and details: `td_section { view: "Front", normal: "y", through: [x, y, z] }` and `td_detail { view, center: [x, y, z], radius }`.
5. Dimension: `td_geometry { view, kind: "circles" }` shows what can be measured, then `td_dim { view, type, refs }`. Name geometry by the part where you can: `{ circle: { diameter: 6, near: [x, y, z] } }`, `{ point: [x, y, z] }`, `{ edge: { through: [p, q] } }`. The whole size of a view without picking anything: `td_dim_special { view, kind: "extent_h" }` and `extent_v`.
6. Tolerance it: `td_dim { …, fit: "H7" }`, or plus and minus, or `basic: true`; `td_tolerance { dimension }` changes one later.
7. Add GD&T: `td_datum { view, letter: "A", on }`, then `td_gdt { view, on, frame: [{ characteristic: "position", tolerance: 0.1, diameter: true, modifier: "M", datums: ["A", "B"] }] }`.
8. `td_list` reads the page back. `td_export { formats: ["pdf", "dxf"] }` writes it out.

## coordinates
- Page `at` is in millimetres from the paper's bottom-left corner, y up.
- A dimension's or balloon's `at` is its text's offset from its view's centre, in page millimetres.
- `td_geometry` gives millimetres on the part, in the view's own plane.

## references: numbers or the part
- `Edge3` and `Vertex5` are TechDraw's own names, counted from 0, in the order its hidden-line pass hands the geometry over. They move whenever the view is drawn again after the part, the direction or the scale changes — a dimension made on `Vertex4` can then sit on another corner or lose its reference (`td_dim_repair` points it again).
- References by the part are looked up each time against the view as it is: `{ point: [x, y, z] }` the vertex drawn there, `{ circle: { diameter, near } }` a round edge of that size, `{ center: { diameter, near } }` a hole's centre (a cosmetic vertex is made when the view has none there), `{ edge: { through: [p, q] } }` the edge through two points.
- A **diameter** named by `{ circle }` takes whole circles only. A slot's end or a fillet is an arc of the same size and is never taken for a hole: with only arcs of that size the call is refused and names `type: "radius"`. `td_geometry { kind: "circles" }` marks each round edge `circle` or `arc`. An arc named outright (`"Edge7"`) still takes a diameter, as TechDraw allows, and the answer notes it.
- Dimensions are measured as projected on the paper (TechDraw's MeasureType Projected): right in the six orthographic views, foreshortened in an iso view (a 53 mm edge reads 43.27). `td_dim_special { kind: "axo_length" }` writes the true length there.

## traps
- A view's lines are worked out by TechDraw's hidden-line pass: at once with no window, on a worker thread in the window, where the tools wait for them (up to 30 s; a view with nothing to draw waits that long). A view that has just been made answers with its edge count; if it is 0, the source is empty or hidden.
- In a projection group the front's direction is set before the other views are added: TechDraw works each one out from the front as it is then. `front` turns the whole group.
- A section's `normal` points toward the person looking at the section, and it must lie across the base view (along the paper, not out of it).
- A point that is hidden in a view has no vertex there. Dimension it in a view that sees it, or in a section.
- Form tolerances (flatness, straightness, circularity, cylindricity) take no datum. Orientation, runout, concentricity and symmetry need one. A refusal says which.
- SVG and PDF are drawn here from the page's objects: views, dimensions, frames, leaders, notes, balloons, tables, centre marks, hatching and cosmetic lines; TechDraw's own PDF and SVG export (TechDrawGui) needs the window. The template's artwork is left out (the title block's fields are kept). DXF comes from TechDraw itself (`TechDraw.writeDXFPage`).
- Drawn by `td_export` only, not in FreeCAD's window: `td_centermarks`, `td_hatch` and the symbol of `td_weld` (its leader shows). `td_cosmetic`'s lines are FreeCAD's own cosmetic edges from 1.1 on and show in both.
- `td_section { hatch: false }` sets the section's CutSurfaceDisplay to Hide, TechDraw's own word for a plain cut.

## centre marks and hatching
- `td_centermarks` puts thin chain crosses on the holes and round edges of views; `extend` is how far past the circle they run.
- A section's cut faces are hatched in exports by themselves. `td_hatch { view, faces, spacing, angle }` hatches other faces of the part; holes stay clear. A face seen edge-on has nothing to hatch, and the answer says so.
- `td_weld` puts a weld symbol on a leader from a feature (fillet, V, bevel, square, U, J, plug, spot, seam, flare, backing, surfacing), with size, length or pitch, arrow or other side, all-around, field weld and a tail note.
- `td_cosmetic` adds centrelines between a shaft's or hole's sides, thread marks (side and end views, ISO coarse pitch by default), and cosmetic lines and circles. `td_leader` points a note at a feature. `td_finish` puts an ISO 1302 surface texture symbol on a surface (Ra, machining required or not, process, lay). `td_area` writes a face's area with a leader.
- `td_dimset` dimensions several points at once along one direction: `chain` (each to the next) or `baseline` (each from the first, in stacked lanes). A hole is dimensioned to its centre with `{ center: { diameter, near } }`, which also works in `td_dim`.
