# Measuring and picking geometry
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

## workflow
- `shape_query` finds faces, edges and vertices by type, normal or axis, radius, area, length, nearness to a point or a box: the references ("Face12", "Edge3") the modelling tools take. `of: "Face6"` gives that face's edges.
- `measure { a }` reads one thing (area, radius, diameter, length, volume); `measure { a, b }` the least distance, and the angle between flat faces or lines (and the gap between parallel faces).
- `section` cuts the body with a plane: area and outlines as [u, v] points in the plane.
- `measure_mass` with a material or density (solid); `clearance` between two bodies says clear, touching or interference with the overlap's volume.

- `measure_keep` leaves a FreeCAD Measure object in the document. It takes elements only ("Body.Edge3"), and what FreeCAD's own types take: distance (two of vertex, edge, flat or cylindrical face), angle (two straight edges or flat faces), length (edges), area (faces), radius (one circular edge, not a cylinder's face), position (one vertex). FreeCAD 1.1 has no kept diameter.

## reading the answers
- Everything is mm, mm², mm³ and degrees; mass in g, density in g/cm³, inertia in g·mm².
- The angle between two flat faces is between their outward normals: 180 for the two sides of a plate, 90 for a corner. Between two straight edges it is 0 to 90.
- `distance` is the least distance between the two things as bounded; `gap` (parallel faces) is the distance between their planes; `centers` is between two round things' centres.
- FreeCAD's own "mass" of a shape is its volume: `measure_mass` multiplies by a density, from `material` (a stock key, or a `material_list` id or name), `density`, or what `material_set` recorded for the body.

## traps
- References go stale after a change: query again.
- Give what `shape_query` answers to the tools that take faces or edges (`pd_fillet`, `pd_chamfer`, `pd_draft`, `pd_thickness`, `fea_hold`, `fea_load`): a reference ("Face8", "Body.Face8"), a list of them, an item as it came, or the same filters (`{ type: "circle", radius: 3 }`). A filter with `near` and no `limit` takes the nearest one.
- References are "Face12" with `body`, or "Box.Face12"; a bare body name means the whole body, a list [x, y, z] a point.
- Normals are outward; `axis` matches either way along a line or a hole's axis.
- `measure_mass` treats the body as solid; a printed part with infill weighs less; an add-on for printing may estimate that.
