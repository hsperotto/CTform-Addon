# Addon status

Details and design rules: `DEVELOPMENT-CONTEXT.md`. Core contract: `Core-Refactor.md`.

## Done
- TCC generator has no default formulation or material: `CTFORM_TCC_FORMULATION` (flow|displacement) and
  `CTFORM_TCC_MATERIAL` are required and the run aborts with `TCC ERROR` if unset or invalid. Merged into main.
- TCC generator takes `CTFORM_TCC_HOLDER_PRESSURE` (MPa, default 5) for the blank holder force. Sensitivity
  packages in Receba/runs/bh-sensitivity (7.5 and 10 MPa). Merged into main.
- Results viewer force series uses `Force_Total` (normal + friction) when `press_force_by_tool.csv` has it
  (Core 4825fb9+), else `Force`. Merged into main.
- TCC remesh sizes default to hBase = hMin = hMax = 0.25 mm (match the 0.25 mm structured Quad4 start mesh;
  the old 0.2/0.25/0.3 grew the element count ~3.5x and Core's ElementBudget refused every remesh).
  Package set `C:/ctf-probes/tcc-quad4-remesh-h025` (3 blank-90 cases). Merged into main.
- TCC generator writes `manifest.csv` (mu, mesh size, formulation, remesh, stroke, addon commit, ...) and takes
  `CTFORM_TCC_MESH_SIZE` (mm). Friction sweep packages for Cilinder_Blank90: `C:/ctf-probes/tcc-quad4-mu{0.15,0.25,0.30}`.
  Merged into main.
- TCC generator turns on `StructuredSheetMesh` (element size 0.25 mm x `CTFORM_TCC_MESH_SCALE`),
  so `workpiece.msh` is Quad4 (checked on Cilinder_Blank100: `elementTypes ["Quad4"]`, groups
  Edge1-4 and Face1 unchanged). No Tri3 validation added; Tri3 stays possible elsewhere. Batch not regenerated.
- FreeCAD 1.1 workbench: case, solver, Workpiece/Tool folders, shared material
  catalog, Gmsh MSH2 mesh, contact pairs, load steps, native FEM conditions.
- v2 package export (`case.json`, `materials.json`, `thermal.json`,
  `loadsteps.json`, MSH2, ASCII DXF).
- New load steps get unique StepIds; export rejects duplicate StepIds and the
  readiness check reports them. Tool records are numbered uniquely per step.
- Initial temperatures live on the Solver (`thermal.initialTemperature`);
  tool motions export `toolId`; readiness lists features Core v2 rejects;
  `packageStatus` is `ready` when no issues remain.
- Tool `Role` is removed (Core derives each tool's side from its geometry):
  no `geometry.tools[].role` is exported and old documents lose the property.
- Native thermal BCs follow Core v2 (Core `a462978`): FreeCAD Heat Flux
  exports by ConstraintType (DFlux -> HeatFlux, Convection, Radiation); body
  heat source Dissipation Rate (W/kg) x workpiece density -> HeatGeneration
  W/m^3. CFlux and Total Power are rejected.
- Readiness also checks that a TabulatedFlowStress table is a complete
  T x rate x strain grid.
- Forces: only on Tools. Tool force motion exports
  `motion {type: "force", direction: [dx, 0, dz], value: F >= 0}` from the FEM
  force's DirectionVector (Reversed included); `axis` and `forceTarget` are no
  longer written. A Force condition on the Workpiece is a readiness error and is
  never exported. An axisymmetric Tool force with a radial component is a
  readiness error. Forces need no tool role.
- Solver `GmshExecutable` / `MmgDirectory` export `run.externalTools` when set.
- DXF export no longer uses FreeCAD's exporter: it wrote any arc with a chord
  shorter than ~1e-2 units (every R6 mm corner, exported in metres) as a full
  CIRCLE. `dxf_writer.py` writes exact LINE/ARC/CIRCLE (other curves are
  discretized).
- Five-punch preparation (industrial arrangement): AISI 304 catalog in
  `resources/materials/aisi304-1mm-nunes2025.json` (Hollomon K/n for 0/45/90 deg
  and the mean, E/nu/rho from Rocha 2022; thermal values are placeholders);
  Solver `ExportTargetCompression` (off omits `run.targetCompression`);
  `analysis.apply_isothermal_preset(solver)`; headless probe
  `tests/freecad/probe_five_punch_export.py`.
- Axisymmetric flow cases need a radial displacement BC of 0 on the r = 0 edge of the
  sheet (Core's flow solver does not constrain the axis); the probe adds it as a
  Displacement constraint on that edge (`Displacement`, `axis X`, `value 0`).
- Readiness also reports a Workpiece mechanical BC (fixed, displacement, symmetry, velocity)
  or surface thermal BC (heat flux, convection, radiation) that is not tied to an
  edge, because Core applies such a BC to every node; whole-body Temperature and
  HeatGeneration are allowed. A Tool force with any radial component is a readiness
  issue (Core moves tools only along Z for now).
- Run CTform Core command (Solver `CoreExecutable`): runs `ctform3_cli`, logs,
  and reports convergence, package warnings and step files (`core_runner.py`).
- Contact interfaces name their master tool explicitly (`masterBody`,
  `masterToolId`, `master.name/toolId`) and the workpiece slave group.
- Thesis test matrix (merged to `main` 2026-11-01): `tcc/Geometrias.FCStd` is a copy of the author's drawings
  (5 punches, BlankHolder, Die, 3 blanks D90/100/110 x 1 mm, axisymmetric, mm). The original is
  `Receba/Workspace/Geometrias.FCStd` (old values, untouched). Values changed by the author on 2026-11-01 to
  Nunes 2025: die opening R27 and entry R6, holder bore R27, cylindrical punch corner R6.
  `tcc/generate_assays.py` (FreeCADCmd) builds 5 x 3 = 15 packages, all `ready`, to `CTFORM_TCC_OUT`
  (`C:/ctf-probes/tcc` without remesh, `C:/ctf-probes/tcc-remesh` with remesh; Cody reads both, do not
  overwrite them while a run is going). Punch, holder and die touch the blank at start (gap 0).
  Strokes per punch and blank come from Thay (`STROKE_MM`, 30 to 70 mm, Nunes Figs. 24/26/28), 19.5 mm/s,
  holder F = p*pi*(D0^2-54^2)/4 at 5 MPa (thesis hypothesis), Coulomb mu 0.2, sheet mesh 0.25 mm.
  Addon choices, NOT in the thesis: 0.3 mm of punch travel per increment and `toolMeshSize` 0.5 mm.
  All generator switches are `CTFORM_TCC_*` (see the script's docstring).
- Optional `toolMeshSize` per tool (Tool property `ToolMeshSize`, mm, exported in metres; Core multiplies by
  1e3). Without it Core reuses the sheet element size on the tool and Gmsh times out.
- Remesh export: Solver properties `RemeshEnabled`, `RemeshEngine`, `RemeshInterval`, `RemeshMinIncrements`,
  `RemeshMaxSteps`, `RemeshHBase/HMin/HMax` (mm), `RemeshQualityMinScoreRetention`. `case.json` carries the full
  `remesh` block in metres; the "Core v2 does not support remeshing" readiness issue is gone. Only Core branch
  `agent/v2-rigid-tool-segments` accepts the block; Core `master` may reject it.
- Hollomon `referenceStrainRate` (1/s, Material `HollomonReferenceStrainRate`; exported only when > 0; Core
  reads it on `agent/v2-rate-reference`). Generator switches `CTFORM_TCC_MRATE` / `CTFORM_TCC_REF_RATE`.
  Defaults unchanged. No round-3 rate-sensitive packages were generated: the aborts were numerical, in Core's
  Newton, so the thesis material stays as it is.
- 123 unit tests pass (`python -m unittest discover -s tests`; pytest is not
  installed on the PC).

## In progress
- TCC campaign (2026-11-01): the author paused all Core runs to decide how to proceed. Cody (Core session)
  found that the round 1 and 2 aborts were numerical (Newton merit gamma = 1e7, blind alpha = 0.5); the CLI
  settings `flow_gamma_fixed=1` and `flow_linesearch_bootstrap=0` fix them. Round 3 (packages of
  `C:/ctf-probes/tcc-remesh`) broke at the second remesh (increment 20): a Core bug (Gmsh full-quad failure
  and a template fallback that zeroed the material state), to be fixed in Core.
- Pre-authorisation (author, 2026-11-01): regenerating TCC case files on Cody's request needs no new approval,
  but the drawn geometry, the 15-case matrix, the thesis values and merges to `main` do.
- Offered, not done (wait for the author): write `run.tuning` (`flow_gamma_fixed`, `flow_linesearch_bootstrap`)
  into `case.json` `run`, which Core passes on from `agent/v2-rate-reference` (fdfaaa9).
- All addon branches are merged. Merged branches stay on origin until the author deletes them. Nothing was
  pushed or tagged.

## Next
1. Fresh interactive run of `MANUAL-SMOKE-TEST.md` in FreeCAD. Restart FreeCAD first to pick up
   the icons and the Run CTform Core command.
2. Run the SmokeTest package with Core `master` (the v2 reader and the v2 thermal/force BCs are in it).
3. Validate contact-pair physical-group references; add conflict diagnostics.
4. Geometry preflight: wire `validation.py` into the export, or delete it.
5. Check Run CTform Core and the Results panel interactively in the FreeCAD GUI on the TCC cases when Core returns them (the VTK reader itself ran on probe9). Also confirm the `Pressure` sign on a longer run.
6. Results viewer phases 3+ of `docs/RESULTS-VIEWER-PLAN.md` (not started).

## Blocked
- Nothing is blocked on the addon side. The old five-punch aborts (Core `08e9ac4`, task C-M1) were fixed in Core
  (see below), and the TCC aborts were Core's Newton (Cody, 2026-11-01). Waiting on the Core fix for the
  second-remesh failure and on the author's decision on how to continue. Old probe packages:
  `C:/ctf-probes/five-punch`.
- Per-pair penalty (`normal.penalty`) is exported but Core v2 ignores it until Core accepts the key.


## Core reference (checked 2026-11-01, via Cody)
- Core `master` is 96e4e6d (includes 35029aa). Branches the TCC packages depend on: `agent/v2-rigid-tool-segments`
  (3754039: rigid tools are the DXF outline only, no volume mesh; remesh in v2) and `agent/v2-rate-reference`
  (3a490ca, fdfaaa9: `referenceStrainRate`, `run.tuning`).

## Core reference (checked 2026-10-30)
- Core `master` 35029aa has Swift hardening, the displacement formulation (pure Quad4), force-controlled
  tools solved in Newton and the C-M1 friction fix. `CORE_SWIFT_SUPPORTED = True`: Swift exports are no longer draft.
  Probes 17-21 (`C:/ctf-probes/five-punch`, Quad4 displacement) are being run by Cody.
- Core `master` contains `agent/v2-thermal-bcs` (a462978 and later), so the earlier wait on that
  branch is over. Core `master` HEAD is `6fa07e9`, a work-in-progress force-servo commit on top.
  The probe runs used `08e9ac4`.

## Recent (2026-10-30)
- `docs/DEVELOPER-GUIDE.md`: module and object graphs, export and run flows, recipes and review findings.
- Run CTform Core: reports every worker failure, refuses a second run while one is active, loads
  results into the document that started the run, and reports an import failure instead of raising.
- New Solver property `CoreTimeoutMinutes` (0 = no limit) stops a hung Core.
- `properties.py` holds the single `add_property` and `length_to_si` helpers (were duplicated in five modules).
- Removed the unused `CTform_CreateAnalysis` command alias.
- Release prep: version 1.0.0 in `package.xml` and `pyproject.toml`, CHANGELOG entry. Tag 1.0.0 is the author's.

## Results viewer, phases 0-2 (merged to main 2026-11-01)
- `results.py` (stdlib only): force CSV, stroke from first contact (displacement minus initial gap, with the
  1 %-of-peak cross-check), ASCII VTK reader for Core step files, maximum of a field over the workpiece
  with its (r, z), probe, line profile, summary CSV, `ResultsSession`. 13 tests in `tests/test_results.py`
  (synthetic mini VTK); `CTFORM_REAL_RESULTS=1` also checks Core's probe9 output.
- `results_panel.py` + command `CTform_ResultsPanel` (toolbar and menu): dock with force-vs-stroke plot
  (click selects the step), step slider labelled with time and stroke, field list, maximum and location,
  colour range, warp factor, probe, line plot, summary CSV. Run CTform Core still loads the 3D result.
- Verified on real Core output (`C:/ctf-probes/five-punch/probe9_gap0_mu0.2`, 3 steps, 87k points):
  reads in ~2 s per step; the panel was driven offscreen in FreeCADCmd (all fields, probe, line, warp call, click).
- NOT verified: the interactive GUI (docking, the 3D view's `Field`, `RangeMin/Max`, warp filter in the
  tree), because FreeCADCmd has no view objects. `FemPostPipeline.Data` is None headless, so the pipeline's own
  field list was not inspected. The pipeline's Frame labels round the time to 2 decimals ('0.02 T'); the panel
  shows the exact time and stroke.
- `Pressure` sign and terms (plan section 3): probe9 has only 3 steps (max 0.09 MPa), so still OPEN.
- The stroke gap is 0 by default (all TCC cases start in contact); there is no gap field in the panel yet.

## Structured sheet mesh (branch agent/structured-sheet-mesh)
- Workpiece property `StructuredSheetMesh` (default off) and `StructuredElementSize` (default 0.25 mm).
  When on, the four-edge sheet face gets transfinite curves, a transfinite surface and a recombine
  line injected after the Merge in the Gmsh geometry (`gmsh_package.structured_sheet_lines`,
  `inject_after_merge`). Element counts come from the edge lengths; opposite edges must match and each
  edge must be a whole number of elements.
- Verified: unit test with Gmsh 4.15 gives 720 Quad4 for the 45 x 1 mm sheet; FreeCAD probe
  (`CTFORM_PROBE_STRUCTURED=1`) gives 720 Quad4, 905 nodes, status ready, edge physical groups intact.
- Blanks 90/100/110 mm (radius 45/50/55 mm) give 180/200/220 x 4 elements (Thay, Henrique's choice).
- Curves are selected by FreeCAD edge index, the same tag GmshTools uses for the EdgeN physical groups,
  so no bounding-box selection is used.
