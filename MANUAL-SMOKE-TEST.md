# CTform FreeCAD Manual Smoke Test (full GUI run)

One sitting, top to bottom, in the FreeCAD GUI. It builds the thesis case
**Cilinder_Blank100** by hand (cylindrical punch, 100 mm blank), exports it, runs the
Core, opens the results, saves and reopens the document, and then tries the things that
should be refused. Every step says what to do, what must happen (**Pass**), and what
usually goes wrong (**Watch**). Where a screenshot is needed for the thesis it says
**SHOT Sxx**; the full list is in the last section.

Record every failure with the step number, what you saw and any red text from the
Report view. A step that fails does not stop the run unless it says **STOP**.

## 0. Before you start

### 0.1 Test record (fill in)

- Date / tester:
- FreeCAD version (Help > About):
- Add-on commit (`git -C <addon> rev-parse --short HEAD`; the branch must be `main`):
- Gmsh version (FreeCAD `bin\gmsh.exe --version`):
- Core executable and Core commit:
- Result: Pass / Fail / Blocked
- Screenshot folder: `C:\Users\henri\Desktop\TCC\Receba\capturas\` (outside any repository)

### 0.2 Preparation

1. Close FreeCAD completely and start it again, so it loads the current add-on code
   (icons, commands). Then open **View > Panels** and switch on **Report view** and
   **Python console**. Keep both visible all the time. Red lines in the Report view are
   failures even if no dialog appears.
   - Watch: a Python import error at startup means the workbench list has no CTform.
2. Create two empty folders: `C:\ctf-smoke\run1` (export target) and
   `C:\ctf-smoke\run1-reopen` (export after reopen). Create `...\capturas` if missing.
3. Have the Core executable path ready (`ctform3_cli.exe`) and note whether the
   `CTFORM_CORE` environment variable is set. Find a known good case for the Core
   (for example `C:\Users\henri\Desktop\TCC\Receba\runs\validation-H\Blank100\Cilinder_Blank100`)
   in case the new package needs a comparison.
4. Quick environment check, in the Python console:
   ```python
   import FreeCAD; print(FreeCAD.Version())
   import Fem, femmesh; print("FEM ok")
   from freecad.CTformFreeCADInterface import commands; print("CTform ok")
   ```
   - Pass: all three lines print. Watch: `No module named ...` means the add-on is not on the
     module path; stop here.
5. Check Gmsh is configured: Edit > Preferences > FEM > Gmsh. Either "Use standard Gmsh
   location" or the full path to FreeCAD's `bin\gmsh.exe`.
   - Watch: an empty or wrong path makes the mesh step fail later with a vague message.

### 0.3 Workbench

1. Pick the **CTform** workbench from the workbench selector.
   - Pass: menu **CTform** with Create CTform Case, Create Workpiece, Create Tool, Create
     Load Step, Clone Load Step, Create CTform Solver, Export CTform Case, Run CTform Core,
     CTform Results; submenus **Materials**, **Geometry & Mesh**, **Contact & Conditions**.
   - Pass: toolbars CTform, CTform Geometry & Mesh, CTform Materials, CTform Contact &
     Conditions. Icons are visible (no blank squares).
   - Watch: a missing command shows as an empty menu or a console error at workbench start.
   - **SHOT S01** the empty workbench with the menus open (CTform menu expanded).

## 1. Case and solver

1. File > New. Run **Create CTform Case**.
   - Pass: a `CTform Case` analysis appears in the tree and a CTform case child.
   - Watch: running it twice must be refused (one case per document): run it again now.
     - Pass: error message, no second analysis.
2. Run **Create CTform Solver**. Select the Solver and set, in the property panel:
   - `Dimension` = `2D`, `ModelingType` = `axisymmetric`, `MechanicalFormulation` = `displacement`
   - `ContactPenalty` = `1e15` (Pa/m; equals 1e6 N/mm3), `InitialGap` as is
   - `CoreExecutable` = path to `ctform3_cli.exe` (or leave empty if `CTFORM_CORE` is set)
   - `CoreTimeoutMinutes` = `30` (so a hung Core cannot block you)
   - `OutputDirectory` = `results_case`
   - Pass: the properties are on the Solver, not on the Case.
   - Watch: `MechanicalFormulation` has no neutral default in the generator (it is chosen
     on purpose); `displacement` needs a pure Quad4 sheet mesh, checked at export (step 9).
   - Watch: `ThermalPlasticEfficiency` defaults to 0.9. The thesis runs are isothermal. The
     isothermal preset is a function (`analysis.apply_isothermal_preset`), not a menu command.
     In the Python console run:
     ```python
     import FreeCAD as App
     from freecad.CTformFreeCADInterface import analysis
     solver = [o for o in App.ActiveDocument.Objects if o.Name.startswith("CTformSolver")][0]
     analysis.apply_isothermal_preset(solver)
     print(solver.ThermalPlasticEfficiency, solver.InitialWorkpieceTemperature)
     ```
     Pass: `0.0 293.15`. (If the Solver object has another name, list the objects in the
     console. Record that the preset has no GUI command.)
   - **SHOT S02** the Solver property panel (all groups expanded: Model, Contact, Run, Output,
     External Tools).

## 2. Geometry

Use the supplied drawing so the case matches the thesis.

1. File > Open `tcc\Geometrias.FCStd` in the add-on folder (a second document). Look in the
   tree: faces labelled `Cilinder`, `Die`, `BlankHolder`, `Blank90`, `Blank100`, `Blank110`,
   and the other four punches. Sketch X is the radius, sketch Y the axial coordinate, mm.
   - Pass: the faces are visible and are planar (Part::Face).
   - Watch: this is the only place where geometry comes from; do not edit it.
2. Copy the four faces you need (`Cilinder`, `Die`, `BlankHolder`, `Blank100`) into the new
   document (select, Ctrl+C, switch to the new document, Ctrl+V; or Edit > Paste). If paste
   gives non-parametric copies, that is fine.
   - Watch: after pasting, check the faces did not move: punch nose and blank top at y = 0,
     holder at y = 0, die top at y = -1. Use the sketch/edge positions in the property panel.
3. **SHOT S03** the 3D view of the four faces (axis X horizontal, Y vertical; fit to view).

## 3. Components and materials

1. Select the `Blank100` face, run **Create Workpiece**.
   - Pass: one Workpiece folder, linked to the shape.
2. One at a time select `Cilinder` -> **Create Tool** and name it `Punch`; `Die` -> `Die`;
   `BlankHolder` -> `BlankHolder`.
   - Pass: three tools with different names. Select each and check `ToolId` is non-empty.
   - Set `ToolMeshSize` = `0.5` on each tool (group Export; mm, the generator value; 0 leaves
     the Core default and the tool profiles are discretised differently).
   - Watch: two tools with the same name, or a name with spaces/accents, must either be
     refused or produce unique IDs: try creating a fourth tool named `Punch` and check.
3. Select the Workpiece, run **Assign CTform Material**, choose **Import materials.json...**
   and pick
   `freecad\CTformFreeCADInterface\resources\materials\aisi304-1mm-nunes2025.json`.
   Choose **AISI 304 1 mm, mean, tabulated Fig22 (Nunes 2025)** for the Workpiece.
   Then assign **Rigid Tool Steel (placeholder)** to each of the three tools.
   - Pass: one **CTform Materials** folder; the four components link to their materials.
   - Watch: importing the same catalog twice must not duplicate materials (do it again, count).
   - Watch: the other eight Nunes entries (Hollomon, Swift, directional) must be listed too;
     the Workpiece material shows `Hardening`/table properties in the panel.
   - **SHOT S04** the model tree after this step (everything expanded), and **SHOT S05** the
     material object of the Workpiece with its properties.
4. Select the Workpiece material and open **Create CTform Material** only to check it
   opens without error (manual fallback), then cancel/delete it.
   - Pass: a new material appears and is deleted without touching the others. Delete it.

## 4. Mesh

1. Select the Blank100 face inside the Workpiece folder, run native **FEM_MeshGmshFromShape**.
   Set `ElementOrder` = `1st`, `ElementDimension` = `2D`, Max size `0.25 mm`, Min size `0.1 mm`.
   Do not run it yet.
2. Select the Workpiece folder and set (property panel, group Mesh):
   `StructuredSheetMesh` = true, `StructuredElementSize` = `0.25 mm`, `StructuredRimSize` = `0 mm`.
3. Generate the mesh.
   - Pass: 800 elements (all Quad4), 4 through the 1 mm thickness. Check **FEM_MeshDisplayInfo**
     in the toolbar: node and element counts.
   - Watch: an element count different from 800 means the edge lengths are not whole
     multiples of the size; the export warns about it (step 9).
   - Watch: Gmsh errors in the Report view.
4. Select the Workpiece folder and the mesh together, run **Assign FEM Mesh to CTform Component**.
   - Pass: the Workpiece `Mesh` link points to the mesh and it is shown under the folder.
   - Watch: it is disabled if the mesh was made for another shape. Try the command with the
     mesh and a Tool folder selected and confirm it refuses.
   - **SHOT S06** the mesh in the 3D view, zoomed to the sheet edge (rim) with the 4 layers visible.
   - **SHOT S07** the full 3D view with the mesh and the three tools.

## 5. Contact

1. Select the Workpiece folder and each Tool in turn with **Create CTform Contact Pair**.
   - Pass: three pairs (Punch, Die, BlankHolder) below the Workpiece, each linking Workpiece + Tool.
2. For each pair set `FrictionModel` = `coulomb`, `FrictionCoefficient` = `0.20`,
   `SlavePhysicalGroup` = `All`. Set distinct `PairName`s.
   - Watch: `FrictionModel` = `none` should hide/ignore the coefficient at export.
   - Watch: the per-pair `Penalty` property is NOT read by the Core (it reads only the
     Solver `ContactPenalty`). Leave it 0 and note that.
   - **SHOT S08** one contact pair property panel (groups Contact, Normal, Friction).

## 6. Load step and conditions

1. Run **Create Load Step**. Set `StepName` = `Press`, `StartTime` = `0`,
   `EndTime` = `2.0513` (40 mm / 19.5 mm/s), `Increments` = `134` (40 / 0.3 mm), `Active` true.
   - Watch: the property editor shows `EndTime` before `StartTime` (known UI quirk).
2. Create a native FEM **Displacement** condition (do not preselect geometry): click **Add**,
   select the punch face in the 3D view, confirm. Set `xFree` true, `yFree` false,
   `yDisplacement` = `-40 mm`, `zFree` true. Select the condition and the step together and
   run **Attach Selected Condition to Load Step**.
   - Pass: the condition is a child of the step.
3. Create a native FEM **Fixed** condition on the Die face; drag it onto the step.
   - Pass: it becomes a child of the step and is no longer under the analysis root.
4. Create a **Displacement** condition on the **left edge of the blank** (the r = 0 axis edge):
   `xFree` false, `xDisplacement` = `0 mm`, `yFree` true, `zFree` true. Attach it to the step.
   - Watch: it must be the edge at X = 0 (axis). Selecting the wrong edge makes the sheet
     slide; the export exposes that as the axis symmetry BC. Verify in step 9.
5. Create a native FEM **Force** condition on the BlankHolder face. Direction: a line along
   axial Y pointing down (create a line from (0,5,0) to (0,0,0) in a new Part feature, or a
   sketch line, and use it as Direction). `Force` = `50301.45 N`
   (p x pi x (62.7^2 - 27^2) mm2 with p = 5 MPa and calibrated R_ext = 62.7 mm). Attach it to the step.
   - Watch: the direction sign decides whether the holder pushes down or up; check the
     arrow in the 3D view points toward the blank.
   - **SHOT S09** the step with its four children in the tree plus the Force direction arrow
     in the 3D view.
6. Add an extra step "Hold" (time 2.0513-3), then select **Press** and run **Clone Load Step**.
   - Pass: the clone has a new unique `StepId`, copies of the conditions that still reference
     the same geometry, is registered in the case. Edit the Force of the clone and check the
     source step did not change.
   - Delete the clone and the Hold step again before exporting (the thesis case has one step).
7. Create a native FEM **Temperature** condition on the whole blank face, attach it to
   the step, then select it and the step and run **Detach Condition from Load Step**.
   - Pass: it returns to the analysis root and is exported as a global condition.
   - Remove it afterwards (the case is isothermal).

## 7. Export

1. Run **Export CTform Case**, choose `C:\ctf-smoke\run1\case.json`.
   - Pass: no error dialog. If a **Draft** warning appears, copy every line into the record:
     each line is a real readiness problem. For this case the package must be `ready`
     (no dialog).
   - **SHOT S10** the export dialog and the result (or the warning dialog, if any).
2. Open the folder and check files: `case.json`, `materials.json`, `loadsteps.json`,
   `thermal.json`, `workpiece.msh`, `geometry\workpiece.dxf`, `geometry\tools\*.dxf` (3 tools).
   - Pass: all exist; `case.json` has `schemaVersion: 2`, `packageStatus: ready`,
     `readinessIssues: []`, `simulation.mechanicalFormulation: displacement`,
     `simulation.penalty: 1e15`, mesh `elementCount: 800`, `elementTypes: ["Quad4"]`.
   - Pass: `loadsteps.json` has one step, `Increments` 134, the punch displacement `-0.04` m,
     the die fixed, the axis BC, and the BlankHolder force `50301.45` N.
   - Pass: `materials.json` has the tabulated material once with 42 table points, and the
     rigid tool material once.
   - Pass: `thermal.json` has the isothermal values (plastic efficiency 0, 293.15 K).
   - **SHOT S11** the exported package folder in the file explorer.
3. Compare with the reference package:
   `C:\Users\henri\Desktop\TCC\Receba\runs\validation-H\Blank100\Cilinder_Blank100`
   (same case made by the generator). In a terminal (outside FreeCAD):
   ```
   fc /b <reference>\workpiece.msh C:\ctf-smoke\run1\workpiece.msh
   ```
   and a JSON diff of `case.json`, `loadsteps.json`, `materials.json`, `thermal.json`.
   - Pass: identical, or the only differences are in `packageDescription`/names/paths and
     floating-point noise. Record every other difference: it is a bug in either the GUI
     route or the generator.
   - Watch: the mesh must be the structured one (800 Quad4); a Tri3 mesh means
     `StructuredSheetMesh` did not take effect.
4. Export a **second time** into the same folder.
   - Pass: files overwritten, no stale files, same hash for `workpiece.msh`
     (stable physical-group IDs).
5. Press Ctrl+Z / look at the Undo list: export must not leave the document modified.

## 8. Run Core from FreeCAD

Skip only if no Core is available (then mark **Blocked** and still do steps 8.4 and 8.6).

1. With the document containing the case active, run **Run CTform Core**.
   - Pass: the message "CTform: running Core on ..." appears in the Report view; FreeCAD
     stays responsive (rotate the 3D view while it runs).
   - Watch: there is no progress bar and no cancel button. Time the run (start/finish) and
     record it: **Run time:**
2. While it runs, run **Run CTform Core** again.
   - Pass: "A Core run is already in progress" warning, no second process (check Task Manager).
3. When it finishes, read the summary dialog: converged yes/no, number of step files, log path.
   - Pass: `results_case` exists next to `case.json` with `case_step_*.vtk`, a log and
     `press_force_by_tool.csv` that has columns `Force_Friction` and `Force_Total`.
   - Watch: a hung Core is stopped only after `CoreTimeoutMinutes`.
   - **SHOT S12** the summary dialog, and **SHOT S13** the Report view after the run.
4. Failure paths (do each once, then restore):
   a. `CoreExecutable` = a path that does not exist: warning, no crash.
   b. `CoreExecutable` = empty and `CTFORM_CORE` unset: message to set it.
   c. Package folder renamed while the run starts: error dialog, no traceback.
   d. Draft package (remove the Workpiece mesh link, export, run): export marks it draft and
      the run must not be started silently. Record what happens.
   e. `CoreTimeoutMinutes` = `0.05` on a long case: the process is stopped, the dialog says
      so, partial steps are listed. Check there is no leftover `ctform3_cli` / gmsh process in
      Task Manager.
5. After a normal run the tree contains a **CTform Result** (`CTformResult`) post pipeline
   under the analysis.
   - Pass: it exists, its time list has as many frames as step files.
   - Watch: this is the unverified part. If the 3D view shows nothing, check the view is
     the XZ plane (Core writes r as X and the axial coordinate as Z, while the model uses Y).
     If the pipeline is empty, copy the error from the Report view.
   - **SHOT S14** the 3D view with the deformed sheet, a field selected (Plastic strain).
6. The Results panel:
   a. Run **CTform Results**; choose the `results_case` folder.
      - Pass: a dock opens with a force-vs-stroke plot, the step slider, the field list.
      - Watch: it needs matplotlib. If it is missing the message must be clear and FreeCAD
        must keep working.
   b. Click a point on the force plot: the step slider follows.
   c. Move the slider: the 3D view changes frame; the label shows time and stroke.
   d. Change the field (Plastic_Strain, VonMises_Stress, ContactPressure, Displacement):
      the maximum and its (r, z) location update; the colour range spinners work; the warp
      factor deforms the view.
   e. Probe at a point inside the sheet and one outside: the outside one reports no value.
   f. Line profile between two points across the thickness; write the summary CSV.
      - Pass: the CSV opens with `Step, Time_s, Stroke_mm, Force_Punch, Max_...` columns.
   g. Compare the force plot's last value with `press_force_by_tool.csv` (Punch, `Force_Total`).
   h. Dock the panel, float it, close it, and open it again: no stale objects.
   i. Open the panel on a folder with no `case_step_*.vtk`: a clear "No case_step" message.
   - Watch: the `Pressure` sign was never confirmed on a long run. Record the sign you see
     for ContactPressure (compression positive or negative).
   - **SHOT S15** the Results panel (force plot + slider + field list), **SHOT S16** the same
     panel with a probe/line plot.

## 9. Save, close, reopen

1. Save the document as `C:\ctf-smoke\smoke.FCStd`. Close FreeCAD completely and start it again.
2. Open the file. Check the Report view for errors at load (proxy errors, "cannot restore").
3. Check: tree intact, the mesh still there, the material links, contacts, step children,
   the pipeline `CTformResult` still shows data (or is cleanly empty).
4. Export again to `C:\ctf-smoke\run1-reopen\case.json`.
   - Pass: the package is byte-for-byte equal to run1 (`fc /b` on `case.json`, `loadsteps.json`,
     `materials.json`, `workpiece.msh`).
   - Watch: tool IDs, material IDs and pair IDs must not change after reopening.
5. Recompute the document (Ctrl+R) and export again: still identical.

## 10. Guardrails (things that must be refused)

Do these in a scratch copy (File > Save As `smoke-guards.FCStd`).

1. Only a load step selected: **Attach Selected Condition to Load Step** disabled.
2. Condition from another document and a step selected: disabled or refused.
3. Condition already in the step + that step: **Detach** enabled; **Attach** idempotent.
4. FEM Force on the workpiece attached to a step: refused (not supported by Core).
5. Root-global Fixed on a boundary plus a step-local Displacement on the same group/axis:
   export gives `overridesGlobal: true` and a warning naming both conditions and the step.
6. A condition on an edge that is not in the assigned mesh: export reports "no matching Gmsh
   physical group" instead of broadening the target.
7. Workpiece without material, tool without material, tool without mesh size: the export is
   `draft` with a precise issue; read each message.
8. Two load steps with the same `StepId` (set it by hand): export rejected.
9. `MechanicalFormulation` = `displacement` and a Tri3 mesh (turn off `StructuredSheetMesh`
   and use the default Gmsh algorithm): the export says it needs a pure Quad4 mesh.
10. `StructuredElementSize` = `0.3 mm` (not a whole divisor of the edges): the export warns
    or refuses; record exactly what it says.
11. Material with `n` outside 0 < n < 1, or a tabulated material with decreasing stress or a
    first point whose plastic strain is not 0: material readiness issue.
12. Delete the Workpiece mesh object after assigning it: export must say the mesh is missing,
    not crash.
13. Delete a Tool folder that has a contact pair: the pair is dropped or flagged; no crash.
14. Two documents open, each with its own case: Run Core and Export act on the active
    document only; results go to the document that started the run.
15. Confirm the custom **Add Mechanical Boundary Condition** and **Add Tool Motion** commands
    are absent; pressure and FEM contact/tie conditions are not offered.
16. Undo/redo (Ctrl+Z / Ctrl+Y) after each of: assign material, assign mesh, create pair,
    attach condition, clone step. No broken links; export identical after undo+redo.
17. Units: set `StructuredElementSize` to `0.25 mm` then to `0.025 cm`: the same export.
18. Non-ASCII or long path for the export folder (a folder with a space and an accent):
    the export either works or says so clearly.
19. Export while the Core is running: no crash; the output of the running Core is unaffected.

## 11. Known unverified items (read the answers off this run)

- Whole GUI flow from an empty document to a ready package (this document).
- Run time of the complete flow: record it. **Total time:**
- Core from FreeCAD: no progress and no cancel exist; the timeout is the only stop.
- 3D result pipeline, the Results panel and the `Pressure` sign (steps 8.5-8.6).
- The isothermal preset has no menu command (step 1.2).
- The per-pair `Penalty` is not read by Core.
- Remesh settings (Solver group Remesh) were not exercised here.

## Screenshots for the thesis (save as `Sxx_<name>.png` in the capture folder)

Use FreeCAD's window as it is (about 1600 px wide), light theme, tree expanded, no stray
dialogs. Use the same file name as below so the thesis session can find them.

| ID | Where | What it shows | Used for |
|---|---|---|---|
| S01 | 0.3 | Empty workbench, CTform menu open | workbench overview |
| S02 | 1.2 | Solver property panel | simulation settings |
| S03 | 2.3 | Geometry faces of the five-punch case | geometry |
| S04 | 3.3 | Model tree, everything expanded | model tree |
| S05 | 3.3 | Workpiece material properties | material |
| S06 | 4.4 | Mesh zoomed at the sheet edge | mesh |
| S07 | 4.4 | Full 3D view with mesh and tools | mesh/assembly |
| S08 | 5.2 | Contact pair property panel | contact |
| S09 | 6.5 | Load step with its conditions + force arrow | load step |
| S10 | 7.1 | Export dialog / draft warning | export |
| S11 | 7.2 | Exported package folder | package |
| S12 | 8.3 | Core summary dialog | Run Core |
| S13 | 8.3 | Report view after the run | Run Core |
| S14 | 8.5 | 3D result with a field | results (optional) |
| S15 | 8.6 | Results panel with force plot | results (optional) |
| S16 | 8.6 | Results panel with probe/line | results (optional) |

For the thesis chapters the useful ones are S04 (model tree), S02/S05/S08/S09 (properties
panel) and S06/S07 (mesh). The result shots (S14-S16) are optional: the thesis shows
results in ParaView.

## Result sheet (copy for each run)

| Step | Pass / Fail / Blocked | Note (what you saw, red text, screenshot) |
|---|---|---|
| 0.2 |  |  |
| 0.3 |  |  |
| 1.1 |  |  |
| 1.2 |  |  |
| 2 |  |  |
| 3 |  |  |
| 4 |  |  |
| 5 |  |  |
| 6 |  |  |
| 7 |  |  |
| 8 |  |  |
| 9 |  |  |
| 10 |  |  |
| Total time |  |  |

## Regression notes

- Native FEM constraints remain the source of truth. A condition moved into a CTform step has
  the step as its document-group parent and the step defines when it applies.
- Dragging a condition into a step and **Attach Selected Condition to Load Step** must give the
  same group membership and exported JSON.
- Root mechanical/thermal conditions are global. Detaching from a step returns them to the root.
- **Clone Load Step** makes new child conditions; generic copy/paste is not the supported way.
- FEM condition targets must resolve to a physical group exported with the assigned Gmsh mesh;
  group names and IDs should be stable across repeated exports.
- Tool displacement and force conditions become per-step tool data in `loadsteps.json`.
- Core's thermal BC schema has `ambientTemperature` for convection/radiation; the adapter does
  not map native FEM convection/radiation fields yet (blocked).
- The Core reads only `simulation.penalty`, not per-interface `normal.penalty`.
- Root-global conditions apply to every step; a step-local condition wins on overlapping
  targets and produces an export warning.
