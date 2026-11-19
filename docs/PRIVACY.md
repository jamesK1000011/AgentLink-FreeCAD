<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Privacy policy: Agent Link for FreeCAD

This policy is for Agent Link for FreeCAD 1.0.0 and later, and for the
add-ons that its Claude extension installs: Workshop, ScanRuler for
FreeCAD, Texturizer, Tutor and Agent Link for OrcaSlicer. It is the
policy that the MCP Registry entry, the Claude extension
(`privacy_policies` in its manifest) and the FreeCAD Addon Index entries
link to.

Agent Link is software that runs on your computer. The maintainers do
not operate a server for it. We receive no data from it.

## 1. What data Agent Link collects

- Agent Link collects no personal data. It has no telemetry, no
  analytics and no crash upload.
- It keeps these records on your computer only:
  - The usage log in `~/AgentLink/usage`: per call, the tool name, the
    time and an estimate of the tokens. It holds no document names, file
    names or file contents. `AGENTLINK_USAGE=off` stops it.
  - `~/AgentLink/approvals.log`: the file steps and code runs that you
    approved.
  - Crash copies in `~/AgentLink/crash`, only when you or the agent run
    `crash_collect`.
  - The Claude extension's launcher log in
    `~/Library/Logs/FreeCAD Agent Link` and its state file in
    `~/.config/freecad-agentlink/state.json` (commit IDs only).
- Your exports, drawings and pictures go to `~/AgentLink` or to the
  output folder that you choose.

## 2. How the data is used and stored

- The records above are for you and for the agent that you connect. They
  help to find faults and to show the cost of a session.
- They stay in the folders above. Agent Link does not send them anywhere.
- The window link listens on 127.0.0.1 only. Nothing outside your
  computer can connect to it.

## 3. Sharing with third parties

- Agent Link sends nothing to a third party on its own.
- Your MCP client (for example Claude Desktop, Claude Code or Cursor)
  sends to its AI provider what the agent reads from FreeCAD (answers,
  pictures). That is the client's traffic, under the
  provider's terms and privacy policy. Agent Link adds no other
  recipient.
- Agent Link uses the network only for these requests. Each request
  sends nothing about you or your files:
  - FreeCAD install or update (`app_install`): from FreeCAD's GitHub
    releases, with a SHA-256 check.
  - Add-on updates (`agentlink_update`, `app_extensions`, and the Claude
    extension at each start when "Keep the add-ons up to date" is on):
    from the add-on repositories on GitHub at their pinned commits.
  - The FreeCAD add-on catalog (`addon`): read from FreeCAD's catalog.
  - The printers that you set up in Workshop Make: on your own network.
- GitHub (privacy statement:
  https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement)
  can see the IP address of each download, as with any download.

## 4. How long data is kept

- The records stay on your computer until you delete them.
- `outputs_clean` deletes old files that Agent Link made: pictures after
  3 days (it keeps the last 50), solver and job runs after 14 days, and
  FreeCAD backups after 7 days. It lists exports but does not delete
  them.
- To remove all of it, delete `~/AgentLink`,
  `~/.config/freecad-agentlink` and `~/Library/Logs/FreeCAD Agent Link`.
  The README's "Uninstall" section gives all the steps.

## 5. Changes

A later version may collect or send more data. If so, this policy and
the changelog say so before that version is released. The feature then
asks for your consent first.

## 6. Contact

- Questions and requests: open an issue at
  https://github.com/jamesK1000011/AgentLink-FreeCAD/issues
- Security reports: use "Report a vulnerability" at
  https://github.com/jamesK1000011/AgentLink-FreeCAD/security
