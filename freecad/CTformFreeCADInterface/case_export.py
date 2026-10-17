# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Export CTform case settings to the existing case.json contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def case_to_dict(case: object) -> dict[str, Any]:
    """Convert CTform case settings into a Core-compatible case dictionary."""
    geometry = _geometry_from_roles(case)
    return {
        "simulationName": _value(case, "SimulationName", "ctform_case"),
        "process": _value(case, "Process", "forging"),
        "materialFile": _value(case, "MaterialFile", "material.json"),
        "loadStepsFile": _value(case, "LoadStepsFile", "loadsteps.json"),
        "thermalFile": _value(case, "ThermalFile", "thermal.json"),
        "simulation": {
            "modelingType": _value(case, "ModelingType", "axisymmetric"),
            "mechanicalFormulation": _value(case, "MechanicalFormulation", "flow"),
        },
        "geometry": geometry,
        "mesh": {},
        "contact": {
            "model": _value(case, "ContactModel", "node_to_segment"),
            "initialGap": _value(case, "InitialGap", 0.05),
            "augmentedLagrangeEnabled": _value(case, "AugmentedLagrangeEnabled", True),
            "penetrationTolerance": _value(case, "PenetrationTolerance", 1e-2),
            "gapTolerance": _value(case, "GapTolerance", 1e-6),
            "thermalContactEnabled": _value(case, "ThermalContactEnabled", False),
            "zBottom": _value(case, "ZBottom", 0.0),
        },
        "contactInterfaces": [],
        "output": {
            "directory": _value(case, "OutputDirectory", "results_case"),
            "vtkEvery": _value(case, "VtkEvery", 1),
            "nodalCsvEnabled": _value(case, "NodalCsvEnabled", False),
        },
        "run": {
            "geometryOnly": _value(case, "GeometryOnly", False),
            "targetCompression": _value(case, "TargetCompression", 7.0),
        },
        "ale": {"enabled": _value(case, "ALEEnabled", False)},
        "remesh": {"enabled": _value(case, "RemeshEnabled", False)},
        "solver": {},
    }


def write_case_json(case: object, path: str | Path) -> Path:
    """Write a CTform case.json file and update its case directory metadata."""
    output = Path(path)
    if output.suffix.lower() != ".json":
        output = output / "case.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(case_to_dict(case), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    loadsteps_path = output.parent / _value(case, "LoadStepsFile", "loadsteps.json")
    loadsteps_path.write_text(
        json.dumps(loadsteps_to_dict(case), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if hasattr(case, "CaseDirectory"):
        case.CaseDirectory = str(output.parent)
    if hasattr(case, "CaseFile"):
        case.CaseFile = output.name
    return output


def loadsteps_to_dict(case: object) -> dict[str, Any]:
    """Convert CTform load-step objects into the Core loadsteps.json schema."""
    steps = []
    for step in getattr(case, "LoadSteps", ()) or ():
        mechanical_bcs = [
            _condition_to_dict(condition, index + 1, thermal=False)
            for index, condition in enumerate(getattr(step, "MechanicalBCs", ()) or ())
        ]
        thermal_bcs = [
            _condition_to_dict(condition, index + 1, thermal=True)
            for index, condition in enumerate(getattr(step, "ThermalBCs", ()) or ())
        ]
        tools = [
            {
                "id": getattr(motion, "MotionId", 1000 + index),
                "name": getattr(motion, "ToolName", ""),
                "type": "Motion",
                "vx": getattr(motion, "Vx", 0.0),
                "vy": getattr(motion, "Vy", 0.0),
                "vz": getattr(motion, "Vz", 0.0),
                "active": getattr(motion, "Active", True),
                "initialTemperature": getattr(motion, "InitialTemperature", 293.15),
                "heatTransferCoefficient": getattr(motion, "HeatTransferCoefficient", 0.0),
            }
            for index, motion in enumerate(getattr(step, "ToolMotions", ()) or ())
        ]
        steps.append(
            {
                "id": getattr(step, "StepId", len(steps) + 1),
                "name": getattr(step, "StepName", "LoadStep"),
                "startTime": getattr(step, "StartTime", 0.0),
                "endTime": getattr(step, "EndTime", 1.0),
                "increments": getattr(step, "Increments", 1),
                "mechanicalBCs": mechanical_bcs,
                "thermalBCs": thermal_bcs,
                "tools": tools,
            }
        )

    if not steps:
        steps.append(
            {
                "id": 1,
                "name": "LoadStep",
                "startTime": 0.0,
                "endTime": 1.0,
                "increments": 1,
                "mechanicalBCs": [],
                "thermalBCs": [],
                "tools": [],
            }
        )
    return {"loadSteps": steps}


def _condition_to_dict(condition: object, identifier: int, thermal: bool) -> dict[str, Any]:
    """Adapt a CTform condition or native FEM condition to CTform JSON."""
    type_id = str(getattr(condition, "TypeId", "")).lower()
    if thermal:
        if "temperature" in type_id:
            condition_type = "Temperature"
        elif "heatflux" in type_id or "heat_flux" in type_id:
            condition_type = "HeatFlux"
        elif "radiation" in type_id:
            condition_type = "Radiation"
        else:
            condition_type = "Convection"
        value_names = ("Temperature", "HeatFlux", "Value", "AmbientTemperature")
    else:
        if "displacement" in type_id:
            condition_type = "Displacement"
        elif "force" in type_id:
            condition_type = "Force"
        elif "pressure" in type_id:
            condition_type = "Pressure"
        elif "symmetry" in type_id:
            condition_type = "Symmetry"
        else:
            condition_type = "Fixed"
        value_names = ("Value", "Displacement", "Force", "Pressure")

    value = next((getattr(condition, name) for name in value_names if hasattr(condition, name)), 0.0)
    return {
        "id": getattr(condition, "BCId", getattr(condition, "Id", identifier)),
        "name": getattr(condition, "Name", getattr(condition, "Label", "BoundaryCondition")),
        "type": condition_type,
        "axis": getattr(condition, "Axis", "Z"),
        "target": _condition_target(condition),
        "value": value,
        "active": getattr(condition, "Active", True),
    }


def _condition_target(condition: object) -> str:
    target = getattr(condition, "Target", "")
    if target:
        return str(target)
    references = getattr(condition, "References", ()) or ()
    if references:
        reference = references[0]
        if isinstance(reference, (tuple, list)) and reference:
            obj = reference[0]
            label = getattr(obj, "Label", getattr(obj, "Name", ""))
            subelements = reference[1] if len(reference) > 1 else ()
            suffix = ":" + ",".join(map(str, subelements)) if subelements else ""
            return f"{label}{suffix}"
    return "All"


def _value(case: object, name: str, default: Any) -> Any:
    value = getattr(case, name, default)
    return default if value is None else value


def _geometry_from_roles(case: object) -> dict[str, Any]:
    geometry: dict[str, Any] = {
        "workpiece": "",
        "dxf": {
            "format": "ascii",
            "coordinateMap": {"r": "x", "z": "y"},
            "symmetryAxis": "Z",
            "symmetryCoordinate": 0.0,
        },
        "tools": [],
    }
    for assignment in getattr(case, "RoleAssignments", ()) or ():
        role = getattr(assignment, "Role", "")
        source_file = getattr(assignment, "SourceFile", "")
        if role == "workpiece":
            geometry["workpiece"] = source_file
            continue
        if role != "tool":
            continue

        tool: dict[str, Any] = {
            "name": getattr(assignment, "ToolName", "") or assignment.Label,
            "type": "dxf_profile" if source_file.lower().endswith(".dxf") else "freecad_object",
            "file": source_file,
            "role": "tool",
        }
        tool_layer = getattr(assignment, "ToolLayer", "")
        if tool_layer:
            tool["toolLayer"] = tool_layer
        tool["initialOffsetZ"] = getattr(assignment, "InitialOffsetZ", 0.0)
        tool["symmetryR"] = getattr(assignment, "SymmetryR", 0.0)
        geometry["tools"].append(tool)
    return geometry
