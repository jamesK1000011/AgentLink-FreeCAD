# SPDX-License-Identifier: LGPL-2.1-or-later
# The agent's server, over stdio — what an MCP client (Claude Desktop, Claude
# Code) starts. Two ways:
#
#   headless   the tools run here, on a document of their own: FreeCAD
#              imported into this Python (FreeCADCmd, or a Python that
#              FreeCAD's library is on — conda-forge's freecad, or
#              FREECAD_LIB pointing at it)
#   --connect  relay to the FreeCAD GUI's Agent Link (the workbench's Start
#              link, port 7318 by default): the person watches each body
#              arrive in their own window
#
# stdout is the protocol's: FreeCAD and OCCT print to it from C++, so the
# real stdout is kept for the protocol and file descriptor 1 pointed at
# stderr before anything is imported.

import os
import socket
import sys
import threading

VERSION = "1.0.0"


def _protocol_stdout():
    real = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return real


def _import_freecad():
    try:
        import FreeCAD  # noqa: F401
        return
    except ImportError:
        pass
    for p in filter(None, [os.environ.get("FREECAD_LIB"), "/usr/lib/freecad/lib", "/usr/lib/freecad-python3/lib", "/Applications/FreeCAD.app/Contents/Resources/lib"]):
        if os.path.isdir(p) and p not in sys.path:
            sys.path.append(p)
    import FreeCAD  # noqa: F401  — the error names what is missing


def relay(port, out):
    """Pass lines both ways between this process's stdio and the GUI's link."""
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=10)
    except OSError as e:
        sys.stderr.write(f"Agent Link: no FreeCAD window listening on port {port} ({e}). In FreeCAD, switch to the Agent Link workbench and press Start link.\n")
        sys.exit(2)
    s.settimeout(None)
    f = s.makefile("rw", encoding="utf-8", newline="\n")
    from . import link_token

    try:
        s.settimeout(10)
        link_token.client_pair(f)
        s.settimeout(None)
    except (link_token.Refused, OSError) as e:
        sys.stderr.write(f"Agent Link: the FreeCAD window could not be paired with ({e}).\n")
        sys.exit(2)

    def down():
        for line in f:
            out.write(line)
            out.flush()
        os._exit(0)

    threading.Thread(target=down, daemon=True).start()
    for line in sys.stdin:
        f.write(line)
        f.flush()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Env as well as flags: FreeCADCmd takes the arguments after a script
    # for files to open, so a script it runs is given these by env.
    out_dir = os.path.abspath(os.environ.get("AGENTLINK_OUT", os.getcwd()))
    port = int(os.environ["AGENTLINK_CONNECT"]) if os.environ.get("AGENTLINK_CONNECT", "").isdigit() else None
    while argv:
        a = argv.pop(0)
        if a == "--out":
            out_dir = os.path.abspath(argv.pop(0))
        elif a == "--connect":
            port = int(argv.pop(0)) if argv and argv[0].isdigit() else 7318
        elif a in ("-h", "--help"):
            sys.stderr.write("agentlink [--out DIR] [--connect [PORT]]\n")
            return 0
    out = _protocol_stdout()
    if port is not None:
        relay(port, out)
        return 0
    _import_freecad()
    from .protocol import serve_lines
    from .tools import Session, build_server

    session = Session(out_dir=out_dir)
    server = build_server(session, version=VERSION)

    supervised = bool(os.environ.get("AGENTLINK_SUPERVISED"))

    def write(text):
        out.write(text)
        out.flush()
        # After each reply: an add-on keeping what this FreeCAD holds (for the
        # one started again after a crash to recover) writes it now.
        from . import hooks

        hooks.emit("reply_written", session)

        how = getattr(session, "exit_after_reply", None)
        if how and supervised:
            # A settings rollback with the window closed: start again on the
            # settings file as it now is. The supervisor sees the mark and
            # starts this FreeCAD again quietly.
            try:
                from . import keep

                keep._save(keep.path(".hidden-restart"), {"why": "settings"})
                if how != "nosave":
                    import FreeCAD

                    FreeCAD.saveParameter()
            except Exception:
                pass
            os._exit(0)

    def notify(msg):
        # A progress notification (protocol.progress): written at once, with none of a reply's after-work.
        from .protocol import compact

        out.write(compact(msg) + "\n")
        out.flush()

    server.notify = notify
    serve_lines(server, sys.stdin.readline, write)
    return 0


if __name__ == "__main__":
    sys.exit(main())
