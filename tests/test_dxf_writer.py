# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

import json
from pathlib import Path
import unittest
from types import SimpleNamespace

from freecad.CTformFreeCADInterface.analysis import apply_isothermal_preset
from freecad.CTformFreeCADInterface.case_export import _target_compression
from freecad.CTformFreeCADInterface.dxf_writer import (
    arc_primitive,
    dxf_text,
    polyline_primitives,
)

CATALOG = (
    Path(__file__).resolve().parents[1]
    / "freecad" / "CTformFreeCADInterface" / "resources" / "materials"
    / "aisi304-1mm-nunes2025.json"
)


def _entities(text):
    lines = text.splitlines()
    pairs = list(zip(lines[0::2], lines[1::2]))
    return [value for code, value in pairs if code.strip() == "0"]


class DxfWriterTests(unittest.TestCase):
    def test_arc_runs_counter_clockwise_whichever_way_the_edge_runs(self):
        # Quarter circle of radius 1 about the origin, from (1, 0) to (0, 1).
        forward = arc_primitive((0, 0), (1, 0), (0.7071, 0.7071), (0, 1))
        backward = arc_primitive((0, 0), (0, 1), (0.7071, 0.7071), (1, 0))

        self.assertAlmostEqual(forward["start_deg"], 0.0)
        self.assertAlmostEqual(forward["end_deg"], 90.0)
        self.assertEqual((backward["start_deg"], backward["end_deg"]), (forward["start_deg"], forward["end_deg"]))

    def test_small_arc_stays_an_arc_not_a_circle(self):
        # R6 mm entry radius of the die written in metres.
        arc = arc_primitive((0.033, -0.006), (0.033, 0.0), (0.0288, -0.0018), (0.027, -0.006))
        text = dxf_text({"ToolProfile": [arc]})

        self.assertIn("ARC", _entities(text))
        self.assertNotIn("CIRCLE", _entities(text))
        self.assertAlmostEqual(arc["radius"], 0.006)
        self.assertAlmostEqual(arc["start_deg"], 90.0)
        self.assertAlmostEqual(arc["end_deg"], 180.0)

    def test_arc_crossing_zero_degrees_keeps_its_short_side(self):
        arc = arc_primitive((0, 0), (0.7071, -0.7071), (1, 0), (0.7071, 0.7071))

        self.assertAlmostEqual(arc["start_deg"], 315.0, places=3)
        self.assertAlmostEqual(arc["end_deg"], 45.0, places=3)

    def test_document_lists_lines_arcs_and_layers_in_group_code_pairs(self):
        text = dxf_text({
            "Edge1": polyline_primitives([(0.0, 0.0), (0.045, 0.0)]),
            "Edge2": [{"type": "CIRCLE", "center": (0.0, 0.0), "radius": 0.01}],
        })

        self.assertEqual(_entities(text), ["SECTION", "LINE", "CIRCLE", "ENDSEC", "EOF"])
        self.assertIn("Edge1", text.splitlines())
        self.assertIn("Edge2", text.splitlines())
        text.encode("ascii")

    def test_zero_length_segments_are_dropped(self):
        self.assertEqual(polyline_primitives([(0.0, 0.0), (0.0, 0.0)]), [])

    def test_non_ascii_layer_is_rejected(self):
        with self.assertRaises(ValueError):
            dxf_text({"Perfilç": []})


class FivePunchSetupTests(unittest.TestCase):
    def test_target_compression_is_omitted_for_sheet_cases(self):
        self.assertEqual(_target_compression(SimpleNamespace()), {"targetCompression": 0.007})
        self.assertEqual(
            _target_compression(SimpleNamespace(ExportTargetCompression=False, TargetCompression=7.0)), {}
        )

    def test_isothermal_preset_sets_every_thermal_parameter(self):
        solver = SimpleNamespace(
            ThermalPlasticEfficiency=0.9, ThermalFrictionEfficiency=0.5, ThermalContactEnabled=True,
            InitialWorkpieceTemperature=1000.0, InitialToolTemperature=400.0,
        )

        apply_isothermal_preset(solver)

        self.assertEqual(
            (solver.ThermalPlasticEfficiency, solver.ThermalFrictionEfficiency, solver.ThermalContactEnabled),
            (0.0, 0.0, False),
        )
        self.assertEqual((solver.InitialWorkpieceTemperature, solver.InitialToolTemperature), (293.15, 293.15))

    def test_aisi304_catalog_matches_the_thesis_table(self):
        from freecad.CTformFreeCADInterface.materials import material_readiness_issues

        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        records = {item["id"]: item for item in catalog["materials"]}
        hollomon = {key: records[key]["constitutive"]["parameters"] for key in records if "mean" in key or "rd" in key}

        self.assertEqual(material_readiness_issues(catalog), [])
        self.assertEqual((hollomon["aisi304-1mm-rd0"]["K"], hollomon["aisi304-1mm-rd0"]["n"]), (1318.3e6, 0.35))
        self.assertEqual((hollomon["aisi304-1mm-rd45"]["K"], hollomon["aisi304-1mm-rd45"]["n"]), (1198.4e6, 0.33))
        self.assertEqual((hollomon["aisi304-1mm-rd90"]["K"], hollomon["aisi304-1mm-rd90"]["n"]), (1232.3e6, 0.34))
        self.assertAlmostEqual(hollomon["aisi304-1mm-mean"]["K"], 1249.667e6, delta=1e3)
        self.assertAlmostEqual(hollomon["aisi304-1mm-mean"]["n"], 0.34)
        for key in hollomon:
            self.assertEqual(records[key]["elastic"], {"youngModulus": 2.0e11, "poissonRatio": 0.3})
            self.assertEqual(records[key]["thermal"]["density"], 8000.0)


if __name__ == "__main__":
    unittest.main()
