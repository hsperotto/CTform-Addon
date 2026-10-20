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
- 52 unit tests pass (`python -m unittest discover -s tests`; pytest is not
  installed on the PC).

## In progress
- Nothing.

## Next
1. Fresh interactive run of `MANUAL-SMOKE-TEST.md` in FreeCAD; renumber old
   StepIds, set Solver initial temperatures and Tool roles, re-export SmokeTest.
2. Run the exported SmokeTest with Core `agent/v2-thermal-bcs` end to end.
3. Validate contact-pair physical-group references; add conflict diagnostics.
4. Harden SI geometry export and preflight for more CAD shapes.
5. Minimal solver run command (invoke `ctform3_cli`, pass `--tune` options).

## Blocked
- Mapping convection/radiation/heat flux to Core: Core v2 accepts only
  Temperature thermal BCs (no area/volume weighting yet). Export reports them
  as readiness issues meanwhile.
- Running cases with Core `master`: the v2 reader and the `-ffast-math` tool
  motion fix exist only on Core `agent/*` branches.
