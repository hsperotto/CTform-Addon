# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Export CTform case settings to the existing case.json contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .loadsteps import fem_condition_category
from .materials import material_readiness_issues, materials_to_dict
from .contacts import contact_pair_to_dict
from .gmsh_package import export_gmsh_mesh
from .geometry_export import export_role_geometry
from .json_export import dumps_si


SCHEMA_VERSION = 2
SI_UNITS = {
    "length": "m",
    "time": "s",
    "temperature": "K",
    "stress": "Pa",
    "pressure": "Pa",
    "force": "N",
    "energy": "J",
    "power": "W",
    "area": "m2",
    "heatFlux": "W/m2",
    "heatTransferCoefficient": "W/(m2 K)",
    "thermalExpansionCoefficient": "1/K",
    "strain": "1",
    "strainRate": "1/s",
    "density": "kg/m3",
    "specificHeat": "J/(kg K)",
    "conductivity": "W/(m K)",
}


def case_to_dict(
    case: object,
    mesh_info: dict[str, Any] | None = None,
    geometry_info: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Convert CTform case settings into a Core-compatible case dictionary."""
    package_version = int(_value(case, "PackageSchemaVersion", SCHEMA_VERSION))
    if package_version != SCHEMA_VERSION:
        raise ValueError(
            f"This addon writes package schema v{SCHEMA_VERSION}; "
            f"case requests unsupported schema v{package_version}"
        )
    geometry = _geometry_from_roles(case, geometry_info)
    material_catalog = materials_to_dict(case)
    return {
        "schemaVersion": package_version,
        "units": dict(SI_UNITS),
        "simulationName": _value(case, "SimulationName", "ctform_case"),
        "process": _value(case, "Process", "forging"),
        "materialsFile": _value(case, "MaterialsFile", "materials.json"),
        "loadStepsFile": _value(case, "LoadStepsFile", "loadsteps.json"),
        "thermalFile": _value(case, "ThermalFile", "thermal.json"),
        "simulation": {
            "modelingType": _value(case, "ModelingType", "axisymmetric"),
            "mechanicalFormulation": _value(case, "MechanicalFormulation", "flow"),
        },
        "geometry": geometry,
        "mesh": mesh_info or {},
        "contact": {
            "model": _value(case, "ContactModel", "node_to_segment"),
            "initialGap": _length_to_si(_value(case, "InitialGap", 0.05)),
            "augmentedLagrangeEnabled": _value(case, "AugmentedLagrangeEnabled", True),
            "penetrationTolerance": _length_to_si(_value(case, "PenetrationTolerance", 1e-2)),
            "gapTolerance": _length_to_si(_value(case, "GapTolerance", 1e-6)),
            "thermalContactEnabled": _value(case, "ThermalContactEnabled", False),
            "zBottom": _length_to_si(_value(case, "ZBottom", 0.0)),
        },
        "contactInterfaces": [
            contact_pair_to_dict(pair, (mesh_info or {}).get("physicalGroups"))
            for pair in (getattr(case, "ContactPairs", ()) or ())
        ],
        "conditionPrecedence": {
            "analysisRoot": "global",
            "loadStep": "local",
            "localOverridesGlobal": True,
        },
        "output": {
            "directory": _value(case, "OutputDirectory", "results_case"),
            "vtkEvery": _value(case, "VtkEvery", 1),
            "nodalCsvEnabled": _value(case, "NodalCsvEnabled", False),
        },
        "run": {
            "geometryOnly": _value(case, "GeometryOnly", False),
            "targetCompression": _length_to_si(_value(case, "TargetCompression", 7.0)),
        },
        "ale": {"enabled": _value(case, "ALEEnabled", False)},
        "remesh": {"enabled": _value(case, "RemeshEnabled", False)},
        "solver": {},
        "packageStatus": "draft",
        "readinessIssues": _readiness_issues(
            case, mesh_info, material_catalog, geometry_info
        ),
    }


def write_case_json(case: object, path: str | Path) -> Path:
    """Write the v2 package and update its case directory metadata."""
    output = Path(path)
    if output.suffix.lower() != ".json":
        output = output / "case.json"
    mesh_info = _export_workpiece_mesh(case, output.parent)
    geometry_info = _export_role_geometries(case, output.parent)
    case_data = case_to_dict(case, mesh_info, geometry_info)
    material_data = materials_to_dict(case)
    physical_groups = (mesh_info or {}).get("physicalGroups")
    thermal_data = thermal_to_dict(case, physical_groups)
    loadsteps_data = loadsteps_to_dict(case, physical_groups)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output, case_data)
    _write_json(output.parent / case_data["materialsFile"], material_data)
    _write_json(output.parent / case_data["thermalFile"], thermal_data)
    _write_json(output.parent / case_data["loadStepsFile"], loadsteps_data)

    if hasattr(case, "CaseDirectory"):
        case.CaseDirectory = str(output.parent)
    if hasattr(case, "CaseFile"):
        case.CaseFile = output.name
    return output


def _export_workpiece_mesh(case: object, package_directory: Path) -> dict[str, Any] | None:
    workpiece_roles = [
        assignment
        for assignment in (getattr(case, "RoleAssignments", ()) or ())
        if getattr(assignment, "Role", "") == "workpiece"
    ]
    if len(workpiece_roles) > 1:
        raise ValueError("CTform v2 currently supports exactly one workpiece role")
    if not workpiece_roles:
        return None
    mesh_object = getattr(workpiece_roles[0], "Mesh", None)
    if mesh_object is None:
        return None

    relative_path = Path(_value(case, "MeshFile", "workpiece.msh"))
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("MeshFile must be a relative path inside the case package")
    metadata = export_gmsh_mesh(
        mesh_object,
        package_directory / relative_path,
    )
    metadata["file"] = relative_path.as_posix()
    return metadata


def _export_role_geometries(
    case: object, package_directory: Path
) -> dict[int, dict[str, Any]]:
    geometry_info = {}
    roles = list(getattr(case, "RoleAssignments", ()) or ())
    workpieces = [role for role in roles if getattr(role, "Role", "") == "workpiece"]
    if len(workpieces) > 1:
        raise ValueError("CTform v2 currently supports one workpiece geometry role")
    for role in roles:
        role_type = str(getattr(role, "Role", ""))
        if role_type not in ("workpiece", "tool"):
            continue
        if role_type == "workpiece":
            relative_path = Path("geometry/workpiece.dxf")
        else:
            tool_id = str(getattr(role, "ToolId", ""))
            if not tool_id:
                raise ValueError(f"Tool role {role.Label!r} has no stable ToolId")
            relative_path = Path("geometry/tools") / f"{tool_id}.dxf"
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("Geometry output paths must stay inside the case package")
        info = export_role_geometry(role, package_directory / relative_path)
        info["file"] = relative_path.as_posix()
        geometry_info[id(role)] = info
    return geometry_info


def _readiness_issues(
    case: object,
    mesh_info: dict[str, Any] | None,
    material_catalog: dict[str, Any] | None = None,
    geometry_info: dict[int, dict[str, Any]] | None = None,
) -> list[str]:
    issues = []
    roles = list(getattr(case, "RoleAssignments", ()) or ())
    workpieces = [role for role in roles if getattr(role, "Role", "") == "workpiece"]
    tools = [role for role in roles if getattr(role, "Role", "") == "tool"]
    if len(workpieces) != 1:
        issues.append("Assign exactly one workpiece role.")
    if not mesh_info:
        issues.append("Assign and generate a 2D FEM/Gmsh mesh for the workpiece.")
    if not tools:
        issues.append("Assign at least one named tool role and define its contact participation.")
    if any(getattr(role, "Material", None) is None for role in roles):
        issues.append("Assign a CTform material to every workpiece and tool role.")
    if geometry_info is not None and any(id(role) not in geometry_info for role in roles):
        issues.append("Export an ASCII SI DXF profile for each geometry role.")
    if any(not getattr(role, "ToolId", "") for role in tools):
        issues.append("Regenerate or assign a stable ToolId to every named tool role.")
    if material_catalog is not None:
        issues.extend(material_readiness_issues(material_catalog))
    if not getattr(case, "ContactPairs", ()):
        issues.append("Define at least one explicit CTform contact pair.")
    if geometry_info is None and tools:
        issues.append("Export ASCII SI DXF profile files for the named tools.")
        if any(not getattr(role, "SourceFile", "") for role in tools):
            issues.append("Export a geometry reference for every tool role.")
    return issues


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_si(data, indent=2) + "\n", encoding="utf-8")


def thermal_to_dict(case: object, physical_groups=None) -> dict[str, Any]:
    """Write process thermal state; intrinsic material properties live in materials.json."""
    thermal_bcs = []
    for index, condition in enumerate(_root_conditions(case, "thermal")):
        if _condition_tool_name(condition, case):
            continue
        thermal_bcs.extend(
            _condition_to_dict(condition, index + 1, thermal=True,
                               physical_groups=physical_groups, scope="global")
        )
    return {
        "initialTemperature": {
            "workpiece": _temperature_to_si(_value(case, "WorkpieceInitialTemperature", 293.15)),
            "tools": _temperature_to_si(_value(case, "ToolInitialTemperature", 293.15)),
        },
        "thermalPlasticEfficiency": _value(case, "ThermalPlasticEfficiency", 0.9),
        "thermalFrictionEfficiency": _value(case, "ThermalFrictionEfficiency", 0.0),
        "frictionHeatPartitionToWorkpiece": _value(
            case, "FrictionHeatPartitionToWorkpiece", 1.0
        ),
        "frictionHeatLayerDepth": _length_to_si(_value(case, "FrictionHeatLayerDepth", 0.5)),
        "frictionHeatDistribution": _value(case, "FrictionHeatDistribution", "uniform"),
        "thermalBCs": thermal_bcs,
    }


def loadsteps_to_dict(case: object, physical_groups=None) -> dict[str, Any]:
    """Convert CTform load-step objects into the Core loadsteps.json schema."""
    root_mechanical = _root_conditions(case, "mechanical")
    root_thermal = _root_conditions(case, "thermal")
    warnings = []
    steps = []
    source_steps = list(getattr(case, "LoadSteps", ()) or ()) or [None]
    for step in source_steps:
        mechanical_bcs = []
        thermal_bcs = []
        local_mechanical = _step_conditions(step, "mechanical", "MechanicalBCs")
        local_thermal = _step_conditions(step, "thermal", "ThermalBCs")
        step_name = getattr(step, "StepName", "LoadStep")
        local_mechanical_records = []
        local_thermal_records = []
        tools = [
            {
                "id": getattr(motion, "MotionId", 1000 + index),
                "toolId": getattr(motion, "ToolId", ""),
                "name": getattr(motion, "ToolName", ""),
                "type": "Motion",
                "vx": getattr(motion, "Vx", 0.0),
                "vy": getattr(motion, "Vy", 0.0),
                "vz": getattr(motion, "Vz", 0.0),
                "active": getattr(motion, "Active", True),
                "scope": "step",
                "initialTemperature": getattr(motion, "InitialTemperature", 293.15),
                "heatTransferCoefficient": getattr(motion, "HeatTransferCoefficient", 0.0),
            }
            for index, motion in enumerate(_step_tool_motions(step))
        ]
        for index, condition in enumerate(root_mechanical):
            tool_data = _condition_tool_data(condition, case)
            tool_name = tool_data["name"] if tool_data else ""
            if not tool_name and "constraintforce" in _condition_type_name(condition):
                raise ValueError(
                    "CTform currently supports FEM force conditions only as force-controlled tool motion"
                )
            if tool_name:
                tools.append(
                    _tool_motion_to_dict(
                        condition, tool_name, step, 1000 + index, "global", tool_data["id"]
                    )
                )
            else:
                if "constraintforce" in _condition_type_name(condition):
                    raise ValueError(
                        "CTform currently supports FEM force conditions only as force-controlled tool motion"
                    )
                mechanical_bcs.extend(
                    _condition_to_dict(
                        condition,
                        index + 1,
                        thermal=False,
                        physical_groups=physical_groups,
                        scope="global",
                    )
                )
        for index, condition in enumerate(local_mechanical):
            tool_data = _condition_tool_data(condition, case)
            tool_name = tool_data["name"] if tool_data else ""
            if not tool_name and "constraintforce" in _condition_type_name(condition):
                raise ValueError(
                    "CTform currently supports FEM force conditions only as force-controlled tool motion"
                )
            if tool_name:
                tool_record = _tool_motion_to_dict(
                    condition, tool_name, step, 1000 + index, "step", tool_data["id"]
                )
                if any(item.get("name") == tool_name and item.get("scope") == "global" for item in tools):
                    warnings.append(
                        f"Step '{step_name}' local tool condition '{tool_record['name']}' "
                        "overrides a root-global tool condition."
                    )
                    tools = [
                        item
                        for item in tools
                        if not (item.get("name") == tool_name and item.get("scope") == "global")
                    ]
                tools.append(tool_record)
            else:
                local_mechanical_records.extend(
                    _condition_to_dict(
                        condition,
                        index + 1,
                        thermal=False,
                        physical_groups=physical_groups,
                        scope="step",
                    )
                )
        for index, condition in enumerate(root_thermal):
            tool_data = _condition_tool_data(condition, case)
            tool_name = tool_data["name"] if tool_data else ""
            if not tool_name:
                continue
            if "temperature" not in _condition_type_name(condition):
                raise ValueError("Only FEM temperature conditions can define global tool temperature")
            tools.append(
                _tool_motion_to_dict(
                    condition, tool_name, step, 2000 + index, "global", tool_data["id"]
                )
            )
        for index, condition in enumerate(local_thermal):
            tool_data = _condition_tool_data(condition, case)
            tool_name = tool_data["name"] if tool_data else ""
            if tool_name:
                if "temperature" not in _condition_type_name(condition):
                    raise ValueError("Only FEM temperature conditions can be applied to CTform tools")
                tool_record = _tool_motion_to_dict(
                    condition, tool_name, step, 1000 + index, "step", tool_data["id"]
                )
                if any(item.get("name") == tool_name and item.get("scope") == "global" for item in tools):
                    warnings.append(
                        f"Step '{step_name}' local tool temperature '{tool_name}' "
                        "overrides a root-global tool condition."
                    )
                    tools = [
                        item
                        for item in tools
                        if not (item.get("name") == tool_name and item.get("scope") == "global")
                    ]
                tools.append(tool_record)
            else:
                local_thermal_records.extend(
                    _condition_to_dict(
                        condition,
                        index + 1,
                        thermal=True,
                        physical_groups=physical_groups,
                        scope="step",
                    )
                )
        warnings.extend(_condition_override_warnings(
            root_mechanical, local_mechanical, case, step_name, False, physical_groups
        ))
        warnings.extend(_condition_override_warnings(
            root_thermal, local_thermal, case, step_name, True, physical_groups
        ))
        for record in local_mechanical_records:
            record["overridesGlobal"] = _overrides_any(record, root_mechanical, case, False, physical_groups)
        for record in local_thermal_records:
            record["overridesGlobal"] = _overrides_any(record, root_thermal, case, True, physical_groups)
        mechanical_bcs.extend(local_mechanical_records)
        thermal_bcs.extend(local_thermal_records)
        steps.append(
            {
                "id": getattr(step, "StepId", len(steps) + 1),
                "name": step_name,
                "startTime": getattr(step, "StartTime", 0.0),
                "endTime": getattr(step, "EndTime", 1.0),
                "increments": getattr(step, "Increments", 1),
                "mechanicalBCs": mechanical_bcs,
                "thermalBCs": thermal_bcs,
                "tools": tools,
            }
        )

    return {"loadSteps": steps, "warnings": sorted(set(warnings))}


def _root_conditions(case: object, category: str) -> list[object]:
    analysis = next(
        (
            parent
            for parent in (getattr(case, "InList", ()) or ())
            if getattr(parent, "TypeId", "") == "Fem::FemAnalysis"
        ),
        getattr(case, "Analysis", None),
    )
    return [
        condition
        for condition in (getattr(analysis, "Group", ()) or ())
        if fem_condition_category(condition) == category
        or category == "mechanical"
        and str(getattr(condition, "Type", ""))
        in ("Fixed", "Displacement", "Force", "Velocity", "Symmetry")
        or category == "thermal"
        and str(getattr(condition, "Type", ""))
        in ("Temperature", "HeatFlux", "Convection", "Radiation", "HeatGeneration")
    ]


def _unique_objects(objects: list[object]) -> list[object]:
    unique = []
    for obj in objects:
        if obj not in unique:
            unique.append(obj)
    return unique


def _condition_override_warnings(
    root_conditions: list[object],
    local_conditions: list[object],
    case: object,
    step_name: str,
    thermal: bool,
    physical_groups=None,
) -> list[str]:
    warnings = []
    for root_condition in root_conditions:
        root_tool = _condition_tool_name(root_condition, case)
        root_records = [] if root_tool else _condition_to_dict(
            root_condition, 0, thermal, physical_groups, "global"
        )
        for local_condition in local_conditions:
            local_tool = _condition_tool_name(local_condition, case)
            if root_tool or local_tool:
                overlaps = bool(root_tool and local_tool and root_tool == local_tool)
                root_name, local_name = root_tool, local_tool
                target_description = f"tool {root_tool}" if overlaps else ""
            else:
                local_records = _condition_to_dict(
                    local_condition, 0, thermal, physical_groups, "step"
                )
                overlaps = any(
                    _condition_records_overlap(root_record, local_record, thermal)
                    for root_record in root_records
                    for local_record in local_records
                )
                root_name = getattr(root_condition, "Label", "Global condition")
                local_name = getattr(local_condition, "Label", "Step condition")
                target_description = "overlapping target/DOF"
            if overlaps:
                warnings.append(
                    f"Step '{step_name}': local condition '{local_name}' overrides "
                    f"root-global condition '{root_name}' on {target_description}."
                )
    return warnings


def _overrides_any(
    local_record: dict[str, Any],
    root_conditions: list[object],
    case: object,
    thermal: bool,
    physical_groups=None,
) -> bool:
    for root_condition in root_conditions:
        if _condition_tool_name(root_condition, case):
            continue
        root_records = _condition_to_dict(
            root_condition, 0, thermal, physical_groups, "global"
        )
        if any(_condition_records_overlap(root_record, local_record, thermal) for root_record in root_records):
            return True
    return False


def _condition_records_overlap(
    root_record: dict[str, Any], local_record: dict[str, Any], thermal: bool
) -> bool:
    if thermal:
        root_type = root_record.get("type")
        local_type = local_record.get("type")
        if root_type != local_type and "Temperature" not in (root_type, local_type):
            return False
    else:
        root_axis = root_record.get("axis", "All")
        local_axis = local_record.get("axis", "All")
        if root_axis != "All" and local_axis != "All" and root_axis != local_axis:
            return False

    root_group = root_record.get("physicalGroupId")
    local_group = local_record.get("physicalGroupId")
    if root_group is not None and local_group is not None:
        return root_group == local_group
    if root_record.get("useZSelector") and local_record.get("useZSelector"):
        return abs(float(root_record.get("zSelector", 0.0)) - float(local_record.get("zSelector", 0.0))) < 1e-9
    root_target = str(root_record.get("target", "All"))
    local_target = str(local_record.get("target", "All"))
    return root_target == local_target or root_target == "All" or local_target == "All"


def _step_conditions(step: object, category: str, legacy_property: str) -> list[object]:
    conditions = []
    candidates = list(getattr(step, "Group", ()) or ())
    candidates.extend(getattr(step, legacy_property, ()) or ())
    for condition in candidates:
        legacy_type = str(getattr(condition, "Type", ""))
        legacy_category = (
            "mechanical"
            if legacy_type in ("Fixed", "Displacement", "Force", "Velocity", "Symmetry")
            else "thermal"
            if legacy_type in ("Temperature", "HeatFlux", "Convection", "Radiation", "HeatGeneration")
            else None
        )
        if (
            fem_condition_category(condition) == category
            or legacy_category == category
        ) and condition not in conditions:
            conditions.append(condition)
    return conditions


def _step_tool_motions(step: object) -> list[object]:
    motions = []
    candidates = [
        motion
        for motion in (getattr(step, "Group", ()) or ())
        if "ctformtoolmotion"
        in type(getattr(motion, "Proxy", None)).__name__.lower()
    ]
    candidates.extend(getattr(step, "ToolMotions", ()) or ())
    for motion in candidates:
        if motion not in motions:
            motions.append(motion)
    return motions


def _condition_to_dict(
    condition: object,
    identifier: int,
    thermal: bool,
    physical_groups=None,
    scope: str | None = None,
) -> list[dict[str, Any]]:
    """Adapt supported CTform or native FEM conditions to CTform JSON."""
    type_name = _condition_type_name(condition)
    targets = _condition_target_data(condition, physical_groups)
    if thermal:
        if "temperature" in type_name or getattr(condition, "Type", "") == "Temperature":
            condition_type = "Temperature"
            value_names = ("Temperature", "Value")
            value_unit = "K"
        elif "heatflux" in type_name or "heat_flux" in type_name or getattr(condition, "Type", "") == "HeatFlux":
            condition_type = "HeatFlux"
            value_names = ("HeatFlux", "Value")
            value_unit = "W/m^2"
        elif "bodyheatsource" in type_name or getattr(condition, "Type", "") == "HeatGeneration":
            condition_type = "HeatGeneration"
            value_names = ("HeatSource", "HeatGeneration", "Value")
            value_unit = "W/m^3"
        elif "radiation" in type_name:
            condition_type = "Radiation"
            value_names = ("Value",)
            value_unit = None
        elif "convection" in type_name:
            condition_type = "Convection"
            value_names = ("Value",)
            value_unit = None
        else:
            raise ValueError(f"Unsupported FEM thermal condition: {type_name}")
        axes = [("All", _first_numeric_value(condition, value_names, 0.0, value_unit))]
    else:
        legacy_type = getattr(condition, "Type", "")
        if "constraintfixed" in type_name or legacy_type == "Fixed":
            condition_type = "Fixed"
            axes = [("All", 0.0)]
        elif "displacement" in type_name or legacy_type == "Displacement":
            condition_type = "Displacement"
            axes = _displacement_components(condition)
        elif "force" in type_name or legacy_type == "Force":
            condition_type = "Force"
            axes = _force_components(condition)
        elif legacy_type == "Velocity":
            condition_type = "Velocity"
            axes = [
                (
                    _map_fem_axis(str(getattr(condition, "Axis", "Y"))),
                    _first_numeric_value(condition, ("Value",), 0.0, "m/s"),
                )
            ]
        elif legacy_type == "Symmetry":
            condition_type = "Symmetry"
            axes = [(str(getattr(condition, "Axis", "Z")), 0.0)]
        else:
            raise ValueError(f"Unsupported FEM mechanical condition: {type_name}")

    base_id = getattr(condition, "BCId", getattr(condition, "Id", identifier))
    name = getattr(condition, "Label", getattr(condition, "Name", "BoundaryCondition"))
    active = getattr(condition, "Active", True)
    output = []
    for component_index, (axis, value) in enumerate(axes):
        record_id = base_id if len(axes) == 1 else int(base_id) * 10 + component_index + 1
        for target_index, target in enumerate(targets):
            record = {
                "id": record_id + target_index,
                "name": name,
                "type": condition_type,
                "axis": axis,
                "value": value,
                "active": active,
            }
            if scope is not None:
                record["scope"] = scope
            if thermal:
                if condition_type in ("Convection", "Radiation"):
                    record["ambientTemperature"] = _first_numeric_value(
                        condition, ("AmbientTemperature", "Temperature"), 293.15, "K"
                    )
                    record["emissivity"] = _first_numeric_value(
                        condition, ("Emissivity",), 0.0
                    )
                if condition_type == "Convection":
                    record["filmCoefficient"] = _first_numeric_value(
                        condition, ("FilmCoefficient", "HeatTransferCoefficient"), 0.0, "W/m^2/K"
                    )
            record.update(target)
            output.append(record)
    return output


def _condition_type_name(condition: object) -> str:
    return " ".join(
        (
            str(getattr(condition, "TypeId", "")),
            type(getattr(condition, "Proxy", None)).__name__,
        )
    ).lower()


def _condition_target_data(condition: object, physical_groups=None) -> list[dict[str, Any]]:
    target = getattr(condition, "Target", "")
    if target:
        if physical_groups is not None and str(target) not in ("All", ""):
            group = next(
                (item for item in physical_groups if item["name"] == str(target)),
                None,
            )
            if group is None:
                raise ValueError(f"Condition references unknown physical group {target!r}")
            return [
                {
                    "physicalGroupId": group["id"],
                    "physicalGroup": group["name"],
                }
            ]
        return [
            {
                "target": str(target),
                "useZSelector": getattr(condition, "UseZSelector", False),
                "zSelector": _length_to_si(getattr(condition, "ZSelector", 0.0)),
            }
        ]
    references = getattr(condition, "References", ()) or ()
    if not references:
        return [{"target": "All", "useZSelector": False, "zSelector": 0.0}]

    selected_elements = []
    for reference in references:
        if not isinstance(reference, (tuple, list)) or not reference:
            continue
        obj = reference[0]
        subelements = reference[1] if len(reference) > 1 else ()
        if isinstance(subelements, str):
            subelements = (subelements,)
        selected_elements.extend((obj, element) for element in (subelements or ()))

    if not selected_elements:
        return [{"target": "All", "useZSelector": False, "zSelector": 0.0}]

    if physical_groups is not None:
        targets = []
        for _, element_name in selected_elements:
            group = next(
                (item for item in physical_groups if item["name"] == str(element_name)),
                None,
            )
            if group is None:
                raise ValueError(
                    f"Selected FEM subelement {element_name!r} has no exported Gmsh physical group"
                )
            targets.append(
                {"physicalGroupId": group["id"], "physicalGroup": group["name"]}
            )
        return _unique_target_dicts(targets)

    z_values = []
    for obj, element_name in selected_elements:
        shape = getattr(obj, "Shape", None)
        if shape is None or not hasattr(shape, "getElement"):
            raise ValueError(f"Cannot resolve FEM geometry reference {element_name!r}")
        element = shape.getElement(element_name)
        if getattr(element, "ShapeType", "") == "Face":
            return [{"target": "All", "useZSelector": False, "zSelector": 0.0}]
        bounds = getattr(element, "BoundBox", None)
        if bounds is None or bounds.YLength > 1e-7 or bounds.ZLength > 1e-7:
            raise ValueError(
                "CTform currently supports FEM edge targets only when they lie at a constant axial coordinate"
            )
        z_values.append(float(bounds.YMin))

    if max(z_values) - min(z_values) > 1e-7:
        raise ValueError("Selected FEM edges span multiple axial coordinates")
    return [{"target": "All", "useZSelector": True, "zSelector": _length_to_si(z_values[0])}]


def _unique_target_dicts(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = []
    for target in targets:
        if target not in unique:
            unique.append(target)
    return unique


def _first_numeric_value(
    condition: object,
    names: tuple[str, ...],
    default: float,
    unit: str | None = None,
) -> float:
    for name in names:
        if hasattr(condition, name):
            value = getattr(condition, name)
            if unit and hasattr(value, "getValueAs"):
                value = value.getValueAs(unit)
            elif hasattr(value, "Value"):
                value = value.Value
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return default


def _displacement_components(condition: object) -> list[tuple[str, float]]:
    components = []
    for fem_axis, core_axis in (("X", "X"), ("Y", "Z"), ("Z", "Y")):
        value_name = f"{fem_axis.lower()}Displacement"
        free_name = f"{fem_axis.lower()}Free"
        if hasattr(condition, value_name):
            if bool(getattr(condition, free_name, False)):
                continue
            value = _first_numeric_value(condition, (value_name,), 0.0, "m")
            if core_axis == "Y":
                if abs(value) > 1e-12:
                    raise ValueError(
                        "Out-of-plane FEM Z displacement is not supported by CTform 2D; "
                        "for XY sketch geometry, FEM X is radial and FEM Y is axial"
                    )
                continue
            components.append((core_axis, value))
    if components:
        return components
    value = _first_numeric_value(condition, ("Displacement", "Value"), 0.0, "m")
    axis = str(getattr(condition, "Axis", "Z")).upper()
    return [(_map_fem_axis(axis), value)]


def _force_components(condition: object) -> list[tuple[str, float]]:
    force = _first_numeric_value(condition, ("Force", "Value"), 0.0, "N")
    direction = getattr(condition, "Direction", None)
    if direction is not None and all(hasattr(direction, axis.lower()) for axis in "XYZ"):
        values = {"X": float(direction.x), "Y": float(direction.y), "Z": float(direction.z)}
        norm = sum(value * value for value in values.values()) ** 0.5
        if norm <= 1e-12:
            raise ValueError("FEM force direction is zero")
        values = {axis: force * value / norm for axis, value in values.items()}
        if abs(values["Z"]) > 1e-12:
            raise ValueError("Out-of-plane FEM force is not supported by CTform 2D")
        return [("X", values["X"]), ("Z", values["Y"])]
    axis = str(getattr(condition, "Axis", "Z")).upper()
    return [(_map_fem_axis(axis), force)]


def _map_fem_axis(axis: str) -> str:
    axis = axis.upper()
    if axis == "Y":
        return "Z"
    if axis == "Z":
        raise ValueError(
            "Out-of-plane FEM Z axis is not supported by CTform 2D; "
            "for XY sketch geometry, FEM X is radial and FEM Y is axial"
        )
    return axis


def _condition_tool_name(condition: object, case: object) -> str:
    tool_data = _condition_tool_data(condition, case)
    return tool_data["name"] if tool_data else ""


def _condition_tool_data(condition: object, case: object) -> dict[str, str] | None:
    references = getattr(condition, "References", ()) or ()
    referenced_objects = [
        reference[0]
        for reference in references
        if isinstance(reference, (tuple, list)) and reference
    ]
    for assignment in getattr(case, "RoleAssignments", ()) or ():
        target = getattr(assignment, "Target", None)
        if (
            getattr(assignment, "Role", "") == "tool"
            and target is not None
            and any(obj is target for obj in referenced_objects)
        ):
            return {
                "id": str(getattr(assignment, "ToolId", "")),
                "name": getattr(assignment, "ToolName", "") or assignment.Label,
            }
    return None


def _tool_motion_to_dict(
    condition: object,
    tool_name: str,
    step: object,
    identifier: int,
    scope: str = "step",
    tool_id: str = "",
) -> dict[str, Any]:
    type_name = _condition_type_name(condition)
    active = getattr(condition, "Active", True)
    duration = max(
        1e-12,
        float(getattr(step, "EndTime", 1.0)) - float(getattr(step, "StartTime", 0.0)),
    )
    if "displacement" in type_name:
        components = _displacement_components(condition)
        velocity = {"X": 0.0, "Z": 0.0}
        for axis, value in components:
            velocity[axis] = value / duration
        return {
            "id": identifier,
            "toolId": tool_id,
            "name": tool_name,
            "type": "Motion",
            "vx": velocity["X"],
            "vy": 0.0,
            "vz": velocity["Z"],
            "active": active,
            "scope": scope,
        }
    if "fixed" in type_name:
        return {
            "id": identifier,
            "toolId": tool_id,
            "name": tool_name,
            "type": "Motion",
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "active": active,
            "scope": scope,
        }
    if "temperature" in type_name:
        return {
            "id": identifier,
            "toolId": tool_id,
            "name": tool_name,
            "type": "Motion",
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "active": active,
            "scope": scope,
            "initialTemperature": _first_numeric_value(
                condition, ("Temperature", "Value"), 293.15, "K"
            ),
        }
    if "force" in type_name:
        components = _force_components(condition)
        axial_force = next((value for axis, value in components if axis == "Z"), 0.0)
        if abs(axial_force) <= 1e-12:
            raise ValueError("CTform force-controlled tool motion requires an axial FEM force")
        return {
            "id": identifier,
            "toolId": tool_id,
            "name": tool_name,
            "type": "Motion",
            "motion": {"type": "force", "axis": "Z", "value": axial_force},
            "forceTarget": abs(axial_force),
            "active": active,
            "scope": scope,
        }
    raise ValueError(f"FEM condition {type_name} cannot drive a CTform tool")


def _value(case: object, name: str, default: Any) -> Any:
    value = getattr(case, name, default)
    return default if value is None else value


def _geometry_from_roles(
    case: object, geometry_info: dict[int, dict[str, Any]] | None = None
) -> dict[str, Any]:
    geometry_info = geometry_info or {}
    geometry: dict[str, Any] = {
        "workpiece": None,
        "dxf": {
            "format": "ascii",
            "coordinateMap": {"r": "x", "z": "y"},
            "symmetryAxis": "Z",
            "symmetryCoordinate": 0.0,
            "lengthUnit": "m",
            "workpieceLayerMap": {},
        },
        "tools": [],
    }
    for assignment in getattr(case, "RoleAssignments", ()) or ():
        role = getattr(assignment, "Role", "")
        source_file = getattr(assignment, "SourceFile", "")
        export_info = geometry_info.get(id(assignment), {})
        material = getattr(assignment, "Material", None)
        material_id = getattr(material, "MaterialId", None) if material is not None else None
        if role == "workpiece":
            geometry["workpiece"] = {
                "file": export_info.get("file", source_file),
                "materialId": material_id,
            }
            geometry["dxf"]["workpieceLayerMap"] = {
                layer: layer for layer in export_info.get("layers", ())
            }
            continue
        if role != "tool":
            continue

        tool: dict[str, Any] = {
            "id": str(getattr(assignment, "ToolId", "")),
            "name": getattr(assignment, "ToolName", "") or assignment.Label,
            "type": "rigid",
            "file": export_info.get("file", source_file),
            "role": "tool",
            "materialId": material_id,
        }
        tool["toolLayer"] = getattr(assignment, "ToolLayer", "") or "ToolProfile"
        tool["initialOffsetZ"] = _length_to_si(getattr(assignment, "InitialOffsetZ", 0.0))
        tool["symmetryR"] = _length_to_si(getattr(assignment, "SymmetryR", 0.0))
        geometry["tools"].append(tool)
    return geometry


def _length_to_si(value: object) -> float:
    if hasattr(value, "getValueAs"):
        return float(value.getValueAs("m"))
    return float(value) * 1e-3


def _temperature_to_si(value: object) -> float:
    if hasattr(value, "getValueAs"):
        return float(value.getValueAs("K"))
    return float(value)
