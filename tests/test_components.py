import unittest
from types import SimpleNamespace

from freecad.CTformFreeCADInterface.analysis import CTformCase, CTformSolver, make_case
from freecad.CTformFreeCADInterface.components import make_tool, make_workpiece
from freecad.CTformFreeCADInterface.contacts import make_contact_pair


class FakeObject:
    def __init__(self, name):
        self.Name = name
        self.Label = name
        self.PropertiesList = []
        self.Group = []
        self.InList = []

    def addProperty(self, property_type, name, group):
        self.PropertiesList.append(name)
        defaults = {
            "App::PropertyString": "",
            "App::PropertyFloat": 0.0,
            "App::PropertyInteger": 0,
            "App::PropertyBool": False,
            "App::PropertyLink": None,
            "App::PropertyLinkList": [],
        }
        setattr(self, name, defaults.get(property_type))

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
        obj = FakeObject(name)
        obj.TypeId = object_type
        obj.Document = self
        self.Objects.append(obj)
        return obj


class ComponentFolderTests(unittest.TestCase):
    def setUp(self):
        self.doc = FakeDocument()
        self.analysis = FakeObject("CTformAnalysis")
        self.case = SimpleNamespace(Workpiece=None, Tools=[])

    def test_workpiece_folder_links_shape_and_rejects_duplicate(self):
        shape = SimpleNamespace(Label="Blank")
        workpiece = make_workpiece(
            self.doc, self.analysis, self.case, shape
        )

        self.assertIs(workpiece.Shape, shape)
        self.assertIn(shape, workpiece.Group)
        self.assertEqual(workpiece.Label, "CTform Workpiece: Blank")
        self.assertIs(self.case.Workpiece, workpiece)
        self.assertIn(workpiece, self.analysis.Group)
        self.assertEqual(workpiece.ContactPairs, [])

        with self.assertRaisesRegex(ValueError, "only one workpiece"):
            make_workpiece(self.doc, self.analysis, self.case, shape)

    def test_document_rejects_a_second_ctform_case(self):
        make_case(self.doc)

        with self.assertRaisesRegex(ValueError, "only one CTform case"):
            make_case(self.doc)

    def test_tool_folder_links_shape_and_is_registered_on_case(self):
        shape = SimpleNamespace(Label="PunchBody")
        tool = make_tool(self.doc, self.analysis, self.case, shape, "UpperPunch")

        self.assertIs(tool.Shape, shape)
        self.assertIn(shape, tool.Group)
        self.assertEqual(tool.ToolName, "UpperPunch")
        self.assertTrue(tool.ToolId)
        self.assertEqual(tool.Label, "CTform Tool: UpperPunch")
        self.assertEqual(self.case.Tools, [tool])
        self.assertIn(tool, self.analysis.Group)

    def test_model_and_execution_settings_belong_to_solver_not_case(self):
        case_obj = FakeObject("CTformCase")
        CTformCase(case_obj, self.analysis)
        solver_obj = FakeObject("CTformSolver")
        CTformSolver(solver_obj)

        self.assertIn("Workpiece", case_obj.PropertiesList)
        self.assertIn("Tools", case_obj.PropertiesList)
        self.assertIn("LoadSteps", case_obj.PropertiesList)
        self.assertNotIn("ModelingType", case_obj.PropertiesList)
        self.assertNotIn("Dimension", case_obj.PropertiesList)
        self.assertIn("ModelingType", solver_obj.PropertiesList)
        self.assertIn("Dimension", solver_obj.PropertiesList)
        self.assertIn("MechanicalFormulation", solver_obj.PropertiesList)
        self.assertIn("ContactModel", solver_obj.PropertiesList)
        self.assertIn("OutputDirectory", solver_obj.PropertiesList)

    def test_contact_pair_is_owned_by_workpiece_and_links_tool(self):
        self.case.Workpiece = make_workpiece(
            self.doc, self.analysis, self.case, SimpleNamespace(Label="Blank")
        )
        tool = make_tool(
            self.doc, self.analysis, self.case, SimpleNamespace(Label="Punch"), "Punch"
        )

        pair = make_contact_pair(self.doc, self.case.Workpiece, tool)

        self.assertIs(pair.Tool, tool)
        self.assertIn(pair, self.case.Workpiece.ContactPairs)
        self.assertIn(pair, self.case.Workpiece.Group)


if __name__ == "__main__":
    unittest.main()