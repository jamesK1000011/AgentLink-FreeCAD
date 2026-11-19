<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# DRAFT: FreeCAD Addon Index submissions

Status: DRAFT. The owner submits. Checked against FreeCAD/Addons at
commit 467ab72 and the Addon Academy on 19 Nov 2026.

## How the Index takes an add-on

- Submit an issue, not a pull request:
  https://github.com/FreeCAD/Addons/issues/new/choose, type
  **Addon - Addition** (Codeberg mirror:
  https://codeberg.org/FreeCAD/Addons/issues/new/choose; or the forum,
  https://forum.freecad.org/viewforum.php?f=65).
- The form has two fields: **Repository** (required) and **Notes**.
- A FreeCAD team member checks the add-on against the Qualities
  (https://freecad.github.io/Addon-Academy/Topics/Addon-Index/Index/Qualities),
  asks for a new release or tag when it complies, and then adds it to
  `Data/Index.json`. It shows in the Addon Manager after about a day.

## Blocker: the 30-day rule

The Qualities say: "The addon's repository and overall codebase must be
at least 30 days old." The repositories were made on 14 and 15 Nov 2026.
Submit on or after these dates:

| Index ID | Repository | Made | Submit on or after |
|---|---|---|---|
| AgentLink | AgentLink-FreeCAD | 2026-11-14 | 2026-12-14 |
| Workshop | Workshop-FreeCAD | 2026-11-14 | 2026-12-14 |
| ScanRulerFC | ScanRuler-FreeCAD | 2026-11-14 | 2026-12-14 |
| Texturizer | Texturizer-FreeCAD | 2026-11-14 | 2026-12-14 |
| Tutor | Tutor-FreeCAD | 2026-11-15 | 2026-12-15 |

Agent Link for OrcaSlicer has no `package.xml` and is not a FreeCAD
add-on: no Index entry.

Submit Agent Link first. Tutor declares `<depend type="addon">Agent
Link</depend>`, and Workshop, ScanRuler for FreeCAD and Texturizer give
their agent tools through it.

## The issues (copy into the form)

### 1. Agent Link

Repository:

```
https://github.com/jamesK1000011/AgentLink-FreeCAD
```

Notes:

```
Agent Link connects an MCP client (an AI agent) to FreeCAD: headless, or live in the user's window, where the agent never moves the cursor. Workbench "Agent Link" (Start/Stop Link, a panel), two preference-pack themes (Studio Light, Studio Dark).
- Index ID proposed: AgentLink (the Mod folder that our Claude extension also installs into, so both installs are the same add-on).
- Branch: main. Release tag: agentlink-v1.0.0. package.xml: version 1.0.0, freecadmin 1.0.0.
- Python dependency: numpy (on the allow list).
- Licence: LGPL-2.1-or-later; data CC-BY-4.0 (LICENSES/).
- Network: none at import or start-up. Only on a user or agent request (FreeCAD and add-on updates from GitHub, the add-on catalog). Disclosed in docs/PRIVACY.md. No telemetry.
- The window link listens on 127.0.0.1 only.
- Code runs and file steps need the user's approval (approve_code, approve_file).
- Legacy Init.py/InitGui.py layout. We plan the freecad/<ModName>/ layout for a later version.
- Not affiliated with or endorsed by the FreeCAD project or the FPA.
```

### 2. Workshop

Repository: `https://github.com/jamesK1000011/Workshop-FreeCAD`

Notes:

```
Workshop adds making features to the workbenches where they belong (standard parts in Part and Part Design, holes and threads, TechDraw drawings, KiCad boards, SafetyNet checkpoints in Tools) and one small Make workbench.
- Index ID proposed: Workshop. Branch: main. Tag: v1.0.0. freecadmin 1.0.0.
- Python: numpy; scipy optional (both on the allow list).
- Licence: LGPL-2.1-or-later; data CC-BY-4.0.
- Agent tools through Agent Link when it is installed; works without it.
- Not affiliated with or endorsed by the FreeCAD project or the FPA.
```

Note for the owner: Workshop adds commands to Part, Part Design,
TechDraw and the File and Tools menus. The Qualities say: "Commands,
toolbars, menus, and other side effects stay within the addon's own
workbench." Expect the reviewer to ask about this. Be ready to explain it
or to move the commands into the Make workbench.

### 3. ScanRuler for FreeCAD

Repository: `https://github.com/jamesK1000011/ScanRuler-FreeCAD`

Notes:

```
A port of ScanRuler's scan measuring (fits, alignment, deviation, wall thickness, sections, mesh tools, reverse engineering) by Stefan Hermann (CNC Kitchen), as a ScanRuler workbench. An independent port, not made or endorsed by CNC Kitchen.
- Index ID proposed: ScanRulerFC. Branch: main. Tag: v1.0.0. freecadmin 1.0.0.
- Python: numpy; scipy optional.
- Licence: AGPL-3.0-only (as ScanRuler); fonts OFL-1.1. NOTICE.md credits the source.
- Not affiliated with or endorsed by the FreeCAD project or the FPA.
```

### 4. Texturizer

Repository: `https://github.com/jamesK1000011/Texturizer-FreeCAD`

Notes:

```
Surface textures for printed parts: BumpMesh's texturing engine by Stefan Hermann (CNC Kitchen), ported to Python, with its settings sidebar, Texture Gallery and live preview, in a Texturizer workbench.
- Index ID proposed: Texturizer. Branch: main. Tag: v1.0.0. freecadmin 1.0.0.
- Python: numpy.
- Licence: AGPL-3.0-only (as BumpMesh); textures CC-BY-4.0 and CC0-1.0. NOTICE.md credits the source.
- Not affiliated with or endorsed by the FreeCAD project, the FPA or CNC Kitchen.
```

### 5. Tutor

Repository: `https://github.com/jamesK1000011/Tutor-FreeCAD`

Notes:

```
An agent teaches FreeCAD in the user's own window: it explains and points at a control, does a job step by step, or guides the user and checks each step. Lessons are data files.
- Index ID proposed: Tutor. Branch: main. Tag: v1.0.0. freecadmin 1.1.0 (content type "other").
- Depends on the add-on "Agent Link" (<depend type="addon">Agent Link</depend>): please list Agent Link first.
- Licence: LGPL-2.1-or-later (LICENSE-Code); assets CC-BY-3.0 (LICENSE-Assets).
- Not affiliated with or endorsed by the FreeCAD project or the FPA.
```

## The Index.json entries (for reference only)

A maintainer writes these. The keys are the ones the current
`Data/Index.json` uses (`curated` is set by the maintainers):

```json
"AgentLink": [
  {
    "repository": "https://github.com/jamesK1000011/AgentLink-FreeCAD",
    "git_ref": "main",
    "branch_display_name": "main",
    "freecad_min": "1.0.0",
    "zip_url": "https://github.com/jamesK1000011/AgentLink-FreeCAD/archive/refs/heads/main.zip"
  }
],
"Workshop": [
  {
    "repository": "https://github.com/jamesK1000011/Workshop-FreeCAD",
    "git_ref": "main",
    "branch_display_name": "main",
    "freecad_min": "1.0.0",
    "zip_url": "https://github.com/jamesK1000011/Workshop-FreeCAD/archive/refs/heads/main.zip"
  }
],
"ScanRulerFC": [
  {
    "repository": "https://github.com/jamesK1000011/ScanRuler-FreeCAD",
    "git_ref": "main",
    "branch_display_name": "main",
    "freecad_min": "1.0.0",
    "zip_url": "https://github.com/jamesK1000011/ScanRuler-FreeCAD/archive/refs/heads/main.zip"
  }
],
"Texturizer": [
  {
    "repository": "https://github.com/jamesK1000011/Texturizer-FreeCAD",
    "git_ref": "main",
    "branch_display_name": "main",
    "freecad_min": "1.0.0",
    "zip_url": "https://github.com/jamesK1000011/Texturizer-FreeCAD/archive/refs/heads/main.zip"
  }
],
"Tutor": [
  {
    "repository": "https://github.com/jamesK1000011/Tutor-FreeCAD",
    "git_ref": "main",
    "branch_display_name": "main",
    "freecad_min": "1.1.0",
    "zip_url": "https://github.com/jamesK1000011/Tutor-FreeCAD/archive/refs/heads/main.zip"
  }
]
```

None of these IDs is in the Index now (checked 19 Nov 2026).

## What the Qualities ask, and where we stand

| Quality | State |
|---|---|
| Repository at least 30 days old | **No** until the dates above |
| Valid `package.xml` (name, version, date, description, maintainer, licence, icon, content, repository URL with `branch`) | Yes, all five |
| `<classname>` matches the `InitGui` class | Yes (Tutor is `other`, no workbench) |
| Licence matches everywhere, exact SPDX IDs | Yes (REUSE.toml in each repository) |
| Python dependencies on the allow list | Yes: numpy, scipy (optional) |
| No network, no heavy work at import or start-up | Likely: no network call in `Init.py` / `InitGui.py`; the modules they import were not audited for this |
| GDPR: disclosure of every external connection | Yes: README "Privacy" and docs/PRIVACY.md (hub) |
| Security reports accepted and handled | Partly: turn on GitHub private vulnerability reporting (now off) |
| Not pre-alpha or alpha | Hub `pyproject.toml` said "3 - Alpha"; now "4 - Beta" |
| Documentation says which features work | Yes: the README's release statistics |
| Bandit scan (reports are public) | Not run yet: run `uvx bandit -r . -x tests` and fix what is real |
| `freecad/<ModName>/` layout, no `sys.path` changes | No: legacy `Init.py` layout ("strongly discouraged", allowed). Some modules change `sys.path` (`agentlink/porting.py`, `agentlink/smoke.py`, `agentlink/setup_check.py`); check that none runs inside FreeCAD's process, or remove it |
| Side effects stay in the add-on's own workbench | Check: Workshop adds commands to core workbenches and menus |
| Release branch apart from the work branch (best practice) | No: the Index would track `main` |
