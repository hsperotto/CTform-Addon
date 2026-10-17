# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

try:
	from FreeCAD import Console
except ImportError:
	Console = None
else:
	Console.PrintLog("freecad/CTformFreeCADInterface/__init__.py\n")
