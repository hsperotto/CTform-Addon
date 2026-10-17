# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Export role geometry as Core-readable ASCII DXF snapshots."""

from __future__ import annotations

from pathlib import Path


def export_role_geometry(role_assignment: object, output_path: str | Path) -> dict[str, object]:
    """Export the assigned planar profile as ASCII DXF scaled to SI meters."""
    import FreeCAD as App
    import Part

    target = getattr(role_assignment, "Target", None)
    shape = getattr(target, "Shape", None)
    if target is None or shape is None or shape.isNull():
        raise ValueError(f"Role {getattr(role_assignment, 'Label', 'geometry')!r} has no exportable Shape")
    if getattr(shape, "Solids", ()):
        raise ValueError("CTform 2D geometry export accepts profiles/faces, not solids")
    edges = tuple(getattr(shape, "Edges", ()) or ())
    if not edges:
        raise ValueError(f"Role {getattr(role_assignment, 'Label', 'geometry')!r} has no profile edges")

    role = str(getattr(role_assignment, "Role", ""))
    if role not in ("workpiece", "tool"):
        raise ValueError(f"Unsupported CTform geometry role: {role}")
    tool_layer = _validate_layer_name(getattr(role_assignment, "ToolLayer", "") or "ToolProfile")
    temporary_document = None
    created = []
    try:
        temporary_document = App.newDocument("CTformDxfExport")
        placement = target.getGlobalPlacement()
        scale = App.Matrix()
        scale.scale(1e-3, 1e-3, 1e-3)
        scaled_edges = []
        for index, edge in enumerate(edges, start=1):
            world_edge = edge.copy().transformShape(placement.Matrix, True, True)
            bounds = world_edge.BoundBox
            if max(abs(bounds.ZMin), abs(bounds.ZMax), bounds.ZLength) > 1e-7:
                raise ValueError(
                    f"Geometry edge Edge{index} is outside the XY plane after placement and cannot be exported as 2D DXF"
                )
            si_edge = world_edge.transformShape(scale, True, True)
            if role == "workpiece":
                export_obj = temporary_document.addObject("Part::Feature", f"Edge{index}")
                export_obj.Shape = si_edge
                created.append(export_obj)
            else:
                scaled_edges.append(si_edge)

        if role == "tool":
            export_obj = temporary_document.addObject("Part::Feature", tool_layer)
            export_obj.Shape = Part.makeCompound(scaled_edges)
            created.append(export_obj)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            import importDXF
        except ImportError:
            import sys
            import FreeCAD

            sys.path.append(FreeCAD.getHomePath() + "Mod/Draft")
            import importDXF

        importDXF.export(created, str(output), nospline=True, lwPoly=True)
        payload = output.read_bytes()
        if b"\x00" in payload:
            raise ValueError("FreeCAD DXF exporter produced binary output; ASCII DXF is required")
        text = payload.decode("ascii", errors="strict")
        dxf_lines = text.splitlines()
        entity_types = {
            dxf_lines[index + 1].strip()
            for index, code in enumerate(dxf_lines[:-1])
            if code.strip() == "0"
        }
        if "ENTITIES" not in text or not entity_types.intersection(
            {"LINE", "LWPOLYLINE", "ARC", "CIRCLE", "ELLIPSE"}
        ):
            raise ValueError("DXF export contains no Core-supported 2D profile entities")
        return {
            "format": "dxf-ascii-r12",
            "lengthUnit": "m",
            "layers": sorted({obj.Name for obj in created}),
            "file": output.as_posix(),
        }
    finally:
        if temporary_document is not None:
            App.closeDocument(temporary_document.Name)


def _validate_layer_name(name: str) -> str:
    if not name or not name.isascii() or any(character in name for character in ('"', "\n", "\r")):
        raise ValueError(f"DXF layer name must be non-empty ASCII text: {name!r}")
    return name
