# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""CTform load-step and process-condition document objects."""


class CTformLoadStep:
    """A process interval serialized into loadsteps.json."""

    def __init__(self, obj):
        self.Object = obj
        self._add_properties()

    def dumps(self):
        return None

    def loads(self, state):
        return None

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

    def onDocumentRestored(self, obj=None):
        if obj is not None:
            self.Object = obj
        self._add_properties()
        self._migrate_legacy_links()
        _sync_condition_links(self.Object)

    def onChanged(self, obj, property_name):
        if property_name == "Group":
            _sync_condition_links(obj)

    def _migrate_legacy_links(self):
        obj = self.Object
        existing = list(getattr(obj, "Group", ()) or ())
        legacy = []
        for property_name in ("MechanicalBCs", "ThermalBCs", "ToolMotions"):
            legacy.extend(getattr(obj, property_name, ()) or ())
        for condition in legacy:
            if condition not in existing:
                obj.addObject(condition)
                existing.append(condition)


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

    def dumps(self):
        return None

    def loads(self, state):
        return None


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

    def dumps(self):
        return None

    def loads(self, state):
        return None


def make_load_step(doc, analysis, name="CTformLoadStep"):
    obj = doc.addObject("App::DocumentObjectGroupPython", name)
    obj.Label = "CTform Load Step"
    obj.Proxy = CTformLoadStep(obj)
    analysis.addObject(obj)
    _link_to_case(analysis, "LoadSteps", obj)
    return obj


def clone_load_step(doc, analysis, source_step):
    """Deep-copy a load step and its native condition children."""
    clone = make_load_step(doc, analysis)
    case = _case_for_analysis(analysis)
    steps = getattr(case, "LoadSteps", ()) if case is not None else ()
    clone.StepId = max((getattr(step, "StepId", 0) for step in steps), default=0) + 1
    clone.StepName = f"{getattr(source_step, 'StepName', 'LoadStep')} Copy"
    clone.StartTime = getattr(source_step, "StartTime", 0.0)
    clone.EndTime = getattr(source_step, "EndTime", 1.0)
    clone.Increments = getattr(source_step, "Increments", 1)
    clone.Active = getattr(source_step, "Active", True)
    clone.Label = f"CTform Load Step {clone.StepId}: {clone.StepName}"

    children = list(getattr(source_step, "Group", ()) or ())
    children.extend(
        condition
        for property_name in ("MechanicalBCs", "ThermalBCs", "ToolMotions")
        for condition in (getattr(source_step, property_name, ()) or ())
        if condition not in children
    )
    for child in children:
        if fem_condition_category(child) is None and not _is_tool_motion(child):
            continue
        copied = doc.copyObject(child, False)
        if copied is None:
            raise RuntimeError(f"Could not clone load-step condition {child.Label}")
        clone.addObject(copied)
    _sync_condition_links(clone)
    return clone


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
    """Add a supported mechanical condition to a load-step folder."""
    if fem_condition_category(condition) != "mechanical":
        raise ValueError("Condition is not a supported CTform mechanical condition")
    attach_condition(load_step, condition)


def attach_thermal_condition(load_step, condition):
    """Add a supported thermal condition to a load-step folder."""
    if fem_condition_category(condition) != "thermal":
        raise ValueError("Condition is not a supported CTform thermal condition")
    attach_condition(load_step, condition)


def attach_condition(load_step, condition):
    """Add a supported native FEM condition as a child of the load-step group."""
    if fem_condition_category(condition) is None:
        raise ValueError("Unsupported FEM condition for CTform load steps")
    if condition not in (getattr(load_step, "Group", ()) or ()):
        load_step.addObject(condition)
    _sync_condition_links(load_step)


def detach_condition(load_step, condition, analysis=None):
    """Move a native FEM condition from a step group back to the analysis root."""
    if condition not in (getattr(load_step, "Group", ()) or ()):
        raise ValueError("Condition is not a child of the selected load step")
    analysis = analysis or find_analysis_for_step(load_step)
    if analysis is None:
        raise ValueError("Load step is not linked to its CTform analysis")
    load_step.removeObject(condition)
    analysis.addObject(condition)
    _sync_condition_links(load_step)


def find_analysis_for_step(load_step):
    """Find the FEM analysis that directly owns a load-step group."""
    return next(
        (
            parent
            for parent in (getattr(load_step, "InList", ()) or ())
            if getattr(parent, "TypeId", "") == "Fem::FemAnalysis"
        ),
        None,
    )


def fem_condition_kind(condition):
    """Return the supported native FEM condition kind, if any."""
    type_name = " ".join(
        (
            str(getattr(condition, "TypeId", "")),
            type(getattr(condition, "Proxy", None)).__name__,
        )
    ).lower()
    if "constraintbodyheatsource" in type_name:
        return "heat_generation"
    if "constraintheatflux" in type_name:
        return "heat_flux"
    if "constrainttemperature" in type_name and "initial" not in type_name:
        return "temperature"
    if "ctformmechanicalbc" in type_name:
        return str(getattr(condition, "Type", "Fixed")).lower()
    for kind in ("fixed", "displacement", "force"):
        if f"constraint{kind}" in type_name:
            return kind
    return None


def fem_condition_category(condition):
    """Return the CTform load-step category for a supported FEM condition."""
    kind = fem_condition_kind(condition)
    if kind in ("temperature", "heat_flux", "heat_generation"):
        return "thermal"
    if kind in ("fixed", "displacement", "force"):
        return "mechanical"
    return None


def condition_targets_role(condition, case, role):
    """Return whether a native condition references an object assigned the role."""
    references = getattr(condition, "References", ()) or ()
    referenced_objects = [
        reference[0]
        for reference in references
        if isinstance(reference, (tuple, list)) and reference
    ]
    return any(
        getattr(assignment, "Role", "") == role
        and any(getattr(assignment, "Target", None) is obj for obj in referenced_objects)
        for assignment in (getattr(case, "RoleAssignments", ()) or ())
    )


def _add(obj, name, property_type, group, default):
    if name not in obj.PropertiesList:
        obj.addProperty(property_type, name, group)
        if property_type == "App::PropertyEnumeration":
            setattr(obj, name, default)
            setattr(obj, name, default[0])
        else:
            setattr(obj, name, default)


def _link_to_case(analysis, property_name, obj):
    case = _case_for_analysis(analysis)
    if case is None:
        return
    if property_name not in case.PropertiesList:
        case.addProperty("App::PropertyLinkList", property_name, "CTform")
    _append_link(case, property_name, obj)


def _case_for_analysis(analysis):
    return next(
        (
            member
            for member in (getattr(analysis, "Group", ()) or ())
            if type(getattr(member, "Proxy", None)).__name__ == "CTformCase"
        ),
        None,
    )


def _append_link(obj, property_name, value):
    values = list(getattr(obj, property_name, ()) or ())
    if value not in values:
        values.append(value)
        setattr(obj, property_name, values)


def _sync_condition_links(step):
    proxy = getattr(step, "Proxy", None)
    if getattr(proxy, "_syncing", False):
        return
    if proxy is not None:
        proxy._syncing = True
    try:
        mechanical = []
        thermal = []
        tool_motions = []
        for child in getattr(step, "Group", ()) or ():
            category = fem_condition_category(child)
            if category == "mechanical":
                mechanical.append(child)
            elif category == "thermal":
                thermal.append(child)
            elif (
                getattr(child, "Proxy", None) is not None
                and "ctformtoolmotion" in type(child.Proxy).__name__.lower()
            ):
                tool_motions.append(child)
        step.MechanicalBCs = mechanical
        step.ThermalBCs = thermal
        step.ToolMotions = tool_motions
    finally:
        if proxy is not None:
            proxy._syncing = False


def _is_tool_motion(obj):
    proxy = getattr(obj, "Proxy", None)
    return proxy is not None and "ctformtoolmotion" in type(proxy).__name__.lower()
