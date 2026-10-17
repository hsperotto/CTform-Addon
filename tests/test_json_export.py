# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

import json
import unittest

from freecad.CTformFreeCADInterface.json_export import dumps_si


class ScientificJsonTests(unittest.TestCase):
    def test_physical_floats_use_scientific_notation_and_round_trip(self):
        data = {"length": 0.001, "stress": 200000000.0, "count": 2, "active": True}

        output = dumps_si(data)
        loaded = json.loads(output)

        self.assertIn("1.0000000000000000e-03", output)
        self.assertIn("2.0000000000000000e+08", output)
        self.assertIn('"count": 2', output)
        self.assertIn('"active": true', output)
        self.assertEqual(loaded, data)

    def test_non_finite_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be finite"):
            dumps_si({"value": float("nan")})


if __name__ == "__main__":
    unittest.main()
