# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

import os

import FreeCADGui as Gui


_ICON = os.path.join(os.path.dirname(__file__), "resources", "icons", "logo.svg")


class CTformFreeCADInterfaceWorkbench(Gui.Workbench):
	MenuText = "CTform"
	ToolTip = "Prepare and visualize CTform Core simulations"
	Icon = _ICON

	def Initialize(self):
		import Fem
		import FemGui
		import femcommands.commands

		from . import commands

		self.appendToolbar(
			"CTform",
			[
				"CTform_CreateCase",
				"CTform_AssignRole",
				"CTform_CreateLoadStep",
				"CTform_AddMechanicalBC",
				"CTform_AddToolMotion",
				"CTform_CreateSolver",
				"CTform_ExportCase",
			],
		)
		self.appendMenu(
			"CTform",
			[
				"CTform_CreateCase",
				"CTform_AssignRole",
				"CTform_CreateLoadStep",
				"CTform_AddMechanicalBC",
				"CTform_AddToolMotion",
				"CTform_CreateSolver",
				"CTform_ExportCase",
			],
		)
		self.appendMenu(
			["CTform", "Materials"],
			["FEM_MaterialEditor", "FEM_MaterialSolid"],
		)
		self.appendToolbar(
			"CTform Materials",
			["FEM_MaterialEditor", "FEM_MaterialSolid"],
		)
		self.appendMenu(
			["CTform", "Mesh"],
			[
				"FEM_MeshGmshFromShape",
				"FEM_MeshRegion",
				"FEM_MeshGroup",
				"FEM_MeshDisplayInfo",
				"FEM_MeshClear",
			],
		)
		self.appendToolbar(
			"CTform Mesh",
			["FEM_MeshGmshFromShape", "FEM_MeshRegion", "FEM_MeshGroup"],
		)

	def GetClassName(self):
		return "Gui::PythonWorkbench"


Gui.addWorkbench(CTformFreeCADInterfaceWorkbench())
