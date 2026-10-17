# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

from types import SimpleNamespace
import unittest

from freecad.CTformFreeCADInterface.validation import validate_points, validate_shape


class ValidationTests(unittest.TestCase):
    def test_points_on_xy_plane_are_valid(self):
        points = [SimpleNamespace(z=0.0), SimpleNamespace(z=1e-8)]

        report = validate_points(points, tolerance=1e-7)

        self.assertTrue(report.is_valid)

    def test_off_plane_point_is_rejected(self):
        report = validate_points([SimpleNamespace(z=1e-4)], tolerance=1e-7)

        self.assertFalse(report.is_valid)
        self.assertEqual(report.issues[0].code, "geometry_off_xy_plane")

    def test_solid_shape_is_rejected(self):
        shape = SimpleNamespace(
            Solids=[object()],
            Vertexes=[SimpleNamespace(Point=SimpleNamespace(z=0.0))],
        )

        report = validate_shape(shape, tolerance=1e-7)

        self.assertFalse(report.is_valid)
        self.assertEqual(report.issues[0].code, "solid_geometry_not_supported")


if __name__ == "__main__":
    unittest.main()
