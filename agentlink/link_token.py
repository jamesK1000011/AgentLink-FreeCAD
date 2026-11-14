# SPDX-License-Identifier: LGPL-2.1-or-later
# The window link's pairing. The FreeCAD window's link listens on 127.0.0.1,
# where any program on this computer can reach it (a web page cannot: its
# request is cut off at its first line). So the window keeps a secret in a
# file only this user can read (~/.config/freecad-agentlink/link-token,
# mode 600), and each side proves it knows it before a call is served. The
# secret itself never crosses the socket, so a program that took the port
# first (a fake window) learns nothing and cannot pass for the window:
#
#   client  {"jsonrpc":"2.0","method":"agentlink/hello","params":{"nonce":c}}
#   window  {"jsonrpc":"2.0","method":"agentlink/hello","params":{"nonce":w,"proof":H("window",c)}}
#   client  {"jsonrpc":"2.0","method":"agentlink/proof","params":{"proof":H("client",w)}}
#
# H is HMAC-SHA256 under the secret. Nothing to set up: the window makes the
# file when its link first starts; the clients (the relay, the supervisor,
# the Claude extension's launcher) read it. It keeps out other users'
# programs and sandboxed apps; a program already running as this user can
# read the file too.
import hashlib
import hmac
import json
import os
import secrets

HELLO = "agentlink/hello"
PROOF = "agentlink/proof"


def path():
    return os.path.expanduser(os.environ.get("AGENTLINK_TOKEN_FILE") or os.path.join("~", ".config", "freecad-agentlink", "link-token"))


def read():
    """The secret, or None when no window has made one yet."""
    try:
        with open(path(), encoding="utf-8") as f:
            t = f.read().strip()
        return t or None
    except OSError:
        return None


def ensure():
    """The secret, made (owner read/write only) when there is none; the
    file's mode put right if something widened it."""
    p = path()
    os.makedirs(os.path.dirname(p), mode=0o700, exist_ok=True)
    t = read()
    if t is None:
        t = secrets.token_urlsafe(32)
        tmp = f"{p}.{os.getpid()}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(t + "\n")
        os.replace(tmp, p)
        t = read() or t  # two windows at once: the file that landed last
    try:
        if os.stat(p).st_mode & 0o077:
            os.chmod(p, 0o600)
    except OSError:
        pass
    return t


def proof(secret, role, nonce):
    return hmac.new(secret.encode(), f"{role}:{nonce}".encode(), hashlib.sha256).hexdigest()


def _msg(method, **params):
    return json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n"


def _parse(line, method):
    try:
        m = json.loads(line)
    except (ValueError, TypeError):
        return None
    if isinstance(m, dict) and m.get("jsonrpc") == "2.0" and m.get("method") == method and isinstance(m.get("params"), dict):
        return m["params"]
    return None


def _same(a, b):
    return isinstance(a, str) and isinstance(b, str) and hmac.compare_digest(a.encode(), b.encode())


# ---- the window's side ------------------------------------------------------------------


def window_greet(line, secret):
    """The window's answer to a client's hello line and the nonce it now
    expects proven, or (None, None) to refuse."""
    p = _parse(line, HELLO)
    if not secret or p is None or not isinstance(p.get("nonce"), str) or not 16 <= len(p["nonce"]) <= 128:
        return None, None
    w = secrets.token_hex(16)
    return _msg(HELLO, nonce=w, proof=proof(secret, "window", p["nonce"])), w


def window_check(line, secret, w):
    """Whether the client's proof line is right for the window's nonce."""
    p = _parse(line, PROOF)
    return p is not None and _same(p.get("proof"), proof(secret, "client", w))


# ---- a client's side -----------------------------------------------------------------------


class Refused(Exception):
    pass


def client_pair(f, secret=None):
    """Pair a client over f (a text file on the socket, already connected):
    says hello, checks the window's proof, proves itself. Raises Refused when
    there is no secret here or the other end is not the window."""
    secret = secret or read()
    if not secret:
        raise Refused("no pairing token here yet: the FreeCAD window makes it when its link starts")
    c = secrets.token_hex(16)
    f.write(_msg(HELLO, nonce=c))
    f.flush()
    line = f.readline()
    p = _parse(line, HELLO)
    if p is None or not _same(p.get("proof"), proof(secret, "window", c)) or not isinstance(p.get("nonce"), str):
        raise Refused("what answered on the window's port did not prove it is the FreeCAD window")
    f.write(_msg(PROOF, proof=proof(secret, "client", p["nonce"])))
    f.flush()
