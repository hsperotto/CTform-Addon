# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from freecad.CTformFreeCADInterface import results

# Core's layout: points are (r, y=0, z); tool cells have element_type 10.
VTK = """\
# vtk DataFile Version 3.0
CTForm3 - Multibody Results
ASCII
DATASET UNSTRUCTURED_GRID

POINTS 6 double
0 0 0
2 0 0
2 0 1
0 0 1
5 0 5
6 0 5
CELLS 3 12
3 0 1 2
3 0 2 3
2 4 5
CELL_TYPES 3
5
5
3
POINT_DATA 6
VECTORS Displacement double
0 0 0
0 0 -3
0 0 -4
0 0 0
0 0 0
0 0 0
SCALARS ContactPressure double 1
LOOKUP_TABLE default
0
2
4
6
0
0
CELL_DATA 3
SCALARS element_type int 1
LOOKUP_TABLE default
1
1
10
SCALARS Plastic_Strain double 1
LOOKUP_TABLE default
0.25
0.5
9.0
TENSORS SIGMAT double
1 0 0
0 1 0
0 0 1

1 0 0
0 1 0
0 0 1

1 0 0
0 1 0
0 0 1

"""

CSV = """Step,Time,Tool,Force
1,0.5,Punch,0
1,0.5,Die,0
2,1.0,Punch,50
2,1.0,Die,50
3,1.5,Punch,200
3,1.5,Die,199
"""

LOADSTEPS = {"loadSteps": [{"startTime": 0.0, "endTime": 2.0,
                            "tools": [{"toolId": "punch", "vz": -0.010, "active": True},
                                      {"toolId": "die", "vz": 0.0, "active": True}]}]}


def write_run(folder: Path):
    out = folder / "out"
    out.mkdir()
    (out / "case_step_1.vtk").write_text(VTK, encoding="utf-8")
    (out / "press_force_by_tool.csv").write_text(CSV, encoding="utf-8")
    (folder / "loadsteps.json").write_text(json.dumps(LOADSTEPS), encoding="utf-8")
    return out


class ForceAndStrokeTests(unittest.TestCase):
    def test_force_csv_groups_by_tool(self):
        with TemporaryDirectory() as tmp:
            out = write_run(Path(tmp))
            series = results.read_force_csv(out / "press_force_by_tool.csv")
        self.assertEqual(series["Punch"].forces, [0.0, 50.0, 200.0])
        self.assertEqual(series["Die"].steps, [1, 2, 3])

    def test_punch_displacement_follows_velocity_in_mm(self):
        profile = results.punch_velocity_profile(LOADSTEPS)
        self.assertEqual(profile, [(0.0, 2.0, -10.0)])
        self.assertAlmostEqual(results.punch_displacement(profile, 1.5), 15.0)
        self.assertAlmostEqual(results.punch_displacement(profile, 9.0), 20.0)  # clamped at the end

    def test_stroke_is_displacement_minus_gap_and_never_negative(self):
        self.assertEqual(results.stroke_from_contact([0.0, 1.0, 3.0], 1.0), [0.0, 0.0, 2.0])

    def test_first_contact_uses_one_percent_of_peak_not_zero(self):
        # a tiny penalty force (0.5 of a 200 N peak) must not count as contact
        self.assertEqual(results.first_contact_displacement([1, 2, 3, 4], [0.5, 1.0, 5.0, 200.0]), 3)
        self.assertIsNone(results.first_contact_displacement([1, 2], [0.0, 0.0]))

    def test_load_run_reports_stroke_and_crosscheck(self):
        with TemporaryDirectory() as tmp:
            out = write_run(Path(tmp))
            records, notes = results.load_run(out, tmp, initial_gap=2.0)
        self.assertEqual([r.number for r in records], [1, 2, 3])
        self.assertAlmostEqual(records[0].stroke, 5.0 - 2.0)   # t = 0.5 s at 10 mm/s
        self.assertAlmostEqual(records[2].stroke, 15.0 - 2.0)
        self.assertEqual(records[2].forces["Die"], 199.0)
        self.assertEqual(notes["stroke"], "displacement minus initial gap")
        self.assertAlmostEqual(notes["crossCheck"]["firstContactDisplacement"], 10.0)

    def test_load_run_without_loadsteps_falls_back_to_time(self):
        with TemporaryDirectory() as tmp:
            out = write_run(Path(tmp))
            records, notes = results.load_run(out, None)
        self.assertEqual(notes["stroke"], "unknown")
        self.assertEqual(records[1].stroke, 1.0)


class VtkTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        path = Path(self._tmp.name) / "case_step_1.vtk"
        path.write_text(VTK, encoding="utf-8")
        self.step = results.VtkStep(path, ["Plastic_Strain", "ContactPressure", "Displacement"])

    def test_reads_points_cells_and_requested_arrays(self):
        self.assertEqual(len(self.step.points), 6)
        self.assertEqual(self.step.cells[0], [0, 1, 2])
        self.assertEqual(self.step.cell_data["Plastic_Strain"], [0.25, 0.5, 9.0])
        self.assertIn("SIGMAT", self.step.array_names["cell"])
        self.assertNotIn("SIGMAT", self.step.cell_data)

    def test_maximum_ignores_tool_cells_and_reports_location(self):
        found = self.step.maximum("Plastic_Strain")  # 9.0 belongs to a tool cell
        self.assertEqual(found.value, 0.5)
        self.assertEqual(found.element, 1)
        self.assertAlmostEqual(found.radius, 2.0 / 3.0)
        self.assertAlmostEqual(found.axial, 2.0 / 3.0)

    def test_point_vector_maximum_is_the_magnitude(self):
        found = self.step.maximum("Displacement")
        self.assertEqual(found.value, 4.0)
        self.assertEqual((found.radius, found.axial), (2.0, 1.0))

    def test_probe_cell_and_point_fields(self):
        self.assertEqual(results.probe(self.step, "Plastic_Strain", 1.5, 0.2), 0.25)
        self.assertEqual(results.probe(self.step, "Plastic_Strain", 0.5, 0.8), 0.5)
        # ContactPressure is 0, 2, 4 on the corners of triangle (0, 1, 2): at (1, 0) it is 1
        self.assertAlmostEqual(results.probe(self.step, "ContactPressure", 1.0, 0.0), 1.0)
        self.assertIsNone(results.probe(self.step, "Plastic_Strain", 5.5, 5.0))  # tool cell, not sheet

    def test_line_profile_has_none_outside_the_sheet(self):
        profile = results.line_profile(self.step, "Plastic_Strain", (0.5, 0.5), (3.0, 0.5), samples=6)
        self.assertEqual(profile[0][1], 0.5)
        self.assertIsNone(profile[-1][1])
        self.assertAlmostEqual(profile[-1][0], 2.5)

    def test_summary_csv(self):
        records = [results.StepRecord(1, 0.5, 1.0, {"Punch": 3.0})]
        maxima = [{"Plastic_Strain": results.FieldMaximum(0.5, 1.0, 2.0, 1)}]
        out = Path(self._tmp.name) / "s.csv"
        results.write_summary_csv(out, records, maxima)
        lines = out.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "Step,Time_s,Stroke_mm,Force_Punch,"
                                   "Max_Plastic_Strain,Max_Plastic_Strain_r_mm,Max_Plastic_Strain_z_mm")
        self.assertEqual(lines[1], "1,0.5,1.0,3.0,0.5,1.0,2.0")


REAL = Path(r"C:\ctf-probes\five-punch\probe9_gap0_mu0.2")


@unittest.skipUnless(REAL.is_dir() and os.environ.get("CTFORM_REAL_RESULTS") == "1",
                     "real Core output (set CTFORM_REAL_RESULTS=1)")
class RealCoreOutputTests(unittest.TestCase):
    def test_probe9_matches_direct_reading(self):
        records, _ = results.load_run(REAL / "out", REAL)
        self.assertEqual(len(records), 3)
        step = results.VtkStep(REAL / "out" / "case_step_3.vtk", ["Plastic_Strain"])
        self.assertEqual(len(step.workpiece_cells()), 1920)
        self.assertGreater(step.maximum("Plastic_Strain").value, 0.0)


if __name__ == "__main__":
    unittest.main()
