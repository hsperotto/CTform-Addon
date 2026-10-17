# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Deterministic JSON output with scientific notation for physical floats."""

from __future__ import annotations

import json
import math
from typing import Any


def dumps_si(value: Any, indent: int = 2) -> str:
    """Serialize structured JSON data, writing every float in round-trip exponent form."""
    def encode(item: Any, level: int) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, int):
            return str(item)
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("JSON physical values must be finite")
            return format(item, ".16e")
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=False)
        if isinstance(item, (list, tuple)):
            if not item:
                return "[]"
            pad = " " * (indent * (level + 1))
            close_pad = " " * (indent * level)
            entries = [pad + encode(value, level + 1) for value in item]
            return "[\n" + ",\n".join(entries) + "\n" + close_pad + "]"
        if isinstance(item, dict):
            if not item:
                return "{}"
            pad = " " * (indent * (level + 1))
            close_pad = " " * (indent * level)
            entries = []
            for key, value in item.items():
                if not isinstance(key, str):
                    raise TypeError("JSON object keys must be strings")
                encoded_key = json.dumps(key, ensure_ascii=False)
                entries.append(pad + encoded_key + ": " + encode(value, level + 1))
            return "{\n" + ",\n".join(entries) + "\n" + close_pad + "}"
        raise TypeError(f"Object of type {type(item).__name__} is not JSON serializable")

    return encode(value, 0)
