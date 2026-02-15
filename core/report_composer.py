"""Report composer for AutoAtlas Pro.

Orchestrates the full pipeline: data engine → map renderer → chart engine → PDF/PNG.
Runs as a QgsTask for non-blocking batch generation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from qgis.core import (
    QgsLayoutExporter,
    QgsLayoutItemPicture,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPageSizeRegistry,
    QgsPrintLayout,
    QgsProject,
    QgsVectorLayer,
)

from .chart_engine import ChartEngine
from .data_engine import DataEngine
from .map_renderer import MapRenderer
from .models import ChartType, MapStyle, OutputFormat, ReportConfig, TemplateConfig


# Default template used when none is specified
_DEFAULT_TEMPLATE = TemplateConfig(
    name="default",
    display_name="Default",
    page_width_mm=297.0,
    page_height_mm=210.0,
    map_rect=(10.0, 30.0, 140.0, 165.0),
    chart_slots=[
        ("DISTRIBUTION", 160.0, 30.0, 125.0, 70.0),
        ("RANKING", 160.0, 105.0, 125.0, 90.0),
        ("WAFFLE", 10.0, 195.0, 70.0, 70.0),      # Overflow onto y, will clip gracefully
        ("SUMMARY_TABLE", 90.0, 195.0, 100.0, 60.0),
    ],
    title_rect=(10.0, 5.0, 277.0, 22.0),
    subtitle_rect=(10.0, 22.0, 277.0, 10.0),
    color_palette={},
    font_family="Arial",
)


class ReportComposer:
    """Orchestrates report generation for all territorial units.

    Usage:
        composer = ReportComposer()
        paths = composer.generate_batch(config, progress_callback=print)
    """

    def __init__(self, project: Optional[QgsProject] = None) -> None:
        self._project = project or QgsProject.instance()
        self._data_engine = DataEngine()
        self._map_renderer = MapRenderer(self._project)
        self._chart_engine = ChartEngine()

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

        for i, fid in enumerate(feature_ids):
            name = self._data_engine._names_cache.get(fid, str(fid))
            if progress_callback:
                progress_callback(i + 1, total, name)

            path = self.generate_single(config, layer, fid)
            output_paths.append(path)

        return output_paths

    # ------------------------------------------------------------------
    # Single report generation
    # ------------------------------------------------------------------

    def generate_single(
        self,
        config: ReportConfig,
        layer: Optional[QgsVectorLayer] = None,
        feature_id: Any = None,
    ) -> Path:
        """Generate a single report page for one territorial unit.

        Args:
            config: Full report configuration.
            layer: Resolved vector layer (or None to auto-resolve).
            feature_id: Feature ID to generate report for.

        Returns:
            Path to the generated output file.
        """
        if layer is None:
            layer = self._resolve_layer(config.layer_id)

        template = config.template or _DEFAULT_TEMPLATE
        name = self._data_engine._names_cache.get(feature_id, str(feature_id))
        safe_name = self._sanitize_filename(name)

        # Create print layout
        layout = QgsPrintLayout(self._project)
        layout.initializeDefaults()

        # Set page size
        page = layout.pageCollection().page(0)
        page.setPageSize(
            QgsLayoutSize(template.page_width_mm, template.page_height_mm)
        )

        # --- Title ---
        self._map_renderer.add_title(
            layout, name, template.title_rect, font_size=18, bold=True
        )

        # --- Subtitle (first indicator) ---
        if template.subtitle_rect and config.indicator_fields:
            self._map_renderer.add_title(
                layout,
                config.indicator_fields[0],
                template.subtitle_rect,
                font_size=11,
                bold=False,
            )

        # --- Map ---
        primary_field = config.indicator_fields[0]

        if config.map_style == MapStyle.CHOROPLETH:
            map_item = self._map_renderer.render_choropleth(
                layout, layer, primary_field, config.color_ramp_name,
                template.map_rect, feature_id, config.id_field,
            )
        elif config.map_style == MapStyle.CATEGORICAL:
            map_item = self._map_renderer.render_categorical(
                layout, layer, primary_field,
                template.map_rect, feature_id, config.id_field,
            )
        else:
            map_item = self._map_renderer.render_choropleth(
                layout, layer, primary_field, config.color_ramp_name,
                template.map_rect, feature_id, config.id_field,
            )

        # --- Legend ---
        legend_x = template.map_rect[0]
        legend_y = template.map_rect[1] + template.map_rect[3] + 2
        self._map_renderer.add_legend(layout, map_item, (legend_x, legend_y))

        # --- Charts ---
        stats = self._data_engine.compute_stats(primary_field)
        ranking = self._data_engine.compute_ranking(primary_field, ascending=False)
        context = self._data_engine.get_feature_context(feature_id, primary_field)

        chart_map: Dict[str, bytes] = {}

        if ChartType.DISTRIBUTION in config.chart_types:
            chart_map["DISTRIBUTION"] = self._chart_engine.render_distribution(
                stats, highlight_value=context.value, title=primary_field
            )

        if ChartType.RANKING in config.chart_types:
            chart_map["RANKING"] = self._chart_engine.render_ranking(
                ranking, highlight_id=feature_id, title=f"Ranking — {primary_field}"
            )

        if ChartType.WAFFLE in config.chart_types:
            chart_map["WAFFLE"] = self._chart_engine.render_waffle(
                context.value, stats.max_val,
                label=name, title=primary_field,
            )

        if ChartType.SUMMARY_TABLE in config.chart_types:
            chart_map["SUMMARY_TABLE"] = self._chart_engine.render_summary_table(
                context, stats, title=name,
            )

        # Place charts according to template slots
        for slot_type, x, y, w, h in template.chart_slots:
            if slot_type in chart_map:
                chart_bytes = chart_map[slot_type]
                self._add_chart_image(layout, chart_bytes, (x, y, w, h))

        # --- Export ---
        output_path = self._export(layout, config, safe_name)

        # Cleanup layout
        self._project.layoutManager().removeLayout(layout)

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
        rect_mm: tuple[float, float, float, float],
    ) -> QgsLayoutItemPicture:
        """Write PNG bytes to a temp file and add as picture item."""
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(png_bytes)
        tmp.flush()
        tmp.close()

        pic = QgsLayoutItemPicture(layout)
        pic.setPicturePath(tmp.name)
        pic.attemptMove(QgsLayoutPoint(rect_mm[0], rect_mm[1]))
        pic.attemptResize(QgsLayoutSize(rect_mm[2], rect_mm[3]))
        pic.setResizeMode(QgsLayoutItemPicture.ZoomResizeFrame)

        layout.addLayoutItem(pic)
        return pic

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
