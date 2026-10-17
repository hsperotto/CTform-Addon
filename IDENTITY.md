# CTform Identity and Naming Guide

## Product family

**CTform** is the product family and the public name of the forging simulation solution.

The simulation engine is a separate proprietary application:

- **CTform Core**: the executable that performs simulation, preparation, meshing, solving, and other computational work.
- **CTform Core API**: the programming interface exposed by the core, if one is provided separately.
- **CTform FreeCAD Interface**: the FreeCAD addon in this repository. It connects FreeCAD to CTform Core and provides a FreeCAD-native user interface.

The preferred addon name is **CTform FreeCAD Interface**. Avoid calling it simply "CTform", because that blurs the boundary between the FreeCAD integration and the simulation software.

## Technical identifiers

Use these identifiers consistently unless a platform requires a different spelling:

| Purpose | Recommended identifier |
| --- | --- |
| Product family | `CTform` |
| Simulation executable | `CTform Core` / `CTform-core` |
| FreeCAD addon display name | `CTform FreeCAD Interface` |
| FreeCAD workbench display name | `CTform` |
| Python package and FreeCAD module | `CTformFreeCADInterface` |
| FreeCAD workbench class | `CTformFreeCADInterfaceWorkbench` |
| Repository | `CTform-FreeCAD-Interface` |
| Python distribution name | `ctform-freecad-interface` |

Display names may contain spaces. Python modules, executable names, and distribution names must follow their platform conventions.

## What to call each part

Use **addon** for the complete installable FreeCAD integration package.

Use **workbench** for the FreeCAD GUI integration registered with FreeCAD. Its FreeCAD display name is **CTform**. The workbench contains menus, toolbars, commands, task panels, and preferences.

Use **interface layer** or **integration layer** for code that translates between FreeCAD objects and CTform Core requests and results.

Use **adapter** for a focused translation component, such as a mesh adapter, material adapter, or result adapter.

Use **connector** for process and communication code that starts, locates, or communicates with CTform Core.

Use **integration API** only for a deliberate, documented programming interface used by other code. Use **binding** only for code that directly exposes a C or C++ API to Python. Do not call the whole addon an API or a binding.

Use **command** for a FreeCAD command exposed through the GUI, such as preparing a model or importing results.

Use **task panel** for an interactive FreeCAD panel that gathers inputs or displays progress.

Use **core** only for the proprietary simulation application and its implementation. The addon must not be described as the core solver.

## Naming and licensing boundary

CTform FreeCAD Interface is an integration product. It does not replace, reimplement, or include CTform Core unless a future distribution explicitly says so.

Documentation and user-facing error messages should say when CTform Core is required and where it must be obtained. The addon should treat the core as an external dependency and should not imply that installing the FreeCAD addon grants rights to use or redistribute the simulation software.

Keep these concerns separate:

- The addon source license applies to CTform FreeCAD Interface source code.
- CTform Core licensing is outside the scope of this repository because CTform Core is not distributed with the addon.
- Third-party and branding licenses apply to icons, logos, fonts, and other assets.

The current addon distribution contains no CTform Core executable, library, runtime, or SDK. If that changes in a future distribution, its licensing and packaging must be reviewed separately.

## Language to prefer

Prefer:

- "CTform FreeCAD Interface connects FreeCAD to CTform Core."
- "The addon sends preparation data to CTform Core."
- "CTform Core must be installed separately."
- "FreeCAD provides the modeling and visualization environment."

Avoid:

- "The CTform addon runs the solver" when referring to the interface alone.
- "CTform is a FreeCAD workbench" when referring to the entire product family.
- "The addon includes CTform Core" unless the distribution really includes the relevant component and its license permits that statement.
- "CTform API" when the code is only launching an executable or using a private adapter.

## Future module layout

A likely Python layout is:

- `workbench/`: FreeCAD workbench registration and GUI setup.
- `commands/`: FreeCAD command implementations.
- `panels/`: task panels and dialogs.
- `interface/`: FreeCAD-to-core translation and orchestration.
- `connector/`: process launching and communication with CTform Core.
- `adapters/`: material, mesh, geometry, and result conversions.
- `preferences/`: FreeCAD preference definitions and accessors.
- `resources/`: icons, documentation, and other static assets.

This is a vocabulary and ownership guide, not a requirement to create every directory immediately.
