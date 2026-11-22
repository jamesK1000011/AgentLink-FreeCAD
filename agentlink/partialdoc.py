# SPDX-License-Identifier: LGPL-2.1-or-later
"""A partly loaded document: FreeCAD opens a file only in part when a link
in another open document needs it (Document.Partial). FreeCAD keeps no
change to such a document: "Any modification to the partially loaded
document will generate a warning, and will not be saved" (FreeCAD_assembly3
wiki, Core Changes, partial document loading). A changing call or a save on
it said ok while nothing was kept (BicycleA part pass 21 Nov 2026, test T1
of claude/tool-research-2026-11-21.md). The call is refused instead, with
the way out: doc_revert loads the whole file."""

# Calls that act on the session rather than on the document's content:
# they must still run on a partly loaded document (they are the way out).
LEAVE = ("batch", "doc_revert", "doc_open", "doc_switch", "doc_close", "doc_new")


def partial(doc):
    try:
        return bool(getattr(doc, "Partial", False))
    except Exception:  # noqa: BLE001 - a deleted document, no FreeCAD
        return False


def refusal(doc, tool_name):
    """The refusal words for tool_name on doc, or None."""
    if tool_name in LEAVE or not partial(doc):
        return None
    label = getattr(doc, "Label", None) or getattr(doc, "Name", "?")
    what = "saved" if tool_name in ("doc_save", "doc_save_all") else "kept"
    return (f"{label} is loaded only in part (FreeCAD opened it for a link in another document): "
            f"FreeCAD keeps no change to it, so nothing would be {what}. "
            f"doc_revert loads the whole file; then call {tool_name} again.")
