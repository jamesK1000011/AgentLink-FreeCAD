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
# Optional, for the live echo in the FreeCAD window (any family, data or code):
SHOWN = ("mine_check",)              # read-only tools (names or prefixes) still shown as they run
AREAS = {"mine": "Mine"}             # prefix → the name the Activity list gives its calls
WORKBENCHES = {"mine_": "PartDesignWorkbench"}  # prefix → the workbench brought up for them
PAGES = ("mine_page_",)              # prefixes of tools working on a drawing page (opened, view not reframed)

def tools(session):
    from agentlink.protocol import Tool, ToolError
    def do_it(a):
        ...
        return {"made": ...}          # plain values, millimetres and grams
    return [Tool("mine_do", "What it does, when to use it.", schema, do_it, changes=True)]
```

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
   "heavy": false, "writes": false, "pathIsCurve": false}}}
```

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
| `provide(name, obj)` / `service(name)` | Offer or use a named service (`process_of`, `checkpoints`, `material_cards`, `frame_solver`, `encased`). Absent gives `None`. |
| `on(event, fn)` | `after_change(session, tool)`, `setting_changed(path, name, old, new)`, `docs_changed(session)`, `call_done(session, tool, ok)`. |
| `extend_tool(name, properties, before, after, describe)` | Add arguments to a tool another family owns. `before(args, session)` may return changed arguments; `after(args, answer, session)` may return a fuller answer; `describe` is a sentence added to the tool's description. The owner never sees your arguments. |
| `register_tab(title, factory, order)` | A tab in Agent Link's panel: `factory(panel)` returns a QWidget. |
| `register_reviewer(fn)` | `fn(session, body)` gives the Review tab its verdict. |
| `guard_setting(path, name)` | A setting `pref_set` must not change (`path` as `pref_set` takes it, e.g. `"Mod/MyAddon"`): one that widens what the agent may do or which code FreeCAD loads. |
| `remember(session, kind, value)` / `analysis(session, kind)` | Last results by kind, for example the last FEA solve. |
| `agentlink.tools.register_guides(folder)` | Markdown guides the agent can read with `guide_read`. A `guides/` folder beside your `agentlink_families.py` is registered for you; if there is also a `freecad_guides/`, only that one is (for add-ons whose `guides/` serve their own server). |
| `agentlink.render.register_layer` / `register_map` | Layers and colour maps for `view_render`. |

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
