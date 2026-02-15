"""Report composer for AutoAtlas Pro.

Orchestrates the full pipeline: data engine → map renderer → PDF/PNG.
Designed for stability: caches shared data, reuses renderers, cleans temp files,
and yields control to the event loop between reports to keep QGIS responsive.
"""

from __future__ import annotations

import gc
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

from qgis.core import (
    Qgis,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemMap,
    QgsLayoutItemPicture,
    QgsLayoutItemShape,
    QgsLayoutMeasurement,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import QApplication

from .chart_engine import ChartEngine
from .data_engine import DataEngine
from .map_renderer import MapRenderer
from .models import (
    BaseMapType,
    ChartType,
    MapStyle,
    OutputFormat,
    ReportConfig,
    TemplateConfig,
)

# ---------------------------------------------------------------------------
# XYZ Tile URL registry
# ---------------------------------------------------------------------------
_BASE_MAP_URLS: Dict[BaseMapType, Tuple[str, str, str]] = {
    # type → (url_template, zmax, zmin)
    BaseMapType.OSM: (
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "19", "0",
    ),
    BaseMapType.POSITRON: (
        "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png", "20", "0",
    ),
    BaseMapType.DARK_MATTER: (
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png", "20", "0",
    ),
    BaseMapType.GOOGLE_MAPS: (
        "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", "19", "0",
    ),
    BaseMapType.GOOGLE_SATELLITE: (
        "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", "19", "0",
    ),
    BaseMapType.GOOGLE_HYBRID: (
        "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", "19", "0",
    ),
    BaseMapType.ESRI_SATELLITE: (
        "https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}", "17", "0",
    ),
    BaseMapType.ESRI_STREET: (
        "https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Street_Map/MapServer/tile/{z}/{y}/{x}", "17", "0",
    ),
    BaseMapType.ESRI_TOPOGRAPHY: (
        "https://services.arcgisonline.com/ArcGIS/rest/services/"
        "World_Topo_Map/MapServer/tile/{z}/{y}/{x}", "20", "0",
    ),
    BaseMapType.BING_SATELLITE: (
        "http://ecn.t3.tiles.virtualearth.net/tiles/a{q}.jpeg?g=1", "19", "1",
    ),
}

# ---------------------------------------------------------------------------
# Default template — Premium "Atlas Pro" layout (A4 Landscape)
# ---------------------------------------------------------------------------
_DEFAULT_TEMPLATE = TemplateConfig(
    name="atlas_pro",
    display_name="Atlas Pro",
    page_width_mm=297.0,
    page_height_mm=210.0,
    # Map fills the main area leaving room for header, footer, and legend column
    map_rect=(8.0, 32.0, 225.0, 166.0),
    chart_slots=[],
    title_rect=(8.0, 4.0, 281.0, 14.0),
    subtitle_rect=(8.0, 17.0, 281.0, 10.0),
    north_arrow_rect=(218.0, 34.0, 12.0, 12.0),
    color_palette={
        "header_bg": "#1B2838",
        "footer_bg": "#1B2838",
        "title_color": "#FFFFFF",
        "subtitle_color": "#A8DADC",
        "footer_color": "#8899AA",
        "map_border": "#2C3E50",
        "legend_bg": "#F8F9FA",
    },
    font_family="Arial",
)


class ReportComposer:
    """Orchestrates report generation for all territorial units."""

    def __init__(self, project: Optional[QgsProject] = None) -> None:
        self._project = project or QgsProject.instance()
        self._data_engine = DataEngine()
        self._map_renderer = MapRenderer(self._project)
        self._chart_engine = ChartEngine(use_plotly=False, dark_theme=False)

    # ------------------------------------------------------------------
    # Batch generation
    # ------------------------------------------------------------------

    def generate_batch(
        self,
        config: ReportConfig,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Path]:
        """Generate reports for all (or specified) features."""
        layer = self._resolve_layer(config.layer_id)
        self._data_engine.load(
            layer, config.id_field, config.name_field, config.indicator_fields
        )

        feature_ids = config.feature_ids or self._data_engine.feature_ids
        total = len(feature_ids)
        output_paths: List[Path] = []

        config.output_dir.mkdir(parents=True, exist_ok=True)

        primary_field = config.indicator_fields[0]

        # ── Apply renderer ONCE ──
        self._apply_renderer(layer, config, primary_field)

        stats = self._data_engine.compute_stats(primary_field)
        ranking = self._data_engine.compute_ranking(primary_field, ascending=False)

        template = config.template or _DEFAULT_TEMPLATE

        # ── Pre-create base map layer ONCE (shared across batch) ──
        base_layer = self._create_base_map_layer(config.base_map)

        errors: Dict[str, int] = {}

        for i, fid in enumerate(feature_ids):
            name = self._data_engine._names_cache.get(fid, str(fid))

            if progress_callback:
                progress_callback(i + 1, total, name)

            QApplication.processEvents()

            try:
                path = self._generate_single(
                    config, layer, template, fid, name,
                    primary_field, stats, ranking, base_layer,
                )
                output_paths.append(path)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                msg = str(exc)
                errors[msg] = errors.get(msg, 0) + 1
                continue

            if i > 0 and i % 10 == 0:
                gc.collect()

        return output_paths

    # ------------------------------------------------------------------
    # Preview generation
    # ------------------------------------------------------------------

    def generate_preview(self, config: ReportConfig) -> Path:
        """Generate a single preview report (first feature) as PNG."""
        layer = self._resolve_layer(config.layer_id)
        self._data_engine.load(
            layer, config.id_field, config.name_field, config.indicator_fields
        )

        primary_field = config.indicator_fields[0]
        self._apply_renderer(layer, config, primary_field)

        stats = self._data_engine.compute_stats(primary_field)
        ranking = self._data_engine.compute_ranking(primary_field, ascending=False)

        fids = self._data_engine.feature_ids
        if not fids:
            raise ValueError("Layer has no features.")
        target_fid = fids[0]
        name = self._data_engine._names_cache.get(target_fid, str(target_fid))

        preview_config = ReportConfig(
            layer_id=config.layer_id,
            id_field=config.id_field,
            name_field=config.name_field,
            indicator_fields=config.indicator_fields,
            map_style=config.map_style,
            color_ramp_name=config.color_ramp_name,
            chart_types=config.chart_types,
            template=config.template or _DEFAULT_TEMPLATE,
            output_format=OutputFormat.PNG,
            output_dir=Path(tempfile.gettempdir()),
            dpi=96,
            base_map=config.base_map,
            variable_alias=config.variable_alias,
        )

        base_layer = self._create_base_map_layer(preview_config.base_map)

        return self._generate_single(
            preview_config, layer, preview_config.template,
            target_fid, f"preview_{name}",
            primary_field, stats, ranking, base_layer,
        )

    # ------------------------------------------------------------------
    # Single report (core layout engine)
    # ------------------------------------------------------------------

    def _generate_single(
        self,
        config: ReportConfig,
        layer: QgsVectorLayer,
        template: TemplateConfig,
        feature_id: Any,
        name: str,
        primary_field: str,
        stats: Any,
        ranking: Any,
        base_layer: Optional[QgsRasterLayer] = None,
    ) -> Path:
        """Generate a single report page with premium layout."""

        safe_name = self._sanitize_filename(name)
        palette = template.color_palette or _DEFAULT_TEMPLATE.color_palette

        # ── Create layout ──
        layout = QgsPrintLayout(self._project)
        layout.initializeDefaults()

        page = layout.pageCollection().page(0)
        page.setPageSize(
            QgsLayoutSize(template.page_width_mm, template.page_height_mm)
        )

        pw = template.page_width_mm  # 297
        ph = template.page_height_mm  # 210

        # ══════════════════════════════════════════════════════════════
        # 1. HEADER BAND — dark bar with title & subtitle
        # ══════════════════════════════════════════════════════════════
        header_h = 28.0
        self._add_rect(layout, (0, 0, pw, header_h), palette.get("header_bg", "#1B2838"))

        # Title — feature name, white, bold, centered
        self._add_label(
            layout, name,
            rect_mm=(0, 3, pw, 14),
            font_size=20, bold=True,
            halign=Qt.AlignCenter, valign=Qt.AlignVCenter,
            color=palette.get("title_color", "#FFFFFF"),
        )

        # Subtitle — variable alias or field name
        subtitle = config.variable_alias or primary_field
        self._add_label(
            layout, subtitle,
            rect_mm=(0, 16, pw, 10),
            font_size=11, bold=False,
            halign=Qt.AlignCenter, valign=Qt.AlignVCenter,
            color=palette.get("subtitle_color", "#A8DADC"),
        )

        # ══════════════════════════════════════════════════════════════
        # 2. MAP — fills main area
        # ══════════════════════════════════════════════════════════════
        map_x, map_y = 8.0, header_h + 4  # 32
        map_w, map_h = 225.0, 166.0
        footer_h = 12.0
        map_h = ph - map_y - footer_h - 4  # dynamic fill

        map_item = self._map_renderer._create_map_item(
            layout, (map_x, map_y, map_w, map_h)
        )

        # Extent — calculated in LAYER CRS (no explicit setCrs needed,
        # map item inherits project CRS and QGIS reprojects on-the-fly)
        extent = self._map_renderer._get_feature_extent(
            layer, config.id_field, feature_id
        )
        map_item.setExtent(extent)

        # Layers: FIRST = on TOP visually, LAST = on BOTTOM
        # Coverage (choropleth) must be on top so it's visible over the base map
        layers_for_map = [layer]
        if base_layer and base_layer.isValid():
            layers_for_map = [layer, base_layer]  # coverage on top, base on bottom

        map_item.setLayers(layers_for_map)
        map_item.setKeepLayerSet(True)      # LOCK the custom layer set
        map_item.setKeepLayerStyles(True)   # LOCK the renderer styles

        # Map border
        map_item.setFrameEnabled(True)
        map_item.setFrameStrokeColor(QColor(palette.get("map_border", "#2C3E50")))
        map_item.setFrameStrokeWidth(
            QgsLayoutMeasurement(0.4, Qgis.LayoutUnit.Millimeters)
        )

        # ══════════════════════════════════════════════════════════════
        # 3. LEGEND — right column with background panel
        # ══════════════════════════════════════════════════════════════
        legend_x = map_x + map_w + 4  # right of map
        legend_y = map_y
        legend_w = pw - legend_x - 4
        legend_h = map_h

        # Legend background panel
        self._add_rect(
            layout, (legend_x - 1, legend_y - 1, legend_w + 2, legend_h + 2),
            palette.get("legend_bg", "#F8F9FA"), border_color="#DEE2E6",
        )

        legend_title = config.variable_alias or primary_field
        self._map_renderer.add_legend(
            layout, map_item, (legend_x + 2, legend_y + 2),
            title=legend_title, layers=[layer],
        )

        # ══════════════════════════════════════════════════════════════
        # 4. NORTH ARROW — inside map, top-right
        # ══════════════════════════════════════════════════════════════
        na_size = 10.0
        self._map_renderer.add_north_arrow(
            layout, (map_x + map_w - na_size - 3, map_y + 3, na_size, na_size)
        )

        # ══════════════════════════════════════════════════════════════
        # 5. SCALE BAR — inside map, bottom-left
        # ══════════════════════════════════════════════════════════════
        self._map_renderer.add_scale_bar(
            layout, map_item,
            (map_x + 5, map_y + map_h - 12),
        )

        # ══════════════════════════════════════════════════════════════
        # 6. FOOTER BAND — credit line
        # ══════════════════════════════════════════════════════════════
        footer_y = ph - footer_h
        self._add_rect(layout, (0, footer_y, pw, footer_h), palette.get("footer_bg", "#1B2838"))

        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        footer_text = f"AutoAtlas Pro  •  {date_str}  •  {subtitle}"
        self._add_label(
            layout, footer_text,
            rect_mm=(8, footer_y + 1, pw - 16, footer_h - 2),
            font_size=7, bold=False,
            halign=Qt.AlignCenter, valign=Qt.AlignVCenter,
            color=palette.get("footer_color", "#8899AA"),
        )

        # ══════════════════════════════════════════════════════════════
        # 7. EXPORT
        # ══════════════════════════════════════════════════════════════
        output_path = self._export(layout, config, safe_name)

        layout.clear()
        del layout

        return output_path

    # ------------------------------------------------------------------
    # Renderer helper
    # ------------------------------------------------------------------

    def _apply_renderer(
        self, layer: QgsVectorLayer, config: ReportConfig, primary_field: str,
    ) -> None:
        """Apply the correct renderer to the layer."""
        if config.map_style == MapStyle.CHOROPLETH:
            self._map_renderer._apply_graduated_renderer(
                layer, primary_field, config.color_ramp_name, num_classes=5
            )
        elif config.map_style == MapStyle.CATEGORICAL:
            self._map_renderer._apply_categorical_renderer(layer, primary_field)

    # ------------------------------------------------------------------
    # Base Map — XYZ layer factory
    # ------------------------------------------------------------------

    @staticmethod
    def _create_base_map_layer(bm_type: BaseMapType) -> Optional[QgsRasterLayer]:
        """Create a QgsRasterLayer from an XYZ tile provider.

        The tile URL is percent-encoded so that ``&`` inside the URL
        is not confused with the ``type=xyz&url=...&zmax=...`` separator.
        """
        if bm_type is None or bm_type == BaseMapType.NONE:
            return None

        entry = _BASE_MAP_URLS.get(bm_type)
        if not entry:
            return None

        raw_url, zmax, zmin = entry

        # CRITICAL: encode the tile URL so & inside it doesn't break the URI
        encoded_url = quote(raw_url, safe="")
        uri = f"type=xyz&url={encoded_url}&zmax={zmax}&zmin={zmin}"

        layer = QgsRasterLayer(uri, bm_type.value, "wms")
        return layer if layer.isValid() else None

    # ------------------------------------------------------------------
    # Layout primitives
    # ------------------------------------------------------------------

    @staticmethod
    def _add_rect(
        layout: QgsPrintLayout,
        rect_mm: Tuple[float, float, float, float],
        fill_color: str,
        border_color: Optional[str] = None,
    ) -> QgsLayoutItemShape:
        """Add a filled rectangle (background band)."""
        shape = QgsLayoutItemShape(layout)
        shape.setShapeType(QgsLayoutItemShape.Rectangle)
        shape.attemptMove(QgsLayoutPoint(rect_mm[0], rect_mm[1]))
        shape.attemptResize(QgsLayoutSize(rect_mm[2], rect_mm[3]))

        symbol = shape.symbol()
        symbol.setColor(QColor(fill_color))
        if border_color:
            symbol.symbolLayer(0).setStrokeColor(QColor(border_color))
            symbol.symbolLayer(0).setStrokeWidth(0.3)
        else:
            symbol.symbolLayer(0).setStrokeColor(QColor(fill_color))
            symbol.symbolLayer(0).setStrokeWidth(0)
        shape.setSymbol(symbol)

        layout.addLayoutItem(shape)
        return shape

    @staticmethod
    def _add_label(
        layout: QgsPrintLayout,
        text: str,
        rect_mm: Tuple[float, float, float, float],
        font_size: int = 12,
        bold: bool = False,
        halign: int = Qt.AlignLeft,
        valign: int = Qt.AlignVCenter,
        color: str = "#000000",
    ) -> QgsLayoutItemLabel:
        """Add a styled text label to the layout."""
        label = QgsLayoutItemLabel(layout)
        label.setText(text)
        label.attemptMove(QgsLayoutPoint(rect_mm[0], rect_mm[1]))
        label.attemptResize(QgsLayoutSize(rect_mm[2], rect_mm[3]))

        font = QFont("Arial", font_size)
        font.setBold(bold)
        label.setFont(font)
        label.setHAlign(halign)
        label.setVAlign(valign)
        label.setFontColor(QColor(color))

        # Transparent background for labels
        label.setBackgroundEnabled(False)
        label.setFrameEnabled(False)

        layout.addLayoutItem(label)
        return label

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _resolve_layer(self, layer_id: str) -> QgsVectorLayer:
        """Resolve a QGIS layer by its ID."""
        layer = self._project.mapLayer(layer_id)
        if not layer or not isinstance(layer, QgsVectorLayer):
            raise ValueError(f"Layer '{layer_id}' not found or not a vector layer.")
        return layer

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Make a string safe for use as a filename."""
        keep = set(" ._-")
        return "".join(c if c.isalnum() or c in keep else "_" for c in name).strip()
