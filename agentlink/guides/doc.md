# The document: files, objects, properties
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

## workflow
- `object_list` to see what is there (names, labels, types, what uses what); `object_get { object, filter }` for one object's properties.
- `object_set { object, values }` changes sizes of parametric objects (a primitive's `Length`, `Radius`) and any object's `Placement`; it recomputes the object and what is built from it, and is refused, and undone, when that recompute fails.
- `Placement` takes `at`, `axis`, `angle` (degrees) or FreeCAD's own `Base`, `Axis`, `Angle`, or `Rotation { axis, angle }` or `[x,y,z,w]`. The case of the keys does not matter. A key you leave out keeps its value: `{ at }` moves the part and keeps its turn. Other keys are refused.
- Read `unchanged` in the answer of `object_set`: it names each value that is the same as before.
- `import_file` brings STEP, IGES, BREP (bodies); STL, OBJ, 3MF, PLY, OFF, AMF, glTF, Collada, VRML, 3DS (meshes, `Mesh::Feature`; `solid: true` makes a body of the triangles); DXF and SVG (Draft geometry); and PNG/JPG/BMP pictures as an image plane `width` mm wide to trace over.
- `export` writes and reads back — check `verify`:
  - solids: STEP, IGES, BREP (`verify.volumeDiff`);
  - one mesh: STL, OBJ, 3MF, PLY, OFF, VRML (wrl), X3D. A mesh object (`Mesh::Feature`) goes as it is, STL by default;
  - a scene for viewers, web pages and render programs, a mesh and colour per object: glTF (glb, gltf) and Collada (dae), with `colors {label: "#rrggbb"}`;
  - 2D for laser, plasma and waterjet cutters or another CAD program: DXF (R12) or SVG of a `view` (top, front, right, … iso; `hidden: true` puts hidden lines on their own dashed layer), or of a `section` at z mm. Circles and arcs stay true circles and arcs. For a dimensioned drawing, use TechDraw (`td_export`).
- `doc_save` before `doc_new` or `doc_open`: those switch the session to another document.

## traps
- `import_file` of a DXF reads lines, arcs, circles, ellipses, polylines (2D and 3D, closed ones closed) and splines itself. A drawing with blocks, text or dimensions goes through FreeCAD's importer. `read` says which, and what failed. Many objects come back as counts and the first few names.
- `doc_new` and `doc_open` are not undo steps and a batch's rollback does not reach past them.
- A mesh file always comes in as a mesh, whatever its size. Use `import_file { solid: true }` for a body (up to 200000 triangles), or the mesh tools (`meshobj_info`, `meshobj_repair` …) on the mesh.
- A body imported from a mesh is made of triangles: measure, section and booleans work; fillets and `shape_query` by radius do not see round faces.
- Booleans and fillets bake a parametric primitive into a plain shape: after that only `Placement` can be set.
- `object_rename` does not carry setups, specs or waivers kept under the old label.
- `object_group` puts objects in folders or App::Part containers, dissolves groups, and makes App::Link copies that follow their original.
- A picture of the parts is `view_render` (the view group), headless or not.
