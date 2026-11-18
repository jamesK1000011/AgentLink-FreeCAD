// SPDX-License-Identifier: LGPL-2.1-or-later
// The extension's launcher against a fake FreeCAD: it serves, restarts a
// crashed FreeCAD, and agentlink_update installs new add-ons and starts
// FreeCAD again without the connection dropping, and hands over to a newer
// launcher in-process, also under Claude Desktop's built-in Node. Node only.
import { execFileSync, spawn } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import readline from 'node:readline'
import assert from 'node:assert/strict'

const here = path.dirname(new URL(import.meta.url).pathname)

// The launcher names no add-on beyond the data list: its built-in fallbacks
// are the lists in packaging/addons.json, field for field.
{
  const text = fs.readFileSync(path.join(here, '..', 'server', 'index.js'), 'utf8')
  const data = JSON.parse(fs.readFileSync(path.join(here, '..', '..', 'addons.json'), 'utf8'))
  const literal = (name) => new Function(`return ${new RegExp(`const ${name} = (\\[[\\s\\S]*?\\n\\])`).exec(text)[1]}`)()
  assert.deepEqual(literal('SOURCES'), data.sources.map((s) => ({ repo: s.repo, branch: s.branch, folder: s.folder, dest: s.dest, pin: s.pin })), 'the built-in SOURCES are addons.json\'s sources')
  assert.ok(!/COMPANIONS_DEFAULT|bumpmesh/i.test(text.replace(/^\s*(\/\/|\*|\/\*\*).*$/gm, '')), 'the launcher names no companion: they come from addons.json')
}
// Companions are read from addons.json: the bundled copy (build.sh puts it
// at the bundle's top; a checkout's packaging/addons.json), then the list
// the last update kept, then the local setting; none when there is no list.
{
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'agentlink-companions-'))
  const data = JSON.parse(fs.readFileSync(path.join(here, '..', '..', 'addons.json'), 'utf8'))
  const bundle = path.join(home, 'bundle')
  fs.mkdirSync(bundle)
  const stand = [{ name: 'standin', dir: '~/src/standin', url: 'https://github.com/jamesK1000011/standin.git', branch: 'main', process: 'mcp/' }]
  fs.writeFileSync(path.join(bundle, 'addons.json'), JSON.stringify({ sources: [], companions: stand }))
  const kept = path.join(home, 'kept.json')
  const local = path.join(home, 'local.json')
  const script = `
global.__agentlinkHandover = true
const L = require(${JSON.stringify(path.join(here, '..', 'server', 'index.js'))})
global.__agentlinkHandover = false
const [checkout, bundle, kept, local, empty] = JSON.parse(process.env.T)
const names = (l) => l.map((c) => c.name + '@' + c.branch)
const fs = require('fs')
const out = {}
out.checkout = names(L.companions(checkout, kept, local))
out.bundle = names(L.companions(bundle, kept, local))
out.none = names(L.companions(empty, kept, local))
fs.writeFileSync(kept, JSON.stringify([{ name: 'keptone', dir: '~/src/k', url: 'https://github.com/jamesK1000011/k.git', branch: 'b' }]))
out.kept = names(L.companions(bundle, kept, local))
fs.writeFileSync(kept, JSON.stringify([{ name: 'bad', dir: '/etc', url: 'https://example.com/x.git', branch: 'b' }]))
out.badKept = names(L.companions(bundle, kept, local))
fs.writeFileSync(local, JSON.stringify([{ name: 'mine', dir: '~/src/m', url: 'x', branch: 'dev' }]))
out.local = names(L.companions(bundle, kept, local))
out.dirExpanded = L.companions(bundle, kept, local)[0].dir.startsWith(require('os').homedir())
process.stdout.write(JSON.stringify(out))
`
  try {
    const empty = path.join(home, 'empty', 'deeper')
    fs.mkdirSync(empty, { recursive: true })
    const out = JSON.parse(execFileSync(process.execPath, ['-e', script], { env: { ...process.env, HOME: home, AGENTLINK_UPDATE: 'false', T: JSON.stringify([path.join(here, '..'), bundle, kept, local, empty]) }, encoding: 'utf8' }))
    assert.deepEqual(out.checkout, data.companions.map((c) => c.name + '@' + c.branch), 'a checkout reads packaging/addons.json')
    assert.deepEqual(out.bundle, ['standin@main'], 'a bundle reads its own addons.json')
    assert.deepEqual(out.none, [], 'no addons.json: no companions')
    assert.deepEqual(out.kept, ['keptone@b'], 'the list the last update kept wins over the bundled one')
    assert.deepEqual(out.badKept, ['standin@main'], 'a kept list this launcher does not take is passed over')
    assert.deepEqual(out.local, ['mine@dev'], 'the local setting wins over both')
    assert.ok(out.dirExpanded, '~ is the home folder')
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
  console.log('launcher companions: from addons.json (bundled, then kept by the last update), the local setting over both')
}
// agentlink_update's window restart: a fresh heartbeat naming another call
// in hand means the app_restart was queued behind it (a window held by a
// nested event loop), so the update force-restarts it; app_restart itself
// in hand, a stale heartbeat or no call is not that.
{
  const script = `
global.__agentlinkHandover = true
const L = require(${JSON.stringify(path.join(here, '..', 'server', 'index.js'))})
global.__agentlinkHandover = false
const now = 1000
process.stdout.write(JSON.stringify({
  held: L.windowHeld({ pid: 42, t: 999, busy: 'batch', busySince: 200 }, now),
  restarting: L.windowHeld({ pid: 42, t: 999, busy: 'app_restart' }, now),
  stale: L.windowHeld({ pid: 42, t: 900, busy: 'batch' }, now),
  idle: L.windowHeld({ pid: 42, t: 999, busy: null }, now),
  none: L.windowHeld(null, now),
  word: L.restartWord({ pid: 42, t: 999, pinned: 'Lesson', docs: [{ name: 'Lesson', label: 'bike-stem-1', file: '/x/l.FCStd' }] }, now),
  noWord: L.restartWord(null, now),
}))
`
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'agentlink-held-'))
  const out = JSON.parse(execFileSync(process.execPath, ['-e', script], { env: { ...process.env, HOME: home, AGENTLINK_UPDATE: 'false' }, encoding: 'utf8' }))
  assert.deepEqual(out.held, { pid: 42, busy: 'batch', since: 200 }, 'a window held by another call is hung for the update')
  assert.equal(out.restarting, null, 'app_restart in hand: it was taken')
  assert.equal(out.stale, null, 'a stale heartbeat: no window to judge')
  assert.equal(out.idle, null)
  assert.equal(out.none, null)
  assert.deepEqual(out.word, { pid: 42, t: 1000, pinned: { name: 'Lesson', label: 'bike-stem-1', file: '/x/l.FCStd' } }, 'the restart word for the next supervisor (finding 52)')
  assert.equal(out.noWord, null)
}
// A stdio server (addons.json's stdio: Agent Link for OrcaSlicer, run by its
// own Claude extension from a cache of versions): the installed copy goes
// into that cache and becomes current, once a commit, with its commit before
// and after for agentlink_update's answer; nothing where that extension has
// not run (live 68).
{
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'agentlink-stdio-'))
  const sha = 'c'.repeat(40)
  const old = 'a'.repeat(40)
  const mod = path.join(home, 'Mod')
  fs.mkdirSync(path.join(mod, 'OrcaLink', 'orcalink', '__pycache__'), { recursive: true })
  fs.writeFileSync(path.join(mod, 'OrcaLink', 'orcalink_server.py'), '# server\n')
  fs.writeFileSync(path.join(mod, 'OrcaLink', 'orcalink', '__pycache__', 'x.pyc'), '')
  const set = path.join(home, 'set')
  fs.mkdirSync(set)
  const stdio = { name: 'orcaslicer-agentlink', cache: '~/.config/orcaslicer-agentlink', entry: 'orcalink_server.py' }
  fs.writeFileSync(path.join(set, '.sources.json'), JSON.stringify([{ repo: 'AgentLink-FreeCAD', branch: 'main', folder: '', dest: 'AgentLink' }, { repo: 'AgentLink-OrcaSlicer', branch: 'main', folder: '', dest: 'OrcaLink', stdio }]))
  fs.writeFileSync(path.join(set, '.shas.json'), JSON.stringify({ AgentLink: 'd'.repeat(40), OrcaLink: sha }))
  const script = `
global.__agentlinkHandover = true
const L = require(${JSON.stringify(path.join(here, '..', 'server', 'index.js'))})
global.__agentlinkHandover = false
const [mod, set, home] = JSON.parse(process.env.T)
const fs = require('fs')
const path = require('path')
const out = { none: L.publishStdio(mod, set, home) }
const cache = path.join(home, '.config', 'orcaslicer-agentlink')
fs.mkdirSync(cache, { recursive: true })
fs.writeFileSync(path.join(cache, 'state.json'), JSON.stringify({ current: ${JSON.stringify(old)}, bad: [] }))
out.first = L.publishStdio(mod, set, home)
out.state = JSON.parse(fs.readFileSync(path.join(cache, 'state.json'), 'utf8'))
out.copied = fs.existsSync(path.join(cache, 'app-${sha}', 'orcalink_server.py'))
out.noCache = fs.existsSync(path.join(cache, 'app-${sha}', 'orcalink', '__pycache__'))
// The other launcher fetched a newer head since: not undone.
fs.writeFileSync(path.join(cache, 'state.json'), JSON.stringify({ ...out.state, current: ${JSON.stringify('e'.repeat(40))} }))
out.again = L.publishStdio(mod, set, home)
out.after = JSON.parse(fs.readFileSync(path.join(cache, 'state.json'), 'utf8')).current
out.badStdio = L.checkSources([{ repo: 'AgentLink-FreeCAD', branch: 'main', dest: 'AgentLink' }, { repo: 'X', branch: 'main', dest: 'X', stdio: { name: 'x', cache: '/etc', entry: 'a.py' } }])
out.kept = L.checkSources(JSON.parse(fs.readFileSync(path.join(set, '.sources.json'), 'utf8')))[1].stdio
process.stdout.write(JSON.stringify(out))
`
  const out = JSON.parse(execFileSync(process.execPath, ['-e', script], { env: { ...process.env, HOME: home, AGENTLINK_UPDATE: 'false', T: JSON.stringify([mod, set, home]) }, encoding: 'utf8' }))
  assert.deepEqual(out.none, [], 'that extension never ran here: nothing done, nothing said')
  assert.deepEqual(out.first, [{ name: 'orcaslicer-agentlink', from: 'aaaaaaa', to: 'ccccccc', note: 'its running server takes the new code at its next call' }])
  assert.equal(out.state.current, sha)
  assert.equal(out.state.previous, 'a'.repeat(40))
  assert.equal(out.state.hubPinned, sha)
  assert.ok(out.copied, 'the installed copy is in the cache')
  assert.ok(!out.noCache, 'no __pycache__ copied')
  assert.deepEqual(out.again, [{ name: 'orcaslicer-agentlink', from: 'eeeeeee', to: 'eeeeeee', note: 'unchanged since the last update' }])
  assert.equal(out.after, 'e'.repeat(40))
  assert.equal(out.badStdio, null, 'a cache outside the home folder is refused')
  assert.deepEqual(out.kept, stdio)
}
// A stdio server's add-ons (addons.json's serverAddons: PrintLoop for the
// OrcaSlicer server): fetched with the set into its hidden .server-addons
// folder, then put in the server's own app folder (app-<commit>/addons), with
// an .id the running server compares. A new add-on pin at the same server
// commit publishes again; the same pins do not. Never in the Mod folder,
// never under ~/AgentLink. An add-on of a server that is not listed, or with
// a name that is not plain, is refused.
{
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'agentlink-srvaddons-'))
  const sha = 'c'.repeat(40)
  const pl1 = '1'.repeat(40)
  const pl2 = '2'.repeat(40)
  const mod = path.join(home, 'Mod')
  fs.mkdirSync(path.join(mod, 'OrcaLink', 'orcalink'), { recursive: true })
  fs.writeFileSync(path.join(mod, 'OrcaLink', 'orcalink_server.py'), '# server\n')
  const set = path.join(home, 'set')
  const pkg = path.join(set, '.server-addons', 'orcaslicer-agentlink', 'PrintLoop-OrcaSlicer', 'printloop')
  fs.mkdirSync(path.join(pkg, '__pycache__'), { recursive: true })
  fs.writeFileSync(path.join(pkg, '__init__.py'), '')
  fs.writeFileSync(path.join(pkg, 'orcalink_addon.py'), 'def tools(ctx):\n    return []\n')
  fs.writeFileSync(path.join(pkg, '__pycache__', 'x.pyc'), '')
  const stdio = { name: 'orcaslicer-agentlink', cache: '~/.config/orcaslicer-agentlink', entry: 'orcalink_server.py' }
  const sources = [{ repo: 'AgentLink-FreeCAD', branch: 'main', folder: '', dest: 'AgentLink' }, { repo: 'AgentLink-OrcaSlicer', branch: 'main', folder: '', dest: 'OrcaLink', stdio }]
  const pl = { repo: 'PrintLoop-OrcaSlicer', branch: 'main', folder: '', dest: 'PrintLoop-OrcaSlicer', pin: 'packaging/pins/printloop-ref', server: 'orcaslicer-agentlink' }
  fs.writeFileSync(path.join(set, '.sources.json'), JSON.stringify(sources))
  fs.writeFileSync(path.join(set, '.shas.json'), JSON.stringify({ AgentLink: 'd'.repeat(40), OrcaLink: sha }))
  fs.writeFileSync(path.join(set, '.server-addons.json'), JSON.stringify([{ ...pl, sha: pl1 }]))
  const script = `
global.__agentlinkHandover = true
const L = require(${JSON.stringify(path.join(here, '..', 'server', 'index.js'))})
global.__agentlinkHandover = false
const [mod, set, home, pl, sources, pl2] = JSON.parse(process.env.T)
const fs = require('fs')
const path = require('path')
const cache = path.join(home, '.config', 'orcaslicer-agentlink')
fs.mkdirSync(cache, { recursive: true })
fs.writeFileSync(path.join(cache, 'state.json'), JSON.stringify({ current: 'a'.repeat(40) }))
const app = path.join(cache, 'app-' + 'c'.repeat(40))
const out = { first: L.publishStdio(mod, set, home) }
out.state = JSON.parse(fs.readFileSync(path.join(cache, 'state.json'), 'utf8'))
out.addon = fs.existsSync(path.join(app, 'addons', 'PrintLoop-OrcaSlicer', 'printloop', 'orcalink_addon.py'))
out.noCache = fs.existsSync(path.join(app, 'addons', 'PrintLoop-OrcaSlicer', 'printloop', '__pycache__'))
out.id = fs.readFileSync(path.join(app, 'addons', '.id'), 'utf8').trim()
out.inMod = fs.readdirSync(mod)
out.same = L.publishStdio(mod, set, home)
fs.writeFileSync(path.join(set, '.server-addons.json'), JSON.stringify([{ ...pl, sha: pl2 }]))
out.moved = L.publishStdio(mod, set, home)
out.state2 = JSON.parse(fs.readFileSync(path.join(cache, 'state.json'), 'utf8'))
out.id2 = fs.readFileSync(path.join(app, 'addons', '.id'), 'utf8').trim()
fs.writeFileSync(path.join(set, '.server-addons.json'), JSON.stringify([]))
out.dropped = L.publishStdio(mod, set, home)
out.left = fs.existsSync(path.join(app, 'addons'))
out.noServer = L.checkServerAddons([{ ...pl, server: 'nobody' }], sources)
out.badDest = L.checkServerAddons([{ ...pl, dest: '../x' }], sources)
out.twice = L.checkServerAddons([pl, pl], sources)
out.none = L.checkServerAddons(undefined, sources)
process.stdout.write(JSON.stringify(out))
`
  const out = JSON.parse(execFileSync(process.execPath, ['-e', script], { env: { ...process.env, HOME: home, AGENTLINK_UPDATE: 'false', T: JSON.stringify([mod, set, home, pl, sources, pl2]) }, encoding: 'utf8' }))
  try {
    assert.deepEqual(out.first, [{ name: 'orcaslicer-agentlink', from: 'aaaaaaa', to: 'ccccccc', addons: ['PrintLoop-OrcaSlicer@1111111'], note: 'its running server takes the new code at its next call' }])
    assert.equal(out.state.current, sha)
    assert.equal(out.state.hubPinned, `${sha}+PrintLoop-OrcaSlicer@${pl1}`)
    assert.ok(out.addon, 'the add-on is in the app folder\'s addons folder')
    assert.ok(!out.noCache, 'no __pycache__ copied')
    assert.equal(out.id, out.state.hubPinned)
    assert.deepEqual(out.inMod, ['OrcaLink'], 'nothing goes into the Mod folder')
    assert.equal(out.same[0].note, 'unchanged since the last update')
    assert.deepEqual(out.moved[0].addons, ['PrintLoop-OrcaSlicer@2222222'], 'a new add-on pin at the same server commit publishes again')
    assert.equal(out.state2.current, sha)
    assert.equal(out.id2, `${sha}+PrintLoop-OrcaSlicer@${pl2}`)
    assert.equal(out.dropped[0].error, undefined)
    assert.ok(!out.left, 'an add-on taken off the list goes from the app folder')
    assert.equal(out.noServer, null, 'an add-on of a server that is not listed is refused')
    assert.equal(out.badDest, null)
    assert.equal(out.twice, null)
    assert.deepEqual(out.none, [])
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
  console.log('launcher server add-ons: pinned, put in the server\'s own app folder, published again on a new pin, never in the Mod folder')
}
// An update's words on add-ons left out: none, nothing said; one, named
// with its error, the groups gone compared with before, and a warning.
{
  const script = `
global.__agentlinkHandover = true
const L = require(${JSON.stringify(path.join(here, '..', 'server', 'index.js'))})
global.__agentlinkHandover = false
process.stdout.write(JSON.stringify({
  none: L.extensionReport({ groups: { a: 1 } }, { ok: true, extensions: { loaded: ['x'], leftOut: [] }, groups: { a: 1 } }),
  old: L.extensionReport({}, { ok: true }),
  one: L.extensionReport({ groups: { core: 3, scan: 133, gone: 0 } }, { ok: true, extensions: { leftOut: [{ extension: 'scan.agentlink_families', error: 'SyntaxError: bad' }] }, groups: { core: 3 } }),
  noBefore: L.extensionReport({}, { ok: true, extensions: { leftOut: [{ extension: 'a.agentlink_families' }, { extension: 'b.agentlink_families', error: 'E' }] }, groups: { core: 3 } }),
  noFile: L.extensionRecord('/nonexistent/extensions.json'),
}))
`
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'agentlink-ext-'))
  const out = JSON.parse(execFileSync(process.execPath, ['-e', script], { env: { ...process.env, HOME: home, AGENTLINK_UPDATE: 'false' }, encoding: 'utf8' }))
  assert.deepEqual(out.none, {}, 'every add-on loaded: nothing said')
  assert.deepEqual(out.old, {}, 'a smoke test from before this: nothing said')
  assert.deepEqual(out.one.leftOut, [{ extension: 'scan.agentlink_families', error: 'SyntaxError: bad' }])
  assert.deepEqual(out.one.lostGroups, ['scan'])
  assert.match(out.one.warning, /An installed add-on did not load.*: scan\. Tool groups gone compared with before: scan\./)
  assert.equal(out.noBefore.lostGroups, undefined, 'no record of before: no groups claimed lost')
  assert.match(out.noBefore.warning, /Installed add-ons did not load.*a, b\./)
  assert.equal(out.noBefore.leftOut[0].error, 'no error given')
  assert.deepEqual(out.noFile, {})
  fs.rmSync(home, { recursive: true, force: true })
  console.log('launcher extensions: an add-on left out is named with its error, the groups gone and a warning')
}
// Every pin the manifest names is a file here holding one commit.
{
  const repo = path.join(here, '..', '..', '..')
  const m = JSON.parse(fs.readFileSync(path.join(here, '..', '..', 'addons.json'), 'utf8'))
  for (const s of [...m.sources, ...(m.serverAddons || [])]) {
    assert.match(s.pin, /^packaging\/pins\/[a-z]+-ref$/, `${s.repo}'s pin is under packaging/pins`)
    assert.match(fs.readFileSync(path.join(repo, s.pin), 'utf8').trim(), /^[0-9a-f]{40}$/, `${s.pin} holds a commit`)
  }
}
// The update channel: AgentLink-FreeCAD's main, with its manifest and pins;
// ScanRuler's freecad-spike (scripts/freecad/addons.json, scripts/bakeoff
// pins) only when the new one's head, manifest or a pin cannot be read;
// an error, not a mix, when neither can. GitHub is a table here.
{
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'agentlink-channel-'))
  const repo = path.join(here, '..', '..', '..')
  const manifest = fs.readFileSync(path.join(here, '..', '..', 'addons.json'), 'utf8')
  const oldManifest = manifest.replace(/packaging\/pins\//g, 'scripts/bakeoff/')
  const pins = {}
  for (const s of [...JSON.parse(manifest).sources, ...(JSON.parse(manifest).serverAddons || [])]) pins[s.pin] = fs.readFileSync(path.join(repo, s.pin), 'utf8')
  const script = `
const run = async () => {
  global.__agentlinkHandover = true
  const L = require(${JSON.stringify(path.join(here, '..', 'server', 'index.js'))})
  global.__agentlinkHandover = false
  const { manifest, oldManifest, pins } = JSON.parse(process.env.T)
  const NEW = 'a'.repeat(40), OLD = 'b'.repeat(40)
  const io = (drop) => ({
    headSha: async (repo) => {
      if (drop.includes('head:' + repo)) throw new Error('unreachable')
      return repo === 'AgentLink-FreeCAD' ? NEW : repo === 'ScanRuler' ? OLD : 'c'.repeat(40)
    },
    getFile: async (url) => {
      const files = {}
      files['AgentLink-FreeCAD/' + NEW + '/packaging/addons.json'] = manifest
      files['ScanRuler/' + OLD + '/scripts/freecad/addons.json'] = oldManifest
      for (const [p, v] of Object.entries(pins)) {
        files['AgentLink-FreeCAD/' + NEW + '/' + p] = v
        files['ScanRuler/' + OLD + '/' + p.replace('packaging/pins/', 'scripts/bakeoff/')] = v.replace(/^./, 'd')
      }
      const key = url.replace('https://raw.githubusercontent.com/jamesK1000011/', '')
      if (drop.includes(key) || !(key in files)) throw new Error(url + ': HTTP 404')
      return Buffer.from(files[key])
    },
  })
  const out = {}
  const pick = (r) => ({ repo: r.channel.repo, launcher: r.channel.launcher, sha: r.sha, pins: r.sources.map((s) => s.pin), shas: r.shas, companions: !!r.companions, addons: r.serverAddons.map((a) => [a.dest, a.server]), addonShas: r.addonShas })
  out.ok = pick(await L.resolveChannel(io([])))
  out.noManifest = pick(await L.resolveChannel(io(['AgentLink-FreeCAD/' + NEW + '/packaging/addons.json'])))
  out.noPin = pick(await L.resolveChannel(io(['AgentLink-FreeCAD/' + NEW + '/packaging/pins/tutor-ref'])))
  out.noHead = pick(await L.resolveChannel(io(['head:AgentLink-FreeCAD'])))
  try { await L.resolveChannel(io(['head:AgentLink-FreeCAD', 'ScanRuler/' + OLD + '/scripts/freecad/addons.json'])); out.none = 'resolved' } catch (e) { out.none = e.message }
  out.channels = L.CHANNELS
  process.stdout.write(JSON.stringify(out))
}
run().catch((e) => { process.stderr.write(e.stack); process.exit(1) })
`
  try {
    const out = JSON.parse(execFileSync(process.execPath, ['-e', script], { env: { ...process.env, HOME: home, AGENTLINK_UPDATE: 'false', T: JSON.stringify({ manifest, oldManifest, pins }) }, encoding: 'utf8' }))
    assert.deepEqual(out.channels.map((c) => [c.repo, c.branch, c.launcher, c.manifest]), [
      ['AgentLink-FreeCAD', 'main', 'packaging/mcpb/server/index.js', 'packaging/addons.json'],
      ['ScanRuler', 'freecad-spike', 'scripts/freecad/mcpb/server/index.js', 'scripts/freecad/addons.json'],
    ])
    const want = JSON.parse(manifest).sources
    assert.equal(out.ok.repo, 'AgentLink-FreeCAD')
    assert.equal(out.ok.launcher, 'packaging/mcpb/server/index.js')
    assert.equal(out.ok.sha, 'a'.repeat(40))
    assert.deepEqual(out.ok.pins, want.map((s) => s.pin))
    assert.deepEqual(out.ok.shas, want.map((s) => pins[s.pin].trim()), 'the pins of the new channel')
    assert.ok(out.ok.companions, 'its companions come with it')
    const extra = JSON.parse(manifest).serverAddons || []
    assert.deepEqual(out.ok.addons, extra.map((a) => [a.dest, a.server]), 'the server add-ons come with it')
    assert.deepEqual(out.ok.addonShas, extra.map((a) => pins[a.pin].trim()), 'each at its pin')
    for (const k of ['noManifest', 'noPin', 'noHead']) {
      assert.equal(out[k].repo, 'ScanRuler', `${k}: falls back to ScanRuler`)
      assert.equal(out[k].launcher, 'scripts/freecad/mcpb/server/index.js')
      assert.equal(out[k].sha, 'b'.repeat(40))
      assert.deepEqual(out[k].pins, want.map((s) => s.pin.replace('packaging/pins/', 'scripts/bakeoff/')))
      assert.deepEqual(out[k].shas, want.map((s) => pins[s.pin].trim().replace(/^./, 'd')), `${k}: the old channel's own pins, not a mix`)
    }
    assert.match(out.none, /^no update channel could be read: AgentLink-FreeCAD: unreachable; ScanRuler: .*HTTP 404/)
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
  console.log('launcher channel: AgentLink-FreeCAD main with its pins; ScanRuler freecad-spike only when that cannot be read; an error when neither can')
}
async function launch(nodeArgs = () => [], again = null) {
  // again: a root from an earlier launch, started once more as it was left.
  const root = again || fs.mkdtempSync(path.join(os.tmpdir(), 'agentlink-launcher-'))
  const app = path.join(root, 'FreeCAD.app')
  const bin = path.join(app, 'Contents', 'Resources', 'bin')
  fs.mkdirSync(bin, { recursive: true })
  fs.mkdirSync(path.join(app, 'Contents', 'Resources', 'lib'), { recursive: true })
  const ud = path.join(root, 'userdata')
  // The real interpreter by its path: the launcher puts the fake's folder
  // first on PATH, as FreeCAD's bin is.
  const fresh = path.join(root, 'fresh')
  const ext = path.join(root, 'ext', 'server')
  // Left at the outer indent: the files below are written from template
  // literals whose indentation is their content.
  if (!again) {
  const realPython = execFileSync('python3', ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8' }).trim()
  const server = path.join(root, 'fake_server.py')
  // A fake FreeCAD Python: answers the user-folder question, else serves MCP,
  // its tools saying which add-ons version it found in the Mod folder.
  fs.writeFileSync(server, `
import json, os, sys
mod = os.path.join(${JSON.stringify(ud)}, 'Mod', 'AgentLink', 'VERSION')
ver = open(mod).read().strip() if os.path.exists(mod) else 'none'
for line in sys.stdin:
    m = json.loads(line)
    if 'id' not in m:
        continue
    if m.get('method') == 'initialize':
        r = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'fake', 'version': ver}}
    elif m.get('method') == 'tools/list':
        r = {'tools': [{'name': 'echo_' + ver.replace('.', '_'), 'inputSchema': {'type': 'object'}}]}
    elif m.get('params', {}).get('name') == 'crash':
        sys.exit(3)
    else:
        r = {'content': [{'type': 'text', 'text': ver}]}
    print(json.dumps({'jsonrpc': '2.0', 'id': m['id'], 'result': r}), flush=True)
  `)
  fs.writeFileSync(path.join(bin, 'python3'), `#!/bin/sh
if [ "$1" = "-c" ]; then printf '@@%s@@' ${JSON.stringify(ud)}; exit 0; fi
case "$1" in *smoke.py) exec ${JSON.stringify(realPython)} "$1";; esac
exec ${JSON.stringify(realPython)} ${JSON.stringify(server)}
`, { mode: 0o755 })
  // The add-ons an update brings.
  for (const n of ['AgentLink', 'ScanRulerFC']) fs.mkdirSync(path.join(fresh, n), { recursive: true })
  fs.writeFileSync(path.join(fresh, 'AgentLink', 'VERSION'), '2.0\n')
  fs.writeFileSync(path.join(fresh, 'VERSION'), '2.0\n')
  // And the launcher itself, as GitHub serves it: #! first line and all.
  fs.mkdirSync(path.join(fresh, 'launcher'), { recursive: true })
  fs.copyFileSync(path.join(here, '..', 'server', 'index.js'), path.join(fresh, 'launcher', 'index.js'))

  // The launcher as the extension holds it: its own folder, no package.json
  // saying ES module (this repository's does).
  fs.mkdirSync(ext, { recursive: true })
  fs.copyFileSync(path.join(here, '..', 'server', 'index.js'), path.join(ext, 'index.js'))
  fs.writeFileSync(path.join(root, 'ext', 'package.json'), '{"type": "commonjs"}\n')
  }
  const child = spawn(process.execPath, [...nodeArgs(root), path.join(ext, 'index.js')], {
    env: { ...process.env, HOME: root, FREECAD_APP: app, AGENTLINK_UPDATE: 'false', AGENTLINK_UPDATE_FROM: fresh, AGENTLINK_PORT: '1', AGENTLINK_OUT: path.join(root, 'out') },
    stdio: ['pipe', 'pipe', 'pipe'],
  })
  let errs = ''
  child.stderr.on('data', (d) => (errs += d))
  const waiting = new Map()
  const notes = []
  readline.createInterface({ input: child.stdout }).on('line', (line) => {
    const m = JSON.parse(line)
    if (m.id !== undefined && waiting.has(m.id)) {
      waiting.get(m.id)(m)
      waiting.delete(m.id)
    } else if (m.method) notes.push(m.method)
  })
  let n = 0
  function call(method, params = {}) {
    const id = ++n
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n')
    return new Promise((resolve, reject) => {
      waiting.set(id, resolve)
      setTimeout(() => reject(new Error(`${method} timed out\n${errs}`)), 20000)
    })
  }
  const tool = (name) => call('tools/call', { name, arguments: {} })
  return { root, ud, fresh, child, call, tool, notes, errs: () => errs }
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

{
  const { root, ud, fresh, child, call, tool, notes, errs } = await launch()
try {
  const init = await call('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 't', version: '1' } })
  assert.equal(init.result.capabilities.tools.listChanged, true, 'the launcher says the tool list may change')
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n')
  let list = await call('tools/list')
  let names = list.result.tools.map((t) => t.name)
  assert.ok(names.includes('agentlink_update'), names.join())
  assert.ok(names.includes('echo_none'), names.join())
  // A crash is answered and FreeCAD comes back.
  const crash = await tool('crash')
  assert.equal(crash.result.isError, true)
  assert.match(crash.result.content[0].text, /started again/)
  await wait(300)
  assert.equal((await tool('anything')).result.content[0].text, 'none')
  // The update: installed into the Mod folder, FreeCAD started again on it.
  const up = await tool('agentlink_update')
  const said = JSON.parse(up.result.content[0].text)
  assert.equal(up.result.isError, false, JSON.stringify(said))
  assert.equal(said.after, 'local+2.0')
  assert.equal(said.restarted, true)
  const kept = path.join(root, '.config', 'freecad-agentlink', 'launcher')
  assert.ok(fs.existsSync(path.join(kept, 'index.js')), 'the launcher was kept for the next start')
  assert.ok(fs.existsSync(path.join(kept, 'package.json')))
  await wait(500)
  assert.ok(notes.includes('notifications/tools/list_changed'), notes.join())
  list = await call('tools/list')
  names = list.result.tools.map((t) => t.name)
  assert.ok(names.includes('echo_2_0'), names.join())
  assert.equal((await tool('anything')).result.content[0].text, '2.0')
  // Again: nothing new, nothing restarted.
  const again = JSON.parse((await tool('agentlink_update')).result.content[0].text)
  assert.equal(again.restarted, false)
  // An update whose smoke test fails: refused, the add-ons in place put
  // back, nothing restarted, the broken ones kept for a look.
  fs.writeFileSync(path.join(fresh, 'VERSION'), '3.0\n')
  fs.writeFileSync(path.join(fresh, 'AgentLink', 'VERSION'), '3.0\n')
  fs.mkdirSync(path.join(fresh, 'AgentLink', 'agentlink'), { recursive: true })
  fs.writeFileSync(path.join(fresh, 'AgentLink', 'agentlink', 'smoke.py'), 'import json\nprint(json.dumps({"ok": False, "failures": ["family cut fails to load"]}))\n')
  const bad = await tool('agentlink_update')
  assert.equal(bad.result.isError, true)
  assert.match(bad.result.content[0].text, /failed the smoke test/)
  assert.equal(fs.readFileSync(path.join(ud, 'Mod', 'AgentLink', 'VERSION'), 'utf8').trim(), '2.0')
  assert.equal((await tool('anything')).result.content[0].text, '2.0')
  const hist = JSON.parse(fs.readFileSync(path.join(root, 'AgentLink', 'versions.json'), 'utf8')).history
  assert.match(hist[hist.length - 1].outcome, /rolled back/)
  // An update whose smoke test passes with an installed add-on left out
  // (one that did not load before either): installed, and the answer says
  // which add-on, its error, the tool groups gone and a plain warning. The
  // smoke test is told which add-ons loaded before.
  fs.writeFileSync(path.join(root, 'AgentLink', 'extensions.json'), JSON.stringify({ hidden: { loaded: [{ extension: 'good.agentlink_families', groups: ['good'], tools: 4 }, { extension: 'bad name;rm', groups: [], tools: 1 }], leftOut: [], groups: { core: 3, good: 4, scan: 133 } } }))
  fs.writeFileSync(path.join(fresh, 'VERSION'), '3.5\n')
  fs.writeFileSync(path.join(fresh, 'AgentLink', 'VERSION'), '3.5\n')
  const envSeen = path.join(root, 'smoke-env.txt')
  fs.writeFileSync(path.join(fresh, 'AgentLink', 'agentlink', 'smoke.py'), `import json, os\nopen(${JSON.stringify(envSeen)}, 'w').write(os.environ.get('AGENTLINK_LOADED_BEFORE', '<none>'))\nprint(json.dumps({"ok": True, "failures": [], "extensions": {"loaded": ["good.agentlink_families"], "leftOut": [{"extension": "scan.agentlink_families", "error": "SyntaxError: invalid syntax (agentlink_families.py, line 12)"}]}, "groups": {"core": 3, "good": 4}}))\n`)
  const warned = await tool('agentlink_update')
  const warnedSaid = JSON.parse(warned.result.content[0].text)
  assert.equal(warned.result.isError, false, JSON.stringify(warnedSaid))
  assert.equal(warnedSaid.after, 'local+3.5')
  assert.deepEqual(warnedSaid.leftOut, [{ extension: 'scan.agentlink_families', error: 'SyntaxError: invalid syntax (agentlink_families.py, line 12)' }])
  assert.deepEqual(warnedSaid.lostGroups, ['scan'])
  assert.match(warnedSaid.warning, /did not load.*scan\./)
  assert.match(warnedSaid.note, /WARNING: .*did not load/, 'the note itself carries the warning')
  assert.equal(fs.readFileSync(envSeen, 'utf8'), 'good.agentlink_families', 'the smoke test is told what loaded before (plain module names only)')
  const hist2 = JSON.parse(fs.readFileSync(path.join(root, 'AgentLink', 'versions.json'), 'utf8')).history
  assert.match(hist2[hist2.length - 1].outcome, /left out: scan\.agentlink_families/)
  await wait(500)
  // Nothing new, and the running FreeCAD's own record names one left out:
  // "already the newest" still says so.
  fs.writeFileSync(path.join(root, 'AgentLink', 'extensions.json'), JSON.stringify({ hidden: { loaded: [], leftOut: [{ extension: 'scan.agentlink_families', error: 'SyntaxError: x' }], groups: { core: 3 } } }))
  const same = JSON.parse((await tool('agentlink_update')).result.content[0].text)
  assert.equal(same.restarted, false)
  assert.equal(same.leftOut[0].extension, 'scan.agentlink_families')
  assert.match(same.note, /Already the newest.*WARNING/)
  fs.rmSync(path.join(root, 'AgentLink', 'extensions.json'))
  // An update that brings a new add-on folder and a newer launcher: the
  // folder installed and written down as ours, and the new launcher takes
  // over this same connection (no restart of Claude).
  fs.rmSync(path.join(fresh, 'AgentLink', 'agentlink'), { recursive: true, force: true })
  fs.writeFileSync(path.join(fresh, 'VERSION'), '4.0\n')
  fs.writeFileSync(path.join(fresh, 'AgentLink', 'VERSION'), '4.0\n')
  fs.mkdirSync(path.join(fresh, 'Extra'), { recursive: true })
  fs.writeFileSync(path.join(fresh, 'Extra', 'marker'), 'x\n')
  const newer = fs.readFileSync(path.join(here, '..', 'server', 'index.js'), 'utf8').replace("description: 'Fetch the newest", "description: 'NEWER Fetch the newest")
  assert.ok(newer.includes('NEWER'))
  fs.writeFileSync(path.join(fresh, 'launcher', 'index.js'), newer)
  // Add-ons now inside Workshop, left in Mod from before: set aside (their
  // package.xml says they are ours); a folder of the same name that is not
  // ours stays.
  const leftover = (dir, name) => {
    fs.mkdirSync(path.join(ud, 'Mod', dir), { recursive: true })
    fs.writeFileSync(path.join(ud, 'Mod', dir, 'package.xml'), `<package format="1"><name>${name}</name></package>\n`)
  }
  leftover('WorkshopMake', 'Workshop Make')
  leftover('SafetyNet', 'SafetyNet')
  leftover('WorkshopParts', 'Someone else\'s parts')
  const hand = await tool('agentlink_update')
  const handSaid = JSON.parse(hand.result.content[0].text)
  assert.equal(hand.result.isError, false, JSON.stringify(handSaid))
  assert.match(handSaid.launcher || '', /new launcher/)
  assert.ok(fs.existsSync(path.join(ud, 'Mod', 'Extra', 'marker')), 'the new add-on folder is installed')
  assert.ok(JSON.parse(fs.readFileSync(path.join(ud, 'Mod', 'AgentLink', '.installed-names'), 'utf8')).includes('Extra'))
  assert.ok(!fs.existsSync(path.join(ud, 'Mod', 'WorkshopMake')), 'a retired Workshop folder is set aside')
  assert.ok(!fs.existsSync(path.join(ud, 'Mod', 'SafetyNet')), 'a retired SafetyNet is set aside')
  assert.ok(fs.existsSync(path.join(ud, 'Mod', 'WorkshopParts')), 'a folder that is not ours stays')
  await wait(1500)
  list = await call('tools/list')
  const upd = list.result.tools.find((t) => t.name === 'agentlink_update')
  assert.match(upd.description, /^NEWER/, 'the new launcher serves')
  assert.equal((await tool('anything')).result.content[0].text, '4.0')
  // A retired add-on left by an older launcher's install: the next update
  // sweeps it even with nothing new, and FreeCAD starts again without it.
  leftover('SafetyNet', 'SafetyNet')
  const swept = JSON.parse((await tool('agentlink_update')).result.content[0].text)
  assert.deepEqual(swept.retired, ['SafetyNet'], JSON.stringify(swept))
  assert.equal(swept.restarted, true)
  assert.ok(!fs.existsSync(path.join(ud, 'Mod', 'SafetyNet')), 'swept on an update with nothing new')
  await wait(500)
  assert.equal((await tool('anything')).result.content[0].text, '4.0')
  const quiet = JSON.parse((await tool('agentlink_update')).result.content[0].text)
  assert.equal(quiet.restarted, false, 'nothing left to sweep: nothing restarted')
  leftover('WorkshopElectronics', 'Workshop Electronics')
  const late = JSON.parse((await tool('agentlink_update')).result.content[0].text)
  assert.equal(late.before, late.after, JSON.stringify(late))
  assert.deepEqual(late.retired, ['WorkshopElectronics'], JSON.stringify(late))
  assert.equal(late.restarted, true)
  assert.match(late.note, /Already the newest; set aside/)
  await wait(500)
  assert.equal((await tool('anything')).result.content[0].text, '4.0')
  // And at the next start, with the add-ons already in place.
  leftover('WorkshopDocuments', 'Workshop Documents')
  child.stdin.end()
  child.kill()
  await wait(500)
  const second = await launch(() => [], root)
  try {
    await second.call('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 't', version: '1' } })
    assert.ok(!fs.existsSync(path.join(ud, 'Mod', 'WorkshopDocuments')), 'swept at the next start')
    assert.ok(fs.existsSync(path.join(ud, 'Mod', 'WorkshopParts')), 'still not ours: stays')
    assert.equal(fs.readFileSync(path.join(ud, 'Mod', 'AgentLink', 'VERSION'), 'utf8').trim(), '4.0')
  } finally {
    second.child.stdin.end()
    second.child.kill()
  }
  console.log('launcher: serves, restarts a crash, updates without dropping the connection, rolls back a failed update, installs a new add-on, sets aside retired ones (at install, at an update with nothing new, at the next start), hands over to a newer launcher; its built-in lists are addons.json\'s')
} finally {
  child.stdin.end()
  child.kill()
  fs.rmSync(root, { recursive: true, force: true })
}
}

// Claude Desktop's built-in Node: Electron's helper, which refuses to start
// Node as a subprocess. The handover still happens, in the same process, and
// a newer launcher that cannot take over leaves this one serving.
{
  const refused = 'The built-in Node.js runtime cannot start "Claude Helper (Plugin)" as a Node.js subprocess (child_process.fork or process.execPath). Install Node.js and turn off "Use built-in Node.js for MCP" in Settings > Extensions > Advanced settings, or avoid spawning Node from this server.'
  const { root, ud, fresh, child, call, tool, errs } = await launch((dir) => {
    const pre = path.join(dir, 'electron.cjs')
    fs.writeFileSync(pre, `
Object.defineProperty(process.versions, 'electron', { value: '45.2.1', enumerable: true })
const cp = require('child_process')
const refused = ${JSON.stringify(refused)}
const spawn = cp.spawn
cp.fork = () => { throw new Error(refused) }
cp.spawn = (cmd, ...rest) => { if (cmd === process.execPath) throw new Error(refused); return spawn(cmd, ...rest) }
`)
    return ['--require', pre]
  })
  const desc = async () => (await call('tools/list')).result.tools.find((t) => t.name === 'agentlink_update').description
  const bump = (v, launcher) => {
    fs.writeFileSync(path.join(fresh, 'VERSION'), `${v}\n`)
    fs.writeFileSync(path.join(fresh, 'AgentLink', 'VERSION'), `${v}\n`)
    fs.writeFileSync(path.join(fresh, 'launcher', 'index.js'), launcher)
  }
  const own = fs.readFileSync(path.join(here, '..', 'server', 'index.js'), 'utf8')
  try {
    await call('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 't', version: '1' } })
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n')
    assert.doesNotMatch(await desc(), /^NEWER/)
    // A newer launcher that throws as it loads: this one keeps serving, on
    // the new add-ons.
    bump('2.0', `const LAUNCHER_STAMP = 99999999\n// startHandedOver\nthrow new Error('broken on purpose')\n`)
    let said = JSON.parse((await tool('agentlink_update')).result.content[0].text)
    assert.equal(said.after, 'local+2.0', JSON.stringify(said))
    assert.match(said.launcher || '', /^kept/)
    await wait(500)
    assert.equal((await tool('anything')).result.content[0].text, '2.0')
    assert.doesNotMatch(await desc(), /^NEWER/)
    assert.match(errs(), /broken on purpose\); this one keeps serving/)
    // One that loads but fails to start: this one serves again.
    bump('3.0', `const LAUNCHER_STAMP = 99999999\nmodule.exports = { startHandedOver: async () => { throw new Error('cannot start on purpose') } }\n`)
    said = JSON.parse((await tool('agentlink_update')).result.content[0].text)
    assert.equal(said.after, 'local+3.0', JSON.stringify(said))
    await wait(800)
    assert.equal((await tool('anything')).result.content[0].text, '3.0')
    assert.doesNotMatch(await desc(), /^NEWER/)
    assert.match(errs(), /cannot start on purpose\); this one keeps serving/)
    // A good newer launcher: it takes over in this process.
    bump('4.0', own.replace("description: 'Fetch the newest", "description: 'NEWER Fetch the newest"))
    said = JSON.parse((await tool('agentlink_update')).result.content[0].text)
    assert.match(said.launcher || '', /new launcher/, JSON.stringify(said))
    await wait(1500)
    assert.match(await desc(), /^NEWER/, 'the new launcher serves')
    assert.equal((await tool('anything')).result.content[0].text, '4.0')
    assert.equal((await tool('anything')).result.content[0].text, '4.0')
    assert.match(errs(), /handed over to the updated launcher in this process .*\(electron 45\.2\.1\)/)
    assert.doesNotMatch(errs(), /cannot start "Claude Helper/)
    assert.equal(child.exitCode, null, 'still the same process')
    console.log('launcher under Claude\'s built-in Node: hands over in-process without spawning Node; a broken newer launcher leaves the old one serving')
  } finally {
    child.stdin.end()
    child.kill()
    fs.rmSync(root, { recursive: true, force: true })
  }
}
