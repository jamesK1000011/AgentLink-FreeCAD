<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
<!-- mcp-name: io.github.jamesK1000011/agentlink-freecad -->
# Agent Link for FreeCAD

> Not affiliated with or endorsed by the FreeCAD project or the FreeCAD project association (FPA); FreeCAD is the FPA's trademark. Get FreeCAD itself from [freecad.org](https://freecad.org).

Agent Link lets an AI agent (Claude, or any client that speaks the Model
Context Protocol) drive FreeCAD for you. You describe the part; the agent
makes it, checks it, draws it and exports it, and you can watch every step
in your own FreeCAD window. Every change is one FreeCAD undo step.

<!-- screenshot: FreeCAD on a Mac with the Agent Link panel open beside the model tree, a part being built -->

- [What you need](#what-you-need)
- [Install](#install)
- [Connect your agent](#connect-your-agent)
- [Where everything lives](#where-everything-lives)
- [What the agent can do](#what-the-agent-can-do)
- [Platforms](#platforms)
- [Token usage](#token-usage)
- [Privacy](#privacy)
- [Troubleshooting](#troubleshooting)
- [Uninstall](#uninstall)
- [Credits and licence](#credits-and-licence)

For an agent setting this up: follow [SETUP.md](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/SETUP.md).

## What you need

Check at any time with the setup check, which says what is missing and how to
get it (it changes nothing):

```
uvx --from git+https://github.com/jamesK1000011/AgentLink-FreeCAD agentlink-freecad --check
```

or, from a copy of this folder, `python3 agentlink_headless.py --check`. In
FreeCAD, **Agent Link > Setup Check** does the same for the Claude extension.

| | macOS | Linux | Windows |
|---|---|---|---|
| **FreeCAD 1.0 or later** (required; 1.1 recommended) | [freecad.org/downloads](https://www.freecad.org/downloads.php), dragged into Applications | the AppImage, your distribution's package, or conda-forge's `freecad` | the installer from freecad.org |
| **uv** (preferred: it brings its own Python) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` or `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| **Node 18+** (the backup to uv) | Claude Desktop brings its own for the extension; otherwise [nodejs.org](https://nodejs.org) | [nodejs.org](https://nodejs.org) or your package manager | [nodejs.org](https://nodejs.org) |
| OrcaSlicer (optional, slicing) | [releases](https://github.com/OrcaSlicer/OrcaSlicer/releases) | AppImage or Flatpak | installer |
| KiCad (optional, circuit boards) | [kicad.org](https://www.kicad.org/download/) | your package manager | installer |
| Gmsh, CalculiX (optional, strength checks) | come with FreeCAD | your package manager, or with FreeCAD | come with FreeCAD |

The server itself runs in FreeCAD's own Python, so you never install
FreeCAD's Python libraries by hand. **Open FreeCAD once** after installing it:
that makes the user folder add-ons are installed into.

## Install

Pick one.

### 1. The Claude Desktop extension (Mac)

Download [`freecad-agentlink.mcpb`](https://github.com/jamesK1000011/AgentLink-FreeCAD/releases/latest/download/freecad-agentlink.mcpb) (attached to the newest
`agentlink-v…` [release of this repository](https://github.com/jamesK1000011/AgentLink-FreeCAD/releases)) and double-click it;
Claude Desktop installs it. It finds FreeCAD in Applications, installs Agent Link and the
add-ons bundled with it into FreeCAD and keeps them up to date: Workshop for
FreeCAD, ScanRuler for FreeCAD (ported from ScanRuler by Stefan Hermann,
CNC Kitchen), Texturizer (BumpMesh's textures, also by Stefan Hermann, CNC
Kitchen), Tutor and Agent Link for OrcaSlicer. The extension is built here
(`packaging/`, see `docs/packaging.md`); the copies once released from
ScanRuler's `freecad-spike` branch are retired, and an installed one moves
to this repository at its next update. Its
settings: the output folder (`~/AgentLink` by default), the FreeCAD app if it
is not in Applications, and whether to keep the add-ons up to date.

<!-- screenshot: Claude Desktop's extension settings for Agent Link for FreeCAD -->

### 2. FreeCAD's Addon Manager (custom repository)

1. In FreeCAD: **Edit > Preferences > Addon Manager**, under *Custom
   repositories* add `https://github.com/jamesK1000011/AgentLink-FreeCAD`,
   branch `main`.
2. **Tools > Addon manager**, find **Agent Link**, Install, restart FreeCAD.
3. Connect your agent ([below](#connect-your-agent)).

<!-- screenshot: Addon Manager preferences with the custom repository added -->

### 3. By hand

Put this folder in FreeCAD's `Mod` folder as `AgentLink`. Find the folder
with `--check`, or in FreeCAD's Python console with
`FreeCAD.getUserAppDataDir()` (the `Mod` folder is inside it).

```
git clone https://github.com/jamesK1000011/AgentLink-FreeCAD "<FreeCAD user folder>/Mod/AgentLink"
```

Restart FreeCAD. To use it headless only (no window), you need no install at
all: the `uvx` command in [Connect your agent](#connect-your-agent) runs it.

## Connect your agent

Copy-paste configs for each client are in [docs/clients/](https://github.com/jamesK1000011/AgentLink-FreeCAD/tree/main/docs/clients/):
[Claude Desktop](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/clients/claude-desktop.md),
[Claude Code](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/clients/claude-code.md),
[Cursor](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/clients/cursor.md),
[VS Code](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/clients/vscode.md),
[LM Studio](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/clients/lm-studio.md),
[OpenCode with Ollama](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/clients/opencode-ollama.md) and
[any other MCP client](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/clients/generic.md). ChatGPT needs a remote
server and is out of scope ([why](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/clients/README.md#chatgpt)).

They all start the same command:

```
uvx --from git+https://github.com/jamesK1000011/AgentLink-FreeCAD agentlink-freecad
```

It finds FreeCAD, serves in FreeCAD's own Python, and writes files to
`~/AgentLink` (`--out DIR` for another folder).

**To watch the agent work**, open FreeCAD, pick the **Agent Link** workbench
and press **Start Link**. Calls then arrive in the document open in your
window; with the link off they run headless. The link listens on 127.0.0.1
only and pairs with the server before it takes a call.

## Where everything lives

- **The workbench**: pick *Agent Link* from FreeCAD's workbench list.
- **The toolbar**: *Start Link*, *Stop Link*, *Agent Link panel*, and
  *Screenshot for Agent* (Alt+Shift+S: take the window, mark it up, leave
  it for the agent).
- **The Agent Link menu**: the same, plus *Setup Check* and *Updates* (which
  Agent Link this is and how it is kept up to date).
- **The panel**, docked beside the model tree, in tabs:
  - *Notes*: notes pinned to the parts, between you and the agent; the agent's questions to you;
  - *Steps*: the build played back step by step, a picture a step;
  - *Review*: the part's review, from a reviewer add-on when one is installed;
  - *Activity*: each thing the agent does in this window, as it happens;
  - the tabs of installed add-ons, in their own places between these;
  - the usage strip along the bottom ([Token usage](#token-usage)).
- **The files**: exports, drawings and pictures go to `~/AgentLink` (or the
  folder you chose).

<!-- screenshot: the Agent Link toolbar and menu -->
<!-- screenshot: the panel's tabs and usage strip -->

Agent Link is a hub. Add-ons installed beside it bring their own tools,
guides and panel tabs; Agent Link finds them when FreeCAD starts and names
none of them in its code. Add-ons such as Workshop for FreeCAD (standard
parts, printing and cutting, electronics, documents), ScanRuler for FreeCAD
(scans and reverse engineering, ported from ScanRuler by Stefan Hermann,
CNC Kitchen), Agent Link for OrcaSlicer, SafetyNet
(checkpoints and recovery) and Texturizer each keep their own repository and
licence.

## What the agent can do

<!-- tools:begin (scripts/tool_summary.py) -->
Agent Link itself declares 415 tools in 32 groups; a FreeCAD build without a workbench (FEM, CAM …)
serves fewer, and each installed add-on adds its own groups.
Groups marked *lean* are listed from the start; the agent turns on the rest with `tool_groups`.

| Group | Tools | What it holds |
|---|---:|---|
| `core` *lean* | 19 | The session, groups, guides, batches, jobs (long reads), undo, soundness, export. Always listed. |
| `app` | 18 |  |
| `find` | 1 | tool_find: any tool by plain words, its card, the groups. Listed in the static base (ToolListMode static). |
| `doc` | 12 | The document: new, open, save; objects listed, read, set, renamed, deleted; recompute; import and export files. |
| `model` | 27 | Part modelling: primitives, booleans, move/rotate/mirror/scale/arrays, fillets and chamfers, offset and shell, extrude, revolve, loft, sweep. |
| `measure` | 6 | Find faces and edges (the references other tools take), measure between them, sections, mass properties, clearance. |
| `sketch` | 20 | PartDesign bodies and sketches: geometry, constraints, the solver's reading (DoF, conflicts, closed wires) and edits. |
| `feature` | 27 | PartDesign features (pad, pocket, revolve, hole, fillet, chamfer, draft, shell, patterns, loft, pipe, datum planes) and the body's feature history. |
| `param` | 6 | Named parameters in a Params spreadsheet, and properties or named sketch constraints bound to expressions over them. |
| `sheet` | 12 | Spreadsheets: any cell read and written (values, expressions, aliases, units), formatting, rows and columns, CSV import and export, and design tables (configurations) that drive a part. |
| `material` | 4 | Materials: search FreeCAD's library and the printing filaments, read a card's figures, set what each body is made of. |
| `strength` | 16 | Strength by finite elements (Gmsh and CalculiX): set up a body, hold faces, load them, solve for stress, displacement and safety factor. |
| `techdraw` | 32 | TechDraw pages piece by piece: template and title block, views, projection groups, sections, details, dimensions on real edges with tolerances and fits, GD&T frames, datums, notes, balloons, tables, export to SVG, PDF and DXF. |
| `inspection` | 6 | FreeCAD's Inspection: an actual (mesh, points, body or scan file) against nominals, point by point, with tolerance, statistics, worst spots, a colour map and a report. |
| `view` *lean* | 3 | Pictures: the parts drawn from any view, cut open, zoomed, with maps (wall, stress, a scan's deviation) — headless; the FreeCAD window's own view. |
| `notes` | 7 | Notes pinned to the parts between the person and the agent; the build played back step by step, a picture a step (inspired by Stefan Hermann's ScanRuler, CNC Kitchen). |
| `mesh` | 21 | FreeCAD's Mesh workbench on document meshes: mesh a body, evaluate and repair, decimate, refine, smooth, offset, trim, transform, booleans, cross-sections, split, planar and curvature segments, curvature, projection onto a mesh. |
| `assembly` | 18 | Assemblies (FreeCAD's Assembly workbench): parts put together, one grounded, joints between faces and edges solved; positions, freedom left and overlaps checked. |
| `cam` | 12 | Toolpaths (FreeCAD's CAM workbench): a job with stock and end mill, profile, pocket, adaptive, facing and drilling operations, G-code posted and checked. |
| `draft` | 19 | Draft: lettering raised from or cut into a face from a TrueType font, SVG/DXF outlines, arrays, and Draft's own parametric 2D shapes, dimensions, labels, link arrays, clones, move/rotate/scale/mirror/offset, upgrade/downgrade, layers, hatches, Draft↔Sketch, 2D views, facebinders, heal. |
| `surface` | 11 | Surface workbench features (parametric): sections, boundary surfaces (stretched/Coons/curved), extend, sewing into shells and solids, surface cuts, blend curves; surfaces filled across edges, lofted through curves, fitted to points or a polynomial, thickened into solids. |
| `points` | 9 | Point clouds (Points, Reverse Engineering): read and write ASC/XYZ, PCD, PLY, E57, CSV; sample a body or mesh; crop and thin; fit a plane, sphere, cylinder or B-spline surface, and make it a body. |
| `bim` | 37 | BIM (Arch): walls, windows and doors in walls, columns, beams, slabs, roofs, stairs, spaces, levels, building and site, quantities, IFC in and out. |
| `openscad` | 6 | OpenSCAD: CSG and SCAD files in, OpenSCAD code run into the document, CSG out, hull and Minkowski sums. |
| `robot` | 7 | Robot: six-axis robots (KUKA models, your own kinematics), moves by axes or tool point, trajectories from waypoints or edges, reach checked along them, KUKA KRL out. |
| `std_more` | 22 | Links, App::Part, the dependency graph, freeze, units, point-pair alignment, duplicates, merge files, document info, revert, save all, appearance and face colours, text documents; compounds, join features; PartDesign clone, move feature, reorder, tip. |
| `cam_more` | 3 | CAM paths from areas and shapes, compound, array, stop, fixture offsets, property bags, job templates. |
| `bim_gaps` | 16 | BIM components, clones, references, structural systems, pipe connectors, panel cuts and sheets, nesting, IFC B-rep flag, 2D level views, image planes, library, re-extrude, rewire, glue, trash, reorder. |
| `fem_more` | 3 | FEM: every boundary condition, material, element, equation, solver and mesh refinement by kind; Netgen meshes, FEM mesh to mesh, mesh groups cleared; stress linearization. |
| `unattended` | 3 | Unattended use: the pinned document, the heavy-job queue, the Addon Manager (dialog_answer and app_force_restart are in core). |
| `dev` | 4 | For add-on developers: an installed add-on's own test suite run in a separate FreeCAD process (addon_test); live window scripts replayed and checked (live_run); mouse and keyboard input to the window's own widgets for GUI checks (gui_input), and closing a menu or dialog that holds the window (gui_unstick). |
| `porting` | 8 | Port an add-on to Agent Link: a draft port from its commands (port_scaffold), and cookbooks of its commands, functions and call lists, run after the person's OK. |
<!-- tools:end -->

Each group has a guide the agent reads (`guide_read`). Any tool runs by name
whether it is listed or not. `AGENTLINK_TOOLS=full` lists every tool from the
start; leave it unset for small local models (see
[docs/clients/](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/clients/README.md#small-local-models)).

The table is generated: `python3 scripts/tool_summary.py` rewrites it, and
`--check` (run by the tests) fails when it is stale.

## Platforms

| | macOS | Linux | Windows |
|---|---|---|---|
| Core tools, headless and in the window | supported | CI-tested | expected to work, untested |
| Claude Desktop extension (`.mcpb`) | supported | Mac only | Mac only |
| Unattended features: a hidden FreeCAD kept running, restarts after a crash, app updates, harmless dialogs answered | supported | not yet | not yet |
| Launcher log and Setup Check's launcher report | supported | Mac only | Mac only |

Windows reports are welcome: open an issue saying what worked and what did not.

## Token usage

The panel's usage strip shows what the agent's calls cost in tokens: the
tool list, each call and its answer, and pictures. These are **estimates**
from the text and image sizes, not your provider's billing. The tool
list starts lean, and add-ons that aren't installed cost nothing: their tools are
never listed. `usage_report` gives the agent the same figures; they are kept
in `~/AgentLink/usage`. `AGENTLINK_USAGE=off` turns the meter off.

## Privacy

Agent Link has no telemetry and sends nothing anywhere on its own. What the
agent reads from FreeCAD (answers, pictures) goes to the AI provider your MCP
client uses, under that provider's terms; Agent Link adds no other recipient.

- **The window link** listens on 127.0.0.1 only and pairs with the server
  before it takes a call; nothing outside your computer can reach it.
- **Token usage** figures are estimates kept on your computer
  (`~/AgentLink/usage`); `AGENTLINK_USAGE=off` turns them off.
- **The network** is used only when you or the agent ask for something that
  needs it: installing or updating FreeCAD (`app_install`, from FreeCAD's
  GitHub releases, SHA-256 checked), add-ons fetched from GitHub
  (`app_extensions`, `agentlink_update`, the Claude extension's updates), and
  FreeCAD's add-on catalog read from addons.freecad.org. Each request names
  itself `AgentLink-FreeCAD` and carries no personal details.
- **Your files** stay where you put them: exports, drawings and pictures go
  to `~/AgentLink` (or the folder you chose).

## Troubleshooting

Run the setup check first (`agentlink-freecad --check`); it names what is
missing and how to get it.

**Logs.**
- Claude Desktop: `~/Library/Logs/Claude/mcp-server-*.log` (Mac),
  `%APPDATA%\Claude\logs\mcp-server-*.log` (Windows).
- The Claude extension's launcher (Mac): `~/Library/Logs/FreeCAD Agent Link/launcher.log`.
- Other clients show the server's messages (its stderr) in their own MCP log or output panel.
- In FreeCAD: **View > Panels > Report view**.

**"Server disconnected".** The client started the server and it stopped.
Read the log above: the last lines say why. Most often FreeCAD was not found
(install it, or set `FREECAD_APP` to the app or `FREECAD_LIB` to its `lib`
folder), `uvx` was not on the client's PATH (give its full path, e.g.
`~/.local/bin/uvx`), or FreeCAD is older than 1.0. Restart the client after
a fix.

**"Open FreeCAD once".** A FreeCAD that has never been opened has no user
folder, so nothing can be installed into it. Open FreeCAD, close it, and try
again.

**The window shows nothing.** Pick the Agent Link workbench and press
*Start Link*; calls go headless while the link is off.

**The Claude extension cannot load** (Mac): **Agent Link > Setup Check** in
FreeCAD reports the launcher and offers *Mend* when it can fix it.

## Uninstall

- **Claude Desktop extension**: Settings > Extensions > Agent Link for
  FreeCAD > Uninstall. Then remove the add-on as below.
- **Addon Manager**: Tools > Addon manager > Agent Link > Uninstall.
- **By hand**: delete `<FreeCAD user folder>/Mod/AgentLink`.
- **The client config**: remove the `agentlink-freecad` entry from your
  client's MCP settings. `uv cache clean agentlink-freecad` drops uv's copy.
- **Your files**: `~/AgentLink` (exports, pictures, usage) and
  `~/.config/freecad-agentlink` (the launcher, add-ons fetched by
  `app_extensions`) are yours to keep or delete.

## Tests

`python3 -m unittest discover -s tests` runs the protocol, data, packaging
and release tests anywhere; the tool tests need FreeCAD and are skipped
without it. CI (`.github/workflows/ci.yml`) runs them all on Linux with
FreeCAD 1.0 and the newest release, with PrusaSlicer and OrcaSlicer.

`AGENTLINK_AS_USER=1` is a test flag, off by default: the agent's calls run
as yours (as a click in the panel does), so an add-on that follows what you
do, such as a lesson you work through, can be tested end to end by an agent.
Never set it for real use (`docs/hooks.md`).

## Credits and licence

- The way Agent Link works, one call per job, small answers in millimetres
  and grams, and refusals that say what to do instead, follows **ScanRuler**
  by **Stefan Hermann (CNC Kitchen)**. The panel's notes and step playback
  are inspired by it. Agent Link copies none of ScanRuler's code.
- **FreeCAD** and the libraries and programs it brings (OpenCASCADE,
  CalculiX, Gmsh, Netgen) do the modelling and the analysis.
- Icons are adapted from **Tabler Icons** (MIT, tabler.io) and
  **Pictogrammers Material Design Icons** (Apache-2.0, pictogrammers.com);
  FreeCAD's own icons are used by name. See `agentlink/icons/CREDITS.md`.

The code is LGPL-2.1-or-later (`LICENSE`), so it can sit beside FreeCAD's
own code, and uses only FreeCAD's public Python API. The data files
(`agentlink/data/`) are CC BY 4.0 (`LICENSE-DATA`). Every file's licence is
stated in its SPDX header or in `REUSE.toml`; the licence texts are in
`LICENSES/`.

FreeCAD's `AI_POLICY.md` does not accept AI-generated pull requests, so Agent
Link is a separate add-on, not an upstream change.
