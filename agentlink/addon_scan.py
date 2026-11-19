# SPDX-License-Identifier: LGPL-2.1-or-later
"""The static scan of an add-on: what its code can reach, read with ast.

It never imports and never runs the add-on's code. It reads each .py file
of the add-on's folder and flags the calls that reach past the document:

    network        sockets, urllib, http, requests and similar
    subprocess     subprocess, os.system, os.popen, os.exec*, pty
    dynamic_code   eval, exec, compile, __import__, a dynamic import,
                   pickle or marshal loads, ctypes, cffi
    obfuscation    a decode of base64, hex or rot13 near a dynamic call,
                   or a very long string literal
    credentials    words of key stores and secrets: .ssh, .aws, keychain,
                   .netrc, id_rsa, a cookies file
    environment    reads of os.environ or os.getenv
    sys_path       changes to sys.path or site folders
    file_write     open for write, remove, rename, shutil, Path.write_*
    file_write_out a write to an absolute path or a home path
    other_documents FreeCAD.listDocuments, openDocument, getDocument
    settings       FreeCAD.ParamGet(...).Set*, Remove*

The flags go into the person's OK (cookbook_approve) as words: "this add-on
calls the network". A flag is not a refusal: add-on code already runs with
the person's rights. The flags help the person decide.

risk(flags) gives the risk of an entry: "code" (it can reach the Mac past
the document), "file" (it reads or writes files or settings) or "none".

Plain Python: no FreeCAD, no other Agent Link module.
"""
import ast
import os
import re

MAX_FILES = 400
MAX_FILE_BYTES = 1024 * 1024
MAX_WALK = 50000
LONG_STRING = 4000
# Only Python's own cache is left out. Every other folder is read, hidden
# ones and build, dist or node_modules too: Python can import from each
# (red team 2, R2-11).
SKIP_DIRS = {"__pycache__"}
# Compiled code: it can be imported, and the scan cannot read it.
COMPILED = (".so", ".pyd", ".dylib", ".pyc", ".pyo")

CODE_KINDS = ("network", "subprocess", "dynamic_code", "obfuscation", "credentials", "environment", "sys_path")
FILE_KINDS = ("file_write", "file_write_out", "other_documents", "settings")
KINDS = CODE_KINDS + FILE_KINDS

WORDS = {
    "network": "This add-on calls the network.",
    "subprocess": "This add-on starts other programs.",
    "dynamic_code": "This add-on runs code that it makes or loads at run time.",
    "obfuscation": "This add-on has hidden or encoded code.",
    "credentials": "This add-on names key stores or secret files.",
    "environment": "This add-on reads the environment variables.",
    "sys_path": "This add-on changes where Python finds modules.",
    "file_write": "This add-on writes or removes files.",
    "file_write_out": "This add-on writes to a fixed path outside the document folder.",
    "other_documents": "This add-on reads other open documents.",
    "settings": "This add-on changes FreeCAD settings.",
}

NET_MODULES = {"socket", "ssl", "urllib", "urllib2", "urllib3", "http", "httplib", "requests", "httpx", "aiohttp", "ftplib", "smtplib",
               "poplib", "imaplib", "telnetlib", "websocket", "websockets", "paramiko", "xmlrpc", "asyncio.open_connection", "socketserver",
               "QtNetwork", "PySide.QtNetwork", "PySide2.QtNetwork", "PySide6.QtNetwork", "webbrowser"}
PROC_MODULES = {"subprocess", "pty", "multiprocessing", "pexpect", "sh", "plumbum"}
DYN_MODULES = {"ctypes", "cffi", "marshal", "pickle", "cPickle", "dill", "shelve", "importlib", "imp", "runpy", "code", "codeop", "zipimport"}
PROC_CALLS = {"os.system", "os.popen", "os.spawnl", "os.spawnv", "os.spawnve", "os.spawnlp", "os.spawnvp", "os.execv", "os.execve", "os.execl",
              "os.execlp", "os.execvp", "os.fork", "os.forkpty", "os.posix_spawn", "os.startfile", "QProcess", "QtCore.QProcess"}
DYN_CALLS = {"eval", "exec", "compile", "__import__", "importlib.import_module", "importlib.__import__", "runpy.run_path", "runpy.run_module",
             "pickle.loads", "pickle.load", "marshal.loads", "marshal.load", "execfile", "Gui.doCommand", "FreeCADGui.doCommand",
             "Gui.doCommandGui", "FreeCADGui.doCommandGui", "FreeCADGui.runCommand_macro", "types.FunctionType", "types.CodeType"}
DECODE_CALLS = {"base64.b64decode", "base64.b32decode", "base64.a85decode", "base64.decodebytes", "binascii.unhexlify", "bytes.fromhex",
                "codecs.decode", "zlib.decompress", "lzma.decompress", "bz2.decompress"}
WRITE_CALLS = {"os.remove", "os.unlink", "os.rename", "os.replace", "os.rmdir", "os.removedirs", "os.makedirs", "os.mkdir", "os.chmod",
               "os.symlink", "os.link", "os.truncate", "shutil.rmtree", "shutil.move", "shutil.copy", "shutil.copy2", "shutil.copyfile",
               "shutil.copytree", "write_text", "write_bytes", "unlink", "rmdir", "touch", "mkdir", "rename", "replace", "symlink_to"}
DOC_CALLS = {"listDocuments", "openDocument", "getDocument", "loadFile"}
SECRET_WORDS = re.compile(r"(\.ssh\b|id_rsa|id_ed25519|\.aws\b|\.netrc|keychain|\.gnupg|cookies\.sqlite|Cookies\b|login\.keychain|"
                          r"\.config/gh|\.docker/config|credentials\.json|security find-(generic|internet)-password|\.git-credentials|"
                          r"Library/Keychains|\.kube/config|\.pypirc|wallet\.dat)", re.I)
HOME_PATH = re.compile(r"^(~|/Users/|/home/|/root\b|[A-Za-z]:\\\\Users\\\\)")


def dotted(node):
    """a.b.c of a Name/Attribute chain, or "" (a call's result gives "")."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    if isinstance(node, ast.Call):
        inner = dotted(node.func)
        if inner:
            parts.append(inner + "()")
            return ".".join(reversed(parts))
    return ""


def _open_mode(call):
    mode = None
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        mode = call.args[1].value
    for k in call.keywords:
        if k.arg == "mode" and isinstance(k.value, ast.Constant):
            mode = k.value.value
    if mode is None and (len(call.args) >= 2 or any(k.arg == "mode" for k in call.keywords)):
        return "?"
    return mode if isinstance(mode, str) else "r"


def _literal_path(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call) and dotted(node.func) in ("os.path.expanduser", "os.path.join", "Path", "pathlib.Path") and node.args:
        return _literal_path(node.args[0])
    return None


def scan_source(src, rel="<file>"):
    """Flags of one file's text: [{kind, file, line, what}]."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError) as e:
        return [{"kind": "dynamic_code", "file": rel, "line": getattr(e, "lineno", 0) or 0, "what": "the file does not parse, so it was not read"}]
    out = []
    aliases = {}

    def flag(kind, node, what):
        out.append({"kind": kind, "file": rel, "line": getattr(node, "lineno", 0), "what": str(what)[:120]})

    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                aliases[a.asname or a.name.split(".")[0]] = a.name
                _module_flag(a.name, n, flag)
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            for a in n.names:
                aliases[a.asname or a.name] = f"{mod}.{a.name}" if mod else a.name
                _module_flag(f"{mod}.{a.name}" if mod else a.name, n, flag)
            _module_flag(mod, n, flag)
    decodes = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, (str, bytes)):
            v = n.value if isinstance(n.value, str) else n.value.decode("latin-1")
            if len(v) > LONG_STRING:
                flag("obfuscation", n, f"a string of {len(v)} characters")
            m = SECRET_WORDS.search(v)
            if m:
                flag("credentials", n, f"names {m.group(0)}")
        if isinstance(n, (ast.Attribute, ast.Name)):
            d = _resolve(dotted(n), aliases)
            if d in ("os.environ", "os.environb"):
                flag("environment", n, d)
            elif d in ("sys.path", "sys.meta_path", "sys.path_hooks", "site.addsitedir"):
                flag("sys_path", n, d)  # a read too: rare in an add-on, and cheap to show
        if not isinstance(n, ast.Call):
            continue
        name = _resolve(dotted(n.func), aliases)
        last = name.rsplit(".", 1)[-1] if name else (n.func.attr if isinstance(n.func, ast.Attribute) else "")
        if name in PROC_CALLS or last == "QProcess" or name.startswith("subprocess."):
            flag("subprocess", n, name or last)
        if name in DYN_CALLS or last in ("eval", "exec") and name in ("eval", "exec", "builtins.eval", "builtins.exec"):
            flag("dynamic_code", n, name)
        if name.startswith(("ctypes.", "cffi.")):
            flag("dynamic_code", n, name)
        if name in DECODE_CALLS:
            decodes.add(n.lineno)
        if name in ("os.getenv", "os.putenv", "os.environ.get"):
            flag("environment", n, name)
        if name.startswith(("socket.", "urllib.", "http.", "requests.", "httpx.", "ftplib.", "smtplib.", "webbrowser.", "ssl.")):
            flag("network", n, name)
        if name in ("open", "io.open", "codecs.open", "builtins.open") or last == "open" and isinstance(n.func, ast.Attribute) and dotted(n.func.value).endswith("Path"):
            mode = _open_mode(n)
            if mode == "?" or any(c in mode for c in "wax+"):
                p = _literal_path(n.args[0]) if n.args else None
                if p and (os.path.isabs(p) or HOME_PATH.match(p)):
                    flag("file_write_out", n, f"open({p[:60]!r}, {mode!r})")
                else:
                    flag("file_write", n, f"open(…, {mode!r})")
        elif name in WRITE_CALLS or last in WRITE_CALLS and isinstance(n.func, ast.Attribute) and last in ("write_text", "write_bytes", "unlink",
                                                                                                           "rmdir", "touch", "symlink_to"):
            p = _literal_path(n.args[0]) if n.args else None
            if p and (os.path.isabs(p) or HOME_PATH.match(p)):
                flag("file_write_out", n, f"{name or last}({p[:60]!r})")
            else:
                flag("file_write", n, name or last)
        if last in DOC_CALLS and name.split(".")[0] in ("FreeCAD", "App", "FreeCADGui", "Gui", "") or name in ("FreeCAD.listDocuments", "App.listDocuments"):
            flag("other_documents", n, name or last)
        if re.search(r"ParamGet\(\)\.(Set|Remove|Clear)", name or "") or (isinstance(n.func, ast.Attribute) and re.match(r"^(Set|Remove)(Bool|Int|Float|String|Unsigned|Group)", last or "")
                                                                         and "ParamGet" in dotted(n.func.value)):
            flag("settings", n, last)
    if decodes and any(f["kind"] == "dynamic_code" for f in out):
        flag("obfuscation", ast.Constant(value="", lineno=min(decodes)), "an encoded text and a dynamic call in one file")
    return out


def _resolve(name, aliases):
    if not name:
        return ""
    head, _, rest = name.partition(".")
    if head in aliases:
        return aliases[head] + ("." + rest if rest else "")
    return name


def _module_flag(mod, node, flag):
    if not mod:
        return
    top = mod.split(".")[0]
    if mod in NET_MODULES or top in NET_MODULES or mod.endswith("QtNetwork"):
        flag("network", node, f"import {mod}")
    elif top in PROC_MODULES:
        flag("subprocess", node, f"import {mod}")
    elif top in DYN_MODULES:
        flag("dynamic_code", node, f"import {mod}")
    elif mod in ("os.system", "os.popen") or mod.startswith("os.exec") or mod.startswith("os.spawn"):
        flag("subprocess", node, f"import {mod}")
    elif mod in ("builtins.eval", "builtins.exec"):
        flag("dynamic_code", node, f"import {mod}")


def walk(folder):
    """(py files, compiled files, more): every .py file under the folder,
    hidden folders and linked files and folders too (each real folder once),
    and the compiled code files. more: True when the walk stopped at a cap."""
    py, compiled, seen, n = [], [], set(), 0
    for root, dirs, files in os.walk(folder, followlinks=True):
        real = os.path.realpath(root)
        if real in seen:
            dirs[:] = []
            continue
        seen.add(real)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            n += 1
            if n > MAX_WALK:
                return py, compiled, True
            if f.endswith(".py"):
                py.append(os.path.join(root, f))
            elif f.endswith(COMPILED):
                compiled.append(os.path.join(root, f))
    return py, compiled, False


def py_files(folder):
    return walk(folder)[0][:MAX_FILES]


def scan(folder, cache_dir=None, package=None):
    """{ files, flags [{kind, file, line, what}], counts {kind: n}, words
    [one line for each kind found], unread [why], risk } of an add-on
    folder. From the index (cached by the bytes of its code files). What is
    not read counts as code: a file not read, compiled code, and a module of
    the package that a file imports but that is not in the folder."""
    ix = index(folder, cache_dir)
    flags = [f for row in ix["files"].values() for f in row["flags"]] + list(ix.get("blind") or [])
    if package:
        mods = ix["modules"]
        for rel, row in ix["files"].items():
            for i in row["imports"]:
                if i.startswith(package + ".") and i not in mods and i.rsplit(".", 1)[0] not in mods:
                    flags.append({"kind": "dynamic_code", "file": rel, "line": 0, "what": f"imports {i[:80]}, which is not in the add-on folder, so it was not read"})
    return summary(flags, len(ix["files"]), ix["unread"])


# ---- the index: one read of the add-on, kept by its fingerprint (live 96) -------------------

_MEMO = {}
CMD_LIKE = re.compile(r"^[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+$")


def fingerprint(folder):
    """SHA-256 of each code file's path and bytes (.py and compiled), and
    the package.xml bytes. A change of the bytes is a new scan, whatever
    the size or the time say (R2-11)."""
    import hashlib

    h = hashlib.sha256()
    py, compiled, more = walk(folder)
    for p in py[:MAX_FILES] + compiled[:MAX_FILES]:
        h.update(os.path.relpath(p, folder).encode("utf-8", "replace") + b"\0")
        try:
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
        except OSError:
            h.update(b"unreadable")
        h.update(b"\n")
    h.update(f"{len(py)}:{len(compiled)}:{more}".encode())
    try:
        with open(os.path.join(folder, "package.xml"), "rb") as f:
            h.update(f.read(512 * 1024))
    except OSError:
        pass
    return h.hexdigest()


def _module_of(rel):
    m = rel[:-3].replace(os.sep, ".")
    return m[:-9] if m.endswith(".__init__") else m


def index(folder, cache_dir=None):
    """{ fingerprint, files {rel: {module, flags, imports}}, modules {module:
    rel}, commands {name: rel}, unread }. Kept in memory and, with
    cache_dir, on disk; read again only when the fingerprint changes."""
    import hashlib
    import json

    folder = os.path.realpath(folder)
    fp = fingerprint(folder)
    got = _MEMO.get(folder)
    if got and got["fingerprint"] == fp:
        return got
    disk = os.path.join(cache_dir, hashlib.sha256(folder.encode()).hexdigest()[:32] + ".json") if cache_dir else None
    if disk:
        try:
            with open(disk, encoding="utf-8") as f:
                got = json.load(f)
            if isinstance(got, dict) and got.get("fingerprint") == fp and got.get("folder") == folder and got.get("v") == 2:
                _MEMO[folder] = got
                return got
        except (OSError, ValueError):
            pass
    files, modules, commands, unread, blind = {}, {}, {}, [], []
    base = os.path.basename(folder)
    allpy, compiled, more = walk(folder)
    paths = allpy[:MAX_FILES]
    for p in compiled[:40]:
        rel = os.path.relpath(p, folder)
        blind.append({"kind": "dynamic_code", "file": rel, "line": 0, "what": "compiled code: the scan cannot read it"})
    if len(compiled) > 40:
        blind.append({"kind": "dynamic_code", "file": "", "line": 0, "what": f"{len(compiled) - 40} more compiled files"})
    for p in paths:
        rel = os.path.relpath(p, folder)
        try:
            if os.path.getsize(p) > MAX_FILE_BYTES:
                unread.append(f"{rel}: larger than 1 MB, not read")
                files[rel] = {"module": _module_of(rel), "flags": [{"kind": "obfuscation", "file": rel, "line": 0, "what": "a file larger than 1 MB"}],
                              "imports": []}
                continue
            with open(p, encoding="utf-8", errors="replace") as f:
                src = f.read()
        except OSError as e:
            unread.append(f"{rel}: cannot read it ({e.strerror or e})")
            blind.append({"kind": "dynamic_code", "file": rel, "line": 0, "what": "the file cannot be read, so it was not scanned"})
            continue
        mod = _module_of(rel)
        files[rel] = {"module": mod, "flags": scan_source(src, rel), "imports": sorted(_imports_src(src, mod, rel.endswith("__init__.py")))}
        modules.setdefault(mod, rel)
        modules.setdefault(f"{base}.{mod}", rel)
        if "addCommand" in src:
            for c in set(re.findall(r"['\"]([A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+)['\"]", src)):
                commands.setdefault(c, rel)
    if len(allpy) > MAX_FILES or more:
        unread.append(f"more than {MAX_FILES} Python files or {MAX_WALK} files: the rest is not read")
        blind.append({"kind": "dynamic_code", "file": "", "line": 0, "what": "the add-on has more files than the scan reads"})
    got = {"v": 2, "folder": folder, "fingerprint": fp, "files": files, "modules": modules, "commands": commands, "unread": unread, "blind": blind}
    _MEMO[folder] = got
    if disk:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            tmp = disk + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(got, f)
            os.replace(tmp, disk)
        except OSError:
            pass
    return got


def _imports_src(src, module, is_init):
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return set()
    out = set()
    pkg_parts = module.split(".") if is_init else module.split(".")[:-1]
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                base = pkg_parts[:len(pkg_parts) - n.level + 1] if n.level > 1 else pkg_parts
                mod = ".".join(base + ([n.module] if n.module else []))
            else:
                mod = n.module or ""
            if mod:
                out.add(mod)
                out |= {f"{mod}.{a.name}" for a in n.names}
    return out


def summary(flags, files=0, unread=()):
    counts = {}
    for f in flags:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    words = [WORDS[k] + f" ({counts[k]} places)" for k in KINDS if k in counts]
    return {"files": files, "flags": flags[:200], "counts": counts, "words": words, "unread": list(unread)[:20], "risk": risk(counts)}


def risk(counts_or_flags):
    """none | file | code, from the kinds found (the worst one wins)."""
    kinds = set(counts_or_flags) if isinstance(counts_or_flags, dict) else {f["kind"] for f in counts_or_flags}
    if kinds & set(CODE_KINDS):
        return "code"
    if kinds & set(FILE_KINDS):
        return "file"
    return "none"


# ---- the modules a call can reach ------------------------------------------------------------

def reach(folder, package, module, limit=200, cache_dir=None):
    """The flags of module and of each module of the package it imports, on
    and on (the add-on's own import closure), from the index. A module not
    found in the folder gives a dynamic_code flag: what cannot be read
    counts as code."""
    ix = index(folder, cache_dir)
    seen, todo, flags = set(), [module], []
    while todo and len(seen) < limit:
        m = todo.pop()
        if m in seen:
            continue
        seen.add(m)
        rel = ix["modules"].get(m)
        if rel is None:
            if m == module:
                flags.append({"kind": "dynamic_code", "file": m, "line": 0, "what": "the module is not in the add-on folder, so it was not read"})
            continue
        row = ix["files"][rel]
        flags += row["flags"]
        todo += sorted(i for i in row["imports"] if (i == package or i.startswith(package + ".")) and i not in seen)
    return flags


def command_file(folder, cmd, cache_dir=None):
    """The file (rel) that names cmd where it registers commands, or None."""
    return index(folder, cache_dir)["commands"].get(cmd)
