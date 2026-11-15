# SPDX-License-Identifier: LGPL-2.1-or-later
"""Agent Link: FreeCAD driven by an agent over the Model Context Protocol."""

import contextlib

# The server run(...) calls into: set for a while by serving(server) (an
# add-on running a saved macro through the agent's own server); otherwise a
# server of its own on the document in front, made at the first call.
_current = []


def run(tool, args=None):
    """Call an Agent Link tool from Python — what a saved macro does (its
    lines are agentlink.run(...)): the same refusals and undo steps as a live
    call. Answers the tool's result; a refusal raises RuntimeError with its
    message."""
    import json
    import os

    if _current:
        server = _current[-1]
    else:
        import FreeCAD

        from .tools import Session, build_server

        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument("AgentLink")
        server = build_server(Session(doc=doc, out_dir=os.path.expanduser("~/AgentLink")), lean=False)
        _current.append(server)
    r = server.call({"name": tool, "arguments": args or {}})
    body = json.loads(r["content"][0]["text"])
    if r.get("isError"):
        raise RuntimeError(f"{tool}: {(body.get('error') or {}).get('message', body)}")
    return body


@contextlib.contextmanager
def serving(server):
    """run(...) goes to this server while the block runs."""
    _current.append(server)
    try:
        yield server
    finally:
        _current.pop()
