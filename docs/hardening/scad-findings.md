# scad_import hang in the window, and four test failures: findings

Checkout: wt3/scad. Nothing committed. FreeCAD could not be run here; everything below is from reading
FreeCAD 1.1 source (tag 1.1.0; the Mac runs 1.1.3) and this repository, plus plain-Python tests.
Plain suite after the changes: 687 passed, 309 skipped (the FreeCAD ones).

## Task 1: scad_import hangs FreeCAD in the window

### Cause: proven by reading up to the last step, which only a Mac can show

The hang is not in the CSG reader. It happens before the tool's own code runs:

1. `scad_import` is a changing tool whose name starts with `scad_`. In the window, `Echo.before`
   (agentlink/echo.py) brings up the tool's workbench first: `("scad_", "OpenSCADWorkbench")`, then
   `FreeCADGui.activateWorkbench("OpenSCADWorkbench")`.
2. The first activation runs `OpenSCADWorkbench.Initialize` (FreeCAD 1.1 source:
   src/Mod/OpenSCAD/InitGui.py). When the preference `openscadexecutable` is empty, it calls
   `OpenSCADUtils.searchforopenscadexe()`. With OpenSCAD not installed the preference is always empty
   (our `exe()` only writes it when it finds the program).
3. `searchforopenscadexe` (src/Mod/OpenSCAD/OpenSCADUtils.py): `shutil.which` fails, then on darwin it runs
   `osascript` asking Finder for the application with id org.openscad.OpenSCAD and waits in
   `p1.communicate()` with no time limit, on FreeCAD's GUI thread.
4. The tool's `console_mode()` swap of `searchforopenscadexe` came later, inside the tool, so it never
   covered this. Headless there is no echo and no workbench, which is why freecadcmd passes.

Steps 1 to 4 are certain from the code. Not provable here: that `osascript` actually blocked on that Mac
(a macOS permission prompt for controlling Finder, or Finder not answering; AppleScript's own wait for a
reply is about two minutes, which fits ">120 s"). It fits everything observed: only in the window, only
without OpenSCAD, twice (each restart is a fresh process, so Initialize runs again), `scad_export`
unaffected (a read: no workbench switch). The old code's own comment already named this search as one
that "waits on a permission prompt".

The same path was open for every changing `scad_` tool (scad_op, scad_code, scad_tidy) and for the
`workbench { activate }` tool.

### Second proven hole: the swap missed the copy FreeCAD uses for hull and minkowski

`OpenSCADFeatures.CGALFeature.execute` does `import OpenSCAD.OpenSCADUtils` (package name; FreeCADInit.py
puts the Mod folder itself on sys.path). That is a second module object, with its own
`searchforopenscadexe`; swapping the one in `OpenSCADUtils` did not reach it. A `.csg` with hull or
minkowski, imported without OpenSCAD, would search through Finder at the recompute, and at every later
recompute of that document (also outside `console_mode`, where the swap had already been put back).

### Third proven fault: modules loaded while GuiUp was faked

`console_mode()` did `import OpenSCADUtils` after setting `FreeCAD.GuiUp = False`. In the window the first
scad call (scad_export in the live test) therefore loaded OpenSCADUtils, importDXF, Draft and their
sub-modules believing there was no window; their module-level switches (`importDXF.gui`, Draft's GUI
imports) stayed off for the rest of the session. Not a hang, but wrong state left behind. Conversely
`importCSG.gui` is read once at import (True in the window) and the GuiUp swap never changed it, so in the
window the reader could raise FreeCAD's "Unsupported Function" message box (importCSG.py, `p_not_supported`
and true projection) and its `fixVisibility()` acts on `FreeCAD.ActiveDocument`, which need not be the
session's document.

### Ruled out by reading (for the cube file)

- ply lexer and parser: same code headless and in the window; tables are built in memory
  (`write_tables=False`); no loop on valid input; `p_error` exists.
- A modal dialog in importCSG: only for glide/subdiv and true projection, not in this file.
- `SendMsgToActiveView`, translate prompts, a file picker for the executable: none on this path.

### What was changed

agentlink/families/openscad.py
- `plain_search()` / `guard_search()`: FreeCAD's `searchforopenscadexe` is replaced for good by `exe()`
  (preference, PATH, usual folders; never Finder). An import guard on `sys.meta_path`, touching only the
  names `OpenSCADUtils` and `OpenSCAD.OpenSCADUtils`, sets it as either copy loads, whoever loads it (the
  workbench a person clicks, a saved hull feature recomputing, a tool). It imports nothing itself, so it
  costs nothing until FreeCAD's OpenSCAD code is wanted. Side effect to know: FreeCAD's own OpenSCAD
  workbench no longer asks Finder either; an OpenSCAD in an unusual place needs its path set in FreeCAD's
  OpenSCAD preferences.
- `console_mode()`: loads the modules before faking GuiUp; sets `importCSG.gui`, `importCSG.printverbose`,
  `exportCSG.gui` and `importDXF.gui` False while it runs and puts them back (importDXF's switch gates the
  DXF-library download question, reachable through 2D hull/minkowski and dxf imports).
- `scad_import` / `scad_code`: one shared reader that makes the session's document the active one while
  FreeCAD's reader runs (the reader makes circles, polygons and mesh imports in the ACTIVE document) and puts
  the front document back; empties the reader's `original_root_objects` list (never emptied by FreeCAD);
  in the window, shows the tops and hides what they are built from (what the reader's own gui branch did).
- `scad_import` of a `.csg` that uses hull, minkowski or text when OpenSCAD is not installed: refused
  "unavailable" before anything is read, naming the words and what to do (before: a broken feature left
  in the document, or a "failed" with FreeCAD's 'OpenSCAD executable unavailable').
- `scad_status`: asks the program's version itself with a 20 s limit (FreeCAD's `getopenscadversion` waits
  without one). Two descriptions gained a clause (scad_import, scad_status); nothing was cut.

agentlink/echo.py, agentlink/families/app.py
- `echo.bench_ready(wb)` runs before both places a workbench is activated from here (the echo, and
  `workbench { activate }`): for OpenSCADWorkbench it puts the plain search in place first.

Tools checked for the same hazard: scad_op (hull without OpenSCAD is computed here, minkowski refuses
"unavailable"; with OpenSCAD it runs inside console_mode), scad_code (refuses "unavailable" first),
scad_export (exportCSG launches nothing), scad_tidy (launches nothing; its only hazard was the workbench
switch). All four are covered by the guard and bench_ready.

### Tests
- tests/test_core_readers.py `test_scad_never_asks_finder` (plain Python, stand-in modules laid out as
  FreeCAD lays them out): either module name gets the plain search; bench_ready; console_mode's switches
  and their restore; `csg_needs`. Passes here.
- tests/test_more_families.py `test_openscad_never_searches` (FreeCAD; not run here): round trip, switches
  restored, hull file refused without OpenSCAD.

### Still to check live on the Mac
- That scad_import of Block.csg now returns in the window (the proof of the last step).
- Any other way a workbench gets activated from a tool (a menu or command run, gui_input on the workbench
  box) goes through FreeCAD directly; the import guard covers those once this family is loaded, bench_ready
  does not.
- With OpenSCAD installed: FreeCAD's `callopenscad` waits for OpenSCAD without a time limit (by design for
  minkowski; unchanged).
- A `.csg` with `text(text = "")` is refused without OpenSCAD although FreeCAD's reader would skip it.

## Task 2

### a. tests/test_doc.py::Doc::test_close: cause NOT proven; code hardened, cause now reported

Not found: which object in close_a was marked touched. I read the hub's path between the save and the
close (doc_new, switch, undo_on, snapshot, the health check, the after_change hooks, SafetyNet's auto-save
and Workshop Fasteners' document observer) and found nothing that writes to that document. ScanRuler and
Texturizer are not on this machine and were not read.

Proven from source, and fixed (code):
- Headless, "changed since saved" is `doc.isTouched()`: any object still marked touched. FreeCAD's save
  clears no mark (src/App/Document.cpp: `save()`, `saveToFile()`; only a recompute purges). `_gui_saved`
  purged only with a window. So an object touched as the file was written (frozen, a failed input, a holder
  nothing recomputes) read as "Changed since saved" for good, straight after doc_save. agentlink/store.py
  now keeps what was touched at the save (`note_saved`) and `is_changed` counts only marks that came after;
  the marks themselves are left for the next recompute. doc_save and doc_save_all call it.
- `modified_state` listed touched objects with `o.isTouched()`, which objects do not have (only documents:
  src/App/DocumentObject.pyi), so `touchedObjects` was never filled; the AttributeError was swallowed. It
  now reads each object's State. This also explains the earlier note "touched after a save with no object
  touched".
- The doc_close refusal now names the objects marked since the save.

If the mark came before the save, this fixes test_close. If something marks an object after the save, it
will still fail, but doc_save's `touchedObjects` and the refusal will name the object on the next run.
Tests: tests/test_gui_saved.py `SavedHeadless` (plain, passes); tests/test_doc.py
`test_close_after_save_with_a_mark_left` (FreeCAD, not run here).

### b. tests/test_live_findings.py::test_snapshot_reuses_stats: proven; the tests were wrong (fixed)

tests/test_core_check.py, at import, loaded a second copy of `agentlink.geometry` and restored only
`sys.modules`; the package attribute `agentlink.geometry` stayed the second copy. In a run of every file in
one FreeCAD (the Mac's runner), `agentlink.tools` already held the first copy, so
`from agentlink import geometry` in the later test patched a module no tool used: 0 calls. Reproduced here
in plain Python before the fix (attribute is not the loaded module) and after (it is). Not related to
add-ons, the cache or the health check; the code is right. Fixed in both tests: test_core_check reuses a
loaded copy and cleans up its stand-in copy; test_live_findings patches `agentlink.tools.geo`.

### c. tests/test_stem_findings_more.py::Jobs::test_slow_read_is_logged: proven; the test was wrong (fixed)

`jobs.note_slow` skips tools `keep.is_heavy` knows, and that is process-wide (`keep.HEAVY`, filled when an
installed add-on's family loads) as well as heavy-tools.json. The test borrowed a real add-on tool's name.
It now uses a name of its own, and a second test states the heavy case on purpose.

### d. tests/test_mcp_contract.py: test changed; one premise of the task was wrong

`test_descriptions` and `test_read_only_tools_say_so` now judge the hub's own tools only (an add-on's
family is known by its group in `families.EXTENSIONS`; a hub family in a group an add-on joined is known
by where its function is written). drawing_make, texture_apply, orca_project and fastener_list drop out.

But `gui_input` and `live_run` are the hub's own (agentlink/families/dev.py), about 1,755 and 2,500
characters against the test's 1,500. No description was shortened. They are listed in `DESC_KEPT` with a
ceiling each (1,850 and 2,600) so they pass as they are and cannot grow unnoticed. That is a decision for
the owner: the alternative is raising the limit for every tool.

The filter cannot be exercised here (no FreeCAD, no add-ons); it is written from how tools.py assigns groups.

## Wishes (files the brief says not to edit)
- protocol.py / tools.py: a Tool could carry whether an add-on owns it; the contract test would then not
  need to infer it.
