# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Part of the CTform FreeCAD Interface addon.

"""CTform Results panel: force vs stroke, field, step, maximum, probe, line plot.

Qt widget over a ``results.ResultsSession`` and the FEM post pipeline that
``RunCoreCommand`` creates. The pipeline stays the single source of what the 3D
view shows; the panel only sets its ``Frame`` and the view's ``Field``. Numbers
that the post objects do not give (force vs stroke, the maximum and where it is,
probe and line values) come from ``results.py``. Plan: docs/RESULTS-VIEWER-PLAN.md.
"""

from __future__ import annotations

import math
from pathlib import Path

import FreeCAD as App
from PySide import QtCore, QtWidgets

from . import results

_FIELD_NAMES = {entry[0]: entry for entry in results.FIELD_CATALOG}


def _unit(name):
    unit = _FIELD_NAMES[name][2]
    return "" if unit == "-" else f" {unit}"


def _canvas(figure):
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

    return FigureCanvasQTAgg(figure)


class ResultsPanel(QtWidgets.QWidget):
    def __init__(self, session: results.ResultsSession, pipeline=None, parent=None):
        super().__init__(parent)
        from matplotlib.figure import Figure

        self.session = session
        self.pipeline = pipeline
        self.setWindowTitle("CTform Results")
        layout = QtWidgets.QVBoxLayout(self)

        # --- force vs stroke -------------------------------------------------
        self.force_figure = Figure(figsize=(5, 3))
        self.force_canvas = _canvas(self.force_figure)
        self.force_canvas.mpl_connect("button_press_event", self._on_force_click)
        layout.addWidget(self.force_canvas, 3)
        self.note = QtWidgets.QLabel("")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

        # --- step and field --------------------------------------------------
        row = QtWidgets.QHBoxLayout()
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, max(0, len(session.files) - 1))
        self.slider.valueChanged.connect(self.set_step)
        self.step_label = QtWidgets.QLabel("")
        row.addWidget(self.slider, 1)
        row.addWidget(self.step_label)
        layout.addLayout(row)

        form = QtWidgets.QFormLayout()
        self.field_box = QtWidgets.QComboBox()
        for name, label, unit, _assoc in results.FIELD_CATALOG:
            self.field_box.addItem(f"{label} [{unit}]", name)
        self.field_box.currentIndexChanged.connect(self.refresh)
        form.addRow("Field", self.field_box)
        self.maximum_label = QtWidgets.QLabel("")
        form.addRow("Maximum", self.maximum_label)

        self.range_min = QtWidgets.QDoubleSpinBox()
        self.range_max = QtWidgets.QDoubleSpinBox()
        for box in (self.range_min, self.range_max):
            box.setDecimals(6)
            box.setRange(-1e12, 1e12)
        self.range_auto = QtWidgets.QCheckBox("Keep one range for all steps (set min and max below)")
        self.range_auto.setChecked(False)
        self.range_auto.toggled.connect(self.apply_range)
        self.range_min.editingFinished.connect(self.apply_range)
        self.range_max.editingFinished.connect(self.apply_range)
        form.addRow(self.range_auto)
        form.addRow("Range min", self.range_min)
        form.addRow("Range max", self.range_max)

        self.warp = QtWidgets.QDoubleSpinBox()
        self.warp.setRange(0.0, 1000.0)
        self.warp.setValue(1.0)
        self.warp.setPrefix("x ")
        self.warp.editingFinished.connect(self.apply_warp)
        form.addRow("Warp by displacement", self.warp)
        layout.addLayout(form)

        # --- probe and line plot --------------------------------------------
        probe_row = QtWidgets.QHBoxLayout()
        self.probe_r = QtWidgets.QDoubleSpinBox()
        self.probe_z = QtWidgets.QDoubleSpinBox()
        for box, prefix in ((self.probe_r, "r = "), (self.probe_z, "z = ")):
            box.setRange(-1e6, 1e6)
            box.setDecimals(4)
            box.setPrefix(prefix)
            box.setSuffix(" mm")
            probe_row.addWidget(box)
        probe_button = QtWidgets.QPushButton("Probe")
        probe_button.clicked.connect(self.do_probe)
        probe_row.addWidget(probe_button)
        layout.addLayout(probe_row)
        self.probe_label = QtWidgets.QLabel("")
        layout.addWidget(self.probe_label)

        line_row = QtWidgets.QHBoxLayout()
        self.line_r1 = QtWidgets.QDoubleSpinBox()
        self.line_z1 = QtWidgets.QDoubleSpinBox()
        for box, prefix in ((self.line_r1, "to r = "), (self.line_z1, "to z = ")):
            box.setRange(-1e6, 1e6)
            box.setDecimals(4)
            box.setPrefix(prefix)
            box.setSuffix(" mm")
            line_row.addWidget(box)
        line_button = QtWidgets.QPushButton("Plot line (from probe point)")
        line_button.clicked.connect(self.plot_line)
        line_row.addWidget(line_button)
        layout.addLayout(line_row)
        self.line_figure = Figure(figsize=(5, 2.5))
        self.line_canvas = _canvas(self.line_figure)
        layout.addWidget(self.line_canvas, 2)

        buttons = QtWidgets.QHBoxLayout()
        maxima_button = QtWidgets.QPushButton("Maximum per step + CSV...")
        maxima_button.clicked.connect(self.export_summary)
        buttons.addWidget(maxima_button)
        layout.addLayout(buttons)

        self._draw_force_plot()
        if session.notes.get("stroke") == "unknown":
            self.note.setText("No loadsteps.json next to the results: the horizontal axis is the step time.")
        else:
            cross = session.notes.get("crossCheck")
            if cross:
                self.note.setText(
                    "Stroke = punch displacement minus the initial gap "
                    f"({cross['initialGap']:g} mm). Cross-check: force passes 1 % of its peak at "
                    f"{cross['firstContactDisplacement']:.3g} mm of punch displacement."
                )
        self.set_step(0)

    # ------------------------------------------------------------------ plots
    def _draw_force_plot(self):
        figure = self.force_figure
        figure.clear()
        axes = figure.add_subplot(111)
        for tool, (stroke, force) in self.session.force_curves().items():
            axes.plot(stroke, force, marker="o", markersize=3, label=tool)
        axes.set_xlabel("Punch stroke from contact [mm]")
        axes.set_ylabel("Force [N]")
        axes.grid(True, alpha=0.3)
        axes.legend()
        self._marker = axes.axvline(0.0, color="gray", linestyle="--")
        figure.tight_layout()
        self.force_canvas.draw_idle()

    def _on_force_click(self, event):
        if event.xdata is not None:
            self.slider.setValue(self.session.nearest_step(event.xdata))

    # --------------------------------------------------------------- stepping
    def current_field(self) -> str:
        return self.field_box.currentData()

    def set_step(self, index: int):
        if not self.session.files:
            return
        self.step_label.setText(self.session.label(index))
        stroke = self.session.steps[index].stroke
        if not math.isnan(stroke):
            self._marker.set_xdata([stroke, stroke])
            self.force_canvas.draw_idle()
        if self.pipeline is not None:
            try:
                names = self.pipeline.getEnumerationsOfProperty("Frame")
                self.pipeline.Frame = names[min(index, len(names) - 1)]
            except Exception as error:  # a stale or empty pipeline must not break the panel
                App.Console.PrintWarning(f"CTform Results: could not set the frame: {error}\n")
        self.refresh()

    def refresh(self, *_):
        if not self.session.files:
            return
        index = self.slider.value()
        name = self.current_field()
        self._set_view_field(name)
        found = self.session.maximum(index, name) if name in self._maximum_fields() else None
        if found is None:
            self.maximum_label.setText("not available for this field")
        else:
            unit = _unit(name)
            self.maximum_label.setText(
                f"{found.value:.6g}{unit} at r = {found.radius:.3f} mm, z = {found.axial:.3f} mm"
            )

    def _maximum_fields(self):
        return {"Plastic_Strain", "VonMises_Stress", "Pressure", "Displacement", "Temperature",
                "ContactPressure", "ContactSticking"}

    # ------------------------------------------------------------- 3D view
    def _view(self):
        return getattr(self.pipeline, "ViewObject", None) if self.pipeline is not None else None

    def _set_view_field(self, name):
        view = self._view()
        if view is None:
            return
        try:
            view.Field = name
        except Exception as error:
            App.Console.PrintWarning(f"CTform Results: the 3D view has no field {name}: {error}\n")

    def apply_range(self, *_):
        view = self._view()
        if view is None or not self.range_auto.isChecked():
            return
        try:
            view.RangeMin = self.range_min.value()
            view.RangeMax = self.range_max.value()
        except Exception as error:
            App.Console.PrintWarning(f"CTform Results: could not set the colour range: {error}\n")

    def apply_warp(self, *_):
        warp = getattr(self, "warp_filter", None)
        if warp is None and self.pipeline is not None:
            try:
                import ObjectsFem

                warp = ObjectsFem.makePostVtkFilterWarp(self.pipeline.Document, self.pipeline)
                self.warp_filter = warp
            except Exception as error:
                App.Console.PrintWarning(f"CTform Results: no warp filter: {error}\n")
                return
        try:
            warp.Factor = self.warp.value()
            warp.Document.recompute()
        except Exception as error:
            App.Console.PrintWarning(f"CTform Results: could not set the warp factor: {error}\n")

    # --------------------------------------------------------- probe and line
    def do_probe(self):
        index = self.slider.value()
        name = self.current_field()
        value = results.probe(self.session.vtk(index), name,
                              self.probe_r.value(), self.probe_z.value(), tolerance=1e-6)
        self.probe_label.setText("outside the sheet" if value is None else f"{value:.6g}{_unit(name)}")

    def plot_line(self):
        index = self.slider.value()
        name = self.current_field()
        start = (self.probe_r.value(), self.probe_z.value())
        end = (self.line_r1.value(), self.line_z1.value())
        profile = results.line_profile(self.session.vtk(index), name, start, end)
        self.line_figure.clear()
        axes = self.line_figure.add_subplot(111)
        axes.plot([p[0] for p in profile if p[1] is not None], [p[1] for p in profile if p[1] is not None])
        axes.set_xlabel("Distance along the line [mm]")
        axes.set_ylabel(f"{_FIELD_NAMES[name][1]} [{_FIELD_NAMES[name][2]}]", fontsize=8)
        axes.set_title(self.session.label(index), fontsize=8)
        axes.grid(True, alpha=0.3)
        self.line_figure.tight_layout()
        self.line_canvas.draw_idle()

    # ----------------------------------------------------------------- export
    def export_summary(self):
        target, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save summary", str(self.session.output / "ctform_summary.csv"), "CSV (*.csv)"
        )
        if not target:
            return
        progress = QtWidgets.QProgressDialog("Reading step files...", "Cancel", 0, len(self.session.files), self)
        progress.setWindowModality(QtCore.Qt.WindowModal)

        def step(done, total):
            progress.setValue(done)
            QtWidgets.QApplication.processEvents()
            return not progress.wasCanceled()

        maxima = self.session.all_maxima(progress=step)
        results.write_summary_csv(target, self.session.steps[: len(maxima)], maxima)
        App.Console.PrintMessage(f"CTform Results: summary written to {target}\n")


def open_panel(doc, output_directory, case_directory=None, pipeline=None, initial_gap=0.0):
    """Create the panel for a run and dock it in the main window."""
    import FreeCADGui as Gui

    session = results.ResultsSession(output_directory, case_directory, initial_gap)
    if not session.files:
        raise ValueError(f"No case_step_*.vtk found in {output_directory}")
    panel = ResultsPanel(session, pipeline)
    window = Gui.getMainWindow()
    dock = QtWidgets.QDockWidget("CTform Results", window)
    dock.setWidget(panel)
    window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
    dock.show()
    return panel
