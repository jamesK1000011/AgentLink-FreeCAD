# hubfix2: findings (16 Nov 2026)

Checkout: d8 at b408a91. Patch: `hubfix2.patch` (new files included, FILES excluded).
Nothing here was run in FreeCAD. "Source" means FreeCAD 1.1.0's source as checked out (the Mac runs 1.1.3);
"tested" means plain-Python tests on stand-ins. `tests/test_hubfix2_fc.py` holds the same against a real
FreeCAD; it is skipped here and was written unrun.

## Before this is pinned

1. **Regenerate FILES.** New: `agentlink/changes.py`, `agentlink/docstates.py`, `agentlink/around.py`,
   `tests/test_hubfix2.py`, `tests/test_hubfix2_fc.py`. `tools.py` imports the first two and
   `protocol.py`, `echo.py`, `outputs.py` the third: without them in FILES the installed add-on fails at
   import. `tests/test_files.py` fails here until then (expected).
2. **Family files touched** (the smallest edits; other agents are in these folders):
   - `families/doc.py`: `open_labels()` added, one line of `doc_close` uses it, one clause added to
     doc_close's description.
   - `families/pd_common.py`: `newly_broken()` added; `settle()` uses it (one line).
   - `families/sheet.py`, `families/param.py`, `families/sketch_more.py`: `pc.broken` → `pc.newly_broken`
     in their refuse-and-roll-back guards (1, 2 and 1 lines).
   - `agentlink/data/tools.json`: not touched.
3. `agentlink/tools.py`'s `batch` description gained two passages (the `around` split, the brief verdict
   lines). No description was shortened.

---

## 1. Family state followed the session into another document — fixed

- **Cause.** `families/doc.py` `switch()` (doc_new, doc_open, doc_close) set `session.doc` and left
  `session.family_state`; only `Session.switch` (doc_switch, doc_revert) emptied it — and that lost the
  state on the way back. The window link (`gui_link._ready`) also sets `session.doc` directly.
- **Fix.** `session.doc` and `session.family_state` are properties of `Session`; `agentlink/docstates.py`
  keeps one dict per document. Whatever sets `session.doc`, the dict of the document left is set aside
  under that document while it stays open, and the document arrived in gets its own back, or an empty
  one. Documents are told by identity (one Python object per open document; source:
  `src/App/Document.cpp`, `DocumentPythonObject`), so a document closed and reopened, or reverted, starts
  empty. Because it hangs on the property, no family file needed a change for this.
- **The hook** (documented in `docs/hooks.md`, "State per document", and in `hooks.py`'s header):
  events `document_state_leaving(session, doc, state)` and `document_state_entered(session, doc, state,
  restored)`; `hooks.own_document_state(key)` for an add-on that settles its own state.
- **ScanRuler.** Its `scanstate.settle` expects, on arriving in another document, to find the state of
  the document it left still under its key (it then writes it into that document and sets it aside
  itself). So a key whose add-on settles itself is carried along untouched. ScanRuler needs no change:
  a key is also taken as self-settling when the session carries the attribute `_<key>_documents`, which
  is exactly the book ScanRuler already keeps (`_scanruler_documents`). Calling
  `hooks.own_document_state("scanruler")` from its `agentlink_families` would say the same explicitly;
  recommended when ScanRuler is next touched, not required.
  One difference, for the better: doc_switch used to empty the state before ScanRuler saw it (so
  whatever a job had left unwritten was lost); now ScanRuler's settle gets it and writes it.
- **Tests.** `test_hubfix2.py` `StatePerDocument` (7), `TheSession.test_family_state_follows…` (the real
  `Session` on a stand-in FreeCAD), `WithAnAddOnsOwnSettle` (runs when ScanRuler is importable: passes
  here with ScanRuler's checkout on the path). Also run here, not in the repo: ScanRuler's own seven
  `StatePerDocument` tests with its context given the hub's two properties — all pass.
- **Changed behaviour to know.** Workshop's SafetyNet keeps its checkpoints under
  `family_state["safetynet"]`: they now stay with their document and come back on doc_switch (before:
  carried into a new document by doc_new, dropped by doc_switch). Its `reopen_copy` (keeps the dict,
  `session.switch`, puts it back) works as before through the setter.
- **Live.** `scan_open` in document A; `doc_new`; `scan_info` → no scan; `doc_save` of the new document →
  small file; `doc_switch` to A → `scan_info` shows the scan with its elements; `doc_close` of the new one →
  A's state still there. `history_checkpoint` in A, `doc_new`, `doc_switch` back, `history_restore` → found.

## 2. A call that changed nothing was an undo step — fixed (two causes; one part unproven live)

- **How FreeCAD 1.1 reports emptiness** (source: `src/App/Document.cpp` `openTransaction`,
  `_checkTransaction`, `commitTransaction`, `_commitTransaction`, `isTransactionEmpty`;
  `src/App/AutoTransaction.cpp` `setActiveTransaction`, `closeActiveTransaction`;
  `src/App/Transactions.cpp` `addObjectNew`, `addObjectDel`, `isEmpty`, `getMemSize`):
  - `openTransaction(name)` only names the application's active transaction; the step is made at the
    first recorded change. Python can ask one thing: `Document.HasPendingTransaction`.
    `Transaction::isEmpty` has no binding; `getMemSize` returns 0.
  - `commitTransaction()` with no step pending does nothing — **and leaves the name active**. The next
    change anyone makes (a read's leftover, the person) is then recorded as a step under that old name.
    `abortTransaction()` likewise after a refusal.
  - A step whose records all cancelled (objects made and removed inside it) is empty and is still pushed
    on the undo stack.
- **Hub causes.** `Session.execute` counted `tx += 1` whatever happened, never closed the active
  transaction, and committed empty steps. The live "drawing_exploded" step that undid nothing (wsdoc 22)
  is one of the two: a stale name picked up by a later change (two refused drawing_exploded calls and a
  library_pack lay between), or a made-and-removed step. I cannot tell which from the answers.
- **Fix** (`agentlink/changes.py` `finish`, called by `Session.execute`):
  - no step pending and the undo stack unchanged → no step counted;
  - after every call, refused ones too, `FreeCAD.closeActiveTransaction()` takes the name back;
  - a step pending whose whole call — seen by FreeCAD's document observers, App and Gui, connected only
    while a call runs — made only objects it removed again, in any document: aborted instead of
    committed (an abort of an empty step rolls back nothing). Never when the observers were not all
    connected, the event log filled, nothing at all was seen, or the session changed document.
  - `session.last_step = { tool, made, why }` says what happened; `session.tx` counts steps made.
- **Not covered.** A step that holds real records that net to nothing (a property set and set back)
  stays a step: telling that needs the old values. A dynamic property renamed has no observer slot;
  it would only matter in a call that otherwise made and removed objects and nothing else.
  At the undo limit with every name alike, a step a tool committed itself inside its call is not counted.
- **Tests.** `test_hubfix2.py` `WhatACallLeft` (4), `TheUndoStep` (7), `TheSession.test_a_call_that_changed_nothing…`.
  `test_hubfix2_fc.py` tests 1–3 (unrun).
- **Live.** `part_primitive` a box; `drawing_exploded` outside an Assembly; `history_undo` → steps
  `["part_primitive"]`, the box gone. Also: a refused changing call, then any read, then
  `history_undo` → never a step named after the refused call. If the drawing_exploded step is still there,
  it holds real records: tell me what `history_undo` answers and I will look at what the tool sets.

## 3. A changing call with no `health` — fixed

- **Cause.** `health.check` returns None when it has no line, nothing unchecked and no *new* next hint
  (`if not lines and not unchecked and not nxt: return None`), and `attach` then added nothing. A
  drawing page is neither sketch nor part, so drawing_make had only the hint to say: the first drawing
  carried a health because the hint was news, the section drawing did not because it was the same hint.
  Not a time budget.
- **Fix.** `attach` puts `{ ok: true, verdict: "nothing red" }` when there is nothing to say, and
  `{ ok: null, verdict: "the health check did not run (…)" }` when the check itself raised (it used to
  vanish). Still absent: a non-dict answer, an answer that brings its own health, a changing tool's
  read-only call, the check switched off (AGENTLINK_HEALTH=0).
- **Tests.** `Health.test_every_changing_call_carries_a_health`, `test_a_check_that_fails_says_so`.
- **Live.** wsdoc call 4 again: `health` present.

## 4. doc_close listed a document twice under `open` — fixed

- **Cause.** `open` was the labels; two open documents shared one (the manifest's warning). Not a
  duplicate entry.
- **Fix.** A label two open documents share is given as `Label (Name)` for each. Description says so.
- **Tests.** `TheSession.test_two_documents_of_one_label…`; `test_hubfix2_fc.py` test 8 (unrun).

## 5. Health showed a call's leftovers one call late — fixed for what happens inside the call

- **Cause.** `check` excused every still-touched object the call itself had made or recomputed. The
  excuse was right for one case and wrong for another, and only the order of events tells them apart
  (source: `Document::recompute` signals an object recomputed and then purges its mark;
  `Document::recomputeFeature` — one object's own `recompute()` — signals and leaves the mark):
  touched from *before* its last recompute is up to date; changed *after* it, or made and never
  recomputed, waits.
- **Fix.** The health mark watches changes and recomputes in order (`changes.after_recompute`); an
  object the call made or recomputed is named under `needRecompute` when it was made and never
  recomputed, or an input property changed after its last recompute (Output properties do not mark an
  object: `DocumentObject::onChanged`). Parts inside an assembly keep the old excuse. When the call was
  not seen whole, the old rule stands.
- **Not fixable here.** A mark set after the call returns (TechDraw finishing on its own thread) still
  shows at the next call.
- **Risk.** Tools that end by setting an input property after their recompute now say "1 object not
  recomputed yet" in their own answer instead of the next call's. That is the truth (the tree shows the
  mark), and `ok` stays true, but expect a few such lines live; each is a tool to give a final
  recompute, as status-findings a-12 did for material_set.
- **Tests.** `Health` (4 on this).  `test_hubfix2_fc.py` test 5 (unrun).
- **Live.** wsdoc call 4 (the section drawing) without Workshop's A12 fix: the template and dimensions
  named in call 4's own health. With A12: nothing named in 4 or 5.

## 7. Calls slow in a document of heavy shapes — two causes found by reading, fixed; timing added

Nothing was timed here. What the code and FreeCAD's source say:

- **Outside the tool's ms: the view fit.** After every changing call the echo fits the view
  (`echo.after` → `fit()` → `fitAll()`). With FreeCAD's view animation on (the default), `viewAll()`
  runs `animatedViewAll(10, 20)`: ten nested event loops of 20 ms, each redrawing the whole scene
  (source: `src/Gui/View3DInventorViewer.cpp`). It scales with how long one redraw takes, which is what
  a document of heavy shapes changes and a small mesh document does not. The echo wraps `server.call`,
  so none of it is in the call's ms. **Fix:** inside a batch the fit runs with the view's animation
  switched off for the fit and put back (`setAnimationEnabled`), except on the batch's last shown
  call; a call on its own fits as before. Same framing, no check involved.
- **Inside the ms, every call: each part's volume, before the call.** `health.mark` worked out a key
  for every part (`_part_hashes` → `_key`: counts, box and, up to 500 faces, `Shape.Volume`) so that the
  check afterwards can tell a recomputed-but-unchanged part. That is every body's volume on every
  changing call, whatever the call did. **Fix:** the key is kept per object while its shape is the very
  same one (`geometry.shape_key`, as `Session.stats_of` already does for the step snapshot), and read
  afresh after the call for every part the call recomputed. Same verdicts.
- **The 44 s health on a swept spring.** For a part of up to 200 faces the check runs
  `shape.check(True)` — BRepCheck plus BOP's self-intersection pass (`geometry.core_check`) — and then
  a boolean `common` against each part whose box it meets. The time budget (1.5 s) only decides what is
  *started*; one OCC call cannot be stopped. On a helical sweep the self-intersection pass is the
  likely 44 s, a `common` the other candidate; `isValid()` alone is unlikely. Which one is for the live
  run to say (`msBy`, below). **Fix:**
  - a shape whose free-form faces carry more than 300 control points (B-spline and Bézier faces by
    their poles, swept and revolved faces by their profile's; analytic faces count nothing) is not given
    the geometry check or an overlap boolean here;
  - a check that took 2 s or more on a shape is not run on that shape again (validity, the geometry
    check), until the shape changes;
  - a geometry check not started for lack of time used to be dropped in silence; it is now named.
  Each is listed in `unchecked` with `body_check { body: "…" } runs it in full (as a job: background:
  true)` or `clearance`, and the verdict ends "; N checks not run here (unchecked names them and the
  tool that does)". Where every check runs, the verdict's words are as they were. The box prefilter and
  "only pairs with what the call changed" were already there.
  **Limit, honestly:** the 300 is a guess that has never met a real shape. A short spring may pass
  under it and still be slow the first time (then it is remembered); a loft with dense sections will
  be left to body_check though it would have been quick.
  Not done: running the check as a job. Jobs run on a worker thread beside the GUI thread, and a
  changing call's next call may change the same shape under it; it would need the job queue's document
  lock and an answer that arrives after the call's. Recommended as its own piece of work if the
  unchecked lines turn out to be common.
- **Timing, so the rest can be seen.** In a batch a call's row carries `around` when 500 ms or more ran
  round the tool: `{ wall, outside { ms, echoBefore, echoAfter, fit, callDone, notice, meter, record,
  other }, inside { healthMark, health, snapshot, undoStep, afterChange, outputs }, tool }` (ms).
  `afterChange` is the add-ons' after_change handlers (SafetyNet's auto-save is there), `callDone`
  their call_done handlers, `snapshot` the step kept for history_diff. A health of 500 ms or more
  carries `msBy { state, sketches, shapes, overlap, families, window }`.
- **Looked at, not changed:** the batch's record already writes every fifth call once a write was slow;
  the panel's one-second refresh runs during the echo's paints and is not timed apart (it would show under `outside.echoBefore` or `echoAfter`);
  `health.mark` still reads every sketch's open-wire count (up to 300 sketches); the auto-save after
  every call is the add-on's.
- **Tests.** `LongChecks` (7), `Around` (4), `Fit` (4).
- **Time live** (the whiffle-ball document, the same batch):
  1. calls per 55 s before and after; expect the ~6 s outside to fall to well under 1 s from the first
     call (no animated fit), the last call still animated;
  2. read `around` on any row that has one: `fit` should be small; if `outside.other`, `callDone` or
     `echoBefore` is large, that is the next thing (send me the row);
  3. `inside.healthMark` should be near nothing from the second call on; `inside.health` with `msBy`
     says whether `shapes` or `overlap` is the cost; `afterChange` is the auto-save;
  4. `part_sweep` of the helical spring: health in about a second, `unchecked` naming the geometry
     check and the overlaps, verdict ending "… checks not run here"; then `body_check { body: "Spring",
     background: true }` for the full reading;
  5. a plain box in the same document: verdict "…: valid, closed, 1 solid" exactly as before.

## 8. A guarded change was refused for objects already failing — fixed

- **Cause.** `sheet.py`'s `check` (and the same guard in `param.py`, `sketch_more.py`,
  `pd_common.settle`) refuses and rolls back when `pd_common.broken(doc)` names anything — every failing
  object in the document, old ones too.
- **Fix.** `health.failing_before(doc)`: the objects already failing when the call in hand began (the
  open health mark's own list, the verdict's "still failing from before"). `pd_common.newly_broken(doc)`
  leaves them out; the four guards use it. With no call marked (the check off, over 4000 objects) the
  guards count everything, as before.
- **Left.** `data/tools.json` line 8874 (sketch_edit's `bad = broken(doc())`) has the same fault and is
  not mine to edit: replace with `newly_broken(doc())` (add the name to the data runner's helpers beside
  `broken`). The three data tools near 7867–7970 already compare with a `broken0` of their own.
- **Tests.** `TheSession.test_a_guard_does_not_count…`, `Health.test_failing_before…`;
  `test_hubfix2_fc.py` test 6 (unrun).
- **Live.** In the document with Left and Dimension002 failing: `sheet_new`, `sheet_set { cells: { A1: 12 } }`
  → ok, health "2 objects still failing from before this call: …". A cell that breaks a third object is
  still refused, naming only that one.

## 9. The batch's compact lines repeated a standing verdict — fixed

- `batchrec.to_reply`: the part "N object(s) still failing from before this call: …" of a line's health
  is given where it first shows and where it changes; a line that repeats it keeps the rest of its
  verdict, or reads "as before" when there was nothing else. `healthNote` says so when anything was left
  out. The file has every verdict whole. batch's description says it.
- **Tests.** `CompactLines` (3).

---

## Undecided, with a recommendation

1. **`session.tx`, `steps`, `calls` and `checks` cross documents on doc_new / doc_open / doc_close** (only
   doc_switch and doc_revert start them afresh). `tx` is "undo steps made in this document", so after
   doc_new it is wrong for the new document; a checkpoint's "can undo reach it" then falls back to the
   saved copy (safe, slower). `calls` deliberately spans documents (a saved macro replays doc_new), and
   batch's rollback filters `calls` by `tx`, so parking `tx` per document alone would break that.
   Recommend: keep `tx` per document in the same book as the family state, and stamp each `calls` entry
   with its document. A piece of work of its own; not done.
2. **run2 C6, helper `session_state` answering null in the file.** Not the hub: the call carried `to`,
   so its row is `{ written }` and the compare script reads `result`. Nothing to fix here.
3. **run2 C6, `health.next` reading "workbench TechDrawWorkbench" after kicad_import, and "likely next:
   td_view…" after part_primitive.** The hint reads the window as it is: the earlier run left a drawing
   page in front, and the rule "a page in front" outweighs body progress. It is true and stale-feeling.
   Recommend lowering that rule's weight when the call in hand is not a drawing tool (data:
   `nexthint.json`), decided with a look at the live window.
4. **status H1 and H2** (a sketch's line repeating; a tool bit's sketch): both are already in
   `health.py` at b408a91 (`_sketch_sigs`, `tool_bit_sketch`). Nothing left.
5. **status c-4, `doc_open { recent }` without the file doc_save wrote.** FreeCAD adds to the recent
   list from the GUI's file commands, not from `saveAs`; I did not find a call a script can make in the
   source I read. Recommend leaving it and saying in doc_open's description that the list is the
   window's.
6. **run2 C1, the cost of every changing ScanRuler call once the scan is dense.** The hub's share is
   now visible (`around.inside`); the packing is ScanRuler's.
7. **The free-form limit (300)** and **the slow memory (2 s)** in health: guesses, see 7.
8. **A health line for the dropped step.** An answer does not say "no undo step was made". It would be
   one more key on every files-only call; `session.last_step` has it for add-ons. Recommend leaving it
   out unless an agent is seen to undo the wrong thing.
