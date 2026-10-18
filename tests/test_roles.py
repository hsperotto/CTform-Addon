import unittest
from types import SimpleNamespace

from freecad.CTformFreeCADInterface.roles import make_role_assignment


class FakeObject:
    def __init__(self, name):
        self.Name = name
        self.Label = name
        self.PropertiesList = []
        self.Group = []

    def addProperty(self, property_type, name, group):
        self.PropertiesList.append(name)
        defaults = {
            "App::PropertyString": "",
            "App::PropertyFloat": 0.0,
            "App::PropertyInteger": 0,
            "App::PropertyBool": False,
            "App::PropertyLink": None,
        }
        setattr(self, name, defaults.get(property_type))

    def addObject(self, obj):
        self.Group.append(obj)


class FakeDocument:
    def addObject(self, object_type, name):
        return FakeObject(name)


class CTformCase:
    pass


class RoleLabelTests(unittest.TestCase):
    def test_workpiece_label_includes_selected_shape_name(self):
        doc = FakeDocument()
        case = SimpleNamespace(Proxy=CTformCase(), RoleAssignments=[])
        analysis = FakeObject("CTformAnalysis")
        analysis.Group.append(case)
        target = SimpleNamespace(Label="Blank Profile")

        assignment = make_role_assignment(doc, analysis, target=target)

        self.assertEqual(assignment.Label, 'CTform Workpiece: "Blank Profile"')
        self.assertIs(assignment.Target, target)

    def test_tool_label_format_is_unchanged(self):
        doc = FakeDocument()
        case = SimpleNamespace(Proxy=CTformCase(), RoleAssignments=[])
        analysis = FakeObject("CTformAnalysis")
        analysis.Group.append(case)

        assignment = make_role_assignment(
            doc, analysis, target=SimpleNamespace(Label="PunchBody"), role="tool", tool_name="Punch"
        )

        self.assertEqual(assignment.Label, "CTform Tool: Punch")


if __name__ == "__main__":
    unittest.main()