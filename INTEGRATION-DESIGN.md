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
- FEM material creation and editing tools.
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

| FreeCAD concept | CTform role |
| --- | --- |
| FEM Analysis container | CTform case |
| Material object | CTform material definition or adapter |
| FEM/Gmsh mesh object | CTform mesh input, after validation |
| Constraint-like object | CTform process or boundary condition |
| Solver object | CTform Core job and execution object |
| Result object | CTform result fields and visualization |

CTform-specific objects should use their own type names and properties rather than
pretending to be a generic FEM solver. Native FEM objects may be referenced or
adapted when that preserves compatibility with existing FreeCAD workflows.

The case object is an orchestration container following the FEM document
model. Geometry, mesh, and material remain separate FreeCAD document objects and
may be placed in the native FEM analysis group using the standard FreeCAD
mechanisms. The
addon must not create a second mechanical-part object model just to duplicate
those properties.

CTform adds role-assignment objects that link existing document objects to
simulation semantics such as `workpiece` and `tool`. A role
assignment is metadata and an export mapping, not a replacement for the linked
Part, Sketcher, FEM material, or mesh object. Simulation-wide settings remain on
the case.

## `case.json` as the canonical case model

The existing CTform case workflow is the integration contract. The FreeCAD
case is the editable front end for that contract; it is not a second,
unrelated simulation model. Export should produce the same case package that the
existing `ctform3_api` and `ctform3_cli` workflows consume.

The mapping should remain explicit:

| FreeCAD analysis data | CTform case data |
| --- | --- |
| Analysis name and process | `simulationName`, `process` |
| Axisymmetric or plane-strain selection | `simulation.modelingType` |
| Mechanical formulation | `simulation.mechanicalFormulation` |
| Role assignments | `geometry.workpiece`, `geometry.tools[*].role` |
| Native geometry references | `geometry.workpiece`, tool files, or exported geometry files |
| FEM/Gmsh mesh object and settings | `mesh` and its referenced mesh file |
| Material objects | `materialFile` and material data |
| Contact and friction objects | `contact`, `contactInterfaces` |
| Load-step objects | `loadStepsFile` and `loadsteps.json` |
| Output settings | `output` |
| Run controls | `run`, `solver`, and related case sections |

The FreeCAD document may keep richer links and UI state than `case.json`, but
export must be deterministic and must not require the standalone legacy GUI. A
case directory should be treated as a derived, inspectable artifact of the
FreeCAD case. Opening an existing case should reconstruct or link the
corresponding FreeCAD objects where possible.

The case object should therefore expose case-level properties such as the
simulation name, process, modeling type, formulation, case directory, and case
status. Geometry, material, mesh, contact, and load-step details should remain on
their respective native or CTform-specific child objects and be serialized by a
case exporter.

## 2D contract

The first supported CTform model is planar in the XY plane:

- Simulation geometry must lie at `z = 0` within a configurable tolerance.
- CTform operations must reject solids and unsupported non-planar geometry.
- Mesh generation must produce a 2D mesh and reject volumetric elements.
- Exported nodes must have zero Z coordinates after validation.
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

The workbench should assign only `workpiece` and `tool` roles, with a separate
user-defined tool name. Tool orientation, motion, and contact participation are
configuration data, not role names.

### 3. Define the model and contact setup

Before meshing, the user defines the simulation-specific setup:

- axisymmetric modeling mode
- workpiece and tool roles
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

Candidate FEM constraints should be reused or wrapped only when their meaning is
clear in a CTform forging model:

| FEM concept | CTform treatment |
| --- | --- |
| Fixed constraint | Wrap as a CTform support or fixed-region condition. |
| Displacement constraint | Wrap as prescribed tool/workpiece motion. |
| Force constraint | Reuse only for a genuine applied process load. |
| Pressure constraint | Reuse only where the CTform process model accepts pressure. |
| Temperature constraint | Keep for a later thermal workflow. |
For the first axisymmetric workflow, the minimum boundary-condition set should

- a fixed or constrained tool region
- prescribed tool motion or displacement per load step
- workpiece/tool contact pairs
- friction parameters
- optional initial gap and positioning

Boundary-condition objects should reference stable FreeCAD geometry roles rather
than relying only on transient mesh element numbers. The workbench may resolve
The task-panel flow should group conditions by purpose:
Supports and symmetry
Tool motion
Contact and friction
Loads
Thermal conditions (later)
```
### 4. Assign materials

The user assigns a material to each simulation region. The material task panel
should expose only properties required by CTform Core, while retaining a clear
mapping to FreeCAD/FEM material concepts where useful.

For the first demo, one workpiece material and tool material defaults are enough.
The data model must still support separate materials for each eligible region.

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

### 6. Define load steps and simulation fields

The user defines the minimum run configuration:

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
geometry).

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
  -> Select Axisymmetric
  -> Create Workpiece and Tool Profiles
  -> Assign Roles and Contact Setup
  -> Assign Materials
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
