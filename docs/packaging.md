<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Packaging

Agent Link ships three ways from this one folder:

| Form | Built from | For |
|---|---|---|
| FreeCAD add-on | the folder as it is (`package.xml`, `Init.py`, `InitGui.py`) | the Addon Manager, or a copy in `Mod` |
| Python package `agentlink-freecad` | `pyproject.toml` | `uvx` and any MCP client's config |
| Claude Desktop extension (`.mcpb`, Mac) | `packaging/mcpb` (launcher, manifest, build), `packaging/addons.json`, `packaging/pins` | double-click install in Claude Desktop |

## The Python package

The server is started by path (`agentlink_headless.py`) and puts its own
folder on `sys.path`, so it runs from anywhere: the add-on folder, a
checkout, or a package's `site-packages`. It needs FreeCAD's own Python,
which no package index has. So the package is a launcher:

- `agentlink-freecad` (`agentlink/launch.py`) runs in whatever Python uv
  gives it. It finds FreeCAD (`agentlink/setup_check.py`: `FREECAD_APP`,
  `FREECAD_LIB`, a Python that imports FreeCAD, then where each OS's
  installer puts it), and runs `agentlink_headless.py` in FreeCAD's Python
  (or `FreeCADCmd`, flags by env), with stdin and stdout passed through.
- `--connect` (the relay to the window) and `--check` need no FreeCAD and run
  in the launcher's own Python.
- The package has no dependencies. It carries `agentlink/`, its families,
  guides and data, and the two top-level modules; not the workbench, icons or
  themes, which only the add-on needs.

`uvx --from git+https://github.com/jamesK1000011/AgentLink-FreeCAD agentlink-freecad`
works without anything on PyPI. To build: `uv build` (or
`python3 -m pip wheel --no-deps .`); offline, with setuptools 77 or later
already installed, `uv build --no-build-isolation`. setuptools 77 is the
first to take the licence expression and `license-files` in `[project]`
(PEP 639). `agentlink-freecad --version` prints the version without
looking for FreeCAD. Nothing is published; a PyPI release would be
`uv publish` of that build, from a tag, best through PyPI's trusted
publishing (a workflow on the tag, no token kept anywhere). Once it is on
PyPI the client configs can drop `--from git+…` for plain
`uvx agentlink-freecad`.

The README's links are absolute (`https://github.com/…/blob/main/…`): PyPI
and the Addon Manager show the README away from the repository, where
relative links break. The release test checks it.

## The MCP Registry entry

`server.json` lists the PyPI package for the
[MCP Registry](https://registry.modelcontextprotocol.io). The registry
checks that the package is ours by the README's
`<!-- mcp-name: io.github.jamesK1000011/agentlink-freecad -->` line, which
PyPI shows as the package's description, so the entry can only be
published after the PyPI release, with `mcp-publisher publish` signed in
through GitHub. The release test keeps its versions, name and package in
step with `pyproject.toml`.

### What differs from the add-on copy

- Add-ons are found where FreeCAD puts them on the path (its `Mod`
  folders), as headless runs from a checkout find them; the "Mod folders
  beside this add-on" scan (`ext._paths`) finds nothing in `site-packages`.
- The window's workbench is the add-on's copy, the server the package's:
  keep them at the same version (update the add-on when you update the
  package).
- Unattended app updates smoke-test the add-on folders they are given; the
  package's copy is not one of them.

## The Claude Desktop extension

Built and released from this repository: tag `agentlink-v*` runs
`.github/workflows/mcpb-release.yml`, which checks out every add-on at its
pin, builds with `packaging/mcpb/build.sh`, runs the privacy and identity
check on the built file, and only then attaches it to the tag's
[release](https://github.com/jamesK1000011/AgentLink-FreeCAD/releases). Its Node launcher (`packaging/mcpb/server/index.js`) finds
FreeCAD in Applications, installs Agent Link and the pinned add-ons into
FreeCAD's `Mod` folder, and starts the server in FreeCAD's Python. It is
macOS-only for now.

What it installs is `packaging/addons.json` (the add-ons, each a repository
and the Mod folder it goes in) at the commits in `packaging/pins/<name>-ref`:
Agent Link, Workshop for FreeCAD, ScanRuler for FreeCAD (ported from
ScanRuler by Stefan Hermann, CNC Kitchen; AGPL-3.0-only), Texturizer (from
Stefan Hermann's BumpMesh, CNC Kitchen; AGPL-3.0-only), Tutor and Agent Link
for OrcaSlicer. Each keeps its own licence; the launcher, manifest and build
script are LGPL-2.1-or-later. `packaging/` is not in `FILES`, so the add-on
copy the launcher installs does not carry it.

**Updates.** The installed launcher updates itself and the add-ons
(`agentlink_update`, and at each start) from this repository's `main`: the
manifest, the pins and the launcher of one commit. If that cannot be read
(manifest or a pin missing), it reads the channel used before 16 Nov 2026,
ScanRuler's `freecad-spike` (`scripts/freecad/addons.json`,
`scripts/bakeoff/*-ref`), which is kept in step until every installed copy
has moved.

**Pins.** A pin moves only once `.github/workflows/bakeoff.yml` is green:
every add-on at its pin, their tests together, the launcher test, the
extension built and checked, and the bake-off brief. Bump on a `pins-*`
branch, then fast-forward `main`; a push to `main` is installed at the next
update. The launcher test checks that every pin the manifest names is here
and holds a commit.

## Releasing

Tagging is the one step left: the version is `0.3.0` in `package.xml`,
`pyproject.toml` and `agentlink/server.py` (the tests check they agree), and
`CHANGELOG.md`'s Unreleased section becomes `## [0.3.0] - <date>`.
