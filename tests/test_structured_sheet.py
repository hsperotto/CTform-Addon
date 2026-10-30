# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

import collections
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from freecad.CTformFreeCADInterface.gmsh_package import (
    inject_after_merge,
    structured_grid_lines,
)

GMSH = Path(os.environ.get("CTFORM_GMSH", r"C:\Program Files\FreeCAD 1.1\bin\gmsh.exe"))

# Sheet meridian of the thesis: radius (blank radius) x 1 mm thickness, 0.25 mm elements.
THICKNESS_MM = 1.0
ELEMENT_MM = 0.25


def _grid(radius_mm):
    """Return the four-edge grid lines for a sheet of the given radius, in boundary order."""
    return structured_grid_lines(
        [1, 2, 3, 4], [radius_mm, THICKNESS_MM, radius_mm, THICKNESS_MM], ELEMENT_MM, surface_tag=1
    )


class StructuredGridCountTests(unittest.TestCase):
    def test_thesis_blanks_give_the_expected_element_counts(self):
        # 90, 100 and 110 mm blanks: radius 45, 50, 55 mm -> 180, 200, 220 x 4 quads.
        for radius_mm, along in ((45.0, 180), (50.0, 200), (55.0, 220)):
            with self.subTest(radius=radius_mm):
                lines = _grid(radius_mm)
                self.assertIn(f"Transfinite Curve {{1, 3}} = {along + 1} Using Progression 1;", lines)
                self.assertIn("Transfinite Curve {2, 4} = 5 Using Progression 1;", lines)
                self.assertIn("Transfinite Surface {1};", lines)
                self.assertIn("Recombine Surface {1};", lines)

    def test_edge_that_is_not_a_whole_number_of_elements_is_rejected(self):
        with self.assertRaises(ValueError):
            structured_grid_lines([1, 2, 3, 4], [45.1, 1, 45.1, 1], ELEMENT_MM)

    def test_opposite_edges_with_different_counts_are_rejected(self):
        with self.assertRaises(ValueError):
            structured_grid_lines([1, 2, 3, 4], [45, 1, 40, 1], ELEMENT_MM)

    def test_non_positive_size_is_rejected(self):
        with self.assertRaises(ValueError):
            structured_grid_lines([1, 2, 3, 4], [45, 1, 45, 1], 0.0)


class InjectionTests(unittest.TestCase):
    def test_lines_go_right_after_the_merge_and_before_the_mesh_settings(self):
        geo = (
            '// open brep geometry\n'
            'Merge "sheet.brep";\n'
            '\n'
            'Mesh.CharacteristicLengthMax = 0.25;\n'
            'Mesh 2;\n'
        )

        out = inject_after_merge(geo, _grid(45.0))

        merge_at = out.index('Merge "sheet.brep";')
        grid_at = out.index("Transfinite Curve {1, 3} = 181")
        mesh_at = out.index("Mesh 2;")
        self.assertLess(merge_at, grid_at)
        self.assertLess(grid_at, mesh_at)

    def test_geometry_without_a_merge_line_is_rejected(self):
        with self.assertRaises(ValueError):
            inject_after_merge("Mesh 2;\n", _grid(45.0))


def _gmsh_or_skip():
    if not GMSH.is_file():
        raise unittest.SkipTest(f"Gmsh not found at {GMSH}; set CTFORM_GMSH to run this test")
    return GMSH


class GmshElementCountTests(unittest.TestCase):
    def test_gmsh_meshes_the_thesis_sheet_with_720_square_quads(self):
        gmsh = _gmsh_or_skip()
        # Explicit 45 x 1 mm rectangle (mm); curves 1..4 are the four edges in loop order.
        geo = "\n".join([
            "lc = 0.25;",
            "Point(1) = {0, 0, 0, lc};",
            "Point(2) = {45, 0, 0, lc};",
            "Point(3) = {45, 1, 0, lc};",
            "Point(4) = {0, 1, 0, lc};",
            "Line(1) = {1, 2};",
            "Line(2) = {2, 3};",
            "Line(3) = {3, 4};",
            "Line(4) = {4, 1};",
            "Curve Loop(1) = {1, 2, 3, 4};",
            "Plane Surface(1) = {1};",
            *_grid(45.0),
            "Physical Surface(\"Sheet\") = {1};",
            "Mesh.ElementOrder = 1;",
            "Mesh.ScalingFactor = 1.0e-03;",
            "Mesh.MshFileVersion = 2.2;",
            "Mesh 2;",
            "",
        ])
        with tempfile.TemporaryDirectory() as folder:
            geo_path = Path(folder) / "sheet.geo"
            msh_path = Path(folder) / "sheet.msh"
            geo_path.write_text(geo, encoding="utf-8")
            subprocess.run(
                [str(gmsh), str(geo_path), "-2", "-format", "msh2", "-o", str(msh_path)],
                check=True, capture_output=True, timeout=120,
            )
            counts = _element_type_counts(msh_path)

        self.assertEqual(counts.get(3, 0), 720)  # Quad4
        self.assertEqual(counts.get(2, 0), 0)  # no triangles


def _element_type_counts(path):
    text = Path(path).read_text(encoding="utf-8")
    body = text.split("$Elements", 1)[1].split("$EndElements", 1)[0].splitlines()[2:]
    return collections.Counter(int(line.split()[1]) for line in body if line.strip())


if __name__ == "__main__":
    unittest.main()
