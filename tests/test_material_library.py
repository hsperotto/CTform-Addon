import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from freecad.CTformFreeCADInterface.analysis import make_case
from freecad.CTformFreeCADInterface.components import make_tool, make_workpiece
from freecad.CTformFreeCADInterface.materials import (
    import_material_catalog,
    make_material,
    materials_in_case,
    materials_to_dict,
)


class FakeObject:
    def __init__(self, name, object_type="App::FeaturePython"):
        self.Name = name
        self.Label = name
        self.TypeId = object_type
        self.PropertiesList = []
        self.Group = []
        self.InList = []

    def addProperty(self, property_type, name, group):
        self.PropertiesList.append(name)
        setattr(self, name, None if property_type == "App::PropertyLink" else [])

    def addObject(self, obj):
        self.Group.append(obj)
        if hasattr(obj, "InList"):
            obj.InList.append(self)

    def setEditorMode(self, name, mode):
        pass


class FakeDocument:
    def __init__(self):
        self.Objects = []

    def addObject(self, object_type, name):
        obj = FakeObject(name, object_type)
        obj.Document = self
        self.Objects.append(obj)
        return obj


class MaterialLibraryTests(unittest.TestCase):
    def setUp(self):
        self.doc = FakeDocument()
        self.case = make_case(self.doc)
        self.analysis = next(obj for obj in self.doc.Objects if obj.TypeId == "Fem::FemAnalysis")
        self.workpiece = make_workpiece(
            self.doc, self.analysis, self.case, FakeObject("Blank", "Part::Feature")
        )
        self.tool = make_tool(
            self.doc, self.analysis, self.case, FakeObject("PunchBody", "Part::Feature"), "Punch"
        )

    @staticmethod
    def source_catalog():
        return {
            "materials": [
                {
                    "id": "old-long-source-id",
                    "name": "AISI H13 Tool Steel",
                    "constitutive": {
                        "model": "HenselSpittel",
                        "parameters": {"A": 1.2e9, "m1": 0.1, "m2": 0.2, "m3": 0.3, "m4": 0.4},
                    },
                    "elastic": {"youngModulus": 2.1e11, "poissonRatio": 0.3},
                    "thermal": {
                        "density": 7800.0,
                        "thermalExpansionCoefficient": 1.2e-5,
                        "thermalConductivity": 30.0,
                        "specificHeat": 460.0,
                    },
                }
            ]
        }

    def test_case_owns_shared_material_library_and_components_link_same_material(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "materials.json"
            path.write_text(json.dumps(self.source_catalog()), encoding="utf-8")

            imported = import_material_catalog(
                self.doc, self.analysis, self.case, path
            )

        material = imported[0]
        self.workpiece.Material = material
        self.tool.Material = material

        self.assertEqual(self.case.MaterialLibrary.Label, "CTform Materials")
        self.assertIn(material, self.case.MaterialLibrary.Group)
        self.assertIs(self.workpiece.Material, self.tool.Material)
        self.assertEqual(material.MaterialId, "aisi-h13-tool-steel")
        self.assertEqual(material.Model, "HenselSpittel")
        self.assertEqual(material.HenselSpittelA, 1.2e9)
        self.assertEqual(len(materials_to_dict(self.case)["materials"]), 1)

    def test_importing_the_same_catalog_twice_does_not_duplicate_material(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "materials.json"
            path.write_text(json.dumps(self.source_catalog()), encoding="utf-8")
            first = import_material_catalog(self.doc, self.analysis, self.case, path)
            second = import_material_catalog(self.doc, self.analysis, self.case, path)

        self.assertIs(first[0], second[0])
        self.assertEqual(len(materials_in_case(self.case)), 1)

    def test_manual_material_creation_from_library_does_not_assign_component(self):
        material = make_material(
            self.doc, self.analysis, self.case, "Manual Test Steel"
        )

        self.assertIn(material, self.case.MaterialLibrary.Group)
        self.assertEqual(material.MaterialId, "manual-test-steel")
        self.assertIsNone(self.workpiece.Material)

    def test_invalid_catalog_does_not_partially_import(self):
        catalog = self.source_catalog()
        catalog["materials"].append({"name": "Incomplete"})
        with TemporaryDirectory() as directory:
            path = Path(directory) / "materials.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "needs a name, constitutive"):
                import_material_catalog(self.doc, self.analysis, self.case, path)

        self.assertEqual(materials_in_case(self.case), [])


if __name__ == "__main__":
    unittest.main()