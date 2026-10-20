# Agent guide

Read `STATUS.md` first, then `DEVELOPMENT-CONTEXT.md` (design rules) and
`Core-Refactor.md` (Core contract). Naming rules are in `IDENTITY.md`.

## Tests
- Run: `python -m unittest discover -s tests`. pytest is not installed.
- All tests must pass before you merge or hand off.

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
