# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

from importlib.resources import as_file, files

import freecad.CTformFreeCADInterface as module

resources = files(module) / "resources"
icons = resources / "icons"


def as_icon(name: str) -> str:
    icon = icons / (name + ".svg")
    with as_file(icon) as path:
        return str(path)
