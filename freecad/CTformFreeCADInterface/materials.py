# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""CTform-owned material definitions and catalog serialization."""

from __future__ import annotations

import json
import uuid
from typing import Any


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
        _add(obj, "MaterialId", "App::PropertyString", "Identity", uuid.uuid4().hex)
        _add(obj, "MaterialName", "App::PropertyString", "Identity", "New CTform Material")
        _add(obj, "Model", "App::PropertyEnumeration", "Constitutive", list(MATERIAL_MODELS))
        _add(obj, "HenselSpittelA", "App::PropertyPressure", "Hensel-Spittel", 0.0)
        for name in ("HenselSpittelM1", "HenselSpittelM2", "HenselSpittelM3", "HenselSpittelM4"):
            _add(obj, name, "App::PropertyFloat", "Hensel-Spittel", 0.0)
        _add(obj, "HollomonK", "App::PropertyPressure", "Hollomon", 0.0)
        for name in ("HollomonN", "HollomonEps0", "HollomonRateExponent"):
            _add(obj, name, "App::PropertyFloat", "Hollomon", 0.0)
        _add(obj, "NortonHoffK", "App::PropertyPressure", "Norton-Hoff", 0.0)
        _add(obj, "NortonHoffM", "App::PropertyFloat", "Norton-Hoff", 0.0)
        _add(obj, "YieldStress", "App::PropertyPressure", "Elastoplastic", 0.0)
        _add(obj, "HardeningModulus", "App::PropertyPressure", "Elastoplastic", 0.0)
        _add(obj, "YoungModulus", "App::PropertyPressure", "Elastic", 0.0)
        _add(obj, "PoissonRatio", "App::PropertyFloat", "Elastic", 0.3)
        _add(obj, "Density", "App::PropertyDensity", "Thermal", 0.0)
        _add(
            obj,
            "ThermalExpansionCoefficient",
            "App::PropertyThermalExpansionCoefficient",
            "Thermal",
            0.0,
        )
        _add(obj, "ThermalConductivity", "App::PropertyThermalConductivity", "Thermal", 0.0)
        _add(obj, "SpecificHeat", "App::PropertySpecificHeat", "Thermal", 0.0)
        for name in (
            "YoungModulusTableJSON",
            "ConductivityTableJSON",
            "SpecificHeatTableJSON",
            "FlowStressTableJSON",
        ):
            _add(obj, name, "App::PropertyString", "Temperature Tables", "[]")

    def onDocumentRestored(self, obj=None):
        if obj is not None:
            self.Object = obj
        self._add_properties()


def make_material(doc, analysis, component=None, name="CTformMaterial"):
    """Create a CTform material and place it in its Workpiece or Tool folder."""
    obj = doc.addObject("App::FeaturePython", name)
    obj.Proxy = CTformMaterial(obj)
    obj.Label = "CTform Material"
    if component is None:
        analysis.addObject(obj)
    else:
        component.addObject(obj)
        component.Material = obj
    return obj


def materials_to_dict(case: object) -> dict[str, Any]:
    """Serialize materials linked directly from the Workpiece and Tool folders."""
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
        if elastic.get("youngModulus", 0.0) <= 0.0:
            issues.append(f"Material {name!r} needs a positive Young's modulus.")
        poisson_ratio = elastic.get("poissonRatio", 0.3)
        if not -1.0 < poisson_ratio < 0.5:
            issues.append(f"Material {name!r} has an invalid Poisson ratio.")
        if thermal.get("density", 0.0) <= 0.0:
            issues.append(f"Material {name!r} needs a positive density.")
    return issues


def _constitutive_parameters(material: object, model: str) -> dict[str, float]:
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


def _add(obj, name, property_type, group, default):
    if name not in obj.PropertiesList:
        obj.addProperty(property_type, name, group)
        if property_type == "App::PropertyEnumeration":
            setattr(obj, name, default)
            setattr(obj, name, default[0])
        else:
            setattr(obj, name, default)
