# Window review: TechDraw and CAM families (FreeCAD 1.1.3, Agent Link echo)

I looked at all 45 pictures (28 TechDraw, 17 CAM). "Known general" means a problem already on the fix list (Tasks tab, whole-document fit, body selected instead of the new item, no lit button, no caption or a stale one). No picture showed a caption or status words for the call, and no picture showed a lit toolbar button. I count that against every picture but do not repeat it per line.

---

## 1. TechDraw (folder td, 28 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 000-doc_open | doc_open | MINOR | TechDraw wb and Page001 shown; orange warnings in Report view (Refine failed, Edge too small) left from loading; the tutorial file's title-block text is oversized (file problem, not echo). |
| 002-td_list | td_list | BAD | Call asked for "Page" but the window still shows Page001; new red text "Exception TopoShapeExpansion.cpp: Shape index 29 out of bound 0" appears with this call. |
| 004-td_page | td_page | MINOR | New A4 page "Tut A4" shown and framed; page not selected in tree; title block reads Scale 1:1 though scale 2 was asked; Dimension002 now has a red mark in the tree. |
| 011-td_title | td_title | MINOR | Page selected and shown; nothing in the title block visibly changes, so the reader cannot see what was filled. |
| 013-td_note | td_note | MINOR | Note text is on the page, but it is large and overlaps the title block; the page is selected, not the note. |
| 019-td_export | td_export | BAD | Window shows a new page "Tut ANSIB", not the exported "Tut A4"; Report view fills with an Agent Link traceback (techdraw.py resolve_ref, FloatingPointError: invalid bounding box). |
| 020-part_primitive | part_primitive | BAD | Workbench changes to Part, but the drawing page stays in front; the new box "Plate" is not seen; old page still selected. |
| 026-part_boolean | part_boolean | BAD | Same: drawing page stays in front, fused result not seen; "Hole10" is selected (args named Slot/SlotA/SlotB); property panel still shows Tut ANSIB. |
| 029-td_view | td_view | MINOR | New A3 page "Plate drawing" with the top view of Plate, correct; page selected, not the view; old red traceback still filling Report view. |
| 030-td_geometry | td_geometry | MINOR | Read-only call; the circles it found are not highlighted on the page. |
| 031-td_dim | td_dim | MINOR | Diameter 6 dimension shown on the right hole; it is not selected. |
| 036-td_dimset | td_dimset | MINOR | Chain dimension drawn, but its two "30" labels sit on top of each other at the centre and touch "R3". |
| 037-td_dim_special | td_dim_special | MINOR | Arc-length label added, but it lands on the 10 mm hole, on top of other text, and is hard to read. |
| 038-td_centermarks | td_centermarks | BAD | No centre marks appear on any circle (zoomed to check). |
| 039-td_section | td_section | MINOR | Section line A-A and section view shown, right; property panel shows a new "Agent Link" property group added to PlateTop; no "SECTION A-A" label under the view. |
| 040-td_section_position | td_section_position | MINOR | Section A properties shown (Y 100.9); no visible move on the page. |
| 041-td_detail | td_detail | MINOR | Detail circle "B" and detail view shown; detail view has no label; property panel still shows Section A. |
| 042-td_datum | td_datum | BAD | Datum A is on the TOP edge of the view; args asked for the edge through y=0, which is the BOTTOM edge. |
| 043-td_gdt | td_gdt | MINOR | Position frame drawn, but it is small and sits on top of the Ø6 dimension and the detail circle. |
| 045-td_balloon | td_balloon | BAD | Balloon "1" is attached to the Detail B view; args asked for the corner (60,40) of PlateTop. |
| 046-td_leader | td_leader | BAD | Leader starts at the bottom-left corner (args asked top-left, y=40); the text "Break sharp edges" floats over the slot, away from the leader end. |
| 047-td_finish | td_finish | MINOR | Ra 1.6 symbol drawn and a leader on the left edge, but the symbol is far from the leader, on top of the Ø10 dimension. |
| 048-td_weld | td_weld | BAD | Only a bare leader at the top-right corner (args asked bottom-right, y=0); no weld symbol is drawn. |
| 049-shape_query | shape_query | MINOR | Read-only; drawing stays in front, the found face is not shown or highlighted in 3D. |
| 052-td_cosmetic | td_cosmetic | BAD | Cosmetic line runs top-left to bottom-right (args: (0,0) to (60,40) = bottom-left to top-right); the centre circle is correct; thread not visible. |
| 053-td_lines | td_lines | MINOR | No visible change (3 mm extension at this zoom); cannot confirm the result. |
| 058-sheet_new | sheet_new | BAD | Workbench changes to Spreadsheet, but the drawing page stays in front; the new sheet "Parts" is not opened or selected. |
| 061-td_view_more | td_view_more | MINOR | PlateTop properties show Lock Position = Yes, right; an empty unlabelled table has appeared on the page (from an earlier call), and the property panel shows Agent Link data (JSON points) stored on the view. |

**Counts (TechDraw):** GOOD 0 / MINOR 17 / BAD 11

### Problems particular to TechDraw

1. **Y axis flipped for annotation anchors** (042, 046, 048, 052; likely 045). Points and edges given in model coordinates are placed mirrored top-to-bottom on the page for datum, leader, weld and cosmetic line. Dimensions and the detail circle (041, centre (45,30)) are placed correctly, so the problem is only in the anchor code for annotations. The echo cannot fix this; the tool must map model Y to page Y the same way td_detail and td_dim do. The echo should, after each annotation, zoom to the anchor point so a wrong side is easy to see.
2. **Wrong target view** (045). The balloon attached to the detail view, not PlateTop. The tool should attach to the named view only.
3. **Missing symbol content** (038 centre marks, 048 weld symbol, 052 thread). The call is accepted but nothing (or only a leader) is drawn. The echo should check that the new object has visible geometry and write a warning caption if it does not.
4. **Agent Link traceback in Report view** (019, then left on screen through 061). FloatingPointError in techdraw.py resolve_ref (invalid bounding box). It stays visible for 20+ pictures. The tool should catch it; the echo should clear or scroll Report view to the current call's lines.
5. **Wrong page in front** (002, 019). td_list on "Page" and td_export of "Tut A4" both leave another page in front. The echo should bring the named page tab to the front.
6. **3D tools leave the drawing in front** (020, 026, 049, 058). After part_primitive, part_boolean, shape_query and sheet_new the workbench changes but the page stays. The echo should switch to the 3D view tab of the document (or open the new spreadsheet) before fitting and selecting.
7. **Text and symbols overlap** (013, 036, 037, 043, 046, 047). New items land on top of existing items. The tools should offset labels away from existing items; the echo should zoom to the new item so overlap is visible.
8. **Property panel stale** (026, 041 to 058). It shows the previous object (Detail B for many calls) because the new item is not selected. Select the new annotation.
9. **Agent Link properties on user objects** (039, 061). An "Agent Link" property group (scale 2.00, JSON points) is added to PlateTop and shows in the property editor. Consider hiding these properties (hidden status) so the user does not see internal data.
10. **Red mark on Dimension002** appears at 004 after the exception at 002; it stays for the rest of the run.

### TechDraw tools proven live in the window (GOOD or MINOR, result shown correctly)

doc_open, td_page, td_title, td_note, td_view, td_dim, td_dimset, td_dim_special (readable only when zoomed), td_section, td_section_position, td_detail, td_gdt, td_finish, td_view_more.

Not proven (MINOR but nothing to see): td_geometry, shape_query, td_lines.

---

## 2. CAM (folder cam, 17 pictures)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-part_primitive | part_primitive | MINOR | Part wb, Block selected and framed, right; Report view still shows red BIM tracebacks (ArchWall DiffuseColor) from the earlier ArchHouse document. |
| 003-part_boolean | part_boolean | MINOR | Pocket cut shows in the block; tree still shows only "Block" (no Cut result object seen); property panel empty. |
| 006-cam_job | cam_job | MINOR | CAM wb, job, stock and tools made; Block selected, not the job "Walkthrough"; job icon hidden (grey). |
| 008-cam_op | cam_op | BAD | No profile toolpath is drawn in the 3D view; Operations folder not opened; nothing selected. |
| 012-cam_list | cam_list | MINOR | Read-only; Report view shows red traceback "EdgeWalker has no edges to load" from the Pocket op made just before; still no toolpaths on screen. |
| 013-cam_sim | cam_sim | BAD | Nothing is shown: no simulator, no path, no stock removal. |
| 014-cam_post | cam_post | MINOR | Report view says "done postprocessing"; no file name or G-code shown. |
| 017-cam_tool_add | cam_tool_add | MINOR | Tool "Drill 5" not shown; Tools folder closed and greyed; nothing selected. |
| 020-cam_dressup | cam_dressup | BAD | No tags and no path on screen; the base op "Profile" now sits at document root, hidden; property panel shows Drill001 (stale). |
| 021-cam_setup | cam_setup | MINOR | Drill001 clearance changes to 31 mm (effect seen); Path.Area warning in Report view. |
| 022-cam_edit | cam_edit | MINOR | Optional stop not shown; "SetupSheet has no support for Optional stop" info line. |
| 026-cam_library | cam_library | MINOR | Export call; nothing to see; no caption naming the file. |
| 027-cam_tool | cam_tool | MINOR | Feed change not shown; property panel stale (Drill001). |
| 028-cam_path | cam_path | MINOR | "Hard stop" not shown or selected (only appears in the panel one call later, picture 030). |
| 030-cam_property_bag | cam_property_bag | MINOR | "Limits" appears at document root (hidden); property panel shows "Hard stop" (stale), not Limits. |
| 031-cam_template_export | cam_template_export | MINOR | Nothing to see; no caption naming the template file. |
| 032-cam_remove | cam_remove | MINOR | "Profile" is gone from the tree, right; the tags dress-up that used it cannot be seen (Operations closed). |

**Counts (CAM):** GOOD 0 / MINOR 14 / BAD 3

### Problems particular to CAM

1. **No toolpaths are ever drawn** (008 through 032). Profile, Pocket, Drill and the tags dress-up all exist, but the 3D view shows only the model and stock. The echo should, after cam_op / cam_dressup / cam_path, make the op visible, recompute it, hide or make the stock transparent, and fit to the path so the green lines show.
2. **cam_sim shows nothing** (013). With inline=false the simulator window should open (or, if it cannot open in background mode, the echo should show the path and write a caption that the sim ran headless with its result).
3. **Pocket op fails silently** (012). Red "EdgeWalker has no edges to load" in PocketShape.py. The tool accepted the call. It should report the failure; the echo should write a warning caption.
4. **Job tree hidden or closed** (006 on). The job "Walkthrough", Model, Tools and SetupSheet are grey and the Operations folder is never opened, so new ops, tools and stops are never seen. The echo should open the Operations (or Tools) folder and select the new child.
5. **Objects outside the job** (020, 030). After the dress-up, "Profile" sits hidden at document root; "Limits" (property bag) also at root. The first one looks like a leftover. Check that the dress-up keeps its base op under the job.
6. **File results not named** (014, 026, 031). Post, library export and template export give no caption with the file path. The echo should say the file name and size.
7. **Stale errors from other documents** (001 onward). BIM tracebacks from ArchHouse stay in Report view. Scroll or mark the start of this call's output.
8. **Property panel stale** (020 to 030). Shows Drill001 or Hard stop instead of the item each call changed.

### CAM tools proven live in the window (GOOD or MINOR, result shown correctly)

part_primitive, part_boolean, cam_job, cam_setup (seen in Drill001 clearance), cam_property_bag (Limits in tree), cam_remove (Profile gone from tree).

Not proven (MINOR but no result on screen): cam_list, cam_post, cam_tool_add, cam_edit, cam_library, cam_tool, cam_path, cam_template_export.
