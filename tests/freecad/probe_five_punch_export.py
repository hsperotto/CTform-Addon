# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Build a five-punch-style case headless in FreeCAD and export its package.

Run with FreeCADCmd (not unittest; it needs FreeCAD and Gmsh):

    set CTFORM_PROBE_OUT=C:\\temp\\probe
    FreeCADCmd.exe tests\\freecad\\probe_five_punch_export.py

Industrial arrangement: punch above, descending under a displacement; die
below, fixed; blank holder above the flange under a constant downward force.
Axisymmetric: sketch X is the radius, sketch Y the axial coordinate (mm).
The punch nose height and the gaps are PLACEHOLDERS, not the LdTM drawings.
"""

import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import FreeCAD as App
import ObjectsFem
import Part

from freecad.CTformFreeCADInterface import analysis, case_export, components, contacts
from freecad.CTformFreeCADInterface import loadsteps, materials

OUT = Path(os.environ.get("CTFORM_PROBE_OUT", ROOT / "tests" / "freecad" / "out"))
GMSH = os.environ.get("CTFORM_GMSH", r"C:\Program Files\FreeCAD 1.1\bin\gmsh.exe")
CATALOG = ROOT / "freecad" / "CTformFreeCADInterface" / "resources" / "materials" / (
    "aisi304-1mm-nunes2025.json"
)

BLANK_RADIUS = 45.0  # mm, D0 = 90
THICKNESS = 1.0
BORE_RADIUS = 27.0
DIE_ENTRY_RADIUS = 6.0
PUNCH_RADIUS = 25.0
PUNCH_CORNER = 6.0
PUNCH_GAP = float(os.environ.get("CTFORM_PROBE_PUNCH_GAP", "1.0"))  # placeholder, mm
HOLDER_GAP = 0.05
FRICTION = float(os.environ.get("CTFORM_PROBE_MU", "0.2"))
STROKE = 30.0
PRESSURE_MPA = 5.0
PRESS_SPEED = 19.5  # mm/s, Rocha (2022); not stated by Nunes
WITH_HOLDER = os.environ.get("CTFORM_PROBE_NO_HOLDER") != "1"
WITH_AXIS_BC = os.environ.get("CTFORM_PROBE_NO_AXIS") != "1"


def arc(center, radius, start_deg, end_deg):
    circle = Part.Circle(App.Vector(*center, 0), App.Vector(0, 0, 1), radius)
    return Part.ArcOfCircle(circle, math.radians(start_deg), math.radians(end_deg)).toShape()


def polygon_face(points):
    edges = [
        Part.makeLine(App.Vector(*a, 0), App.Vector(*b, 0))
        for a, b in zip(points, points[1:] + points[:1])
    ]
    return Part.Face(Part.Wire(edges))


def feature(doc, name, shape):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    return obj


def make_profile_face(segments):
    return Part.Face(Part.Wire(Part.__sortEdges__(segments)))


def build():
    doc = App.newDocument("FivePunchProbe")
    case = analysis.make_case(doc)
    fem = analysis.analysis_for_case(case)
    solver = analysis.make_solver(doc, case)
    solver.Dimension = "2D"
    solver.ModelingType = "axisymmetric"
    solver.MechanicalFormulation = os.environ.get("CTFORM_PROBE_FORMULATION", "flow")
    analysis.apply_isothermal_preset(solver)
    solver.ExportTargetCompression = False  # the run ends when its load steps end

    top = THICKNESS
    sheet = feature(doc, "Sheet", polygon_face(
        [(0, 0), (BLANK_RADIUS, 0), (BLANK_RADIUS, top), (0, top)]
    ))

    # Die below the sheet: flat top at z=0, entry fillet, bore wall, bottom.
    cx = BORE_RADIUS + DIE_ENTRY_RADIUS
    die = feature(doc, "DieShape", make_profile_face([
        Part.makeLine(App.Vector(60, 0, 0), App.Vector(cx, 0, 0)),
        arc((cx, -DIE_ENTRY_RADIUS), DIE_ENTRY_RADIUS, 90, 180),
        Part.makeLine(App.Vector(BORE_RADIUS, -DIE_ENTRY_RADIUS, 0), App.Vector(BORE_RADIUS, -20, 0)),
        Part.makeLine(App.Vector(BORE_RADIUS, -20, 0), App.Vector(60, -20, 0)),
        Part.makeLine(App.Vector(60, -20, 0), App.Vector(60, 0, 0)),
    ]))

    # Cylindrical punch above the sheet (corner R6); nose height is a placeholder.
    nose = top + PUNCH_GAP
    cxp = PUNCH_RADIUS - PUNCH_CORNER
    punch = feature(doc, "PunchShape", make_profile_face([
        Part.makeLine(App.Vector(0, nose, 0), App.Vector(cxp, nose, 0)),
        arc((cxp, nose + PUNCH_CORNER), PUNCH_CORNER, 270, 360),
        Part.makeLine(App.Vector(PUNCH_RADIUS, nose + PUNCH_CORNER, 0), App.Vector(PUNCH_RADIUS, nose + 40, 0)),
        Part.makeLine(App.Vector(PUNCH_RADIUS, nose + 40, 0), App.Vector(0, nose + 40, 0)),
        Part.makeLine(App.Vector(0, nose + 40, 0), App.Vector(0, nose, 0)),
    ]))

    # Blank holder above the flange.
    holder_bottom = top + HOLDER_GAP
    holder = feature(doc, "HolderShape", polygon_face(
        [(BORE_RADIUS + 1, holder_bottom), (60, holder_bottom), (60, holder_bottom + 20),
         (BORE_RADIUS + 1, holder_bottom + 20)]
    ))
    doc.recompute()

    workpiece = components.make_workpiece(doc, fem, case, sheet)
    tools = {
        "Punch": components.make_tool(doc, fem, case, punch, "Punch"),
        "Die": components.make_tool(doc, fem, case, die, "Die"),
    }
    if WITH_HOLDER:
        tools["BlankHolder"] = components.make_tool(doc, fem, case, holder, "BlankHolder")

    imported = {m.MaterialName: m for m in materials.import_material_catalog(doc, fem, case, CATALOG)}
    material_name = os.environ.get("CTFORM_PROBE_MATERIAL", "AISI 304 1 mm, mean of 0/45/90 deg (Nunes 2025)")
    workpiece.Material = imported[material_name]
    workpiece.StructuredSheetMesh = os.environ.get("CTFORM_PROBE_STRUCTURED") == "1"  # transfinite Quad4 sheet
    for tool in tools.values():
        tool.Material = imported["Rigid Tool Steel (placeholder)"]

    mesh = ObjectsFem.makeMeshGmsh(doc, "SheetMesh")
    mesh.Shape = sheet
    mesh.ElementDimension = "2D"
    mesh.ElementOrder = "1st"
    mesh.RecombineAll = os.environ.get("CTFORM_PROBE_QUAD") == "1"  # structured Quad4 for displacement runs
    if os.environ.get("CTFORM_PROBE_ALGO2D"):
        mesh.Algorithm2D = os.environ["CTFORM_PROBE_ALGO2D"]
    mesh.CharacteristicLengthMax = "0.25 mm"
    mesh.CharacteristicLengthMin = "0.1 mm"
    workpiece.Mesh = mesh
    workpiece.addObject(mesh)
    doc.recompute()

    for tool in tools.values():
        pair = contacts.make_contact_pair(doc, workpiece, tool)
        pair.FrictionModel = "coulomb" if FRICTION > 0 else "none"
        pair.FrictionCoefficient = FRICTION

    total = float(os.environ.get("CTFORM_PROBE_TOTAL_TRAVEL", PUNCH_GAP + STROKE))  # mm
    duration = total / PRESS_SPEED
    step = loadsteps.make_load_step(doc, fem)
    step.StepName = "Press"
    step.StartTime = 0.0
    step.EndTime = duration
    step.Increments = int(os.environ.get("CTFORM_PROBE_INCREMENTS", "100"))

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

    if WITH_AXIS_BC:
        # Core's flow formulation does not constrain the r = 0 axis by itself:
        # fix the radial displacement (only X) on the sheet's axis edge.
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
    if not WITH_HOLDER:
        doc.recompute()
        return doc, case
    holder_force = ObjectsFem.makeConstraintForce(doc, "BlankHolderForce")
    holder_force.References = [(holder, "Face1")]
    down = feature(doc, "ForceDirection", Part.makeLine(App.Vector(0, 5, 0), App.Vector(0, 0, 0)))
    doc.recompute()
    holder_force.Direction = (down, ["Edge1"])
    area = math.pi * ((2 * BLANK_RADIUS) ** 2 - (2 * BORE_RADIUS) ** 2) / 4
    holder_force.Force = f"{PRESSURE_MPA * area} N"
    fem.addObject(holder_force)
    loadsteps.attach_condition(step, holder_force)
    doc.recompute()
    return doc, case


def main():
    App.ParamGet("User parameter:BaseApp/Preferences/Mod/Fem/Gmsh").SetBool("UseStandardGmshLocation", False)
    App.ParamGet("User parameter:BaseApp/Preferences/Mod/Fem/Gmsh").SetString("gmshBinaryPath", GMSH)
    doc, case = build()
    OUT.mkdir(parents=True, exist_ok=True)
    case_json = case_export.write_case_json(case, OUT)
    data = json.loads(case_json.read_text(encoding="utf-8"))
    print("PROBE package:", case_json)
    print("PROBE status:", data["packageStatus"], "issues:", json.dumps(data["readinessIssues"], indent=1))
    print("PROBE run:", json.dumps(data["run"]))
    print("PROBE tools:", [(t["id"], t.get("role", "-")) for t in data["geometry"]["tools"]])
    print("PROBE contacts:", [(c["id"], c["master"]["name"], c["masterBody"]) for c in data["contactInterfaces"]])
    steps = json.loads((OUT / data["loadStepsFile"]).read_text(encoding="utf-8"))
    for record in steps["loadSteps"][0]["tools"]:
        print("PROBE step tool:", json.dumps(record))
    print("PROBE step BCs:", json.dumps(steps["loadSteps"][0]["mechanicalBCs"]))
    print("PROBE warnings:", steps["warnings"])
    thermal = json.loads((OUT / data["thermalFile"]).read_text(encoding="utf-8"))
    print("PROBE thermal:", json.dumps({k: v for k, v in thermal.items() if k != "thermalBCs"}), thermal["thermalBCs"])
    print("PROBE mesh:", json.dumps({k: v for k, v in data["mesh"].items() if k != "physicalGroups"}))


main()
