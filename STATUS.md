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
- Tools have a `Role` (auto/upper/lower); upper/lower is exported as
  `geometry.tools[].role`, auto lets Core infer it from the DXF position.
- Native thermal BCs follow Core v2 (Core `a462978`): FreeCAD Heat Flux
  exports by ConstraintType (DFlux -> HeatFlux, Convection, Radiation); body
  heat source Dissipation Rate (W/kg) x workpiece density -> HeatGeneration
  W/m^3. CFlux and Total Power are rejected. Workpiece Force BCs are exported
  (flow formulation only); zero force components are dropped.
- Readiness also checks that a TabulatedFlowStress table is a complete
  T x rate x strain grid, and that force-controlled motion is not on a Tool
  with Role `lower` (Core's servo only pushes toward -Z).
- 57 unit tests pass (`python -m unittest discover -s tests`; pytest is not
  installed on the PC).

## In progress
- Branch `agent/core-thermal-force-sync` (this work) must merge into addon
  `main` only after Core `agent/v2-thermal-bcs` is merged into Core `master`.
  Core `master` still rejects these thermal BCs, workpiece forces and
  TabulatedFlowStress, and refuses packages with readiness issues.

## Next
1. Fresh interactive run of `MANUAL-SMOKE-TEST.md` in FreeCAD; renumber old
   StepIds, set Solver initial temperatures and Tool roles, re-export SmokeTest.
2. Run the exported SmokeTest with Core `agent/v2-thermal-bcs` end to end.
3. Validate contact-pair physical-group references; add conflict diagnostics.
4. Harden SI geometry export and preflight for more CAD shapes.
5. Minimal solver run command (invoke `ctform3_cli`, pass `--tune` options).

## Blocked
- Running cases with Core `master`: the v2 reader and the `-ffast-math` tool
  motion fix exist only on Core `agent/*` branches.
