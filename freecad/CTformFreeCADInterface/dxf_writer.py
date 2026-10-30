# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Minimal ASCII DXF writer for 2D profiles, in the units of the primitives.

FreeCAD's own DXF exporter writes any arc whose chord is shorter than about
1e-2 length units as a full CIRCLE, which breaks every small corner radius
(for example an R6 mm punch corner exported in metres). This writer emits
LINE, ARC and CIRCLE entities directly, so the profile is exact.

Primitives are plain dicts, so the writer needs no FreeCAD:

    {"type": "LINE", "start": (x, y), "end": (x, y)}
    {"type": "ARC", "center": (x, y), "radius": r, "start_deg": a, "end_deg": b}
    {"type": "CIRCLE", "center": (x, y), "radius": r}
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable, Mapping


def arc_primitive(center, start, middle, end) -> dict:
    """Return the counter-clockwise DXF ARC through three points of a circle.

    DXF arcs always run counter-clockwise from ``start_deg`` to ``end_deg``;
    the edge may run either way, so the middle point decides the direction.
    """
    cx, cy = center

    def angle(point):
        return math.degrees(math.atan2(point[1] - cy, point[0] - cx)) % 360.0

    first, mid, last = angle(start), angle(middle), angle(end)
    if (mid - first) % 360.0 < (last - first) % 360.0:
        start_deg, end_deg = first, last
    else:
        start_deg, end_deg = last, first
    radius = math.hypot(start[0] - cx, start[1] - cy)
    return {"type": "ARC", "center": (cx, cy), "radius": radius,
            "start_deg": start_deg, "end_deg": end_deg}


def polyline_primitives(points: Iterable[tuple[float, float]]) -> list[dict]:
    """Return LINE primitives joining consecutive points."""
    points = list(points)
    return [
        {"type": "LINE", "start": a, "end": b}
        for a, b in zip(points, points[1:])
        if math.hypot(b[0] - a[0], b[1] - a[1]) > 0.0
    ]


def dxf_text(layers: Mapping[str, Iterable[dict]]) -> str:
    """Return an ASCII DXF document with one entity list per layer."""
    pairs: list[tuple[int, str]] = [(0, "SECTION"), (2, "ENTITIES")]
    for layer, primitives in layers.items():
        if not layer or not layer.isascii() or any(c in layer for c in '"\r\n'):
            raise ValueError(f"DXF layer name must be non-empty ASCII text: {layer!r}")
        for item in primitives:
            kind = item["type"]
            pairs += [(0, kind), (8, layer)]
            if kind == "LINE":
                (x1, y1), (x2, y2) = item["start"], item["end"]
                pairs += [(10, _num(x1)), (20, _num(y1)), (30, "0.0"),
                          (11, _num(x2)), (21, _num(y2)), (31, "0.0")]
            elif kind in ("ARC", "CIRCLE"):
                x, y = item["center"]
                pairs += [(10, _num(x)), (20, _num(y)), (30, "0.0"), (40, _num(item["radius"]))]
                if kind == "ARC":
                    pairs += [(50, _num(item["start_deg"])), (51, _num(item["end_deg"]))]
            else:
                raise ValueError(f"Unsupported DXF primitive: {kind}")
    pairs += [(0, "ENDSEC"), (0, "EOF")]
    return "".join(f"{code:>3}\n{value}\n" for code, value in pairs)


def write_dxf(path: str | Path, layers: Mapping[str, Iterable[dict]]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dxf_text(layers), encoding="ascii")
    return output


def _num(value: float) -> str:
    return repr(float(value))
