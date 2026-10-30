# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

import unittest
from types import SimpleNamespace

from freecad.CTformFreeCADInterface.properties import add_property, length_to_si


class FakeObject:
    """Stands in for a FreeCAD document object: a property list and attributes."""

    def __init__(self):
        self.PropertiesList = []

    def addProperty(self, property_type, name, group):
        self.PropertiesList.append(name)


class AddPropertyTests(unittest.TestCase):
    def test_adds_the_property_and_sets_its_default(self):
        obj = FakeObject()

        add_property(obj, "Friction", "App::PropertyFloat", "Friction", 0.3)

        self.assertEqual(obj.PropertiesList, ["Friction"])
        self.assertEqual(obj.Friction, 0.3)

    def test_existing_property_keeps_the_user_value(self):
        obj = FakeObject()
        add_property(obj, "Friction", "App::PropertyFloat", "Friction", 0.3)
        obj.Friction = 0.05

        add_property(obj, "Friction", "App::PropertyFloat", "Friction", 0.3)

        self.assertEqual(obj.PropertiesList, ["Friction"])
        self.assertEqual(obj.Friction, 0.05)

    def test_enumeration_takes_its_first_choice_as_value(self):
        obj = FakeObject()

        add_property(obj, "FrictionModel", "App::PropertyEnumeration", "Friction",
                     ["coulomb", "levanov", "none"])

        self.assertEqual(obj.FrictionModel, "coulomb")

    def test_none_default_leaves_no_value_set(self):
        obj = FakeObject()

        add_property(obj, "Shape", "App::PropertyLink", "Component", None)

        self.assertEqual(obj.PropertiesList, ["Shape"])
        self.assertFalse(hasattr(obj, "Shape"))


class LengthToSiTests(unittest.TestCase):
    def test_plain_number_is_millimetres(self):
        self.assertAlmostEqual(length_to_si(5.0), 0.005)

    def test_quantity_is_converted_to_metres(self):
        quantity = SimpleNamespace(getValueAs=lambda unit: 0.25 if unit == "m" else None)

        self.assertEqual(length_to_si(quantity), 0.25)


if __name__ == "__main__":
    unittest.main()
