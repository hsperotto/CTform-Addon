<!-- SPDX-License-Identifier: LGPL-3.0-or-later -->
<!-- SPDX-FileNotice: Part of the CTform FreeCAD Interface addon. -->

# Changelog

Versions follow semantic versioning (MAJOR.MINOR.PATCH). The case package schema
(`SCHEMA_VERSION = 2`) is versioned separately; a package-format change is a MAJOR bump.

## [1.0.0] - 2026-10-30

First release aligned with CTform Core v2 and used for the five-punch validation.

### Added

- v2 case package export (`case.json`, `materials.json`, `thermal.json`, `loadsteps.json`,
  MSH2 mesh, ASCII DXF profiles) with readiness checks and `packageStatus`.
- Solver properties: initial workpiece/tool temperature, isothermal preset, external
  Gmsh/MMG paths, Core executable, optional `targetCompression`.
- Tool force motions with a direction vector; `toolId` on every step tool record;
  native thermal conditions (heat flux, convection, radiation, heat source).
- Exact DXF writer (`dxf_writer.py`); AISI 304 1 mm material catalog (Nunes 2025).
- Run CTform Core command: runs `ctform3_cli`, logs, imports step files as a result.
- Tree and toolbar icons for Workpiece, Tool, Load Step and Material.
- Optional per-contact `Penalty` exported as `normal.penalty` (ignored by Core v2 for now).
- Headless FreeCAD probe for the five-punch export.

### Changed

- Unique load step ids and per-step tool record ids.
- Contact interfaces name their master tool explicitly.

### Removed

- Tool `Role` property and `geometry.tools[].role` export (Core derives the side from geometry).
- Workpiece forces are never exported (reported as a readiness error).

### Known limitations

- Core aborts at the first contact of the five-punch case with Coulomb friction (Core task C-M1).
- Thermal properties in the AISI 304 catalog are placeholders.

[1.0.0]: #
