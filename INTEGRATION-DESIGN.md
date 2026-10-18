# CTform FreeCAD Integration Design

## Purpose

CTform FreeCAD Interface makes FreeCAD the normal user environment for preparing,
meshing, running, and visualizing CTform simulations. CTform Core remains a
separate proprietary application and is not distributed by this addon.

The addon should follow FreeCAD FEM conventions wherever they fit, while keeping
CTform-specific analysis, validation, execution, and result behavior under its
own control.

## Workbench scope

The workbench is displayed as **CTform**.

It may expose selected functionality from existing FreeCAD workbenches:

- Part, Sketcher, and Draft geometry preparation commands.
- Selected Part Design geometry commands where they are useful for planar model
  preparation.
- CTform-owned material creation and assignment tools.
- FEM/Gmsh 2D mesh creation and refinement tools.
- CTform-specific analysis, validation, execution, and result commands.

It must not expose or register unrelated FEM solver commands. In particular, the
CTform workbench should not present CalculiX, Elmer, Z88, Mystran, or other FEM
solver workflows as CTform features.

## Reuse policy

Prefer reusing FreeCAD commands and task panels through stable command registration
where that is appropriate. Do not copy large portions of FEM or Gmsh source into
the addon merely to place commands in a different menu.

CTform wrappers are preferred when a command needs any of the following:

- CTform-specific input validation.
- A stable CTform command name independent of FreeCAD internals.
- A restricted 2D workflow.
- Conversion to a CTform-owned document object.
- A different material, mesh, or result contract.

Optional dependencies such as FEM or Gmsh must be detected gracefully. The CTform
workbench should still load when an optional dependency is unavailable, and should
report a useful message when a dependent command is selected.

## Document model

The initial model should follow FEM's established object organization:

| FreeCAD concept | CTform object |
| --- | --- |
| FEM Analysis container | Dimension-neutral case tree |
| Workpiece folder | Shape/mesh links, shared material reference, and owned contact pairs |
| Tool folder | Shape/mesh links, shared material reference, stable identity, and geometry settings |
| Materials folder | One case-level object per CTform material, reusable across components |
| Material object | CTform constitutive and intrinsic thermal data |
| FEM/Gmsh mesh object | Mesh linked from its Workpiece or Tool folder |
| Constraint-like object | CTform process or boundary condition |
| Solver object | Modeling dimension, formulation, numerical/run/output configuration |
| Result object | CTform result fields and visualization |

CTform-specific objects should use their own type names and properties rather than
pretending to be a generic FEM solver. Native FEM objects may be referenced or
adapted when that preserves compatibility with existing FreeCAD workflows.

The CTform case is a dimension-neutral orchestration object. It links one
Workpiece folder, named Tool folders, a shared Materials folder, and Load Step
folders. Each material object exists once in the case catalog; component folders
link to it alongside their native shape and mesh. Contact pairs are owned by
the Workpiece and each links a Tool. The Solver owns modeling dimension/type,
formulation, contact numerics, thermal/run/output, ALE, and remeshing settings.
No second mechanical-part model is introduced.

## `case.json` as the canonical case model

The existing CTform case workflow is the integration contract. The FreeCAD
case is the editable front end for that contract; it is not a second,
unrelated simulation model. Export should produce the same case package that the
existing `ctform3_api` and `ctform3_cli` workflows consume.

The mapping should remain explicit:

| FreeCAD analysis data | CTform case data |
| --- | --- |
| Analysis name and process | `simulationName`, `process` |
| Solver modeling type and dimension | `simulation.dimension`, `simulation.modelingType` |
| Solver mechanical formulation | `simulation.mechanicalFormulation` |
| Workpiece and Tool folders | `geometry.workpiece`, `geometry.tools[*]` |
| Native geometry references | `geometry.workpiece`, tool files, or exported geometry files |
| FreeCAD FEM/Gmsh mesh object and settings | Authoritative initial `mesh` file plus stable physical-group IDs; Core remesh preserves those IDs |
| Component material links/catalog | `materialsFile` (`materials.json`) plus stable `materialId` references on workpiece/tools/regions |
| Solver contact numerics and Workpiece-owned contact pairs | `contact`, `contactInterfaces` |
| Load-step objects | `loadStepsFile` and `loadsteps.json` |
| Solver output settings | `output` |
| Solver run controls | `run`, `solver`, ALE, and remesh sections |

The FreeCAD document may keep richer links and UI state than `case.json`, but
export must be deterministic and must not require the standalone legacy GUI. A
case directory should be treated as a derived, inspectable artifact of the
FreeCAD case. Opening an existing case should reconstruct or link the
corresponding FreeCAD objects where possible. Existing development documents are
not migrated to the new component tree; they must be rebuilt with the current
Create Workpiece/Create Tool workflow.

New package format uses one integer `schemaVersion` in `case.json` for the whole
package; unversioned cases are legacy v1 and the new writer emits v2. V2 physical
values are unprefixed SI quantities in scientific notation. The UI may display
prefixed SI values and converts at the package boundary. Core may keep its
existing internal unit system, but converts once in its v2 loader.

The case object should therefore expose case-level properties such as the
simulation name, process, modeling type, formulation, case directory, and case
status. Geometry, material, mesh, contact, and load-step details should remain on
their respective native or CTform-specific child objects and be serialized by a
case exporter.

## 2D contract

The first supported CTform model is planar in the XY plane:

- Simulation geometry must lie at `z = 0` within a configurable tolerance.
- CTform operations must reject solids and unsupported non-planar geometry.
- FreeCAD FEM/Gmsh creates the authoritative initial 2D solver mesh; export that
  mesh and its physical-group IDs. Reject volumetric or unsupported elements.
- Exported geometry and mesh coordinates use SI meters; UI display units may use
  prefixes. Sketch X maps to radial Core X and sketch Y maps to axial Core Z.
- Exported nodes must lie on the XY plane after unit conversion and validation.
- Material, boundary-condition, and result references must resolve to planar
  geometry or 2D mesh entities.

When the CTform workbench is activated, it should select an orthographic top view
and fit the model. This is a usability default, not the only enforcement mechanism.
The actual enforcement belongs in CTform validation and mesh/export preflight.

## Core workflow

The first end-to-end workflow should be:

```text
FreeCAD case document
  -> case.json package
  -> ctform3_api / ctform3_cli
  -> results_case/
  -> FreeCAD result objects
The CTform Core connector should operate through an external, versioned interface.
## Golden-path workflow

The primary user journey should take a new user from an empty FreeCAD document to
a small axisymmetric simulation in approximately 15 to 20 minutes. The workbench
should provide all commands needed for this path without requiring the legacy
Python GUI.

The existing `ctform3_api` and Qt GUI are references for behavior and data flow,
not constraints on the final UI. API changes are acceptable when they make the
FreeCAD workflow clearer, more robust, or better aligned with FreeCAD's document
and task-panel model.

### 1. Create a CTform case
### 2. Sketch the workpiece and tools

The user creates the workpiece and any number of tool profiles using FreeCAD
Sketcher or another supported geometry tool. The UI should make the required
axisymmetric coordinate convention visible:

- FreeCAD sketch X maps to CTform radial `r`.
- FreeCAD sketch Y maps to CTform axial `z`.
- Profiles must be planar and suitable for the selected axisymmetric model.

The workbench creates one Workpiece folder and named Tool folders directly from
selected geometry. Tool orientation, motion, and contact participation are
component and process data.

### 3. Configure Solver and contact setup

Before meshing, the user creates a Solver. Modeling dimension/type,
formulation, and execution controls live on that object. The user defines:

- dimension and modeling type
- mechanical formulation
- Workpiece and Tool folders
- contact pairs
- initial gaps or positioning
- friction settings
- symmetry or axis rules
- process direction and constraints

This is the step missing from a simple geometry-to-mesh sequence. It corresponds
to the contact and geometry sections already present in the CTform case format.

### Boundary-condition policy

Boundary conditions are part of the simulation setup and must be visible in the
CTform workbench. FEM provides a useful vocabulary and many reusable task-panel
patterns, but its complete constraint catalog should not be copied into CTform.

The CTform Conditions toolbar reuses FEM task-panel commands and keeps the FEM
condition objects native. A CTform load step is a document group: a condition
becomes step-local when it is dragged into the group or added with **Attach
Selected Condition to Load Step**. Both actions produce the same group child and
export result. Because this analysis is CTform-only, the step group is the
condition's owner after attachment. Conditions left at the analysis root are
global and are inherited by every load step. Detaching returns the condition to
that root. **Clone Load Step** copies its schedule and creates independent native
condition objects that retain their geometry references.

When a step-local condition overlaps a root-global condition on the same
physical group and degree of freedom, the local condition takes precedence and
preflight warns with both condition names. Non-overlapping components and
targets remain active.

The supported forging mapping is deliberately narrower than the full FEM catalog:

| FEM concept | CTform treatment |
| --- | --- |
| Fixed constraint | Native FEM condition; export as a fixed workpiece-region condition or zero-motion state on a named tool. |
| Displacement constraint | Native FEM condition; export as a Workpiece displacement or, on a named Tool folder, as per-step tool velocity. |
| Force constraint | Native FEM condition; supported only on a named Tool folder as axial CTform force control. FEM Y maps to CTform Z; radial FEM X force is not supported by the current force servo. |
| Temperature constraint | Native FEM condition; export as a workpiece thermal condition or tool temperature state. |
| Heat-flux constraint | Native FEM condition; export as a workpiece thermal condition. |
| Body heat source | Native FEM condition; export as CTform heat generation on the workpiece. |
| Pressure constraint | Not exposed yet. Core needs a pressure traction implementation; treating pressure as displacement or a point force would be incorrect. Forging contact already computes interface pressure. |
| FEM contact/tie and other solver-specific constraints | Not exposed. CTform owns its contact-pair model, and these FEM constraints do not map to its rigid-profile contact contract. |

Native FEM condition subelements resolve to physical groups from the assigned
FreeCAD/Gmsh mesh. The exporter writes the group ID and name alongside the same
physical groups embedded in the MSH2 file. A selected subelement with no matching
physical group is rejected instead of being guessed as `All` or a coordinate
selector.

For the first axisymmetric workflow, the minimum boundary-condition set should

- a fixed workpiece region where needed
- prescribed workpiece or tool displacement per load step
- workpiece/tool contact pairs
- friction parameters
- optional initial gap and positioning

Boundary-condition objects should reference the Shape link on the relevant
Workpiece or Tool folder rather than relying only on transient mesh element numbers. The workbench may resolve
The task-panel flow should group conditions by purpose:
Supports and symmetry
Tool motion
Contact and friction
Loads
Thermal conditions (later)
```
### 4. Assign materials

The user assigns a CTform material to each simulation region. New case packages
use a case-scoped `materials.json` catalog; the workpiece, each tool, and future
regions reference catalog entries by stable `materialId` in `case.json`.
`thermal.json` contains case/process thermal state and conditions, not intrinsic
material properties such as conductivity or heat capacity.

CTform material objects are the only material authoring and assignment path in
the workbench. Native FEM material editor commands are not exposed; CTform
constitutive laws and temperature-dependent flow data stay in CTform material
records. Export a deterministic snapshot so runs do not depend on a mutable
global FreeCAD material library.

The first demo may use one workpiece material and a shared tool material, but the
catalog and assignments must support distinct materials per eligible region.

### 5. Generate and inspect the 2D Gmsh mesh

The user chooses mesh parameters and generates the 2D mesh. The workbench should
show the mesh before execution and validate that:

- the workpiece mesh is planar
- the mesh contains only supported 2D elements
- the geometry is within the axisymmetric coordinate convention
- the mesh density is sufficient for the selected model

Tools may remain profile geometry rather than being independently meshed if that
matches the CTform Core contract. The UI should make this distinction explicit
instead of suggesting that every object is a deformable mesh.

The workpiece's assigned `Fem::FemMeshGmsh` is the authoritative initial solver
mesh. Package export uses FreeCAD's `GmshTools` with that object's shape and
settings to save a native Gmsh MSH2 file; it does not serialize FEM elements
itself. The same run refreshes the visible FEM mesh from UNV. Physical group IDs
are pinned from group dimension/name in the generated `.geo`, and MSH coordinates
are scaled from FreeCAD millimeters to SI meters. Core remeshing must preserve
the exported physical-group names and IDs.

Component geometry is exported as plain ASCII DXF profile snapshots because the Core
DXF reader consumes that text format and rejects binary DXF. Workpiece edge
layers preserve FreeCAD `EdgeN` names so they can match Gmsh physical groups;
tool profiles use their named tool-profile layer. Both mesh and DXF snapshots are
scaled to meters and linked from the v2 package.

### 6. Define load steps and simulation fields

The user defines load-step scheduling on Load Step folders and the run
configuration on Solver:

- simulation name
- load-step count and duration
- tool motion or displacement
- target compression or equivalent process control
- solver tolerances and iteration limits
- output frequency

Advanced solver settings should remain hidden behind an advanced section. The
first demo should use sensible CTform defaults.

### 7. Validate and save the case

The workbench runs a preflight check before allowing execution. It reports missing
or invalid geometry, materials, mesh, contacts, load steps, units, and CTform Core
compatibility in the task panel.

Only after a successful preflight should the workbench export or synchronize the
case package (`case.json`, `loadsteps.json`, material data, mesh, and referenced
geometry). This is a development-only clean break; saved documents built with
the previous tree are recreated rather than migrated.

### 8. Run CTform Core

The user starts the simulation from the workbench. Execution must be asynchronous
and provide progress, log output, cancellation, and a clear failure state. This
replaces the current standalone GUI's solver dispatch while preserving its useful
progress behavior.

### 9. Inspect results

The workbench imports or references the generated results and provides a compact
first-result view:

- deformed mesh or displacement field
- force versus displacement
- process diagnostics
- step selection
- solver log and error details

The result objects should remain linked to the case and case directory so the
document can be reopened without losing provenance.

### Golden-path command order

```text
Create CTform Case
  -> Create Solver and select dimension/modeling type
  -> Create Workpiece and Tool Profiles
  -> Create Workpiece-to-Tool Contact Pairs
  -> Choose/import from the shared Materials catalog
  -> Generate 2D Gmsh Mesh
  -> Define Load Steps and Simulation Fields
  -> Validate and Save Case
  -> Run CTform Core
  -> Inspect Results
```

## Current FreeCAD reference points

The public FEM implementation provides useful patterns in:

- `Fem/ObjectsFem.py` for analysis, material, mesh, result, and solver object
  factories.
- `Fem/femcommands/` for command registration.
- `Fem/femtaskpanels/` for task-panel structure, including material and Gmsh mesh
  panels.
- `Fem/InitGui.py` for workbench initialization and deferred imports.

The CTform workbench should reuse the patterns, not expose the FEM solver layer.
Exact command IDs must be checked against the supported FreeCAD version before
being added to the CTform menus.

## Next implementation slice

1. Identify the supported FreeCAD version and installed FEM/Gmsh modules.
2. Record the exact command IDs for planar geometry, material, and Gmsh mesh tools.
3. Create a CTform case object and a 2D preflight validator.
4. Add only the selected commands to CTform menus and toolbars.
5. Define the CTform Core job and result contract before implementing execution.
