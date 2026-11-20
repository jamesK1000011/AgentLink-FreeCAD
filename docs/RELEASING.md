<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Releasing

The steps a maintainer runs by hand to release Agent Link for FreeCAD and the
add-ons the Claude extension bundles. Everything before this (versions,
changelogs, the extension's manifest, CI) is prepared in the repositories;
these are the steps that publish.

Steps marked **IRREVERSIBLE** put something public that cannot be taken back
cleanly: a pushed tag is fetched and mirrored at once, a GitHub release is
downloaded, a PyPI version number can never be uploaded again (even after
deleting it), an MCP Registry version cannot be published twice, and an
Addon Index entry is public as soon as it is merged. Read each block before
running it.

Each block starts in a fresh clone in a temporary folder; paste them in one
terminal, in order. A check prints `ok …` or `STOP …`: go on only when every
check says ok. What you need once:
`git`, the GitHub CLI signed in (`gh auth status`), `python3`, `uv`
(`brew install uv`) and, for the MCP Registry, `mcp-publisher`
(`brew install mcp-publisher`).

| Repository | Version | Tag | Assets | PyPI | MCP Registry | Addon Index |
|---|---|---|---|---|---|---|
| AgentLink-OrcaSlicer | 1.0.0 | `v1.0.0` | `orcaslicer-agentlink.mcpb` | no | no | no (no `package.xml`) |
| Workshop-FreeCAD | 1.0.0 | `v1.0.0` | none (source) | no | no | yes, `Workshop` |
| Texturizer-FreeCAD | 1.0.0 | `v1.0.0` | none (source) | no | no | yes, `Texturizer` |
| ScanRuler-FreeCAD | 1.0.0 | `v1.0.0` | none (source) | no | no | yes, `ScanRulerFC` |
| Tutor-FreeCAD | 1.0.0 | `v1.0.0` | none (source) | no | no | yes, `Tutor` (after Agent Link) |
| AgentLink-FreeCAD | 1.0.0 | `agentlink-v1.0.0` | `freecad-agentlink.mcpb` (built by CI) | `agentlink-freecad` | `io.github.jamesK1000011/agentlink-freecad` | yes, `AgentLink` |

Order: the add-ons first, each tagged at the commit the extension pins
(`packaging/pins/` here), so what is tagged is what the extension installs;
then Agent Link, whose tag builds the extension from those pins; then PyPI,
the MCP Registry and the Addon Index.

## 0. Privacy check on what is built

Every artefact is checked before it is published, with the check every
repository carries (`.github/privacy/check.py`; a finding is fixed, never
waived):

```sh
python3 .github/privacy/check.py dist/
```

It reads zip-based files (`.mcpb`, `.whl`) inside; a `.tar.gz` is unpacked
first (the blocks below do that).

## 1. The add-ons (Workshop, Texturizer, ScanRuler for FreeCAD, Tutor)

The same block for each; set the three lines at the top. Values:

| `REPO` | `V` | `PIN` |
|---|---|---|
| Workshop-FreeCAD | 1.0.0 | workshop-ref |
| Texturizer-FreeCAD | 1.0.0 | texturizer-ref |
| ScanRuler-FreeCAD | 1.0.0 | scanrulerfc-ref |
| Tutor-FreeCAD | 1.0.0 | tutor-ref |

```sh
REPO=Workshop-FreeCAD V=1.0.0 PIN=workshop-ref
cd "$(mktemp -d)"
gh repo clone "jamesK1000011/$REPO" -- -q && cd "$REPO"
C=$(gh api "repos/jamesK1000011/AgentLink-FreeCAD/contents/packaging/pins/$PIN" -H "Accept: application/vnd.github.raw" | tr -d '[:space:]')
# The pinned commit must say this version, with a dated changelog section.
git show "$C:package.xml" | grep -q "<version>$V</version>" && echo "ok package.xml $V" || echo "STOP package.xml at the pin is not $V"
git show "$C:CHANGELOG.md" | grep -E -q "^## \[?$V\]? (-|—) [0-9]{4}-" && echo "ok CHANGELOG $V" || echo "STOP no dated $V section in CHANGELOG.md at the pin"
gh run list --commit "$C" --json name,conclusion -q '.[] | "\(.name): \(.conclusion)"'   # every line: success
mkdir dist && git archive --format=zip --prefix="$REPO-$V/" -o "dist/$REPO-$V.zip" "$C"
python3 .github/privacy/check.py dist/
git show "$C:CHANGELOG.md" | awk -v v="$V" '$0 ~ "^## \\[?"v"\\]? " {f=1; next} /^## /{if (f) exit} f' > notes.md
```

Then, **IRREVERSIBLE** (the tag and the release):

```sh
git tag -a "v$V" "$C" -m "$REPO $V"
git push origin "v$V"
gh release create "v$V" --verify-tag --title "$REPO $V" --notes-file notes.md
```

The release carries GitHub's own source archives (the same files the zip
above was checked from). Each tag runs that repository's privacy workflow;
`gh run list --limit 3` shows it pass.

## 2. Agent Link for OrcaSlicer 1.0.0

Its changelog has `## [1.0.0] - <date>` (the release commit). The pin
`packaging/pins/orcalink-ref` here moves to that commit (bake-off green).
Then:

```sh
REPO=AgentLink-OrcaSlicer V=1.0.0 PIN=orcalink-ref
cd "$(mktemp -d)"
gh repo clone "jamesK1000011/$REPO" -- -q && cd "$REPO"
C=$(gh api "repos/jamesK1000011/AgentLink-FreeCAD/contents/packaging/pins/$PIN" -H "Accept: application/vnd.github.raw" | tr -d '[:space:]')
git checkout -q "$C"
python3 -c "import json; v=json.load(open('mcpb/manifest.json'))['version']; print('ok manifest' if v == '$V' else 'STOP manifest says ' + v)"
grep -E -q "^## \[?$V\]? (-|—) [0-9]{4}-" CHANGELOG.md && echo "ok CHANGELOG $V" || echo "STOP no dated $V section in CHANGELOG.md"
node mcpb/test/launcher.test.mjs
mkdir -p dist && sh mcpb/build.sh "$PWD/dist/orcaslicer-agentlink.mcpb"
python3 .github/privacy/check.py dist/
awk -v v="$V" '$0 ~ "^## \\[?"v"\\]? " {f=1; next} /^## /{if (f) exit} f' CHANGELOG.md > notes.md
```

**IRREVERSIBLE**:

```sh
git tag -a "v$V" "$C" -m "$REPO $V"
git push origin "v$V"
gh release create "v$V" --verify-tag --title "Agent Link for OrcaSlicer $V" --notes-file notes.md dist/orcaslicer-agentlink.mcpb
```

No Addon Index entry: it has no `package.xml` (the Claude extension and
Agent Link install it).

## 3. Agent Link for FreeCAD 1.0.0

### 3.1 Checks

```sh
cd "$(mktemp -d)"
gh repo clone jamesK1000011/AgentLink-FreeCAD -- -q && cd AgentLink-FreeCAD
python3 scripts/release.py check --tag agentlink-v1.0.0
# The pinned Agent Link carries this commit's add-on files (FILES): else the
# extension would install an older Agent Link than the tag.
grep -v -E '^#|^$' FILES | tr '\n' '\0' | xargs -0 git diff --quiet "$(cat packaging/pins/addon-ref)" HEAD -- && echo "ok addon-ref is current" || echo "STOP addon-ref pins an older Agent Link"
gh run list --commit "$(git rev-parse HEAD)" --json name,conclusion -q '.[] | "\(.name): \(.conclusion)"'   # every line: success
```

`release.py check` says "1.0.0 agrees everywhere and with
agentlink-v1.0.0" (that is its ok), or lists what does not. If it says Unreleased has
entries (work that landed after the changelog was folded), fold them into
1.0.0 and push, then run the checks again (the `addon-ref` pin moves with
them):

```sh
python3 scripts/release.py fold 1.0.0
git commit -am "Changelog: fold Unreleased into 1.0.0" && git push origin HEAD
```

### 3.2 Tag: the extension is built and attached by CI — **IRREVERSIBLE**

```sh
git tag -a agentlink-v1.0.0 -m "Agent Link for FreeCAD 1.0.0"
git push origin agentlink-v1.0.0
sleep 15; gh run watch "$(gh run list --workflow=mcpb-release.yml --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status
```

`.github/workflows/mcpb-release.yml` checks the tag against every version
(`scripts/release.py check --tag`), clones every add-on at its pin, runs
the launcher test, builds `dist/freecad-agentlink.mcpb`, runs the privacy
check on it and only then creates the release `agentlink-v1.0.0` with the
file attached. The README's download link
(`releases/latest/download/freecad-agentlink.mcpb`) points at it from then
on. Put the changelog's section in as the release notes:

```sh
awk '/^## \[1\.0\.0\] /{f=1; next} /^## /{if (f) exit} f' CHANGELOG.md > notes.md
gh release edit agentlink-v1.0.0 --notes-file notes.md
```

## After the tags: the front doors

The tags and the GitHub releases (sections 1 to 3.2) come first. Then
each front door, in this order. The drafts for every submission are in
[packaging/listing/](https://github.com/jamesK1000011/AgentLink-FreeCAD/tree/main/packaging/listing),
each marked DRAFT. Nothing is submitted for you.

| Front door | What it needs | When |
|---|---|---|
| PyPI `agentlink-freecad` | a PyPI account; trusted publishing (a pending publisher, once) | after the hub tag |
| MCP Registry | the PyPI release; a GitHub sign-in | after PyPI |
| Claude extension (`.mcpb`) | nothing more: it is the release file | at the hub tag |
| Anthropic directory | the PyPI release; a paid Claude plan; GitHub connected on claude.ai | after PyPI |
| FreeCAD Addon Index | repositories 30 days old; private vulnerability reporting on | on or after 14 Dec 2026 (Tutor 15 Dec) |

Rules checked on 19 Nov 2026. Sources are in each section.

### 3.3 PyPI (`agentlink-freecad`) — **IRREVERSIBLE**

The rule: a file name and version number can never be uploaded again, even
after you delete it. Do it in a fresh clone of the tag.

1. Make an account at https://pypi.org/account/register/ and turn on
   two-factor authentication (PyPI requires it to upload).
2. Build and check:

   ```sh
   cd "$(mktemp -d)"
   gh repo clone jamesK1000011/AgentLink-FreeCAD -- -q --branch agentlink-v1.0.0 && cd AgentLink-FreeCAD
   rm -rf dist && uv build
   rm -rf /tmp/sdist-check && mkdir /tmp/sdist-check && tar -xzf dist/agentlink_freecad-1.0.0.tar.gz -C /tmp/sdist-check
   python3 .github/privacy/check.py dist/
   python3 .github/privacy/check.py /tmp/sdist-check
   uvx twine check dist/*
   ```

3. Upload. The chosen way is **trusted publishing** (no token):
   `.github/workflows/pypi-publish.yml` is active and runs on each
   `agentlink-v*` tag. **Before the first hub tag**, add a pending publisher
   once at https://pypi.org/manage/account/publishing/ : project
   `agentlink-freecad`, owner `jamesK1000011`, repository
   `AgentLink-FreeCAD`, workflow `pypi-publish.yml`, environment `pypi`.
   If the tag came first, the publish job fails and uploads nothing: add the
   publisher, then re-run the job (`gh run rerun --failed <run id>`).
   Optional: a required reviewer on the `pypi` environment (Settings >
   Environments > pypi), so each upload waits for you. Guide:
   https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/
   The way by hand, if ever needed: a token from
   https://pypi.org/manage/account/token/ and `uv publish dist/agentlink_freecad-1.0.0*`
   (user `__token__`).
4. Check:

   ```sh
   uvx agentlink-freecad@1.0.0 --version    # agentlink-freecad 1.0.0
   open https://pypi.org/project/agentlink-freecad/
   ```

   The page shows the README. The README's line 2,
   `<!-- mcp-name: io.github.jamesK1000011/agentlink-freecad -->`, must
   be in the page source: the MCP Registry reads it.

No other repository makes a Python package, and none makes an npm
package.

### 3.4 MCP Registry (`server.json`) — **IRREVERSIBLE**

The rules (https://modelcontextprotocol.io/registry/quickstart,
https://modelcontextprotocol.io/registry/package-types):
the registry keeps metadata only; the package must be on PyPI first; the
PyPI README must hold `mcp-name: <server name>`; a GitHub sign-in may
publish names that start with `io.github.<login>/` (the case counts:
`jamesK1000011`); a version is published once only; the description is
100 characters or fewer. The registry is in preview: data resets are
possible.

1. Install the tool once: `brew install mcp-publisher`.
2. Validate and publish, from the top folder of the clone of step 3.3:

   ```sh
   mcp-publisher validate
   mcp-publisher login github
   mcp-publisher publish
   ```

   `login github` shows a code. Enter it at https://github.com/login/device.
3. Check:

   ```sh
   curl -s "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.jamesK1000011/agentlink-freecad"
   ```

`server.json` uses the current schema (2025-12-11). To list the `.mcpb`
file in the registry too, see
[packaging/listing/mcp-registry.md](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/packaging/listing/mcp-registry.md):
do it before the first publish, or with the next version.

## 4. The Claude extension (`.mcpb`)

Nothing to submit. CI attaches `freecad-agentlink.mcpb` to the release
(3.2), and the README links to
`https://github.com/jamesK1000011/AgentLink-FreeCAD/releases/latest/download/freecad-agentlink.mcpb`.

1. Check that the link gives the file:

   ```sh
   curl -sIL https://github.com/jamesK1000011/AgentLink-FreeCAD/releases/latest/download/freecad-agentlink.mcpb | grep -i -E '^(HTTP|content-length)'
   ```

2. Install it on the Mac the way a user does: double-click the file, or
   drag it into the Claude Desktop window, or Settings > Extensions >
   Advanced settings > Install Extension
   (https://claude.com/docs/connectors/building/mcpb).
3. The manifest's `privacy_policies` links to
   [docs/PRIVACY.md](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/PRIVACY.md).

Anthropic's directory does not take `.mcpb` files any more: "desktop
extension listings in the directory are deprecated"
(https://claude.com/docs/connectors/building/submission). The directory
path is the plugin of section 5.

## 5. Anthropic directory (a plugin) — public once published

The rules (https://claude.com/docs/plugins/submit): a plugin from a
public GitHub repository; a paid Claude plan; the GitHub account connected
on claude.ai has push access to the repository; a licence; a README that
says what the plugin does and what data it sends; the directory's
validation and security scan pass; Anthropic publishes the first version.
The draft plugin is
[packaging/listing/claude-plugin/](https://github.com/jamesK1000011/AgentLink-FreeCAD/tree/main/packaging/listing/claude-plugin).
It runs `uvx agentlink-freecad@1.0.0`, so PyPI comes first.

1. Read the plugin pre-submission checklist:
   https://claude.com/docs/plugins/pre-submission-checklist
2. Remove the DRAFT comment line from
   `packaging/listing/claude-plugin/README.md`, push, and validate:

   ```sh
   claude plugin validate ./packaging/listing/claude-plugin
   ```

3. On claude.ai, connect GitHub for your Claude organization.
4. Open https://claude.ai/directory/manage > **Submit new** >
   **Plugin bundle**. Repository `jamesK1000011/AgentLink-FreeCAD`,
   plugin path `packaging/listing/claude-plugin`, branch `main`. Select
   **Validate**.
5. Fill in **Data handling** and **Compliance** from
   [packaging/listing/anthropic-directory.md](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/packaging/listing/anthropic-directory.md),
   then **Submit for review**.
6. When the version passes, select **Publish**. Track it in the portal.

A later version: raise `version` in `plugin.json` and the `@1.0.0` in
`.mcp.json` with the PyPI release.

## 6. FreeCAD Addon Index — **IRREVERSIBLE** once merged

The rules
(https://freecad.github.io/Addon-Academy/Guides/Publishing/Indexed and
https://freecad.github.io/Addon-Academy/Topics/Addon-Index/Index/Qualities):
submit an **issue**, not a pull request, at
https://github.com/FreeCAD/Addons/issues/new/choose, type
**Addon - Addition**, one issue for each add-on; the repository must be
at least 30 days old; the add-on must meet the Qualities (valid
`package.xml`, matching SPDX licences, Python dependencies only from the
allow list, no network at start-up, disclosure of each external
connection, security reports handled, not alpha). A team member reviews
it, asks for a release tag, and adds it to `Data/Index.json`.

1. Wait for the dates: 14 Dec 2026 (Agent Link, Workshop, ScanRuler for
   FreeCAD, Texturizer) and 15 Dec 2026 (Tutor).
2. Turn on private vulnerability reporting in each repository:

   ```sh
   for r in AgentLink-FreeCAD Workshop-FreeCAD Texturizer-FreeCAD ScanRuler-FreeCAD Tutor-FreeCAD; do
     gh api -X PUT "repos/jamesK1000011/$r/private-vulnerability-reporting"
   done
   ```

3. Add the topics `freecad` and `addon`:

   ```sh
   for r in AgentLink-FreeCAD Workshop-FreeCAD Texturizer-FreeCAD ScanRuler-FreeCAD Tutor-FreeCAD; do
     gh repo edit "jamesK1000011/$r" --add-topic freecad --add-topic addon
   done
   ```

4. Run the Bandit scan that the Index runs, and fix what is real:

   ```sh
   for r in AgentLink-FreeCAD Workshop-FreeCAD Texturizer-FreeCAD ScanRuler-FreeCAD Tutor-FreeCAD; do
     (cd "$(mktemp -d)" && gh repo clone "jamesK1000011/$r" -- -q && cd "$r" && uvx bandit -q -r . -x ./tests)
   done
   ```

5. Open one issue for each add-on, Agent Link first (Tutor depends on
   it). Copy the Repository and Notes fields from
   [packaging/listing/freecad-addon-index.md](https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/packaging/listing/freecad-addon-index.md).
   The Index IDs are the Mod folders that the Claude extension installs
   into (`AgentLink`, `Workshop`, `ScanRulerFC`, `Texturizer`, `Tutor`),
   so an install from either place is the same add-on.
6. Answer the reviewer. When they ask for a release, raise `<version>`
   and `<date>` in `package.xml` and tag it.

**Names.** FreeCAD has no published trademark rule for add-on names. The
FPA's brand guidelines (https://fpa.freecad.org/handbook/process/logo.html)
cover the spelling "FreeCAD" and the logo: third parties may use the
logo only to credit FreeCAD or to link to freecad.org. The Addon Academy
(Guides > Polish > Metadata) says that `<name>` "should not" contain the
word FreeCAD and that the description needs no "FreeCAD" either: the
Addon Manager is already inside FreeCAD. So:

- `<name>Agent Link</name>`, `Workshop`, `Texturizer`, `Tutor` agree.
  `ScanRuler for FreeCAD` does not: a later version can use `ScanRuler FC`
  or `ScanRuler`. Ask CNC Kitchen about the name ScanRuler first.
- "for FreeCAD" belongs in the text outside FreeCAD (PyPI, the MCP
  Registry, Anthropic's directory), with the "not affiliated" line. Inside
  the Addon Manager, the first sentence of `<description>` can leave it
  out.
- A short name such as "AgentLink-FC" has no "FreeCAD" in it, so it
  agrees with the guidance.
- The repository names (`AgentLink-FreeCAD`, `Workshop-FreeCAD` and the
  others) can stay. The guidance is about `<name>`, not the repository,
  and many indexed add-ons have "FreeCAD" in the repository name
  (for example `FreeCAD-ClaudeCode`, `FreeCAD-HexFill`). Write it
  "FreeCAD" (capital F, C, A, D) in all text.

## 7. After

- Client docs: once PyPI has 1.0.0, `uvx --from git+…` becomes
  `uvx agentlink-freecad` in `docs/clients/` and the release test's
  `COMMAND` (the Cursor and VS Code install links change with it).
- ScanRuler's `freecad-spike` extension channel retires: the copy of the
  launcher kept there for installed extensions to move over goes once no
  installed copy reads it.
- A later release: the version in `package.xml` (with its date),
  `pyproject.toml`, `server.json` (both places), `agentlink/server.py` and
  `build_server`'s default in `agentlink/tools.py`; then
  `python3 scripts/release.py manifest` and
  `python3 scripts/release.py fold X.Y.Z`. The tests
  (`tests/test_release_tools.py`) fail while any of them disagree. Raise
  the plugin's `version` and `@X.Y.Z` too (section 5), and publish the
  new `server.json` (3.4).
