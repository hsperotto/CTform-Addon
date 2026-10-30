# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Export CTform case settings to the existing case.json contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .analysis import find_solver
from .loadsteps import fem_condition_category
from .materials import material_readiness_issues, materials_to_dict
from .contacts import contact_pair_to_dict
from .gmsh_package import export_gmsh_mesh
from .geometry_export import export_component_geometry
from .json_export import dumps_si
from .properties import length_to_si


SCHEMA_VERSION = 2
# Set to True when Core's v2 ElastoPlasticIsotropic reads K, n and eps0 (Swift hardening).
# Core master does not read them yet; Cody's change is on agent/cm1-friction-tangent.
CORE_SWIFT_SUPPORTED = False
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
    solver: object | None = None,
) -> dict[str, Any]:
    """Convert case structure and Solver settings into the package manifest."""
    solver = solver or find_solver(case)
    package_version = int(_value(case, "PackageSchemaVersion", SCHEMA_VERSION))
    if package_version != SCHEMA_VERSION:
        raise ValueError(
            f"This addon writes package schema v{SCHEMA_VERSION}; "
            f"case requests unsupported schema v{package_version}"
        )
    geometry = _geometry_from_components(case, geometry_info)
    material_catalog = materials_to_dict(case)
    readiness_issues = _readiness_issues(
        case, mesh_info, material_catalog, geometry_info, solver
    )
    return {
        "schemaVersion": package_version,
        "units": dict(SI_UNITS),
        "simulationName": _value(case, "SimulationName", "ctform_case"),
        "process": _value(case, "Process", "forging"),
        "materialsFile": _value(case, "MaterialsFile", "materials.json"),
        "loadStepsFile": _value(case, "LoadStepsFile", "loadsteps.json"),
        "thermalFile": _value(case, "ThermalFile", "thermal.json"),
        "simulation": {
            "dimension": _value(solver, "Dimension", "2D"),
            "modelingType": _value(solver, "ModelingType", "axisymmetric"),
            "mechanicalFormulation": _value(solver, "MechanicalFormulation", "flow"),
        },
        "geometry": geometry,
        "mesh": mesh_info or {},
        "contact": {
            "model": _value(solver, "ContactModel", "node_to_segment"),
            "initialGap": length_to_si(_value(solver, "InitialGap", 0.05)),
            "augmentedLagrangeEnabled": _value(solver, "AugmentedLagrangeEnabled", True),
            "penetrationTolerance": length_to_si(_value(solver, "PenetrationTolerance", 1e-2)),
            "gapTolerance": length_to_si(_value(solver, "GapTolerance", 1e-6)),
            "thermalContactEnabled": _value(solver, "ThermalContactEnabled", False),
            "zBottom": length_to_si(_value(solver, "ZBottom", 0.0)),
        },
        "contactInterfaces": [
            contact_pair_to_dict(pair, (mesh_info or {}).get("physicalGroups"))
            for pair in (getattr(getattr(case, "Workpiece", None), "ContactPairs", ()) or ())
        ],
        "conditionPrecedence": {
            "analysisRoot": "global",
            "loadStep": "local",
            "localOverridesGlobal": True,
        },
        "output": {
            "directory": _value(solver, "OutputDirectory", "results_case"),
            "vtkEvery": _value(solver, "VtkEvery", 1),
            "nodalCsvEnabled": _value(solver, "NodalCsvEnabled", False),
        },
        "run": {
            "geometryOnly": _value(solver, "GeometryOnly", False),
            **_target_compression(solver),
            **_external_tools(solver),
        },
        "ale": {"enabled": _value(solver, "ALEEnabled", False)},
        "remesh": {"enabled": _value(solver, "RemeshEnabled", False)},
        "solver": {},
        "packageStatus": "ready" if not readiness_issues else "draft",
        "readinessIssues": readiness_issues,
    }


def write_case_json(case: object, path: str | Path) -> Path:
    """Write the v2 package and update its case directory metadata."""
    output = Path(path)
    if output.suffix.lower() != ".json":
        output = output / "case.json"
    mesh_info = _export_workpiece_mesh(case, output.parent)
    geometry_info = _export_component_geometries(case, output.parent)
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
    workpiece = getattr(case, "Workpiece", None)
    if workpiece is None:
        return None
    mesh_object = getattr(workpiece, "Mesh", None)
    if mesh_object is None:
        return None

    relative_path = Path(_value(workpiece, "MeshFile", "workpiece.msh"))
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("MeshFile must be a relative path inside the case package")
    structured = bool(_value(workpiece, "StructuredSheetMesh", False))
    structured_size = length_to_si(_value(workpiece, "StructuredElementSize", 0.25)) * 1e3 if structured else None
    metadata = export_gmsh_mesh(
        mesh_object,
        package_directory / relative_path,
        structured_element_size=structured_size,
    )
    metadata["file"] = relative_path.as_posix()
    return metadata


def _export_component_geometries(
    case: object, package_directory: Path
) -> dict[int, dict[str, Any]]:
    geometry_info = {}
    workpiece = getattr(case, "Workpiece", None)
    components = ([workpiece] if workpiece is not None else [])
    components.extend(getattr(case, "Tools", ()) or ())
    for component in components:
        if component is workpiece:
            relative_path = Path("geometry/workpiece.dxf")
        else:
            tool_id = str(getattr(component, "ToolId", ""))
            if not tool_id:
                raise ValueError(f"Tool {component.Label!r} has no stable ToolId")
            relative_path = Path("geometry/tools") / f"{tool_id}.dxf"
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("Geometry output paths must stay inside the case package")
        info = export_component_geometry(component, package_directory / relative_path)
        info["file"] = relative_path.as_posix()
        geometry_info[id(component)] = info
    return geometry_info


def _readiness_issues(
    case: object,
    mesh_info: dict[str, Any] | None,
    material_catalog: dict[str, Any] | None = None,
    geometry_info: dict[int, dict[str, Any]] | None = None,
    solver: object | None = None,
) -> list[str]:
    issues = []
    workpiece = getattr(case, "Workpiece", None)
    tools = list(getattr(case, "Tools", ()) or ())
    if workpiece is None:
        issues.append("Create one CTform Workpiece folder.")
    if not mesh_info:
        issues.append("Assign and generate a FEM/Gmsh mesh for the Workpiece.")
    if not tools:
        issues.append("Create at least one named Tool folder and define its contact participation.")
    components = ([workpiece] if workpiece is not None else []) + tools
    if any(getattr(component, "Material", None) is None for component in components):
        issues.append("Add a CTform material to the Workpiece and every Tool folder.")
    if geometry_info is not None and any(id(component) not in geometry_info for component in components):
        issues.append("Export an ASCII SI DXF profile for each component.")
    if any(not getattr(tool, "ToolId", "") for tool in tools):
        issues.append("Assign a stable ToolId to every named Tool folder.")
    if _duplicate_step_ids(getattr(case, "LoadSteps", ()) or ()):
        issues.append("Give every Load Step a unique StepId.")
    if material_catalog is not None:
        issues.extend(material_readiness_issues(material_catalog))
    if workpiece is None or not getattr(workpiece, "ContactPairs", ()):
        issues.append("Add at least one explicit contact pair to the Workpiece.")
    if solver is None:
        issues.append("Create a CTform Solver and configure its modeling and execution settings.")
    elif str(getattr(solver, "Dimension", "2D")) != "2D":
        issues.append("Current geometry and mesh export supports 2D Solver configurations only.")
    if geometry_info is None and tools:
        issues.append("Export ASCII SI DXF profile files for the Tools.")
    issues.extend(_core_v2_unsupported_issues(case, mesh_info, material_catalog, solver))
    return issues


def _core_v2_unsupported_issues(
    case: object,
    mesh_info: dict[str, Any] | None,
    material_catalog: dict[str, Any] | None,
    solver: object | None,
) -> list[str]:
    """Report features that Core's v2 reader rejects with an error."""
    issues = []
    if solver is not None and _value(solver, "RemeshEnabled", False):
        issues.append("Core v2 does not support remeshing yet; disable Remesh on the Solver.")
    element_types = set((mesh_info or {}).get("elementTypes") or ())
    if {"Tri3", "Quad4"} <= element_types:
        issues.append("Core v2 does not support meshes that mix Tri3 and Quad4 elements.")
    formulation = str(_value(solver, "MechanicalFormulation", "flow")) if solver is not None else "flow"
    if formulation == "displacement" and element_types and element_types != {"Quad4"}:
        issues.append(
            "The displacement formulation needs a pure Quad4 mesh; Core rejects Tri3 for it. "
            "Mesh the Workpiece with Quad4 elements."
        )
    if not CORE_SWIFT_SUPPORTED:
        for record in (material_catalog or {}).get("materials", ()):
            constitutive = record.get("constitutive", {})
            if constitutive.get("model") == "ElastoPlasticIsotropic" and "eps0" in constitutive.get("parameters", {}):
                issues.append(
                    f"Material {record.get('name', record.get('id'))!r} uses Swift hardening (K, n, eps0), "
                    "which Core master does not read yet; the export waits for the Core change."
                )
    groups = (mesh_info or {}).get("physicalGroups")
    steps = list(getattr(case, "LoadSteps", ()) or ())
    for step in steps:
        for condition in _step_conditions(step, "thermal", "ThermalBCs"):
            _check_workpiece_thermal(condition, case, issues)
            _check_whole_body_target(condition, case, groups, True, issues)
        for condition in _step_conditions(step, "mechanical", "MechanicalBCs"):
            _check_workpiece_force(condition, case, solver, issues)
            _check_whole_body_target(condition, case, groups, False, issues)
    for condition in _root_conditions(case, "thermal"):
        _check_workpiece_thermal(condition, case, issues)
        _check_whole_body_target(condition, case, groups, True, issues)
    for condition in _root_conditions(case, "mechanical"):
        _check_workpiece_force(condition, case, solver, issues)
        _check_whole_body_target(condition, case, groups, False, issues)
    return list(dict.fromkeys(issues))


def _check_whole_body_target(
    condition: object, case: object, groups, thermal: bool, issues: list[str]
) -> None:
    """Core applies a BC without a specific target to every node of the sheet.

    Mechanical BCs (fixed, displacement, symmetry, velocity) and surface thermal
    BCs (heat flux, convection, radiation) must name an edge; a whole-body
    Temperature or HeatGeneration is legitimate and is not reported.
    """
    if _condition_tool_data(condition, case) is not None:
        return
    type_name = _condition_type_name(condition)
    kind = str(getattr(condition, "Type", ""))
    if thermal:
        if "temperature" in type_name or "bodyheatsource" in type_name or kind in (
            "Temperature", "HeatGeneration"
        ):
            return
    elif "force" in type_name or kind == "Force":
        return  # reported by _check_workpiece_force
    try:
        targets = _condition_target_data(condition, groups)
    except ValueError:
        return  # unknown group: the export itself fails with a clear message
    by_name = {item["name"]: item for item in groups or ()}
    for target in targets:
        whole = target.get("target") == "All" and not target.get("useZSelector")
        group = by_name.get(target.get("physicalGroup", ""))
        if whole or (group is not None and group.get("dimension") == 2):
            issues.append(
                f"Condition {getattr(condition, 'Label', '')!r} is not tied to an edge of the "
                "Workpiece, so Core would apply it to every node of the sheet; select the edge "
                "it acts on."
            )
            return


def _workpiece_density(case: object) -> float | None:
    material = getattr(getattr(case, "Workpiece", None), "Material", None)
    density = _first_numeric_value(material, ("Density",), 0.0, "kg/m^3") if material else 0.0
    return density if density > 0.0 else None


def _check_workpiece_thermal(condition: object, case: object, issues: list[str]) -> None:
    if _condition_tool_data(condition, case) is not None:
        return
    type_name = _condition_type_name(condition)
    native_type = str(getattr(condition, "ConstraintType", ""))
    label = getattr(condition, "Label", "")
    if "temperature" in type_name and native_type == "CFlux":
        issues.append(
            f"Thermal condition {label!r}: Core v2 does not support concentrated heat flux (CFlux)."
        )
    if "bodyheatsource" in type_name:
        mode = str(getattr(condition, "Mode", ""))
        if mode == "Total Power":
            issues.append(
                f"Body heat source {label!r}: use Dissipation Rate; Core v2 needs W/m^3, not Total Power."
            )
        elif mode == "Dissipation Rate" and _workpiece_density(case) is None:
            issues.append(
                f"Body heat source {label!r}: the Workpiece material needs a density to convert W/kg."
            )


def _check_workpiece_force(
    condition: object, case: object, solver: object | None, issues: list[str]
) -> None:
    if "force" not in _condition_type_name(condition) and getattr(condition, "Type", "") != "Force":
        return
    label = getattr(condition, "Label", "")
    if _condition_tool_data(condition, case) is None:
        issues.append(
            f"Force condition {label!r}: forces are only allowed on Tools as the press force; "
            "remove it from the Workpiece."
        )
        return
    try:
        direction, _ = _tool_force_direction(condition)
    except ValueError:
        return
    if abs(direction[0]) <= 1e-9:
        return
    if str(_value(solver, "ModelingType", "axisymmetric")) == "axisymmetric":
        issues.append(
            f"Force condition {label!r}: an axisymmetric Tool force cannot have a radial "
            "component (a full ring carries no net radial force); use an axial direction."
        )
    else:
        issues.append(
            f"Force condition {label!r}: Core currently moves tools only along Z, so a Tool "
            "force with a radial component is not supported; use an axial direction."
        )


def _target_compression(solver: object | None) -> dict[str, Any]:
    """Workpiece compression target; omitted for sheet cases that run to the end of their steps."""
    if not _value(solver, "ExportTargetCompression", True):
        return {}
    return {"targetCompression": length_to_si(_value(solver, "TargetCompression", 7.0))}


def _external_tools(solver: object | None) -> dict[str, Any]:
    """Optional Gmsh executable and MMG folder; omitted when both are empty."""
    tools = {}
    gmsh = str(_value(solver, "GmshExecutable", "") or "").strip()
    mmg = str(_value(solver, "MmgDirectory", "") or "").strip()
    if gmsh:
        tools["gmsh"] = gmsh
    if mmg:
        tools["mmgDirectory"] = mmg
    return {"externalTools": tools} if tools else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_si(data, indent=2) + "\n", encoding="utf-8")


def thermal_to_dict(case: object, physical_groups=None) -> dict[str, Any]:
    """Write process thermal state; intrinsic material properties live in materials.json."""
    solver = find_solver(case)
    thermal_bcs = []
    for index, condition in enumerate(_root_conditions(case, "thermal")):
        if _condition_tool_name(condition, case):
            continue
        thermal_bcs.extend(
            _condition_to_dict(condition, index + 1, thermal=True,
                               physical_groups=physical_groups, scope="global",
                               density=_workpiece_density(case))
        )
    return {
        "thermalPlasticEfficiency": _value(solver, "ThermalPlasticEfficiency", 0.9),
        "thermalFrictionEfficiency": _value(solver, "ThermalFrictionEfficiency", 0.0),
        "frictionHeatPartitionToWorkpiece": _value(
            solver, "FrictionHeatPartitionToWorkpiece", 1.0
        ),
        "frictionHeatLayerDepth": length_to_si(_value(solver, "FrictionHeatLayerDepth", 0.5)),
        "frictionHeatDistribution": _value(solver, "FrictionHeatDistribution", "uniform"),
        "initialTemperature": {
            "workpiece": _value(solver, "InitialWorkpieceTemperature", 293.15),
            "tools": _value(solver, "InitialToolTemperature", 293.15),
        },
        "thermalBCs": thermal_bcs,
    }


def _motion_tool_id(motion: object, case: object) -> str:
    """Use the motion's ToolId, else look the tool up by ToolName."""
    tool_id = str(getattr(motion, "ToolId", "") or "")
    if tool_id:
        return tool_id
    name = getattr(motion, "ToolName", "")
    for tool in getattr(case, "Tools", ()) or ():
        if name and name in (getattr(tool, "ToolName", ""), getattr(tool, "Label", "")):
            return str(getattr(tool, "ToolId", ""))
    return ""


def _duplicate_step_ids(steps) -> list[int]:
    seen = set()
    duplicates = []
    for step in steps:
        if step is None:
            continue
        step_id = getattr(step, "StepId", None)
        if step_id in seen and step_id not in duplicates:
            duplicates.append(step_id)
        seen.add(step_id)
    return duplicates


def _check_unique_step_ids(steps) -> None:
    duplicates = _duplicate_step_ids(steps)
    if duplicates:
        raise ValueError(
            f"Load steps share StepId {', '.join(map(str, duplicates))}; give every step a unique StepId"
        )


def loadsteps_to_dict(case: object, physical_groups=None) -> dict[str, Any]:
    """Convert CTform load-step objects into the Core loadsteps.json schema."""
    root_mechanical = _root_conditions(case, "mechanical")
    root_thermal = _root_conditions(case, "thermal")
    warnings = []
    steps = []
    source_steps = list(getattr(case, "LoadSteps", ()) or ()) or [None]
    _check_unique_step_ids(source_steps)
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
                "toolId": _motion_tool_id(motion, case),
                "name": getattr(motion, "ToolName", ""),
                "type": "Motion",
                "vx": getattr(motion, "Vx", 0.0),
                "vy": getattr(motion, "Vy", 0.0),
                "vz": getattr(motion, "Vz", 0.0),
                "active": getattr(motion, "Active", True),
                "scope": "step",
                "heatTransferCoefficient": getattr(motion, "HeatTransferCoefficient", 0.0),
            }
            for index, motion in enumerate(_step_tool_motions(step))
        ]
        for index, condition in enumerate(root_mechanical):
            tool_data = _condition_tool_data(condition, case)
            tool_name = tool_data["name"] if tool_data else ""
            if tool_name:
                tools.append(
                    _tool_motion_to_dict(
                        condition, tool_name, step, 1000 + index, "global", tool_data["id"]
                    )
                )
            else:
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
            if tool_data is None:
                continue
            raise ValueError(
                f"CTform does not support thermal boundary conditions on Tool {tool_data['name']!r}"
            )
        for index, condition in enumerate(local_thermal):
            tool_data = _condition_tool_data(condition, case)
            if tool_data is not None:
                raise ValueError(
                    f"CTform does not support thermal boundary conditions on Tool {tool_data['name']!r}"
                )
            local_thermal_records.extend(
                _condition_to_dict(
                    condition,
                    index + 1,
                    thermal=True,
                    physical_groups=physical_groups,
                    scope="step",
                    density=_workpiece_density(case),
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
        # Root and step condition loops each count from 1000; renumber so every
        # tool record in a step is unique. Tools are matched by toolId, not id.
        for offset, record in enumerate(tools):
            record["id"] = 1000 + offset
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
    density: float | None = None,
) -> list[dict[str, Any]]:
    """Adapt supported CTform or native FEM conditions to CTform JSON.

    ``density`` (kg/m^3) converts a native body heat source given in W/kg to
    Core's W/m^3; without it the W/kg value is kept, which only target/DOF
    comparisons may rely on.
    """
    type_name = _condition_type_name(condition)
    targets = _condition_target_data(condition, physical_groups)
    if thermal:
        native_type = str(getattr(condition, "ConstraintType", ""))
        if "temperature" in type_name or getattr(condition, "Type", "") == "Temperature":
            if native_type == "CFlux":
                raise ValueError(
                    f"Temperature condition {getattr(condition, 'Label', '')!r} uses CFlux "
                    "(concentrated heat flux), which CTform Core does not support; "
                    "use a Heat Flux condition instead"
                )
            condition_type = "Temperature"
            value_names = ("Temperature", "Value")
            value_unit = "K"
        elif (
            "heatflux" in type_name or "heat_flux" in type_name
            or getattr(condition, "Type", "") == "HeatFlux"
        ) and native_type in ("", "DFlux"):
            condition_type = "HeatFlux"
            value_names = ("DFlux", "HeatFlux", "Value")
            value_unit = "W/m^2"
        elif "heatflux" in type_name and native_type == "Convection":
            condition_type = "Convection"
            value_names = ()
            value_unit = None
        elif "heatflux" in type_name and native_type == "Radiation":
            condition_type = "Radiation"
            value_names = ()
            value_unit = None
        elif "bodyheatsource" in type_name or getattr(condition, "Type", "") == "HeatGeneration":
            condition_type = "HeatGeneration"
            value_names = ("HeatSource", "HeatGeneration", "Value")
            value_unit = "W/m^3"
            mode = str(getattr(condition, "Mode", ""))
            if mode == "Total Power":
                raise ValueError(
                    f"Body heat source {getattr(condition, 'Label', '')!r} uses Total Power; "
                    "CTform Core needs a volumetric rate, so switch it to Dissipation Rate"
                )
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
        value = _first_numeric_value(condition, value_names, 0.0, value_unit)
        if condition_type == "HeatGeneration" and str(getattr(condition, "Mode", "")) == "Dissipation Rate":
            rate = _first_numeric_value(condition, ("DissipationRate",), 0.0, "W/kg")
            value = rate * density if density is not None else rate
        axes = [("All", value)]
    else:
        legacy_type = getattr(condition, "Type", "")
        if "constraintfixed" in type_name or legacy_type == "Fixed":
            condition_type = "Fixed"
            axes = [("All", 0.0)]
        elif "displacement" in type_name or legacy_type == "Displacement":
            condition_type = "Displacement"
            axes = _displacement_components(condition)
        elif "force" in type_name or legacy_type == "Force":
            # Core takes forces only as tool motion; the readiness check reports
            # this condition, so it is not exported as a workpiece Force BC.
            return []
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
                        condition, ("AmbientTemp", "AmbientTemperature", "Temperature"), 293.15, "K"
                    )
                    record["emissivity"] = _first_numeric_value(
                        condition, ("Emissivity",), 0.0
                    )
                if condition_type == "Convection":
                    record["filmCoefficient"] = _first_numeric_value(
                        condition, ("FilmCoef", "FilmCoefficient", "HeatTransferCoefficient"),
                        0.0, "W/m^2/K"
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
                "zSelector": length_to_si(getattr(condition, "ZSelector", 0.0)),
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
    return [{"target": "All", "useZSelector": True, "zSelector": length_to_si(z_values[0])}]


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
    direction = getattr(condition, "DirectionVector", None)
    if direction is None:
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


def _tool_force_direction(condition: object) -> tuple[list[float], float]:
    """Return (unit direction [dx, 0, dz] in Core coordinates, magnitude in N).

    The direction comes from the FEM DirectionVector, which already includes
    Reversed; FEM X is Core X (radial) and FEM Y is Core Z (axial).
    """
    components = dict(_force_components(condition))
    fx, fz = components.get("X", 0.0), components.get("Z", 0.0)
    magnitude = (fx * fx + fz * fz) ** 0.5
    if magnitude <= 1e-12:
        raise ValueError(
            f"Force condition {getattr(condition, 'Label', '')!r} on a Tool needs a non-zero force"
        )
    return [fx / magnitude, 0.0, fz / magnitude], magnitude


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
    for tool in getattr(case, "Tools", ()) or ():
        target = getattr(tool, "Shape", None)
        if target is not None and any(obj is target for obj in referenced_objects):
            return {
                "id": str(getattr(tool, "ToolId", "")),
                "name": getattr(tool, "ToolName", "") or tool.Label,
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
    if "force" in type_name:
        direction, magnitude = _tool_force_direction(condition)
        return {
            "id": identifier,
            "toolId": tool_id,
            "name": tool_name,
            "type": "Motion",
            "motion": {"type": "force", "direction": direction, "value": magnitude},
            "active": active,
            "scope": scope,
        }
    raise ValueError(f"FEM condition {type_name} cannot drive a CTform tool")


def _value(case: object, name: str, default: Any) -> Any:
    value = getattr(case, name, default)
    return default if value is None else value


def _geometry_from_components(
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
    workpiece = getattr(case, "Workpiece", None)
    if workpiece is not None:
        export_info = geometry_info.get(id(workpiece), {})
        material = getattr(workpiece, "Material", None)
        material_id = getattr(material, "MaterialId", None) if material is not None else None
        geometry["workpiece"] = {
            "file": export_info.get("file", "geometry/workpiece.dxf"),
            "materialId": material_id,
        }
        geometry["dxf"]["workpieceLayerMap"] = {
            layer: layer for layer in export_info.get("layers", ())
        }
    for tool_component in getattr(case, "Tools", ()) or ():
        export_info = geometry_info.get(id(tool_component), {})
        material = getattr(tool_component, "Material", None)
        material_id = getattr(material, "MaterialId", None) if material is not None else None
        tool: dict[str, Any] = {
            "id": str(getattr(tool_component, "ToolId", "")),
            "name": getattr(tool_component, "ToolName", "") or tool_component.Label,
            "type": "rigid",
            "file": export_info.get(
                "file", f"geometry/tools/{getattr(tool_component, 'ToolId', '')}.dxf"
            ),
            "materialId": material_id,
        }
        tool["toolLayer"] = getattr(tool_component, "ToolLayer", "") or "ToolProfile"
        tool["initialOffsetZ"] = length_to_si(getattr(tool_component, "InitialOffsetZ", 0.0))
        tool["symmetryR"] = length_to_si(getattr(tool_component, "SymmetryR", 0.0))
        geometry["tools"].append(tool)
    return geometry

