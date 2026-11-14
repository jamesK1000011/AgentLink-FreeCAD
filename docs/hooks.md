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
| `guard_setting(path, name)` | A setting `pref_set` must not change. |
| `remember(session, kind, value)` / `analysis(session, kind)` | Last results by kind, for example the last FEA solve. |
| `agentlink.tools.register_guides(folder)` | Markdown guides the agent can read with `guide_read`. |
| `agentlink.render.register_layer` / `register_map` | Layers and colour maps for `view_render`. |

## Shared library

Records kept in the document, shape helpers, fits, versioned data files and
dialog pieces come from **AddonKit for FreeCAD** (`addonkit`), which Agent
Link uses too. Depend on it with a range:

```python
import addonkit
addonkit.require(">=1.0,<2", "My add-on")
```

and in `package.xml`: `<depend>AddonKit</depend>`.

## Testing

Run your tests twice in CI: your add-on alone (no Agent Link on the path),
then with Agent Link beside it. A test should check in a fresh Python that
your API imports nothing named `agentlink`.
