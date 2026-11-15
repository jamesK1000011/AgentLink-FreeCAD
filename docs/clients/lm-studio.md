<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# LM Studio

LM Studio 0.3.17 or later: **Program** tab (right sidebar) **> Install >
Edit mcp.json** (`~/.lmstudio/mcp.json`), and add:

```json
{
  "mcpServers": {
    "agentlink-freecad": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/jamesK1000011/AgentLink-FreeCAD", "agentlink-freecad"]
    }
  }
}
```

Turn the server on in the chat's integrations. Local models: keep the lean
tool list (the default) and see [Small local models](README.md#small-local-models).
Pick a model that supports tool use, with a context of 32k tokens or more.
