# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Dimension-neutral CTform case and solver document objects."""


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
            ("LoadStepsFile", "Files", "loadsteps.json"),
            ("ThermalFile", "Files", "thermal.json"),
        )
        for name, group, default in string_properties:
            if name not in obj.PropertiesList:
                obj.addProperty("App::PropertyString", name, group)
                setattr(obj, name, default)

        integer_properties = (("PackageSchemaVersion", "Files", 2),)
        for name, group, default in integer_properties:
            if name not in obj.PropertiesList:
                obj.addProperty("App::PropertyInteger", name, group)
                setattr(obj, name, default)
        obj.setEditorMode("PackageSchemaVersion", 1)

        if "Workpiece" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Workpiece", "Components")
        if "Tools" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkList", "Tools", "Components")
        if "MaterialLibrary" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "MaterialLibrary", "Components")
        if "LoadSteps" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLinkList", "LoadSteps", "CTform")
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


class CTformSolver:
    """Solver-owned modeling, numerical, thermal, run, and output settings."""

    def __init__(self, obj):
        self.Object = obj
        self._add_properties()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def onDocumentRestored(self, obj=None):
        if obj is not None:
            self.Object = obj
        self._add_properties()

    def _add_properties(self):
        obj = self.Object
        enum_properties = (
            ("Dimension", "Model", ["2D", "3D"], "2D"),
            ("ModelingType", "Model", ["axisymmetric", "plane_strain"], "axisymmetric"),
            ("MechanicalFormulation", "Model", ["flow", "displacement"], "flow"),
            ("Plane", "Model", ["XY"], "XY"),
            ("FrictionHeatDistribution", "Thermal", ["uniform", "exponential"], "uniform"),
        )
        for name, group, values, default in enum_properties:
            if name not in obj.PropertiesList:
                obj.addProperty("App::PropertyEnumeration", name, group)
                setattr(obj, name, values)
                setattr(obj, name, default)

        string_properties = (
            ("OutputDirectory", "Output", "results_case"),
            ("ContactModel", "Contact", "node_to_segment"),
            ("CoreExecutable", "External Tools", ""),
            ("GmshExecutable", "External Tools", ""),
            ("MmgDirectory", "External Tools", ""),
            ("AnalysisType", "Model", "CTform"),
        )
        for name, group, default in string_properties:
            _add(obj, name, "App::PropertyString", group, default)

        float_properties = (
            ("ThermalPlasticEfficiency", "Thermal", 0.9),
            ("ThermalFrictionEfficiency", "Thermal", 0.0),
            ("FrictionHeatPartitionToWorkpiece", "Thermal", 1.0),
            ("FrictionHeatLayerDepth", "Thermal", 0.5),
            ("InitialWorkpieceTemperature", "Thermal", 293.15),
            ("InitialToolTemperature", "Thermal", 293.15),
            ("TargetCompression", "Run", 7.0),
            ("InitialGap", "Contact", 0.05),
            ("PenetrationTolerance", "Contact", 1e-2),
            ("GapTolerance", "Contact", 1e-6),
            ("ZBottom", "Contact", 0.0),
            ("PlaneTolerance", "Model", 1e-7),
        )
        for name, group, default in float_properties:
            _add(obj, name, "App::PropertyFloat", group, default)

        integer_properties = (("VtkEvery", "Output", 1),)
        for name, group, default in integer_properties:
            _add(obj, name, "App::PropertyInteger", group, default)

        bool_properties = (
            ("NodalCsvEnabled", "Output", False),
            ("GeometryOnly", "Run", False),
            ("AugmentedLagrangeEnabled", "Contact", True),
            ("ThermalContactEnabled", "Contact", False),
            ("ExportTargetCompression", "Run", True),
            ("ALEEnabled", "Advanced", False),
            ("RemeshEnabled", "Advanced", False),
        )
        for name, group, default in bool_properties:
            _add(obj, name, "App::PropertyBool", group, default)

        if "Status" not in obj.PropertiesList:
            obj.addProperty("App::PropertyEnumeration", "Status", "CTform")
            obj.Status = ["New", "Ready", "Running", "Completed", "Failed"]
            obj.Status = "New"
        if "Case" not in obj.PropertiesList:
            obj.addProperty("App::PropertyLink", "Case", "CTform")


def apply_isothermal_preset(solver, temperature_k=293.15):
    """Set the Solver parameters that keep a case isothermal at ``temperature_k``.

    No master switch exists: plastic and friction heating are set to zero,
    thermal contact is off, and the sheet and tools start at the same
    temperature. Thermal boundary conditions are simply not added.
    """
    solver.ThermalPlasticEfficiency = 0.0
    solver.ThermalFrictionEfficiency = 0.0
    solver.ThermalContactEnabled = False
    solver.InitialWorkpieceTemperature = float(temperature_k)
    solver.InitialToolTemperature = float(temperature_k)


def make_case(doc, name="CTformCase"):
    """Create a native FEM analysis with a CTform case child object."""
    if find_case(doc) is not None:
        raise ValueError("A document can contain only one CTform case")
    analysis = doc.addObject("Fem::FemAnalysis", "CTformAnalysis")
    analysis.Label = "CTform Case"

    case = doc.addObject("App::FeaturePython", name)
    case.Label = "CTform Case Settings"
    case.Proxy = CTformCase(case, analysis)
    analysis.addObject(case)
    from .materials import ensure_material_library

    ensure_material_library(doc, analysis, case)
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
    if find_solver(case) is not None:
        raise ValueError("This CTform case already has a Solver")
    solver = doc.addObject("Fem::FemSolverObjectPython", name)
    solver.Label = "CTform Solver"
    solver.Proxy = CTformSolver(solver)
    solver.Case = case
    analysis.addObject(solver)

    return solver


def _add(obj, name, property_type, group, default):
    if name not in obj.PropertiesList:
        obj.addProperty(property_type, name, group)
        setattr(obj, name, default)


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


def find_solver(case):
    """Return the CTform Solver owned by the same FEM Analysis as the case."""
    analysis = analysis_for_case(case)
    if analysis is None:
        return None
    return next(
        (
            member
            for member in (getattr(analysis, "Group", ()) or ())
            if isinstance(getattr(member, "Proxy", None), CTformSolver)
            and getattr(member, "Case", None) is case
        ),
        None,
    )


CTformAnalysis = CTformCase
make_analysis = make_case
