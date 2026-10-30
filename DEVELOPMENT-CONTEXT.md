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
7. CTform-specific objects include Workpiece and Tool folders, contacts,
   load-step scheduling, Solver settings, case export, and Core execution.
   Native FEM conditions remain the source of truth; tool motion is mapped from
   native FEM conditions during export.
8. The FEM analysis contains expandable Workpiece, Tool, CTform Materials, and
   Load Step folders. The Workpiece owns contact pairs; each component links its
   shape, mesh, and one shared catalog material. Tools have explicit names and
   readable stable IDs.
9. Modeling dimension, formulation, contact numerics, thermal/run/output
   settings, ALE, and remeshing belong to the CTform Solver object. The Case
   remains component- and dimension-neutral.
10. New case packages use `case.json`, `materials.json`, `thermal.json`,
   `loadsteps.json`, and a native Gmsh MSH2 mesh artifact. Legacy singular
   `material.json` remains a Core migration input.

## Golden workflow

```text
Create CTform Case
-> Create geometry with Part/Sketcher/Draft/FEM tools
-> Create Workpiece and named Tool folders from selected shapes
-> Choose/import shared CTform materials and link them from components
-> Create/refine a 2D Gmsh mesh
-> Assign the FEM/Gmsh mesh to its component folder
-> Create visible Workpiece-to-Tool contact pairs
-> Configure dimension/modeling and execution on the Solver object
-> Create load-step folders
-> Create native FEM mechanical and thermal conditions
-> Drag/attach conditions into a step; leave global conditions at analysis root
-> Clone steps with the CTform Clone Load Step command
-> Export the complete case package
-> Run CTform Core
-> Inspect results
```

The current solver supports axisymmetric and plane-strain 2D models. Geometry
and load-step ownership live outside Solver; FreeCAD sketch X maps to radial r
and sketch Y maps to axial z for axisymmetric cases.

## Current addon implementation

Package location:

```text
freecad/CTformFreeCADInterface/
```

Implemented modules:

- `init_gui.py`: registers CTform and loads selected FEM commands lazily.
- `analysis.py`: creates native `Fem::FemAnalysis`, dimension-neutral CTform
   case settings, and the Solver-owned modeling/execution settings.
- `components.py`: Workpiece and Tool folders with direct shape, mesh, material,
   stable identity, and contact links.
- `commands.py`: creates cases, solvers, components, and CTform materials;
   assigns materials and FEM meshes; creates contact pairs/load steps; attaches and
  detaches native FEM conditions; clones steps; exports cases.
- `materials.py`: shared case-level CTform material catalog, readable stable
   IDs, JSON import, named constitutive parameters, unit-aware properties, and
   material snapshot export.
- `contacts.py`: visible workpiece-to-tool contact pairs and v2 serialization.
- `gmsh_package.py`: uses FreeCAD FEM `GmshTools` to save the same Gmsh run as
   native MSH2 for Core and refresh the visible FEM mesh from UNV; no custom mesh
   serialization.
- `geometry_export.py`: exports each component profile as ASCII DXF, with Workpiece
   `EdgeN` layers matching mesh physical groups and all coordinates scaled to m.
- `loadsteps.py`: load-step groups that own native mechanical/thermal condition
   children; the `MechanicalBCs` and `ThermalBCs` properties mirror group contents
   for serialization and inspection. Analysis-root conditions are global across
   steps.
- `case_export.py`: writes the v2 package (`case.json`, `materials.json`,
  `thermal.json`, `loadsteps.json`, linked MSH2, and component ASCII DXFs),
  including stable IDs, physical groups, contact pairs, conditions, and
  readiness warnings.
- `validation.py`: FreeCAD-independent initial XY-plane validation helpers.

Selected FEM commands exposed in CTform:

- `FEM_MeshGmshFromShape` (the smoke-test workflow sets first-order elements)
- `FEM_MeshRegion`
- `FEM_MeshGroup`
- `FEM_MeshDisplayInfo`
- `FEM_MeshClear`
- Native FEM fixed, displacement, force, temperature, heat-flux, and body-heat
   source commands, plus CTform material, mesh assignment, contact-pair, attach,
   detach, and clone-step actions.

No FEM solver commands are exposed in CTform menus.

## Current validation

The addon currently has 81 passing Python tests (`python -m unittest discover -s tests`, as of 2026-10-30). Python compilation and diagnostics
also pass. FreeCAD 1.1 runtime probes have verified component-tree save/reopen,
shared material catalog import with unit-aware values, nested Workpiece Gmsh
MSH2 export in `From Shape` mode, and native FEM Force `DirectionVector` mapping.
The complete GUI workflow in `MANUAL-SMOKE-TEST.md` still needs a fresh
interactive run.

## 2026-10-18 Handoff Status

- **Resolved:** The Tool Force export reads FEM's `DirectionVector`, not the
   `Direction` geometry link. For the supported XY profile, FEM X maps to CTform
   radial X and FEM Y maps to axial Z. Tool force control remains axial only;
   radial force and Workpiece Force are rejected. When assigning a tool Force,
   reference the Tool folder's source face so the condition can resolve its
   stable ToolId; selecting a separate sketch edge did not match the Tool shape.
- **Superseded (2026-10-30):** The statement that initial-temperature support was
   removed no longer holds. Initial workpiece and tool temperatures are Solver
   properties exported as `thermal.initialTemperature` (K). Workpiece Temperature,
   Heat Flux, Convection, Radiation and body Heat Source are exported to Core v2
   (see `STATUS.md`). Tool Temperature handling was not re-checked in the current
   export code; verify it before relying on it.
- **Resolved:** The native FEM Gmsh command is used. Set `ElementOrder` to `1st`
   in the task panel before generating; CTform exports first-order Tri3/Quad4.
   `ElementDimension=From Shape` is accepted for Face/Shell shapes.
- **Resolved:** Create Case enforces one case per document. Materials are stored
   once in a shared case-level **CTform Materials** folder and linked from
   Workpiece/Tool folders. The Assign Material picker imports `materials.json`
   catalogs or selects existing entries; manual creation is the fallback.
- **Resolved:** New Tool, material, and contact IDs are readable slugs with
   numeric suffixes on collisions. IDs remain stable if display labels change.
- **Sample material catalog:** `C:\Users\henri\Desktop\TCC\CTForm Addon\materials.json`
   contains `hot-forging-steel-demo` and `h13-tool-steel-demo`. The hot-forging
   coefficients reuse `cases/benchmarks/ring_6_3_2_mmg2d_hot/material.json`; A is
   converted from MPa to Pa and its Celsius temperature factor is shifted to Kelvin.
   Elastic and thermal values are illustrative estimates, not production
   calibration.
- **Resolved (2026-10-20):** `SmokeTest/loadsteps.json` repeated step ID 1 and
   tool-record ID 1000. `make_load_step` now assigns the next StepId, export
   rejects duplicate StepIds (readiness reports them), and tool records are
   renumbered 1000.. per step. Existing documents with duplicate StepIds must be
   renumbered by hand, then SmokeTest re-exported.
- **SmokeTest package issues to revisit:** The current Core reader does not implement the addon v2 contract, so keep the
   package marked draft and do not run it as a certified case. Its two full-face
   Temperature BCs (600 K then 450 K) are maintained constraints, not initial
   states; confirm that is intended for the smoke scenario.
- **Core scope:** Core has not been modified. Continue treating the v2 reader,
   stable-ID resolution, and runtime integration as separate Core work.

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

The current Core examples still use `upper` and `lower` tool names. The addon
intentionally uses generic named tools instead. Core refactoring to merge tool
identity and per-step tool data by stable name/ID is deferred until the FreeCAD
workflow is more complete.

## Important remaining work

### Highest priority

1. Harden SI-normalized component geometry export and preflight for more CAD shapes;
   current export supports planar profiles/entities understood by the Core ASCII
   DXF parser.
2. Map native FEM convection/radiation fields to Core thermal inputs, including
   ambient temperature.
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
- Do not encode upper/lower/fixture distinctions into the component model.
- Do not expose unrelated FEM solvers in CTform.
- New addon packages use v2 SI values, `materials.json`, and native MSH2 mesh
   references; don't regress to a custom mesh writer or singular new material file.
- Keep native FEM objects as the source of truth and use CTform objects for
  scheduling, mapping, contact, tool motion, and Core integration.
- Treat the JSON files as an export package, not as the primary FreeCAD document
  model.
- Avoid deep investigation of solver calculations; inspect only the Core input,
  preprocessing, runtime setup, and result contracts needed by the addon.
