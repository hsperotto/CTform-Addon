# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""FreeCAD commands exposed by the CTform workbench."""

import json
import os
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from .analysis import analysis_for_case, find_case, make_case, make_solver
from .case_export import write_case_json
from .contacts import make_contact_pair
from .loadsteps import (
    CTformLoadStep,
    attach_condition,
    clone_load_step,
    detach_condition,
    fem_condition_category,
    fem_condition_kind,
    make_load_step,
    condition_targets_role,
)
from .materials import make_material
from .roles import CTformRoleAssignment, make_role_assignment


_ICON = os.path.join(os.path.dirname(__file__), "resources", "icons", "logo.svg")


class CreateCaseCommand:
    """Create an empty CTform 2D case."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Create CTform Case",
            "ToolTip": "Create a CTform 2D case",
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        case = make_case(App.ActiveDocument)
        import FemGui

        FemGui.setActiveAnalysis(analysis_for_case(case))
        App.ActiveDocument.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(case)


class CreateSolverCommand:
    """Create a CTform solver/job object for the active case."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Create CTform Solver",
            "ToolTip": "Create a CTform Core solver job",
        }

    def IsActive(self):
        return App.ActiveDocument is not None and find_case(App.ActiveDocument) is not None

    def Activated(self):
        case = find_case(App.ActiveDocument)
        solver = make_solver(App.ActiveDocument, case)
        App.ActiveDocument.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(solver)


class CreateMaterialCommand:
    """Create an addon-owned CTform thermomechanical material record."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Create CTform Material",
            "ToolTip": "Create a CTform material with constitutive and thermal properties",
        }

    def IsActive(self):
        return App.ActiveDocument is not None and find_case(App.ActiveDocument) is not None

    def Activated(self):
        case = find_case(App.ActiveDocument)
        material = make_material(App.ActiveDocument, analysis_for_case(case), case)
        App.ActiveDocument.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(material)


def _selected_role_and_material():
    selection = Gui.Selection.getSelection()
    if len(selection) != 2:
        return None, None
    role = next(
        (
            obj
            for obj in selection
            if isinstance(getattr(obj, "Proxy", None), CTformRoleAssignment)
        ),
        None,
    )
    material = next(
        (
            obj
            for obj in selection
            if type(getattr(obj, "Proxy", None)).__name__ == "CTformMaterial"
        ),
        None,
    )
    if role is None or material is None or role.Document is not material.Document:
        return None, None
    case = find_case(role.Document)
    if (
        case is None
        or role not in (getattr(case, "RoleAssignments", ()) or ())
        or material not in (getattr(case, "Materials", ()) or ())
    ):
        return None, None
    return role, material


class AssignMaterialCommand:
    """Assign a CTform material catalog entry to a geometry role."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Assign CTform Material",
            "ToolTip": "Assign a selected CTform material to a workpiece or tool role",
        }

    def IsActive(self):
        role, material = _selected_role_and_material()
        return role is not None and material is not None

    def Activated(self):
        role, material = _selected_role_and_material()
        if role is None or material is None:
            return
        doc = role.Document
        doc.openTransaction("Assign CTform material")
        role.Material = material
        doc.recompute()
        doc.commitTransaction()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(role)


def _selected_role_and_fem_mesh():
    selection = Gui.Selection.getSelection()
    if len(selection) != 2:
        return None, None
    roles = [
        obj
        for obj in selection
        if isinstance(getattr(obj, "Proxy", None), CTformRoleAssignment)
    ]
    meshes = [obj for obj in selection if str(getattr(obj, "TypeId", "")).startswith("Fem::FemMesh")]
    if len(roles) != 1 or len(meshes) != 1:
        return None, None
    role, mesh = roles[0], meshes[0]
    case = find_case(role.Document)
    if (
        mesh.Document is not role.Document
        or case is None
        or role not in (getattr(case, "RoleAssignments", ()) or ())
        or mesh not in (getattr(analysis_for_case(case), "Group", ()) or ())
    ):
        return None, None
    target_shape = getattr(getattr(role, "Target", None), "Shape", None)
    mesh_source = getattr(mesh, "Shape", None)
    mesh_shape = getattr(mesh_source, "Shape", mesh_source)
    if target_shape is not None and mesh_shape is not None and not mesh_shape.isSame(target_shape):
        return None, None
    return role, mesh


class AssignMeshCommand:
    """Assign a native FEM mesh object to a CTform geometry role."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Assign FEM Mesh to CTform Role",
            "ToolTip": "Link a Gmsh FEM mesh to the selected workpiece or tool role",
        }

    def IsActive(self):
        role, mesh = _selected_role_and_fem_mesh()
        return role is not None and mesh is not None

    def Activated(self):
        role, mesh = _selected_role_and_fem_mesh()
        if role is None or mesh is None:
            return
        doc = role.Document
        doc.openTransaction("Assign FEM mesh to CTform role")
        role.Mesh = mesh
        doc.recompute()
        doc.commitTransaction()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(role)


def _selected_workpiece_tool_roles():
    selection = Gui.Selection.getSelection()
    if len(selection) != 2:
        return None, None
    roles = [
        obj
        for obj in selection
        if isinstance(getattr(obj, "Proxy", None), CTformRoleAssignment)
    ]
    if len(roles) != 2 or roles[0].Document is not roles[1].Document:
        return None, None
    workpiece = next((role for role in roles if getattr(role, "Role", "") == "workpiece"), None)
    tool = next((role for role in roles if getattr(role, "Role", "") == "tool"), None)
    case = find_case(roles[0].Document)
    if (
        workpiece is None
        or tool is None
        or case is None
        or any(role not in (getattr(case, "RoleAssignments", ()) or ()) for role in roles)
    ):
        return None, None
    return workpiece, tool


class CreateContactPairCommand:
    """Create a visible contact pair from selected workpiece and tool roles."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Create CTform Contact Pair",
            "ToolTip": "Create a contact pair from a selected workpiece and named tool",
        }

    def IsActive(self):
        workpiece, tool = _selected_workpiece_tool_roles()
        return workpiece is not None and tool is not None

    def Activated(self):
        workpiece, tool = _selected_workpiece_tool_roles()
        if workpiece is None or tool is None:
            return
        case = find_case(workpiece.Document)
        doc = workpiece.Document
        doc.openTransaction("Create CTform contact pair")
        pair = make_contact_pair(doc, analysis_for_case(case), case, workpiece, tool)
        doc.recompute()
        doc.commitTransaction()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(pair)


class ExportCaseCommand:
    """Export the active CTform case settings to case.json."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Export CTform Case",
            "ToolTip": "Write the CTform case.json package",
        }

    def IsActive(self):
        return App.ActiveDocument is not None and find_case(App.ActiveDocument) is not None

    def Activated(self):
        case = find_case(App.ActiveDocument)
        default_path = "case.json"
        if case.CaseDirectory:
            default_path = str(Path(case.CaseDirectory) / case.CaseFile)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            Gui.getMainWindow(),
            "Export CTform Case",
            default_path,
            "CTform case (case.json)",
        )
        if not path:
            return
        try:
            output = write_case_json(case, path)
        except (OSError, ValueError, RuntimeError) as error:
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(), "CTform Case Export", str(error)
            )
            return
        case_data = json.loads(output.read_text(encoding="utf-8"))
        loadsteps_path = output.parent / case_data.get("loadStepsFile", "loadsteps.json")
        loadsteps_data = json.loads(loadsteps_path.read_text(encoding="utf-8"))
        messages = list(case_data.get("readinessIssues", ()))
        messages.extend(loadsteps_data.get("warnings", ()))
        if case_data.get("packageStatus") == "draft" and not messages:
            messages.append("The v2 package is staged for the future Core contract and is not solver-certified.")
        if messages:
            QtWidgets.QMessageBox.warning(
                Gui.getMainWindow(),
                "CTform Package Exported as Draft",
                "\n".join(f"- {message}" for message in messages),
            )
        App.Console.PrintMessage(f"CTform case exported to {output}\n")


class CreateRoleAssignmentCommand:
    """Assign the selected native object to a CTform workpiece or tool role."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Assign CTform Role",
            "ToolTip": "Assign the selected object as a workpiece or named tool",
        }

    def IsActive(self):
        return (
            App.ActiveDocument is not None
            and find_case(App.ActiveDocument) is not None
            and len(Gui.Selection.getSelection()) == 1
        )

    def Activated(self):
        case = find_case(App.ActiveDocument)
        target = Gui.Selection.getSelection()[0]
        role, accepted = QtWidgets.QInputDialog.getItem(
            Gui.getMainWindow(),
            "Assign CTform Role",
            "Role:",
            ["workpiece", "tool"],
            0,
            False,
        )
        if not accepted:
            return

        tool_name = ""
        if role == "tool":
            tool_name, accepted = QtWidgets.QInputDialog.getText(
                Gui.getMainWindow(),
                "Name CTform Tool",
                "Tool name:",
                text=target.Label,
            )
            if not accepted or not tool_name.strip():
                return

        assignment = make_role_assignment(
            App.ActiveDocument,
            analysis_for_case(case),
            target=target,
            role=role,
            tool_name=tool_name.strip(),
        )
        App.ActiveDocument.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(assignment)


def _selected_load_step():
    selection = Gui.Selection.getSelection()
    if len(selection) == 1 and isinstance(getattr(selection[0], "Proxy", None), CTformLoadStep):
        return selection[0]
    return None


class CreateLoadStepCommand:
    """Create a load-step object in the active CTform case."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Create Load Step",
            "ToolTip": "Create a CTform load step",
        }

    def IsActive(self):
        return App.ActiveDocument is not None and find_case(App.ActiveDocument) is not None

    def Activated(self):
        case = find_case(App.ActiveDocument)
        step = make_load_step(App.ActiveDocument, analysis_for_case(case))
        App.ActiveDocument.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(step)


class CloneLoadStepCommand:
    """Clone a selected CTform load step and its child conditions."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Clone Load Step",
            "ToolTip": "Duplicate the selected load step and its conditions",
        }

    def IsActive(self):
        step = _selected_load_step()
        return step is not None and find_case(step.Document) is not None

    def Activated(self):
        source_step = _selected_load_step()
        if source_step is None:
            return
        case = find_case(source_step.Document)
        doc = source_step.Document
        doc.openTransaction("Clone CTform load step")
        clone = clone_load_step(doc, analysis_for_case(case), source_step)
        doc.recompute()
        doc.commitTransaction()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(clone)


def _selected_condition_and_step():
    selection = Gui.Selection.getSelection()
    if len(selection) != 2:
        return None, None
    step = next(
        (obj for obj in selection if isinstance(getattr(obj, "Proxy", None), CTformLoadStep)),
        None,
    )
    condition = next((obj for obj in selection if obj is not step), None)
    if step is None or condition is None or fem_condition_category(condition) is None:
        return None, None
    case = find_case(step.Document)
    analysis = analysis_for_case(case) if case is not None else None
    analysis_member = condition in analysis.Group if analysis is not None else False
    step_member = condition in (getattr(step, "Group", ()) or ())
    if (
        case is None
        or condition.Document is not step.Document
        or not (analysis_member or step_member)
    ):
        return None, None
    kind = fem_condition_kind(condition)
    is_tool_condition = condition_targets_role(condition, case, "tool")
    if kind == "force" and not is_tool_condition:
        return None, None
    if is_tool_condition and kind not in ("fixed", "displacement", "force", "temperature"):
        return None, None
    return condition, step


class AttachConditionToStepCommand:
    """Move a native FEM condition into the selected CTform load-step folder."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Attach Selected Condition to Load Step",
            "ToolTip": "Add a selected native FEM condition to a CTform load-step folder",
        }

    def IsActive(self):
        condition, step = _selected_condition_and_step()
        return condition is not None and step is not None

    def Activated(self):
        condition, step = _selected_condition_and_step()
        if condition is None or step is None:
            return
        doc = step.Document
        doc.openTransaction("Attach FEM condition to CTform load step")
        attach_condition(step, condition)
        doc.recompute()
        doc.commitTransaction()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(step)


class DetachConditionFromStepCommand:
    """Return a selected step condition to the CTform analysis root."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Detach Condition from Load Step",
            "ToolTip": "Move the selected condition to the analysis root",
        }

    def IsActive(self):
        condition, step = _selected_condition_and_step()
        return condition is not None and condition in (getattr(step, "Group", ()) or ())

    def Activated(self):
        condition, step = _selected_condition_and_step()
        if condition is None or condition not in (getattr(step, "Group", ()) or ()):
            return
        doc = step.Document
        doc.openTransaction("Detach condition from CTform load step")
        detach_condition(step, condition)
        doc.recompute()
        doc.commitTransaction()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(condition)


Gui.addCommand("CTform_CreateCase", CreateCaseCommand())
Gui.addCommand("CTform_CreateSolver", CreateSolverCommand())
Gui.addCommand("CTform_CreateMaterial", CreateMaterialCommand())
Gui.addCommand("CTform_AssignMaterial", AssignMaterialCommand())
Gui.addCommand("CTform_AssignMesh", AssignMeshCommand())
Gui.addCommand("CTform_CreateContactPair", CreateContactPairCommand())
Gui.addCommand("CTform_ExportCase", ExportCaseCommand())
Gui.addCommand("CTform_AssignRole", CreateRoleAssignmentCommand())
Gui.addCommand("CTform_CreateLoadStep", CreateLoadStepCommand())
Gui.addCommand("CTform_CloneLoadStep", CloneLoadStepCommand())
Gui.addCommand("CTform_AttachConditionToStep", AttachConditionToStepCommand())
Gui.addCommand("CTform_DetachConditionFromStep", DetachConditionFromStepCommand())
Gui.addCommand("CTform_CreateAnalysis", CreateCaseCommand())
