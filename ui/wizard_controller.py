"""Controller for WizardDialog in AutoAtlas Pro."""

from pathlib import Path
from typing import List, Optional

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import QApplication

from ..core.models import (
    ChartType,
    ContextLayerConfig,
    MapStyle,
    OutputFormat,
    ReportConfig,
)
from ..core.report_composer import ReportComposer


class WizardController:
    """Handles the business logic, validation, and generation batch orchestration
    for the WizardDialog. This separates UI concerns from generating logic.
    """

    def __init__(self, view) -> None:
        """Initialize controller with a reference to the WizardDialog view."""
        self.view = view
        self._composer: Optional[ReportComposer] = None
        
        # Batch generation state
        self._cancelled = False
        self._batch_config: Optional[ReportConfig] = None
        self._batch_paths: List[Path] = []
        self._batch_errors: List[str] = []
        self._consecutive_errors = 0
        self._batch_layer = None
        self._batch_primary: Optional[str] = None
        self._batch_stats = None
        self._batch_ranking = None
        self._batch_ids: List = []
        self._batch_index = 0
        self._batch_total = 0
        self._batch_template = None
        self._batch_base_layer = None

    def validate_step_data(self) -> bool:
        """Validate step 1 (Data) input before proceeding."""
        layer = self.view._layer_combo.currentLayer()
        if not layer:
            return False, self.view.tr("Please select a coverage layer.")
            
        has_indic = False
        for i in range(self.view._indicator_list.count()):
            if self.view._indicator_list.item(i).checkState() == Qt.Checked:
                has_indic = True
                break
        
        if not has_indic:
            return False, self.view.tr("Please select at least one indicator field.")

        return True, ""

    def build_config(self) -> ReportConfig:
        """Builds a ReportConfig securely reading from UI Widgets in the view."""
        layer = self.view._layer_combo.currentLayer()

        indicator_fields = []
        for i in range(self.view._indicator_list.count()):
            item = self.view._indicator_list.item(i)
            if item.checkState() == Qt.Checked:
                indicator_fields.append(item.text())

        map_style = self.view._style_combo.currentData()
        base_map = self.view._basemap_combo.currentData()
        
        map_opacity = self.view._opacity_widget.opacity()
        highlight = self.view._chk_highlight.isChecked()
        
        label_field = None
        if self.view._chk_labels.isChecked():
            label_field = self.view._label_field_combo.currentField()
            
        context_configs: List[ContextLayerConfig] = []
        for i in range(self.view._ctx_table.rowCount()):
            chk = self.view._ctx_table.item(i, 0)
            if chk and chk.checkState() == Qt.Checked:
                lid = chk.data(Qt.UserRole)
                alias = (self.view._ctx_table.item(i, 2).text() or "").strip()
                spin = self.view._ctx_table.cellWidget(i, 3)
                opa = spin.value() if spin else 1.0
                context_configs.append(
                    ContextLayerConfig(layer_id=lid, legend_alias=alias, opacity=opa)
                )

        show_overview_map = self.view._chk_overview.isChecked()
        show_overview_labels = self.view._chk_overview_labels.isChecked()
        layer_legend_alias = self.view._layer_alias_edit.text().strip()

        custom_title = self.view._title_edit.text()
        custom_footer = self.view._footer_edit.text()
        header_color = self.view._col_header.color().name()
        footer_color = self.view._col_footer.color().name()

        language = self.view._lang_combo.currentText()
        template_name = self.view._template_combo.currentText()
        logo_path = self.view._logo_path_edit.text().strip()
        logo_pos = self.view._logo_pos_combo.currentText()
        variable_alias = self.view._alias_edit.text().strip()

        output_format = OutputFormat.PDF if self.view._radio_pdf.isChecked() else OutputFormat.PNG
        output_dir = Path(self.view._dir_edit.text().strip())

        ramp_name = "Spectral"
        if map_style == MapStyle.GRADUATED:
            ramp_name = self.view._ramp_combo.currentText()
        elif map_style == MapStyle.CATEGORIZED:
            ramp_name = self.view._cat_ramp_combo.currentText()
            
        graduated_mode = self.view._mode_combo.currentData()
        graduated_classes = self.view._classes_spin.value()
        single_color = self.view._color_btn_single.color().name()
        category_field = self.view._cat_col_combo.currentField()
        
        return ReportConfig(
            layer_id=layer.id(),
            id_field=self.view._id_field_combo.currentText(),
            name_field=self.view._name_field_combo.currentText(),
            indicator_fields=indicator_fields,
            map_style=map_style,
            color_ramp_name=ramp_name,
            graduated_mode=graduated_mode,
            graduated_classes=graduated_classes,
            single_color=single_color,
            category_field=category_field,
            base_map=base_map,
            chart_types=[],
            output_format=output_format,
            output_dir=output_dir,
            dpi=self.view._dpi_spin.value(),
            map_opacity=map_opacity,
            highlight_analyzed=highlight,
            label_field=label_field,
            context_layers_config=context_configs,
            show_overview_map=show_overview_map,
            show_overview_labels=show_overview_labels,
            layer_legend_alias=layer_legend_alias,
            custom_title=custom_title,
            custom_subtitle=self.view._subtitle_edit.text().strip(),
            custom_footer=custom_footer,
            header_color=header_color,
            footer_color=footer_color,
            language=language,
            template_name=template_name,
            logo_path=logo_path,
            logo_position=logo_pos,
            variable_alias=variable_alias,
        )

    def start_generation(self) -> None:
        """Prepare batch generation and start async processing."""
        output_dir = self.view._dir_edit.text().strip()
        if not output_dir:
            self.view._dir_edit.setText(str(Path.home() / "AutoAtlas_Output"))

        config = self.build_config()

        self._cancelled = False
        self._batch_config = config
        self._batch_paths = []
        self._batch_errors = []
        self._consecutive_errors = 0

        try:
            self._composer = ReportComposer()
            layer = self._composer._resolve_layer(config.layer_id)
            self._batch_layer = layer
            self._composer._data_engine.load(
                layer, config.id_field, config.name_field, config.indicator_fields,
            )

            primary = config.indicator_fields[0]
            self._batch_primary = primary

            self._composer._apply_renderer(layer, config, primary)

            self._batch_stats = self._composer._data_engine.compute_stats(primary)
            self._batch_ranking = self._composer._data_engine.compute_ranking(
                primary, ascending=False,
            )

            feature_ids = config.feature_ids or self._composer._data_engine.feature_ids
            self._batch_ids = list(feature_ids)
            self._batch_index = 0
            self._batch_total = len(self._batch_ids)
            self._batch_template = config.template or None
            
            self._batch_base_layer = self._composer._create_base_map_layer(config.base_map)

            self.view._progress_bar.setRange(0, self._batch_total)
            self.view._progress_bar.setValue(0)

            config.output_dir.mkdir(parents=True, exist_ok=True)

            # Start Async Loop
            QTimer.singleShot(0, self.process_next_report)

        except Exception as exc:
            self.view._on_batch_error(str(exc))

    def process_next_report(self) -> None:
        """Process one report, check circuit breaker, and schedule the next."""
        if getattr(self, '_cancelled', False):
            self.view._on_batch_cancelled()
            return

        if self._batch_index >= self._batch_total:
            self.view._on_batch_complete(self._batch_paths, self._batch_errors)
            return

        fid = self._batch_ids[self._batch_index]
        name = self._composer._data_engine._names_cache.get(fid, str(fid))

        self.view.update_progress(
            self._batch_index + 1, self._batch_total, name
        )

        try:
            path = self._composer._generate_single(
                self._batch_config,
                self._batch_layer,
                self._batch_template or self._composer._resolve_template(),
                fid,
                name,
                self._batch_primary,
                self._batch_stats,
                self._batch_ranking,
                self._batch_base_layer,
            )
            self._batch_paths.append(path)
            self._consecutive_errors = 0  # Reset on success
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self._batch_errors.append(f"{name}: {exc}")
            self._consecutive_errors += 1
            # Circuit Breaker: If we accumulated 3 consecutive direct errors, break
            if self._consecutive_errors >= 3:
                self.view._on_batch_error(self.view.tr("Circuit Breaker Tripped: Demasiados errores de renderizado consecutivos."))
                return

        self._batch_index += 1

        if self._batch_index % 10 == 0:
            import gc
            gc.collect()

        QTimer.singleShot(0, self.process_next_report)

    def cancel_generation(self) -> None:
        self._cancelled = True

    def cleanup(self) -> None:
        if self._batch_base_layer and self._composer:
            try:
                self._composer._project.removeMapLayer(self._batch_base_layer.id())
            except Exception:
                pass
            self._batch_base_layer = None
