# SPDX-License-Identifier: LGPL-2.1-or-later
"""The person's approvals through the client's own tool permissions.

The owner's decision (18 Nov 2026, docs/security/red-team-2026-11-18.md):
an approval is a call of one of two small tools, and the person sets each
of them in the client's tool permissions (Claude Desktop: "always allow",
"ask first" or "block"):

  approve_file  a file-level step: answer a file dialog (dialog_answer on
                FreeCAD's close confirm or a "replace the file" box),
                accept a recovered copy (an add-on's recovery), save every
                changed document at a restart (app_restart save: "all").
  approve_code  running or installing code: a cookbook, a macro, an add-on
                install, update or removal, an extension.

With "ask first", the client asks the person before each call, so an agent
cannot approve alone. With "always allow", the person chose to let the
agent approve (headless use).

The tool that needs an approval never gives it. ask() answers "pending"
with the exact approve_file or approve_code arguments; the agent calls that
tool; then the first tool, called again, acts. An approval is for one
kind, one id and one fingerprint (a commit, a file hash, a folder's
fingerprint): a new version needs a new approval.

  ask(kind, name, title, lines, fingerprint=None, on_ok=None, shown=None)
      A grant waits for (kind, name, fingerprint): it is used up, and the
      answer is {"ok": True}. Else the request is kept and the answer is
      {"pending": True, "approve": {"tool", "arguments"}, "next"}.
      on_ok: called at the approval for an approval that is kept (a
      cookbook's or a macro's hash in its store). Without it, the approval
      is a grant for one action that the next call uses up (TTL s).
      shown: the facts the person must see in the client's prompt, as
      arguments of the approve tool (source, version, author; document,
      file, button).

  approve(tool, args)
      The handler of approve_file and approve_code. It answers only a call
      that came straight from the MCP client (protocol.Server.handle marks
      it, client_call below): a batch, a job, a cookbook, a lesson or a
      panel never reach it. The arguments must be the ones the pending
      answer gave, word for word: what the client showed the person is
      what is approved.

The FreeCAD window's Approve dialog (agentlink/person_ok.py) is an
optional extra path: a person's press there gives the same approval.
"""
import hashlib
import json
import os
import threading
import time
import unicodedata
from urllib.parse import urlsplit

FILE_TOOL = "approve_file"
CODE_TOOL = "approve_code"
CLIENT_ONLY = (FILE_TOOL, CODE_TOOL)
# Kinds approved with approve_file; every other kind is approve_code's.
FILE_KINDS = {"dialog", "recover", "save-all"}
# The kinds of approval: every other kind is refused (red team 2, R2-9).
# "gcode": G-code that an add-on sends to a printer or writes for one
# (agentlink-orcaslicer asks it before it starts a print).
CODE_KINDS = {"cookbook", "macro", "extension", "addon-install", "addon-update", "addon-remove", "addon-uninstall", "gcode"}
KINDS = FILE_KINDS | CODE_KINDS
# The facts each tool shows the person, beside kind, id, fingerprint, what.
# approve_code also shows the risk and the first words of the scan of the
# code (a cookbook's add-on), and the fingerprint of the add-on's folder
# that the OK binds (red team 2, R2-1 and R2-2).
SHOWN = {CODE_TOOL: ("source", "version", "author", "addon", "risk", "scan"), FILE_TOOL: ("document", "file", "button")}
# The caps of the shown fields (MAX_FIELD for the others).
FIELD_CAP = {"scan": 400, "addon": 120}
TTL = 600.0          # s a one-time grant stays good
OPEN_FOR = 3600.0    # s a pending request waits for its approval
MAX_LINES = 40
MAX_LINE = 300
MAX_FIELD = 200
MAX_ID = 120

_lock = threading.Lock()
_OPEN = {}           # key -> request
_GRANTS = {}         # key -> (expiry time, connection)
_CLIENT = {}         # tool -> [arguments of calls in hand, from the client]
_CONN = threading.local()  # .stack: the connections whose calls are in hand on this thread


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def tool_for(kind):
    return FILE_TOOL if kind in FILE_KINDS else CODE_TOOL


def key(kind, name, fingerprint):
    return f"{kind}:{ident(name)}:{fingerprint or ''}"


# Characters that show nothing but can carry hidden text (red team 4,
# R4-8): the variation selectors, the combining grapheme joiner, the Hangul
# fillers, the Mongolian selectors and the blank Braille pattern.
HIDING = ((0xFE00, 0xFE0F), (0xE0100, 0xE01EF), (0x034F, 0x034F), (0x115F, 0x1160), (0x3164, 0x3164),
          (0xFFA0, 0xFFA0), (0x180B, 0x180F), (0x2800, 0x2800))


def invisible(c):
    """True for a character that a person cannot see or that turns the
    text: Unicode category Cf (format: zero widths, joiners, direction
    marks), the tag block U+E0000-E007F, and U+202A-202E, U+2066-2069
    (red team 2, R2-7); and the HIDING characters (red team 4, R4-8)."""
    o = ord(c)
    return (0xE0000 <= o <= 0xE007F or 0x202A <= o <= 0x202E or 0x2066 <= o <= 0x2069 or unicodedata.category(c) == "Cf"
            or any(a <= o <= b for a, b in HIDING))


def hiding(text):
    """True when the text holds a HIDING character: such an id is refused,
    not cleaned (red team 4, R4-8). Format characters and direction marks
    are removed from it, as before (R2-7)."""
    return any(a <= ord(c) <= b for c in str(text) for a, b in HIDING)


def ascii_host(host):
    """A host as the client shows it: a non-ASCII host (Cyrillic letters
    that look like Latin ones) as punycode, with the words "non-ASCII
    host" (red team 4, R4-8). Answers (shown, was it non-ASCII)."""
    h = str(host)
    if h.isascii():
        return h, False
    try:
        return h.encode("idna").decode("ascii"), True
    except (UnicodeError, ValueError):
        return h.encode("ascii", "backslashreplace").decode("ascii"), True


def clean(text, cap=MAX_LINE):
    """One line of plain text: no control, invisible or direction
    characters (they are removed), capped."""
    t = "".join("" if invisible(c) else (" " if ord(c) < 32 or 0x7F <= ord(c) < 0xA0 or c in "\u2028\u2029" else c) for c in str(text))
    t = " ".join(t.split())
    return t[:cap] + ("…" if len(t) > cap else "")


def ident(name):
    """An approval's id: cleaned and capped (R2-9). A dialog's title or an
    add-on's name can be long or hold marks."""
    return clean(name, MAX_ID)


def tilde(text):
    """The home folder written as ~ (R2-17)."""
    t = str(text)
    h = os.path.expanduser("~")
    if h and h not in ("/", "~"):
        t = t.replace(h, "~")
    return t


def source_field(v):
    """The source as the client shows it: home as ~, a URL with its host
    first ("host: x, path: y"). Refused when it is longer than the cap:
    a cut would hide the tail (R2-10)."""
    t = clean(tilde(v), 10 * MAX_FIELD)
    u = None
    try:
        u = urlsplit(t) if "://" in t else None
    except ValueError:
        u = None
    if u is not None and u.netloc:
        host, idn = ascii_host(u.hostname or u.netloc)
        t = f"host: {host}{' (non-ASCII host)' if idn else ''}, path: {u.path or '/'}" + (f", query: {u.query}" if u.query else "") + (f", scheme: {u.scheme}" if u.scheme not in ("https", "http") else "")
        if "@" in u.netloc or (u.port and u.port not in (80, 443)):
            t += f", address: {u.netloc}"
    elif ":" in t and "@" in t.split(":", 1)[0] and "/" not in t.split(":", 1)[0]:  # git@host:path
        h, _, path = t.partition(":")
        host, idn = ascii_host(h.split("@", 1)[1])
        t = f"host: {host}{' (non-ASCII host)' if idn else ''}, path: {path}"
    if len(t) > MAX_FIELD:
        raise Refused("invalid_input", f"source: {len(t)} characters; the client shows {MAX_FIELD} or fewer, and a cut would hide the end. "
                                       "Use a shorter source. Nothing was asked.")
    return t


def identity(*parts):
    """A fingerprint of words (a repository and branch, a list of
    documents): sha256 of them, for an approval with no file to hash."""
    h = hashlib.sha256()
    for p in parts:
        h.update(json.dumps(p, sort_keys=True, default=str).encode("utf-8"))
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


SKIP_DIRS = {".git", "__pycache__", ".DS_Store"}


def folder_fingerprint(folder, cap_files=20000):
    """sha256 of a folder's files: each relative path and its bytes, in
    order (.git and __pycache__ left out). A new version of an add-on in a
    folder has a new fingerprint. None when the folder is not there."""
    folder = os.path.abspath(os.path.expanduser(folder))
    if not os.path.isdir(folder):
        return None
    h = hashlib.sha256()
    n = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f in SKIP_DIRS or f.endswith(".pyc"):
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, folder).replace(os.sep, "/")
            h.update(rel.encode("utf-8") + b"\0")
            if os.path.islink(p):
                h.update(b"link:" + os.readlink(p).encode("utf-8", "replace"))
            else:
                try:
                    with open(p, "rb") as fh:
                        for chunk in iter(lambda: fh.read(1 << 20), b""):
                            h.update(chunk)
                except OSError:
                    h.update(b"unreadable")
            h.update(b"\0")
            n += 1
            if n >= cap_files:
                h.update(b"capped")
                return "sha256:" + h.hexdigest()
    return "sha256:" + h.hexdigest()


# ---- calls from the client ------------------------------------------------------------------

class client_call:
    """protocol.Server.handle wraps a tools/call of approve_file or
    approve_code with this: the call came from the MCP client, so the
    client's permission prompt guarded it. Nested calls (batch, jobs,
    cookbooks, lessons, the panel) use Server.call and never get it."""

    def __init__(self, tool, args):
        self.tool = tool
        self.args = dict(args or {}) if isinstance(args, dict) else {}

    def __enter__(self):
        with _lock:
            _CLIENT.setdefault(self.tool, []).append(self.args)
        return self

    def __exit__(self, *exc):
        with _lock:
            got = _CLIENT.get(self.tool) or []
            for i, a in enumerate(got):
                if a is self.args:
                    del got[i]
                    break
        return False


class connection_call:
    """protocol.Server.handle wraps every tools/call with the connection it
    came on (the window link gives one for each paired connection; stdio
    has one only, None). A request is bound to the connection that asked,
    and only that connection approves it or uses its grant (red team 4,
    R4-11)."""

    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        st = getattr(_CONN, "stack", None)
        if st is None:
            st = _CONN.stack = []
        st.append(self.conn)
        return self

    def __exit__(self, *exc):
        st = getattr(_CONN, "stack", None) or []
        if st:
            st.pop()
        return False


def connection():
    """The connection whose call is in hand on this thread, or None."""
    st = getattr(_CONN, "stack", None)
    return st[-1] if st else None


def from_client(tool, args):
    """True when a call of tool with these arguments is in hand from the
    client (client_call)."""
    want = {k: (args or {}).get(k) for k in ("kind", "id", "fingerprint")}
    with _lock:
        return any({k: a.get(k) for k in want} == want for a in _CLIENT.get(tool) or ())


# ---- asking ---------------------------------------------------------------------------------

def _mine(bound, conn):
    """True when a request or grant bound to one connection is for this
    one: the same connection, or one of the two is not a connection's (a
    call with no connection: stdio, a job, the window's own press)."""
    return bound is None or conn is None or bound == conn


def take(kind, name, fingerprint=None):
    """Use up a grant: True when the person approved this (on this
    connection, R4-11)."""
    k = key(kind, name, fingerprint)
    conn = connection()
    with _lock:
        g = _GRANTS.get(k)
        if g is None or not _mine(g[1], conn):
            return False
        _GRANTS.pop(k, None)
    return g[0] >= time.time()


def granted(kind, name, fingerprint=None):
    with _lock:
        g = _GRANTS.get(key(kind, name, fingerprint))
    return g is not None and g[0] >= time.time() and _mine(g[1], connection())


def _prune(now):
    with _lock:
        for k in [k for k, r in _OPEN.items() if now - r["opened"] > OPEN_FOR]:
            _OPEN.pop(k, None)
        for k in [k for k, g in _GRANTS.items() if g[0] < now]:
            _GRANTS.pop(k, None)


def arguments(kind, name, fingerprint, title, shown=None):
    """The approve tool's arguments for a request: what the client shows
    the person."""
    if kind not in KINDS:
        raise Refused("invalid_input", f"kind {clean(kind, 40)!r}: not a kind of approval ({', '.join(sorted(KINDS))}). Nothing was asked.")
    if hiding(name):
        # Refused, not cleaned (red team 4, R4-8): an id with hidden
        # characters can look like an id that the person knows.
        raise Refused("invalid_input", f"id {clean(name, 60)!r}: it has invisible characters (variation selectors, fillers). Nothing was asked.")
    tool = tool_for(kind)
    args = {"kind": kind, "id": ident(name), "fingerprint": clean(fingerprint, MAX_FIELD), "what": clean(title, MAX_FIELD)}
    for f in SHOWN[tool]:
        v = (shown or {}).get(f)
        if v not in (None, ""):
            args[f] = source_field(v) if f == "source" else clean(v, FIELD_CAP.get(f, MAX_FIELD))
    return args


def ask(kind, name, title, lines=(), fingerprint=None, on_ok=None, shown=None, then=None, window=True):
    """See the module's words. Never raises for a missing window: the
    client's permission is the approval; the window is an extra path."""
    now = time.time()
    _prune(now)
    fp = fingerprint or identity(kind, name, shown or {})
    args = arguments(kind, name, fp, title, shown)
    name, fp = args["id"], args["fingerprint"]
    k = key(kind, name, fp)
    if on_ok is None and take(kind, name, fp):
        return {"ok": True}
    tool = tool_for(kind)
    req = {"key": k, "kind": kind, "name": name, "sha": fp, "tool": tool, "args": args, "title": clean(title, 120),
           "lines": [clean(x) for x in list(lines or [])[:MAX_LINES]], "on_ok": on_ok, "then": then, "opened": now, "shown": None,
           "client": connection()}
    with _lock:
        was = _OPEN.get(k)
        if was is not None:
            req["opened"] = was["opened"]
            req["dialog"] = was.get("dialog")
            req["alive"] = was.get("alive", True)
        _OPEN[k] = req
    in_window = False
    if window:
        try:
            from . import person_ok

            in_window = person_ok.offer(req, again=was is not None)
        except Exception:  # noqa: BLE001 - the window is an extra path only
            in_window = False
    kept = "It is kept: the next call answers at once." if on_ok else "Then call this tool again with the same arguments."
    next_words = (f"Call {tool} with exactly these arguments (approve.arguments). The person sets {tool} in the client's tool permissions: "
                  f"with \"ask first\", the client asks the person before the call. {kept}"
                  + (" The person can also press Approve in the FreeCAD window." if in_window else ""))
    return {"pending": True, "kind": kind, "name": str(name), "approve": {"tool": tool, "arguments": args}, "next": next_words}


def _record(req, by):
    try:
        from . import keep

        p = keep.path("approvals.log")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            conn = req.get("client")
            f.write(json.dumps({"t": round(time.time(), 1), "by": by, **({"connection": str(conn)} if conn is not None else {}),
                                **{k: tilde(v) for k, v in req["args"].items()}}, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 - a record only
        pass


def give(req, by, now=None):
    """The approval is given (by the client's approve tool, or by a
    person's press in the window): kept by on_ok, else a grant for the
    next call."""
    now = time.time() if now is None else now
    with _lock:
        _OPEN.pop(req["key"], None)
    if req.get("on_ok"):
        try:
            req["on_ok"](by)
        except TypeError:
            req["on_ok"]()
    else:
        with _lock:
            _GRANTS[req["key"]] = (now + TTL, req.get("client"))
    _record(req, by)
    if req.get("then"):
        try:
            req["then"]()
        except Exception:  # noqa: BLE001
            pass


def declined(req):
    with _lock:
        _OPEN.pop(req["key"], None)
        _GRANTS.pop(req["key"], None)


def waiting():
    """The requests that wait for an approval (of this connection, when a
    connection's call is in hand): their approve arguments."""
    now = time.time()
    _prune(now)
    conn = connection()
    with _lock:
        return [{"tool": r["tool"], "arguments": dict(r["args"]), "since": round(now - r["opened"])} for r in _OPEN.values() if _mine(r.get("client"), conn)]


def approve(tool, args):
    """approve_file / approve_code: see the module's words."""
    args = dict(args or {})
    if tool not in CLIENT_ONLY:
        raise Refused("invalid_input", f"{tool}: not an approval tool.")
    if not from_client(tool, args):
        raise Refused("not_allowed", f"{tool} takes only a direct call from the MCP client, which asks the person first when they set it to \"ask first\". "
                                     "A batch, a job, a cookbook, a lesson, a panel or another tool cannot call it. Nothing was approved.")
    kind, name, fp = args.get("kind"), args.get("id"), args.get("fingerprint")
    for f, v in (("kind", kind), ("id", name), ("fingerprint", fp)):
        if not isinstance(v, str) or not v:
            raise Refused("invalid_input", f"{f}: copy it from the pending answer (approve.arguments). Nothing was approved.")
    if kind not in KINDS:
        raise Refused("invalid_input", "kind: not a kind of approval. Copy it from the pending answer (approve.arguments). Nothing was approved.")
    for f, v in args.items():
        if isinstance(v, str) and (len(v) > 2000 or any(invisible(c) or ord(c) < 32 for c in v)):
            raise Refused("invalid_input", f"{f}: it has invisible or control characters, or it is too long. Use exactly the pending answer's arguments. Nothing was approved.")
    _prune(time.time())
    with _lock:
        req = _OPEN.get(key(kind, name, fp))
        same = [r for r in _OPEN.values() if r["kind"] == kind and r["name"] == name]
    if req is None:
        if same:
            raise Refused("invalid_state", f"{kind} {name}: the fingerprint is not the one that waits ({same[0]['sha'][:24]}…). It changed: a new version needs a new approval. "
                                           f"Call the tool that asked again, and use the arguments of its new pending answer. Nothing was approved.")
        raise Refused("not_found", f"Nothing waits for an approval of {kind} {name}. Call the tool that needs it first: its pending answer gives the {tool} arguments. Nothing was approved.")
    if req["tool"] != tool:
        raise Refused("invalid_input", f"{kind} is approved with {req['tool']}, not {tool}. Nothing was approved.")
    if not _mine(req.get("client"), connection()):
        # Another client asked for it (R4-11): that client's own permission
        # setting decides, not this one's.
        raise Refused("not_allowed", f"{kind} {name}: another client connection asked for this approval. Only that connection can approve it. Nothing was approved.")
    want = req["args"]
    extra = sorted(k for k in args if k not in want)
    if extra:
        raise Refused("invalid_input", f"{', '.join(extra)}: not in this approval. Use exactly the pending answer's arguments. Nothing was approved.")
    for f, v in want.items():
        if args.get(f) != v:
            raise Refused("invalid_input", f"{f}: must be exactly {json.dumps(v, ensure_ascii=False)} (the pending answer's). The client shows the person these arguments. Nothing was approved.")
    give(req, "client")
    return {"approved": True, "kind": kind, "id": name, "fingerprint": fp,
            "next": "Kept: the tool that asked answers at once now." if req.get("on_ok") else f"Call the tool that asked again with the same arguments within {int(TTL / 60)} min. The approval is for that one action."}


def reset():
    """Forget every request, grant and client call (tests)."""
    with _lock:
        _OPEN.clear()
        _GRANTS.clear()
        _CLIENT.clear()


# ---- the two tools' schemas (their words are in agentlink/tools.py) -------------------------

def schema(tool):
    props = {"kind": {"type": "string"}, "id": {"type": "string"}, "fingerprint": {"type": "string"}, "what": {"type": "string"}}
    for f in SHOWN[tool]:
        props[f] = {"type": "string"}
    return {"type": "object", "properties": props, "required": ["kind", "id", "fingerprint"], "additionalProperties": False}
