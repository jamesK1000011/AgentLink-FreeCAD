<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Plugging an add-on into Agent Link (API 1)

Agent Link for FreeCAD lets an AI agent drive FreeCAD. Your FreeCAD add-on
can offer its own tools to the agent without Agent Link knowing it exists,
and without your add-on depending on Agent Link: if Agent Link is not
installed, nothing below is ever loaded.

## The one file: `agentlink_families.py`

Put a module named `agentlink_families.py` inside your package (a folder
with `__init__.py` on FreeCAD's path, which every `Mod` folder is). Agent
Link looks for it on the path at start and imports it; nothing else of
yours is imported by Agent Link.

```python
# mypkg/agentlink_families.py
AGENTLINK_API = ">=1,<2"     # which Agent Link API you need
CREDIT = None                # or "Based on X by Y" — shown with your tools
LICENSE = "LGPL-2.1-or-later"

from . import fam_mine
FAMILIES = [fam_mine]
```

Each family module has:

```python
GROUP = "mine"                       # its tool group's name
INFO = "One line on what the group holds."
LEAN = False                         # True: listed by default (keep it small)
# For tools built in code only (tools as data carry these per tool):
HEAVY = {"mine_solve"}               # optional: queued, timed, given a deadline
WRITERS = {"mine_export"}            # optional: their "path" is written, not read
GEOMETRIC = set()                    # optional: their "path" is a curve, not a file
NOT_IN_MACROS = set()                # optional: changing calls a saved macro does not replay
PINNED_FREE = set()                  # optional: answered after the person closed the document the agent worked in (a recovery tool)
NEXT = {"mine-after-pad": {"when": {"body": "features", "lastFeature": "pad"}, "suggest": [{"tool": "mine_check", "why": "check the new solid"}], "weight": 49, "source": "mine", "date": "2026-11-16"}}  # optional: rules for the "next" hint (agentlink/data/nexthint.json says the facts and the shape)
# Optional, for the live echo in the FreeCAD window (any family, data or code):
SHOWN = ("mine_check",)              # read-only tools (names or prefixes) still shown as they run
AREAS = {"mine": "Mine"}             # prefix → the area name in a call's fallback words ("Mine do on Lid")
PHRASES = {"mine_do": ["Did it to {body}", "Did it"]}  # tool or prefix → what a call did, in the Activity tab's words
WORKBENCHES = {"mine_": "MineWorkbench"}  # tool or prefix → the workbench brought up for them (longest match wins)
COMMANDS = {"mine_do": "Mine_Do"}    # tool or prefix → the command whose button (and menu item) lights for them
NO_BUTTON = {"mine_do_quiet"}        # tools or prefixes that light no button, even where a COMMANDS prefix matches
NO_ECHO = ("mine_point",)            # tools or prefixes never shown as they run (no bench, button, caption, selection; still in Activity)
CAPTIONS = {"mine_share": ["Shared {document} with {to}", "Shared the work"]}  # tool or prefix → the caption over the 3D view (see below)
PAGES = ("mine_page_",)              # prefixes of tools working on a drawing page (opened, view not reframed)
# def command_for(name, args): ...   # optional: the command for a call by its arguments, or None

def tools(session):
    from agentlink.protocol import Tool, ToolError
    def do_it(a):
        ...
        return {"made": ...}          # plain values, millimetres and grams
    return [Tool("mine_do", "What it does, when to use it.", schema, do_it, changes=True)]
```

- **The live echo.** When the agent runs one of your tools, the bench from `WORKBENCHES` comes up (use your own workbench where the tool has a button there; a drawing-page tool goes to `TechDrawWorkbench`; safety and settings tools declare none) and the button from `COMMANDS` lights, unless the tool is in `NO_BUTTON` (an exact name or a prefix), which always wins. A bench not loaded in this window is left alone and logged once, never an error. Neither is needed for a tool to work.
- **Your captions.** `CAPTIONS` gives the words the window shows over the 3D
  view and in the status bar for your tools: a template, a list of
  templates (the same rules as `PHRASES`: `{fields}` from the call's
  arguments or its answer, the first that fits wins), or a callable
  `fn(name, args, body) -> words or None` (`body` is `None` while the call
  runs). The key is a tool's name or a prefix; the longest match wins. The
  words are said when the call starts (arguments only), and again when it
  ends, after any tools it ran inside it, so the last inner step's words
  never stand for your call; a tool in `NO_ECHO` still gets its caption at
  the end. When nothing fits, Agent Link says neutral words ("Working on
  it", "Done", "That step: refused (…)"), never the tool's name. The
  Activity row keeps `PHRASES`. Agent Link has no words of its own for an
  add-on's tools: declare them here.
- **Keep your core free of Agent Link.** Put the work in your own API (plain
  functions on FreeCAD) and keep the family a thin layer over it. Raise
  `ToolError(code, message)` with a message that says what to do instead.
- **Version mismatch.** If this Agent Link does not meet `AGENTLINK_API`, your
  add-on is left out with the reason in the log, never a crash.
- **Names.** A tool can't take a name Agent Link already has; yours is left
  out instead.

## Tools as data (the usual way)

Keep your tools in `yourpkg/data/tools.json` and bind handlers by name. The
format is Agent Link's (`agentlink/tooldata.py`, `agentlink/data/tools.schema.json`):

```json
{"dataVersion": "1.0.0", "licence": "CC-BY-4.0", "about": "My add-on's tools.",
 "entries": {"mine_do": {"group": "mine", "description": "What it does, when to use it.",
   "inputSchema": {"type": "object", "properties": {"body": {"type": "string"}}, "required": []},
   "changes": true, "source": "written for mine", "date": "2026-11-14",
   "heavy": false, "writes": false, "pathIsCurve": false,
   "activity": "Did it to {body}"}}}
```

`activity` is optional: what a call did, in the panel's Activity tab — a
short plain sentence whose `{fields}` come from the call's arguments or its
answer (a path shows as its file name). Without it the tab says the tool's
friendly name and main argument. Templates in a list (PHRASES) are tried in
order, the first whose fields are all given wins; `" if {field}"` or
`" if {field=value}"` at the end makes one conditional.

```python
# yourpkg/fam_mine.py — the only module besides agentlink_families that sees Agent Link
from agentlink import hooks
from . import api, DATA

GROUP = "mine"
INFO = "One line on what the group holds."

def tools(session):
    return hooks.tools_from_data(DATA, GROUP, {"mine_do": lambda a: api.do_it(session, a)}, "My add-on")
```

- Every tool in the group needs a handler and every handler a tool, or the
  family is left out with the reason in the log.
- A handler refuses by raising any exception with `code` (`invalid_input`,
  `not_found`, `invalid_state`, `unavailable`, `failed`) and `message`; your
  API defines its own such exception and never imports Agent Link.
- README tool tables are generated from the same file.

### Agent Link's own fields (add-ons don't need them)

Agent Link keeps its own one-command wrappers in `agentlink/data/tools.json`
with five more fields, run by `agentlink/runners.py` instead of a handler:
`runner` (`make`, `apply`, `command` or `read`), `target` (the maker or
TypeId, method, command, or what to read), `args` (each argument's default,
conversion, family helper, property, or step once the object is made),
`rules` (the checks, each with its refusal message word for word) and
`answer` (its fields and the family helper that finishes it). They are
accepted in an add-on's file only as part of a valid runner entry, and an
add-on's tools are still bound to its handlers; leave them out.

## Hooks (`agentlink.hooks`)

All optional. Every hook catches and logs your exceptions.

| Hook | Use |
|---|---|
| `register_reader(kind, fn)` | Answer a question by kind (`"wall"`: the thinnest wall of a shape; `"thread_scan"`: a thread read from a scan). Return `None` to pass; the first answer wins. |
| `provide(name, obj)` / `service(name)` | Offer or use a named service (`process_of`, `checkpoints`, `reopen`, `material_cards`, `frame_solver`, `encased`). Absent gives `None`. |
| `on(event, fn)` | `after_change(session, tool)`, `setting_changing(tool, path)`, `setting_changed(path, name, old, new, tool=, restart=, applies=)`, `reply_written(session)`, `docs_changed(session)`, `call_done(session, tool, ok, changed)`. |
| `extend_tool(name, properties, before, after, describe)` | Add arguments to a tool another family owns. `before(args, session)` may return changed arguments; `after(args, answer, session)` may return a fuller answer; `describe` is a sentence added to the tool's description. The owner never sees your arguments. |
| `register_tab(title, factory, order, workbench=None, own_credit=False)` | A tab in Agent Link's panel: `factory(panel)` returns a QWidget; its `fill()`, if it has one, runs each time the tab comes up. Agent Link's own tabs sit at Notes 10, Steps 20, Review 50 and Activity 95, and keep 15 (between Notes and Steps) free for an add-on; an add-on's `order` places its tab between them (at the same order Agent Link's comes first, and a core tab's title is not taken). `panel._call(tool, args)` runs a tool as the person's click, answering `(ok, result)`. With `workbench` (a workbench name as `FreeCADGui.activeWorkbench().name()` gives it, or several) the tab shows only while that workbench is active; Notes, Steps and Activity show everywhere. With `own_credit=True` (or a widget whose `own_credit` is true) the page carries its own credit line for the work it builds on, and Agent Link's line is hidden while it is in front; a page that declares nothing but shows a label crediting that work is read the same way. Agent Link names no add-on's tab. |
| `tab_in(title, *workbenches)` | Show a tab (an add-on's, or Agent Link's Review) in more workbenches. |
| `service("panel_layout")` | Agent Link's placer (`agentlink/layout.py`): `show(key, dock, workbench)`, `hide(key)`, `toggle()`, `reveal(key)`. An add-on's own panel placed through it shares one place with the others by the `Mod/AgentLink` `PanelLayout` setting (`right`, `left-tab`, `left-slide`). |
| `register_rider(owner, fn)` / `unregister_rider(owner)` | A short line that joins every answer while your add-on has something in hand (`lesson: step 3/7 passed`); see [The rider line](#the-rider-line). |
| `agent_acting()` | True while one of the agent's own calls runs (any call through the server whose `session.by` is `"agent"`), False during a panel click and between calls. An add-on's observers use it to keep the person's events apart from the agent's. False too while a `gui_input` call with `as: "person"` runs its steps (`person_input()`, dev only: a student agent standing in for the person); an agent's call taken inside it is the agent's again. |
| `register_thread_tool(name)` | The window link answers this tool on a thread of its own, never through the GUI thread's queue and never holding the call in hand: for a long poll (wait up to 25 s for the person's events). The handler must read only what the add-on keeps behind its own lock and touch no FreeCAD or Qt object; the call gets no undo step, echo, `call_done`, notice, rider or meter (`Server.handle_light`). |
| `watch_window(owner)` / `unwatch_window(owner)` | While any owner watches, `workbench_activated(name, by)` and `command_used(name, by)` are emitted (`agentlink/gui_events.py`): the main window's `workbenchActivated` and every command's `QAction.triggered` (toolbar, menu, shortcut; actions of a workbench switched to later joined then), `by` `"agent"` or `"person"`. Only Agent Link's own slots are connected and taken off again; nothing is changed. False without a window. |
| `register_reviewer(fn)` | `fn(session, body)` gives the Review tab its verdict (`{"verdict": "pass"/"warn"/"fail", "findings": [...], "figures": {...}, "process": ...}`), or `None` to pass. Reviewers are asked in the order they registered; the first answer that is not `None` is shown. With none, the tab says so and offers the core `body_check`. |
| `guard_setting(path, name)` | A setting `pref_set` must not change (`path` as `pref_set` takes it, e.g. `"Mod/MyAddon"`): one that widens what the agent may do or which code FreeCAD loads. |
| `remember(session, kind, value)` / `analysis(session, kind)` | Last results by kind, for example the last FEA solve. |
| `session.family_state` / `own_document_state(key)` | Your family's own state, under your group's name: `session.family_state.setdefault("mine", {})`. It is one dict per document; see [State per document](#state-per-document). |
| `agentlink.tools.register_guides(folder)` | Markdown guides the agent can read with `guide_read`. A `guides/` folder beside your `agentlink_families.py` is registered for you; if there is also a `freecad_guides/`, only that one is (for add-ons whose `guides/` serve their own server). |
| `agentlink.render.register_layer` / `register_map` | Layers and colour maps for `view_render`. |

### Services Agent Link offers

Provided once the FreeCAD window is up (`hooks.service(name)`; `None` in
FreeCADCmd). Nothing here moves the cursor, sends input, takes focus, opens a
menu, raises the window or goes full screen.

| Service | Methods | Notes |
|---|---|---|
| `overlay` (`agentlink/overlay.py`) | `show(specs, say=None, ms=None, owner="")` → `{handle, shown: [i], hidden: [(i, why)]}`; `flash(widget, ms=1300)`; `menu(titles, badge=None, owner="", handle=None)` → `{handle}`, `{native: True}` or `{missing: title}`; `watch_menu(menu, action, owner="", handle=None, badge=None)` rings action inside menu whenever the person opens it (a toolbar button's dropdown); `clear(owner=None, handle=None)`; `visible(widget)` → `None` or why (`hidden`, `covered`: only when the window's widget under its middle is another, so the overlay and its callout never count; `in another window`); `colours()` | One transparent, mouse-transparent child of the main window draws a 3 px ring in the theme's accent (`ThemeAccentColor1`, else the palette's highlight; a colour-blind-safe stand-in under 3:1 contrast) with a 2 px halo, black on a light window and white on a dark one (the theme's name decides, since FreeCAD's light themes are stylesheets over a palette that may stay dark), a numbered badge, and one callout (wrapped at 320 px, the app font and at least 13 px, inside the window, on the target's free side, never over the 3D view, whose GL surface paints over the overlay: it goes to the docks or toolbar area beside it, down to 180 px wide with more lines, and keeps off tab bars and the menubar where it can). A spec is `{widget, rect?, viewport?, badge?}`: `rect` a callable giving `(x, y, w, h)` in `viewport` (default the widget) coordinates, such as a tree row's `visualItemRect`. Rects follow their widgets (Move, Resize, Show, Hide, and a 250 ms timer); a hidden target stays listed and is drawn when it shows. A menu is ringed at its menubar title, then inside each menu the person opens on the way; the native macOS menubar cannot be drawn over (`native`). The echo's lit buttons are drawn here (`flash`): no widget's stylesheet is changed. |
| `annotations` (`agentlink/annotate.py`) | `light(obj, ["Face6", "Edge3", "Vertex1"], owner="", colour="#rrggbb", badge=None)` → `{lit, missing: [(sub, why)]}`; `badge` draws that number on the first lit element, a disc and a bold number sized for the screen's pixel ratio, at the point of it nearest its centre that the view shows with room around it (not under another part; without a view, the nearest point on it); `clear(owner=None)` | Coin nodes under an `SoAnnotation` in the 3D view's scene graph, where the panel's note pins and Steps stage draw: a face tinted, an edge thick, a vertex marked, at the shape's place in the scene. Never in the document, never FreeCAD's selection. |
| `panel_layout`, `panel_caller` | see above | |

`agentlink.targets` finds the window's controls for the echo and for
add-ons: `command_for(tool, args)` (the command whose button does what a call
does), `actions(cmd)` (QActions by `objectName`, as the echo finds them),
`buttons(cmd)`, `group_buttons(cmd)` (`[(button, menu, action)]`: toolbar
buttons whose dropdown holds the command, a group command such as FreeCAD
1.1's Sketcher rectangles or Part Design's primitives, where the button
shows the group's action and `buttons` finds nothing; `command_name(action)`
reads an action's command, its `objectName` or FreeCAD's `CommandName`
property; `in_menu(menu, cmd)`), `menus_of(cmd)`, `associated(action)`, `menu_path(titles)`
(`{bar, chain: [(menu, action)], path, missing}`; titles compared without
`&` or a trailing `…`, case ignored), `native_menubar()` and
`workbench_of(cmd)` (from the command's prefix).

### Services Agent Link asks for

| Service | Methods | Used by | Without it |
|---|---|---|---|
| `checkpoints` | `take(session, name=None, auto=False, doc=None)` → `(entry, dropped)`; `find(session, ref)` → entry or `None`; `index(doc_name)` → entries; `restore(session, ref)` → answer | `history_diff { since: "cp3" }`, a copy before a heavy job and before `app_restart` saves | `history_diff` by checkpoint is refused `unavailable`; no copies are taken |
| `reopen` | `keep([doc])` → `[{ name, label, file, copy, t }]` | `app_restart`, for changed documents it does not save | `app_restart` reopens saved files only, and refuses while a changed document would be lost |
| `notice` | `fn()` → a short line or `None` | Every tool call's answer: a line is added once as `"notice"`, on that answer only (refusals too) | Answers are unchanged |

`notice` tells the agent of something the person did that it would not
otherwise know, such as a screenshot taken in the window. Return a line only
once for each new thing, and `None` the rest of the time. The provider is
given 0.2 s: a slower one never holds an answer up, and a line it gives late
rides on the next answer. A provider that raises is logged and skipped.

### The rider line

`notice` is one service with one provider and a line given once. The rider
line is for any number of add-ons that follow a job alongside the agent: each
registers `register_rider(owner, fn)`, and after every call `fn(tool)` is
asked (with the tool's name) for a short line, or `None` when the add-on has
nothing in hand. The lines of every active provider join the answer as
`"rider"`, separated by ` · `; each is cut to 80 characters and the whole to
200. Providers are asked on the thread that answers, after `call_done`, so
keep them to reading what you hold in memory. Registering again under the
same owner replaces the provider; one that raises is logged and skipped.
Give a line only while it says something new if every answer would
otherwise carry it.

### The test flag `AGENTLINK_AS_USER`

For tests only, off by default. With `AGENTLINK_AS_USER=1` in the
environment of the FreeCAD that serves, every call the agent makes runs as
the person's (`session.by` is `"person"` while it runs, as for a panel
click, and `call_done` sees it so), and Agent Link logs once that the flag
is on. An add-on that tells the person's actions from the agent's (a lesson
the person works through) can then be tested end to end by an agent. Never
set it for real use: the add-on can no longer tell who did what.

An entry is `{ id, name, file, step, tx, session, … }`: `file` a saved copy
Agent Link can open, `session` the `id()` of the session that took it and
`step`/`tx` that session's step and undo count then.

### State per document

`session.family_state` is a dict of each family's own state under its
group's name, and it belongs to the document the session is in. However the
session comes to another document (`doc_new`, `doc_open`, `doc_close`,
`doc_switch`, `doc_revert`, the person closing the agent's document), the
dict of the document it leaves is set aside with that document for as long
as it stays open, and the document it arrives in gets its own dict back, or
an empty one. So a new document never sees another document's state, and
going back to a document finds its state as it was left. A document is told
by identity, not by name: one closed and opened again (or reverted) starts
empty, and your family reads what it keeps in the document itself, as after
a restart. Nothing is written into a document for you.

Two events say when, on the thread that moved the session and before any
state is handed out for the new document:

| Event | When |
|---|---|
| `document_state_leaving(session, doc, state)` | The session has moved away from `doc`, which is still open; `state` is `doc`'s dict, about to be set aside. Write into `doc` now what must not be lost with the session (`session.doc` is already the new document: write to `doc`). Not told for an empty dict or a closed document. |
| `document_state_entered(session, doc, state, restored)` | `state` is the session's dict for `doc` from now on; `restored` is True when it is the one set aside earlier, False when it starts empty. |

An add-on that settles its own state per document (it keeps its own book of
which document its state belongs to, and writes, sets aside and restores it
itself) calls `own_document_state("mine")` once from its
`agentlink_families` module. Its key is then carried along with the session
untouched, so on arriving in another document it still finds the state of
the document it left, to settle as it does. The same holds, with no call,
for a key whose book is kept on the session under the attribute
`_<key>_documents`. `session.family_state = d` puts `d` in place as the
state of the document the session is in (an add-on that reopened a document
from a copy puts back the state it kept).

The session's own record of a document goes the same way and by the same
book: `session.steps` (what `history_diff` compares), `session.meta`,
`session.tx` (undo steps made in this document), `session.calls` (its
changing calls, for a macro) and `session.checks` are the document's. A new
or opened document starts at nothing (its `calls` begin with the `doc_new` or
`doc_open` that made it), and one the session comes back to while it stayed
open finds its own again; `session.switch(doc)` no longer empties them. An
add-on that reopens a document from a copy and puts the record back
(`session.steps, session.meta, session.calls = kept` after `switch`) works as
before: the names are properties over the record of the document the session
is in. `agentlink.docstates.own_of(session, doc)` reaches the record of a
document the session left open.

### Reads that must run in place

A read (`"changes": false`) may be run on a worker thread as a job
(`background: true`, `job_start`, a heavy or slow read on its own). One that
changes nothing in the end but drives the document or the window on the way
— poses tried and put back, a solve, a recompute, the selection, a view, a
document made active, a setting written — must not: only FreeCAD's GUI
thread may do those, and such a read on a worker thread stopped FreeCAD's
window. Say so from your `agentlink_families` module:

```python
from agentlink import jobs
jobs.in_place("mygroup_fit_check", "moves the parts through each pose and puts them back")
```

The words are said in `background`'s refusal after the tool's name. Agent
Link's own are in `agentlink/jobs.py` (`IN_PLACE`), each with what it does.

### Events Agent Link emits

| Event | When |
|---|---|
| `after_change(session, tool)` | After every changing call. A call that changed nothing leaves no undo step (`session.last_step` is `{ tool, made, why }`; `session.tx` counts the steps made). |
| `setting_changing(tool, path)` | Before `pref_set`, `pref_reset`, `pref_pack` or `pref_import` changes anything: a snapshot taken now is the state before. |
| `setting_changed(path, name, old, new, tool=, restart=, applies=)` | After each value changed; `restart` when it shows only after FreeCAD restarts, `applies` `"at next launch"` headless. |
| `reply_written(session)` | After each reply of the stdio server (the hidden FreeCAD): say what it holds for whoever restarts it after a crash. |
| `workbench_activated(name, by)`, `command_used(name, by)` | While an add-on watches the window (`watch_window`): a workbench switched to, a command's action triggered; `by` is `"agent"` during the agent's own calls, else `"person"`. |
| `call_done(session, tool, ok, changed)` | After every call through the server (`Server.call`: the agent's, a panel click's, a batch's inner calls), refusals too, before the answer's notice and rider lines are asked. `ok` is False for a refusal; `changed` is True when the call went through and changed the document (its undo count moved, the session's document is another, or the tool changes it by its kind). `session.by` says whose call it was. Not told for a name that is no tool. |

### Tools from Python

`agentlink.run(tool, args)` calls a tool as a live call does (a saved macro's
lines); `with agentlink.serving(server):` sends those calls to the given
server while the block runs.

## Nothing shared to install

Each add-on installs and runs on its own: it carries its own copy of any
helper it needs (a document-records reader, shape helpers, a data-file
loader), and needs no other add-on and no shared library. The notes kept in
the FreeCAD document follow one written format (`docs/records.md`), so each
add-on reads and writes them on its own. Agent Link owns one format only:
the tool data above.

## Testing

Run your tests twice in CI: your add-on alone (no Agent Link on the path),
then with Agent Link beside it. A test should check in a fresh Python that
your API imports nothing named `agentlink`.
