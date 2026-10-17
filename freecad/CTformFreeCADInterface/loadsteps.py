# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""CTform load-step and process-condition document objects."""


class CTformLoadStep:
    """A process interval serialized into loadsteps.json."""

    def __init__(self, obj):
        self.Object = obj
        self._add_properties()

    def _add_properties(self):
        obj = self.Object
        _add(obj, "StepId", "App::PropertyInteger", "Load Step", 1)
        _add(obj, "StepName", "App::PropertyString", "Load Step", "LoadStep")
        _add(obj, "StartTime", "App::PropertyFloat", "Load Step", 0.0)
        _add(obj, "EndTime", "App::PropertyFloat", "Load Step", 1.0)
        _add(obj, "Increments", "App::PropertyInteger", "Load Step", 1)
        _add(obj, "Active", "App::PropertyBool", "Load Step", True)
        _add(obj, "MechanicalBCs", "App::PropertyLinkList", "Conditions", [])
        _add(obj, "ThermalBCs", "App::PropertyLinkList", "Conditions", [])
        _add(obj, "ToolMotions", "App::PropertyLinkList", "Conditions", [])

    def onDocumentRestored(self):
        self._add_properties()


class CTformMechanicalBC:
    """Mechanical boundary condition belonging to a load step."""

    def __init__(self, obj):
        self.Object = obj
        _add(obj, "BCId", "App::PropertyInteger", "Boundary Condition", 1)
        _add(obj, "Name", "App::PropertyString", "Boundary Condition", "BoundaryCondition")
        _add(obj, "Type", "App::PropertyString", "Boundary Condition", "Fixed")
        _add(obj, "Axis", "App::PropertyEnumeration", "Boundary Condition", ["X", "Y", "Z"])
        obj.Axis = "Z"
        _add(obj, "Target", "App::PropertyString", "Boundary Condition", "")
        _add(obj, "Value", "App::PropertyFloat", "Boundary Condition", 0.0)
        _add(obj, "Active", "App::PropertyBool", "Boundary Condition", True)


class CTformToolMotion:
    """Tool motion and optional thermal fields for one load step."""

    def __init__(self, obj):
        self.Object = obj
        _add(obj, "MotionId", "App::PropertyInteger", "Tool Motion", 1000)
        _add(obj, "ToolName", "App::PropertyString", "Tool Motion", "")
        _add(obj, "Vx", "App::PropertyFloat", "Tool Motion", 0.0)
        _add(obj, "Vy", "App::PropertyFloat", "Tool Motion", 0.0)
        _add(obj, "Vz", "App::PropertyFloat", "Tool Motion", 0.0)
        _add(obj, "Active", "App::PropertyBool", "Tool Motion", True)
        _add(obj, "InitialTemperature", "App::PropertyFloat", "Thermal", 293.15)
        _add(obj, "HeatTransferCoefficient", "App::PropertyFloat", "Thermal", 0.0)


def make_load_step(doc, analysis, name="CTformLoadStep"):
    obj = doc.addObject("App::DocumentObjectGroupPython", name)
    obj.Label = "CTform Load Step"
    obj.Proxy = CTformLoadStep(obj)
    analysis.addObject(obj)
    _link_to_case(analysis, "LoadSteps", obj)
    return obj


def make_mechanical_bc(doc, analysis, load_step, name="CTformMechanicalBC"):
    obj = doc.addObject("App::FeaturePython", name)
    obj.Label = "CTform Mechanical BC"
    obj.Proxy = CTformMechanicalBC(obj)
    analysis.addObject(obj)
    _append_link(load_step, "MechanicalBCs", obj)
    return obj


def make_tool_motion(doc, analysis, load_step, name="CTformToolMotion"):
    obj = doc.addObject("App::FeaturePython", name)
    obj.Label = "CTform Tool Motion"
    obj.Proxy = CTformToolMotion(obj)
    load_step.addObject(obj)
    _append_link(load_step, "ToolMotions", obj)
    return obj


def attach_mechanical_condition(load_step, condition):
    """Attach an existing FEM mechanical condition to a load step."""
    _append_link(load_step, "MechanicalBCs", condition)


def attach_thermal_condition(load_step, condition):
    """Attach an existing FEM thermal condition to a load step."""
    _append_link(load_step, "ThermalBCs", condition)


def _add(obj, name, property_type, group, default):
    if name not in obj.PropertiesList:
        obj.addProperty(property_type, name, group)
        if property_type == "App::PropertyEnumeration":
            setattr(obj, name, default)
            setattr(obj, name, default[0])
        else:
            setattr(obj, name, default)


def _link_to_case(analysis, property_name, obj):
    case = getattr(analysis, "CTformCase", None)
    if case is None:
        return
    if property_name not in case.PropertiesList:
        case.addProperty("App::PropertyLinkList", property_name, "CTform")
    _append_link(case, property_name, obj)


def _append_link(obj, property_name, value):
    values = list(getattr(obj, property_name, ()) or ())
    values.append(value)
    setattr(obj, property_name, values)
