# Window review, round 6: ScanRuler add-on, folder sr-a

Pictures: `pics6/sra` (63, all listed in pictures.json). I looked at every picture at full size and at enlarged crops of
0017, 0019, 1000, 1005, 1009, 1016, 2018, 3000, 3001, 3003 (legend) and 3017.
Compared with round 3, sr-a part (`window-r3-scanruler-findings.md`) and the claimed fixes in `sr4-findings.md`.
No code was read. No other file was changed. No Mac tools were used.

Limit: the Report view is not shown in any round-6 picture (the right dock shows an empty Tasks panel), so error text
and the RuntimeWarnings of round 3 could not be checked.

## Counts

| folder | pictures | GOOD | MINOR | BAD |
|---|---|---|---|---|
| sr-a round 6 | 63 | 24 | 32 | 7 |
| sr-a round 3 | 63 | 6 | 32 | 25 |

Ring on the right button: 0001, 0003, 0007, 0019, 1000, 1005, 1009, 2010 (kept through 2016), 4011, 4017, 4019
(4007-4010 ring a Make button). Caption present and specific: 57 of 63 (tool name only in 2002, 2004, 2007, 3004,
4003, 4007, 4009).

## Per-picture table

| picture | tool | rating | reason |
|---|---|---|---|
| 0001 | part_primitive | GOOD | Primitives ring, Block selected, volume in caption. |
| 0003 | part_boolean | GOOD | Cut ring, bore visible, caption with volume. |
| 0004 | part_transform | MINOR | Worn selected; caption says "Moved Block", not copy Worn. |
| 0007 | meshobj_from_shape | GOOD | Mesh ring, WornScan selected, Mesh Info sensible. |
| 0008 | scan_open | MINOR | ScanRuler bench and caption now; no ring on Open Scan. |
| 0009 | scan_info | GOOD | Caption gives triangles and size. |
| 0010 | scan_qa | GOOD | Caption gives rims and noise. |
| 0014 | mesh_densify | MINOR | Edited copy drawn; panel shows Reduce section; workspace label blank. |
| 0015 | mesh_use_edited | GOOD | Caption and panel agree, 219,600 triangles. |
| 0017 | scan_nearest | MINOR | Point and line drawn but tiny; label unreadable. |
| 0018 | scan_query | GOOD | 23,465 marked points drawn purple; count in caption. |
| 0019 | element_fit_marked | BAD | Plane Top not visible: no orange patch, no label. |
| 1000 | element_fit | MINOR | Bottom drawn blue, old Top orange (colours swapped); old marks remain. |
| 1005 | element_construct | MINOR | Point ring; Corner a tiny blue dot; all old elements orange. |
| 1009 | dimension_add | MINOR | Ring; Height line drawn blue; label unreadable. |
| 1016 | dimension_set_basic | MINOR | Caption "Ang = 1.047 mm": angle in mm, not 89°. |
| 1017 | dimension_set_limit | MINOR | BoreDia line marked; caption good; labels unreadable. |
| 1019 | dimension_remove | GOOD | Caption names Ang; DIM 7 to 6. |
| 2001 | element_rename | GOOD | Edge1 marked blue; caption names it. |
| 2002 | element_unlink | MINOR | Caption is tool name; no visible change. |
| 2004 | element_set_visible | MINOR | Caption says "visible" for a hide; hide not visible. |
| 2005 | element_remove | GOOD | Caption names Edge1; elements 10 to 9. |
| 2006 | element_list | GOOD | Caption gives 9 elements. |
| 2007 | report_get | MINOR | Caption "Report" only; report not shown. |
| 2009 | export_csv | GOOD | Caption names the CSV. |
| 2010 | section_cut | GOOD | Section ring; Mid loop drawn at z 10. |
| 2011 | section_list | GOOD | Caption gives count; sections drawn. |
| 2012 | section_get | GOOD | Mid highlighted; caption gives chains. |
| 2013 | section_fit | MINOR | Fitted shapes not drawn; caption gives no fit. |
| 2016 | section_remove | GOOD | Caption: removed, 1 left. |
| 2018 | section_to_sketch | MINOR | Sketch not seen or selected under overlay; tree hidden. |
| 3000 | element_to_document | MINOR | New objects hidden by overlay; one green face only. |
| 3001 | scan_segment | MINOR | Segments coloured; top speckled, 155 regions; old selection left. |
| 3002 | scan_fit_surface | MINOR | Only a tiny normal line; no surface patch. |
| 3003 | scan_draft | MINOR | Draft map shown; legend has no title or numbers. |
| 3004 | scan_pattern | MINOR | Caption tool name; nothing drawn. |
| 3005 | scan_heightmap | MINOR | Height map shown; legend unlabelled; old green selection. |
| 3008 | scan_outline | MINOR | Outline loops faint thin blue on top edge. |
| 3009 | scan_cloud | GOOD | Caption names the file. |
| 3010 | scan_thread | GOOD | Bore axis marked; caption "thread: none". |
| 3011 | thickness_measure | MINOR | Thickness map shown; legend unlabelled; workspace label blank. |
| 3012 | thickness_settings | GOOD | Map kept; caption gives 119 thin spots. |
| 3013 | deviation_open_reference | GOOD | Block selected; Deviation panel; caption. |
| 3014 | deviation_align | MINOR | Map and RMS shown; range ±0.001 mm; pocket hidden. |
| 3015 | deviation_settings | GOOD | Caption with RMS and ±1 mm; map kept. |
| 3016 | deviation_measure | MINOR | All green; worn pocket hidden by selected reference. |
| 3017 | deviation_hotspots | BAD | Hot spot is a 4 px dot, no label. |
| 3018 | deviation_volume | BAD | Volume error region not drawn. |
| 3019 | deviation_export | GOOD | Caption gives result. |
| 4001 | deviation_set_target | MINOR | Map on Top only; pocket hidden by selection. |
| 4003 | wear_setup | BAD | Old 23,465 marks return; tagged region not drawn. |
| 4004 | wear_diff | MINOR | Wear shown only as rim ring; "lost -1 mm". |
| 4005 | wear_rebuild | MINOR | File named; repaired mesh not shown. |
| 4006 | wear_prewarp | GOOD | Caption names the file. |
| 4007 | fit_scan_setup | BAD | Switches to Make workbench; caption tool name. |
| 4008 | fit_scan_features | BAD | Make workbench; features not drawn. |
| 4009 | fit_scan_measure | BAD | Make workbench; no measured value; caption tool name. |
| 4010 | fit_scan_export | MINOR | File named; still Make workbench. |
| 4011 | align_datum | MINOR | Ring, scan moved; sections stay at old place. |
| 4015 | align_clear | GOOD | Scan and overlay back in place; caption clear. |
| 4017 | align_auto | MINOR | Ring; caption explains; sections left behind. |
| 4018 | align_symmetry | MINOR | Moved, RMS in caption; symmetry plane not drawn. |
| 4019 | scan_scale | MINOR | Ring, factor in caption; Block cut off at right edge. |

## Round-3 problems: status

| round-3 problem | status | pictures |
|---|---|---|
| 1. Results never drawn | PARTLY | Fixed: 0017, 0018, 1000, 1005, 1009, 2010-2016, 3010. Still missing or nearly invisible: 0019, 2013, 3002, 3017, 3018, 4008, 4018. |
| 2. No colour map or legend | PARTLY | Maps now show: 3001, 3003, 3005, 3011, 3012, 3014-3019, 4001, 4004, 4009. Legend has no title or tick numbers. Map goes away when not needed: 3004, 3008, 4011. |
| 3. Mesh edits not shown | FIXED (sr-a part) | 0014 shows the edited copy in the scan's place. |
| 4. Wrong workbench (scan_open/info/qa in Mesh) | FIXED | 0008-0010 in ScanRuler. New: fit_scan_* go to Make (4007-4010). |
| 5. Stale captions | FIXED | 3001, 3005, 3011, 3016 now correct. |
| 6. Missing captions | FIXED | 3014, 3018, 4001 have captions. |
| 7. RuntimeWarnings in Report | NOT CHECKED | Report view not shown in round 6. |
| 8. align_auto offset, no RMS | PARTLY | 4017 caption says "to its own axes", moved 36.056 mm; offset by design. |
| 10. Panel section not following | PARTLY | 3013-4006 now Deviation (right). Still wrong: 0014 Reduce, 0017/0018 Mesh Tools. |
| 11. Blank workspace label (0014) | NOT FIXED | 0014, 3011. |
| 11. 0004 property label Block | FIXED | Shows Worn; but caption says "Moved Block". |
| Selection left from 3000 | NOT FIXED | Green bore face stays 3001-3011. |
| Lit button for construct and section | FIXED | 1005 Point ring, 2010 Section ring. |

## Family-particular problems (most important first)

1. **fit_scan_* tools switch to the Make workbench** (4007, 4008, 4009, 4010). The Make panel shows "No setups yet",
   which has nothing to do with the call. They should stay in ScanRuler and show the Fit Scan section.
2. **New and old overlay colours are swapped.** The new thing is blue and every older element is orange
   (1000, 1005, 1009, 1017, 2010). sr4 says the new one is orange and the rest in panel colours. Draw only the new one orange.
3. **Overlay labels are about 6 px and cannot be read** (all pictures with elements, 1005-4019). The dimension
   value ("Height 20.000 mm") cannot be seen. Make labels larger, and give the new one a bigger label.
4. **Legend has no title and no numbers** (3003, 3005, 3011, 3014-4010). It also stands over the right side of the part.
   Show "DEVIATION · MM" and ticks, and place it clear of the part.
5. **The selected reference hides the deviation result.** From 3013 the Block is selected and drawn green over the
   worn pocket, so the 1 mm pocket loss never shows in 3016-4010; the hot spot (3017) is under it. Do not leave the
   reference selected over the map, or draw the map in front.
6. **Overlay does not follow the scan's pose.** After align_datum, align_auto and align_symmetry the sections and the
   Bore ring stay at the old place while the scan and elements move (4011, 4017, 4018, 4019).
7. **Marked points stay and come back.** The 23,465 marks of 0018 stay through 0019 and 1000 and return at wear_setup
   (4003). Marks should show only for the call that made them; wear_setup should draw its tagged box.
8. **Results still not drawn:** element_fit_marked plane (0019), section_fit shapes (2013), fit-surface patch (3002),
   hot spot (3017, 4 px), volume errors (3018), fit-scan features (4008), symmetry plane (4018).
9. **Overlay hides FreeCAD objects made from it** (2018 sketch, 3000 Top/Bore/Corner/Mirror). In round 3 these
   showed and were selected. Dim the overlay or show the new objects in front. WORSE than round 3.
10. Wrong words: 1016 gives the angle as "1.047 mm" (should be 89°); 2004 says "visible" for a hide; 4004 says
    "lost -1 mm".
11. scan_segment finds 155 regions on a simple block, and the top face is speckled (3001). The densified top may be
    over-split. Check in ScanRuler.
12. 4019 frames the scan but cuts off the Block on the right.

General (known) problems, counted only: ScanRuler tab in front of Model in every ScanRuler picture; lit button missing
on most changing calls; tool-name captions in 7 pictures.

## Proven live

PROVEN_LIVE ScanRuler: part_primitive, part_boolean, part_transform, meshobj_from_shape, scan_open, scan_info, scan_qa, mesh_densify, mesh_use_edited, scan_nearest, scan_query, element_fit, element_construct, dimension_add, dimension_set_limit, dimension_remove, element_rename, element_remove, element_list, export_csv, section_cut, section_list, section_get, section_remove, scan_segment, scan_fit_surface, scan_draft, scan_heightmap, scan_outline, scan_cloud, scan_thread, thickness_measure, thickness_settings, deviation_open_reference, deviation_align, deviation_settings, deviation_measure, deviation_export, deviation_set_target, wear_diff, wear_rebuild, wear_prewarp, align_datum, align_clear, align_auto, align_symmetry, scan_scale
NOT_PROVEN ScanRuler: element_fit_marked (plane not visible), dimension_set_basic (angle shown as mm), element_unlink (no visible change, tool-name caption), element_set_visible (caption says visible, hide not seen), report_get (report not shown), section_fit (fits not drawn), section_to_sketch (sketch not seen under overlay), element_to_document (new objects hidden by overlay), scan_pattern (nothing shown, tool-name caption), deviation_hotspots (4 px marker), deviation_volume (not drawn), wear_setup (old marks, region not drawn), fit_scan_setup (Make workbench), fit_scan_features (Make workbench, not drawn), fit_scan_measure (Make workbench, no value), fit_scan_export (Make workbench)
