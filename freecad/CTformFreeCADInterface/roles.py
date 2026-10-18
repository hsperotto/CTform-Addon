# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""CTform role assignments over native FreeCAD document objects."""

import uuid


ROLE_NAMES = ("workpiece", "tool")


class CTformRoleAssignment:
    """Map a native FreeCAD object to a CTform case role."""

    def __init__(self, obj):
        self.Object = obj
        self._add_properties()

    def dumps(self):
        return None

    def loads(self, state):
        return None

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
        if "ToolId" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "ToolId", "CTform")
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
        if getattr(obj, "Role", "") == "tool" and not getattr(obj, "ToolId", ""):
            obj.ToolId = uuid.uuid4().hex

    def onDocumentRestored(self, obj=None):
        if obj is not None:
            self.Object = obj
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
    if role == "tool" and not obj.ToolId:
        obj.ToolId = uuid.uuid4().hex
    obj.Target = target
    if role == "tool" and tool_name:
        obj.Label = f"CTform Tool: {tool_name}"
    elif role == "workpiece" and target is not None:
        obj.Label = f'CTform Workpiece: "{target.Label}"'
    else:
        obj.Label = f"CTform Role: {role}"
    analysis.addObject(obj)
    case = next(
        (
            member
            for member in (getattr(analysis, "Group", ()) or ())
            if type(getattr(member, "Proxy", None)).__name__ == "CTformCase"
        ),
        None,
    )
    if case is not None:
        assignments = list(case.RoleAssignments)
        assignments.append(obj)
        case.RoleAssignments = assignments
    return obj
