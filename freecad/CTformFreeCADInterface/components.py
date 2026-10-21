# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""CTform workpiece and tool component folders."""

from .identifiers import readable_id
from .viewproviders import attach_view_provider


class CTformWorkpiece:
    """Own links to the workpiece shape, mesh, material, and contact pairs."""

    def __init__(self, obj):
        self.Object = obj
        self._add_properties()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def onDocumentRestored(self, obj=None):
        if obj is not None:
            self.Object = obj
        self._add_properties()

    def _add_properties(self):
        obj = self.Object
        _add(obj, "Shape", "App::PropertyLink", "Component", None)
        _add(obj, "Mesh", "App::PropertyLink", "Component", None)
        _add(obj, "Material", "App::PropertyLink", "Component", None)
        _add(obj, "ContactPairs", "App::PropertyLinkList", "Contact", [])
        _add(obj, "MeshFile", "App::PropertyString", "Export", "workpiece.msh")


class CTformTool:
    """Own links and export settings for one named tool component."""

    def __init__(self, obj):
        self.Object = obj
        self._add_properties()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def onDocumentRestored(self, obj=None):
        if obj is not None:
            self.Object = obj
        self._add_properties()

    def _add_properties(self):
        obj = self.Object
        _add(obj, "ToolId", "App::PropertyString", "Identity", "")
        _add(obj, "ToolName", "App::PropertyString", "Identity", "Tool")
        _add(obj, "Shape", "App::PropertyLink", "Component", None)
        _add(obj, "Mesh", "App::PropertyLink", "Component", None)
        _add(obj, "Material", "App::PropertyLink", "Component", None)
        if "Role" not in obj.PropertiesList:
            obj.addProperty("App::PropertyEnumeration", "Role", "Export")
            obj.Role = ["auto", "upper", "lower"]
            obj.Role = "auto"
        _add(obj, "ToolLayer", "App::PropertyString", "Export", "ToolProfile")
        _add(obj, "InitialOffsetZ", "App::PropertyFloat", "Export", 0.0)
        _add(obj, "SymmetryR", "App::PropertyFloat", "Export", 0.0)


def make_workpiece(doc, analysis, case, shape, name="CTformWorkpiece"):
    if getattr(case, "Workpiece", None) is not None:
        raise ValueError("A CTform case can contain only one workpiece")
    if shape is None:
        raise ValueError("Select a shape before creating the CTform workpiece")
    obj = doc.addObject("App::DocumentObjectGroupPython", name)
    obj.Proxy = CTformWorkpiece(obj)
    obj.Shape = shape
    obj.Label = f'CTform Workpiece: {shape.Label}'
    analysis.addObject(obj)
    obj.addObject(shape)
    case.Workpiece = obj
    attach_view_provider(obj)
    return obj


def make_tool(
    doc,
    analysis,
    case,
    shape,
    tool_name="",
    name="CTformTool",
):
    if shape is None:
        raise ValueError("Select a shape before creating a CTform tool")
    tool_name = str(tool_name).strip()
    if not tool_name:
        raise ValueError("A CTform tool must have a name")
    obj = doc.addObject("App::DocumentObjectGroupPython", name)
    obj.Proxy = CTformTool(obj)
    obj.Shape = shape
    obj.ToolName = tool_name
    obj.ToolId = readable_id(
        tool_name,
        (getattr(existing, "ToolId", "") for existing in (getattr(case, "Tools", ()) or ())),
        fallback="tool",
    )
    obj.Label = f"CTform Tool: {tool_name}"
    analysis.addObject(obj)
    obj.addObject(shape)
    tools = list(getattr(case, "Tools", ()) or ())
    tools.append(obj)
    case.Tools = tools
    attach_view_provider(obj)
    return obj


def _add(obj, name, property_type, group, default):
    if name not in obj.PropertiesList:
        obj.addProperty(property_type, name, group)
        if default is not None:
            setattr(obj, name, default)