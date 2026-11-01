# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Generate the thesis test matrix (5 punches x 3 blanks) from tcc/Geometrias.FCStd.

Run with FreeCADCmd (needs FreeCAD and its Gmsh; not run by unittest):

    set CTFORM_TCC_OUT=C:\\ctf-probes\\tcc
    FreeCADCmd.exe tcc\\generate_assays.py

Geometry comes unchanged from Geometrias.FCStd (axisymmetric, mm: sketch X is
the radius, sketch Y the axial coordinate). In that drawing the punch nose
touches the blank top (y = 0), the blank holder rests on it (y = 0) and the
die top touches its underside (y = -1). Everything else here is a PLACEHOLDER
taken from probe_five_punch_export.py: stroke, press speed, holder pressure,
friction, mesh size. Optional switches:

    CTFORM_TCC_ONLY       comma list of case names to build (e.g. Cilinder_Blank90)
    CTFORM_TCC_STROKE     punch travel, mm (default 30)
    CTFORM_TCC_PUNCH_GAP  initial punch-to-blank gap, mm (default 0 = as drawn)
    CTFORM_TCC_HOLDER_GAP initial holder-to-blank gap, mm (default 0 = as drawn)
    CTFORM_TCC_MU         Coulomb friction (0 exports friction none; default 0.2)
    CTFORM_TCC_FORMULATION  flow (default) or displacement
    CTFORM_TCC_TOOL_MESH  tool-profile element size, mm (default 0.5)
    CTFORM_TCC_MESH_SCALE   multiplies the 0.25 mm sheet element size
"""

import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import FreeCAD as App
import ObjectsFem
import Part

from freecad.CTformFreeCADInterface import analysis, case_export, components, contacts
from freecad.CTformFreeCADInterface import loadsteps, materials

SOURCE = ROOT / "tcc" / "Geometrias.FCStd"
OUT = Path(os.environ.get("CTFORM_TCC_OUT", ROOT / "tcc" / "out"))
GMSH = os.environ.get("CTFORM_GMSH", r"C:\Program Files\FreeCAD 1.1\bin\gmsh.exe")
CATALOG = ROOT / "freecad" / "CTformFreeCADInterface" / "resources" / "materials" / (
    "aisi304-1mm-nunes2025.json"
)
MATERIAL = "AISI 304 1 mm, mean of 0/45/90 deg (Nunes 2025)"

PUNCHES = ["Cilinder", "Hemisphere", "FlatElipse", "DeepElipse", "VeryDeepElipse"]
BLANKS = ["Blank90", "Blank100", "Blank110"]

STROKE = float(os.environ.get("CTFORM_TCC_STROKE", "30"))
PUNCH_GAP = float(os.environ.get("CTFORM_TCC_PUNCH_GAP", "0"))
HOLDER_GAP = float(os.environ.get("CTFORM_TCC_HOLDER_GAP", "0"))
FRICTION = float(os.environ.get("CTFORM_TCC_MU", "0.2"))
PRESS_SPEED = 19.5  # mm/s, Rocha (2022); placeholder
PRESSURE_MPA = 5.0  # blank holder pressure; placeholder
TOOL_MESH_SIZE = float(os.environ.get("CTFORM_TCC_TOOL_MESH", "0.5"))  # mm; resolves the 5 mm radii
MESH_SCALE = float(os.environ.get("CTFORM_TCC_MESH_SCALE", "1"))


def faces_by_label(source):
    return {o.Label: o.Shape for o in source.Objects if o.TypeId == "Part::Face"}


def feature(doc, name, shape, dy=0.0):
    shape = shape.copy()
    if dy:
        shape.translate(App.Vector(0, dy, 0))
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    return obj


def build(shapes, punch_name, blank_name):
    doc = App.newDocument(f"{punch_name}_{blank_name}")
    case = analysis.make_case(doc)
    fem = analysis.analysis_for_case(case)
    solver = analysis.make_solver(doc, case)
    solver.Dimension = "2D"
    solver.ModelingType = "axisymmetric"
    solver.MechanicalFormulation = os.environ.get("CTFORM_TCC_FORMULATION", "flow")
    analysis.apply_isothermal_preset(solver)
    solver.ExportTargetCompression = False

    sheet = feature(doc, "Sheet", shapes[blank_name])
    punch = feature(doc, "PunchShape", shapes[punch_name], dy=PUNCH_GAP)
    die = feature(doc, "DieShape", shapes["Die"])
    holder = feature(doc, "HolderShape", shapes["BlankHolder"], dy=HOLDER_GAP)
    doc.recompute()

    workpiece = components.make_workpiece(doc, fem, case, sheet)
    tools = {
        "Punch": components.make_tool(doc, fem, case, punch, "Punch"),
        "Die": components.make_tool(doc, fem, case, die, "Die"),
        "BlankHolder": components.make_tool(doc, fem, case, holder, "BlankHolder"),
    }
    imported = {m.MaterialName: m for m in materials.import_material_catalog(doc, fem, case, CATALOG)}
    workpiece.Material = imported[MATERIAL]
    for tool in tools.values():
        tool.Material = imported["Rigid Tool Steel (placeholder)"]
        tool.ToolMeshSize = TOOL_MESH_SIZE

    mesh = ObjectsFem.makeMeshGmsh(doc, "SheetMesh")
    mesh.Shape = sheet
    mesh.ElementDimension = "2D"
    mesh.ElementOrder = "1st"
    mesh.CharacteristicLengthMax = f"{0.25 * MESH_SCALE} mm"
    mesh.CharacteristicLengthMin = f"{0.1 * MESH_SCALE} mm"
    workpiece.Mesh = mesh
    workpiece.addObject(mesh)
    doc.recompute()

    for tool in tools.values():
        pair = contacts.make_contact_pair(doc, workpiece, tool)
        pair.FrictionModel = "coulomb" if FRICTION > 0 else "none"
        pair.FrictionCoefficient = FRICTION

    total = PUNCH_GAP + STROKE
    step = loadsteps.make_load_step(doc, fem)
    step.StepName = "Press"
    step.StartTime = 0.0
    step.EndTime = total / PRESS_SPEED
    step.Increments = 100

    punch_disp = ObjectsFem.makeConstraintDisplacement(doc, "PunchDisplacement")
    punch_disp.References = [(punch, "Face1")]
    punch_disp.xFree = True
    punch_disp.yFree = False
    punch_disp.yDisplacement = f"{-total} mm"
    punch_disp.zFree = True
    fem.addObject(punch_disp)
    loadsteps.attach_condition(step, punch_disp)

    die_fixed = ObjectsFem.makeConstraintFixed(doc, "DieFixed")
    die_fixed.References = [(die, "Face1")]
    fem.addObject(die_fixed)
    loadsteps.attach_condition(step, die_fixed)

    # Core's flow formulation does not constrain r = 0 by itself.
    axis_edge = next(
        f"Edge{i}" for i, edge in enumerate(sheet.Shape.Edges, start=1)
        if edge.BoundBox.XMax < 1e-9
    )
    axis_bc = ObjectsFem.makeConstraintDisplacement(doc, "AxisRadialFixed")
    axis_bc.References = [(sheet, axis_edge)]
    axis_bc.xFree = False
    axis_bc.xDisplacement = "0 mm"
    axis_bc.yFree = True
    axis_bc.zFree = True
    fem.addObject(axis_bc)
    loadsteps.attach_condition(step, axis_bc)

    holder_force = ObjectsFem.makeConstraintForce(doc, "BlankHolderForce")
    holder_force.References = [(holder, "Face1")]
    down = feature(doc, "ForceDirection", Part.makeLine(App.Vector(0, 5, 0), App.Vector(0, 0, 0)))
    doc.recompute()
    holder_force.Direction = (down, ["Edge1"])
    blank_radius = sheet.Shape.BoundBox.XMax
    bore_radius = holder.Shape.BoundBox.XMin
    area = math.pi * (blank_radius ** 2 - bore_radius ** 2)  # contact annulus, mm2
    holder_force.Force = f"{PRESSURE_MPA * area} N"
    fem.addObject(holder_force)
    loadsteps.attach_condition(step, holder_force)
    doc.recompute()
    return doc, case


def main():
    App.ParamGet("User parameter:BaseApp/Preferences/Mod/Fem/Gmsh").SetBool("UseStandardGmshLocation", False)
    App.ParamGet("User parameter:BaseApp/Preferences/Mod/Fem/Gmsh").SetString("gmshBinaryPath", GMSH)
    source = App.openDocument(str(SOURCE))
    shapes = faces_by_label(source)
    missing = [n for n in PUNCHES + BLANKS + ["Die", "BlankHolder"] if n not in shapes]
    if missing:
        raise SystemExit(f"Geometrias.FCStd lacks faces: {missing}")
    only = {s for s in os.environ.get("CTFORM_TCC_ONLY", "").split(",") if s}
    summary = []
    for punch_name in PUNCHES:
        for blank_name in BLANKS:
            name = f"{punch_name}_{blank_name}"
            if only and name not in only:
                continue
            doc, case = build(shapes, punch_name, blank_name)
            out = OUT / name
            out.mkdir(parents=True, exist_ok=True)
            case_json = case_export.write_case_json(case, out)
            data = json.loads(case_json.read_text(encoding="utf-8"))
            summary.append((name, data["packageStatus"], data["readinessIssues"]))
            print("TCC", name, data["packageStatus"], json.dumps(data["readinessIssues"]))
            App.closeDocument(doc.Name)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("TCC done:", len(summary), "cases in", OUT)


main()
