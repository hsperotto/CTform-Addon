# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""CTform role assignments over native FreeCAD document objects."""


ROLE_NAMES = ("workpiece", "tool")


class CTformRoleAssignment:
    """Map a native FreeCAD object to a CTform case role."""

    def __init__(self, obj):
        self.Object = obj
        self._add_properties()

    def _add_properties(self):
        obj = self.Object
        if "Role" not in obj.PropertiesList:
            obj.addProperty("App::PropertyEnumeration", "Role", "CTform")
            obj.Role = list(ROLE_NAMES)
            obj.Role = "workpiece"
        if "Target" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Target", "CTform")
        if "Mesh" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Mesh", "CTform")
        if "Material" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Material", "CTform")
        if "ToolName" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "ToolName", "CTform")
        if "SourceFile" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SourceFile", "Export")
        if "ToolLayer" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "ToolLayer", "Export")
        if "InitialOffsetZ" not in obj.PropertiesList:
            obj.addProperty("App::PropertyFloat", "InitialOffsetZ", "Export")
            obj.InitialOffsetZ = 0.0
        if "SymmetryR" not in obj.PropertiesList:
            obj.addProperty("App::PropertyFloat", "SymmetryR", "Export")
            obj.SymmetryR = 0.0

    def onDocumentRestored(self):
        self._add_properties()


def make_role_assignment(
    doc,
    analysis,
    target=None,
    role="workpiece",
    tool_name="",
    name="CTformRole",
):
    """Create a role assignment as a direct member of a FEM analysis."""
    if role not in ROLE_NAMES:
        raise ValueError(f"Unsupported CTform role: {role}")
    obj = doc.addObject("App::FeaturePython", name)
    obj.Label = f"CTform Role: {role}"
    obj.Proxy = CTformRoleAssignment(obj)
    obj.Role = role
    obj.ToolName = tool_name if role == "tool" else ""
    obj.Target = target
    obj.Label = f"CTform Tool: {tool_name}" if role == "tool" and tool_name else f"CTform Role: {role}"
    analysis.addObject(obj)
    case = getattr(analysis, "CTformCase", None)
    if case is not None:
        assignments = list(case.RoleAssignments)
        assignments.append(obj)
        case.RoleAssignments = assignments
    return obj
