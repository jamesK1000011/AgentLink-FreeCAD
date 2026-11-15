<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# OpenCode with Ollama

Ollama runs the model; [OpenCode](https://opencode.ai) is the MCP client.
In `~/.config/opencode/opencode.json` (or `opencode.json` in a project):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama",
      "options": { "baseURL": "http://localhost:11434/v1" },
      "models": { "gpt-oss:20b": {} }
    }
  },
  "mcp": {
    "agentlink-freecad": {
      "type": "local",
      "command": ["uvx", "--from", "git+https://github.com/jamesK1000011/AgentLink-FreeCAD", "agentlink-freecad"],
      "enabled": true
    }
  }
}
```

Put the model you pulled (`ollama pull gpt-oss:20b`, or another with tool
use) in `models`, and raise Ollama's context (`OLLAMA_CONTEXT_LENGTH=32768`
before `ollama serve`): the default is too short for a tool list.

Keep the lean tool list (the default); see
[Small local models](README.md#small-local-models).
