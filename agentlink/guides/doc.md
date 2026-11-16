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

## names and labels
- Every object has a `name` (FreeCAD's internal one: fixed when it is made, unique, ASCII) and a `label` (what the person sees; `object_rename` changes it). Tools take either; the name wins when both match. FreeCAD keeps labels apart by itself unless its duplicate-labels preference is on.
- Documents too: `doc_new { name }` gives the label, and FreeCAD makes the internal name from it. `doc_save { path }` under a new file name relabels the document after the file (`labelWas` in the reply); the name stays.
- `doc_close { documents }` takes names, labels or `.FCStd` paths. Two documents with one label are told apart by name ("Label (Name)" in refusals; `doc_switch` with no arguments lists both). There is no `save` input: a changed document is refused until `doc_save`, or closed and its changes lost with `discard: true`.

## setting properties
- `object_get { object, filter }` gives each property's `type`, `readOnly`, `hidden` and an enumeration's `choices`.
- Lengths, angles and other quantities take a number (mm, degrees) or a string with a unit (`"1 in"`, `"30 deg"`); plain floats take numbers only. Integers and percents take whole numbers. Vectors are `[x, y, z]`; a link is the other object's name or label (`null` clears it); a list of links is a list of names.
- Links to faces or edges (`PropertyLinkSub…`: a sketch's support, a fillet's edges) are not set here: the tool that made the object sets them again.
- `recompute` runs only what is touched. `force: true` reruns everything, also when the document's skip-recompute switch is on (`object_freeze { skipRecompute }`). Its `recomputed` is FreeCAD's count of objects run; `errors` lists the failed ones with FreeCAD's reason.
- `object_delete` refuses while something uses the object: FreeCAD itself would delete it and leave the users broken, which is what `force: true` allows.

## links, copies, groups
- `link_make` / `object_group { action: "link" }` make App::Link objects: the original shown again, following every change. A link's placement stands in for the original's own (LinkTransform is false), it is not added to it. `count` makes an array whose elements start on top of one another: each is an object, placed with `object_set`.
- `object_duplicate` copies: still built from the same inputs unless `dependencies: true`; `simple: true` is the shape alone.
- A folder (`kind: "folder"`) only sorts the tree. A part (`kind: "part"`, App::Part) has a Placement that moves what is in it. An object sits in one group at a time.
- `object_freeze` needs the window (FreeCAD 1.1 has no headless call) and the frozen state is not saved with the file; `skipRecompute` works anywhere.
- `doc_merge` brings another .FCStd's objects in; `doc_revert` goes back to the saved file by closing and reopening it, so the session's undo steps go too.

## traps
- `import_file` of STEP, IGES or BREP reads the shape only: one body for the file (or one per solid with `split: true`), without the file's colours, part names or assembly structure.
- `import_file` of a DXF reads lines, arcs, circles, ellipses, polylines (2D and 3D, closed ones closed) and splines itself. A drawing with blocks, text or dimensions goes through FreeCAD's importer. `read` says which, and what failed. Many objects come back as counts and the first few names.
- `doc_new` and `doc_open` are not undo steps and a batch's rollback does not reach past them.
- A mesh file always comes in as a mesh, whatever its size. Use `import_file { solid: true }` for a body (up to 200000 triangles), or the mesh tools (`meshobj_info`, `meshobj_repair` …) on the mesh.
- A body imported from a mesh is made of triangles: measure, section and booleans work; fillets and `shape_query` by radius do not see round faces.
- Booleans and fillets bake a parametric primitive into a plain shape: after that only `Placement` can be set.
- `object_rename` does not carry setups, specs or waivers kept under the old label.
- `object_group` puts objects in folders or App::Part containers, dissolves groups, and makes App::Link copies that follow their original.
- A picture of the parts is `view_render` (the view group), headless or not.
