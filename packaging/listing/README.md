<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Listing drafts (DRAFT: the owner submits)

All files in this folder are drafts. Nothing here is submitted. The owner
submits each one by hand, in the order of `docs/RELEASING.md`
(sections 3.3 to 6). Read the rules that each front door has in that file.

| File | Front door | Submitted how |
|---|---|---|
| [freecad-addon-index.md](freecad-addon-index.md) | FreeCAD Addon Index (FreeCAD/Addons) | one "Addon - Addition" issue for each add-on |
| [mcp-registry.md](mcp-registry.md) | Official MCP Registry | `mcp-publisher publish` of the top-level `server.json` |
| [anthropic-directory.md](anthropic-directory.md) | Anthropic's directory (claude.ai) | developer portal, "Plugin bundle" |
| [claude-plugin/](claude-plugin/) | the plugin that the portal reads | portal "Plugin path": `packaging/listing/claude-plugin` |
| [pypi-publish.yml](pypi-publish.yml) | PyPI trusted publishing (optional) | move to `.github/workflows/` and register it on PyPI |

The listing text for every place is in
[docs/listing.md](../../docs/listing.md). The privacy policy is
[docs/PRIVACY.md](../../docs/PRIVACY.md).

`packaging/` is not in `FILES`, so the add-on that FreeCAD and the Claude
extension install does not carry these drafts.
