# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""FreeCAD document object for a CTform case."""


class CTformCase:
    """Proxy for the CTform case settings object."""

    def __init__(self, obj, analysis):
        self.Object = obj
        self.Analysis = analysis
        self._add_properties()

    def dumps(self):
        return None

    def loads(self, state):
        return None

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
            ("MaterialsFile", "Files", "materials.json"),
            ("MeshFile", "Files", "workpiece.msh"),
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

        integer_properties = (
            ("PackageSchemaVersion", "Files", 2),
            ("VtkEvery", "Output", 1),
        )
        for name, group, default in integer_properties:
            if name not in obj.PropertiesList:
                obj.addProperty("App::PropertyInteger", name, group)
                setattr(obj, name, default)
        obj.setEditorMode("PackageSchemaVersion", 1)
        obj.setEditorMode("MaterialFile", 2)

        thermal_float_properties = (
            ("WorkpieceInitialTemperature", "Thermal", 293.15),
            ("ToolInitialTemperature", "Thermal", 293.15),
            ("ThermalPlasticEfficiency", "Thermal", 0.9),
            ("ThermalFrictionEfficiency", "Thermal", 0.0),
            ("FrictionHeatPartitionToWorkpiece", "Thermal", 1.0),
            ("FrictionHeatLayerDepth", "Thermal", 0.5),
        )
        for name, group, default in thermal_float_properties:
            if name not in obj.PropertiesList:
                obj.addProperty("App::PropertyFloat", name, group)
                setattr(obj, name, default)

        if "FrictionHeatDistribution" not in obj.PropertiesList:
            obj.addProperty("App::PropertyEnumeration", "FrictionHeatDistribution", "Thermal")
            obj.FrictionHeatDistribution = ["uniform", "exponential"]
            obj.FrictionHeatDistribution = "uniform"

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
        if "Materials" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkList", "Materials", "CTform")
        if "ContactPairs" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkList", "ContactPairs", "CTform")
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

    def onDocumentRestored(self, obj=None):
        if obj is not None:
            self.Object = obj
        self.Analysis = analysis_for_case(self.Object)
        if self.Analysis is None:
            self.Analysis = getattr(self.Object, "Analysis", None)
        if self.Analysis is not None:
            if "Analysis" in self.Object.PropertiesList:
                self.Object.Analysis = None
            if (
                "CTformCase" in self.Analysis.PropertiesList
                and getattr(self.Analysis, "CTformCase", None) is self.Object
            ):
                self.Analysis.CTformCase = None
        self._add_properties()


def make_case(doc, name="CTformCase"):
    """Create a native FEM analysis with a CTform case child object."""
    analysis = doc.addObject("Fem::FemAnalysis", "CTformAnalysis")
    analysis.Label = "CTform Case"

    case = doc.addObject("App::FeaturePython", name)
    case.Label = "CTform Case Settings"
    case.Proxy = CTformCase(case, analysis)
    analysis.addObject(case)
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

    analysis = analysis_for_case(case)
    if analysis is None:
        raise ValueError("The CTform case is not a child of a FEM analysis")
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

    return solver


def analysis_for_case(case):
    """Return the FEM analysis that owns the CTform case settings object."""
    for parent in getattr(case, "InList", ()) or ():
        if (
            getattr(parent, "TypeId", "") == "Fem::FemAnalysis"
            and case in (getattr(parent, "Group", ()) or ())
        ):
            return parent
    legacy_analysis = getattr(case, "Analysis", None)
    if getattr(legacy_analysis, "TypeId", "") == "Fem::FemAnalysis":
        return legacy_analysis
    return None


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
