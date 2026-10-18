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


def export_gmsh_mesh(mesh_object: object, output_path: str | Path) -> dict[str, object]:
    """Run the assigned FEM Gmsh object and save its mesh as native Gmsh MSH2.

    FreeCAD FEM's task panel normally saves the generated mesh as UNV for its
    in-document visualization. This repeats that object's Gmsh setup, emits the
    package MSH2 from the same Gmsh run, and refreshes the FEM preview from UNV.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not _is_supported_mesh_dimension(mesh_object):
        raise ValueError(
            "CTform v2 requires a 2D FreeCAD FEM/Gmsh mesh; set ElementDimension "
            "to 2D or use From Shape with a Face/Shell geometry"
        )
    if str(getattr(mesh_object, "ElementOrder", "1st")) not in _SUPPORTED_ELEMENT_ORDERS:
        raise ValueError("CTform v2 currently supports first-order Tri3/Quad4 Gmsh meshes only")

    from femmesh.gmshtools import GmshTools

    gmsh = GmshTools(mesh_object)
    gmsh.prepare()
    geo_path = Path(gmsh.temp_file_geo)
    geo_text = _pin_physical_group_ids(geo_path.read_text(encoding="utf-8"))
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
