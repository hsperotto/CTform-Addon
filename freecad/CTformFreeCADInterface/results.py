# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Read CTform Core results: forces, punch stroke, field catalog, maxima per step.

Pure Python (standard library only, no FreeCAD, no VTK), so it runs under the
unit tests. The FreeCAD panel (``results_panel.py``) uses it for what the FEM
post objects do not give: force versus stroke and the maximum of a field with
its location. See ``docs/RESULTS-VIEWER-PLAN.md``.

Core writes, per converged step, ``case_step_<n>.vtk`` (legacy ASCII VTK) and one
``press_force_by_tool.csv`` (``Step,Time,Tool,Force``). The meridian plane is X
(radius) and Z (axial); lengths in the VTK are millimetres.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

TOOL_ELEMENT_TYPE = 10  # `element_type` of the cells that belong to a rigid tool

# (VTK name, label, unit, association). Order follows the thesis comparison (plan section 3).
FIELD_CATALOG = (
    ("Plastic_Strain", "Equivalent plastic strain", "-", "cell"),
    ("VonMises_Stress", "Von Mises stress", "MPa", "cell"),
    ("Pressure", "Mean stress (sm = (srr+szz+stt)/3, tension positive)", "MPa", "cell"),
    ("Displacement", "Displacement", "mm", "point"),
    ("Temperature", "Temperature", "K", "cell"),
    ("ContactPressure", "Contact pressure", "MPa", "point"),
    ("ContactSticking", "Contact sticking", "-", "point"),
)


@dataclass
class ForceSeries:
    """Force of one tool at each written step."""

    tool: str
    steps: list[int] = field(default_factory=list)
    times: list[float] = field(default_factory=list)
    forces: list[float] = field(default_factory=list)


def read_force_csv(path: str | Path) -> dict[str, ForceSeries]:
    """Return ``{tool name: ForceSeries}`` from ``press_force_by_tool.csv``.

    Uses ``Force_Total`` (normal + friction, the real vertical tool reaction; Core 4825fb9 and later)
    when the column exists, otherwise ``Force`` (older CSVs: normal component only).
    """
    series: dict[str, ForceSeries] = {}
    with open(path, newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            try:
                step = int(row["Step"])
                time = float(row["Time"])
                force = float(row["Force_Total"] if row.get("Force_Total") not in (None, "") else row["Force"])
            except (KeyError, TypeError, ValueError):
                continue
            item = series.setdefault(row["Tool"], ForceSeries(row["Tool"]))
            item.steps.append(step)
            item.times.append(time)
            item.forces.append(force)
    return series


def punch_velocity_profile(loadsteps: dict, tool_id: str = "punch") -> list[tuple[float, float, float]]:
    """Return ``(start, end, vz in mm/s)`` for each load step that moves ``tool_id``.

    ``loadsteps.json`` stores velocities in m/s. Force-controlled records are skipped.
    """
    profile = []
    for step in loadsteps.get("loadSteps", []):
        for record in step.get("tools", []):
            if record.get("toolId") == tool_id and "vz" in record and record.get("active", True):
                profile.append((float(step["startTime"]), float(step["endTime"]), float(record["vz"]) * 1000.0))
    return sorted(profile)


def punch_displacement(profile: Sequence[tuple[float, float, float]], time: float) -> float:
    """Downward punch travel in mm (positive) at ``time``, from constant velocities per step."""
    travel = 0.0
    for start, end, vz in profile:
        if time <= start:
            break
        travel += -vz * (min(time, end) - start)
    return travel


def stroke_from_contact(displacements: Sequence[float], initial_gap: float = 0.0) -> list[float]:
    """Stroke measured from the punch's first contact: displacement minus the initial gap.

    This is the rule approved for the thesis (plan section 3). Values before contact
    are clipped at zero.
    """
    return [max(0.0, value - initial_gap) for value in displacements]


def first_contact_displacement(
    displacements: Sequence[float], forces: Sequence[float], fraction: float = 0.01
) -> float | None:
    """Cross-check: displacement where the punch force first exceeds ``fraction`` of its peak."""
    peak = max((abs(value) for value in forces), default=0.0)
    if peak <= 0.0:
        return None
    for displacement, force in zip(displacements, forces):
        if abs(force) > fraction * peak:
            return displacement
    return None


@dataclass
class StepRecord:
    number: int
    time: float
    stroke: float  # mm from first contact
    forces: dict[str, float]


def load_run(output_directory: str | Path, case_directory: str | Path | None = None,
             initial_gap: float = 0.0, punch_id: str = "punch",
             punch_name: str = "Punch") -> tuple[list[StepRecord], dict]:
    """Return the per-step records of a run and a dictionary of notes.

    ``case_directory`` holds ``loadsteps.json`` (punch velocity); without it the stroke is
    None-free but unknown, so it is reported as the step time (see ``notes["stroke"]``).
    """
    output = Path(output_directory)
    forces = read_force_csv(output / "press_force_by_tool.csv")
    notes: dict = {"stroke": "unknown", "crossCheck": None}
    punch = forces.get(punch_name) or next(iter(forces.values()), None)
    if punch is None:
        return [], notes
    profile = []
    if case_directory is not None and (Path(case_directory) / "loadsteps.json").is_file():
        profile = punch_velocity_profile(
            json.loads((Path(case_directory) / "loadsteps.json").read_text(encoding="utf-8")), punch_id
        )
    if profile:
        displacements = [punch_displacement(profile, time) for time in punch.times]
        strokes = stroke_from_contact(displacements, initial_gap)
        notes["stroke"] = "displacement minus initial gap"
        crossing = first_contact_displacement(displacements, punch.forces)
        if crossing is not None:
            notes["crossCheck"] = {"firstContactDisplacement": crossing, "initialGap": initial_gap}
    else:
        strokes = list(punch.times)
    records = []
    for index, step in enumerate(punch.steps):
        records.append(StepRecord(
            number=step, time=punch.times[index], stroke=strokes[index],
            forces={name: series.forces[index] for name, series in forces.items()
                    if index < len(series.forces) and series.steps[index] == step},
        ))
    return records, notes


@dataclass
class FieldMaximum:
    value: float
    radius: float  # mm
    axial: float   # mm
    element: int | None = None


class VtkStep:
    """Minimal legacy-ASCII VTK reader for Core's step files (requested arrays only)."""

    def __init__(self, path: str | Path, arrays: Iterable[str] = ()):
        self.path = Path(path)
        self.wanted = set(arrays) | {"element_type"}
        self.points: list[tuple[float, float, float]] = []
        self.cells: list[list[int]] = []
        self.cell_data: dict[str, list[float]] = {}
        self.point_data: dict[str, list[float]] = {}
        self.array_names: dict[str, list[str]] = {"point": [], "cell": []}
        self._read()

    def _read(self) -> None:
        section = None      # "POINTS", "CELLS", or an association "point"/"cell"
        association = None
        current = None
        remaining = 0
        with open(self.path, encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("LOOKUP_TABLE"):
                    continue
                head = line.split(None, 1)[0]
                if head[0].isalpha() and head.lower() not in ("nan", "inf"):
                    words = line.split()
                    key = words[0]
                    current = None
                    section = None
                    if key == "POINTS":
                        section, remaining = "POINTS", int(words[1])
                    elif key == "CELLS":
                        section, remaining = "CELLS", int(words[1])
                    elif key == "POINT_DATA":
                        association = "point"
                    elif key == "CELL_DATA":
                        association = "cell"
                    elif key in ("SCALARS", "VECTORS", "TENSORS") and association:
                        name = words[1]
                        self.array_names[association].append(name)
                        if key == "SCALARS" and name in self.wanted:
                            current = (self.point_data if association == "point" else self.cell_data
                                       ).setdefault(name, [])
                        elif key == "VECTORS" and name in self.wanted:
                            current = (self.point_data if association == "point" else self.cell_data
                                       ).setdefault(name, [])
                    continue
                if line.startswith("LOOKUP_TABLE"):
                    continue
                if section == "POINTS":
                    values = line.split()
                    for i in range(0, len(values) - 2, 3):
                        self.points.append((float(values[i]), float(values[i + 1]), float(values[i + 2])))
                elif section == "CELLS":
                    values = [int(v) for v in line.split()]
                    self.cells.append(values[1:])
                elif current is not None:
                    values = line.split()
                    if len(values) == 1:
                        current.append(float(values[0]))
                    else:  # a vector: keep its magnitude
                        current.append(sum(float(v) ** 2 for v in values) ** 0.5)

    def workpiece_cells(self) -> list[int]:
        types = self.cell_data.get("element_type")
        if types is None:
            return list(range(len(self.cells)))
        return [i for i, kind in enumerate(types) if int(kind) != TOOL_ELEMENT_TYPE]

    def cell_centroid(self, index: int) -> tuple[float, float]:
        nodes = [self.points[n] for n in self.cells[index]]
        return (sum(p[0] for p in nodes) / len(nodes), sum(p[2] for p in nodes) / len(nodes))

    def maximum(self, name: str) -> FieldMaximum | None:
        """Maximum of a cell or point field over the workpiece, with its location."""
        if name in self.cell_data:
            candidates = self.workpiece_cells()
            data = self.cell_data[name]
            if not candidates or len(data) <= max(candidates):
                return None
            best = max(candidates, key=lambda i: data[i])
            radius, axial = self.cell_centroid(best)
            return FieldMaximum(data[best], radius, axial, best)
        if name in self.point_data:
            used = {n for i in self.workpiece_cells() for n in self.cells[i]}
            data = self.point_data[name]
            if not used:
                return None
            best = max(used, key=lambda n: data[n])
            return FieldMaximum(data[best], self.points[best][0], self.points[best][2], None)
        return None


def step_maxima(files: Sequence[str | Path], names: Sequence[str] = ("Plastic_Strain", "VonMises_Stress")
                ) -> list[dict[str, FieldMaximum | None]]:
    """Maximum of each named field in each step file (Nunes Figs. 36, 39, 41 comparison)."""
    out = []
    for path in files:
        step = VtkStep(path, names)
        out.append({name: step.maximum(name) for name in names})
    return out


def step_number(path: str | Path) -> int:
    digits = re.findall(r"\d+", Path(path).stem)
    return int(digits[-1]) if digits else -1


def _barycentric(point, a, b, c):
    """Barycentric weights of ``point`` in the triangle (a, b, c), all (r, z)."""
    d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(d) < 1e-30:
        return None
    w1 = ((b[1] - c[1]) * (point[0] - c[0]) + (c[0] - b[0]) * (point[1] - c[1])) / d
    w2 = ((c[1] - a[1]) * (point[0] - c[0]) + (a[0] - c[0]) * (point[1] - c[1])) / d
    return w1, w2, 1.0 - w1 - w2


def probe(step: VtkStep, name: str, radius: float, axial: float, tolerance: float = 1e-9) -> float | None:
    """Value of a cell or point field at (radius, axial) in the workpiece, or None outside it.

    A cell field returns the value of the cell that contains the point; a point field is
    interpolated linearly. Cells are triangles or quads (a quad is two triangles).
    """
    point = (radius, axial)
    for index in step.workpiece_cells():
        nodes = step.cells[index]
        coords = [(step.points[n][0], step.points[n][2]) for n in nodes]
        if len(nodes) == 3:
            triangles = [(0, 1, 2)]
        elif len(nodes) == 4:
            triangles = [(0, 1, 2), (0, 2, 3)]
        else:
            triangles = []
        for t in triangles:
            weights = _barycentric(point, coords[t[0]], coords[t[1]], coords[t[2]])
            if weights is None or min(weights) < -tolerance:
                continue
            if name in step.cell_data:
                return step.cell_data[name][index]
            if name in step.point_data:
                return sum(w * step.point_data[name][nodes[i]] for w, i in zip(weights, t))
            return None
    return None


def line_profile(step: VtkStep, name: str, start: tuple[float, float], end: tuple[float, float],
                 samples: int = 100) -> list[tuple[float, float | None]]:
    """``(distance along the line, value)`` at ``samples`` points; value is None outside the sheet."""
    samples = max(2, samples)
    length = ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
    out = []
    for i in range(samples):
        fraction = i / (samples - 1)
        r = start[0] + fraction * (end[0] - start[0])
        z = start[1] + fraction * (end[1] - start[1])
        out.append((fraction * length, probe(step, name, r, z, tolerance=1e-6)))
    return out


class ResultsSession:
    """One Core run, ready for the panel: step files, forces, stroke, lazily read fields.

    ``output`` is the folder with ``case_step_*.vtk`` and ``press_force_by_tool.csv``;
    ``case`` is the folder with ``loadsteps.json``. Step files are read on demand and the
    last few are kept (a field read is slow for large meshes, ~2 s for 87,000 points).
    """

    DEFAULT_FIELDS = ("Plastic_Strain", "VonMises_Stress", "Pressure")
    ALL_FIELDS = tuple(entry[0] for entry in FIELD_CATALOG)

    def __init__(self, output: str | Path, case: str | Path | None = None, initial_gap: float = 0.0):
        self.output = Path(output)
        self.files = sorted(self.output.glob("case_step_*.vtk"), key=step_number)
        self.records, self.notes = load_run(self.output, case, initial_gap)
        by_number = {record.number: record for record in self.records}
        # one record per step file; a step file without a CSV row keeps its number only
        self.steps = [by_number.get(step_number(path), StepRecord(step_number(path), float("nan"),
                                                                  float("nan"), {})) for path in self.files]
        self._maxima: dict[tuple[int, str], FieldMaximum | None] = {}
        self._cache: dict[int, VtkStep] = {}
        self._cache_order: list[int] = []

    def label(self, index: int) -> str:
        step = self.steps[index]
        return f"step {step.number}  |  t = {step.time:.4g} s  |  stroke = {step.stroke:.3g} mm"

    def nearest_step(self, stroke: float) -> int:
        """Index of the step whose stroke is closest to ``stroke`` (a click on the force plot)."""
        return min(range(len(self.steps)), key=lambda i: abs(self.steps[i].stroke - stroke))

    def vtk(self, index: int, names: Sequence[str] = ALL_FIELDS) -> VtkStep:
        if index not in self._cache:
            self._cache[index] = VtkStep(self.files[index], names)
            self._cache_order.append(index)
            while len(self._cache_order) > 3:
                self._cache.pop(self._cache_order.pop(0), None)
        return self._cache[index]

    def maximum(self, index: int, name: str) -> FieldMaximum | None:
        key = (index, name)
        if key not in self._maxima:
            self._maxima[key] = self.vtk(index).maximum(name)
        return self._maxima[key]

    def all_maxima(self, names: Sequence[str] = DEFAULT_FIELDS[:2], progress=None) -> list[dict]:
        out = []
        for index in range(len(self.files)):
            out.append({name: self.maximum(index, name) for name in names})
            if progress is not None and progress(index + 1, len(self.files)) is False:
                break
        return out

    def force_curves(self) -> dict[str, tuple[list[float], list[float]]]:
        """``{tool: (stroke, force)}`` for every tool in the CSV."""
        tools = sorted({name for step in self.steps for name in step.forces})
        return {
            tool: ([s.stroke for s in self.steps if tool in s.forces],
                   [s.forces[tool] for s in self.steps if tool in s.forces])
            for tool in tools
        }


def write_summary_csv(path: str | Path, records: Sequence[StepRecord],
                      maxima: Sequence[dict[str, FieldMaximum | None]] = ()) -> None:
    """One row per step: time, stroke, tool forces, and the maximum (value, r, z) of each field."""
    tools = sorted({name for record in records for name in record.forces})
    names = sorted({name for item in maxima for name in item})
    header = ["Step", "Time_s", "Stroke_mm"] + [f"Force_{t}" for t in tools]
    for name in names:
        header += [f"Max_{name}", f"Max_{name}_r_mm", f"Max_{name}_z_mm"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for index, record in enumerate(records):
            row = [record.number, record.time, record.stroke] + [record.forces.get(t, "") for t in tools]
            for name in names:
                found = maxima[index].get(name) if index < len(maxima) else None
                row += [found.value, found.radius, found.axial] if found else ["", "", ""]
            writer.writerow(row)
