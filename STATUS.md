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
1. Harden SI geometry export and preflight for more CAD shapes.
2. Map native FEM convection/radiation (and ambient temperature) to Core thermal inputs.
3. Validate contact-pair physical-group references; add conflict diagnostics.
4. Resolve Core's global-tool plus per-step-tool merge before multi-tool runs.
5. Minimal solver configuration and run command.
6. Fresh interactive run of `MANUAL-SMOKE-TEST.md`; re-export SmokeTest.

## Blocked
- Running exported cases: Core still reads only the legacy contract, not v2.
