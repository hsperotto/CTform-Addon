# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""Readable stable identifiers for CTform document objects."""

import re
import unicodedata


def readable_id(label, existing=(), fallback="item"):
    """Create a readable slug, adding a numeric suffix only on collision."""
    text = unicodedata.normalize("NFKD", str(label))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", text)
    base = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    base = base or fallback
    used = {str(value) for value in existing if value}
    if base not in used:
        return base
    suffix = 2
    while f"{base}-{suffix}" in used:
        suffix += 1
    return f"{base}-{suffix}"
