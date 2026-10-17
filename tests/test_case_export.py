# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace

from freecad.CTformFreeCADInterface.case_export import (
    case_to_dict,
    loadsteps_to_dict,
    write_case_json,
)


class CaseExportTests(unittest.TestCase):
    def test_case_to_dict_matches_core_sections(self):
        case = SimpleNamespace(
            SimulationName="demo",
            Process="forging",
            MaterialFile="material.json",
            LoadStepsFile="loadsteps.json",
            ThermalFile="thermal.json",
            ModelingType="axisymmetric",
            MechanicalFormulation="flow",
            ContactModel="node_to_segment",
            InitialGap=0.05,
            AugmentedLagrangeEnabled=True,
            PenetrationTolerance=1e-2,
            GapTolerance=1e-6,
            ThermalContactEnabled=False,
            ZBottom=0.0,
            OutputDirectory="results_case",
            VtkEvery=1,
            NodalCsvEnabled=False,
            GeometryOnly=False,
            TargetCompression=7.0,
            ALEEnabled=False,
            RemeshEnabled=False,
        )

        data = case_to_dict(case)

        self.assertEqual(data["simulationName"], "demo")
        self.assertEqual(data["simulation"]["modelingType"], "axisymmetric")
        self.assertEqual(data["contact"]["model"], "node_to_segment")
        self.assertEqual(data["geometry"]["tools"], [])
        self.assertIn("solver", data)

    def test_write_case_json_updates_case_path(self):
        case = SimpleNamespace(
            SimulationName="demo",
            Process="forging",
            MaterialFile="material.json",
            LoadStepsFile="loadsteps.json",
            ThermalFile="thermal.json",
            ModelingType="axisymmetric",
            MechanicalFormulation="flow",
            ContactModel="node_to_segment",
            InitialGap=0.05,
            AugmentedLagrangeEnabled=True,
            PenetrationTolerance=1e-2,
            GapTolerance=1e-6,
            ThermalContactEnabled=False,
            ZBottom=0.0,
            OutputDirectory="results_case",
            VtkEvery=1,
            NodalCsvEnabled=False,
            GeometryOnly=False,
            TargetCompression=7.0,
            ALEEnabled=False,
            RemeshEnabled=False,
            CaseDirectory="",
            CaseFile="case.json",
        )

        with TemporaryDirectory() as directory:
            path = write_case_json(case, Path(directory) / "case.json")
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(path.name, "case.json")
        self.assertEqual(case.CaseFile, "case.json")
        self.assertEqual(data["simulationName"], "demo")

    def test_named_tools_export_without_directional_roles(self):
        case = SimpleNamespace(
            SimulationName="demo",
            Process="forging",
            MaterialFile="material.json",
            LoadStepsFile="loadsteps.json",
            ThermalFile="thermal.json",
            ModelingType="axisymmetric",
            MechanicalFormulation="flow",
            ContactModel="node_to_segment",
            InitialGap=0.05,
            AugmentedLagrangeEnabled=True,
            PenetrationTolerance=1e-2,
            GapTolerance=1e-6,
            ThermalContactEnabled=False,
            ZBottom=0.0,
            OutputDirectory="results_case",
            VtkEvery=1,
            NodalCsvEnabled=False,
            GeometryOnly=False,
            TargetCompression=7.0,
            ALEEnabled=False,
            RemeshEnabled=False,
            RoleAssignments=[
                SimpleNamespace(Role="workpiece", SourceFile="workpiece.dxf"),
                SimpleNamespace(
                    Role="tool",
                    ToolName="Punch",
                    SourceFile="punch.dxf",
                    ToolLayer="Profile",
                    InitialOffsetZ=1.0,
                    SymmetryR=0.0,
                    Label="CTform Tool: Punch",
                ),
                SimpleNamespace(
                    Role="tool",
                    ToolName="GuidePin",
                    SourceFile="guide_pin.dxf",
                    ToolLayer="",
                    InitialOffsetZ=0.0,
                    SymmetryR=0.0,
                    Label="CTform Tool: GuidePin",
                ),
            ],
        )

        tools = case_to_dict(case)["geometry"]["tools"]

        self.assertEqual([tool["name"] for tool in tools], ["Punch", "GuidePin"])
        self.assertTrue(all(tool["role"] == "tool" for tool in tools))

    def test_loadsteps_export_matches_core_shape(self):
        condition = SimpleNamespace(
            BCId=1,
            Name="AxisSymmetry",
            Type="Fixed",
            Axis="X",
            Target="Symmetry0",
            Value=0.0,
            Active=True,
        )
        motion = SimpleNamespace(
            MotionId=1000,
            ToolName="Punch",
            Vx=0.0,
            Vy=0.0,
            Vz=-1.0,
            Active=True,
            InitialTemperature=293.15,
            HeatTransferCoefficient=0.0,
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="CylinderCompression",
            StartTime=0.0,
            EndTime=7.6,
            Increments=190,
            MechanicalBCs=[condition],
            ToolMotions=[motion],
        )
        case = SimpleNamespace(LoadSteps=[step])

        exported = loadsteps_to_dict(case)["loadSteps"][0]

        self.assertEqual(exported["increments"], 190)
        self.assertEqual(exported["mechanicalBCs"][0]["target"], "Symmetry0")
        self.assertEqual(exported["tools"][0]["name"], "Punch")


if __name__ == "__main__":
    unittest.main()
