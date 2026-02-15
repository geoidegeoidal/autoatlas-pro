"""Report composer for AutoAtlas Pro.

Orchestrates the full pipeline: data engine → map renderer → chart engine → PDF/PNG.
Designed for stability: caches shared data, reuses renderers, cleans temp files,
and yields control to the event loop between reports to keep QGIS responsive.
"""

from __future__ import annotations

import gc
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from qgis.core import (
    QgsLayoutExporter,
    QgsLayoutItemPicture,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtWidgets import QApplication

from .chart_engine import ChartEngine
from .data_engine import DataEngine
from .map_renderer import MapRenderer
from .models import ChartType, MapStyle, OutputFormat, ReportConfig, TemplateConfig


# Default template
_DEFAULT_TEMPLATE = TemplateConfig(
    name="default",
    display_name="Default",
    page_width_mm=297.0,
    page_height_mm=210.0,
    map_rect=(10.0, 30.0, 140.0, 165.0),
    chart_slots=[
        ("DISTRIBUTION", 160.0, 30.0, 125.0, 70.0),
        ("RANKING", 160.0, 105.0, 125.0, 90.0),
        ("WAFFLE", 10.0, 195.0, 70.0, 70.0),
        ("SUMMARY_TABLE", 90.0, 195.0, 100.0, 60.0),
    ],
    title_rect=(10.0, 5.0, 277.0, 22.0),
    subtitle_rect=(10.0, 22.0, 277.0, 10.0),
    color_palette={},
    font_family="Arial",
)


class ReportComposer:
    """Orchestrates report generation for all territorial units.

    Key stability features:
    - Applies renderer ONCE before the batch loop (not per feature)
    - Pre-computes stats and ranking ONCE (shared across all reports)
    - Cleans up temp chart image files after each export
    - Calls QApplication.processEvents() between reports
    - Never adds layouts to the project manager (avoids UI interference)
    """

    def __init__(self, project: Optional[QgsProject] = None) -> None:
        self._project = project or QgsProject.instance()
        self._data_engine = DataEngine()
        self._map_renderer = MapRenderer(self._project)
        # Force matplotlib for batch — plotly+kaleido spawns a Chromium
        # subprocess per chart, which freezes QGIS on large datasets.
        self._chart_engine = ChartEngine(use_plotly=False)

    def _resolve_template(self) -> TemplateConfig:
        """Return the default template config."""
        return _DEFAULT_TEMPLATE

    # ------------------------------------------------------------------
    # Batch generation
    # ------------------------------------------------------------------

    def generate_batch(
        self,
        config: ReportConfig,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Path]:
        """Generate reports for all (or specified) features.

        Args:
            config: Full report configuration.
            progress_callback: Optional (current, total, name) callback.

        Returns:
            List of output file paths.
        """
        layer = self._resolve_layer(config.layer_id)
        self._data_engine.load(
            layer, config.id_field, config.name_field, config.indicator_fields
        )

        feature_ids = config.feature_ids or self._data_engine.feature_ids
        total = len(feature_ids)
        output_paths: List[Path] = []

        config.output_dir.mkdir(parents=True, exist_ok=True)

        primary_field = config.indicator_fields[0]

        # ── Pre-compute shared data ONCE ──
        # Apply renderer once (not per feature — this was causing crashes)
        if config.map_style == MapStyle.CHOROPLETH:
            self._map_renderer._apply_graduated_renderer(
                layer, primary_field, config.color_ramp_name, num_classes=5
            )
        elif config.map_style == MapStyle.CATEGORICAL:
            self._map_renderer._apply_categorical_renderer(
                layer, primary_field
            )

        stats = self._data_engine.compute_stats(primary_field)
        ranking = self._data_engine.compute_ranking(primary_field, ascending=False)

        # Pre-render charts that are the SAME for all features (ranking stays the same)
        shared_charts: Dict[str, bytes] = {}
        if ChartType.RANKING in config.chart_types:
            # Ranking chart without highlight — we'll render per-feature below
            pass  # ranking varies per feature (highlight changes)

        if ChartType.DISTRIBUTION in config.chart_types:
            # Base distribution without highlight — also varies per feature
            pass

        template = config.template or _DEFAULT_TEMPLATE

        for i, fid in enumerate(feature_ids):
            name = self._data_engine._names_cache.get(fid, str(fid))

            if progress_callback:
                progress_callback(i + 1, total, name)

            # Yield to event loop to keep QGIS alive
            QApplication.processEvents()

            try:
                path = self._generate_single_fast(
                    config, layer, template, fid, name,
                    primary_field, stats, ranking,
                )
                output_paths.append(path)
            except Exception as exc:
                # Log but don't crash the entire batch
                import traceback
                traceback.print_exc()
                continue

            # Periodic GC to prevent memory buildup
            if i > 0 and i % 10 == 0:
                gc.collect()

        return output_paths

    # ------------------------------------------------------------------
    # Single report (optimized — no renderer re-application)
    # ------------------------------------------------------------------

    def _generate_single_fast(
        self,
        config: ReportConfig,
        layer: QgsVectorLayer,
        template: TemplateConfig,
        feature_id: Any,
        name: str,
        primary_field: str,
        stats: Any,
        ranking: Any,
    ) -> Path:
        """Generate a single report. Renderer already applied to layer."""

        safe_name = self._sanitize_filename(name)
        temp_files: List[str] = []

        # Create layout (NOT added to project manager — avoids UI interference)
        layout = QgsPrintLayout(self._project)
        layout.initializeDefaults()

        page = layout.pageCollection().page(0)
        page.setPageSize(
            QgsLayoutSize(template.page_width_mm, template.page_height_mm)
        )

        # --- Title ---
        self._map_renderer.add_title(
            layout, name, template.title_rect, font_size=18, bold=True
        )

        # --- Subtitle ---
        if template.subtitle_rect and config.indicator_fields:
            self._map_renderer.add_title(
                layout, primary_field, template.subtitle_rect,
                font_size=11, bold=False,
            )

        # --- Map (renderer already applied, just set extent) ---
        map_item = self._map_renderer._create_map_item(layout, template.map_rect)
        extent = self._map_renderer._get_feature_extent(
            layer, config.id_field, feature_id
        )
        map_item.setExtent(extent)
        map_item.setLayers([layer])

        # --- Legend ---
        legend_x = template.map_rect[0]
        legend_y = template.map_rect[1] + template.map_rect[3] + 2
        self._map_renderer.add_legend(layout, map_item, (legend_x, legend_y))

        # --- Charts (only feature-specific parts) ---
        context = self._data_engine.get_feature_context(feature_id, primary_field)
        chart_map: Dict[str, bytes] = {}

        if ChartType.DISTRIBUTION in config.chart_types:
            chart_map["DISTRIBUTION"] = self._chart_engine.render_distribution(
                stats, highlight_value=context.value, title=primary_field
            )

        if ChartType.RANKING in config.chart_types:
            chart_map["RANKING"] = self._chart_engine.render_ranking(
                ranking, highlight_id=feature_id,
                title=f"Ranking — {primary_field}",
            )

        if ChartType.WAFFLE in config.chart_types:
            chart_map["WAFFLE"] = self._chart_engine.render_waffle(
                context.value, stats.max_val, label=name, title=primary_field,
            )

        if ChartType.SUMMARY_TABLE in config.chart_types:
            chart_map["SUMMARY_TABLE"] = self._chart_engine.render_summary_table(
                context, stats, title=name,
            )

        # Place charts
        for slot_type, x, y, w, h in template.chart_slots:
            if slot_type in chart_map:
                tmp_path = self._add_chart_image(
                    layout, chart_map[slot_type], (x, y, w, h)
                )
                temp_files.append(tmp_path)

        # --- Export ---
        output_path = self._export(layout, config, safe_name)

        # --- Cleanup ---
        # Delete layout items to free memory (don't call removeLayout,
        # since we never added it to the layout manager)
        layout.clear()
        del layout

        # Remove temp chart image files
        for tmp in temp_files:
            try:
                os.unlink(tmp)
            except OSError:
                pass

        return output_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_layer(self, layer_id: str) -> QgsVectorLayer:
        """Resolve a QGIS layer by its ID."""
        layer = self._project.mapLayer(layer_id)
        if not layer or not isinstance(layer, QgsVectorLayer):
            raise ValueError(f"Layer '{layer_id}' not found or not a vector layer.")
        return layer

    @staticmethod
    def _add_chart_image(
        layout: QgsPrintLayout,
        png_bytes: bytes,
        rect_mm: Tuple[float, float, float, float],
    ) -> str:
        """Write PNG bytes to a temp file and add as picture item.

        Returns:
            Path to the temp file (caller is responsible for cleanup).
        """
        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, png_bytes)
        finally:
            os.close(fd)

        pic = QgsLayoutItemPicture(layout)
        pic.setPicturePath(tmp_path)
        pic.attemptMove(QgsLayoutPoint(rect_mm[0], rect_mm[1]))
        pic.attemptResize(QgsLayoutSize(rect_mm[2], rect_mm[3]))
        pic.setResizeMode(QgsLayoutItemPicture.ZoomResizeFrame)

        layout.addLayoutItem(pic)
        return tmp_path

    def _export(
        self,
        layout: QgsPrintLayout,
        config: ReportConfig,
        filename: str,
    ) -> Path:
        """Export the layout to PDF or PNG."""
        exporter = QgsLayoutExporter(layout)

        if config.output_format == OutputFormat.PDF:
            out_path = config.output_dir / f"{filename}.pdf"
            settings = QgsLayoutExporter.PdfExportSettings()
            settings.dpi = config.dpi
            result = exporter.exportToPdf(str(out_path), settings)
        else:
            out_path = config.output_dir / f"{filename}.png"
            settings = QgsLayoutExporter.ImageExportSettings()
            settings.dpi = config.dpi
            result = exporter.exportToImage(str(out_path), settings)

        if result != QgsLayoutExporter.Success:
            raise RuntimeError(
                f"Export failed for '{filename}' with error code {result}"
            )

        return out_path

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Make a string safe for use as a filename."""
        keep = set(" ._-")
        return "".join(c if c.isalnum() or c in keep else "_" for c in name).strip()
