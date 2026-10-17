# CTform FreeCAD Interface Development Context

This file is a handoff note for resuming development.

## Product identity

- Product family: CTform.
- Proprietary simulation executable/application: CTform Core.
- FreeCAD addon identity: CTform FreeCAD Interface.
- FreeCAD workbench display name: CTform.
- Python package: `CTformFreeCADInterface`.
- Workbench class: `CTformFreeCADInterfaceWorkbench`.
- CTform Core is not distributed with this addon.

## Licensing

- Addon source: LGPL-3.0-or-later.
- Branding and protected graphics: separate `LICENSE-Assets` license.
- CTform Core has its own license and is outside this repository's distribution.

## Architectural decisions

1. FreeCAD is the primary user workflow and CTform Core is an external engine.
2. The addon follows FreeCAD 1.1 FEM conventions instead of creating a parallel
   simulation object system.
3. The native FreeCAD container is `Fem::FemAnalysis`, displayed as `CTform Case`.
4. A child `App::FeaturePython` object named `CTformCase` stores CTform case
   settings and export metadata.
5. A CTform solver/job object uses `Fem::FemSolverObjectPython` and will call
   `ctform3_api` or `ctform3_cli` later.
6. Native FEM geometry, material, mesh, mechanical constraints, thermal
   constraints, and results remain native objects.
7. CTform-specific objects are limited to roles, tool motion, contacts, load-step
   scheduling, case export, and Core execution.
8. No custom folders are added inside the FEM analysis. Load steps are the
   exception: each `CTformLoadStep` is an expandable
   `App::DocumentObjectGroupPython` directly under the analysis.
9. Tool roles are only `workpiece` and `tool`. Tools have arbitrary explicit names
   through `ToolName`; there are no upper/lower/fixture roles.
10. The case package remains split into focused files:
    `case.json`, `material.json`, `thermal.json`, and `loadsteps.json`.

## Golden workflow

```text
Create CTform Case
-> Create geometry with Part/Sketcher/Draft/FEM tools
-> Assign workpiece/tool roles with explicit tool names
-> Create or reuse FEM materials
-> Create/refine a 2D Gmsh mesh
-> Create load-step folders
-> Attach native FEM mechanical and thermal conditions to steps
-> Add named tool motions to steps
-> Export the complete case package
-> Run CTform Core
-> Inspect results
```

The first supported model is axisymmetric, with plane strain as a later option.
The initial geometry contract uses FreeCAD sketch X -> CTform radial r and
FreeCAD sketch Y -> CTform axial z.

## Current addon implementation

Package location:

```text
freecad/CTformFreeCADInterface/
```

Implemented modules:

- `init_gui.py`: registers CTform and loads selected FEM commands lazily.
- `analysis.py`: creates native `Fem::FemAnalysis`, CTform case settings, and a
  FEM-compatible CTform solver/job object.
- `commands.py`: creates cases and solvers, assigns roles, creates load steps,
  adds prototype mechanical BCs/tool motions, exports cases, and exposes selected
  FEM material/Gmsh commands.
- `roles.py`: role assignment objects linking native objects to `workpiece` or
  named `tool` roles.
- `loadsteps.py`: load-step folder objects, mechanical/thermal link lists, and
  CTform tool-motion objects.
- `case_export.py`: writes `case.json` and `loadsteps.json`, including role,
  load-step, mechanical-BC, thermal-BC, and tool-motion serialization.
- `validation.py`: FreeCAD-independent initial XY-plane validation helpers.

Selected FEM commands exposed in CTform:

- `FEM_MaterialEditor`
- `FEM_MaterialSolid`
- `FEM_MeshGmshFromShape`
- `FEM_MeshRegion`
- `FEM_MeshGroup`
- `FEM_MeshDisplayInfo`
- `FEM_MeshClear`

No FEM solver commands are exposed in CTform menus.

## Current validation

The addon currently has 7 passing Python tests. Python compilation and diagnostics
also pass. The FreeCAD runtime smoke tests already confirmed that the workbench
appears and can create a case; the native FEM case/solver and load-step folder
changes still need a fresh interactive smoke test.

## CTform Core findings

The CTform source is at:

```text
C:\Users\henri\Desktop\TCC\CTForm
```

Relevant existing integration layer:

- `ctform3_api`: Python API/CLI orchestration.
- `ctform3_cli`: C++ case execution executable.
- `CaseConfigLoader`: loads `case.json` and referenced sidecar files.
- `PreprocessorBuilder`: creates runtime load steps and runtime conditions.
- `CasePrepared`: caches prepared models using a fingerprint that includes the
  case, material, loadsteps, thermal, mesh, and tool files.

The current Core contract is:

```text
case.json
    -> material.json
    -> thermal.json
    -> loadsteps.json
    -> prepared runtime model
    -> ctform3_cli execution
```

`loadsteps.json` is essential. It is parsed into runtime `LoadStep` objects and
controls time windows, increments, mechanical BCs, thermal BCs, tool motions,
tool thermal state, runtime timesteps, and contact scheduling.

Global thermal data comes from `thermal.json`; step-specific thermal conditions
come from `loadsteps.json` and are merged into each runtime step. Mechanical BCs
are step-specific. Tool identity belongs in `case.json`, while tool motion and
thermal state belong in `loadsteps.json`.

The current Core examples still use `upper` and `lower` tool roles. The addon
intentionally uses generic named tools instead. Core refactoring to merge tool
identity and per-step tool data by stable name/ID is deferred until the FreeCAD
workflow is more complete.

## Important remaining work

### Highest priority

1. Replace the prototype custom mechanical-BC creation path with commands that
   attach selected native FEM mechanical constraints to a load-step folder.
2. Add the equivalent native FEM thermal-condition attachment path.
3. Add a proper thermal configuration/material exporter:
   - FEM material data -> `material.json`
   - thermal material tables/global thermal settings -> `thermal.json`
4. Add mesh and geometry export/reference handling. Current role export can still
   produce empty `file` values for native FreeCAD objects.
5. Add CTform contact-interface objects and export them by named workpiece/tool.
6. Add a minimal solver configuration and run command after the exported package
   is complete.

### Later/deferred

- Full load-step editor; the current property panels and folders are enough for
  the first prototype.
- Advanced solver tuning.
- Diagnostics configuration.
- ALE and remeshing configuration.
- General case import/migration.
- Result import and visualization.
- Core refactoring for generic named tools.

## Design rules for the next session

- Do not create a second geometry/material/mesh/constraint system.
- Do not restore upper/lower/fixture role semantics.
- Do not expose unrelated FEM solvers in CTform.
- Keep native FEM objects as the source of truth and use CTform objects for
  scheduling, mapping, contact, tool motion, and Core integration.
- Treat the JSON files as an export package, not as the primary FreeCAD document
  model.
- Avoid deep investigation of solver calculations; inspect only the Core input,
  preprocessing, runtime setup, and result contracts needed by the addon.
