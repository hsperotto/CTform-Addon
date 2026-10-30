# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

from freecad.CTformFreeCADInterface.core_runner import (
    build_command,
    collect_outputs,
    parse_log,
    run_core,
    step_times,
)

LOG = """\
[CasePackageV2][WARN] role ignorado: o lado vem da geometria
[CasePackageV2][WARN] mais de uma ferramenta
increment 1 ...
[Timing][Summary] total=12.5s converged=1
"""


class CoreRunnerTests(unittest.TestCase):
    def test_command_line_follows_core_cli(self):
        command = build_command(
            "C:/core/ctform3_cli.exe", "pkg/case.json", "out",
            gmsh="C:/gmsh.exe", mmg_directory="C:/mmg", extra=["--tune", "keep_mesh_files=1"],
        )

        self.assertEqual(
            command,
            ["C:/core/ctform3_cli.exe", "--fresh", "--case", "pkg/case.json", "--output-dir", "out",
             "--gmsh", "C:/gmsh.exe", "--mmg-dir", "C:/mmg", "--tune", "keep_mesh_files=1"],
        )

    def test_optional_arguments_are_left_out(self):
        command = build_command("core.exe", "case.json", "out", fresh=False)

        self.assertEqual(command, ["core.exe", "--case", "case.json", "--output-dir", "out"])

    def test_log_reports_convergence_and_package_warnings(self):
        converged, warnings = parse_log(LOG)

        self.assertTrue(converged)
        self.assertEqual(warnings, ["role ignorado: o lado vem da geometria", "mais de uma ferramenta"])
        self.assertEqual(parse_log("converged=1 without the marker"), (False, []))
        self.assertFalse(parse_log("[Timing][Summary] total=1s converged=0")[0])

    def test_outputs_are_sorted_by_step_number(self):
        with TemporaryDirectory() as folder:
            for name in ("case_step_10.vtk", "case_step_2.vtk", "case_step_1.vtk", "notes.txt"):
                (Path(folder) / name).write_text("x")
            (Path(folder) / "press_force_by_tool.csv").write_text("x")

            steps, force_csv = collect_outputs(folder)

            self.assertEqual([p.name for p in steps], ["case_step_1.vtk", "case_step_2.vtk", "case_step_10.vtk"])
            self.assertEqual(force_csv.name, "press_force_by_tool.csv")

    def test_step_times_come_from_the_force_csv(self):
        with TemporaryDirectory() as folder:
            csv = Path(folder) / "press_force_by_tool.csv"
            csv.write_text("Step,Time,Tool,Force\n1,0.1,Punch,0\n1,0.1,Die,0\n3,0.3,Punch,5\n")
            steps = [Path(folder) / "case_step_1.vtk", Path(folder) / "case_step_2.vtk",
                     Path(folder) / "case_step_3.vtk"]

            self.assertEqual(step_times(steps, csv), [0.1, 2.0, 0.3])
            self.assertEqual(step_times(steps, None), [1.0, 2.0, 3.0])

    def test_run_collects_log_warnings_and_outputs(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            stub = root / "fake_core.py"
            stub.write_text(
                "import sys\nfrom pathlib import Path\n"
                "out = Path(sys.argv[sys.argv.index('--output-dir') + 1])\n"
                "out.mkdir(parents=True, exist_ok=True)\n"
                "(out / 'case_step_1.vtk').write_text('vtk')\n"
                f"print({LOG!r})\n"
            )
            case = root / "case.json"
            case.write_text("{}")
            launcher = root / ("fake_core.bat" if os.name == "nt" else "fake_core.sh")
            launcher.write_text(
                f'@"{sys.executable}" "{stub}" %*\n' if os.name == "nt"
                else f'#!/bin/sh\n"{sys.executable}" "{stub}" "$@"\n'
            )
            launcher.chmod(0o755)

            result = run_core(launcher, case, root / "out", timeout=60)

            self.assertTrue(result.finished)
            self.assertEqual(result.return_code, 0)
            self.assertEqual(len(result.warnings), 2)
            self.assertEqual([p.name for p in result.steps], ["case_step_1.vtk"])
            self.assertTrue(result.log_file.is_file())

    def test_missing_executable_or_package_is_reported(self):
        with TemporaryDirectory() as folder:
            case = Path(folder) / "case.json"
            case.write_text("{}")

            with self.assertRaises(FileNotFoundError):
                run_core(Path(folder) / "missing.exe", case, Path(folder) / "out")
            with self.assertRaises(FileNotFoundError):
                run_core(Path(sys.executable), Path(folder) / "nope.json", Path(folder) / "out")


if __name__ == "__main__":
    unittest.main()
