# SPDX-License-Identifier: LGPL-2.1-or-later
"""Why a picture is empty, in words: view_render and view_snapshot answer
"empty" with the reason and what to do, instead of a blank image to look at
(a picture costs the agent about a thousand tokens to learn nothing).
Plain Python: the callers read FreeCAD and hand the facts in."""

ALMOST = 0.002   # a picture with under 0.2% of its pixels covered shows almost nothing
SMALL_PX = 6     # a model under this many pixels across is a speck


def _names(xs, n=6):
    xs = [str(x) for x in xs]
    return ", ".join(xs[:n]) + (f" … ({len(xs)} in all)" if len(xs) > n else "")


def nothing_to_draw(hidden=(), shapeless=(), objects=0, named=False, layers=()):
    """view_render with no layer to draw. hidden: parts that are hidden;
    shapeless: objects that have no solid (named, or in the document);
    objects: how many objects the document holds; named: objects was given;
    layers: the add-on layers there are."""
    if named and shapeless:
        return (f"Nothing to draw: {_names(shapeless)} {'has' if len(shapeless) == 1 else 'have'} no solid shape (a sketch, a surface, a mesh, an empty or failed feature) — "
                "session_state lists the bodies that can be drawn; recompute names what failed to build.")
    if hidden:
        return (f"Nothing to draw: every part is hidden ({_names(hidden)}) — view_render {{ objects: [names] }} draws them anyway, "
                "object_set { values: { Visibility: true } } shows one.")
    if not objects:
        return "Nothing to draw: the document is empty — make a body first (part_primitive, pd_body_new), or doc_open a file."
    if shapeless:
        return (f"Nothing to draw: no object here has a solid shape ({_names(shapeless)}: sketches, surfaces, meshes or features that made nothing) — "
                "recompute names what failed to build; a mesh or a scan is drawn by its own layer" + (f" (layers: {_names(layers)})" if layers else "") + ".")
    return "Nothing to draw: no body is shown, and no scan or other layer is loaded — session_state lists what the document holds."


def off_frame(cover, frame=None, section=None, box=None):
    """A render whose pixels are (almost) all background, or None when
    something is to be seen. cover: {view: fraction of pixels covered};
    frame: the zoom { at, size }; box: the parts' { min, max }."""
    if not cover:
        return None
    worst = max(cover.values())
    if worst > ALMOST:
        return None
    what = "Nothing" if worst <= 0 else "Almost nothing"
    where = ""
    if box:
        where = f" The parts span {[round(float(c), 1) for c in box['min']]} to {[round(float(c), 1) for c in box['max']]} mm."
    if frame:
        inside = True
        if box:
            half = float(frame.get("size", 20)) / 2.0
            inside = all(float(box["min"][i]) - half <= float(frame["at"][i]) <= float(box["max"][i]) + half for i in range(3))
        why = (f"the zoom frames {float(frame.get('size', 20)):g} mm at {[round(float(c), 1) for c in frame['at']]}, "
               + ("where the parts have no surface facing the view (inside a solid, or a gap)" if inside else "which is outside the parts"))
        todo = "zoom at a point on the part (a finding's at, shape_query's centroid), a larger size, or leave zoom out to fit everything"
    elif section:
        why = "the cut leaves nothing on the side that is kept"
        todo = "another offset (the middle when left out), flip: true for the other side, or leave section out"
    else:
        why = "the parts are a speck at this size (one far-off part stretches the frame)"
        todo = "objects: [names] draws only those, or zoom { at, size } frames a spot"
    return f"{what} landed in the picture: {why}.{where} Try {todo}."


def no_map(name, why):
    """A map with nothing to colour by: the reason its reader gave."""
    return f"No {name} map to draw: {why}"


def off_screen(points, size, shown=1, hidden=()):
    """The window's own view (view_snapshot) with nothing, or almost
    nothing, of the model in it, or None. points: the model's box corners
    in pixels [(x, y) …]; size: the view's (w, h); shown: how many objects
    with a shape are visible; hidden: names of hidden parts."""
    if not shown:
        if hidden:
            return (f"The view is empty: everything is hidden ({_names(hidden)}) — object_set {{ values: {{ Visibility: true }} }} shows one; "
                    "view_render { objects: [names] } draws them without showing them.")
        return "The view is empty: the document has nothing with a shape to show — session_state lists what it holds."
    if not points or not size:
        return None
    w, h = float(size[0]), float(size[1])
    xs, ys = [float(p[0]) for p in points], [float(p[1]) for p in points]
    if max(xs) < 0 or min(xs) > w or max(ys) < 0 or min(ys) > h:
        return ("The view misses the model: it lies wholly outside the frame as the view stands (panned or zoomed away) — "
                "view_snapshot with a view (iso, top …) turns and fits it; fit: false keeps the zoom.")
    if max(xs) - min(xs) < SMALL_PX and max(ys) - min(ys) < SMALL_PX:
        return ("The model is a speck in the view (under 6 pixels across: zoomed far out) — "
                "view_snapshot with a view (iso, top …) and fit left on fits it.")
    return None
