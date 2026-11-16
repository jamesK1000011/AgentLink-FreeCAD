# Draft, Mesh, Surface hardening: findings

Checkout: the `draftmesh` copy of AgentLink-FreeCAD. Nothing was run on FreeCAD here: every fix is from reading FreeCAD 1.1 source (tag 1.1.0; the Mac runs 1.1.3) and each has a FreeCAD test that has not been run yet.

# 1. Draft (group "draft", 19 tools)

Checked against FreeCAD 1.1 source: `src/Mod/Draft/draftmake/*.py` (every maker the tools call), `draftfunctions/` (move, rotate, scale, mirror, offset, upgrade, downgrade, join, split, draftify, heal), `draftobjects/` (wire, circle, polygon, ellipse, rectangle, bspline, dimension, label, layer, hatch, facebinder, shape2dview, shapestring), `draftutils/utils.py` (annotation styles, modifier filters), `draftutils/gui_utils.py`, `draftutils/params.py`, `draftviewproviders/` (view_dimension, view_draft_annotation, view_wpproxy), `draftguitools/` (gui_annotationstyleeditor, gui_dimension_ops), `WorkingPlane.py`, `src/Mod/Part/App/AppPartPy.cpp` (makeWireString), `src/Mod/TechDraw/PAT/FCPAT.pat`; wiki `Draft_tutorial.md`, `Draft_ShapeString_tutorial.md`.

Files changed: `agentlink/families/draft_more.py`, `agentlink/families/draft.py` (descriptions only), `agentlink/families/cam_more.py` (draft_fix), `agentlink/data/tools.json` (draft_to_sketch description and refusal), `agentlink/guides/draft.md`, `tests/test_draft.py` (new class `DraftHardening`, 5 tests). No new files.

## Bugs fixed (proved from source)

1. **draft_style wrote styles Draft 1.1 cannot read.** `ArrowType` was stored as a name. Draft reads a style back through `utils.repair_annotation_style`, which compares each value's Python type with its default's (an arrow type is an *index* into `ARROW_TYPES`) and passes a string to `float()`: `float("Arrow")` raises ValueError wherever Draft reads the document's styles (the style editor, an annotation's `AnnotationStyle` change). Now stored as Draft 1.1 does: `ArrowTypeStart` / `ArrowTypeEnd` as indexes (a name or an index is taken), `ArrowSizeStart` / `ArrowSizeEnd`, floats as floats; a name left by an older call is converted on the next `set`.
2. **draft_style apply never applied a style made after the object.** An annotation's `AnnotationStyle` is an enumeration whose list is fixed when its view provider is made; assigning a newer style's name raises, and the tool fell through to "recorded … no window here" with the window up. Now the list is refreshed first (the pattern Draft's own style editor uses), and objects already wearing a style follow a later `set` and are unstyled on `delete`.
3. **draft_dimension angular always answered 0 headless.** `Angle` is worked out in the view provider (`view_dimension.py`, "TODO: move the calculation of 'Angle' from the viewprovider"). `measures` is now the same sum from FirstAngle / LastAngle; reply also carries `unit`.
4. **draft_2d_view section: true gave a silently empty view.** `Shape2DView.execute` handles `Cutlines` / `Cutfaces` only when Base is a BIM SectionPlane; on a body it prints "mode not implemented" and sets no shape. Now refused with what to use instead; an empty view carries `warning`.
5. **draft_modify join reported success when nothing joined.** `join_wires` returns the list of wires left, joined or not (always truthy). Now compared with what went in; non-Draft-wires are refused up front (they have no `Points`, which raised AttributeError).
6. **draft_modify upgrade on one open Draft wire said "Nothing to upgrade" after changing it.** Draft closes the wire in place (`closeWire`: `obj.Closed = True`, nothing in the add list). Now recognised as done.
7. **draft_modify offset on a Draft circle raised.** `Draft.offset` takes the *new radius* (a number) for a circle, not a vector. The radius is now that of the circle through its first vertex moved by `by`. A Draft B-spline (Draft wants the new point list, worked out in its window) is refused, naming part_offset2d.
8. **draft_modify split lost a closed wire's closing segment.** The tool cut the point list and set `Closed = False`, dropping the last-to-first segment. Now as Draft's `split_closed_wire`: that segment becomes its own wire and the rest one open wire; `edge` may name the closing segment. On an open wire `at` is projected onto the segment (Draft projects it; a point off the segment bent the wire) and a point beyond its ends is refused. The reply now lists both pieces (it listed only the new one).
9. **draft_fix heal { objects } raised after healing.** Draft removes each healed original; the reply then read `.Label` off deleted objects (ReferenceError). Labels are read first; the reply counts what was rebuilt and removed. Both actions now record a step.
10. **draft_layer lineWidth on an existing layer was dropped**; now set on its view object when there is a window. (Putting an object on a second layer already takes it off the first: `Layer.onChanged`.)
11. **draft_hatch on an object with no flat face made an empty Hatch** (`Hatch.execute` returns quietly). Now refused; a hatch that drew no lines carries `warning`.
12. **draft_link_array circular with symmetry 0** fell into Draft's ortho branch (`make_array`: `if arg6:`) with a number as IntervalX. Counts, spacings and the path / points objects are now checked before Draft is called (Draft answers None with a console line, which reached the agent as "Draft made nothing from that").
13. **draft_label show area / length / … without object** made a label reading "No Target". Now refused.
14. **draft_clone scale on a BIM object** (cloned through Arch, no `Scale` property) raised; now refused with the clone removed. Scale is validated before the clone is made.

## Changed without proof (needs the live check most)

- **The 3D-view refusals.** With the window up `make_dimension` / `make_angular_dimension` call `gui_utils.get3DView().getViewDirection()` and `make_workingplaneproxy` reads `Gui.ActiveDocument.ActiveView.getCameraNode()`; both raise AttributeError when the tab in front is not a 3D view. draft_dimension and draft_plane now turn that into an `invalid_state` refusal and remove the half-made object. The refusal can only ask for the 3D view's tab to be brought forward: no core tool was found that does it. **Wish:** a way to activate the document's 3D view before Draft calls (in protocol or the shared runner), so these never fail unattended.
- **draft_modify offset side.** Which side a vector takes for wires and rectangles is `DraftGeomUtils.offsetWire`'s rule; not traced.

## Per tool

| Tool | Checked against | Fixed | Still doubtful / live check | Description |
|---|---|---|---|---|
| draft_2d_view | make_shape2dview, Shape2DView.execute, ProjectionMode list | #4, empty-view warning, shape check | length of a hidden-line view; that a top view of a box is exactly its outline | rewritten |
| draft_array | none in Draft (Part copies and fuse) | nothing | none | rewritten |
| draft_clone | make_clone (delta is a displacement; Clone2D for Part2DObjects; Arch route) | #14 | Clone2D of a sketch | rewritten |
| draft_dimension | make_linear_dimension, make_linear_dimension_obj (1-based, None on any bad input), make_radial_dimension_obj (GeomCircle only), make_angular_dimension, LinearDimension.execute, view_dimension | #3; vertex / edge numbers and the edge's kind checked first with the valid range; 3D-view refusal | the 3D-view refusal live; which pair Vertex1-Vertex2 of a faced rectangle is | rewritten |
| draft_facebinder | make_facebinder, Facebinder.addSubobjects / execute, Extrusion, Offset | refusal for a whole-object ref (was AttributeError on None) | extrusion direction on a curved face | rewritten |
| draft_fix | heal (manual mode force-rebuilds), Draft_FlipDimension (Normal negated) | #9; dimension check by its properties | heal on a really old file | rewritten |
| draft_fonts | none (file listing) | nothing | none | rewritten |
| draft_from_sketch | draftify, draftify_shape (wires of lines, one circle or arc; else a plain shape) | objects with no edges refused | none | rewritten |
| draft_hatch | make_hatch, Hatch.execute (flat faces only, .pat only, TechDraw's hatch), FCPAT.pat names | #11; scale over 0; file must be .pat | line length at a given scale | rewritten |
| draft_label | make_label, Label.execute, return_info, label types | #13; comment corrected (Draft fills the text headless too) | "Volume" and the "Label + …" types are not offered (a feature, left) | rewritten |
| draft_layer | make_layer (view properties only with a window), Layer.onChanged / addObject | #10; a layer as a member refused; headless note | none | rewritten |
| draft_link_array | make_ortho_array, make_polar_array, make_circular_array, make_array, make_path_array, make_point_array | #12; reply names the base | circular copy count; path align | rewritten |
| draft_modify | move, rotate, scale, mirror (always a Part Mirroring; plane from the working plane), offset, upgrade, downgrade, join_wires, make_fillet, split | #5 – #8; scale 0, mirror from = to, fillet that does not fit, a None result each refused with the reason | offset side; downgrade's result kinds | rewritten |
| draft_outline | importSVG.insert, Import.readDXF by name only | nothing | none | rewritten |
| draft_plane | make_workingplaneproxy, view_wpproxy.writeCamera | 3D-view refusal; active document set | the refusal live | rewritten |
| draft_shape | make_wire / bspline / bezcurve (no placement passed: points absolute), make_rectangle, make_circle (startangle / endangle), make_ellipse (radii; the tool halves major / minor), make_polygon (inscribed), make_point, MakeFaceMode default True | sizes over 0, sides ≥ 3, arc start ≠ end, repeated end point, `face` a boolean: each refused by name instead of "Draft made nothing" | none | rewritten: `face` left out fills a closed shape (the old text said the opposite) |
| draft_style | get_default_annotation_style, repair_annotation_style, style editor save_meta, view provider onChanged | #1, #2; values type-checked | apply and set live in the window | rewritten |
| draft_text | Part.makeWireString(text, font, size, tracking), ShapeString.execute | nothing | "capitals near 0.7 of size" is a typical figure, not derived | rewritten |
| draft_to_sketch | make_sketch (planar and coplanar checks, autoconstraints) | refusal says what must hold | constraint count | rewritten (data entry) |

## Notes

- Descriptions: 18 of the 19 grew beyond 1.3x (one-liners of 80 – 300 characters now 150 – 800; draft_modify 807). The op-by-op rules are in `guide_read draft`. Say if they should be cut back.
- Working plane in 1.1: Draft reads `WorkingPlane.get_working_plane(update=False)` (a `PlaneGui` per 3D view; headless a fresh one on XY); `FreeCAD.DraftWorkingPlane` is only kept for old code. No tool sets it, and the descriptions now say XY.
- Headless: dimensions, labels and layers are made and their `Distance` / `Text` / `Group` computed; text size, arrows, colours and layer line widths exist only on view providers. Hatch lines are real geometry (headless too, if TechDraw loads).
- Not offered (features, left): Draft Text and ShapeString objects, path-twisted arrays, label types Volume and "Label + …", `Draft.offset` bind / sym / occ.

## Test model

`draftmesh-draft-model.json`: 81 calls, 18 of the 19 tools (draft_outline needs a file), 9 refusals. Lengths and areas are worked out from Draft_tutorial.md's dimensions; no answer-key file exists for it.

# 2. Mesh (group "mesh", 21 tools)

Checked against FreeCAD 1.1 source: `src/Mod/Mesh/App/Mesh.pyi`, `MeshPyImp.cpp`, `MeshFeaturePyImp.cpp`, `BuildRegularGeoms.py`, and (via `git show HEAD:`) `Mesh.cpp`, `MeshFeature.cpp`, `AppMeshPy.cpp`, `Core/Decimation.cpp`, `Core/TrimByPlane.cpp`, `Core/TopoAlgorithm.cpp`, `Core/Algorithm.cpp`, `Core/MeshIO.cpp`; `src/Mod/MeshPart/App/AppMeshPartPy.cpp` (meshFromShape's keyword sets, projectShapeOnMesh); `src/App/ComplexGeoData.pyi`; wiki `Mesh_Workbench.md`, `Mesh_Scripting.md`, `Mesh_to_Part.md`.

Files changed: `agentlink/families/meshobj.py`, `agentlink/data/tools.json` (meshobj_offset description), `agentlink/guides/mesh.md`, `tests/test_meshobj.py` (new class `MeshHardening`, 7 tests). The helpers `meshbool.py`, `meshformats.py`, `meshdist.py`, `hull3d.py` are plain Python with their own tests and were read, not changed (only meshbool is used by this family).

## Bugs fixed (proved from source)

1. **meshobj_segments kind curvature failed every time.** `getSegmentsByCurvature` takes tuples of (wanted max curvature, wanted min curvature, tolerance, tolerance, least facets), each read with `Py::Float`; the tool passed `("Plane", tol, tol, n)`. Now `(0.0, 0.0, tol, tol, minFacets)`: flat regions judged by curvature. With `keep: true` the kept meshes were the first `top` found, not the largest listed; now in the listed order.
2. **meshobj_transform was wrong for a mesh with a placement.** `Mesh.transform` moves the stored points, before the object's Placement is applied (`getKernel().Transform`), so a placed mesh turned and scaled about its own origin. The matrix is now carried through the placement (P⁻¹ · M · P). A negative scale factor now flips the normals as a mirror does (an odd count turns the triangles inside out and the volume negative).
3. **meshobj_merge put placed meshes in the wrong place.** `addMesh` is `_kernel.Merge(mesh._kernel)`: both placements are passed by. Each mesh is now brought to where it stands first.
4. **meshobj_primitive torus was off-centre by its radius.** `BuildRegularGeoms.Toroid` builds the tube's circle at x = radius1 + …, where x is the body's axis: the ring stands `radius` along its axis from the origin, which after the turn to z put it at z = -radius. Now centred on `at`.
5. **meshobj_sections with a normal of mixed signs sliced in the wrong places.** The mesh's reach along the normal was read off two corners of its box (min·n and max·n); right only when n's components share a sign. For [1, -1, 0] on a box every evenly spaced slice landed on the same plane. Now the low or high end per axis by n's sign.
6. **meshobj_unwrap refused every mesh.** The reference went through `picks.resolve`, which refuses an object with no Shape ("has no shape … a mesh becomes a body with import_file"), though the description offers "or a mesh". A mesh's name is now looked up first. A closed mesh, more than one piece, and more than 50,000 triangles are refused with what to do (flatmesh needs one open patch; it runs apart with a 5 minute limit).
7. **meshobj_refine was described as splitting each triangle in four.** `MeshObject::refine` inserts a point at each triangle's centre (`InsertVertexAndSwapEdge`): about three for one. Description, refusal and guide corrected; refused past 2,000,000 triangles.
8. **meshobj_primitive cylinder / cone: ring spacing fixed at 0.5 mm.** `BuildRegularGeoms.Cone` makes len / edgelen rings, each a Python loop: a 1 m cylinder was about 380,000 triangles. Spacing is now max(0.5, longest size / 40): unchanged up to 20 mm.
9. **meshobj_info ran the self-intersection search twice** (`hasSelfIntersections`, then `getSelfIntersections` for the count, on every call). The pairs are now listed only when there are any.
10. **meshobj_boundary counted edges in a Python dict of every edge**; now in numpy (same answer).

## Changed without proof (needs the live check most)

- **meshobj_sections' default tolerance, 1e-6 → 0.01.** It is the distance within which FreeCAD chains cut segments into loops (`ConnectLines`, squared, on float32 points; FreeCAD's own default is 0.01). 1e-6 mm is below float32's spacing at 100 mm, so loops could come back in fragments. Not shown to have happened.
- **meshobj_split refuses more than 100 pieces** (a noisy scan would make thousands of objects), **meshobj_trim refuses a cut that leaves nothing**, **meshobj_export refuses an extension Mesh.write does not know** (it listed `amf … asy …`; the full list is now MeshOutput::GetFormat's). New limits, chosen by judgment.

## Per tool

| Tool | Checked against | Fixed | Still doubtful / live check | Description |
|---|---|---|---|---|
| meshobj_boolean | meshbool.py's contract; MeshObject::unite (applies both placements); Part makeShapeFromMesh fallback | nothing | time on a dense scan (not measured); `maxFacets`, `deflection` are read but not in the schema | rewritten |
| meshobj_boundary | Topology (placement applied) | #10; empty mesh refused; `mesh` now carries its description | a chain started mid-way through an open (non-loop) boundary comes back in two parts | rewritten |
| meshobj_curvature | getCurvaturePerVertex (max, min, directions) | empty mesh refused | how FreeCAD scores a box's corners | rewritten: can run as a job |
| meshobj_decimate | decimate(tolerance, reduction) → target = facets × (1 - reduction); Simplify stops at tolerance | tolerance > 0; note when it stops short of the count | how far short at tolerance 0.1 | rewritten |
| meshobj_edit | none in FreeCAD (Agent Link's own) | nothing | none | rewritten |
| meshobj_export | Mesh.write, MeshOutput::GetFormat (22 extensions) | extension checked first; reply has format, facets | amf / 3mf need FreeCAD's zip support | rewritten: can run as a job |
| meshobj_from_shape | meshFromShape: Standard (LinearDeflection, AngularDeflection radians, Relative), Mefisto (MaxLength), Netgen (Fineness, SecondOrder, Optimize, AllowQuad): all three keyword sets match | deflection, angle, maxLength, fineness checked; a wrong body lists the bodies; `heavy` past 200,000 | netgen on the Mac's build | rewritten |
| meshobj_info | has* / count* names in Mesh.pyi | #9 | time on a dense mesh | rewritten: can run as a job |
| meshobj_merge | MeshObject::addMesh | #3; the same mesh twice refused | none | rewritten |
| meshobj_offset | offset → offsetSpecial2 (points along normals, flipped triangles collapsed) | nothing (data entry) | how far inward before it damages | rewritten |
| meshobj_primitive | createBox / Sphere / Cylinder / Cone / Torus signatures, BuildRegularGeoms | #4, #8; sizes checked by name | none | rewritten |
| meshobj_project | MeshPart.projectShapeOnMesh(Shape, Mesh, Direction) | direction checked; refusal says why nothing landed | whether a mesh's placement is honoured | rewritten |
| meshobj_refine | MeshObject::refine | #7 | exact count (FreeCAD skips "deformed" triangles) | rewritten |
| meshobj_repair | fixIndices, rebuildNeighbourHood, removeDuplicated*, fixDegenerations(eps), removeNeedles(len), removeNonManifolds / Points, fixSelfIntersections, removeFoldsOnSurface, harmonizeNormals, flipNormals, fillupHoles(len, level), removeComponents(count: pieces of count or fewer), removePointsOnEdge(FillBoundary) | `fix` checked as a list | filled holes' facing without `normals` | rewritten |
| meshobj_sections | crossSections(planes, min_eps, connect), CutWithPlane | #5; count / at / tolerance checked | the tolerance change (above) | rewritten |
| meshobj_segments | getPlanarSegments(dev, minFacets), getSegmentsByCurvature, meshFromSegment | #1; inputs checked; a note when none is found | whether a region of exactly minFacets counts | rewritten |
| meshobj_smooth | smooth(Method, Iteration, Lambda, Micro) | iterations checked | none | rewritten |
| meshobj_split | getSeparateComponents | 100-piece guard; reply has facets | none | rewritten |
| meshobj_transform | MeshPy::transform, Feature::onChanged (Placement and Mesh kept in step) | #2; inputs checked; nothing asked refused | none | rewritten |
| meshobj_trim | trimByPlane (applies the placement; the side the normal points to goes) | a cut leaving nothing refused | none | rewritten |
| meshobj_unwrap | flatmesh use unchanged; picks.resolve | #6 | flatmesh on the Mac's build; stretch figures | rewritten |

## Notes

- Heavy tools and limits, as now written in the descriptions and the guide (`size and time`): past about 200,000 triangles meshobj_info, meshobj_repair, meshobj_segments and meshobj_boolean get slow. **No timing was measured.** Changing tools cannot run as jobs; the three reads (meshobj_info, meshobj_curvature, meshobj_export) can (`background: true`) and say so.
- FreeCAD's own `unite` / `intersect` / `difference` need no OpenSCAD or CGAL (MeshCore SetOperations); the tool uses them only after Agent Link's boolean refuses.
- Descriptions: 3,435 → about 6,200 characters for the 20 in meshobj.py (most were one line). Say if they should be cut back.
- Not used by any tool (left): decimate(targetSize), offsetSpecial, nearestFacetOnRay, getSegmentsOfType (Cylinder, Sphere), smooth's PlaneFit / MedianFilter, cut / trim by polygon.

## Test model

`draftmesh-mesh-model.json`: 63 calls, all 21 tools, 10 refusals. Derived: the cube's 8 points / 12 facets / 600 / 1000, the half cube's rim and repair, the 36-sided pipe of Mesh_Scripting.md, the 684-byte STL, the can's flat side. Guesses (said as such in each `expect`): the sphere meshes' facet counts and how far under the true volume they sit, the mefisto count, decimate's stopping point, curvature at a box's corners.

# 3. Surface (group "surface", 11 tools)

Checked against FreeCAD 1.1 source (via `git show HEAD:`): `src/Mod/Surface/App/FeatureSections.cpp`, `FeatureGeomFillSurface.cpp`, `FeatureFilling.cpp`, `FeatureExtend.cpp`, `FeatureCut.cpp`, `FeatureSewing.cpp`, `Blending/FeatureBlendCurve.cpp`; `Blending/BlendCurve.pyi`, `BlendPoint.pyi`; `src/Mod/Part/App/TopoShape.pyi`; wiki `Surface_Workbench.md`, `Surface_Filling.md`, `Surface_GeomFillSurface.md`, `Surface_Sections.md`, `Surface_ExtendFace.md`, `Surface_BlendCurve.md`. `src/Mod/ReverseEngineering` holds no Python-callable polynomial fit that surface_polynomial uses: the tool is its own numpy least squares, checked as arithmetic only.

Files changed: `agentlink/families/surface.py`, `agentlink/families/draft.py` (surface_fill, surface_loft; descriptions of all four plain-surface tools), `agentlink/families/std_more.py` (surface_polynomial's description and refusals), `agentlink/guides/surface.md`, `tests/test_more_families.py` (new `test_surface_hardening`).

Every property name and enumeration the tools set was found as written in the sources: `NSections`; `BoundaryList`, `ReversedList`, `FillType` (Stretched, Coons, Curved); `BoundaryEdges`, `BoundaryOrder` (Filling); `Face`, `ExtendUNeg`, `ExtendVNeg`, `ExtendUSymetric`, `ExtendVSymetric` (spelled so in FreeCAD); `ShapeList`, `Tolerance` (Sewing); `ShapeList` (Cut); `StartEdge` / `StartParameter` / `StartContinuity` / `StartSize` and the `End…` four; type names `Surface::Sections`, `::GeomFillSurface`, `::Filling`, `::Extend`, `::Sewing`, `::Cut`, `::FeatureBlendCurve`.

## Bugs fixed (proved from source)

1. **surface_boundary counted references, not edges.** GeomFillSurface takes 2 – 4 edges in all (`validator.numEdges()`); a sketch or wire named whole brings every edge. One sketch of four edges was refused ("two to four boundary curves"), and two wires of three edges each went through to FreeCAD's "Only 2-4 curves are allowed". Now counted after expansion. `fill` is checked before the object is made.
2. **surface_boundary's reversal flags were read off vertex order.** FreeCAD reverses the *curve under the edge* (`BRep_Tool::Curve`, then `curves[i]->Reverse()`), which does not follow the edge's orientation in its body; the flags are now worked out from the curve's own ends (`valueAt(FirstParameter / LastParameter)`).
3. **surface_sections refused one wire holding several section curves** and let one single-edge reference through; the count is now of edges (each is one section, as `NSections` reads them). The reply carries `sections`.
4. **surface_fill filled the first run of edges and dropped the rest without a word** (`Part.sortEdges(edges)[0]`). More than one run is now refused; an open boundary says how far apart its ends are; `thickness: 0` is refused.
5. **surface_extend passed any u, v to a constrained property** (range -0.5 … 10 in `FeatureExtend.cpp`); now checked. The description and note now say what the feature really makes: a refitted four-sided B-spline over the face's whole u, v range within 0.1 mm (`Tolerance`), so holes and a trimmed outline are lost.
6. **surface_cut by a surface** reported a plain success. `Cut::execute` is `ts1.cut(ts2)`: a second *surface* removes nothing. The reply now says when nothing was removed (split only) and when nothing crossed. Objects without a shape are refused before the feature is made.
7. **surface_sew's "not made: the shell is open"** now counts the edges with a face on one side only; a sewing that joined nothing carries `warning`. `tolerance` must be over 0.
8. **surface_blend** took any `size` (the property is constrained to -100 … 100) and a non-object `start` / `end` raised AttributeError; both are refused by name. The reply has the curve's `length` (a curve has no area, so the reading said nothing about it).
9. **surface_loft closed: true with two curves** went to OCC; refused (three or more).

## Changed without proof / not verified

- **surface_cut's note for a surface tool** assumes OCC returns the first surface split in two along the crossing (faces up, area the same). If it comes back unsplit the note says "nothing was cut" instead. Live check.
- **surface_boundary with two edges**: the tool treats two curves as meeting at a corner (`chain(closed=False)`); what `GeomFill_BSplineCurves::Init(C1, C2)` requires is OCC's, not in the FreeCAD tree. Not verified.
- **Coons / Curved fallback to Surface::Filling**: kept as it was (triggered by "disjoint" in FreeCAD's error for three or more edges). `Filling::addConstraints` wants boundary edges in consecutive order, which `chain` has already checked.

## Per tool

| Tool | Checked against | Fixed | Still doubtful / live check | Description |
|---|---|---|---|---|
| surface_blend | FeatureBlendCurve.cpp (constraints 0 … 1, 0 … 25, -100 … 100; recompute on every property change, so both edges are set first, as the tool does) | #8 | length for given sizes | rewritten |
| surface_boundary | FeatureGeomFillSurface.cpp, FeatureFilling.cpp | #1, #2; reply has fill, sides; refusal hint | two-edge case; when Coons is refused | rewritten |
| surface_cut | FeatureCut.cpp | #6 | split-by-surface | rewritten |
| surface_extend | FeatureExtend.cpp | #5; reply has u, v | which of u, v is the long side of a given face | rewritten |
| surface_fill | Part.makeFilledFace, makeOffsetShape(offset, tolerance, fill) | #4 | none | rewritten |
| surface_loft | Part.makeLoft(wires, solid, ruled, closed) | #9 | none | rewritten |
| surface_points | BSplineSurface.interpolate / approximate keywords | nothing | approximate with 2 rows (degree 1) | rewritten |
| surface_polynomial | own numpy fit; BezierSurface increase / setPole (1-based) | refusals say what to give | residual is along the fit plane's normal, not true distance (now said) | rewritten |
| surface_sections | FeatureSections.cpp (GeomFill_NSections) | #3; refusal hint | closed section curves | rewritten |
| surface_sew | FeatureSewing.cpp (BRepBuilderAPI_Sewing) | #7 | none | rewritten |
| surface_thicken | makeOffsetShape | nothing | none | rewritten |

## Notes

- Not offered (features, left): Surface::Filling's `BoundaryFaces` / `BoundaryOrder` (tangent to neighbours), `UnboundEdges`, `Points`, `FreeFaces`, `InitialFace`, `Degree` …; Extend's separate ends and `SampleU` / `SampleV`; Sewing's four options; Curve on Mesh (window only). All can be set with object_set on the feature the tools make; the guide lists the property names.
- Descriptions: the six in surface.py were 54 – 141 characters and are now about 300 – 385.

## Test model

`draftmesh-surface-model.json`: 52 calls, all 11 tools, 10 refusals. Part A is a 40 × 30 frame of four lines with exact areas and volumes (boundary, fill, sections, extend 1728 and 1452, cut 600, sew 2000 / 2400 / 8000, thicken 2400). Part B runs the wiki's own scripting examples (GeomFillSurface, Sections, BlendCurve) through draft_shape's B-splines; their areas are free-form and marked as guesses.

# Across the three

- Tools checked: 51 (19 Draft, 21 Mesh, 11 Surface). Descriptions rewritten: 51. Bugs fixed from source: 33 (14 Draft, 10 Mesh, 9 Surface).
- Plain-Python suite after the changes: 681 passed, 275 skipped (262 before: the 13 new FreeCAD tests skip here). FILES was not regenerated (no file added).
- Could not do: run anything on FreeCAD; measure any timing; verify OCC-side behaviour (GeomFill with two curves, a face cut by a face, offsetWire's side).
- Wishes for files I may not edit: (1) protocol / the shared runner: bring the document's 3D view to the front before a changing Draft call when the window is up (draft_dimension, draft_plane fail otherwise, see Draft above). (2) health.py: none.
