# asmtd findings: Assembly (18 tools) and TechDraw (32 tools)

Checkout: the agent checkout. Patch: asmtd.patch. Models: asmtd-assembly-model.json, asmtd-techdraw-model.json.
FreeCAD source read is the 1.1.0 tag (the Mac runs 1.1.3): anything that changed between 1.1.0 and 1.1.3 is not seen here.
Nothing here was run on FreeCAD. "Proven" below means read in FreeCAD's source; every behaviour fix needs the live run.
Tests: `python3 -m pytest -q -x` green (676 passed, 239 skipped) on the final code; the new FreeCAD tests are among the skipped.

## Where I stopped

- **Assembly: done.** All 18 tools read end to end against JointObject.py, UtilsAssembly.py, CommandCreate*.py, AssemblyObject.cpp / AssemblyUtils.cpp / AssemblyLink.cpp / BomObject.cpp and the wiki pages. All 18 descriptions rewritten, refusals reworked, guide updated, 2 FreeCAD tests added, model file written.
- **TechDraw: partly done.** All 32 tool bodies read once and every property and enumeration name they set checked against the 1.1 C++ (list below). 31 descriptions rewritten (td_weld: one clause). 6 bugs fixed, 2 FreeCAD tests added, guide updated, model file written.
  Not reviewed at all: the export drawing code (page_sheet, draw_item, draw_dim, draw_table, cut_line, draw_arch: techdraw.py lines about 437–530 and 860–1160), agentlink/gdt.py, sheets.py. So td_export's SVG/PDF output and the symbols' shapes (td_gdt, td_datum, td_finish, td_weld) are unchecked beyond their inputs.
  Not checked line by line against source: the paper/view coordinate maths (frame_of, to_paper, _canon, the leader's X/Y and WayPoints, a dimension's and a balloon's X/Y, DrawViewDetail's AnchorPoint). They were built against live FreeCAD before this pass; I read them but did not re-derive them.
  TechDraw descriptions came out at 1.42x the old length (6807 to 9685 characters), over the 1.3x aim; the per-reference rules moved to the guide.

## Bugs fixed (each provable in source; all need the live run)

Assembly
1. **asm_new never marked the assembly as one** (`Type = "Assembly"`, which FreeCAD's Create Assembly sets: CommandCreateAssembly.py). JointObject.py branches on it in four places. Without it: a new joint always moved its second part even when that part was grounded; parts already joined to the moved one were left behind; and in the window, editing a joint's distance, angle or offset did not solve. Now set in asm_new, and healed in asm_joint for assemblies made before. **Riskiest change**: joint creation now runs FreeCAD's own path (preSolve picks the part not joined to ground; setJointConnectors solves).
2. **Follow-on of 1**: with Type set, every `Joint.__init__` calls `setJointConnectors(joint, [])`, which calls `assembly.undoSolve()`. FreeCAD's joint panel clears that undo on OK (`clearUndo`); asm_joint now does the same, or the next joint would start by putting the parts back where they were before the last one's flip.
3. **A linked part was checked in the wrong place.** `link.Shape` is the target's own Shape property (LinkBaseExtension::extensionGetPropertyByName hands on the linked object's properties), so it ignores the link's placement. asm_check, asm_joint's overlap test, asm_sweep and asm_explode's boxes now use `Part.getShape(link)`.
4. **asm_check skipped a sub-assembly's parts** (Assembly::AssemblyLink was not walked; its children are App::Links) and read parts inside a moved App::Part in that Part's own frame. Both now walked, with the container's placement applied.
5. **asm_joint turned parts over by itself on kinds FreeCAD offers no Reverse for** (ball, perpendicular, angle, couplings): matchJCS there snaps the two frames together, which moves a part a joint of that kind does not hold. The automatic turn-over is now limited to JointUsingReverse kinds; `reverse: true` given outright still works on any.
6. **Texts that named things that do not happen**: "redundant: the solve refuses it" (1.1's solve never returns redundant; the wiki's own example has two redundant constraints and solves), `_health`'s "asm_check names the joints" (asm_list does), asm_sub's `next` and the guide's "joint to it like any part" (asm_joint cannot take a sub-assembly: see gaps).

TechDraw
7. **Diameter on a partial arc (the leftover).** `{ circle: { diameter } }` matched any round edge of that size, so a ⌀6 callout could land on a slot's R3 end. For type diameter the reference now takes whole circles only (a circle handed over in pieces on one centre counts; two arcs lying on each other do not). With only arcs of that size it is refused and names `type: "radius"`. An arc named outright ("Edge7") still takes a diameter, as TechDraw allows, and the reply carries a note. td_dimset, td_centermarks and td_dim_special make no diameters and could not make this mistake; td_centermarks already skips arcs up to a half turn. td_dim_format's `prefix: "diameter"` is text only and is now described as such.
8. **td_section { hatch: false } did nothing.** It set CutSurfaceDisplay to "None"; the enumeration is Hide | Color | SvgHatch | PatHatch (DrawViewSection.cpp), the error was swallowed, and the export's own check compared against "None" too. Now "Hide".
9. **td_projection { front } turned only the front view.** DrawProjGroup::addProjection works each secondary view's direction out from the anchor as it is at that moment; the tool set the anchor's direction after adding them. Now set before. A bad `front` is now refused before anything is made (it was swallowed). Duplicate entries in `views` no longer raise TechDraw's TypeError.
10. **td_lines { action: "style" } made the edge see-through on 1.1.** formatGeometricEdge was given a colour of three numbers; DrawUtil::pyTupleToColor then leaves alpha 0, and from 1.1 Base::Color's alpha 0 is transparent (1 opaque). Alpha 1 is now passed on 1.1 and newer. **Needs a live look**: I read the meaning of alpha in Color.h, not how TechDraw's page item draws it.
11. **td_lines { centerlines } always refused on 1.1**: it called `replaceCenterLine`, which is not in 1.1's Python. `getCenterLine` returns the view's own object, so the change is made on it; replaceCenterLine is used only where present. Not verified that the page repaints.
12. **Lines read before they were there**: td_centermarks, td_hatch and td_dimset read a view's edges without waiting for the hidden-line thread (the others wait). They now wait like the rest.

## What I could not do or verify

- **Degrees of freedom**: FreeCAD 1.1 does not report them to Python. `solve()` returns 0, -1 or -6 only (AssemblyObject.cpp; the -2 … -5 in its own doc string are not returned in 1.1.0), and getLastDoF and friends in the header are not bound. The SOLVE table is right as documented and kept; descriptions and the guide now say "solved is not fully constrained". The assembly model's DoF (1) is by counting, not read.
- **asm_joint and asm_ground cannot take a sub-assembly or an asm_new_part link as a part** (`_parts` needs a Shape; an AssemblyLink and a link to an App::Part have none). Finishing that is a feature (FreeCAD's reference form for it is `[component, ["Child.Face3", "Child.Face3"]]`), so it is only said plainly now, in the tools' text and the guide. Needs a decision.
- **asm_sweep's zero**: from/to count from where the joint stands; asm_pose's `to` and asm_limits count from the joint's own zero, and the sweep's axis is the element's own, which can point the other way from the joint frame's z. They agree only while the joint stands at zero. Documented, not changed (a fix needs the signs proven live).
- **asm_sweep and asm_check are registered as reads but move parts** (the sweep sets placements; both run the solver). jobs.py would run them on a worker thread if asked with background: true. I took the advice to use a job out of their descriptions; a wish for whoever owns jobs.py: keep these two off worker threads.
- **asm_list runs the solver** to answer `solve`, so a "changes nothing" read can move a part that was dragged off its joints. Described now; not changed.
- Wish for health.py: none needed for Assembly beyond the registered line. For TechDraw there is no health line at all (a view with 0 edges, a dimension whose getRawValue raises): worth one.

## Assembly, per tool

Sources for all: JointObject.py, UtilsAssembly.py, AssemblyObject.pyi / AssemblyObjectPyImp.cpp / AssemblyObject.cpp, wiki Assembly_Workbench.md and the page named.

| tool | checked against | wrong and fixed | still doubtful, needs live | description rewritten |
|---|---|---|---|---|
| asm_new | CommandCreateAssembly.py, Assembly_CreateAssembly.md | Type "Assembly" was never set (fix 1); refusal for a part already in an assembly now says what to do | the changed joint path (fix 1) | yes |
| asm_add | CommandInsertLink.py (FreeCAD links; this tool moves bodies in), Assembly_InsertLink.md | refusal text | does not refuse a body that sits in another assembly (asm_new does): it is moved out of the other one | yes |
| asm_ground | CommandCreateJoint.py createGroundedJoint, Assembly_ToggleGrounded.md, getGroundedParts | none: GroundedJoint and ObjectToGround as FreeCAD's | — | yes |
| asm_joint | JointObject.Joint (JointTypes strings all 13 match; Reference form `[part, [el, el]]` is 1.1's component-rooted one; Offset2 as the panel sets it; Distance / Distance2 / Angle), UtilsAssembly.findPlacement, makeMbdJointOfType, Assembly_CreateJoint*.md | fixes 1, 2, 5, 6; "which part moves" was described wrongly | fix 1's path on the Mac: run test_assembly.py and the model; a joint with both parts already joined to ground cannot be flipped (matchJCS returns) | yes |
| asm_joint_remove | — | not_found text | — | yes |
| asm_list | Reference1/2 read both 1.0 and 1.1 forms | description said "changes nothing": it solves | — | yes |
| asm_check | isPartConnected / removeUnconnectedJoints (unjoined parts and their joints are left out of the solve silently) | fixes 3, 4 | the App::Part frame maths (placement of a container applied to its children) | yes |
| asm_sweep | limit properties EnableAngleMin … LengthMax (C++ reads them for Revolute, Slider, Cylindrical), SolveOnRecompute in AssemblyObject::execute | description claimed "solving at each" and gave no limits; steps refusal | zero and sign (above); a closed loop | yes |
| asm_limits | JointObject createProperties, AssemblyObject.cpp limits block (FreeCAD swaps min and max itself; the tool refuses) | refusals | — | yes |
| asm_pose | UtilsAssembly.getJcsGlobalPlc, getJointXYAngle / getJointDistance (same reading as joint_value) | refusals now say why the solver moved it back | closed loops (the model asks for one manual try) | yes |
| asm_motion | Assembly_CreateSimulation.md, CommandCreateSimulation.py: FreeCAD's Simulation object is a different thing and is not used | description called it "a simulation": now says it is Agent Link's own | — | yes |
| asm_explode | CommandCreateView.py (ExplodedView, ExplodedViewStep, References `[asm, ["Part."]]`, saveAssemblyAndExplode), Assembly_CreateView.md | boxes of linked parts (fix 3); refusals | FreeCAD's exploded view is meant to be applied while edited and restored; the tool leaves it applied and suppresses joints — works by reading, not seen live by me | yes |
| asm_bom | CommandCreateBom.py, BomObject.cpp (columnsNames; Index, Name, Quantity, File Name are FreeCAD's own columns), Assembly_CreateBom.md | none: ".Label2" (a dot-led name reads a property) confirmed in BomObject::addObjectToBom; "File Name" and hand-filled columns added to the text | — | yes |
| asm_sub | AssemblyLink.cpp (Rigid, LinkedObject), CommandInsertLink.py | `next` told the agent to asm_joint the sub-assembly, which the tool cannot do (gap above) | — | yes |
| asm_fits | pure geometry on the joint's elements; iso286.py not reviewed | refusals | — | yes |
| asm_export | AssemblyObjectPyImp.cpp exportAsASMT(fileName), Assembly_ExportASMT.md | refusals | — | yes |
| asm_rigid_group (cam_more.py) | no RigidGroupJoint anywhere in 1.1.0's Assembly: "unavailable" is the right answer on the Mac | refusal text | — | yes |
| asm_new_part (cam_more.py) | CommandInsertNewPart.py (a Link in the assembly to a new App::Part) | description and note now say asm_joint / asm_ground cannot take the link | — | yes |

Simulations (1.1, Assembly_CreateSimulation): no tool uses FreeCAD's SimulationGroup / generateSimulation. Not a bug; noted so nobody assumes asm_motion is it.

## TechDraw, per tool

Property and enumeration names checked in 1.1 C++ for: DrawPage (ProjectionType "First angle" | "Third angle", Scale, NextBalloonIndex), DrawProjGroup (Source, Anchor, ProjectionType, AutoDistribute; the ten projection names), DrawViewDimension (Type: Distance, DistanceX, DistanceY, DistanceZ, Radius, Diameter, Angle, Angle3Pt, Area; MeasureType True | Projected; FormatSpec, Arbitrary, TheoreticalExact, EqualTolerance, OverTolerance, UnderTolerance, AngleOverride, LineAngle, ExtensionAngle), DrawViewSection, DrawViewDetail (BaseView, AnchorPoint, Radius, Reference), DrawViewBalloon, DrawLeaderLine, DrawViewAnnotation, DrawViewSpreadsheet, DrawViewSymbol, DrawBrokenView, DrawViewClip, DrawViewImage, DrawViewDraft, DrawViewArch; DrawViewPart's Python methods (the makeCosmetic* family returns tag strings; getEdgeByIndex / getVertexByIndex are unscaled, y down, and raise ValueError past the end); TechDraw.makeExtentDim(view, [edges], 0|1) and writeDXFPage(page, file).
Hidden-line removal in 1.1 (DrawViewPart.cpp): at once with no window; on a QtConcurrent thread in the window. td_wait.py pumps the event loop until every view has visible edges, 30 s at most — so a view with truly nothing to draw waits the whole 30 s (not changed).

| tool | checked | wrong and fixed | still doubtful | description rewritten |
|---|---|---|---|---|
| td_page | DrawPage, DrawSVGTemplate.EditableTexts, template folder names in 1.1 (ISO/, ASME/) | — | template ranking across releases | yes |
| td_title | EditableTexts map | blank-template refusal | — | yes |
| td_view | Source, Direction, XDirection, ScaleType "Custom", Scale, HardHidden | — | — | yes |
| td_projection | DrawProjGroup.cpp addProjection, getDirsFromFront | fix 9 | first/third layout by AutoDistribute | yes |
| td_section | DrawViewSection.cpp (SectionNormal, SectionOrigin, SectionSymbol, SectionDirection Right/Left/Up/Down/Aligned) | fix 8 | — | yes |
| td_section_position | — | — | — | yes |
| td_detail | DrawViewDetail properties | refusal | AnchorPoint maths | yes |
| td_geometry | getEdgeByIndex, getVertexByIndex | — | — | yes (index base, numbers move) |
| td_dim | DrawViewDimension | fix 7; refusals name what was got and td_geometry | — | yes |
| td_dimset | — (calls td_dim) | fix 12 | lane placement | yes |
| td_dim_special | makeExtentDim signature; AngleOverride / LineAngle / ExtensionAngle | refusal | arc_length when a semicircle comes as two quarter arcs (model asks to record) | yes |
| td_dim_format | FormatSpec | — | — | yes (prefix is text only) |
| td_dim_align | — | — | — | yes |
| td_dim_repair | References2D | — | — | yes |
| td_tolerance | EqualTolerance / OverTolerance / UnderTolerance / TheoreticalExact / Arbitrary | — | — | yes |
| td_centermarks | — (own marks, export only) | fix 12 | — | yes (export only; half-turn rule) |
| td_hatch | — (own hatching, export only; FreeCAD's DrawHatch / DrawGeomHatch are not used) | fix 12; refusal | — | yes |
| td_cosmetic | makeCosmeticLine / makeCosmeticCircle return tags; getCosmeticEdge; removeCosmeticEdge | — | _canon's coordinates; the Format tuple's order | yes |
| td_lines | formatGeometricEdge "iidOi"; getCenterLine | fixes 10, 11 | both need a look in the window | yes |
| td_leader | DrawLeaderLine properties | — | — | yes |
| td_note | DrawViewAnnotation Text, TextSize | — | — | yes |
| td_balloon | DrawViewBalloon SourceView, OriginX, OriginY, Text | — | origin units | yes |
| td_table | DrawViewSpreadsheet Source, CellStart, CellEnd, TextSize | empty-sheet refusal | — | yes |
| td_gdt | inputs only; gdt.py not reviewed | — | the frame's drawing | yes |
| td_datum | inputs only | — | — | yes |
| td_finish | inputs only | — | — | yes |
| td_weld | inputs only (FreeCAD's DrawWeldSymbol is not used: own symbol on a DrawLeaderLine) | — | — | one clause (export only) |
| td_area | — | — | — | yes (text does not follow the part) |
| td_view_more | DrawBrokenView, DrawViewClip, DrawViewImage, DrawViewDraft, DrawViewSymbol properties | — | broken view's Breaks objects | yes |
| td_bim | DrawViewArch properties | — | Arch view with no window | yes |
| td_list | — | — | — | yes |
| td_export | writeDXFPage is in the App module (no window needed); TechDrawGui's PDF / SVG export needs the window, which is why SVG and PDF are drawn here | guide said hatching is left out of SVG/PDF while the code draws it: corrected | the drawing code itself (not reviewed) | yes |

Not offered by any td_ tool, for the record: linking a dimension to the 3D model (References3D, MeasureType True — the tutorial's last step), Angle3Pt and Area dimensions, FreeCAD's own centerlines (makeCenterLine), DrawHatch / DrawGeomHatch, DrawRichAnno, DrawWeldSymbol.

## Test models

- Assembly: no tutorial page exists for the built-in workbench (Tutorial_KinematicAssembly.md is for the external Assembly3). Assembly_Workbench.md carries an "Example crank and slider" with the parts' Python and the four joints; the model builds those parts with part_primitive / part_boolean and follows it. 73 calls, all 18 asm_ tools. Three calls need a face name read from the call before (marked `<…>`). Expected DoF 1 is by counting and cannot be read from FreeCAD 1.1.
- TechDraw: Basic_TechDraw_Tutorial.md with the answer key read from Document.xml (page 1: one top view, vertical 26 and horizontal 53, one annotation; page 2: ANSI B, first angle, group at scale 2 with Front, Left, Top, FrontTopLeft, one dimension linked to 3D reading 53 — 43.27 unlinked). 66 calls, 31 of 32 td_ tools (td_bim needs a BIM section plane). Part B is a small plate with a hole and a slot, which proves the diameter leftover live. Several calls need a name read from an earlier reply (marked `<…>`). The Body's box (53 x 26 x 26) is read from the file's first sketch and pad, not measured: the first calls confirm it.
- The Workshop leftover itself (its own diameter callouts) is not touched: other repo.
