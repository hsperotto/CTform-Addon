# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""CTform-owned material definitions and catalog serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .identifiers import readable_id
from .viewproviders import attach_view_provider
from .properties import add_property


MATERIAL_MODELS = (
    "HenselSpittel",
    "Hollomon",
    "NortonHoffViscoplastic",
    "ElastoPlasticIsotropic",
    "ElasticIsotropic",
    "TabulatedFlowStress",
)


class CTformMaterial:
    """Editable CTform thermomechanical material record."""

    def __init__(self, obj):
        self.Object = obj
        self._add_properties()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def _add_properties(self):
        obj = self.Object
        add_property(obj, "MaterialId", "App::PropertyString", "Identity", "")
        add_property(obj, "MaterialName", "App::PropertyString", "Identity", "New CTform Material")
        add_property(obj, "Model", "App::PropertyEnumeration", "Constitutive", list(MATERIAL_MODELS))
        add_property(obj, "HenselSpittelA", "App::PropertyPressure", "Hensel-Spittel", 0.0)
        for name in ("HenselSpittelM1", "HenselSpittelM2", "HenselSpittelM3", "HenselSpittelM4"):
            add_property(obj, name, "App::PropertyFloat", "Hensel-Spittel", 0.0)
        add_property(obj, "HollomonK", "App::PropertyPressure", "Hollomon", 0.0)
        for name in ("HollomonN", "HollomonEps0", "HollomonRateExponent"):
            add_property(obj, name, "App::PropertyFloat", "Hollomon", 0.0)
        add_property(obj, "NortonHoffK", "App::PropertyPressure", "Norton-Hoff", 0.0)
        add_property(obj, "NortonHoffM", "App::PropertyFloat", "Norton-Hoff", 0.0)
        add_property(obj, "YieldStress", "App::PropertyPressure", "Elastoplastic", 0.0)
        add_property(obj, "HardeningModulus", "App::PropertyPressure", "Elastoplastic", 0.0)
        # Swift hardening: sigma_y = K (eps0 + epsP)^n with eps0 = (Rp0.2 / K)^(1/n).
        add_property(obj, "SwiftK", "App::PropertyPressure", "Elastoplastic", 0.0)
        add_property(obj, "SwiftN", "App::PropertyFloat", "Elastoplastic", 0.0)
        add_property(obj, "YieldStrength02", "App::PropertyPressure", "Elastoplastic", 0.0)
        add_property(obj, "YoungModulus", "App::PropertyPressure", "Elastic", 0.0)
        add_property(obj, "PoissonRatio", "App::PropertyFloat", "Elastic", 0.3)
        add_property(obj, "Density", "App::PropertyDensity", "Thermal", 0.0)
        add_property(
            obj,
            "ThermalExpansionCoefficient",
            "App::PropertyThermalExpansionCoefficient",
            "Thermal",
            0.0,
        )
        add_property(obj, "ThermalConductivity", "App::PropertyThermalConductivity", "Thermal", 0.0)
        add_property(obj, "SpecificHeat", "App::PropertySpecificHeat", "Thermal", 0.0)
        for name in (
            "YoungModulusTableJSON",
            "ConductivityTableJSON",
            "SpecificHeatTableJSON",
            "FlowStressTableJSON",
        ):
            add_property(obj, name, "App::PropertyString", "Temperature Tables", "[]")

    def onDocumentRestored(self, obj=None):
        if obj is not None:
            self.Object = obj
        self._add_properties()


def ensure_material_library(doc, analysis, case):
    """Return the single case-owned CTform material catalog folder."""
    library = getattr(case, "MaterialLibrary", None)
    if library is not None:
        return library
    library = doc.addObject("App::DocumentObjectGroup", "CTformMaterials")
    library.Label = "CTform Materials"
    analysis.addObject(library)
    case.MaterialLibrary = library
    return library


def materials_in_case(case) -> list[Any]:
    library = getattr(case, "MaterialLibrary", None)
    return [
        material
        for material in (getattr(library, "Group", ()) or ())
        if type(getattr(material, "Proxy", None)).__name__ == "CTformMaterial"
    ]


def make_material(
    doc,
    analysis,
    case,
    material_name="New CTform Material",
    component=None,
    record: dict[str, Any] | None = None,
):
    """Create one shared case material, optionally importing a complete record."""
    library = ensure_material_library(doc, analysis, case)
    material_name = str(material_name).strip() or "New CTform Material"
    existing = materials_in_case(case)
    material_id = readable_id(
        material_name,
        (getattr(material, "MaterialId", "") for material in existing),
        fallback="material",
    )
    obj = doc.addObject("App::FeaturePython", "CTformMaterial")
    obj.Proxy = CTformMaterial(obj)
    obj.MaterialName = material_name
    obj.MaterialId = material_id
    obj.Label = f"CTform Material: {material_name}"
    library.addObject(obj)
    if record is not None:
        _apply_material_record(obj, record)
    if component is not None:
        component.Material = obj
    attach_view_provider(obj)
    return obj


def import_material_catalog(doc, analysis, case, path: str | Path) -> list[object]:
    """Import complete material records from a CTform materials.json catalog."""
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    records = data.get("materials") if isinstance(data, dict) else None
    if not isinstance(records, list) or not records:
        raise ValueError("Select a CTform materials.json file with a non-empty materials list")

    validated_records = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each imported material must be a JSON object")
        name = str(record.get("name", "")).strip()
        if not name or not all(section in record for section in ("constitutive", "elastic", "thermal")):
            raise ValueError("Each imported material needs a name, constitutive, elastic, and thermal data")
        if not all(isinstance(record[section], dict) for section in ("constitutive", "elastic", "thermal")):
            raise ValueError(f"Material {name!r} has malformed constitutive, elastic, or thermal data")
        model = record["constitutive"].get("model")
        if model not in MATERIAL_MODELS:
            raise ValueError(f"Unsupported CTform material model in imported catalog: {model}")
        issues = material_readiness_issues({"materials": [record]})
        if issues:
            raise ValueError("Imported material is incomplete: " + " ".join(issues))
        validated_records.append(record)

    existing = materials_in_case(case)
    imported = []
    for record in validated_records:
        name = str(record["name"]).strip()
        source_record = dict(record)
        source_record.pop("id", None)
        duplicate = next(
            (
                material
                for material in existing
                if _record_without_id(material_to_dict(material)) == source_record
            ),
            None,
        )
        if duplicate is not None:
            imported.append(duplicate)
            continue
        material = make_material(doc, analysis, case, name, record=record)
        existing.append(material)
        imported.append(material)
    return imported


def _record_without_id(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "id"}


def _apply_material_record(material, record: dict[str, Any]) -> None:
    constitutive = record["constitutive"]
    model = str(constitutive["model"])
    if model not in MATERIAL_MODELS:
        raise ValueError(f"Unsupported CTform material model in imported catalog: {model}")
    material.Model = model
    parameters = constitutive.get("parameters", {})
    parameter_fields = {
        "HenselSpittel": {
            "A": ("HenselSpittelA", "Pa"),
            "m1": ("HenselSpittelM1", None),
            "m2": ("HenselSpittelM2", None),
            "m3": ("HenselSpittelM3", None),
            "m4": ("HenselSpittelM4", None),
        },
        "Hollomon": {
            "K": ("HollomonK", "Pa"),
            "n": ("HollomonN", None),
            "eps0": ("HollomonEps0", None),
            "mRate": ("HollomonRateExponent", None),
        },
        "NortonHoffViscoplastic": {
            "K": ("NortonHoffK", "Pa"),
            "m": ("NortonHoffM", None),
        },
        "ElastoPlasticIsotropic": {
            "yieldStress": ("YieldStress", "Pa"),
            "hardeningModulus": ("HardeningModulus", "Pa"),
        },
    }
    for key, (property_name, unit) in parameter_fields.get(model, {}).items():
        if key in parameters:
            _set_imported_value(material, property_name, parameters[key], unit)
    if model == "ElastoPlasticIsotropic" and "K" in parameters:
        _set_imported_value(material, "SwiftK", parameters["K"], "Pa")
        material.SwiftN = float(parameters.get("n", 0.0))
        if "yieldStrength02" in parameters:
            yield_02 = float(parameters["yieldStrength02"])
        elif "eps0" in parameters:
            # Rp0.2 = K * eps0^n is the inverse of swift_eps0.
            yield_02 = float(parameters["K"]) * float(parameters["eps0"]) ** float(parameters["n"])
        else:
            yield_02 = 0.0
        _set_imported_value(material, "YieldStrength02", yield_02, "Pa")

    elastic = record["elastic"]
    _set_imported_value(material, "YoungModulus", elastic.get("youngModulus", 0.0), "Pa")
    material.PoissonRatio = float(elastic.get("poissonRatio", 0.3))
    thermal = record["thermal"]
    for key, property_name, unit in (
        ("density", "Density", "kg/m^3"),
        ("thermalExpansionCoefficient", "ThermalExpansionCoefficient", "1/K"),
        ("thermalConductivity", "ThermalConductivity", "W/m/K"),
        ("specificHeat", "SpecificHeat", "J/kg/K"),
    ):
        if key in thermal:
            _set_imported_value(material, property_name, thermal[key], unit)

    for source, table_name, property_name in (
        (elastic, "youngModulusTable", "YoungModulusTableJSON"),
        (thermal, "conductivityTable", "ConductivityTableJSON"),
        (thermal, "specificHeatTable", "SpecificHeatTableJSON"),
        (record, "flowStressTable", "FlowStressTableJSON"),
    ):
        value = source.get(table_name)
        if value is not None:
            setattr(material, property_name, json.dumps(value))


def _set_imported_value(material, property_name: str, value, unit: str | None) -> None:
    if unit is None:
        setattr(material, property_name, float(value))
        return
    try:
        import FreeCAD as App
    except ImportError:
        setattr(material, property_name, float(value))
        return
    setattr(material, property_name, App.Units.Quantity(f"{float(value)} {unit}"))


def materials_to_dict(case: object) -> dict[str, Any]:
    """Serialize unique materials referenced by the Workpiece and Tool folders."""
    components = [getattr(case, "Workpiece", None)]
    components.extend(getattr(case, "Tools", ()) or ())
    materials = []
    for component in components:
        material = getattr(component, "Material", None) if component is not None else None
        if material is not None and material not in materials:
            materials.append(material)

    records = []
    ids: dict[str, object] = {}
    for material in materials:
        record = material_to_dict(material)
        material_id = record["id"]
        if material_id in ids and ids[material_id] is not material:
            raise ValueError(f"Duplicate CTform material ID: {material_id}")
        ids[material_id] = material
        if all(existing["id"] != material_id for existing in records):
            records.append(record)
    return {"materials": records}


def material_to_dict(material: object) -> dict[str, Any]:
    """Serialize one CTform material object to the v2 catalog record."""
    model = str(getattr(material, "Model", "HenselSpittel"))
    parameters = _constitutive_parameters(material, model)
    elastic: dict[str, Any] = {
        "youngModulus": _quantity_si(material, "YoungModulus", "Pa"),
        "poissonRatio": float(getattr(material, "PoissonRatio", 0.3)),
    }
    young_table = _json_array(material, "YoungModulusTableJSON")
    if young_table:
        elastic["youngModulusTable"] = young_table

    thermal: dict[str, Any] = {
        "density": _quantity_si(material, "Density", "kg/m^3"),
        "thermalExpansionCoefficient": _quantity_si(
            material, "ThermalExpansionCoefficient", "1/K"
        ),
        "thermalConductivity": _quantity_si(material, "ThermalConductivity", "W/m/K"),
        "specificHeat": _quantity_si(material, "SpecificHeat", "J/kg/K"),
    }
    conductivity_table = _json_array(material, "ConductivityTableJSON")
    specific_heat_table = _json_array(material, "SpecificHeatTableJSON")
    if conductivity_table:
        thermal["conductivityTable"] = conductivity_table
    if specific_heat_table:
        thermal["specificHeatTable"] = specific_heat_table

    record: dict[str, Any] = {
        "id": str(getattr(material, "MaterialId", "")),
        "name": str(getattr(material, "MaterialName", getattr(material, "Label", "Material"))),
        "constitutive": {"model": model, "parameters": parameters},
        "elastic": elastic,
        "thermal": thermal,
    }
    flow_table = _json_array(material, "FlowStressTableJSON")
    if flow_table:
        record["flowStressTable"] = flow_table
    if not record["id"]:
        raise ValueError(f"CTform material {record['name']!r} has no stable material ID")
    return record


def material_readiness_issues(catalog: dict[str, Any]) -> list[str]:
    """Return missing/invalid physical fields that prevent a runnable material."""
    issues = []
    for material in catalog.get("materials", ()):
        name = material.get("name", material.get("id", "Unnamed material"))
        model = material.get("constitutive", {}).get("model", "")
        parameters = material.get("constitutive", {}).get("parameters", {})
        elastic = material.get("elastic", {})
        thermal = material.get("thermal", {})
        if model == "HenselSpittel" and parameters.get("A", 0.0) <= 0.0:
            issues.append(f"Material {name!r} needs a positive Hensel-Spittel A coefficient.")
        elif model in ("Hollomon", "NortonHoffViscoplastic") and parameters.get("K", 0.0) <= 0.0:
            issues.append(f"Material {name!r} needs a positive flow-stress K coefficient.")
        elif model == "TabulatedFlowStress" and not material.get("flowStressTable"):
            issues.append(f"Material {name!r} needs a non-empty flow-stress table.")
        elif model == "TabulatedFlowStress" and not _is_complete_flow_stress_grid(
            material["flowStressTable"]
        ):
            issues.append(
                f"Material {name!r}: the flow-stress table must list every temperature x "
                "strain rate x strain combination exactly once."
            )
        elif model == "ElastoPlasticIsotropic" and "K" in parameters:
            if not (parameters.get("K", 0.0) > 0.0 and 0.0 < parameters.get("n", 0.0) < 1.0):
                issues.append(f"Material {name!r} needs K > 0 and 0 < n < 1 for Swift hardening.")
            elif parameters.get("eps0", 0.0) <= 0.0 and parameters.get("yieldStrength02", 0.0) <= 0.0:
                issues.append(f"Material {name!r} needs eps0 or Rp0.2 for Swift hardening.")
        if elastic.get("youngModulus", 0.0) <= 0.0:
            issues.append(f"Material {name!r} needs a positive Young's modulus.")
        poisson_ratio = elastic.get("poissonRatio", 0.3)
        if not -1.0 < poisson_ratio < 0.5:
            issues.append(f"Material {name!r} has an invalid Poisson ratio.")
        if thermal.get("density", 0.0) <= 0.0:
            issues.append(f"Material {name!r} needs a positive density.")
    return issues


def _is_complete_flow_stress_grid(table) -> bool:
    """Core interpolates on a rectilinear T x rate x strain grid with no gaps or repeats."""
    try:
        keys = [
            (float(point["temperature"]), float(point["strainRate"]), float(point["strain"]))
            for point in table
        ]
    except (KeyError, TypeError, ValueError):
        return False
    axes = [len({key[index] for key in keys}) for index in range(3)]
    return len(set(keys)) == len(keys) == axes[0] * axes[1] * axes[2]


def swift_eps0(yield_strength_02: float, K: float, n: float) -> float:
    """Return the Swift pre-strain eps0 = (Rp0.2 / K)^(1/n).

    With this eps0, K (eps0 + epsP)^n equals Rp0.2 at zero plastic strain, which is
    the convention of the thesis. Core floors eps0 at the elastic-line intersection
    (about 4.8e-4) when it is absent, so it must be exported explicitly.
    """
    if K <= 0.0 or not 0.0 < n < 1.0 or yield_strength_02 <= 0.0:
        raise ValueError("Swift hardening needs K > 0, 0 < n < 1 and a positive Rp0.2")
    eps0 = (yield_strength_02 / K) ** (1.0 / n)
    if eps0 >= 1.0:
        raise ValueError("Swift hardening: Rp0.2 must be smaller than K")
    return eps0


def _swift_enabled(material: object) -> bool:
    return _quantity_si(material, "SwiftK", "Pa") > 0.0


def _constitutive_parameters(material: object, model: str) -> dict[str, float]:
    if model == "ElastoPlasticIsotropic" and _swift_enabled(material):
        K = _quantity_si(material, "SwiftK", "Pa")
        n = float(getattr(material, "SwiftN", 0.0))
        yield_02 = _quantity_si(material, "YieldStrength02", "Pa")
        return {"K": K, "n": n, "eps0": swift_eps0(yield_02, K, n)}
    fields = {
        "HenselSpittel": {
            "A": ("HenselSpittelA", "Pa"),
            "m1": ("HenselSpittelM1", None),
            "m2": ("HenselSpittelM2", None),
            "m3": ("HenselSpittelM3", None),
            "m4": ("HenselSpittelM4", None),
        },
        "Hollomon": {
            "K": ("HollomonK", "Pa"),
            "n": ("HollomonN", None),
            "eps0": ("HollomonEps0", None),
            "mRate": ("HollomonRateExponent", None),
        },
        "NortonHoffViscoplastic": {
            "K": ("NortonHoffK", "Pa"),
            "m": ("NortonHoffM", None),
        },
        "ElastoPlasticIsotropic": {
            "yieldStress": ("YieldStress", "Pa"),
            "hardeningModulus": ("HardeningModulus", "Pa"),
        },
        "ElasticIsotropic": {},
        "TabulatedFlowStress": {},
    }
    if model not in fields:
        raise ValueError(f"Unsupported CTform material model: {model}")
    output = {}
    for key, (property_name, unit) in fields[model].items():
        if unit:
            output[key] = _quantity_si(material, property_name, unit)
        else:
            output[key] = float(getattr(material, property_name, 0.0))
    return output


def _quantity_si(obj: object, property_name: str, unit: str) -> float:
    value = getattr(obj, property_name, 0.0)
    if hasattr(value, "getValueAs"):
        value = value.getValueAs(unit)
    return float(value)


def _json_array(obj: object, property_name: str) -> list[Any]:
    raw = str(getattr(obj, property_name, "[]") or "[]")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"{property_name} must contain a JSON array: {error}") from error
    if not isinstance(value, list):
        raise ValueError(f"{property_name} must contain a JSON array")
    return value

