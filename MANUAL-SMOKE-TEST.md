# CTform FreeCAD Manual Smoke Test

Use this checklist after changes to workbench registration, FEM condition handling,
load steps, geometry references, or case export. It validates the FreeCAD GUI and
export adapter; it does not validate a CTform Core solve.

## Test Record

- Date:
- Tester:
- FreeCAD version:
- Add-on revision:
- CTform Core revision, if relevant:
- Result: Pass / Fail / Blocked
- Notes or screenshot paths:

## Preconditions

- FreeCAD 1.1 starts with the CTform addon installed and enabled.
- Gmsh is installed and configured for FreeCAD FEM.
- Use a new document and a temporary export directory.
- Confirm the workbench contains the CTform, Geometry, Mesh, Materials, and
  Conditions toolbars/menus.
- Do not start a CTform solver. The addon now emits the v2 package and Gmsh mesh,
  but Core's v2 catalog/SI/physical-group reader is not implemented yet.

## Scenario A: Forging Model, Materials, Mesh, and Conditions

1. Switch to the CTform workbench and create a new document.
2. Run **Create CTform Case**.
   - Pass: a native FEM analysis named `CTform Case` is created and becomes the
     active FEM analysis.
  Run **Create CTform Solver** and set `Dimension` to `2D`, `ModelingType` to
  `axisymmetric`, and `MechanicalFormulation` to `flow`.
  - Pass: these properties are on the Solver object, not CTform Case Settings.
3. Use **Geometry > New Sketch** to create a Sketcher profile on the XY plane.
   Draw a closed workpiece section on positive sketch X. CTform maps sketch X to
   radial position and sketch Y to axial position.
4. Create a planar face from the closed workpiece sketch. Create two more closed
   profiles/faces: an upper punch above the workpiece and a lower die below it.
   Keep the tool profiles separate from the workpiece.
5. Select the workpiece face and run **Create Workpiece**. Select the upper and
   lower faces and run **Create Tool**, naming them `UpperPunch` and `LowerDie`.
   - Pass: the analysis tree contains one Workpiece folder and two separately
     named Tool folders, each linked to its source shape.
6. Select the Workpiece folder and run **Create CTform Material**. Create
   `ForgingSteel` with `HenselSpittel`; create `ToolSteel` on `UpperPunch`, then
   select `LowerDie` and the existing ToolSteel object and run **Assign CTform
   Material**.
   - Pass: each component has a material link; both materials have stable IDs
     and appear once each in `materials.json`.
   - Native FEM Solid Material may still be created as a reference/preset, but it
     is not the CTform constitutive material.
7. Select the workpiece face and run **Mesh From Shape by Gmsh**. Use the task
   panel to generate a mesh.
   - Pass: a non-empty FEM mesh is created for the workpiece face, and the mesh
     is planar with 2D elements. If FreeCAD generates a volume mesh or cannot
     mesh the face, record that as a blocker; do not proceed as if it were a
     valid CTform 2D mesh. Select the Workpiece folder and mesh together and run
     **Assign FEM Mesh to CTform Component**.
   - Pass: the Workpiece folder's `Mesh` link points to this mesh object and the
     mesh appears under that folder in the tree.
8. Select the Workpiece folder and each Tool folder in turn with **Create CTform
   Contact Pair** to create a visible workpiece-to-tool pair. Set distinct pair
   names and review friction/contact properties.
   - Pass: each pair appears under the Workpiece folder, links that Workpiece
     and its Tool, and exports in `contactInterfaces`.
9. Create two CTform load steps. Set Step 1 time to 0-1 and Step 2 time to 1-2.
   - Pass: both values are editable. Record whether `StartTime` appears before
     `EndTime`; the property editor currently displays `EndTime` first and this
     remains a UI issue.
10. Create the native FEM **Fixed** condition first. In its task panel, click
   **Add**, then select the lower die geometry in the 3D view/tree and confirm
   the selection in the task panel. Do not preselect the geometry before
   invoking the command. Drag the created condition from the analysis root onto
   Step 1.
   - Pass: the condition becomes a child of Step 1, its `MechanicalBCs` property
     reflects that child, and it exports as zero tool velocity on `LowerDie`.
     It is no longer a direct child of the analysis root.
11. Create a native FEM **Displacement** condition first. Click **Add**, select
    the upper punch geometry, prescribe motion along FreeCAD FEM Y (the sketch
    axial direction), and confirm. Select the condition and Step 1 together and
    run **Attach Selected Condition to Load Step**.
    - Pass: it becomes a child of Step 1 just as in the drag test, and exports as
      tool velocity along CTform Z. Sketch X / FEM X maps to CTform radial X;
      sketch Y / FEM Y maps to CTform axial Z; FEM Z is out of plane and
      unsupported.
12. Create a native FEM **Temperature** condition. Click **Add** and select the
    whole workpiece face if a uniform prescribed temperature on the whole domain
    is intended; attach it to Step 1.
    - Pass: it becomes a child of Step 1 and the target exports as the face's
      physical-group ID/name from the assigned Gmsh mesh.
      Do not use this as a substitute for initial temperature unless that
      time-dependent Dirichlet condition is intended.
    - Separately create native FEM **Initial Temperature** conditions: leave one
      at the analysis root and attach another to Step 1.
    - Pass: the root condition appears in `thermal.json` under
      `initialTemperatureConditions` with `scope: global`; the step condition
      appears in Step 1's `initialTemperatureConditions` with `scope: step`.
      Neither appears in `thermalBCs`; selected geometry resolves to the same
      Gmsh physical-group IDs as other native FEM conditions.
      A condition selected on a named tool targets its stable `toolId`, not a
      workpiece physical group.
13. Create a native FEM **Body Heat Source** condition. Click **Add** and select
    the whole workpiece face; attach it to Step 2.
    - Pass: it becomes a child of Step 2 and exports as `HeatGeneration` over the
  selected face physical group.
14. If testing **Heat Flux**, click **Add** and select a workpiece boundary edge,
    not the whole face. Attach it to Step 2.
    - Pass: the edge's Gmsh physical-group ID/name is preserved. Heat flux is a
      boundary-surface condition; whole-domain heating belongs to Body Heat
      Source.
15. Optionally create a native FEM **Force** condition on the upper tool by
    clicking **Add** and selecting the tool. Attach it to Step 2.
    - Pass: it exports as force-controlled tool motion. Workpiece Force is not
      supported by Core and must not be attached.
16. Select Step 1 and run **Clone Load Step**.
    - Pass: the clone has a unique step ID, copies the source schedule and
      active state, and contains distinct copies of Step 1's conditions that
      still reference the same geometry. Editing a cloned condition does not
      change the source condition.
    - Pass: the cloned step is registered under the CTform analysis and in the
      case's `LoadSteps` list. Use this command instead of relying on generic
      FreeCAD copy/paste to create CTform steps.
17. Select the whole-workpiece Temperature condition and Step 1, then run
    **Detach Condition from Load Step**.
    - Pass: the condition moves to the CTform analysis root, disappears from
      Step 1's group/category list, and is exported once in `thermal.json` as a
      global condition inherited by all steps.
18. Export the case package to the temporary directory.
    - Pass: `case.json`, `materials.json`, `thermal.json`, and `loadsteps.json`
      are written without a FreeCAD error dialog; `case.json` has
      `schemaVersion: 2` and unprefixed SI units.
    - Pass: `case.json.mesh.file` points to the package-local Gmsh `.msh` created
      from the assigned FEM/Gmsh object. `mesh.physicalGroups` contains the group
      names/IDs, and MSH node coordinates are in meters. The FEM preview remains
      visible after export.
    - Pass: `geometry/workpiece.dxf` and each named tool DXF are readable ASCII
      DXF profile snapshots with meter coordinates; workpiece DXF edge layers
      match the physical-group names used by the Gmsh mesh.
    - Pass: both named tools appear in `case.json`; all three load steps appear in
      `loadsteps.json` with their expected tool and BC data.
    - Pass: face/edge conditions reference the same physical-group IDs listed in
      `case.json.mesh.physicalGroups`.
    - Pass: `materials.json` contains each unique material once, with Workpiece
      and Tool components referring to it by `materialId`; `thermal.json`
      contains process thermal state/conditions but no intrinsic conductivity
      or heat-capacity tables.
    - Pass: fixed `LowerDie` exports with zero velocity; `UpperPunch` exports
      with the expected axial velocity; root-global mechanical conditions carry
      `scope: global`, while local conditions carry `scope: step`.
    - Pass: invalid or unexportable component geometry leaves the package marked
      `draft` with a readiness issue; do not invoke Core.
19. Save the FreeCAD document, close it, reopen it, and repeat the export.
    - Pass: component links, step links, native condition objects, and exported
      values remain intact after restore; tool IDs, material IDs, and contact
      pairs are unchanged, with no proxy serialization errors or cycles.

## Scenario B: Selection and Unsupported-Input Guardrails

1. With only a load step selected, check **Attach Selected Condition to Load
   Step**.
   - Pass: it is disabled.
2. Select a FEM condition and a load step from different documents, if available.
   - Pass: it is disabled or refuses the attachment; no cross-document link is
     created.
3. Select a condition already in a step with that same step.
  - Pass: **Detach Condition from Load Step** is enabled; **Attach Selected
    Condition to Load Step** is idempotent.
4. Create a FEM Force condition on the workpiece. Select it with a load step.
   - Pass: attachment is unavailable. Workpiece force loads are not currently
     supported by Core's mechanical BC application.
5. Create a root-global Fixed condition on one boundary and a step-local
  Displacement condition on that same physical group/axis; export.
  - Pass: the local record has `overridesGlobal: true` and the warning names
    both conditions and the affected load step.
6. Create a FEM condition on a subelement from geometry that is not included in
   the assigned workpiece Gmsh mesh, attach it, and export.
   - Pass: export reports that the subelement has no matching Gmsh physical group
     instead of silently broadening its target. Do not run Core with the rejected
     package.
7. Confirm the CTform custom **Add Mechanical Boundary Condition** and
   **Add Tool Motion** actions are absent from CTform menus, toolbars, and
   command search.
   - Pass: native FEM condition actions and the CTform attach action are the
     only condition-creation workflow.
8. Confirm pressure and FEM contact/tie are not presented as supported CTform
   Conditions actions.
   - Pass: they remain omitted until Core has compatible solver semantics;
     CTform's contact model remains authoritative for forging interface contact.

## Regression Notes

- Native FEM constraints remain the source of truth. Moving one into a CTform
  step makes the step its document-group parent and defines when it applies.
- Dragging a condition into a step and using **Attach Selected Condition to Load
  Step** must produce identical group membership and exported JSON.
- Root mechanical/thermal boundary conditions are global; root initial-temperature
  conditions are exported once as case initial state. Detaching from a step
  returns the condition to the analysis root.
- **Clone Load Step** creates new child condition objects; generic FreeCAD
  copy/paste is not the supported cloning path because it does not register the
  clone in CTform's step list or assign a fresh step ID.
- FEM condition targets must resolve to a physical group exported with the
  assigned Gmsh mesh. Gmsh group names/IDs should be stable for the same named
  groups across repeated exports.
- Tool displacement and force conditions are translated to CTform per-step tool
  data; the old CTform custom condition and tool-motion creation commands should
  not reappear in the workflow.
- Native FEM Initial Temperature exports as separate case- or step-scoped
  initial-state data, not as a persistent thermal boundary condition. The
  existing Workpiece/Tool default temperatures remain available in `thermal.json`.
- Core's thermal BC schema includes `ambientTemperature` for convection/radiation.
  It also consumes film coefficient and emissivity. Ambient heat exchange is
  therefore modeled in Core through convection/radiation thermal BC data, not as
  a single global ambient-temperature switch. The current FreeCAD adapter does
  not yet map native FEM convection/radiation fields; record this as blocked
  until that native-condition mapping is implemented.
- Core currently reads tool identities from `case.json` and per-step tool state
  from `loadsteps.json`; verify/fix its merge-by-name behavior before attempting
  a solve with the upper and lower tools together.
- Root-global conditions apply to every step; local conditions take precedence
  on overlapping targets/DOFs and should produce an export warning.
- The Gmsh `.msh` is generated from the assigned FEM Gmsh object's shape/settings
  and is exported in meters. Core must preserve physical-group names through its
  initial mesh import and later remeshing.
- Do not run Core with the v2 package until Core supports the catalog, SI units,
  MSH physical groups, ASCII DXF component snapshots, and local/global scopes. Full
  preflight and Core compatibility remain pending.
