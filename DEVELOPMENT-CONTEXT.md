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
7. CTform-specific objects are limited to roles, contacts, load-step scheduling,
   case export, and Core execution. Native FEM conditions remain the source of
   truth; tool motion is mapped from native FEM conditions during export.
8. No custom folders are added inside the FEM analysis. Load steps are the
   exception: each `CTformLoadStep` is an expandable
   `App::DocumentObjectGroupPython` directly under the analysis.
9. Tool roles are only `workpiece` and `tool`. Tools have arbitrary explicit names
   through `ToolName`; there are no upper/lower/fixture roles.
10. New case packages use `case.json`, `materials.json`, `thermal.json`,
   `loadsteps.json`, and a native Gmsh MSH2 mesh artifact. Legacy singular
   `material.json` remains a Core migration input.

## Golden workflow

```text
Create CTform Case
-> Create geometry with Part/Sketcher/Draft/FEM tools
-> Assign workpiece/tool roles with explicit tool names
-> Create/assign CTform material catalog entries
-> Create/refine a 2D Gmsh mesh
-> Assign the FEM/Gmsh mesh to the workpiece role
-> Create visible workpiece/tool contact pairs
-> Create load-step folders
-> Create native FEM mechanical and thermal conditions
-> Drag/attach conditions into a step; leave global conditions at analysis root
-> Clone steps with the CTform Clone Load Step command
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
- `commands.py`: creates cases, solvers, and CTform materials; assigns roles,
  materials, and FEM meshes; creates contact pairs/load steps; attaches and
  detaches native FEM conditions; clones steps; exports cases.
- `roles.py`: role assignment objects linking native objects to `workpiece` or
  named `tool` roles.
- `materials.py`: CTform-owned material records with stable IDs, named
   constitutive parameters, unit-aware scalar properties, and table fields.
- `contacts.py`: visible workpiece-to-tool contact pairs and v2 serialization.
- `gmsh_package.py`: uses FreeCAD FEM `GmshTools` to save the same Gmsh run as
   native MSH2 for Core and refresh the visible FEM mesh from UNV; no custom mesh
   serialization.
- `geometry_export.py`: exports each role profile as ASCII DXF, with workpiece
   `EdgeN` layers matching mesh physical groups and all coordinates scaled to m.
- `loadsteps.py`: load-step groups that own native mechanical/thermal condition
   children; the `MechanicalBCs` and `ThermalBCs` properties mirror group contents
   for serialization and inspection. Analysis-root conditions are global across
   steps.
- `case_export.py`: writes the v2 package (`case.json`, `materials.json`,
  `thermal.json`, `loadsteps.json`, linked MSH2, and per-role ASCII DXFs),
  including stable IDs, physical groups, contact pairs, conditions, and
  readiness warnings.
- `validation.py`: FreeCAD-independent initial XY-plane validation helpers.

Selected FEM commands exposed in CTform:

- `FEM_MaterialEditor`
- `FEM_MaterialSolid`
- `FEM_MeshGmshFromShape`
- `FEM_MeshRegion`
- `FEM_MeshGroup`
- `FEM_MeshDisplayInfo`
- `FEM_MeshClear`
- Native FEM fixed, displacement, force, temperature, heat-flux, and body-heat
   source commands, plus CTform material, mesh assignment, contact-pair, attach,
   detach, and clone-step actions.

No FEM solver commands are exposed in CTform menus.

## Current validation

The addon currently has 26 passing Python tests. Python compilation and diagnostics
also pass. The FreeCAD runtime smoke tests already confirmed that the workbench
appears and can create a case; the updated native condition, material, mesh, and
load-step workflow in `MANUAL-SMOKE-TEST.md` still needs a fresh interactive run.

## CTform Core findings

Before changing Core's input, material, geometry, or runtime contracts, read
[`Core-Refactor.md`](Core-Refactor.md). Keep its assumption/problem log current
whenever investigation establishes a new fact, decision, or unresolved issue.

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

Core currently reads the legacy contract; the addon writer targets the accepted
v2 contract described in `Core-Refactor.md`:

```text
case.json (schemaVersion 2)
   -> materials.json
   -> workpiece.msh (Gmsh MSH2)
   -> geometry/workpiece.dxf and geometry/tools/*.dxf (ASCII)
   -> thermal.json
   -> loadsteps.json
   -> prepared runtime model
   -> ctform3_cli execution
```

`loadsteps.json` is essential. It is parsed into runtime `LoadStep` objects and
controls time windows, increments, mechanical BCs, thermal BCs, tool motions,
tool thermal state, runtime timesteps, and contact scheduling.

Root mechanical conditions are serialized as global scope; step conditions are
local and override conflicts with warnings. Global thermal conditions live in
`thermal.json`; step-local thermal conditions live in `loadsteps.json`. Tool
identity/material belongs in `case.json`; per-step tool state lives in
`loadsteps.json`.

The current Core examples still use `upper` and `lower` tool roles. The addon
intentionally uses generic named tools instead. Core refactoring to merge tool
identity and per-step tool data by stable name/ID is deferred until the FreeCAD
workflow is more complete.

## Important remaining work

### Highest priority

1. Harden SI-normalized role geometry export and preflight for more CAD shapes;
   current export supports planar profiles/entities understood by the Core ASCII
   DXF parser.
2. Map native FEM convection/radiation fields to Core thermal inputs, including
   ambient temperature. Native FEM initial-temperature conditions now export as
   separate case- or step-scoped initial state.
3. Validate contact-pair physical-group references and add conflict/preflight
   diagnostics for arbitrary groups and complex pair topology.
4. Resolve Core's global-tool plus per-step-tool merge behavior before running
   cases with multiple named tools.
5. Add a minimal solver configuration and run command after the exported package
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
- Keep native FEM conditions as the source of truth; CTform load-step groups own
   attached conditions and define their step scope. Drag and attach-command paths
   must stay equivalent.
- Do not restore upper/lower/fixture role semantics.
- Do not expose unrelated FEM solvers in CTform.
- New addon packages use v2 SI values, `materials.json`, and native MSH2 mesh
   references; don't regress to a custom mesh writer or singular new material file.
- Keep native FEM objects as the source of truth and use CTform objects for
  scheduling, mapping, contact, tool motion, and Core integration.
- Treat the JSON files as an export package, not as the primary FreeCAD document
  model.
- Avoid deep investigation of solver calculations; inspect only the Core input,
  preprocessing, runtime setup, and result contracts needed by the addon.
