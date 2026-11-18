# SPDX-License-Identifier: LGPL-2.1-or-later
"""The FreeCAD side of cookbook v2 (agentlink/cookbook2.py): the document's
state, the picks as objects, a scratch document for probes, and a task
panel's fields filled from data (no clicks, no cursor).

Every function takes FreeCAD as an argument (App, Gui) or imports it late,
so the tests give stand-ins.
"""
import contextlib

PICK_PREFIX = {"Face": "face", "Edge": "edge", "Vertex": "vertex"}


def snapshot(doc):
    """{name: {type, valid, sig}} of the document's objects (data for the
    result check)."""
    out = {}
    if doc is None:
        return out
    for o in list(getattr(doc, "Objects", []))[:5000]:
        row = {"type": getattr(o, "TypeId", "?")}
        sh = getattr(o, "Shape", None)
        if sh is not None:
            try:
                row["valid"] = bool(sh.isValid()) if not sh.isNull() else False
                row["sig"] = sh.hashCode() if hasattr(sh, "hashCode") else None
            except Exception:  # noqa: BLE001
                pass
        try:
            row["state"] = sorted(str(x) for x in getattr(o, "State", []))
        except Exception:  # noqa: BLE001
            pass
        out[o.Name] = row
    return out


def state(App, Gui, picks):
    """The state for the preconditions: document open, the selection as
    [(kind, ref)] (the picks of the inputs if any, else the window's
    selection), the count of each object type."""
    doc = getattr(App, "ActiveDocument", None)
    sel = list(picks)
    if not sel and Gui is not None and getattr(App, "GuiUp", False):
        try:
            for so in Gui.Selection.getSelectionEx():
                obj = so.Object
                subs = list(getattr(so, "SubElementNames", []) or [])
                if subs:
                    for s in subs:
                        kind = next((v for k, v in PICK_PREFIX.items() if s.startswith(k)), "object")
                        sel.append((kind, f"{obj.Name}.{s}"))
                else:
                    sel.append(("body" if getattr(obj, "TypeId", "") == "PartDesign::Body" else "object", obj.Name))
        except Exception:  # noqa: BLE001
            pass
    types = {}
    for o in list(getattr(doc, "Objects", []) if doc is not None else [])[:5000]:
        types[o.TypeId] = types.get(o.TypeId, 0) + 1
    return {"document": doc is not None, "selection": sel, "types": types}


class PickError(ValueError):
    pass


def resolve(doc, spec, ref):
    """One pick as the function wants it (spec "as"): name (the text),
    object, subname ((object, "Face3")) or shape (the sub-shape)."""
    as_ = spec.get("as", "name")
    if as_ == "name":
        return ref
    name, _, sub = ref.partition(".")
    obj = doc.getObject(name) if doc is not None else None
    if obj is None:
        raise PickError(f"{ref}: no object {name} in the document")
    if spec.get("type") == "body" and getattr(obj, "TypeId", "") != "PartDesign::Body":
        raise PickError(f"{ref}: {name} is not a PartDesign Body")
    if as_ == "object":
        return obj
    if as_ == "subname":
        return (obj, sub)
    sh = getattr(obj, "Shape", None)
    if sh is None:
        raise PickError(f"{ref}: {name} has no shape")
    if not sub:
        return sh
    try:
        return sh.getElement(sub)
    except Exception:  # noqa: BLE001
        raise PickError(f"{ref}: {name} has no {sub}")


def kwargs(doc, inputs, values):
    out = {}
    for k, v in values.items():
        spec = inputs.get(k, {})
        if spec.get("type") in ("face", "edge", "vertex", "object", "body"):
            out[k] = [resolve(doc, spec, r) for r in v] if isinstance(v, list) else resolve(doc, spec, v)
        else:
            out[k] = v
    return out


@contextlib.contextmanager
def scratch(App, name="AgentLinkProbe"):
    """A hidden scratch document for a probe, closed after; the person's
    active document is put back."""
    was = getattr(App, "ActiveDocument", None)
    try:
        doc = App.newDocument(name, hidden=True, temp=True)
    except TypeError:
        doc = App.newDocument(name)
    try:
        yield doc
    finally:
        try:
            App.closeDocument(doc.Name)
        except Exception:  # noqa: BLE001
            pass
        if was is not None:
            try:
                App.setActiveDocument(was.Name)
            except Exception:  # noqa: BLE001
                pass


def probe_values(App, doc, inputs):
    """Inputs for a probe: each default; a pick of a Part box made in the
    scratch document (Face1, Edge1, Vertex1, the box). None and the reason
    when an input has neither."""
    vals, box = {}, None
    for k, spec in (inputs or {}).items():
        t = spec.get("type")
        if "default" in spec:
            vals[k] = spec["default"]
        elif t in ("face", "edge", "vertex", "object"):
            if box is None:
                box = doc.addObject("Part::Box", "ProbeBox")
                doc.recompute()
            ref = box.Name if t == "object" else f"{box.Name}.{t.capitalize()}1"
            n = (spec.get("count") or [1, 1])[0] or 1
            vals[k] = [ref] * n if isinstance(spec.get("count"), list) and spec["count"][1] > 1 else ref
        elif spec.get("required", True):
            return None, f"input {k} ({t}) has no default; give one in the entry, or probe it live with cookbook_run"
    return vals, None


# ---- a task panel's fields, from data ----------------------------------------------------------

SETTABLE = ("QDoubleSpinBox", "QSpinBox", "Gui::QuantitySpinBox", "Gui::InputField", "Gui::UIntSpinBox", "Gui::IntSpinBox",
            "Gui::DoubleSpinBox", "QLineEdit", "QCheckBox", "QRadioButton", "QComboBox", "QSlider", "Gui::PrefQuantitySpinBox",
            "Gui::PrefSpinBox", "Gui::PrefDoubleSpinBox", "Gui::PrefCheckBox", "Gui::PrefLineEdit", "Gui::PrefComboBox")


class FormError(ValueError):
    pass


def _class(w):
    try:
        return w.metaObject().className()
    except Exception:  # noqa: BLE001
        return type(w).__name__


def _kind(w):
    """The setter family of a widget, by its class or its first known base."""
    try:
        mo = w.metaObject()
        while mo is not None:
            c = mo.className()
            if c in SETTABLE:
                return c
            mo = mo.superClass()
    except Exception:  # noqa: BLE001
        c = type(w).__name__
        if c in SETTABLE:
            return c
    return None


def find(root, name):
    """The widget with objectName name under root, or None."""
    try:
        from PySide import QtGui

        QtW = getattr(__import__("PySide", fromlist=["QtWidgets"]), "QtWidgets", QtGui)
        hits = [w for w in root.findChildren(QtW.QWidget) if w.objectName() == name]
    except Exception:  # noqa: BLE001
        hits = [w for w in getattr(root, "children_all", lambda: [])() if w.objectName() == name]
    return hits[0] if len(hits) == 1 else (None if not hits else FormError(f"{name}: {len(hits)} widgets have this name"))


def fill(root, fields, finder=None):
    """Set each widget (objectName: value) of a task panel. All widgets are
    found and checked first: nothing is set when one is missing. Only input
    widgets are set; a button is never pressed here. Answers what each
    widget shows after."""
    finder = finder or find
    found = {}
    for name, v in fields.items():
        w = finder(root, name)
        if isinstance(w, FormError):
            raise w
        if w is None:
            raise FormError(f"{name}: no such field in the task panel (the add-on version may differ)")
        k = _kind(w)
        if k is None:
            raise FormError(f"{name}: a {_class(w)} is not an input field; a form fills fields only")
        found[name] = (w, k, v)
    out = {}
    for name, (w, k, v) in found.items():
        out[name] = _set(w, k, v, name)
    return out


def _set(w, k, v, name):
    if k.endswith(("QuantitySpinBox", "InputField")):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise FormError(f"{name}: a number")
        lo, hi = _range(w)
        if lo is not None and not lo <= v <= hi:
            raise FormError(f"{name}: {v} is out of the field's range {lo} to {hi}")
        w.setProperty("rawValue", float(v))
        return w.property("rawValue")
    if k.endswith(("SpinBox", "QSlider")):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise FormError(f"{name}: a number")
        lo, hi = _range(w)
        if lo is not None and not lo <= v <= hi:
            raise FormError(f"{name}: {v} is out of the field's range {lo} to {hi}")
        w.setValue(int(v) if "Double" not in k else float(v))
        return w.value()
    if k.endswith("LineEdit"):
        w.setText(str(v))
        return w.text()
    if k.endswith(("CheckBox", "RadioButton")):
        if not isinstance(v, bool):
            raise FormError(f"{name}: true or false")
        w.setChecked(v)
        return w.isChecked()
    if k.endswith("ComboBox"):
        if isinstance(v, int) and not isinstance(v, bool):
            if not 0 <= v < w.count():
                raise FormError(f"{name}: item {v} is not there ({w.count()} items)")
            w.setCurrentIndex(v)
        else:
            i = w.findText(str(v))
            if i < 0:
                raise FormError(f"{name}: no item {str(v)[:40]!r}")
            w.setCurrentIndex(i)
        return w.currentText()
    raise FormError(f"{name}: not an input field")


def _range(w):
    try:
        return float(w.minimum()), float(w.maximum())
    except Exception:  # noqa: BLE001
        return None, None
