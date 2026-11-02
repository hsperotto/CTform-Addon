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
    CTFORM_TCC_STROKE     one punch travel for all cases, mm (default: STROKE_MM table)
    CTFORM_TCC_INCREMENT_MM  punch travel per increment, mm (default 0.3)
    CTFORM_TCC_PUNCH_GAP  initial punch-to-blank gap, mm (default 0 = as drawn)
    CTFORM_TCC_HOLDER_GAP initial holder-to-blank gap, mm (default 0 = as drawn)
    CTFORM_TCC_MU         Coulomb friction (0 exports friction none; default 0.2)
    CTFORM_TCC_FORMULATION  REQUIRED: flow or displacement (no default; the run aborts if unset)
    CTFORM_TCC_TOOL_MESH  tool-profile element size, mm (default 0.5)
    CTFORM_TCC_REMESH=1   export the remesh block (Core v2 on agent/v2-rigid-tool-segments); CTFORM_TCC_REMESH_*
                          set interval, min increments, max steps and h (mm); see REMESH_SETTINGS
    CTFORM_TCC_MRATE / CTFORM_TCC_REF_RATE  Hollomon rate exponent m and reference strain rate (1/s) of the sheet
    CTFORM_TCC_MESH_SCALE   multiplies the 0.25 mm sheet element size
    CTFORM_TCC_MATERIAL     REQUIRED: catalog material name of the sheet (no default; the run aborts if unset)
    CTFORM_TCC_HOLDER_PRESSURE  blank holder pressure, MPa (default 5; force = p x annulus area)
    CTFORM_TCC_HOLDER_FORCE_N   blank holder force in N, used as given (wins over HOLDER_PRESSURE); needs
                                CTFORM_TCC_HOLDER_FORCE_SOURCE (text recorded in manifest.csv)
    CTFORM_TCC_RIM_SIZE     element size at the sheet rim, mm (radial grading from MESH_SIZE at the axis; 0 = uniform)
    CTFORM_TCC_MESH_SIZE    sheet element size in mm (named parameter; wins over MESH_SCALE)
Every run also writes manifest.csv (case, mu, mesh size, formulation, remesh, stroke, ...).
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


def _fail(message):
    # FreeCADCmd does not show the message of an exception raised at import time: print it first.
    print("TCC ERROR:", message, file=sys.stderr, flush=True)
    print("TCC ERROR:", message, flush=True)
    raise RuntimeError(message)


def _required(name, allowed=None):
    """Read a choice the user must make knowingly: there is no default."""
    value = os.environ.get(name, "").strip()
    if not value:
        _fail(f"{name} is required (no default). Set it explicitly before running.")
    if allowed and value not in allowed:
        _fail(f"{name}={value!r} is not valid; choose one of {sorted(allowed)}.")
    return value


FORMULATION = _required("CTFORM_TCC_FORMULATION", {"flow", "displacement"})
MATERIAL = _required("CTFORM_TCC_MATERIAL")

PUNCHES = ["Cilinder", "Hemisphere", "FlatElipse", "DeepElipse", "VeryDeepElipse"]
BLANKS = ["Blank90", "Blank100", "Blank110"]

# Punch travel from first contact, mm (Thay: Nunes 2025 Figs. 24/26/28, +-1 mm, rounded up to
# multiples of 5; source CTform-Thesis tools/casematrix.py STROKE_MM). VeryDeepElipse D90 is
# not an experiment in the thesis: it repeats the 100 mm value per Thay's table.
STROKE_MM = {
    "Cilinder": {"Blank90": 30, "Blank100": 40, "Blank110": 30},
    "FlatElipse": {"Blank90": 35, "Blank100": 40, "Blank110": 35},
    "Hemisphere": {"Blank90": 45, "Blank100": 50, "Blank110": 70},
    "DeepElipse": {"Blank90": 50, "Blank100": 60, "Blank110": 45},
    "VeryDeepElipse": {"Blank90": 55, "Blank100": 45, "Blank110": 45},
}
STROKE_OVERRIDE = os.environ.get("CTFORM_TCC_STROKE")  # one stroke for every case, mm
# Increments are NOT defined in the thesis: this is an addon choice (~0.3 mm of punch travel
# each, the ratio of the earlier 100 increments for 30 mm), to be confirmed by the author.
INCREMENT_MM = float(os.environ.get("CTFORM_TCC_INCREMENT_MM", "0.3"))
HOLDER_FORCE_BORE_RADIUS = 27.0  # mm; thesis hypothesis F = p*pi*(D0^2 - 54^2)/4 (Nunes die opening)
PUNCH_GAP = float(os.environ.get("CTFORM_TCC_PUNCH_GAP", "0"))
HOLDER_GAP = float(os.environ.get("CTFORM_TCC_HOLDER_GAP", "0"))
FRICTION = float(os.environ.get("CTFORM_TCC_MU", "0.2"))
PRESS_SPEED = 19.5  # mm/s, Rocha (2022); placeholder
PRESSURE_MPA = float(os.environ.get("CTFORM_TCC_HOLDER_PRESSURE", "5.0"))  # blank holder pressure, MPa; 5 MPa is the thesis value
HOLDER_FORCE_N = os.environ.get("CTFORM_TCC_HOLDER_FORCE_N")
HOLDER_FORCE_SOURCE = os.environ.get("CTFORM_TCC_HOLDER_FORCE_SOURCE", "").strip()
if HOLDER_FORCE_N:
    HOLDER_FORCE_N = float(HOLDER_FORCE_N)
    if not HOLDER_FORCE_SOURCE:
        print("TCC ERROR: CTFORM_TCC_HOLDER_FORCE_N needs CTFORM_TCC_HOLDER_FORCE_SOURCE (where the force comes from)", flush=True)
        raise RuntimeError("CTFORM_TCC_HOLDER_FORCE_N needs CTFORM_TCC_HOLDER_FORCE_SOURCE")
else:
    HOLDER_FORCE_N = None
    HOLDER_FORCE_SOURCE = HOLDER_FORCE_SOURCE or "pressure x annulus area pi(D0^2-54^2)/4 (hypothesis)"
TOOL_MESH_SIZE = float(os.environ.get("CTFORM_TCC_TOOL_MESH", "0.5"))  # mm; resolves the 5 mm radii
REMESH = os.environ.get("CTFORM_TCC_REMESH") == "1"
# Remesh settings; sizes in mm (exported in metres). Switches: CTFORM_TCC_REMESH_{INTERVAL,MIN_INC,MAX_STEPS,H_BASE,H_MIN,H_MAX}
REMESH_SETTINGS = {
    "RemeshInterval": int(os.environ.get("CTFORM_TCC_REMESH_INTERVAL", "10")),
    "RemeshMinIncrements": int(os.environ.get("CTFORM_TCC_REMESH_MIN_INC", "10")),
    "RemeshMaxSteps": int(os.environ.get("CTFORM_TCC_REMESH_MAX_STEPS", "40")),
    "RemeshHBase": float(os.environ.get("CTFORM_TCC_REMESH_H_BASE", "0.25")),
    "RemeshHMin": float(os.environ.get("CTFORM_TCC_REMESH_H_MIN", "0.25")),
    "RemeshHMax": float(os.environ.get("CTFORM_TCC_REMESH_H_MAX", "0.25")),
    "RemeshQualityMinScoreRetention": float(os.environ.get("CTFORM_TCC_REMESH_QUALITY_RETENTION", "0.5")),
}
# Optional strain-rate sensitivity of the sheet (round 3 proposal; not the thesis default). Unset = rate independent.
M_RATE = os.environ.get("CTFORM_TCC_MRATE")
REFERENCE_STRAIN_RATE = os.environ.get("CTFORM_TCC_REF_RATE")  # 1/s
MESH_SCALE = float(os.environ.get("CTFORM_TCC_MESH_SCALE", "1"))
# Named sheet element size in mm (overrides the 0.25 mm x MESH_SCALE default when set).
RIM_SIZE = float(os.environ.get("CTFORM_TCC_RIM_SIZE", "0"))  # mm; 0 = uniform grid
MESH_SIZE = float(os.environ.get("CTFORM_TCC_MESH_SIZE", 0.25 * MESH_SCALE))


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
    solver.MechanicalFormulation = FORMULATION
    analysis.apply_isothermal_preset(solver)
    solver.ExportTargetCompression = False
    if REMESH:
        solver.RemeshEnabled = True
        solver.RemeshEngine = "gmsh"
        for name, value in REMESH_SETTINGS.items():
            setattr(solver, name, value)

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
    if M_RATE is not None:
        workpiece.Material.HollomonRateExponent = float(M_RATE)
    if REFERENCE_STRAIN_RATE is not None:
        workpiece.Material.HollomonReferenceStrainRate = float(REFERENCE_STRAIN_RATE)
    for tool in tools.values():
        tool.Material = imported["Rigid Tool Steel (placeholder)"]
        tool.ToolMeshSize = TOOL_MESH_SIZE

    mesh = ObjectsFem.makeMeshGmsh(doc, "SheetMesh")
    mesh.Shape = sheet
    mesh.ElementDimension = "2D"
    mesh.ElementOrder = "1st"
    mesh.CharacteristicLengthMax = f"{MESH_SIZE} mm"
    mesh.CharacteristicLengthMin = f"{0.4 * MESH_SIZE} mm"
    workpiece.Mesh = mesh
    workpiece.addObject(mesh)
    # Transfinite recombined Quad4 grid (4 elements through the 1 mm thickness).
    workpiece.StructuredSheetMesh = True
    workpiece.StructuredElementSize = f"{MESH_SIZE} mm"
    if RIM_SIZE:
        workpiece.StructuredRimSize = f"{RIM_SIZE} mm"
    doc.recompute()

    for tool in tools.values():
        pair = contacts.make_contact_pair(doc, workpiece, tool)
        pair.FrictionModel = "coulomb" if FRICTION > 0 else "none"
        pair.FrictionCoefficient = FRICTION

    stroke = float(STROKE_OVERRIDE) if STROKE_OVERRIDE else float(STROKE_MM[punch_name][blank_name])
    total = PUNCH_GAP + stroke
    step = loadsteps.make_load_step(doc, fem)
    step.StepName = "Press"
    step.StartTime = 0.0
    step.EndTime = total / PRESS_SPEED
    step.Increments = max(1, math.ceil(total / INCREMENT_MM))

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
    area = math.pi * (blank_radius ** 2 - HOLDER_FORCE_BORE_RADIUS ** 2)  # mm2, thesis formula
    holder_force.Force = f"{HOLDER_FORCE_N if HOLDER_FORCE_N is not None else PRESSURE_MPA * area} N"
    fem.addObject(holder_force)
    loadsteps.attach_condition(step, holder_force)
    doc.recompute()
    return doc, case


def _commit():
    try:
        import subprocess
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return ""


COMMIT = _commit()


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
    manifest = []
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
            stroke = float(STROKE_OVERRIDE) if STROKE_OVERRIDE else float(STROKE_MM[punch_name][blank_name])
            manifest.append({
                "case": name, "status": data["packageStatus"], "mu": FRICTION, "mesh_size_mm": MESH_SIZE, "rim_size_mm": RIM_SIZE or "",
                "elements": data["mesh"]["elementCount"], "element_types": "|".join(data["mesh"]["elementTypes"]),
                "formulation": data["simulation"]["mechanicalFormulation"], "material": MATERIAL, "remesh": data["remesh"].get("enabled"),
                "stroke_mm": stroke, "increment_mm": INCREMENT_MM, "press_speed_mm_s": PRESS_SPEED,
                "holder_pressure_MPa": "" if HOLDER_FORCE_N is not None else PRESSURE_MPA, "holder_force_N": HOLDER_FORCE_N if HOLDER_FORCE_N is not None else "", "holder_force_source": HOLDER_FORCE_SOURCE, "punch_gap_mm": PUNCH_GAP, "addon_commit": COMMIT,
            })
            print("TCC", name, data["packageStatus"], json.dumps(data["readinessIssues"]))
            App.closeDocument(doc.Name)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    if manifest:
        import csv
        with open(OUT / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(manifest[0]))
            writer.writeheader()
            writer.writerows(manifest)
    print("TCC done:", len(summary), "cases in", OUT)


main()
