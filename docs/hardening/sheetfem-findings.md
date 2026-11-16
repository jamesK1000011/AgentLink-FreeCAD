# Spreadsheet / VarSet and FEM hardening: findings

Two workbenches, done in order. **Spreadsheet / VarSet (18 tools) is complete. FEM (19 of the 20 tools; `fea_frame` is not in this repo) is complete for the FreeCAD FEM route, fem_more, descriptions and refusals; where I stopped is listed under "Where I stopped" at the end.**

Nothing was run on FreeCAD here. Every fix is from reading the FreeCAD 1.1 source (tag 1.1.0; the Mac runs 1.1.3) and each has a test that has not been run on FreeCAD yet. Plain-Python suite: 683 passed, 264 skipped.

Files changed: `agentlink/cells.py`, `exprs.py`, `families/sheet.py`, `param.py`, `std_more.py` (sheet_cells only), `strength.py`, `fem_more.py`, guides `sheet.md`, `param.md`, `strength.md`, tests `test_cells.py`, `test_sheet.py`, `test_fem_route.py`, `test_strength.py`. No new files (FILES unchanged). `health.py`, `protocol.py`, `tools.py`, `keep.py` untouched. `ccx_hint`, `NOT_SOLVERS` and `_health` kept (ccx_hint gained two cases).

Model files: `sheetfem-sheet-model.json` (55 calls, all 18 tools), `sheetfem-fem-model.json` (43 calls, 19 tools).

---

# 1. Spreadsheet / VarSet

Checked against FreeCAD 1.1 source: `src/Mod/Spreadsheet/App/Sheet.pyi`, `SheetPyImp.cpp`, and (via `git show HEAD:`) `Sheet.cpp`, `PropertySheet.cpp`, `Cell.cpp`, `src/Mod/Spreadsheet/Gui/DlgSheetConf.cpp`, `src/App/Range.cpp`, `Expression.l`, `Expression.cpp`, `VarSet.h/.cpp`, `DynamicProperty.cpp`, `DocumentObjectPyImp.cpp`, `PropertyContainerPyImp.cpp`, `src/Gui/Dialogs/DlgAddProperty.cpp`, `src/Mod/Sketcher/App/SketchObject.cpp` (validateExpression). Wiki: `Spreadsheet_Workbench.md`, `Spreadsheet_SetAlias.md`, `Configuration_Tables.md`, `Std_VarSet.md`.

## Bugs fixed (proved from source)

1. **A failed cell was never seen as an error.** `Sheet::recomputeCell` catches the evaluation error and stores the text `ERR: <reason>` as the cell's value; `Sheet.get` does not raise. `value_of` only looked for an exception, so `sheet_read` showed `value: "ERR: …"` with no `error`, and the refusal after a bad write could not name the cell (it fell back to FreeCAD's "One or more cells failed contains errors"). Now an `=` cell whose value starts `ERR: ` is an error with FreeCAD's reason; `sheet_set` and `param_set` refusals name the cell.
2. **A formula FreeCAD cannot parse was kept silently as text.** `Cell::setContent` catches the parse error, keeps the whole string as a `StringExpression`, and `Sheet::execute` then returns success (the cell is never put in `cellErrors`). `sheet_set { B1: "=(A1 + 2" }` and `param_set { value: "(w /" }` answered success with the formula as the value. Both now refuse right after `Sheet.set`, by reading back the content (FreeCAD gives a text cell a leading `'`). A whole-string literal (`=<<text>>`) is left alone.
3. **`sheet_set { A1: null }` was refused.** Clearing removes the cell's property and `Sheet.get` raises for an empty cell (the wiki's Scripting section says so); the tool read that as "does not evaluate" and rolled back. An empty cell now reads `{ content: "", empty: true }` in `sheet_set`, `sheet_read` and `sheet_format`. The same made an alias on a still-empty cell fail; FreeCAD allows it, so it now passes.
4. **Alias rules were looser than FreeCAD's.** `PropertySheet::isValidAlias`: a letter first (no leading `_`), not a cell address, not a unit or constant token of the expression parser, not a property of the sheet. The tools let `_x`, `m`, `mm`, `W`, `e`, `pi` through to FreeCAD's bare "Invalid alias". `cells.alias_problem` now gives the reason; the full unit list is taken from `Expression.l`. Used by `sheet_set`, `sheet_table make` (params are aliases) and `param_set`. A taken alias says which cell holds it.
5. **VarSet variables named like a unit or constant.** `addProperty` from Python accepts `mm`, `e`, `N`; FreeCAD's own Add Property dialog (`DlgAddProperty.cpp`, `isTokenAUnit / isTokenAConstant`) refuses them because `VarSet.mm` does not read as a variable. `varset_new` / `varset_set` now refuse them too.
6. **`cells.content` cut the zeros off an exponent.** `repr(1e-10).rstrip("0")` gave `1e-1`; `1e20` gave `1e+2`. Plain-Python bug, fixed and tested (`tests/test_cells.py`).
7. **`sheet_import` ignored a failed import.** `Sheet::importFromFile` answers False (no exception) for a file it cannot open or a line it cannot split, after clearing the sheet. Now refused, nothing kept. `sheet_export` checks its answer the same way.
8. **Design-table switch missing `CopyOnChange`.** FreeCAD's dialog sets `prop->setStatus(CopyOnChange, true)` on the enumeration, which is what makes a variant Link or SubShapeBinder copy the owner when its own switch turns (wiki Configuration_Tables steps 12 to 19). `sheet_table make` now sets it (`setPropertyStatus(prop, "CopyOnChange")`).
9. **`param_set` wrote the name as typed.** `Cell::setContent` reads a bare `inf` or `nan` as a number (strtod), so such a parameter's name cell became a number and `rows()` lost it. Names and notes are now written as text (leading `'`); a note starting `=` no longer becomes a formula.
10. **`sheet_cells` passed lower-case addresses through** (`stringToAddress` takes capitals only: "Invalid cell specifier") and reported `span: null` always (`getCellSpan` does not exist on `Sheet`). Addresses are normalised and checked; the reply says what was merged and that the other cells were cleared.
11. **`sheet_clear` / `sheet_table make` rebuilt the range's cell set once per filled cell** (quadratic); hoisted. `sheet_clear` and `sheet_format` now refuse a range over 20000 cells with the count (a whole column is 16384) instead of looping over millions.
12. **Merging threw away aliases in use.** `PropertySheet::mergeCells` clears every cell but the top-left one, aliases too. `sheet_format { merge: true }` now refuses when those cells hold aliases another object uses (the later recompute check would have refused with a vaguer message, or not at all for an unused alias).
13. **`param_bind` on a reference (driven) constraint** reached FreeCAD's "Reference constraints cannot be set!" as a bare message; refused before with what to do. `Constraints[3]` (by number) now says a constraint is bound by its name and lists them.

## Per tool

| Tool | Checked against | Fixed | Still doubtful / live check | Description |
|---|---|---|---|---|
| sheet_new | wiki Scripting; `Sheet` naming | nothing | none | rewritten |
| sheet_list | `getNonEmptyCells`, `getAlias` | nothing | none | rewritten |
| sheet_read | `SheetPy::get`, `Sheet::recomputeCell`, `getStringContent` | bugs 1, 3 | the exact text after `ERR: ` on 1.1.3 | rewritten |
| sheet_set | `SheetPy::set`, `Cell::setContent`, `PropertySheet::setAlias / isValidAlias`, `Sheet::execute` | bugs 1 to 4 | cyclic dependency: FreeCAD marks the cells with an exception but leaves their values, so no cell reads `ERR:`; the refusal then says "cells that depend on each other in a circle" (wording from source, not seen live) | rewritten |
| sheet_clear | `Sheet::clear` (alias and property removed) | bug 11 | none | rewritten |
| sheet_format | `setStyle` / `setAlignment` (string with `|`, "replace"), `decodeColor` (3 or 4 tuple), `setDisplayUnit`, `setColumnWidth("A", px)`, `setRowHeight("1", px)`, `mergeCells`, `splitCell` | bugs 3, 11, 12 | whether a displayUnit of the wrong dimension shows an error in the cell (it does not change the value) | rewritten |
| sheet_rows | `insertRows("3", n)` (1-based string, cells at and below move down), `insertColumns("C", n)` | refusal words | inserting above cells whose aliases a sketch uses: expected to keep the part unchanged; in the model | rewritten |
| sheet_import | `Sheet::importFromFile` (clears first, each field through `setCell`, False on failure) | bug 7 | none | rewritten |
| sheet_export | `Sheet::exportToFile` (values only; a quantity as its number in internal units) | answer checked; note corrected | none | rewritten |
| sheet_chart | plain Python (`charts.py`) | nothing | none | rewritten |
| sheet_table | `DlgSheetConf.cpp` (enum bound to the names column, `hiddenref(…String)`, `.cells.Bind`, row offset) | bugs 4, 8, 11 | the tool binds an explicit names range (`A3:A4`) where the dialog writes the growing `A3:\|`; `add` rewrites it. Left as is | rewritten |
| sheet_cells (std_more.py) | `mergeCells(Range)`, `splitCell`, `stringToAddress` | bug 10 | none | rewritten |
| param_set | alias rules; `Cell::setContent` | bugs 2, 4, 9; cell named in the refusal | none | rewritten |
| param_list | reads only | nothing | none | rewritten (kept, tightened) |
| param_bind | `DocumentObjectPy::setExpression` (path, None clears), `evalExpression`, `SketchObject::validateExpression` | bug 13; refusals | a cyclic expression is refused by FreeCAD at `setExpression`; its message is passed on with a hint (not seen live) | rewritten |
| param_remove | `setAlias("")`, `removeRows` | refusal words | none | rewritten |
| varset_new | `App::VarSet`, `addDynamicProperty` (identifier names), `DlgAddProperty` rules, wiki Std_VarSet type table | bug 5; unit list (dropped `inch`, which FreeCAD does not know) | none | rewritten |
| varset_set | same | bug 5; refusal names the kind | none | rewritten |

Not done, on purpose (would be new features): renaming a VarSet variable (`renameProperty` exists in 1.1), VarSet group-name validation (the dialog applies name rules to groups; Python does not), `Constraints[n]` binding by number.

---

# 2. FEM

Checked against FreeCAD 1.1 source: `src/Mod/Fem/ObjectsFem.py`, `femtools/ccxtools.py`, `femtools/checksanalysis.py`, `femtools/femutils.py`, `femtools/geomtools.py`, `femtools/objecttools.py`, `femmesh/gmshtools.py`, `femmesh/netgentools.py`, `femobjects/solver_calculix.py`, `solver_ccxtools.py`, `mesh_gmsh.py`, `constraint_selfweight.py`, `result_mechanical.py`, `femsolver/calculix/write_constraint_force.py`, `write_constraint_selfweight.py`, `feminout/importCcxFrdResults.py`, `femexamples/ccx_cantilever_faceload.py`, `ccx_cantilever_base_solid.py`, `meshes/generate_mesh.py`, and (via `git show HEAD:`) `src/Mod/Fem/App/FemConstraint.cpp`, `FemConstraintForce.cpp`, `FemTools.cpp`, `src/Mod/Part/App/PrimitiveFeature.cpp`, `TopoShapeExpansion.cpp`, `src/App/PropertyLinks.cpp`, `femtest/data/calculix/ccx_cantilever_faceload.inp`. Wiki: `FEM_CalculiX_Cantilever_3D.md`.

`fea_frame`: no code in this repo (`grep -r fea_frame agentlink/` finds nothing; `tests/test_no_addon_names.py` lists it as an add-on's). Skipped.

## Bugs fixed (proved from source)

1. **Self weight used properties FreeCAD 1.1 no longer has.** `constraint_selfweight.py` in 1.1 keeps `GravityAcceleration` (a quantity) and `GravityDirection` (a unit vector); `Gravity_x / _y / _z` exist only in files from before, to be migrated. `fea_solve`'s FEM route and `fea_native` both set `g.Gravity_x, …`. On 1.1 that either raises (the route then falls back to the own deck with "FreeCAD's FEM route failed") or sets nothing, leaving 1 g down -z whatever was asked. New `self_weight()` sets the 1.1 properties (magnitude = FreeCAD's own 1 g times the vector's length, as its migration code does) and the old ones on an older FreeCAD. **Which of the two failures happened on 1.1.3 I could not tell from source** (it depends on whether a FeaturePython object accepts an unknown attribute).
2. **Netgen never meshed on 1.1.** `NetgenTools` is a `QProcess` tool (`objecttools.ObjectTools`): `run()` starts the process and returns at once; the tool called `update_properties()` immediately after, before any mesh existed. Now run to the end through the same bounded runner as Gmsh.
3. **`GmshTools.create_mesh()` answers nothing in 1.1** (`self.run(True)`, "for backward compatibility only") and waits without limit (`waitForFinished(-1)`). The route's `err` was always None, so a failed mesh said only "no volume elements", and `timeout` did not bound it. New `gmsh_run()` does what `run(True)` does (`prepare()`, `compute()`, wait) with the timeout, kills Gmsh when it is over, and reads Gmsh's stderr for the refusal. A FreeCAD without the 1.1 process tools still goes through `create_mesh()`. On 1.0, `create_mesh()` returned Gmsh's stderr and the route refused on any warning; it now refuses only when no volume elements came back.
4. **`ccx_run()` forgot the binary it was given.** It calls `self.setup_ccx()` again with no argument, which looks in FreeCAD's preference and the PATH only. With CalculiX found through `AGENTLINK_CCX` alone, FreeCAD's route raised "CalculiX binary not found" and the solve silently went to the own deck. The instance's `setup_ccx` is now wrapped so the binary found here is the one it runs.
5. **The single material carried a reference.** `mo.References = [(o, "")]` makes `checksanalysis.py` print an error line at every solve ("Only one material object, but this one has a reference shape. The reference shape will be ignored."), which the shared health check then reports as a Report-view error. FreeCAD's own examples leave it empty; removed in `fea_solve`'s route and in `fea_native`.
6. **Each solve left a result mesh behind.** `importFrd` links `CCX_Results_Mesh` from the result object (`res_obj.Mesh`); it is not a member of the analysis. The clean-up before a new solve removed the analysis's members only. Result meshes, and a mesh's refinements (`MeshRegionList` and the like, where `fem_add` puts them), now go with it.
7. **CalculiX's lines never reached the health check on FreeCAD's route.** `_health` reads `session._ccx_tail`, which only the own deck set. The route now keeps `FemToolsCcx.ccx_stdout / ccx_stderr` there after `ccx_run()`.
8. **`fea_probe` thought every mesh was 1 mm.** It read `r.get("mesh")` from the session's record, which holds `body, stats, study, result, field`; so `msize` was always 1.0, a line's "leaves the part" warning fired for any sample over 2 mm from a node (every sample on a coarse mesh), and the face tolerance was fixed at 0.05 mm. Now the study's mesh size.
9. **A zero force or zero gravity was accepted**, then failed inside the route at `normalize()` of a null vector (reported as a route failure). Refused at `fea_load`.
10. **The solver's analysis type was left to defaults.** Set outright to `static` / `linear`, as FreeCAD's examples do (1.1's defaults are those; before 1.1 they came from preferences).
11. **`fem_add material_nonlinear` could take a fluid material as its base** (any `App::MaterialObjectPython`; 1.1's solid material Proxy type is `Fem::MaterialCommon`, so the "MaterialSolid" test never matched). Now the analysis's solid one (`Category`).
12. **`fem_linearize` with an unknown field** raised a bare AttributeError; refused with the result's list properties. An empty list is refused.
13. **`mesh.Shape`**: FreeCAD 1.1's Gmsh object has `Shape`; before it the link was `Part`. Both handled.

## Verified as right (no change)

- `makeSolverCalculiXCcxTools` exists in 1.1 and is the object `FemToolsCcx` wants; `makeSolverCalculiX` is the new-framework object (what `fea_native` makes, for the GUI).
- `FemToolsCcx` order: `update_objects()`, `setup_working_dir(dir)` (the folder must exist), `setup_ccx(bin)`, `check_prerequisites()` (a message string, empty when fine), `write_inp_file()` (sets `inp_file_name`), `ccx_run()` (exit code; stdout / stderr kept as text), `load_results()`.
- Force direction: `ConstraintForce` derives `DirectionVector` only when `Direction` is assigned, from the shape as it is then. The helper `Part::Line` recomputes itself when X2 / Y2 / Z2 are set (`Part::Line::onChanged`), so its edge exists at that moment and the direction is right. `Reversed` stays false.
- Units: the deck is mm, N, MPa (`ccx_cantilever_faceload.inp` trailer); `Force = "… N"`, `Pressure = "… MPa"`, `CharacteristicLengthMax = "… mm"`, density in kg/m^3.
- References `[(obj, ("Face1", …))]`; a helper solid's faces are picked afresh from its shape at every solve (`_need_study` rebuilds the helper).
- Material with `""` as sub-element resolves to the whole solid (`getSubTopoShape` with an empty name), so the old reference did not break the check; it only printed the error line (bug 5).
- 1.1 renamed the solver's `IterationsMaximum` to `IncrementsMaximum` (and the time-step properties); the tools set none of them.

## Per tool

| Tool | Checked against | Fixed | Still doubtful / live check | Description |
|---|---|---|---|---|
| fea_setup | own logic; helper solid | nothing | none | rewritten |
| fea_hold | own logic; `facepick` | nothing | none | rewritten |
| fea_load | own logic | bug 9 | none | rewritten |
| fea_solve | everything listed above | bugs 1, 3 to 7, 10, 13 | **the riskiest change**: `gmsh_run` drives the QProcess itself (prepare, compute, bounded wait) instead of `create_mesh()`; and the wrapped `setup_ccx`. Both follow 1.1.0's code; 1.1.3 may differ. CalculiX run by `ccx_run()` is still not bounded by `timeout` (FreeCAD's `p.communicate()` has none) | rewritten |
| fea_results | own logic | nothing | none | rewritten |
| fea_clear | own logic | nothing | it leaves FEM analyses in the document (said in the description now) | rewritten |
| fea_probe | own logic | bug 8 | none | rewritten |
| fea_chart | own logic (`charts.py`) | inherits bug 8's fix | none | kept (reviewed, already complete) |
| fea_export | own logic | nothing | none | rewritten |
| fea_refine | own Gmsh script | nothing | none | rewritten |
| fea_modes | own deck | nothing | not a changing tool, so no health check runs after it; NOT_SOLVERS' comment says every other fea_ tool carries CalculiX's lines, which holds only for changing ones (a wish for health.py / the registrations, not changed here) | rewritten |
| fea_buckle | own deck | nothing | same as fea_modes | rewritten |
| fea_heat | own deck | nothing | same as fea_modes | rewritten |
| fea_shell | own deck; `Fem.read`, `writeABAQUS` | nothing | not read line by line (see below) | rewritten |
| fea_parts | own deck; `getccxVolumesByFace` | nothing | not read line by line (see below) | rewritten |
| fea_native | `ObjectsFem` makers, 1.1 property names | bugs 1, 5, 13 | Elmer side (`_elmer_conditions`, `_elmer_write`) not checked against `femsolver/elmer` | rewritten |
| fea_frame | not in this repo | skipped | | no |
| fem_add | all 53 kinds against `ObjectsFem.py` 1.1.0 | bug 11; refusals | 1.1.0 has no `makeConstraintElectromagnetic`, `makeMeshDistance`, `makeMeshManipulate`, `makeMeshAdvanced`, `makeMeshShape`, `makeMeshTransfinite*`: those kinds answer "unavailable" there (right behaviour; 1.1.3 may have some) | rewritten |
| fem_mesh | `netgentools.py`, `femmesh2mesh`, `FemMesh.Groups / removeGroup` | bug 2 | Netgen itself needs the netgen Python module; expect the unavailable refusal on the Mac | rewritten |
| fem_linearize | `result_mechanical.py` properties; `FemPostDataAlongLineFilter` | bug 12 | pipeline branch (`XAxisData / YAxisData` after one recompute) not verified; the result branch is O(points x nodes) in Python, slow past about 100,000 nodes | rewritten |

`ccx_hint` gained "no material was assigned" (`ccxtools.has_no_material_assigned` looks for the same line) and "too many cutbacks" / "increment size smaller"; the guide lists what each line wants.

## The cantilever's numbers, and where they come from

- z-displacement **-86.93 mm**: wiki `FEM_CalculiX_Cantilever_3D.md`, "Visualizing Results" step 4, read from FreeCAD's example file (its own coarse Tet10 mesh).
- 500 MN along +x: **18.95 mm** in x: same page.
- **von Mises is not documented** on the page or in `femexamples/`. Beam theory: 432 MPa at the root, 216 MPa at mid-span. The model file gives a band (400 to 800 MPa at the hold) and says it is not an answer key.
- Beam theory for the rest (mine, shown in the model file): tip 87.77 mm (88.8 with shear), first bending mode 13.0 Hz, Euler buckling factor 75 at 9 MN.
- `displacementMax.mm` in the reply is the size of the vector, so it reads a little over 86.93 (about 8 mm of x at the top and bottom fibres adds in quadrature): 86 to 90.

## Where I stopped

- **Not read line by line:** `fea_parts` / `_parts_split`, `fea_shell`, `fea_modes`, `fea_heat`, `fea_buckle` bodies and `agentlink/ccx_io.py`. They build Agent Link's own deck and touch FreeCAD only through `Fem.read`, `FemMesh.writeABAQUS(file, 1, False)` and `getccxVolumesByFace`, whose signatures I checked. Their descriptions were rewritten from the code's inputs and replies; their refusals were skimmed, not rewritten.
- **Not checked:** the Elmer half of `fea_native` (`_elmer_conditions`, `_elmer_write`) against `femsolver/elmer`.
- **Not changed, flagged:** `ccx_run()` has no time limit on FreeCAD's route. Bounding it means running `ccx` on FreeCAD's deck ourselves instead of calling `ccx_run()`; I left FreeCAD's call in place and said so in the description and the guide.
- **Tests written but not run on FreeCAD:** `test_sheet.py::test_6_hardening`, `test_strength.py::test_4_hardening`. The stand-in tests in `test_fem_route.py` (self weight on both property layouts, the bounded mesher run, ccx_hint) and `test_cells.py` run here and pass.
