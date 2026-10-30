# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from freecad.CTformFreeCADInterface import case_export
from freecad.CTformFreeCADInterface.materials import (
    _apply_material_record,
    material_readiness_issues,
    material_to_dict,
    swift_eps0,
)

CATALOG = (
    Path(__file__).resolve().parents[1]
    / "freecad" / "CTformFreeCADInterface" / "resources" / "materials"
    / "aisi304-1mm-nunes2025.json"
)


def _material(**values):
    """A stand-in for a CTform material object with plain SI values."""
    defaults = dict(
        MaterialId="test-material", MaterialName="Test", Model="ElastoPlasticIsotropic",
        YoungModulus=2.0e11, PoissonRatio=0.3, Density=8000.0,
        ThermalExpansionCoefficient=1.73e-5, ThermalConductivity=16.2, SpecificHeat=500.0,
        SwiftK=0.0, SwiftN=0.0, YieldStrength02=0.0, YieldStress=0.0, HardeningModulus=0.0,
    )
    defaults.update(values)
    return SimpleNamespace(**defaults)


def _catalog_records():
    return {item["id"]: item for item in json.loads(CATALOG.read_text(encoding="utf-8"))["materials"]}


class SwiftEps0Tests(unittest.TestCase):
    def test_eps0_is_the_yield_strength_over_k_to_the_one_over_n(self):
        eps0 = swift_eps0(217e6, 1318.3e6, 0.35)

        self.assertAlmostEqual(eps0, (217e6 / 1318.3e6) ** (1.0 / 0.35), places=15)
        self.assertAlmostEqual(1318.3e6 * eps0 ** 0.35, 217e6, delta=1.0)

    def test_catalog_eps0_values_are_in_the_expected_range_and_not_the_core_default(self):
        records = _catalog_records()
        for key in ("aisi304-1mm-ep-rd0", "aisi304-1mm-ep-rd45", "aisi304-1mm-ep-rd90", "aisi304-1mm-ep-mean"):
            with self.subTest(key=key):
                exported = material_to_dict(_material(
                    MaterialId=key,
                    Model="ElastoPlasticIsotropic",
                    SwiftK=records[key]["constitutive"]["parameters"]["K"],
                    SwiftN=records[key]["constitutive"]["parameters"]["n"],
                    YieldStrength02=records[key]["constitutive"]["parameters"]["yieldStrength02"],
                ))
                eps0 = exported["constitutive"]["parameters"]["eps0"]
                self.assertGreater(eps0, 0.0045)
                self.assertLess(eps0, 0.0060)

    def test_invalid_swift_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            swift_eps0(217e6, 1318.3e6, 1.2)
        with self.assertRaises(ValueError):
            swift_eps0(0.0, 1318.3e6, 0.35)
        with self.assertRaises(ValueError):
            swift_eps0(2000e6, 1318.3e6, 0.35)


class SwiftExportTests(unittest.TestCase):
    def test_swift_material_exports_k_n_and_eps0_under_elastoplastic(self):
        exported = material_to_dict(_material(SwiftK=1318.3e6, SwiftN=0.35, YieldStrength02=217e6))

        self.assertEqual(exported["constitutive"]["model"], "ElastoPlasticIsotropic")
        self.assertEqual(set(exported["constitutive"]["parameters"]), {"K", "n", "eps0"})
        self.assertEqual(exported["constitutive"]["parameters"]["K"], 1318.3e6)
        self.assertEqual(exported["constitutive"]["parameters"]["n"], 0.35)

    def test_without_k_the_linear_elastoplastic_form_is_kept(self):
        exported = material_to_dict(_material(YieldStress=300e6, HardeningModulus=1e9))

        self.assertEqual(
            exported["constitutive"]["parameters"],
            {"yieldStress": 300e6, "hardeningModulus": 1e9},
        )

    def test_hollomon_entries_keep_their_flow_law_parameters(self):
        exported = material_to_dict(_material(Model="Hollomon", HollomonK=1318.3e6, HollomonN=0.35))

        self.assertEqual(exported["constitutive"]["parameters"]["K"], 1318.3e6)
        self.assertIn("eps0", exported["constitutive"]["parameters"])
        self.assertNotIn("yieldStress", exported["constitutive"]["parameters"])


class SwiftImportTests(unittest.TestCase):
    def test_catalog_record_round_trips_to_the_same_export(self):
        record = _catalog_records()["aisi304-1mm-ep-rd0"]
        material = SimpleNamespace(MaterialId=record["id"], MaterialName=record["name"])

        _apply_material_record(material, record)
        exported = material_to_dict(material)

        self.assertEqual(material.SwiftK, 1318.3e6)
        self.assertEqual(material.YieldStrength02, 217e6)
        self.assertAlmostEqual(
            exported["constitutive"]["parameters"]["eps0"], swift_eps0(217e6, 1318.3e6, 0.35), places=15
        )

    def test_eps0_record_gives_back_the_yield_strength(self):
        record = {
            "id": "eps0-only",
            "name": "eps0 only",
            "constitutive": {"model": "ElastoPlasticIsotropic", "parameters": {
                "K": 1318.3e6, "n": 0.35, "eps0": swift_eps0(217e6, 1318.3e6, 0.35),
            }},
            "elastic": {"youngModulus": 2.0e11, "poissonRatio": 0.3},
            "thermal": {"density": 8000.0, "thermalExpansionCoefficient": 1e-5,
                        "thermalConductivity": 16.0, "specificHeat": 500.0},
        }
        material = SimpleNamespace(MaterialId="eps0-only", MaterialName="eps0 only")

        _apply_material_record(material, record)

        self.assertAlmostEqual(material.YieldStrength02, 217e6, delta=1.0)


class SwiftReadinessTests(unittest.TestCase):
    def test_shipped_catalog_has_no_readiness_issues(self):
        self.assertEqual(material_readiness_issues(json.loads(CATALOG.read_text(encoding="utf-8"))), [])

    def test_swift_record_with_a_bad_exponent_is_reported(self):
        catalog = {"materials": [{
            "id": "bad", "name": "bad",
            "constitutive": {"model": "ElastoPlasticIsotropic", "parameters": {"K": 1e9, "n": 1.2}},
            "elastic": {"youngModulus": 2e11, "poissonRatio": 0.3},
            "thermal": {"density": 8000.0},
        }]}

        self.assertTrue(any("0 < n < 1" in issue for issue in material_readiness_issues(catalog)))


def _case():
    return SimpleNamespace(LoadSteps=[], Tools=[])


class CoreV2GuardTests(unittest.TestCase):
    def _issues(self, mesh_types, formulation="flow", catalog=None):
        return case_export._core_v2_unsupported_issues(
            _case(),
            {"elementTypes": mesh_types},
            catalog,
            SimpleNamespace(MechanicalFormulation=formulation, RemeshEnabled=False),
        )

    def test_displacement_formulation_needs_a_pure_quad4_mesh(self):
        self.assertTrue(any("pure Quad4" in issue for issue in self._issues(["Tri3"], "displacement")))
        self.assertFalse(any("pure Quad4" in issue for issue in self._issues(["Quad4"], "displacement")))
        self.assertFalse(any("pure Quad4" in issue for issue in self._issues(["Tri3"], "flow")))

    def test_swift_export_is_ready_with_core_support(self):
        catalog = {"materials": [{
            "id": "ep", "name": "EP",
            "constitutive": {"model": "ElastoPlasticIsotropic", "parameters": {"K": 1e9, "n": 0.3, "eps0": 0.005}},
        }]}

        self.assertFalse(any("Swift hardening" in issue for issue in self._issues(["Quad4"], "displacement", catalog)))
        with mock.patch.object(case_export, "CORE_SWIFT_SUPPORTED", False):
            self.assertTrue(any("Swift hardening" in issue for issue in self._issues(["Quad4"], "displacement", catalog)))


if __name__ == "__main__":
    unittest.main()
