# Agent guide

Read `STATUS.md` first, then `DEVELOPMENT-CONTEXT.md` (design rules) and
`Core-Refactor.md` (Core contract). Naming rules are in `IDENTITY.md`.
For how the code fits together (module and object graphs, export and run flows,
recipes, review findings) read `docs/DEVELOPER-GUIDE.md`.

## Tests
- Run: `python -m unittest discover -s tests`. pytest is not installed.
- All tests must pass before you merge or hand off.

- FreeCAD probe (needs FreeCADCmd and FreeCAD's gmsh; not run by unittest):
  `set CTFORM_PROBE_OUT=<folder>` then
  `FreeCADCmd.exe tests/freecad/probe_five_punch_export.py`. Optional switches: `CTFORM_PROBE_PUNCH_GAP` (mm), `CTFORM_PROBE_MU`
  (0 exports friction `none`), `CTFORM_PROBE_NO_HOLDER`, `CTFORM_PROBE_NO_AXIS`,
  `CTFORM_PROBE_INCREMENTS`, `CTFORM_PROBE_FORMULATION` (`flow` or `displacement`),
  `CTFORM_PROBE_MATERIAL` (catalog material name), `CTFORM_PROBE_QUAD=1` (recombined mesh),
  `CTFORM_PROBE_ALGO2D` (Gmsh 2D algorithm, e.g. `Quasi-structured Quad`, which gives pure Quad4),
  `CTFORM_PROBE_STRUCTURED=1` (transfinite, recombined Quad4 sheet: 720 elements for the 45 x 1 mm probe). It builds a
  five-punch-style case (placeholder nose height) and prints what the export
  contains.

## Workflow
- FreeCAD loads this directory directly, so keep the checked-out branch on a clean `main`.
- Do half-finished work on an `agent/<topic>` branch and merge only when tests pass.
- Package code is in `freecad/CTformFreeCADInterface/`.

## Export rules
- Load step `StepId` values must be unique; export rejects duplicates.
- Tool record `id` values are unique within a step (numbered from 1000). Core
  v2 matches step tools by `toolId` (falling back to name with a warning), so
  every step tool record must carry a non-empty `toolId`.

## Handoff
- Update `STATUS.md` (and `DEVELOPMENT-CONTEXT.md` for design changes) before finishing.
