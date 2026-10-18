# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from freecad.CTformFreeCADInterface.gmsh_package import (
    _pin_physical_group_ids,
    _is_supported_mesh_dimension,
    export_gmsh_mesh,
    read_msh2_physical_names,
)


class GmshPackageTests(unittest.TestCase):
    def test_from_shape_accepts_two_dimensional_profiles(self):
        for shape_type in ("Face", "Shell"):
            with self.subTest(shape_type=shape_type):
                mesh = SimpleNamespace(
                    ElementDimension="From Shape",
                    Shape=SimpleNamespace(Shape=SimpleNamespace(ShapeType=shape_type)),
                )
                self.assertTrue(_is_supported_mesh_dimension(mesh))

    def test_from_shape_rejects_non_two_dimensional_shapes(self):
        mesh = SimpleNamespace(
            ElementDimension="From Shape",
            Shape=SimpleNamespace(Shape=SimpleNamespace(ShapeType="Solid")),
        )
        self.assertFalse(_is_supported_mesh_dimension(mesh))

    def test_explicit_mesh_dimension_requires_two_dimensions(self):
        mesh = SimpleNamespace(ElementDimension="3D", Shape=None)
        self.assertFalse(_is_supported_mesh_dimension(mesh))
        mesh.ElementDimension = "2D"
        self.assertTrue(_is_supported_mesh_dimension(mesh))

    def test_second_order_mesh_error_points_to_ctform_mesher(self):
        mesh = SimpleNamespace(ElementDimension="2D", ElementOrder="2nd")
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "ElementOrder to '1st'"):
                export_gmsh_mesh(mesh, Path(directory) / "workpiece.msh")

    def test_physical_group_tags_are_deterministic(self):
        geo = '\n'.join(
            (
                'Physical Surface("Workpiece") = {1};',
                'Physical Line("Outer Edge") = {2, 3};',
            )
        )

        first = _pin_physical_group_ids(geo)
        second = _pin_physical_group_ids(geo)

        self.assertEqual(first, second)
        self.assertIn('Physical Surface("Workpiece", ', first)
        self.assertIn('Physical Line("Outer Edge", ', first)

    def test_physical_names_are_read_from_msh2(self):
        mesh_text = '\n'.join(
            (
                "$MeshFormat",
                "2.2 0 8",
                "$EndMeshFormat",
                "$PhysicalNames",
                "2",
                '1 701 "Outer Edge"',
                '2 901 "Workpiece"',
                "$EndPhysicalNames",
                "$Nodes",
                "0",
                "$EndNodes",
                "$Elements",
                "0",
                "$EndElements",
                "",
            )
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.msh"
            path.write_text(mesh_text, encoding="utf-8")
            groups = read_msh2_physical_names(path)

        self.assertEqual(
            groups,
            [
                {"id": 701, "name": "Outer Edge", "dimension": 1},
                {"id": 901, "name": "Workpiece", "dimension": 2},
            ],
        )

    def test_missing_physical_names_fails(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.msh"
            path.write_text("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"missing a valid \$PhysicalNames"):
                read_msh2_physical_names(path)


if __name__ == "__main__":
    unittest.main()
