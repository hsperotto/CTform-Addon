# CTform Core Refactor Brief

**Purpose:** Working contract for AI agents and developers refactoring CTform Core to consume cases authored by the CTform FreeCAD Interface. This is a living document. Add evidence-backed assumptions, decisions, blockers, and resolutions here whenever they arise.

**Core source:** `C:\Users\henri\Desktop\TCC\CTForm`

**Addon source:** `freecad/CTformFreeCADInterface/`

## Mission and Boundaries

FreeCAD is the authoring environment. CTform Core owns forging physics, constitutive evaluation, contact, solve control, and result generation. The CTform analysis is CTform-only; this is not a goal of making it interchangeable with CalculiX, Elmer, or another FEM solver.

Reuse native FreeCAD geometry, materials, meshes, and constraint task panels when useful. Core must remain independent of FreeCAD Python. The addon serializes a portable, inspectable case package and invokes Core through `ctform3_api` or `ctform3_cli`.

## Accepted Working Assumptions

These are the agreed direction for addon work and future Core changes. Do not reopen them without new evidence that makes the model unworkable. Implementation details that are explicitly listed as open remain open.

1. **Materials are a case-scoped catalog.** New packages use `materials.json`, containing named material records with stable IDs. Workpiece, tools, and future regions refer to those IDs from `case.json`.
2. **Material properties belong to materials.** Constitutive models/curves, elasticity, density, conductivity, specific heat, and other intrinsic thermomechanical data belong in material records, not `thermal.json`.
3. **Thermal files describe process state and conditions.** Initial temperatures, ambient/environment conditions, thermal boundary conditions, plastic/friction heat settings, and thermal-contact controls belong in `thermal.json` or the appropriate load step. Initial temperature is state, not an intrinsic material property.
4. **CTform material data is authoritative.** Native FEM/standard materials can seed or display compatible scalar properties, but cannot replace CTform constitutive data. Export a deterministic snapshot; do not depend on a live mutable global FreeCAD library at solve time.
5. **Legacy material files remain readable during migration.** Existing singular `material.json` inputs normalize to a one-entry default catalog. New addon work targets the catalog contract.
6. **Keep the files readable.** Prefer one case-local `materials.json` over one file per geometry object or a remote database. Use named fields, explicit units, simple references, and concise metadata.
7. **FreeCAD FEM/Gmsh mesh is authoritative for the initial solve mesh.** Core imports that mesh and its physical groups; later Core remeshing is allowed only if it preserves stable group identity and provenance.
8. **Physical groups are the geometry/BC/contact/material-region contract.** Export stable group IDs and names rather than labels, coordinate guesses, or transient subelement indices.
9. **Tool identity is defined once.** `case.json` owns each named tool's geometry and material reference; step records reference that tool ID and contain only process state/motion.
10. **Contact pairs are visible in the addon.** The addon presents explicit named pairs. A simple obvious default pair may be auto-created, but must be editable and serialized; Core changes should reuse the existing contact pipeline where possible.
11. **Local conditions override global conditions.** Analysis-root conditions apply to every step; a step-local condition for the same target/DOF takes precedence and triggers a warning.
12. **New package values use SI units and scientific notation.** UI may use convenient SI prefixes; export converts to the declared canonical units. IDs, enumerations, and integer counts remain ordinary integers.
13. **One package schema version governs all files.** `case.json` carries an integer `schemaVersion`; unversioned packages are legacy v1, new packages write v2, and sidecars follow that package version. Unsupported future versions fail clearly.

## Current Addon Model

| Addon object/data | Intended Core meaning |
| --- | --- |
| `Fem::FemAnalysis` | One CTform case container |
| CTform case settings | Case/process, modeling type, files, contact, run, and output settings |
| Role assignment | Native geometry link with `workpiece` or named `tool` role |
| Role material link | Material ID/reference for that workpiece/tool; not yet exported |
| FEM/Gmsh mesh | Core workpiece mesh plus stable named regions/boundaries; export incomplete |
| Load-step group | Step schedule and its local condition children |
| FEM condition at analysis root | Global condition inherited by every exported step |
| FEM condition inside a load-step group | Condition active only in that step |

Drag-and-drop into a load-step group and **Attach Selected Condition to Load Step** have the same result. **Detach Condition from Load Step** returns the condition to the analysis root. **Clone Load Step** copies its schedule and creates independent native condition objects while retaining geometry references.

FreeCAD group membership is exclusive: moving a condition into a step removes it from the analysis root. This is intended for the CTform-only analysis. Root conditions are expanded into every step during addon export. Conflicts between root-global and step-local conditions still need explicit validation.

## Package Contract

Current Core inputs are `case.json`, singular `material.json`, `thermal.json`, `loadsteps.json`, and referenced geometry/mesh files. The observed path is:

```text
CaseConfigLoader
  -> CaseConfig
  -> PreprocessorBuilder
  -> load steps / runtime steps / contact schedule
  -> RuntimeBoundaryConditionSetup resolves targets
  -> SimulationAssembly / ThermoMechanicalCoupler
```

### New package direction

`case.json` references `materials.json` and puts a `materialId` on each physical workpiece/tool/region. It references the initial Gmsh MSH2 mesh and ASCII DXF snapshots for the workpiece and tools. DXF is text (binary DXF is unsupported by Core); workpiece edge layers match the MSH physical names. `materials.json` defines each material once. `thermal.json` contains process thermal state and conditions, not conductivity or heat-capacity tables. `loadsteps.json` contains per-step conditions and tool state/motion.

### Simple schema-version and unit policy

- `case.json` is the package manifest and contains one integer `schemaVersion`.
  That version governs `case.json` and every referenced sidecar; do not version
  each JSON file independently in the first iteration.
- No `schemaVersion` means legacy v1. The v1 reader preserves legacy field and
  unit interpretations, then normalizes to Core's current in-memory model.
- The first catalog/physical-group/SI package is v2. The v2 writer always emits
  `schemaVersion: 2`; v2 requires the `materialsFile`, stable material/physical
  group IDs, and the canonical SI unit declaration below.
- Core supports v1 and v2 readers during migration. Unsupported versions greater
  than the highest implemented version fail with a clear diagnostic. Do not
  silently downgrade, rewrite, or reinterpret a package.
- Increment the integer version only for an incompatible package-format change.
  Add optional backward-compatible fields without incrementing it. Document each
  version's exact differences here and test each supported reader.
- V2 physical quantities use unprefixed SI units in files: `m`, `kg`, `s`, `K`,
  `Pa`, `J`, `W`, with derived units such as `kg/m3`, `J/(kg K)`, `W/(m K)`, and
  `W/(m2 K)`. Dimensionless quantities use `1`. The `units` object in `case.json`
  declares this contract; all sidecars inherit it.
- The UI may display convenient SI prefixes such as mm, MPa, kN, or kJ. Convert
  at the export/import boundary. Serialize physical floating-point values using
  scientific notation with enough significant digits for round-trip fidelity
  (for example `1.0000000000000000e-03`). IDs, enums, booleans, and integer
  counts remain their natural JSON types.
- Core may retain its current internal units initially; the v2 loader converts
  SI file values once into internal units. Do not scatter conversions through
  solvers or material laws.

Illustrative `case.json` fragment:

```json
{
  "schemaVersion": 2,
  "units": {
    "length": "m",
    "time": "s",
    "temperature": "K",
    "stress": "Pa",
    "strain": "1",
    "strainRate": "1/s"
  },
  "materialsFile": "materials.json",
  "geometry": {
    "dxf": {"format": "ascii", "lengthUnit": "m", "coordinateMap": {"r": "x", "z": "y"}, "workpieceLayerMap": {"Edge1": "Edge1"}},
    "workpiece": {"file": "geometry/workpiece.dxf", "materialId": "steel-42crmo4"},
    "tools": [
      {"id": "tool-upper-id", "name": "UpperPunch", "file": "geometry/tools/tool-upper-id.dxf", "materialId": "h13-tool-steel", "type": "rigid", "toolLayer": "ToolProfile"},
      {"id": "tool-lower-id", "name": "LowerDie", "file": "geometry/tools/tool-lower-id.dxf", "materialId": "h13-tool-steel", "type": "rigid", "toolLayer": "ToolProfile"}
    ]
  },
  "mesh": {"file": "mesh/workpiece.msh", "lengthUnit": "m", "physicalGroups": []}
}
```

Illustrative `materials.json` fragment; Hensel-Spittel parameters below are
serialization placeholders, not a calibrated material. Exact fields and
coefficient units require the checks below:

```json
{
  "materials": [
    {
      "id": "steel-42crmo4",
      "name": "42CrMo4 forging steel",
      "constitutive": {
        "model": "HenselSpittel",
        "parameters": {"A": 1.0000000000000000e+09, "m1": -1.0000000000000000e-03, "m2": -1.0000000000000000e-01, "m3": 1.0000000000000000e-01, "m4": -1.0000000000000000e-02}
      },
      "elastic": {"youngModulusTable": [], "poissonRatio": 2.9000000000000000e-01},
      "thermal": {"density": 7.8000000000000000e+03, "conductivityTable": [], "specificHeatTable": []}
    }
  ]
}
```

This is a target for readability, not permission to implement unverified material
coefficients or silently reinterpret legacy cases. V2 physical values in examples
and exported packages use scientific notation; integer identifiers/counts remain
integers.

### Ownership by file

- `case.json`: case identity, simulation type/formulation, geometry/tool identity and material references, mesh references, contact setup, run/output settings, sidecar references.
- `materials.json`: CTform constitutive model and parameters or measured flow curves; elastic properties; density; conductivity, heat capacity, expansion, and other intrinsic material data.
- `thermal.json`: default and native FEM initial-temperature conditions; ambient conditions and thermal BCs; thermal plastic/friction efficiencies; contact heat-transfer/process controls.
- `loadsteps.json`: time window/increments; step-local mechanical/thermal BCs and initial-temperature conditions; per-step tool motion and thermal state.

Native FEM `ConstraintInitialTemperature` is an initial-state condition, distinct
from `ConstraintTemperature`, which remains a thermal boundary condition. Case
conditions are written once in `thermal.json`; step-owned initial conditions are
written under that step in `loadsteps.json`.
Role-level temperatures provide defaults; an explicit condition overrides its
selected physical-group target, or a named tool by stable `toolId`. A step-owned
condition initializes that target at the start of that step and does not hold it
at the specified temperature afterward.

Tool temperature/motion can vary by process step; tool identity and its intrinsic material reference do not. Do not copy material data into every step.

## Addon/Core Decisions Needed for a Runnable Package

These are remaining product-contract decisions between the current FreeCAD case
model and a trustworthy, runnable Core package. Accepted assumptions are marked
**Settled**; open items still need evidence or a decision.

| Priority | Decision | Status | Recommended direction |
| --- | --- | --- | --- |
| P0 | Geometry and mesh authority | Settled | FreeCAD FEM/Gmsh mesh is the initial solver mesh; Core imports it and its groups. Core remeshing may follow while preserving group IDs. |
| P0 | Stable region/boundary identity | Settled | Use stable physical-group IDs/names for regions, boundaries, BCs, contact, and materials. Reject unresolved IDs. |
| P0 | Material catalog/assignment | Settled | Case-local `materials.json`; stable `materialId` on workpiece/tools/regions; intrinsic properties live in material records. |
| P0 | Tool identity/state merge | Settled | Define geometry/material once in `case.json`; per-step state references that tool ID and never creates a second tool. |
| P0 | Contact-pair authoring | Settled direction | Show explicit named pairs in the addon; allow a visible editable default for the simple case. Reuse Core contact structures where possible. |
| P0 | Boundary-condition scope | Settled | Root conditions are global; step-local conditions override matching root conditions and produce a warning. |
| P1 | Units and coordinates | Settled | V2 files use unprefixed SI values in scientific notation; UI may use prefixes. V1 inputs preserve legacy interpretation and normalize at the boundary. |
| P1 | Load-step time rules | Open | Define overlap/gap rules, inactive-step behavior, and increment semantics before relying on `duration / increments`. |
| P1 | Package versioning/paths | Partly settled | One integer package `schemaVersion` in `case.json`; unversioned is v1, new writer emits v2, all sidecars follow it. Path/checksum policy remains open. |
| P1 | Readiness/defaults | Open | Distinguish draft, exportable, and runnable cases. State which fields require user input versus safe defaults. |
| P2 | Run/results contract | Open | Define structured errors, progress, cancellation, result manifest, and mapping back to FreeCAD regions/materials/steps. |

### P0 Decision Notes

**Geometry and mesh authority (settled):** FreeCAD's FEM/Gmsh mesh is the
authoritative initial solver mesh because it is already generated by Gmsh and
visible to the user. Export the actual mesh and physical-group membership. Core
must import supported 2D element types and reject unsupported element types or
missing groups. Core adaptive remeshing may replace the discretization later but
must preserve named physical-group identity, region/material assignment, and
result provenance. The addon reuses FreeCAD `GmshTools` to save MSH2 in the same
run that refreshes the FEM preview from UNV; it does not serialize mesh elements
itself. It scales MSH node coordinates to SI meters and pins physical tags from
group dimension/name. Never treat a separate mesh as identical to the visible
FreeCAD mesh.

**Role geometry snapshots (settled):** the addon writes ASCII DXF profile
snapshots for the workpiece and each rigid tool. It uses FreeCAD's
`importDXF.export` with spline flattening/linear-wire output; Core's parser
accepts the resulting ASCII LINE/ARC/LWPOLYLINE/CIRCLE/ELLIPSE entities and
rejects binary DXF. Workpiece `EdgeN` DXF layers match MSH physical-group names;
tools use a named tool-profile layer. Geometry is transformed to world placement
and scaled to SI meters before export. Keep explicit case offsets additive and
avoid applying any placement twice.

**Tool identity and motion (settled):** addon roles are `workpiece` and
arbitrarily named `tool`. `case.json` defines tool ID, geometry, and material
once. `loadsteps.json` references the tool ID for motion and thermal/process
state; it does not define a second tool. Core currently builds tools from both
`geometry.tools` and per-step `tools`; refactor that path to merge by ID. A tool
without an explicit step motion is fixed for that step unless a later process
state rule says otherwise.

**Contact pairs (settled direction):** roles do not define which surfaces contact
or master/slave semantics. The addon owns visible named contact-pair objects and
serializes target/master physical-group IDs, friction, thermal interface data,
and gap. A simple obvious pair may be auto-created for a workpiece and tools, but
it must be visible and editable. Keep Core changes minimal by adapting these
objects to its existing `contactInterfaces` path before changing contact physics.

**Boundary conditions (settled):** resolve targets through stable physical
groups. Root conditions apply to every step; a local condition on the same target
and DOF overrides the global condition and emits a warning naming both objects.
Non-conflicting components/targets remain active. Do not map unsupported
pressure, force, or thermal conditions to a different quantity.

### Other Decisions to Record

- Supported CAD object types, geometry healing/flattening rules, and rejection
  criteria for non-planar or unsupported profiles.
- Whether tool placement comes from profile coordinates, case offsets, or both;
  prevent applying transforms twice.
- Material requirements for rigid contact tools versus thermally active or
  deformable tools.
- Whether convection/radiation is global, per exposed boundary, or both.
- Which checks gate export and which gate actual execution.
- How edits invalidate exported packages, prepared caches, restart checkpoints,
  and results so stale artifacts cannot appear current.

## Verified Core Material Findings

- `MaterialFactory` currently creates one global material from a `type`, positional `params`, and `elasticModulusTable`.
- Existing analytic types include Hensel-Spittel, Hollomon, Norton-Hoff, elastoplastic J2, and elastic isotropic.
- `HenselSpittelFlowLaw` evaluates stress as a function of equivalent plastic strain, strain rate, and temperature; its current coefficient vector is positional (`A,m1,m2,m3,m4`, with optional `E,nu`). It returns derivatives used by the nonlinear tangent.
- An elastic-modulus temperature table is attached to the material object.
- The current material contract does not accept arbitrary measured flow-stress families over strain, rate, and temperature.
- `CaseConfigLoader` reads thermal conductivity and heat-capacity tables from `thermal.json`; `SimulationAssembly` forwards them to `ThermoMechanicalCoupler`.
- Tools have separate thermal property fields in geometry/tool/thermal/load-step structures. These duplicate or fragment material-level data.
- The addon already has a `Material` link on role assignments but does not serialize it. FEM's material UI provides common scalar properties, not CTform constitutive laws or hot-flow curve families.

Relevant Core sources to inspect when changing these contracts:

- `src/CTF3/IO/CaseConfigLoader.cpp`
- `include/CTF3/IO/CaseConfig.h`
- `src/CTF3/IO/MaterialFactory.cpp`
- `include/CTF3/Materials/FlowStressLaws.h`
- `src/CTF3/Materials/HenselSpittelMaterial.cpp`
- `src/CTF3/Pre/PreprocessorBuilder.cpp`
- `src/CTF3/Pre/TargetResolver.cpp`
- `src/CTF3/Run/RuntimeBoundaryConditionSetup.cpp`
- `src/CTF3/Run/SimulationAssembly.cpp`
- `src/CTF3/Pre/CasePrepared.cpp`

## Open Technical Questions (Do Not Guess)

1. **Temperature convention:** V2 input temperature is Kelvin. Existing v1 initial temperatures include `1173.15`; modulus tables include `20, 200, ...`; some thermal tables include `293.15`-style values. Determine each legacy field's convention and whether Hensel-Spittel coefficients were calibrated for Celsius or Kelvin. The v1 adapter must preserve legacy meaning; the v2 law receives Kelvin.
2. **Heat-capacity basis:** FEM `SpecificHeat` is mass-specific. Some Core example heat-capacity values are around `2.4e6`, suggesting volumetric heat capacity. Trace the heat equation and benchmark before converting or renaming.
3. **Conductivity and stress units:** V2 file values use SI: conductivity `W/(m K)`, stress/pressure `Pa`, and length `m`. Determine legacy units and conversion locations at the input boundary; Core may use other internal units after one loader conversion.
4. **Flow-curve representation:** Choose regular tensor grid or a set of curves indexed by temperature and strain rate. Define interpolation, extrapolation, sparse slices, duplicate points, valid ranges, and required derivatives before implementation.
5. **Tool material requirements:** Decide whether every rigid tool must reference a material or whether a named, explicit default is permitted. Never silently use the workpiece material.
6. **Region assignment:** Decide how multiple materials in one workpiece mesh map to stable physical groups and how those IDs survive remesh/restart.
7. **Material conflict behavior:** If a FEM material seeds a CTform material, define one-way import/snapshot or explicit override precedence. Never maintain two equally authoritative editable values.
8. **Tool merge:** Core currently builds tool definitions from `geometry.tools` and per-step `tools`. Merge per-step state with geometry identity by stable ID/name; reject conflicting duplicate identities.
9. **Geometry targets:** Current Core target strings include `All`, top/bottom aliases, and Z selectors; unknown strings currently fall back to all nodes. New packages need stable physical-group IDs and must reject unknown IDs rather than broaden the target.

## Refactor Sequence

### Phase 0: Characterize legacy behavior

- Build a case matrix for each current material model and thermal mode.
- Record units and meanings from equations/source and calibration provenance, not from field names.
- Add loader tests for legacy parameter counts/defaults, material sidecars, and thermal tables.
- Save baseline benchmark outputs and define acceptable comparison tolerances.

### Phase 1: Version and normalize

- Add a schema version and normalize all inputs to canonical internal units at the loader boundary.
- Continue reading old singular `material.json` as one implicit default material.
- Convert legacy conductivity/heat-capacity tables from `thermal.json` into that internal record without changing old-case behavior.
- When a new catalog and legacy values conflict, report the conflict. Do not silently pick a winner.

### Phase 2: Catalog and assignments

- Add `materialsFile`/`materials.json`, stable material IDs, and material references on workpiece/tools/regions.
- Resolve every reference before preprocessing and fail clearly on missing/duplicate IDs.
- Use the same resolved material data for mechanical constitutive and thermal calculations on a region.
- Include the catalog and referenced material data in prepared-cache fingerprints and restart provenance.

### Phase 3: Constitutive models and curves

- Replace UI-facing positional vectors with named parameters while retaining a legacy adapter.
- Add a table-backed `IFlowStressLaw` for measured data.
- Finite-difference-check returned derivatives at interior points, table boundaries, rate cutoffs, and temperature boundaries.
- Add explicit diagnostics for out-of-range strain, rate, and temperature.

### Phase 4: Geometry/process integration

- Export stable physical-group/region IDs and map conditions/material assignments through those IDs.
- Keep root conditions global and load-step children local; validate conflicting definitions on overlapping regions/DOFs.
- Merge tool geometry/material identity with step motion/thermal state by stable ID/name.

### Phase 5: API and results

- Keep Core independent of FreeCAD; expose a stable versioned API/CLI contract.
- Return structured preflight errors, execution state/progress, cancellation result, and result manifest.
- Preserve material/geometry/mesh provenance so results can be mapped back to FreeCAD objects.

## Acceptance Criteria

- Existing cases still parse and reproduce reference behavior within agreed tolerances.
- New cases can assign distinct materials to the workpiece and tools/regions without hand-editing JSON.
- New material data is self-contained and readable in `materials.json`; intrinsic thermal properties are not duplicated in `thermal.json` or each load step.
- Material IDs remain stable through preprocessing, remesh, restart, and result export.
- Flow stress uses declared units and temperature/rate/strain behavior; tangent checks pass.
- Unknown material and geometry IDs fail validation; they never silently select a default or `All`.
- Core remains callable through `ctform3_api` and `ctform3_cli` with legacy compatibility.

## Assumption and Problem Log Procedure

Whenever an agent/developer makes an assumption, discovers a Core limitation, changes a schema, or resolves an integration mismatch:

1. Add or update a dated entry in this log before ending the task.
2. Label each point `Observed`, `Assumption`, `Decision`, `Open`, or `Resolved`.
3. Include evidence (source symbol/file, representative case, test, or runtime result) and distinguish fact from inference.
4. State the effect on addon/Core contracts, migration, and tests.
5. If contradicted, mark earlier entries superseded; do not erase the reasoning.
6. Update the relevant contract section above when the finding changes implementation.

## Current Assumption and Problem Log

### 2026-10-17: Case-scoped material catalog

- **Observed:** Core currently has one global material configuration with positional parameters and a separate elastic-modulus table. Thermal conductivity and heat-capacity tables are read from `thermal.json`. Evidence: `CaseConfigLoader.cpp`, `CaseConfig.h`, `MaterialFactory.cpp`, `SimulationAssembly.cpp`.
- **Observed:** The addon can link a native FEM material to a role, but does not serialize the link. Evidence: addon `roles.py` and `case_export.py`.
- **Assumption accepted for addon development:** new cases use a case-scoped `materials.json` catalog, with stable `materialId` references from workpiece/tools/regions. Core will be refactored to consume this model. Intrinsic properties move to catalog records; process thermal state and BCs remain in `thermal.json`/`loadsteps.json`.
- **Open:** exact schema fields, legacy conversion, Celsius/Kelvin convention, heat-capacity basis, conductivity/stress units, measured-curve interpolation, and tool material requirements. These details do not reopen the accepted catalog/reference direction.
- **Next:** trace equations and data provenance, then specify unit-normalized migration tests before implementing the new parser/writer.

### 2026-10-17: Load-step condition ownership

- **Observed:** FreeCAD group membership is exclusive. Moving a native condition into a CTform step removes it from the analysis root.
- **Decision:** analysis-root conditions apply to every exported step; step-group children apply only to that step. Detach returns a condition to the root; clone creates independent native conditions and retains geometry references.
- **Open:** conflict policy for overlapping global and step-local conditions. Add explicit validation and tests before relying on precedence.

### 2026-10-17: Mesh, physical groups, units, and package versioning

- **Decision:** the FreeCAD FEM/Gmsh mesh is the authoritative initial solver
mesh. Core imports that mesh; later Core remeshing may change elements but must
preserve physical-group identity and result/material/BC mappings.
- **Decision:** named physical groups with stable exported IDs are the reference
for regions, boundaries, material assignment, contact, and boundary conditions.
- **Decision:** contact pairs are visible addon objects. A simple default may be
auto-created, but remains editable and serialized; refactor Core parsing to reuse
the current contact pipeline where possible rather than replace contact physics.
- **Decision:** local step conditions override matching root-global conditions;
emit a warning that identifies both conditions and the overlapping group/DOF.
- **Decision:** V2 package values use unprefixed SI quantities in scientific
notation. The UI may use prefixes; Core converts once at its input boundary.
- **Decision:** one integer `schemaVersion` in `case.json` versions the whole
package. Missing version is legacy v1; new format is v2; sidecars inherit that
version; reject unsupported future versions. V1 compatibility remains required.
- **Observed:** FreeCAD 1.1 `GmshTools` writes a temporary UNV for the FEM preview;
the addon appends an MSH2 `Save` to the same generated `.geo` and refreshes the
preview from UNV. A FreeCAD integration probe confirmed MSH2 physical names,
deterministic dimension/name-derived tags, and mm-to-m scaling.
- **Open:** whether Core's adaptive remesher preserves these group IDs/names and
material/BC mappings; compatibility of all FEM/Gmsh group types in forging
fixtures; and validation of overlapping physical membership. Test those in Core
before enabling execution.

### 2026-10-17: Addon v2 integration slice

- **Implemented in addon:** schema-v2 SI manifest and scientific-notation JSON;
case-local CTform material catalog with role IDs; ASCII DXF role snapshots;
process-only thermal sidecar; visible contact-pair objects; GmshTools-produced
MSH2 and physical-group metadata; stable tool IDs; physical-group condition
targets; root-global/step-local scopes with local override warnings; export
readiness issues.
- **Validated:** 26 addon Python tests; syntax and diagnostics; FreeCAD 1.1
material-property conversion probe; FreeCAD/Gmsh full package-export probe with
MSH2 physical groups and SI node coordinates.
- **Not implemented in Core:** v2 catalog/SI reader, physical-group ID targeting,
scope precedence, and stable tool-state merge. Core source was not changed in
this addon-only stage; v2 packages are marked draft and must not be run yet.
- **Remaining addon blocker:** complete geometry/material/contact preflight,
semantic workpiece layer mapping for arbitrary topology, and validation of
tool placement/offset interaction before a case can be marked runnable.
