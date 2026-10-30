# Addon status

Details and design rules: `DEVELOPMENT-CONTEXT.md`. Core contract: `Core-Refactor.md`.

## Done
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
- 81 unit tests pass (`python -m unittest discover -s tests`; pytest is not
  installed on the PC).

## In progress
- Nothing open on the addon side. Merged branches stay on origin until the author deletes them.

## Next
1. Fresh interactive run of `MANUAL-SMOKE-TEST.md` in FreeCAD. Restart FreeCAD first to pick up
   the icons and the Run CTform Core command.
2. Run the SmokeTest package with Core `master` (the v2 reader and the v2 thermal/force BCs are in it).
3. Validate contact-pair physical-group references; add conflict diagnostics.
4. Geometry preflight: wire `validation.py` into the export, or delete it.
5. Check Run CTform Core on a converging case. The import of `case_step_*.vtk` has not run on real output yet.

## Blocked
- Five-punch cases abort at the first contact (Coulomb 0.2 and Levanov 0.2 fail with
  `line_search_failed_all_lambdas`) on Core `08e9ac4`. Core task C-M1 (friction treatment in the
  flow formulation). Probe packages: `C:\ctf-probes\five-punch`.
- Per-pair penalty (`normal.penalty`) is exported but Core v2 ignores it until Core accepts the key.


## Core reference (checked 2026-10-30)
- Core `master` 35029aa has Swift hardening, the displacement formulation (pure Quad4), force-controlled
  tools solved in Newton and the C-M1 friction fix. `CORE_SWIFT_SUPPORTED = True`: Swift exports are no longer draft.
  Probes 17-21 (`C:\ctf-probesive-punch`, Quad4 displacement) are being run by Cody.
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
