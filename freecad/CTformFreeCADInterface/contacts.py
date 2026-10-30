# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Visible CTform Workpiece/Tool contact-pair objects."""

from __future__ import annotations

from .identifiers import readable_id
from .properties import add_property, length_to_si


class CTformContactPair:
    """A named contact interface owned by its Workpiece."""

    def __init__(self, obj):
        self.Object = obj
        self._add_properties()

    def dumps(self):
        return None

    def loads(self, state):
        return None

    def _add_properties(self):
        obj = self.Object
        add_property(obj, "PairId", "App::PropertyString", "Identity", "")
        add_property(obj, "PairName", "App::PropertyString", "Contact", "Workpiece Tool Contact")
        add_property(obj, "Tool", "App::PropertyLink", "Contact", None)
        add_property(obj, "SlavePhysicalGroup", "App::PropertyString", "Contact", "All")
        add_property(obj, "MasterPhysicalGroup", "App::PropertyString", "Contact", "")
        add_property(obj, "GapTolerance", "App::PropertyLength", "Normal", 0.0)
        add_property(obj, "Penalty", "App::PropertyFloat", "Normal", 0.0)  # 0 = Core default
        add_property(obj, "FrictionModel", "App::PropertyEnumeration", "Friction", ["coulomb", "levanov", "tresca", "none"])
        add_property(obj, "FrictionCoefficient", "App::PropertyFloat", "Friction", 0.3)
        add_property(obj, "LevanovM", "App::PropertyFloat", "Friction", 0.3)
        add_property(obj, "LevanovN", "App::PropertyFloat", "Friction", 1.25)
        add_property(obj, "ThermalEnabled", "App::PropertyBool", "Thermal Contact", False)
        add_property(obj, "HeatTransferCoefficient", "App::PropertyFloat", "Thermal Contact", 0.0)
        add_property(obj, "Active", "App::PropertyBool", "Contact", True)

    def onDocumentRestored(self, obj=None):
        if obj is not None:
            self.Object = obj
        self._add_properties()


def make_contact_pair(doc, workpiece, tool):
    """Create a contact pair owned by a Workpiece and linked to a Tool."""
    from .components import CTformTool, CTformWorkpiece

    if not isinstance(getattr(workpiece, "Proxy", None), CTformWorkpiece):
        raise ValueError("A CTform contact pair requires a Workpiece")
    if not isinstance(getattr(tool, "Proxy", None), CTformTool):
        raise ValueError("A CTform contact pair requires a Tool")
    obj = doc.addObject("App::FeaturePython", "CTformContactPair")
    obj.Proxy = CTformContactPair(obj)
    obj.Tool = tool
    tool_name = getattr(tool, "ToolName", "") or tool.Label
    obj.PairName = f"Workpiece to {tool_name}"
    obj.PairId = readable_id(
        obj.PairName,
        (getattr(pair, "PairId", "") for pair in (getattr(workpiece, "ContactPairs", ()) or ())),
        fallback="contact",
    )
    obj.Label = obj.PairName
    workpiece.addObject(obj)
    pairs = list(getattr(workpiece, "ContactPairs", ()) or ())
    if obj not in pairs:
        pairs.append(obj)
    workpiece.ContactPairs = pairs
    return obj


def contact_pair_to_dict(pair, mesh_groups=None):
    """Serialize a visible contact pair to the v2 contactInterfaces record."""
    from .components import CTformWorkpiece

    workpiece = next(
        (
            parent
            for parent in (getattr(pair, "InList", ()) or ())
            if isinstance(getattr(parent, "Proxy", None), CTformWorkpiece)
        ),
        None,
    )
    tool = getattr(pair, "Tool", None)
    if workpiece is None or tool is None:
        raise ValueError(f"Contact pair {getattr(pair, 'Label', 'Contact')} needs a Workpiece and Tool")
    slave_group = str(getattr(pair, "SlavePhysicalGroup", "All") or "All")
    master_group = str(getattr(pair, "MasterPhysicalGroup", "") or "")
    if mesh_groups is not None and slave_group != "All":
        group = next((item for item in mesh_groups if item["name"] == slave_group), None)
        if group is None:
            raise ValueError(f"Contact pair references unknown workpiece physical group {slave_group!r}")
        slave_reference = {"physicalGroupId": group["id"], "physicalGroup": slave_group}
    else:
        slave_reference = {"physicalGroup": slave_group}
    master_name = getattr(tool, "ToolName", "") or tool.Label
    master_tool_id = str(getattr(tool, "ToolId", ""))
    master_reference = {"name": master_name, "toolId": master_tool_id}
    if master_group:
        master_reference["physicalGroup"] = master_group
    record = {
        "id": str(getattr(pair, "PairId", "")),
        "name": str(getattr(pair, "PairName", getattr(pair, "Label", "Contact"))),
        "active": bool(getattr(pair, "Active", True)),
        "slave": {"body": "workpiece", **slave_reference},
        "master": {"body": "tool", **master_reference},
        "target": slave_group,
        "slaveBody": "workpiece",
        "masterBody": master_name,
        "masterToolId": master_tool_id,
        "masterPhysicalGroup": master_group,
        "gapTolerance": length_to_si(getattr(pair, "GapTolerance", 0.0)),
        "friction": {
            "type": str(getattr(pair, "FrictionModel", "coulomb")),
            "coefficient": float(getattr(pair, "FrictionCoefficient", 0.3)),
            "levanovM": float(getattr(pair, "LevanovM", 0.3)),
            "levanovN": float(getattr(pair, "LevanovN", 1.25)),
        },
        "thermal": {
            "enabled": bool(getattr(pair, "ThermalEnabled", False)),
            "heatTransferCoefficient": float(getattr(pair, "HeatTransferCoefficient", 0.0)),
        },
    }
    penalty = float(getattr(pair, "Penalty", 0.0) or 0.0)
    if penalty > 0.0:
        # Core's legacy loader reads contactInterfaces[].normal.penalty; the v2
        # normalizer does not keep it yet, so this is ignored until Core accepts it.
        record["normal"] = {"penalty": penalty}
    return record

