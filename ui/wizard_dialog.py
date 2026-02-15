"""Multi-step wizard dialog for AutoAtlas Pro.

Three-step workflow:
  1. Data — Select layer, ID field, name field, indicator fields
  2. Style — Map style, color ramp, chart selection, template
  3. Output — Format, directory, batch options
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from qgis.core import (
    QgsMapLayerProxyModel,
    QgsProject,
    QgsStyle,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication, QSize, Qt
from qgis.PyQt.QtGui import QFont, QIcon
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from qgis.gui import QgisInterface, QgsMapLayerComboBox

from ..core.models import ChartType, MapStyle, OutputFormat, ReportConfig


class WizardDialog(QDialog):
    """Three-step wizard for configuring and launching report generation."""

    def __init__(
        self,
        iface: QgisInterface,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._iface = iface
        self._current_step = 0

        self.setWindowTitle(self.tr("AutoAtlas Pro — Report Wizard"))
        self.setMinimumSize(QSize(680, 520))
        self.setModal(True)

        self._build_ui()

    def tr(self, message: str) -> str:
        return QCoreApplication.translate("WizardDialog", message)

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # --- Header with step indicators ---
        self._header = self._build_header()
        root.addWidget(self._header)

        # --- Stacked content area ---
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_step_data())
        self._stack.addWidget(self._build_step_style())
        self._stack.addWidget(self._build_step_output())
        root.addWidget(self._stack, stretch=1)

        # --- Footer with navigation buttons ---
        footer = self._build_footer()
        root.addWidget(footer)

    # ------------------------------------------------------------------
    # Header (step indicator)
    # ------------------------------------------------------------------

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: #0f3460; padding: 16px; }"
        )
        layout = QHBoxLayout(header)

        self._step_labels: list[QLabel] = []
        steps = [
            self.tr("① Data"),
            self.tr("② Style"),
            self.tr("③ Output"),
        ]
        for i, text in enumerate(steps):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignCenter)
            font = QFont("Arial", 12, QFont.Bold if i == 0 else QFont.Normal)
            lbl.setFont(font)
            lbl.setStyleSheet(
                "color: white;" if i == 0 else "color: rgba(255,255,255,0.5);"
            )
            self._step_labels.append(lbl)
            layout.addWidget(lbl)

        return header

    def _update_step_indicator(self) -> None:
        for i, lbl in enumerate(self._step_labels):
            if i == self._current_step:
                lbl.setStyleSheet("color: white;")
                font = lbl.font()
                font.setBold(True)
                lbl.setFont(font)
            elif i < self._current_step:
                lbl.setStyleSheet("color: rgba(255,255,255,0.7);")
                font = lbl.font()
                font.setBold(False)
                lbl.setFont(font)
            else:
                lbl.setStyleSheet("color: rgba(255,255,255,0.4);")
                font = lbl.font()
                font.setBold(False)
                lbl.setFont(font)

    # ------------------------------------------------------------------
    # Step 1: Data Selection
    # ------------------------------------------------------------------

    def _build_step_data(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(QLabel(
            f"<h3>{self.tr('Select Data Source')}</h3>"
            f"<p>{self.tr('Choose the vector layer and fields for your report.')}</p>"
        ))

        # Layer selection
        grp_layer = QGroupBox(self.tr("Coverage Layer"))
        grp_layout = QVBoxLayout(grp_layer)

        from qgis.gui import QgsMapLayerComboBox
        self._layer_combo = QgsMapLayerComboBox()
        self._layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self._layer_combo.layerChanged.connect(self._on_layer_changed)
        grp_layout.addWidget(self._layer_combo)
        layout.addWidget(grp_layer)

        # Fields
        grp_fields = QGroupBox(self.tr("Fields"))
        fields_layout = QVBoxLayout(grp_fields)

        # ID field
        row_id = QHBoxLayout()
        row_id.addWidget(QLabel(self.tr("ID Field:")))
        self._id_field_combo = QComboBox()
        row_id.addWidget(self._id_field_combo, stretch=1)
        fields_layout.addLayout(row_id)

        # Name field
        row_name = QHBoxLayout()
        row_name.addWidget(QLabel(self.tr("Name Field:")))
        self._name_field_combo = QComboBox()
        row_name.addWidget(self._name_field_combo, stretch=1)
        fields_layout.addLayout(row_name)

        # Indicator fields (multi-select)
        fields_layout.addWidget(QLabel(self.tr("Indicator Fields (select one or more):")))
        self._indicator_list = QListWidget()
        self._indicator_list.setSelectionMode(QListWidget.MultiSelection)
        self._indicator_list.setMaximumHeight(150)
        fields_layout.addWidget(self._indicator_list)

        layout.addWidget(grp_fields)
        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Populate if a layer is already selected
        self._on_layer_changed(self._layer_combo.currentLayer())

        return page

    def _on_layer_changed(self, layer: Optional[QgsVectorLayer]) -> None:
        """Populate field combos when layer selection changes."""
        self._id_field_combo.clear()
        self._name_field_combo.clear()
        self._indicator_list.clear()

        if not layer:
            return

        fields = layer.fields()
        for f in fields:
            fname = f.name()
            self._id_field_combo.addItem(fname)
            self._name_field_combo.addItem(fname)

            # Only show numeric fields in indicator list
            if f.isNumeric():
                item = QListWidgetItem(fname)
                self._indicator_list.addItem(item)

    # ------------------------------------------------------------------
    # Step 2: Style Configuration
    # ------------------------------------------------------------------

    def _build_step_style(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(QLabel(
            f"<h3>{self.tr('Configure Style')}</h3>"
            f"<p>{self.tr('Choose how your maps and charts will look.')}</p>"
        ))

        # Map style
        grp_map = QGroupBox(self.tr("Map Style"))
        map_layout = QVBoxLayout(grp_map)
        self._radio_choropleth = QRadioButton(self.tr("Choropleth (graduated colors)"))
        self._radio_choropleth.setChecked(True)
        self._radio_categorical = QRadioButton(self.tr("Categorical (unique values)"))
        map_layout.addWidget(self._radio_choropleth)
        map_layout.addWidget(self._radio_categorical)

        # Color ramp
        row_ramp = QHBoxLayout()
        row_ramp.addWidget(QLabel(self.tr("Color Ramp:")))
        self._ramp_combo = QComboBox()
        ramp_names = QgsStyle.defaultStyle().colorRampNames()
        self._ramp_combo.addItems(sorted(ramp_names))
        idx = self._ramp_combo.findText("Spectral")
        if idx >= 0:
            self._ramp_combo.setCurrentIndex(idx)
        row_ramp.addWidget(self._ramp_combo, stretch=1)
        map_layout.addLayout(row_ramp)

        layout.addWidget(grp_map)

        # Charts
        grp_charts = QGroupBox(self.tr("Charts to Include"))
        charts_layout = QVBoxLayout(grp_charts)

        self._chk_distribution = QCheckBox(self.tr("Distribution histogram"))
        self._chk_distribution.setChecked(True)
        self._chk_ranking = QCheckBox(self.tr("Ranking lollipop chart"))
        self._chk_ranking.setChecked(True)
        self._chk_waffle = QCheckBox(self.tr("Proportion donut chart"))
        self._chk_waffle.setChecked(True)
        self._chk_summary = QCheckBox(self.tr("Summary statistics table"))
        self._chk_summary.setChecked(True)

        charts_layout.addWidget(self._chk_distribution)
        charts_layout.addWidget(self._chk_ranking)
        charts_layout.addWidget(self._chk_waffle)
        charts_layout.addWidget(self._chk_summary)
        layout.addWidget(grp_charts)

        # Template
        grp_template = QGroupBox(self.tr("Report Template"))
        tmpl_layout = QVBoxLayout(grp_template)
        self._template_combo = QComboBox()
        self._template_combo.addItems([
            self.tr("Default (A4 Landscape)"),
            self.tr("Institutional"),
            self.tr("Academic"),
            self.tr("Minimal"),
        ])
        tmpl_layout.addWidget(self._template_combo)
        layout.addWidget(grp_template)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        return page

    # ------------------------------------------------------------------
    # Step 3: Output Configuration
    # ------------------------------------------------------------------

    def _build_step_output(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(QLabel(
            f"<h3>{self.tr('Configure Output')}</h3>"
            f"<p>{self.tr('Choose format and destination for your reports.')}</p>"
        ))

        # Format
        grp_format = QGroupBox(self.tr("Output Format"))
        fmt_layout = QVBoxLayout(grp_format)
        self._radio_pdf = QRadioButton("PDF")
        self._radio_pdf.setChecked(True)
        self._radio_png = QRadioButton("PNG")
        fmt_layout.addWidget(self._radio_pdf)
        fmt_layout.addWidget(self._radio_png)
        layout.addWidget(grp_format)

        # DPI
        row_dpi = QHBoxLayout()
        row_dpi.addWidget(QLabel(self.tr("Resolution (DPI):")))
        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(72, 1200)
        self._dpi_spin.setValue(150)
        self._dpi_spin.setSingleStep(50)
        row_dpi.addWidget(self._dpi_spin)
        layout.addLayout(row_dpi)

        # Output directory
        grp_dir = QGroupBox(self.tr("Output Directory"))
        dir_layout = QHBoxLayout(grp_dir)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText(self.tr("Select output folder..."))
        dir_layout.addWidget(self._dir_edit, stretch=1)
        browse_btn = QPushButton(self.tr("Browse..."))
        browse_btn.clicked.connect(self._browse_output_dir)
        dir_layout.addWidget(browse_btn)
        layout.addWidget(grp_dir)

        # Progress (shown during generation)
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setVisible(False)
        self._progress_label.setStyleSheet("font-style: italic; color: gray;")
        layout.addWidget(self._progress_label)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        return page

    def _browse_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, self.tr("Select Output Directory"),
            str(Path.home()),
        )
        if directory:
            self._dir_edit.setText(directory)

    # ------------------------------------------------------------------
    # Footer (navigation)
    # ------------------------------------------------------------------

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setStyleSheet("QFrame { border-top: 1px solid palette(mid); padding: 12px; }")
        layout = QHBoxLayout(footer)

        self._btn_back = QPushButton(self.tr("← Back"))
        self._btn_back.setEnabled(False)
        self._btn_back.clicked.connect(self._go_back)
        layout.addWidget(self._btn_back)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self._btn_next = QPushButton(self.tr("Next →"))
        self._btn_next.setStyleSheet(
            """
            QPushButton {
                background-color: #0f3460;
                color: white;
                font-weight: bold;
                padding: 8px 24px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #1a4a7a; }
            QPushButton:disabled { background-color: #95a5a6; }
            """
        )
        self._btn_next.clicked.connect(self._go_next)
        layout.addWidget(self._btn_next)

        return footer

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_next(self) -> None:
        if self._current_step == 0 and not self._validate_step_data():
            return
        if self._current_step == 1 and not self._validate_step_style():
            return
        if self._current_step == 2:
            self._generate_reports()
            return

        self._current_step += 1
        self._stack.setCurrentIndex(self._current_step)
        self._btn_back.setEnabled(True)

        if self._current_step == 2:
            self._btn_next.setText(self.tr("🚀 Generate"))

        self._update_step_indicator()

    def _go_back(self) -> None:
        if self._current_step <= 0:
            return

        self._current_step -= 1
        self._stack.setCurrentIndex(self._current_step)
        self._btn_back.setEnabled(self._current_step > 0)
        self._btn_next.setText(self.tr("Next →"))
        self._update_step_indicator()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_step_data(self) -> bool:
        layer = self._layer_combo.currentLayer()
        if not layer:
            QMessageBox.warning(self, self.tr("Validation"), self.tr("Please select a coverage layer."))
            return False

        selected_indicators = self._indicator_list.selectedItems()
        if not selected_indicators:
            QMessageBox.warning(self, self.tr("Validation"), self.tr("Please select at least one indicator field."))
            return False

        return True

    def _validate_step_style(self) -> bool:
        # All style options have defaults, so always valid
        return True

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def _build_config(self) -> ReportConfig:
        """Build a ReportConfig from the wizard's current state."""
        layer = self._layer_combo.currentLayer()

        indicator_fields = [
            item.text() for item in self._indicator_list.selectedItems()
        ]

        map_style = (
            MapStyle.CHOROPLETH if self._radio_choropleth.isChecked()
            else MapStyle.CATEGORICAL
        )

        chart_types: List[ChartType] = []
        if self._chk_distribution.isChecked():
            chart_types.append(ChartType.DISTRIBUTION)
        if self._chk_ranking.isChecked():
            chart_types.append(ChartType.RANKING)
        if self._chk_waffle.isChecked():
            chart_types.append(ChartType.WAFFLE)
        if self._chk_summary.isChecked():
            chart_types.append(ChartType.SUMMARY_TABLE)

        output_format = OutputFormat.PDF if self._radio_pdf.isChecked() else OutputFormat.PNG

        output_dir = self._dir_edit.text().strip()
        if not output_dir:
            output_dir = str(Path.home() / "AutoAtlas_Output")

        return ReportConfig(
            layer_id=layer.id(),
            id_field=self._id_field_combo.currentText(),
            name_field=self._name_field_combo.currentText(),
            indicator_fields=indicator_fields,
            map_style=map_style,
            color_ramp_name=self._ramp_combo.currentText(),
            chart_types=chart_types,
            output_format=output_format,
            output_dir=Path(output_dir),
            dpi=self._dpi_spin.value(),
        )

    def _generate_reports(self) -> None:
        """Validate output step and launch async generation."""
        output_dir = self._dir_edit.text().strip()
        if not output_dir:
            self._dir_edit.setText(str(Path.home() / "AutoAtlas_Output"))

        config = self._build_config()

        # Show progress UI
        self._progress_bar.setVisible(True)
        self._progress_label.setVisible(True)
        self._btn_next.setText(self.tr("Cancel"))
        self._btn_next.setEnabled(True)
        self._btn_back.setEnabled(False)

        # Disconnect old signal and connect cancel
        try:
            self._btn_next.clicked.disconnect()
        except TypeError:
            pass
        self._btn_next.clicked.connect(self._cancel_generation)

        # Initialize batch state
        self._cancelled = False
        self._batch_config = config
        self._batch_paths: list[Path] = []
        self._batch_errors: list[str] = []

        try:
            from ..core.report_composer import ReportComposer

            self._composer = ReportComposer()

            # Load data and apply renderer ONCE
            layer = self._composer._resolve_layer(config.layer_id)
            self._batch_layer = layer
            self._composer._data_engine.load(
                layer, config.id_field, config.name_field,
                config.indicator_fields,
            )

            primary = config.indicator_fields[0]
            self._batch_primary = primary

            # Apply renderer once
            from ..core.models import MapStyle
            if config.map_style == MapStyle.CHOROPLETH:
                self._composer._map_renderer._apply_graduated_renderer(
                    layer, primary, config.color_ramp_name, num_classes=5,
                )
            elif config.map_style == MapStyle.CATEGORICAL:
                self._composer._map_renderer._apply_categorical_renderer(
                    layer, primary,
                )

            # Pre-compute shared data
            self._batch_stats = self._composer._data_engine.compute_stats(primary)
            self._batch_ranking = self._composer._data_engine.compute_ranking(
                primary, ascending=False,
            )

            feature_ids = (
                config.feature_ids
                or self._composer._data_engine.feature_ids
            )
            self._batch_ids = list(feature_ids)
            self._batch_index = 0
            self._batch_total = len(self._batch_ids)
            self._batch_template = config.template or None

            self._progress_bar.setRange(0, self._batch_total)
            self._progress_bar.setValue(0)

            config.output_dir.mkdir(parents=True, exist_ok=True)

            # Start async loop — process first report after yielding to event loop
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(0, self._process_next_report)

        except Exception as exc:
            self._on_batch_error(str(exc))

    def _process_next_report(self) -> None:
        """Process one report, then schedule the next via QTimer."""
        if self._cancelled:
            self._on_batch_cancelled()
            return

        if self._batch_index >= self._batch_total:
            self._on_batch_complete()
            return

        fid = self._batch_ids[self._batch_index]
        name = self._composer._data_engine._names_cache.get(fid, str(fid))

        # Update progress
        self._progress_bar.setValue(self._batch_index + 1)
        self._progress_label.setText(
            self.tr("Generating: {name} ({current}/{total})").format(
                name=name,
                current=self._batch_index + 1,
                total=self._batch_total,
            )
        )

        try:
            path = self._composer._generate_single_fast(
                self._batch_config,
                self._batch_layer,
                self._batch_template or self._composer._resolve_template(),
                fid,
                name,
                self._batch_primary,
                self._batch_stats,
                self._batch_ranking,
            )
            self._batch_paths.append(path)
        except Exception as exc:
            self._batch_errors.append(f"{name}: {exc}")

        self._batch_index += 1

        # Periodic garbage collection
        if self._batch_index % 10 == 0:
            import gc
            gc.collect()

        # Schedule next report — yields back to Qt event loop
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(0, self._process_next_report)

    def _cancel_generation(self) -> None:
        """Set cancel flag — processing stops on next iteration."""
        self._cancelled = True
        self._progress_label.setText(self.tr("Cancelling..."))
        self._btn_next.setEnabled(False)

    def _on_batch_complete(self) -> None:
        """Called when all reports have been processed."""
        self._reset_buttons()
        n = len(self._batch_paths)
        msg = self.tr("Generated {n} reports in:\n{dir}").format(
            n=n, dir=self._batch_config.output_dir,
        )
        if self._batch_errors:
            msg += self.tr("\n\n{e} errors (skipped):").format(e=len(self._batch_errors))
            msg += "\n" + "\n".join(self._batch_errors[:10])

        QMessageBox.information(self, self.tr("Success"), msg)
        self.accept()

    def _on_batch_cancelled(self) -> None:
        """Called when user cancels mid-batch."""
        self._reset_buttons()
        n = len(self._batch_paths)
        QMessageBox.information(
            self,
            self.tr("Cancelled"),
            self.tr("Cancelled. {n} reports were generated before stopping.").format(n=n),
        )

    def _on_batch_error(self, error: str) -> None:
        """Called on fatal setup error."""
        self._reset_buttons()
        QMessageBox.critical(
            self,
            self.tr("Error"),
            self.tr("Report generation failed:\n{err}").format(err=error),
        )

    def _reset_buttons(self) -> None:
        """Restore footer buttons to normal state."""
        self._progress_bar.setVisible(False)
        self._progress_label.setVisible(False)
        self._btn_next.setText(self.tr("🚀 Generate"))
        self._btn_next.setEnabled(True)
        self._btn_back.setEnabled(True)
        try:
            self._btn_next.clicked.disconnect()
        except TypeError:
            pass
        self._btn_next.clicked.connect(self._go_next)

