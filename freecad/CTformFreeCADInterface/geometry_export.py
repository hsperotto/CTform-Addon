# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Export Workpiece and Tool geometry as Core-readable ASCII DXF snapshots."""

from __future__ import annotations

from pathlib import Path

from .components import CTformTool, CTformWorkpiece
from .dxf_writer import arc_primitive, polyline_primitives, write_dxf


def export_component_geometry(component: object, output_path: str | Path) -> dict[str, object]:
    """Export a component's planar profile as ASCII DXF in SI meters."""
    import FreeCAD as App

    target = getattr(component, "Shape", None)
    shape = getattr(target, "Shape", None)
    if target is None or shape is None or shape.isNull():
        raise ValueError(f"Component {getattr(component, 'Label', 'geometry')!r} has no exportable Shape")
    if getattr(shape, "Solids", ()):
        raise ValueError("CTform 2D geometry export accepts profiles/faces, not solids")
    edges = tuple(getattr(shape, "Edges", ()) or ())
    if not edges:
        raise ValueError(f"Component {getattr(component, 'Label', 'geometry')!r} has no profile edges")

    is_workpiece = isinstance(getattr(component, "Proxy", None), CTformWorkpiece)
    is_tool = isinstance(getattr(component, "Proxy", None), CTformTool)
    if not is_workpiece and not is_tool:
        raise ValueError(f"Unsupported CTform geometry component: {component.Label!r}")
    tool_layer = _validate_layer_name(getattr(component, "ToolLayer", "") or "ToolProfile")
    placement = target.getGlobalPlacement()
    layers: dict[str, list[dict]] = {}
    for index, edge in enumerate(edges, start=1):
        world_edge = edge.copy().transformShape(placement.Matrix, True, True)
        bounds = world_edge.BoundBox
        if max(abs(bounds.ZMin), abs(bounds.ZMax), bounds.ZLength) > 1e-7:
            raise ValueError(
                f"Geometry edge Edge{index} is outside the XY plane after placement and cannot be exported as 2D DXF"
            )
        layer = f"Edge{index}" if is_workpiece else tool_layer
        layers.setdefault(layer, []).extend(_edge_primitives(world_edge))
    if not any(layers.values()):
        raise ValueError("DXF export contains no Core-supported 2D profile entities")

    output = write_dxf(output_path, layers)
    return {
        "format": "dxf-ascii-r12",
        "lengthUnit": "m",
        "layers": sorted(layers),
        "file": output.as_posix(),
    }


_MM_TO_M = 1e-3


def _edge_primitives(edge) -> list[dict]:
    """Convert one FreeCAD edge (mm, in the XY plane) to DXF primitives in meters.

    Lines and circular arcs stay exact; any other curve is discretized.
    """
    curve_type = type(edge.Curve).__name__
    first, last = edge.FirstParameter, edge.LastParameter

    def point(parameter):
        value = edge.valueAt(parameter)
        return (value.x * _MM_TO_M, value.y * _MM_TO_M)

    if curve_type in ("Line", "LineSegment"):
        return polyline_primitives([point(first), point(last)])
    if curve_type == "Circle":
        center = edge.Curve.Center
        center_m = (center.x * _MM_TO_M, center.y * _MM_TO_M)
        radius_m = edge.Curve.Radius * _MM_TO_M
        if edge.isClosed():
            return [{"type": "CIRCLE", "center": center_m, "radius": radius_m}]
        return [arc_primitive(center_m, point(first), point((first + last) / 2.0), point(last))]
    points = [(p.x * _MM_TO_M, p.y * _MM_TO_M) for p in edge.discretize(Deflection=1e-3)]
    return polyline_primitives(points)


def _validate_layer_name(name: str) -> str:
    if not name or not name.isascii() or any(character in name for character in ('"', "\n", "\r")):
        raise ValueError(f"DXF layer name must be non-empty ASCII text: {name!r}")
    return name
