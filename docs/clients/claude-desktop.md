<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Claude Desktop

**On a Mac, the extension is simplest**: download `freecad-agentlink.mcpb`
from the newest `agentlink-v…` release and double-click it. It finds FreeCAD,
installs the add-on and keeps it up to date. Nothing below is needed.

Otherwise (Windows, or a Mac without the extension): **Settings > Developer
> Edit Config** opens `claude_desktop_config.json`
(`~/Library/Application Support/Claude/` on Mac,
`%APPDATA%\Claude\` on Windows). Add:

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

Quit and reopen Claude Desktop. If it says the server disconnected, give
`uvx`'s full path in `command` and see the README's Troubleshooting. Logs:
`~/Library/Logs/Claude/mcp-server-agentlink-freecad.log` (Mac),
`%APPDATA%\Claude\logs\` (Windows).
