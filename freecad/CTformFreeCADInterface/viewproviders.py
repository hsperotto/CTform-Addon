# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Object-tree icons for CTform Workpiece, Tool, Load Step and Material objects (GUI only)."""

from __future__ import annotations

import os

_ICON_DIR = os.path.join(os.path.dirname(__file__), "resources", "icons")
WORKPIECE_ICON = os.path.join(_ICON_DIR, "workpiece.svg")
TOOL_ICON = os.path.join(_ICON_DIR, "tool.svg")
LOAD_STEP_ICON = os.path.join(_ICON_DIR, "load-step.svg")
MATERIAL_ICON = ":/icons/FEM_MaterialSolid.svg"


class _FolderViewProvider:
    """Base for tree view providers; subclasses return a fixed icon.

    The icon comes from the class, not an attribute, because FreeCAD restores
    a saved view provider without calling ``__init__``.
    """

    def __init__(self, view_object):
        view_object.Proxy = self

    def attach(self, view_object):
        self.Object = view_object.Object

    def dumps(self):
        return None

    def loads(self, state):
        return None


class WorkpieceViewProvider(_FolderViewProvider):
    def getIcon(self):
        return WORKPIECE_ICON


class ToolViewProvider(_FolderViewProvider):
    def getIcon(self):
        return TOOL_ICON


class LoadStepViewProvider(_FolderViewProvider):
    def getIcon(self):
        return LOAD_STEP_ICON


class MaterialViewProvider(_FolderViewProvider):
    def getIcon(self):
        return MATERIAL_ICON


def attach_view_provider(obj) -> None:
    """Give a CTform object its tree icon; no-op without a GUI."""
    from .components import CTformTool, CTformWorkpiece
    from .loadsteps import CTformLoadStep
    from .materials import CTformMaterial

    view_object = getattr(obj, "ViewObject", None)
    if view_object is None or getattr(view_object, "Proxy", None) is not None:
        return
    proxy = getattr(obj, "Proxy", None)
    for proxy_class, view_provider in (
        (CTformWorkpiece, WorkpieceViewProvider),
        (CTformTool, ToolViewProvider),
        (CTformLoadStep, LoadStepViewProvider),
        (CTformMaterial, MaterialViewProvider),
    ):
        if isinstance(proxy, proxy_class):
            view_provider(view_object)
            return


def attach_view_providers(doc) -> None:
    """Attach icons to objects of a document opened before icons existed."""
    for obj in getattr(doc, "Objects", ()) or ():
        attach_view_provider(obj)
