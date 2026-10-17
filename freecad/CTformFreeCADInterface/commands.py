# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""FreeCAD commands exposed by the CTform workbench."""

import os
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from .analysis import find_case, make_case, make_solver
from .case_export import write_case_json
from .loadsteps import CTformLoadStep, make_load_step, make_mechanical_bc, make_tool_motion
from .roles import make_role_assignment


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

        FemGui.setActiveAnalysis(case.Analysis)
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
        output = write_case_json(case, path)
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
            case.Analysis,
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
        step = make_load_step(App.ActiveDocument, case.Analysis)
        App.ActiveDocument.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(step)


class AddMechanicalBCCommand:
    """Add a simple mechanical boundary condition to a selected load step."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Add Mechanical Boundary Condition",
            "ToolTip": "Add a mechanical condition to the selected load step",
        }

    def IsActive(self):
        return _selected_load_step() is not None

    def Activated(self):
        step = _selected_load_step()
        analysis = find_case(step.Document).Analysis
        bc_type, accepted = QtWidgets.QInputDialog.getItem(
            Gui.getMainWindow(),
            "Mechanical Boundary Condition",
            "Type:",
            ["Fixed", "Displacement", "Force", "Pressure"],
            0,
            False,
        )
        if not accepted:
            return
        axis, accepted = QtWidgets.QInputDialog.getItem(
            Gui.getMainWindow(), "Mechanical Boundary Condition", "Axis:", ["X", "Y", "Z"], 2, False
        )
        if not accepted:
            return
        target, accepted = QtWidgets.QInputDialog.getText(
            Gui.getMainWindow(), "Mechanical Boundary Condition", "Target:", text=""
        )
        if not accepted:
            return
        value, accepted = QtWidgets.QInputDialog.getDouble(
            Gui.getMainWindow(), "Mechanical Boundary Condition", "Value:", 0.0
        )
        if not accepted:
            return
        condition = make_mechanical_bc(App.ActiveDocument, analysis, step)
        condition.Type = bc_type
        condition.Axis = axis
        condition.Target = target
        condition.Value = value
        App.ActiveDocument.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(condition)


class AddToolMotionCommand:
    """Add named tool motion to a selected load step."""

    def GetResources(self):
        return {
            "Pixmap": _ICON,
            "MenuText": "Add Tool Motion",
            "ToolTip": "Add named tool motion to the selected load step",
        }

    def IsActive(self):
        return _selected_load_step() is not None

    def Activated(self):
        step = _selected_load_step()
        analysis = find_case(step.Document).Analysis
        tool_name, accepted = QtWidgets.QInputDialog.getText(
            Gui.getMainWindow(), "Tool Motion", "Tool name:", text=""
        )
        if not accepted or not tool_name.strip():
            return
        vz, accepted = QtWidgets.QInputDialog.getDouble(
            Gui.getMainWindow(), "Tool Motion", "Velocity Z:", 0.0
        )
        if not accepted:
            return
        motion = make_tool_motion(App.ActiveDocument, analysis, step)
        motion.ToolName = tool_name.strip()
        motion.Vz = vz
        App.ActiveDocument.recompute()
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(motion)


Gui.addCommand("CTform_CreateCase", CreateCaseCommand())
Gui.addCommand("CTform_CreateSolver", CreateSolverCommand())
Gui.addCommand("CTform_ExportCase", ExportCaseCommand())
Gui.addCommand("CTform_AssignRole", CreateRoleAssignmentCommand())
Gui.addCommand("CTform_CreateLoadStep", CreateLoadStepCommand())
Gui.addCommand("CTform_AddMechanicalBC", AddMechanicalBCCommand())
Gui.addCommand("CTform_AddToolMotion", AddToolMotionCommand())
Gui.addCommand("CTform_CreateAnalysis", CreateCaseCommand())
