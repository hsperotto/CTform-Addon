# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""FreeCAD document object for a CTform case."""


class CTformCase:
    """Proxy for the CTform case settings object."""

    def __init__(self, obj, analysis):
        self.Object = obj
        self.Analysis = analysis
        self._add_properties()

    def _add_properties(self):
        obj = self.Object
        self._add_case_properties()

    def _add_case_properties(self):
        obj = self.Object
        string_properties = (
            ("SimulationName", "Case", "ctform_case"),
            ("Process", "Case", "forging"),
            ("CaseDirectory", "Case", ""),
            ("CaseFile", "Case", "case.json"),
            ("MaterialFile", "Files", "material.json"),
            ("LoadStepsFile", "Files", "loadsteps.json"),
            ("ThermalFile", "Files", "thermal.json"),
            ("OutputDirectory", "Output", "results_case"),
            ("ContactModel", "Contact", "node_to_segment"),
        )
        for name, group, default in string_properties:
            if name not in obj.PropertiesList:
                obj.addProperty("App::PropertyString", name, group)
                setattr(obj, name, default)

        enum_properties = (
            ("ModelingType", "Simulation", ["axisymmetric", "plane_strain"], "axisymmetric"),
            ("MechanicalFormulation", "Simulation", ["flow", "displacement"], "flow"),
        )
        for name, group, values, default in enum_properties:
            if name not in obj.PropertiesList:
                obj.addProperty("App::PropertyEnumeration", name, group)
                setattr(obj, name, values)
                setattr(obj, name, default)

        integer_properties = (("VtkEvery", "Output", 1),)
        for name, group, default in integer_properties:
            if name not in obj.PropertiesList:
                obj.addProperty("App::PropertyInteger", name, group)
                setattr(obj, name, default)

        float_properties = (
            ("TargetCompression", "Run", 7.0),
            ("InitialGap", "Contact", 0.05),
            ("PenetrationTolerance", "Contact", 1e-2),
            ("GapTolerance", "Contact", 1e-6),
            ("ZBottom", "Contact", 0.0),
        )
        for name, group, default in float_properties:
            if name not in obj.PropertiesList:
                obj.addProperty("App::PropertyFloat", name, group)
                setattr(obj, name, default)

        bool_properties = (
            ("NodalCsvEnabled", "Output", False),
            ("GeometryOnly", "Run", False),
            ("AugmentedLagrangeEnabled", "Contact", True),
            ("ThermalContactEnabled", "Contact", False),
            ("ALEEnabled", "Advanced", False),
            ("RemeshEnabled", "Advanced", False),
        )
        for name, group, default in bool_properties:
            if name not in obj.PropertiesList:
                obj.addProperty("App::PropertyBool", name, group)
                setattr(obj, name, default)

        if "RoleAssignments" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkList", "RoleAssignments", "CTform")
        if "LoadSteps" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkList", "LoadSteps", "CTform")

        if "AnalysisType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "AnalysisType", "CTform")
            obj.AnalysisType = "CTform 2D"
        if "Plane" not in obj.PropertiesList:
            obj.addProperty("App::PropertyEnumeration", "Plane", "2D")
            obj.Plane = ["XY"]
            obj.Plane = "XY"
        if "PlaneTolerance" not in obj.PropertiesList:
            obj.addProperty("App::PropertyFloat", "PlaneTolerance", "2D")
            obj.PlaneTolerance = 1e-7
        if "Status" not in obj.PropertiesList:
            obj.addProperty("App::PropertyEnumeration", "Status", "CTform")
            obj.Status = ["New", "Ready", "Invalid", "Completed"]
            obj.Status = "New"

    def onDocumentRestored(self):
        self._add_properties()


def make_case(doc, name="CTformCase"):
    """Create a native FEM analysis with a CTform case child object."""
    analysis = doc.addObject("Fem::FemAnalysis", "CTformAnalysis")
    analysis.Label = "CTform Case"

    case = doc.addObject("App::FeaturePython", name)
    case.Label = "CTform Case Settings"
    case.addProperty("App::PropertyLink", "Analysis", "CTform")
    case.Analysis = analysis
    case.Proxy = CTformCase(case, analysis)
    analysis.addObject(case)

    if "CTformCase" not in analysis.PropertiesList:
        analysis.addProperty("App::PropertyLink", "CTformCase", "CTform")
    analysis.CTformCase = case
    return case


def make_solver(doc, case=None, name="CTformSolver"):
    """Create a CTform solver/job object under the native FEM analysis."""
    if case is None:
        case = next(
            (
                obj
                for obj in doc.Objects
                if hasattr(obj, "Proxy") and isinstance(obj.Proxy, CTformCase)
            ),
            None,
        )
    if case is None:
        raise ValueError("Create a CTform case before creating its solver")

    analysis = case.Analysis
    solver = doc.addObject("Fem::FemSolverObjectPython", name)
    solver.Label = "CTform Solver"
    solver.addProperty("App::PropertyLink", "Case", "CTform")
    solver.Case = case
    solver.addProperty("App::PropertyEnumeration", "Status", "CTform")
    solver.Status = ["New", "Ready", "Running", "Completed", "Failed"]
    solver.Status = "New"
    solver.addProperty("App::PropertyString", "CaseDirectory", "CTform")
    solver.CaseDirectory = case.CaseDirectory
    analysis.addObject(solver)

    if "Solver" not in case.PropertiesList:
        case.addProperty("App::PropertyLink", "Solver", "CTform")
    case.Solver = solver
    return solver


def find_case(doc):
    """Return the first CTform case settings object in a document."""
    return next(
        (
            obj
            for obj in doc.Objects
            if isinstance(getattr(obj, "Proxy", None), CTformCase)
        ),
        None,
    )


CTformAnalysis = CTformCase
make_analysis = make_case
