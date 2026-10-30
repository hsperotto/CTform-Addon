# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Helpers for FreeCAD property definitions and unit conversion.

No FreeCAD imports, so the rules can be tested with plain objects.
"""

from typing import Any


def add_property(obj: Any, name: str, property_type: str, group: str, default: Any) -> None:
    """Add a property once, and set its default only when the property is created.

    An enumeration takes its choices as ``default``; the first choice becomes the
    value. A ``None`` default leaves FreeCAD's own default (for example an empty link).
    """
    if name in obj.PropertiesList:
        return
    obj.addProperty(property_type, name, group)
    if property_type == "App::PropertyEnumeration":
        setattr(obj, name, default)
        setattr(obj, name, default[0])
    elif default is not None:
        setattr(obj, name, default)


def length_to_si(value: Any) -> float:
    """Return a FreeCAD length in metres; a plain number is read as millimetres."""
    if hasattr(value, "getValueAs"):
        return float(value.getValueAs("m"))
    return float(value) * 1e-3
