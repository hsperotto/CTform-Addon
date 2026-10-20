# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from freecad.CTformFreeCADInterface.case_export import (
    case_to_dict,
    loadsteps_to_dict,
    thermal_to_dict,
    write_case_json,
    _core_v2_unsupported_issues,
)
from freecad.CTformFreeCADInterface.contacts import contact_pair_to_dict
from freecad.CTformFreeCADInterface.components import CTformWorkpiece
from freecad.CTformFreeCADInterface.materials import materials_to_dict
from freecad.CTformFreeCADInterface.loadsteps import CTformLoadStep, attach_condition


class CaseExportTests(unittest.TestCase):
    def test_case_to_dict_matches_core_sections(self):
        case = SimpleNamespace(
            SimulationName="demo",
            Process="forging",
            LoadStepsFile="loadsteps.json",
            ThermalFile="thermal.json",
        )
        solver = SimpleNamespace(
            Dimension="2D",
            ModelingType="axisymmetric",
            MechanicalFormulation="flow",
            ContactModel="node_to_segment",
            InitialGap=0.05,
            AugmentedLagrangeEnabled=True,
            PenetrationTolerance=1e-2,
            GapTolerance=1e-6,
            ThermalContactEnabled=False,
            ZBottom=0.0,
        )

        data = case_to_dict(case, solver=solver)

        self.assertEqual(data["simulationName"], "demo")
        self.assertEqual(data["simulation"]["modelingType"], "axisymmetric")
        self.assertEqual(data["contact"]["model"], "node_to_segment")
        self.assertEqual(data["schemaVersion"], 2)
        self.assertEqual(data["units"]["length"], "m")
        self.assertEqual(data["materialsFile"], "materials.json")
        self.assertAlmostEqual(data["contact"]["initialGap"], 5e-5)
        self.assertEqual(data["geometry"]["tools"], [])
        self.assertIn("solver", data)

    def test_write_case_json_updates_case_path(self):
        case = SimpleNamespace(
            SimulationName="demo",
            Process="forging",
            LoadStepsFile="loadsteps.json",
            ThermalFile="thermal.json",
            Workpiece=None,
            Tools=[],
            LoadSteps=[],
            Analysis=SimpleNamespace(Group=[]),
            CaseDirectory="",
            CaseFile="case.json",
        )

        with TemporaryDirectory() as directory:
            path = write_case_json(case, Path(directory) / "case.json")
            case_text = path.read_text(encoding="utf-8")
            data = json.loads(case_text)
            self.assertTrue((path.parent / "materials.json").exists())
            self.assertTrue((path.parent / "thermal.json").exists())
            self.assertTrue((path.parent / "loadsteps.json").exists())

        self.assertEqual(path.name, "case.json")
        self.assertEqual(case.CaseFile, "case.json")
        self.assertEqual(data["simulationName"], "demo")
        self.assertIn('"initialGap": 5.0000000000000002e-05', case_text)

    def test_writer_links_workpiece_mesh_into_case_package(self):
        mesh_object = SimpleNamespace(TypeId="Fem::FemMeshGmsh")
        workpiece = SimpleNamespace(
            Mesh=mesh_object,
            MeshFile="mesh/workpiece.msh",
            Shape=SimpleNamespace(Label="Blank"),
            Material=None,
            ContactPairs=[],
            Label='CTform Workpiece: "Blank"',
        )
        case = SimpleNamespace(
            SimulationName="mesh-test",
            Process="forging",
            Workpiece=workpiece,
            Tools=[],
            LoadSteps=[],
            Analysis=SimpleNamespace(Group=[]),
            CaseDirectory="",
            CaseFile="case.json",
        )

        def fake_gmsh_export(mesh, output_path):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("native gmsh mesh", encoding="utf-8")
            return {
                "format": "gmsh-msh2",
                "lengthUnit": "m",
                "nodeCount": 4,
                "elementCount": 2,
                "elementTypes": ["Tri3"],
                "physicalGroups": [{"id": 121, "name": "Face1", "dimension": 2}],
            }

        def fake_geometry_export(component, output_path):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("ascii dxf", encoding="ascii")
            return {"layers": ["Edge1"]}

        with TemporaryDirectory() as directory, patch(
            "freecad.CTformFreeCADInterface.case_export.export_gmsh_mesh",
            side_effect=fake_gmsh_export,
        ), patch(
            "freecad.CTformFreeCADInterface.case_export.export_component_geometry",
            side_effect=fake_geometry_export,
        ):
            path = write_case_json(case, Path(directory) / "case.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            mesh_path = path.parent / data["mesh"]["file"]
            self.assertTrue(mesh_path.exists())

        self.assertEqual(data["mesh"]["format"], "gmsh-msh2")
        self.assertEqual(data["mesh"]["lengthUnit"], "m")
        self.assertEqual(data["mesh"]["physicalGroups"][0]["id"], 121)

    def test_material_catalog_uses_named_fields_and_si_values(self):
        class Quantity:
            def __init__(self, value):
                self.value = value

            def getValueAs(self, unit):
                return self.value

        material = SimpleNamespace(
            MaterialId="steel-test-001",
            MaterialName="Test forging steel",
            Model="HenselSpittel",
            HenselSpittelA=Quantity(1.2e9),
            HenselSpittelM1=-1e-3,
            HenselSpittelM2=-0.2,
            HenselSpittelM3=0.15,
            HenselSpittelM4=-0.05,
            YoungModulus=Quantity(2.1e11),
            PoissonRatio=0.3,
            Density=Quantity(7800.0),
            ThermalExpansionCoefficient=Quantity(1.2e-5),
            ThermalConductivity=Quantity(30.0),
            SpecificHeat=Quantity(460.0),
            YoungModulusTableJSON="[]",
            ConductivityTableJSON="[]",
            SpecificHeatTableJSON="[]",
            FlowStressTableJSON="[]",
        )

        catalog = materials_to_dict(
            SimpleNamespace(
                Workpiece=SimpleNamespace(Material=material),
                Tools=[],
            )
        )
        record = catalog["materials"][0]

        self.assertNotIn("schemaVersion", catalog)
        self.assertNotIn("units", catalog)
        self.assertEqual(record["id"], "steel-test-001")
        self.assertEqual(record["constitutive"]["model"], "HenselSpittel")
        self.assertEqual(record["constitutive"]["parameters"]["A"], 1.2e9)
        self.assertEqual(record["elastic"]["youngModulus"], 2.1e11)
        self.assertEqual(record["thermal"]["specificHeat"], 460.0)

    def test_named_tools_export_from_tool_folders(self):
        case = SimpleNamespace(
            SimulationName="demo",
            Process="forging",
            LoadStepsFile="loadsteps.json",
            ThermalFile="thermal.json",
            Workpiece=SimpleNamespace(Shape=SimpleNamespace(Label="Blank")),
            Tools=[
                SimpleNamespace(
                    Shape=SimpleNamespace(Label="PunchBody"),
                    ToolId="tool-punch-id",
                    ToolName="Punch",
                    ToolLayer="Profile",
                    InitialOffsetZ=1.0,
                    SymmetryR=0.0,
                    Material=None,
                    Label="CTform Tool: Punch",
                ),
                SimpleNamespace(
                    Shape=SimpleNamespace(Label="GuideBody"),
                    ToolId="tool-guide-id",
                    ToolName="GuidePin",
                    ToolLayer="",
                    InitialOffsetZ=0.0,
                    SymmetryR=0.0,
                    Material=None,
                    Label="CTform Tool: GuidePin",
                ),
            ],
        )

        tools = case_to_dict(case)["geometry"]["tools"]

        self.assertEqual([tool["name"] for tool in tools], ["Punch", "GuidePin"])
        self.assertEqual([tool["id"] for tool in tools], ["tool-punch-id", "tool-guide-id"])
        self.assertEqual(tools[0]["type"], "rigid")
        self.assertEqual(tools[0]["initialOffsetZ"], 0.001)

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

    def test_native_displacement_maps_xy_to_core_xz_and_axial_selector(self):
        edge = SimpleNamespace(
            ShapeType="Edge",
            BoundBox=SimpleNamespace(YLength=0.0, ZLength=0.0, YMin=4.0),
        )
        profile = SimpleNamespace(Shape=SimpleNamespace(getElement=lambda name: edge))
        condition = SimpleNamespace(
            TypeId="Fem::ConstraintDisplacement",
            Proxy=None,
            Label="Axial displacement",
            References=[(profile, ["Edge1"])],
            xDisplacement=0.0,
            xFree=True,
            yDisplacement=-2.0,
            yFree=False,
            zDisplacement=0.0,
            zFree=True,
            Active=True,
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Press",
            StartTime=0.0,
            EndTime=1.0,
            Increments=10,
            MechanicalBCs=[condition],
            ThermalBCs=[],
            ToolMotions=[],
        )

        exported = loadsteps_to_dict(SimpleNamespace(LoadSteps=[step]))["loadSteps"][0]
        bc = exported["mechanicalBCs"][0]

        self.assertEqual(bc["axis"], "Z")
        self.assertEqual(bc["value"], -2.0)
        self.assertTrue(bc["useZSelector"])
        self.assertEqual(bc["zSelector"], 0.004)

    def test_native_condition_reference_maps_to_exported_physical_group_id(self):
        profile = SimpleNamespace(Shape=SimpleNamespace())
        condition = SimpleNamespace(
            TypeId="Fem::ConstraintFixed",
            Proxy=None,
            Label="Bottom support",
            References=[(profile, ["Edge1"])],
            Active=True,
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Forge",
            StartTime=0.0,
            EndTime=1.0,
            Increments=1,
            Group=[condition],
            MechanicalBCs=[condition],
            ThermalBCs=[],
            ToolMotions=[],
        )
        physical_groups = [{"id": 41001, "name": "Edge1", "dimension": 1}]

        exported = loadsteps_to_dict(
            SimpleNamespace(LoadSteps=[step]), physical_groups
        )["loadSteps"][0]

        bc = exported["mechanicalBCs"][0]
        self.assertEqual(bc["physicalGroupId"], 41001)
        self.assertEqual(bc["physicalGroup"], "Edge1")

    def test_native_displacement_quantity_converts_from_freecad_to_si(self):
        class Quantity:
            def getValueAs(self, unit):
                self.requested_unit = unit
                return 0.002

        profile = SimpleNamespace(Shape=SimpleNamespace())
        condition = SimpleNamespace(
            TypeId="Fem::ConstraintDisplacement",
            Proxy=None,
            Label="Axial displacement",
            References=[(profile, ["Edge1"])],
            xDisplacement=0.0,
            xFree=True,
            yDisplacement=Quantity(),
            yFree=False,
            zDisplacement=0.0,
            zFree=True,
            Active=True,
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Press",
            StartTime=0.0,
            EndTime=1.0,
            Increments=1,
            Group=[condition],
            MechanicalBCs=[condition],
            ThermalBCs=[],
            ToolMotions=[],
        )

        exported = loadsteps_to_dict(
            SimpleNamespace(LoadSteps=[step]),
            [{"id": 101, "name": "Edge1", "dimension": 1}],
        )["loadSteps"][0]
        bc = exported["mechanicalBCs"][0]

        self.assertEqual(condition.yDisplacement.requested_unit, "m")
        self.assertEqual(bc["value"], 0.002)
        self.assertEqual(bc["physicalGroupId"], 101)

    def test_contact_pair_serializes_workpiece_tool_and_physical_group(self):
        workpiece = SimpleNamespace(
            Proxy=object.__new__(CTformWorkpiece),
            Label='CTform Workpiece: "Blank"',
        )
        tool = SimpleNamespace(
            ToolId="tool-upper-id", ToolName="UpperPunch", Label="UpperPunch"
        )
        pair = SimpleNamespace(
            PairId="pair-001",
            PairName="Workpiece to UpperPunch",
            InList=[workpiece],
            Tool=tool,
            SlavePhysicalGroup="EdgeTop",
            MasterPhysicalGroup="ContactFace",
            GapTolerance=0.25,
            FrictionModel="coulomb",
            FrictionCoefficient=0.22,
            LevanovM=0.3,
            LevanovN=1.25,
            ThermalEnabled=True,
            HeatTransferCoefficient=1800.0,
            Active=True,
        )

        data = contact_pair_to_dict(
            pair,
            [{"id": 7102, "name": "EdgeTop", "dimension": 1}],
        )

        self.assertEqual(data["id"], "pair-001")
        self.assertEqual(data["slave"]["physicalGroupId"], 7102)
        self.assertEqual(
            data["master"],
            {
                "body": "tool",
                "name": "UpperPunch",
                "toolId": "tool-upper-id",
                "physicalGroup": "ContactFace",
            },
        )
        self.assertEqual(data["masterToolId"], "tool-upper-id")
        self.assertEqual(data["slave"]["body"], "workpiece")
        self.assertEqual(data["master"]["body"], "tool")
        self.assertEqual(data["friction"]["coefficient"], 0.22)
        self.assertEqual(data["gapTolerance"], 0.00025)

    def test_native_tool_displacement_becomes_step_tool_velocity(self):
        tool_profile = SimpleNamespace()
        condition = SimpleNamespace(
            TypeId="Fem::ConstraintDisplacement",
            Proxy=None,
            Label="Punch displacement",
            References=[(tool_profile, ["Edge1"])],
            xDisplacement=0.0,
            xFree=True,
            yDisplacement=-6.0,
            yFree=False,
            zDisplacement=0.0,
            zFree=True,
            Active=True,
        )
        tool = SimpleNamespace(
            Shape=tool_profile, ToolId="tool-punch-id",
            ToolName="Punch", Label="CTform Tool: Punch"
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Press",
            StartTime=0.0,
            EndTime=2.0,
            Increments=20,
            MechanicalBCs=[condition],
            ThermalBCs=[],
            ToolMotions=[],
        )

        exported = loadsteps_to_dict(
            SimpleNamespace(LoadSteps=[step], Tools=[tool])
        )["loadSteps"][0]

        self.assertEqual(exported["mechanicalBCs"], [])
        self.assertEqual(exported["tools"][0]["name"], "Punch")
        self.assertEqual(exported["tools"][0]["toolId"], "tool-punch-id")
        self.assertEqual(exported["tools"][0]["vz"], -3.0)

    def test_native_fixed_tool_becomes_zero_velocity(self):
        tool_profile = SimpleNamespace()
        condition = SimpleNamespace(
            TypeId="Fem::ConstraintFixed",
            Proxy=None,
            Label="Fixed lower die",
            References=[(tool_profile, ["Face1"])],
            Active=True,
        )
        tool = SimpleNamespace(
            Shape=tool_profile, ToolId="tool-lower-id",
            ToolName="LowerDie", Label="CTform Tool: LowerDie"
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Forge",
            StartTime=0.0,
            EndTime=1.0,
            Increments=10,
            MechanicalBCs=[condition],
            ThermalBCs=[],
            ToolMotions=[],
        )

        exported = loadsteps_to_dict(
            SimpleNamespace(LoadSteps=[step], Tools=[tool])
        )["loadSteps"][0]

        self.assertEqual(exported["mechanicalBCs"], [])
        self.assertEqual(exported["tools"][0]["name"], "LowerDie")
        self.assertEqual(exported["tools"][0]["toolId"], "tool-lower-id")
        self.assertEqual(exported["tools"][0]["vx"], 0.0)
        self.assertEqual(exported["tools"][0]["vz"], 0.0)

    def test_global_and_step_tool_records_get_unique_ids(self):
        die_profile = SimpleNamespace()
        punch_profile = SimpleNamespace()
        die_fixed = SimpleNamespace(
            TypeId="Fem::ConstraintFixed",
            Proxy=None,
            Label="Fixed die",
            References=[(die_profile, ["Face1"])],
            Active=True,
        )
        punch_move = SimpleNamespace(
            TypeId="Fem::ConstraintDisplacement",
            Proxy=None,
            Label="Punch displacement",
            References=[(punch_profile, ["Edge1"])],
            xDisplacement=0.0,
            xFree=True,
            yDisplacement=-6.0,
            yFree=False,
            zDisplacement=0.0,
            zFree=True,
            Active=True,
        )
        tools = [
            SimpleNamespace(Shape=die_profile, ToolId="die", ToolName="Die", Label="CTform Tool: Die"),
            SimpleNamespace(Shape=punch_profile, ToolId="punch", ToolName="Punch", Label="CTform Tool: Punch"),
        ]
        step = SimpleNamespace(
            StepId=1,
            StepName="Press",
            StartTime=0.0,
            EndTime=2.0,
            Increments=20,
            MechanicalBCs=[punch_move],
            ThermalBCs=[],
            ToolMotions=[],
        )
        case = SimpleNamespace(
            Analysis=SimpleNamespace(Group=[die_fixed]),
            LoadSteps=[step],
            Tools=tools,
        )

        exported_tools = loadsteps_to_dict(case)["loadSteps"][0]["tools"]

        self.assertEqual([tool["toolId"] for tool in exported_tools], ["die", "punch"])
        self.assertEqual([tool["id"] for tool in exported_tools], [1000, 1001])

    def test_duplicate_step_ids_are_rejected(self):
        steps = [
            SimpleNamespace(
                StepId=1,
                StepName=name,
                StartTime=0.0,
                EndTime=1.0,
                Increments=1,
                MechanicalBCs=[],
                ThermalBCs=[],
                ToolMotions=[],
            )
            for name in ("Upset", "Finish")
        ]

        with self.assertRaisesRegex(ValueError, "unique StepId"):
            loadsteps_to_dict(SimpleNamespace(LoadSteps=steps))

    def test_drag_and_attach_command_grouping_export_identically(self):
        class StepObject:
            def __init__(self):
                self.Group = []
                self.MechanicalBCs = []
                self.ThermalBCs = []
                self.ToolMotions = []
                self.Proxy = object.__new__(CTformLoadStep)
                self.StepId = 1
                self.StepName = "Forge"
                self.StartTime = 0.0
                self.EndTime = 1.0
                self.Increments = 1

            def addObject(self, condition):
                self.Group.append(condition)
                self.Proxy.onChanged(self, "Group")

        def fixed_condition():
            return SimpleNamespace(
                TypeId="Fem::ConstraintFixed",
                Proxy=None,
                Label="Fixed workpiece region",
                References=[],
                Active=True,
            )

        dragged_step = StepObject()
        dragged_condition = fixed_condition()
        dragged_step.Group.append(dragged_condition)
        dragged_step.Proxy.onChanged(dragged_step, "Group")

        attached_step = StepObject()
        attach_condition(attached_step, fixed_condition())

        dragged_export = loadsteps_to_dict(SimpleNamespace(LoadSteps=[dragged_step]))
        attached_export = loadsteps_to_dict(SimpleNamespace(LoadSteps=[attached_step]))
        self.assertEqual(dragged_export, attached_export)
        self.assertEqual(len(dragged_step.MechanicalBCs), 1)
        self.assertEqual(len(attached_step.MechanicalBCs), 1)

    def test_analysis_root_conditions_apply_to_every_load_step(self):
        global_condition = SimpleNamespace(
            TypeId="Fem::ConstraintFixed",
            Proxy=None,
            Label="Global workpiece support",
            References=[],
            Active=True,
        )
        steps = [
            SimpleNamespace(
                StepId=step_id,
                StepName=f"Step {step_id}",
                StartTime=float(step_id - 1),
                EndTime=float(step_id),
                Increments=1,
                Group=[],
                MechanicalBCs=[],
                ThermalBCs=[],
                ToolMotions=[],
            )
            for step_id in (1, 2)
        ]
        case = SimpleNamespace(
            Analysis=SimpleNamespace(Group=[global_condition]),
            LoadSteps=steps,
        )

        exported_steps = loadsteps_to_dict(case)["loadSteps"]

        self.assertEqual(len(exported_steps), 2)
        self.assertTrue(all(len(step["mechanicalBCs"]) == 1 for step in exported_steps))
        self.assertEqual(
            [step["mechanicalBCs"][0]["name"] for step in exported_steps],
            ["Global workpiece support", "Global workpiece support"],
        )

    def test_step_local_condition_overrides_root_and_emits_warning(self):
        global_condition = SimpleNamespace(
            TypeId="Fem::ConstraintFixed",
            Proxy=None,
            Label="Global support",
            Type="Fixed",
            Target="Bottom",
            Axis="Z",
            Value=0.0,
            Active=True,
        )
        local_condition = SimpleNamespace(
            TypeId="Fem::ConstraintFixed",
            Proxy=None,
            Label="Step support",
            Type="Fixed",
            Target="Bottom",
            Axis="Z",
            Value=0.0,
            Active=True,
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Forge",
            StartTime=0.0,
            EndTime=1.0,
            Increments=1,
            Group=[local_condition],
            MechanicalBCs=[local_condition],
            ThermalBCs=[],
            ToolMotions=[],
        )
        case = SimpleNamespace(
            Analysis=SimpleNamespace(Group=[global_condition]),
            LoadSteps=[step],
        )

        exported = loadsteps_to_dict(case)
        records = exported["loadSteps"][0]["mechanicalBCs"]

        self.assertEqual([record["scope"] for record in records], ["global", "step"])
        self.assertTrue(records[1]["overridesGlobal"])
        self.assertEqual(len(exported["warnings"]), 1)
        self.assertIn("Step support", exported["warnings"][0])
        self.assertIn("Global support", exported["warnings"][0])

    def test_native_tool_force_becomes_force_control(self):
        tool_profile = SimpleNamespace()
        condition = SimpleNamespace(
            TypeId="Fem::ConstraintForce",
            Proxy=None,
            Label="Punch force",
            References=[(tool_profile, ["Edge1"])],
            Force=500.0,
            Direction=(tool_profile, ["Edge1"]),
            DirectionVector=SimpleNamespace(x=0.0, y=1.0, z=0.0),
            Active=True,
        )
        tool = SimpleNamespace(
            Shape=tool_profile, ToolId="tool-punch-id",
            ToolName="Punch", Label="CTform Tool: Punch"
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Press",
            StartTime=0.0,
            EndTime=1.0,
            Increments=10,
            MechanicalBCs=[condition],
            ThermalBCs=[],
            ToolMotions=[],
        )

        exported = loadsteps_to_dict(
            SimpleNamespace(LoadSteps=[step], Tools=[tool])
        )["loadSteps"][0]

        self.assertEqual(exported["tools"][0]["forceTarget"], 500.0)
        self.assertEqual(exported["tools"][0]["motion"]["axis"], "Z")

    def test_radial_native_tool_force_is_not_mapped_to_axial_control(self):
        tool_profile = SimpleNamespace()
        condition = SimpleNamespace(
            TypeId="Fem::ConstraintForce",
            Proxy=None,
            Label="Radial punch force",
            References=[(tool_profile, ["Edge1"])],
            Force=500.0,
            Direction=(tool_profile, ["Edge1"]),
            DirectionVector=SimpleNamespace(x=1.0, y=0.0, z=0.0),
            Active=True,
        )
        tool = SimpleNamespace(
            Shape=tool_profile,
            ToolId="tool-punch-id",
            ToolName="Punch",
            Label="CTform Tool: Punch",
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Press",
            StartTime=0.0,
            EndTime=1.0,
            Increments=10,
            MechanicalBCs=[condition],
            ThermalBCs=[],
            ToolMotions=[],
        )

        with self.assertRaisesRegex(ValueError, "requires an axial FEM force"):
            loadsteps_to_dict(SimpleNamespace(LoadSteps=[step], Tools=[tool]))

    def test_native_tool_temperature_condition_is_rejected(self):
        tool_profile = SimpleNamespace()
        condition = SimpleNamespace(
            TypeId="Fem::ConstraintTemperature",
            Proxy=None,
            Label="Punch temperature",
            References=[(tool_profile, ["Face1"])],
            Temperature=650.0,
            Active=True,
        )
        tool = SimpleNamespace(
            Shape=tool_profile, ToolId="tool-punch-id",
            ToolName="Punch", Label="CTform Tool: Punch"
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Heat",
            StartTime=0.0,
            EndTime=1.0,
            Increments=1,
            MechanicalBCs=[],
            ThermalBCs=[condition],
            ToolMotions=[],
        )

        with self.assertRaisesRegex(ValueError, "thermal boundary conditions on Tool"):
            loadsteps_to_dict(
                SimpleNamespace(LoadSteps=[step], Tools=[tool])
            )

    def test_native_workpiece_temperature_remains_a_thermal_boundary_condition(self):
        condition = SimpleNamespace(
            TypeId="Fem::ConstraintTemperature",
            Proxy=None,
            Label="Workpiece temperature BC",
            References=[],
            Temperature=650.0,
            Active=True,
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Thermal hold",
            StartTime=0.0,
            EndTime=1.0,
            Increments=1,
            MechanicalBCs=[],
            ThermalBCs=[condition],
            ToolMotions=[],
        )

        exported = loadsteps_to_dict(SimpleNamespace(LoadSteps=[step]))["loadSteps"][0]

        self.assertEqual(exported["thermalBCs"][0]["type"], "Temperature")
        self.assertEqual(exported["thermalBCs"][0]["value"], 650.0)

    def test_native_workpiece_force_is_rejected(self):
        condition = SimpleNamespace(
            TypeId="Fem::ConstraintForce",
            Proxy=None,
            Label="Unsupported workpiece force",
            References=[],
            Force=500.0,
            Direction=SimpleNamespace(x=0.0, y=1.0, z=0.0),
            Active=True,
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Press",
            StartTime=0.0,
            EndTime=1.0,
            Increments=1,
            MechanicalBCs=[condition],
            ThermalBCs=[],
            ToolMotions=[],
        )

        with self.assertRaisesRegex(ValueError, "force conditions only as force-controlled tool motion"):
            loadsteps_to_dict(SimpleNamespace(LoadSteps=[step]))

    def test_native_body_heat_source_maps_to_heat_generation(self):
        profile = SimpleNamespace(Shape=SimpleNamespace())
        proxy = type("ConstraintBodyHeatSource", (), {})()
        condition = SimpleNamespace(
            TypeId="Fem::ConstraintPython",
            Proxy=proxy,
            Label="Workpiece heat source",
            References=[(profile, [])],
            HeatSource=12.5,
            Active=True,
        )
        step = SimpleNamespace(
            StepId=1,
            StepName="Heat",
            StartTime=0.0,
            EndTime=1.0,
            Increments=1,
            MechanicalBCs=[],
            ThermalBCs=[condition],
            ToolMotions=[],
        )

        exported = loadsteps_to_dict(SimpleNamespace(LoadSteps=[step]))["loadSteps"][0]
        bc = exported["thermalBCs"][0]

        self.assertEqual(bc["type"], "HeatGeneration")
        self.assertEqual(bc["value"], 12.5)
        self.assertEqual(bc["target"], "All")

    def test_thermal_exports_initial_temperature_from_solver(self):
        solver = SimpleNamespace(
            InitialWorkpieceTemperature=1423.15, InitialToolTemperature=473.15
        )
        with patch("freecad.CTformFreeCADInterface.case_export.find_solver", return_value=solver):
            exported = thermal_to_dict(SimpleNamespace())

        self.assertEqual(
            exported["initialTemperature"], {"workpiece": 1423.15, "tools": 473.15}
        )

    def test_tool_motion_without_tool_id_resolves_it_from_tool_name(self):
        tool = SimpleNamespace(ToolId="upper-punch", ToolName="UpperPunch", Label="UpperPunch")
        motion = SimpleNamespace(ToolName="UpperPunch", Vz=-1.0)
        step = SimpleNamespace(
            StepId=1, StepName="Press", StartTime=0.0, EndTime=1.0, Increments=1,
            MechanicalBCs=[], ThermalBCs=[], ToolMotions=[motion],
        )

        exported = loadsteps_to_dict(SimpleNamespace(LoadSteps=[step], Tools=[tool]))

        self.assertEqual(exported["loadSteps"][0]["tools"][0]["toolId"], "upper-punch")

    def test_readiness_reports_features_core_v2_rejects(self):
        convection = SimpleNamespace(
            TypeId="Fem::ConstraintHeatflux", Proxy=None, Label="Air", References=[]
        )
        step = SimpleNamespace(
            StepId=1, MechanicalBCs=[], ThermalBCs=[convection], ToolMotions=[]
        )
        case = SimpleNamespace(LoadSteps=[step], Tools=[])
        issues = _core_v2_unsupported_issues(
            case,
            {"elementTypes": ["Tri3", "Quad4"]},
            {"materials": [{"name": "Steel", "constitutive": {"model": "TabulatedFlowStress"}}]},
            SimpleNamespace(RemeshEnabled=True),
        )

        self.assertEqual(len(issues), 4)
        self.assertTrue(any("Remesh" in issue for issue in issues))
        self.assertTrue(any("Tri3 and Quad4" in issue for issue in issues))
        self.assertTrue(any("TabulatedFlowStress" in issue for issue in issues))
        self.assertTrue(any("Temperature thermal" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
