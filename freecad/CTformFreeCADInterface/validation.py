# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Validation helpers for the CTform 2D model contract."""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ValidationIssue:
    """A single model validation failure."""

    code: str
    message: str
    location: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    """The result of validating one or more model inputs."""

    issues: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.issues


def validate_points(points: Iterable[object], tolerance: float) -> ValidationReport:
    """Ensure every point has a finite Z coordinate within the XY plane."""
    issues: list[ValidationIssue] = []

    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")

    for index, point in enumerate(points):
        location = f"point[{index}]"
        z_value = getattr(point, "z", None)
        if z_value is None:
            issues.append(
                ValidationIssue(
                    "missing_z_coordinate",
                    "The point does not provide a Z coordinate.",
                    location,
                )
            )
            continue

        try:
            z_coordinate = float(z_value)
        except (TypeError, ValueError):
            issues.append(
                ValidationIssue(
                    "invalid_z_coordinate",
                    "The point Z coordinate is not numeric.",
                    location,
                )
            )
            continue

        if abs(z_coordinate) > tolerance:
            issues.append(
                ValidationIssue(
                    "geometry_off_xy_plane",
                    f"The point has Z={z_coordinate:g}, outside the XY plane tolerance.",
                    location,
                )
            )

    return ValidationReport(tuple(issues))


def validate_shape(shape: object, tolerance: float) -> ValidationReport:
    """Validate a FreeCAD-like shape against the CTform planar contract."""
    issues: list[ValidationIssue] = []
    is_null = getattr(shape, "isNull", None)
    if callable(is_null) and is_null():
        return ValidationReport(
            (ValidationIssue("empty_shape", "The selected shape is empty."),)
        )

    solids = getattr(shape, "Solids", ())
    if solids:
        issues.append(
            ValidationIssue(
                "solid_geometry_not_supported",
                "CTform requires planar geometry and does not accept solid volumes.",
            )
        )

    vertices = getattr(shape, "Vertexes", ())
    point_report = validate_points(
        (getattr(vertex, "Point", vertex) for vertex in vertices), tolerance
    )
    issues.extend(point_report.issues)
    return ValidationReport(tuple(issues))
