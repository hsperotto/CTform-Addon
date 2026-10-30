# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Run CTform Core on an exported case package and read what it reports.

CTform Core is a separate program: this module only builds its command line,
runs it, and parses its log. It does not link or copy any Core code.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

_WARNING_PREFIX = "[CasePackageV2][WARN]"
_SUMMARY = re.compile(r"\[Timing\]\[Summary\].*?converged=(\d+)")


@dataclass
class CoreRunResult:
    """What a Core run left behind."""

    return_code: int | None
    converged: bool
    warnings: list[str] = field(default_factory=list)
    log_file: Path | None = None
    output_directory: Path | None = None
    steps: list[Path] = field(default_factory=list)
    force_csv: Path | None = None
    timed_out: bool = False

    @property
    def finished(self) -> bool:
        """A run is finished when Core reported convergence, even if the process hung at exit."""
        return self.converged


def build_command(
    core_executable: str | Path,
    case_json: str | Path,
    output_directory: str | Path,
    *,
    gmsh: str | None = None,
    mmg_directory: str | None = None,
    fresh: bool = True,
    extra: Sequence[str] = (),
) -> list[str]:
    """Return the Core command line for a package."""
    command = [str(core_executable)]
    if fresh:
        command.append("--fresh")
    command += ["--case", str(case_json), "--output-dir", str(output_directory)]
    if gmsh:
        command += ["--gmsh", str(gmsh)]
    if mmg_directory:
        command += ["--mmg-dir", str(mmg_directory)]
    command += [str(item) for item in extra]
    return command


def parse_log(text: str) -> tuple[bool, list[str]]:
    """Return (converged, package warnings) from Core's console output."""
    converged = False
    warnings = []
    for line in text.splitlines():
        if line.startswith(_WARNING_PREFIX):
            warnings.append(line[len(_WARNING_PREFIX):].strip())
        match = _SUMMARY.search(line)
        if match:
            converged = match.group(1) == "1"
    return converged, warnings


def collect_outputs(output_directory: str | Path) -> tuple[list[Path], Path | None]:
    """Return the per-step VTK files in step order and the tool-force CSV, if any."""
    folder = Path(output_directory)

    def step_number(path: Path) -> int:
        digits = re.findall(r"\d+", path.stem)
        return int(digits[-1]) if digits else -1

    steps = sorted(folder.glob("case_step_*.vtk"), key=step_number)
    force_csv = folder / "press_force_by_tool.csv"
    return steps, force_csv if force_csv.is_file() else None


def step_times(steps: Sequence[Path], force_csv: str | Path | None) -> list[float]:
    """Return the simulation time of each step file, read from press_force_by_tool.csv.

    Falls back to the step index when the CSV has no row for a step.
    """
    times: dict[int, float] = {}
    if force_csv and Path(force_csv).is_file():
        for line in Path(force_csv).read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            fields = line.split(",")
            if len(fields) >= 2:
                try:
                    times.setdefault(int(fields[0]), float(fields[1]))
                except ValueError:
                    continue
    result = []
    for position, path in enumerate(steps, start=1):
        digits = re.findall(r"\d+", Path(path).stem)
        number = int(digits[-1]) if digits else position
        result.append(times.get(number, float(number)))
    return result


def run_core(
    core_executable: str | Path,
    case_json: str | Path,
    output_directory: str | Path,
    *,
    log_file: str | Path | None = None,
    timeout: float | None = None,
    gmsh: str | None = None,
    mmg_directory: str | Path | None = None,
    extra: Sequence[str] = (),
) -> CoreRunResult:
    """Run Core to completion, logging its console output.

    Core can hang at process exit (Gmsh DLL) after it wrote its results, so a
    timeout does not discard a log that already says converged=1.
    """
    executable = Path(core_executable)
    if not executable.is_file():
        raise FileNotFoundError(f"CTform Core executable not found: {executable}")
    package = Path(case_json)
    if not package.is_file():
        raise FileNotFoundError(f"Case package not found: {package}")
    out = Path(output_directory)
    out.mkdir(parents=True, exist_ok=True)
    log = Path(log_file) if log_file else out / "core_run.log"
    environment = dict(os.environ)
    environment["PATH"] = os.pathsep.join([str(executable.parent), environment.get("PATH", "")])
    command = build_command(
        executable, package, out, gmsh=gmsh,
        mmg_directory=str(mmg_directory) if mmg_directory else None, extra=extra,
    )
    timed_out = False
    with log.open("w", encoding="utf-8", errors="replace") as handle:
        process = subprocess.Popen(
            command, stdout=handle, stderr=subprocess.STDOUT, env=environment,
            cwd=str(package.parent),
        )
        try:
            return_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            return_code = None
    converged, warnings = parse_log(log.read_text(encoding="utf-8", errors="replace"))
    steps, force_csv = collect_outputs(out)
    return CoreRunResult(
        return_code=return_code, converged=converged, warnings=warnings, log_file=log,
        output_directory=out, steps=steps, force_csv=force_csv, timed_out=timed_out,
    )
