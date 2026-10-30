# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Export the native FreeCAD FEM Gmsh setup as a package-local MSH2 file."""

from __future__ import annotations

import hashlib
import re
import shlex
from pathlib import Path


_SUPPORTED_ELEMENT_ORDERS = {"1st"}


def _is_supported_mesh_dimension(mesh_object: object) -> bool:
    dimension = str(getattr(mesh_object, "ElementDimension", ""))
    if dimension == "2D":
        return True
    if dimension != "From Shape":
        return False
    shape_link = getattr(mesh_object, "Shape", None)
    shape = getattr(shape_link, "Shape", shape_link)
    return str(getattr(shape, "ShapeType", "")) in ("Face", "Shell")


def export_gmsh_mesh(
    mesh_object: object,
    output_path: str | Path,
    *,
    structured_element_size: float | None = None,
) -> dict[str, object]:
    """Run the assigned FEM Gmsh object and save its mesh as native Gmsh MSH2.

    FreeCAD FEM's task panel normally saves the generated mesh as UNV for its
    in-document visualization. This repeats that object's Gmsh setup, emits the
    package MSH2 from the same Gmsh run, and refreshes the FEM preview from UNV.

    With ``structured_element_size`` (millimetres) the four-edge sheet face gets a
    transfinite, recombined Quad4 grid instead of Gmsh's free mesh.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not _is_supported_mesh_dimension(mesh_object):
        raise ValueError(
            "CTform v2 requires a 2D FreeCAD FEM/Gmsh mesh; set ElementDimension "
            "to 2D or use From Shape with a Face/Shell geometry"
        )
    if str(getattr(mesh_object, "ElementOrder", "1st")) not in _SUPPORTED_ELEMENT_ORDERS:
        raise ValueError(
            "CTform v2 currently supports first-order Tri3/Quad4 Gmsh meshes only. "
            "Use Mesh From Shape by Gmsh, set ElementOrder to '1st', and regenerate."
        )

    from femmesh.gmshtools import GmshTools

    gmsh = GmshTools(mesh_object)
    gmsh.prepare()
    geo_path = Path(gmsh.temp_file_geo)
    geo_text = _pin_physical_group_ids(geo_path.read_text(encoding="utf-8"))
    if structured_element_size is not None:
        geometry = getattr(mesh_object.Shape, "Shape", mesh_object.Shape)  # a feature link or a shape
        lines = structured_sheet_lines(geometry, structured_element_size)
        geo_text = inject_after_merge(geo_text, lines)
    geo_text += "\n// CTform package mesh export\n"
    geo_text += "Mesh.SaveAll = 0;\n"
    geo_text += "Mesh.MshFileVersion = 2.2;\n"
    geo_text += "Mesh.ScalingFactor = 1.0000000000000000e-03;\n"
    geo_text += f"Save {_quote_geo_path(output)};\n"
    geo_path.write_text(geo_text, encoding="utf-8")

    diagnostics = gmsh.run_gmsh_with_geo()
    if getattr(gmsh, "error", False):
        raise RuntimeError(f"FreeCAD FEM Gmsh export failed: {diagnostics}")
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(
            "Gmsh did not create the package MSH2 file. "
            f"Diagnostics: {diagnostics or 'no diagnostic output'}"
        )

    gmsh.read_and_set_new_mesh()
    groups = read_msh2_physical_names(output)
    if not groups:
        raise ValueError("The Gmsh package mesh contains no physical groups")
    fem_mesh = mesh_object.FemMesh
    face_ids = tuple(getattr(fem_mesh, "Faces", ()) or ())
    face_node_counts = {
        len(fem_mesh.getElementNodes(element_id)) for element_id in face_ids
    }
    element_types = []
    if face_node_counts == {3}:
        element_types = ["Tri3"]
    elif face_node_counts == {4}:
        element_types = ["Quad4"]
    elif face_node_counts == {3, 4}:
        element_types = ["Tri3", "Quad4"]
    else:
        raise ValueError(f"Unsupported 2D element node counts: {sorted(face_node_counts)}")
    return {
        "format": "gmsh-msh2",
        "lengthUnit": "m",
        "nodeCount": len(fem_mesh.Nodes),
        "elementCount": len(face_ids),
        "elementTypes": element_types,
        "physicalGroups": groups,
    }


def read_msh2_physical_names(path: str | Path) -> list[dict[str, object]]:
    """Read MSH2 $PhysicalNames records for inclusion in case.json."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    try:
        marker = lines.index("$PhysicalNames")
        count = int(lines[marker + 1])
    except (ValueError, IndexError) as error:
        raise ValueError("Gmsh mesh is missing a valid $PhysicalNames section") from error
    groups = []
    for line in lines[marker + 2 : marker + 2 + count]:
        parts = shlex.split(line)
        if len(parts) != 3:
            raise ValueError(f"Invalid Gmsh physical-group record: {line!r}")
        dimension, group_id = int(parts[0]), int(parts[1])
        groups.append({"id": group_id, "name": parts[2], "dimension": dimension})
    return groups


def _quote_geo_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _pin_physical_group_ids(geo_text: str) -> str:
    """Make Gmsh physical tags deterministic from each group's dimension/name."""
    pattern = re.compile(
        r'^(?P<head>\s*Physical\s+(?P<kind>Point|Line|Surface|Volume)\s*\()'
        r'(?P<name>"(?:\\.|[^"\\])*")'
        r'(?P<tail>\s*(?:,\s*\d+)?\)\s*=\s*\{[^}]*\};\s*)$',
        re.MULTILINE,
    )
    dimensions = {"Point": 0, "Line": 1, "Surface": 2, "Volume": 3}
    seen: dict[int, tuple[int, str]] = {}

    def replace(match):
        name = shlex.split(match.group("name"))[0]
        dimension = dimensions[match.group("kind")]
        group_id = _physical_tag(dimension, name)
        previous = seen.get(group_id)
        if previous is not None and previous != (dimension, name):
            raise ValueError(f"Physical group ID collision: {previous[1]!r} and {name!r}")
        seen[group_id] = (dimension, name)
        tail = re.sub(r"^\s*,\s*\d+", "", match.group("tail"))
        return f"{match.group('head')}{match.group('name')}, {group_id}{tail}"

    return pattern.sub(replace, geo_text)


def _physical_tag(dimension: int, name: str) -> int:
    digest = hashlib.sha256(f"{dimension}:{name}".encode("utf-8")).digest()
    return (int.from_bytes(digest[:4], "big") & 0x3FFFFFFF) or 1


_MERGE_LINE = re.compile(r'^\s*Merge\s+"[^"]*";\s*$', re.MULTILINE)


def structured_sheet_lines(shape: object, element_size: float) -> list[str]:
    """Return the Gmsh lines for a structured Quad4 grid on the sheet face of ``shape``.

    The curve and surface tags are the FreeCAD indices of the edges and face, which
    GmshTools also uses for its physical groups (EdgeN). ``element_size`` is in
    millimetres, the unit of the FreeCAD document the geometry is merged in.
    """
    faces = list(getattr(shape, "Faces", ()) or ())
    if len(faces) != 1:
        raise ValueError("Structured sheet meshing needs a shape with exactly one face")
    face = faces[0]
    loop = list(face.OuterWire.OrderedEdges)
    if len(loop) != 4 or len(face.Edges) != 4:
        raise ValueError("Structured sheet meshing needs a face bounded by exactly four edges")
    edge_tags = [_shape_index(shape.Edges, edge) for edge in loop]
    return structured_grid_lines(
        edge_tags,
        [edge.Length for edge in loop],
        element_size,
        surface_tag=_shape_index(shape.Faces, face),
    )


def structured_grid_lines(
    edge_tags: list[int],
    lengths: list[float],
    element_size: float,
    surface_tag: int = 1,
) -> list[str]:
    """Return transfinite and recombine lines for a four-edge face.

    ``edge_tags`` and ``lengths`` are in boundary order, so opposite edges are
    positions 0/2 and 1/3. Each edge must be a whole number of elements long, so
    the elements stay square; opposite edges must then have the same count.
    """
    if len(edge_tags) != 4 or len(lengths) != 4:
        raise ValueError("A structured sheet needs four edges")
    if element_size <= 0.0:
        raise ValueError("The structured element size must be positive")
    elements = []
    for length in lengths:
        ratio = length / element_size
        if abs(ratio - round(ratio)) > 1e-6 or round(ratio) < 1:
            raise ValueError(
                f"Edge length {length:g} is not a whole number of {element_size:g} elements"
            )
        elements.append(round(ratio))
    if elements[0] != elements[2] or elements[1] != elements[3]:
        raise ValueError(
            f"Opposite sheet edges need the same element count; got {elements} "
            f"for lengths {lengths} and size {element_size:g}"
        )
    nodes = [count + 1 for count in elements]
    return [
        f"Transfinite Curve {{{edge_tags[0]}, {edge_tags[2]}}} = {nodes[0]} Using Progression 1;",
        f"Transfinite Curve {{{edge_tags[1]}, {edge_tags[3]}}} = {nodes[1]} Using Progression 1;",
        f"Transfinite Surface {{{surface_tag}}};",
        f"Recombine Surface {{{surface_tag}}};",
    ]


def inject_after_merge(geo_text: str, lines: list[str]) -> str:
    """Insert ``lines`` right after the Merge of the geometry, before any mesh settings."""
    match = _MERGE_LINE.search(geo_text)
    if match is None:
        raise ValueError("The Gmsh geometry has no Merge line to attach the structured sheet to")
    block = "\n// CTform structured sheet: transfinite Quad4 grid\n" + "\n".join(lines) + "\n"
    return geo_text[: match.end()] + block + geo_text[match.end() :]


def _shape_index(items, target) -> int:
    """Return the 1-based FreeCAD index of ``target`` in ``items``."""
    for index, item in enumerate(items, start=1):
        if item.isSame(target):
            return index
    raise ValueError("The sheet edge or face is not part of the mesh shape")
