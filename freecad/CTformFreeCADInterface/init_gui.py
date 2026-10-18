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
		import Part
		import PartGui
		import Sketcher
		import SketcherGui

		from . import commands

		self.appendToolbar(
			"CTform",
			[
				"CTform_CreateCase",
				"CTform_AssignRole",
				"CTform_CreateLoadStep",
				"CTform_CloneLoadStep",
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
				"CTform_CloneLoadStep",
				"CTform_CreateSolver",
				"CTform_ExportCase",
			],
		)
		self.appendMenu(
			["CTform", "Contact"],
			["CTform_CreateContactPair"],
		)
		self.appendToolbar(
			"CTform Contact",
			["CTform_CreateContactPair"],
		)
		self.appendMenu(
			["CTform", "Materials"],
			[
				"CTform_CreateMaterial",
				"CTform_AssignMaterial",
				"FEM_MaterialEditor",
				"FEM_MaterialSolid",
			],
		)
		self.appendToolbar(
			"CTform Materials",
			[
				"CTform_CreateMaterial",
				"CTform_AssignMaterial",
				"FEM_MaterialEditor",
				"FEM_MaterialSolid",
			],
		)
		self.appendMenu(
			["CTform", "Mesh"],
			[
				"FEM_MeshGmshFromShape",
				"CTform_AssignMesh",
				"FEM_MeshRegion",
				"FEM_MeshGroup",
				"FEM_MeshDisplayInfo",
				"FEM_MeshClear",
			],
		)
		self.appendToolbar(
			"CTform Mesh",
			[
				"FEM_MeshGmshFromShape",
				"CTform_AssignMesh",
				"FEM_MeshRegion",
				"FEM_MeshGroup",
			],
		)
		self.appendMenu(
			["CTform", "Geometry"],
			["Part_MakeFace"],
		)
		self.appendToolbar(
			"CTform Geometry",
			["Sketcher_NewSketch", "Part_MakeFace"],
		)
		self.appendMenu(
			["CTform", "Conditions"],
			[
				"FEM_ConstraintFixed",
				"FEM_ConstraintDisplacement",
				"FEM_ConstraintForce",
				"FEM_ConstraintTemperature",
				"FEM_ConstraintInitialTemperature",
				"FEM_ConstraintHeatflux",
				"FEM_ConstraintBodyHeatSource",
				"CTform_AttachConditionToStep",
				"CTform_DetachConditionFromStep",
			],
		)
		self.appendToolbar(
			"CTform Conditions",
			[
				"FEM_ConstraintFixed",
				"FEM_ConstraintDisplacement",
				"FEM_ConstraintForce",
				"FEM_ConstraintTemperature",
				"FEM_ConstraintInitialTemperature",
				"FEM_ConstraintHeatflux",
				"FEM_ConstraintBodyHeatSource",
				"CTform_AttachConditionToStep",
				"CTform_DetachConditionFromStep",
			],
		)

	def GetClassName(self):
		return "Gui::PythonWorkbench"


Gui.addWorkbench(CTformFreeCADInterfaceWorkbench())
