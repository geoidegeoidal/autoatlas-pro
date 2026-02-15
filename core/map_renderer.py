"""Map renderer for AutoAtlas Pro.

Creates thematic maps (choropleth, categorical) within QGIS print layouts,
with automated legend, scale bar, north arrow, and title generation.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from qgis.core import (
    QgsFeatureRequest,
    QgsGraduatedSymbolRenderer,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsLegendStyle,
    QgsMapLayer,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsRendererRange,
    QgsSimpleFillSymbolLayer,
    QgsStyle,
    QgsSymbol,
    QgsUnitTypes,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont

from .models import MapStyle


class MapRenderer:
    """Renders thematic maps within a QgsPrintLayout.

    Supports choropleth (graduated) and categorical map styles,
    with automatic extent calculation per feature.
    """

    EXTENT_MARGIN_RATIO = 0.25

    def __init__(self, project: Optional[QgsProject] = None) -> None:
        self._project = project or QgsProject.instance()

    # ------------------------------------------------------------------
    # Main render methods
    # ------------------------------------------------------------------

    def render_choropleth(
        self,
        layout: QgsPrintLayout,
        layer: QgsVectorLayer,
        field_name: str,
        color_ramp_name: str,
        rect_mm: Tuple[float, float, float, float],
        feature_id: object = None,
        id_field: str = "",
        num_classes: int = 5,
    ) -> QgsLayoutItemMap:
        """Add a choropleth (graduated) map to the layout."""
        self._apply_graduated_renderer(layer, field_name, color_ramp_name, num_classes)
        map_item = self._create_map_item(layout, rect_mm)

        if feature_id is not None and id_field:
            extent = self._get_feature_extent(layer, id_field, feature_id)
        else:
            extent = layer.extent()

        map_item.setExtent(extent)
        map_item.setLayers([layer])
        return map_item

    def render_categorical(
        self,
        layout: QgsPrintLayout,
        layer: QgsVectorLayer,
        field_name: str,
        rect_mm: Tuple[float, float, float, float],
        feature_id: object = None,
        id_field: str = "",
    ) -> QgsLayoutItemMap:
        """Add a categorical map to the layout."""
        self._apply_categorical_renderer(layer, field_name)
        map_item = self._create_map_item(layout, rect_mm)

        if feature_id is not None and id_field:
            extent = self._get_feature_extent(layer, id_field, feature_id)
        else:
            extent = layer.extent()

        map_item.setExtent(extent)
        map_item.setLayers([layer])
        map_item.setKeepLayerSet(True)
        map_item.setKeepLayerStyles(True)
        return map_item

    @staticmethod
    def _apply_categorical_renderer(
        layer: QgsVectorLayer,
        field_name: str,
        opacity: float = 1.0,
    ) -> None:
        """Apply a categorized renderer using Spectral color ramp."""
        from qgis.core import QgsCategorizedSymbolRenderer, QgsRendererCategory

        layer.setOpacity(opacity)
        categories = []
        unique_values = sorted(set(
            f[field_name]
            for f in layer.getFeatures()
            if f[field_name] is not None
        ))

        ramp = QgsStyle.defaultStyle().colorRamp("Spectral")
        for i, val in enumerate(unique_values):
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            if ramp and len(unique_values) > 1:
                color = ramp.color(i / max(len(unique_values) - 1, 1))
                symbol.setColor(color)
            categories.append(QgsRendererCategory(val, symbol, str(val)))

        renderer = QgsCategorizedSymbolRenderer(field_name, categories)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    # ------------------------------------------------------------------
    # Layout element helpers
    # ------------------------------------------------------------------

    def add_title(
        self,
        layout: QgsPrintLayout,
        text: str,
        rect_mm: Tuple[float, float, float, float],
        font_size: int = 18,
        bold: bool = True,
        alignment: Qt.AlignmentFlag = Qt.AlignCenter,
    ) -> QgsLayoutItemLabel:
        """Add a title label to the layout."""
        label = QgsLayoutItemLabel(layout)
        label.setText(text)
        label.attemptMove(QgsLayoutPoint(rect_mm[0], rect_mm[1]))
        label.attemptResize(QgsLayoutSize(rect_mm[2], rect_mm[3]))

        font = QFont("Arial", font_size)
        font.setBold(bold)
        label.setFont(font)
        label.setHAlign(alignment)

        layout.addLayoutItem(label)
        return label

    def add_legend(
        self,
        layout: QgsPrintLayout,
        map_item: QgsLayoutItemMap,
        pos_mm: Tuple[float, float],
        title: str = "",
        layers: Optional[List[QgsMapLayer]] = None,
    ) -> QgsLayoutItemLegend:
        """Add a legend linked to a map item.

        Args:
            layout: Target print layout.
            map_item: Map item the legend references.
            pos_mm: (x, y) position in mm.
            title: Optional title for the legend.
            layers: If set, only show these layers (excludes all others).

        Returns:
            The created legend item.
        """
        legend = QgsLayoutItemLegend(layout)
        legend.setLinkedMap(map_item)
        legend.attemptMove(QgsLayoutPoint(pos_mm[0], pos_mm[1]))

        if layers is not None:
            legend.setAutoUpdateModel(False)
            # Use the legend's OWN root group (C++ owned, safe from GC)
            root = legend.model().rootGroup()
            root.removeAllChildren()
            for lyr in layers:
                root.addLayer(lyr)
        else:
            legend.setAutoUpdateModel(True)

        if title:
            legend.setTitle(title)

        # ── Font hierarchy ──
        legend.setStyleFont(QgsLegendStyle.Title, QFont("Arial", 11, QFont.Bold))
        legend.setStyleFont(QgsLegendStyle.Subgroup, QFont("Arial", 9))
        legend.setStyleFont(QgsLegendStyle.SymbolLabel, QFont("Arial", 8))

        # Transparent background (parent will provide bg panel)
        legend.setBackgroundEnabled(False)
        legend.setFrameEnabled(False)

        layout.addLayoutItem(legend)
        return legend

    def add_scale_bar(
        self,
        layout: QgsPrintLayout,
        map_item: QgsLayoutItemMap,
        pos_mm: Tuple[float, float],
    ) -> QgsLayoutItemScaleBar:
        """Add a scale bar linked to a map item."""
        scale_bar = QgsLayoutItemScaleBar(layout)
        scale_bar.setLinkedMap(map_item)
        scale_bar.attemptMove(QgsLayoutPoint(pos_mm[0], pos_mm[1]))
        scale_bar.setStyle("Single Box")
        scale_bar.setNumberOfSegments(3)
        scale_bar.setNumberOfSegmentsLeft(0)

        # Auto-detect appropriate segment size from map extent
        extent = map_item.extent()
        extent_width = extent.width()  # in map CRS units

        # If CRS units are degrees, convert ~111km per degree
        crs = map_item.crs()
        if crs.isValid() and crs.mapUnits() == QgsUnitTypes.DistanceDegrees:
            extent_width_m = extent_width * 111000
        else:
            extent_width_m = extent_width

        # Pick a clean segment size (~1/5 of extent width)
        target = extent_width_m / 5
        # Round to nearest "nice" number
        nice_values = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500,
                       1000, 2000, 5000, 10000, 20000, 50000, 100000]
        seg_size = min(nice_values, key=lambda v: abs(v - target))

        if seg_size >= 1000:
            scale_bar.setUnitsPerSegment(seg_size)
            scale_bar.setMapUnitsPerScaleBarUnit(1000)
            scale_bar.setUnitLabel("km")
        else:
            scale_bar.setUnitsPerSegment(seg_size)
            scale_bar.setMapUnitsPerScaleBarUnit(1)
            scale_bar.setUnitLabel("m")

        # Style
        scale_bar.setFont(QFont("Arial", 7))
        scale_bar.setBackgroundEnabled(False)
        scale_bar.setFrameEnabled(False)

        layout.addLayoutItem(scale_bar)
        return scale_bar

    def add_north_arrow(
        self,
        layout: QgsPrintLayout,
        rect_mm: Tuple[float, float, float, float],
    ) -> QgsLayoutItemPicture:
        """Add a north arrow SVG to the layout."""
        from qgis.core import QgsApplication
        import os

        arrow = QgsLayoutItemPicture(layout)
        arrow.attemptMove(QgsLayoutPoint(rect_mm[0], rect_mm[1]))
        arrow.attemptResize(QgsLayoutSize(rect_mm[2], rect_mm[3]))

        # Search for north arrow SVG in QGIS installation
        svg_path = ""
        search_patterns = [
            ("arrows", "NorthArrow_02.svg"),
            ("arrows", "NorthArrow_01.svg"),
            ("north_arrows", "layout_default_north_arrow.svg"),
        ]
        for folder, filename in search_patterns:
            for base_path in QgsApplication.svgPaths():
                candidate = os.path.join(base_path, folder, filename)
                if os.path.exists(candidate):
                    svg_path = candidate
                    break
            if svg_path:
                break

        if svg_path:
            arrow.setPicturePath(svg_path)

        # Transparent background
        arrow.setBackgroundEnabled(False)
        arrow.setFrameEnabled(False)
        layout.addLayoutItem(arrow)
        return arrow

    # ------------------------------------------------------------------
    # Visual enhancements
    # ------------------------------------------------------------------

    @staticmethod
    def setup_labels(
        layer: QgsVectorLayer,
        field_name: str,
        font_size: int = 10,
        buffer_color: str = "#FFFFFF",
    ) -> None:
        """Configure simple labeling for the layer."""
        from qgis.core import (
            QgsPalLayerSettings,
            QgsTextBufferSettings,
            QgsTextFormat,
            QgsVectorLayerSimpleLabeling,
        )
        from qgis.PyQt.QtGui import QFont, QColor

        settings = QgsPalLayerSettings()
        settings.fieldName = field_name
        settings.placement = QgsPalLayerSettings.OverPoint

        text_format = QgsTextFormat()
        text_format.setFont(QFont("Arial", font_size))
        text_format.setColor(QColor("#000000"))

        buffer = QgsTextBufferSettings()
        buffer.setEnabled(True)
        buffer.setSize(1.0)
        buffer.setColor(QColor(buffer_color))
        text_format.setBuffer(buffer)

        settings.setFormat(text_format)

        layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        layer.setLabelsEnabled(True)

    @staticmethod
    def create_highlight_overlay(
        geometry: Any,  # QgsGeometry
        crs: Any,       # QgsCoordinateReferenceSystem
        color: str = "#FF00FF",
        width: float = 0.8,
    ) -> Optional[QgsVectorLayer]:
        """Create a transient memory layer highlighting the geometry."""
        from qgis.core import QgsFeature, QgsField, QgsFillSymbol, QgsVectorLayer
        from typing import Any, Optional

        if not geometry or geometry.isEmpty():
            return None

        # Create memory layer
        uri = f"Polygon?crs={crs.authid()}"
        layer = QgsVectorLayer(uri, "Highlight", "memory")
        if not layer.isValid():
            return None

        prov = layer.dataProvider()
        feat = QgsFeature()
        feat.setGeometry(geometry)
        prov.addFeatures([feat])
        layer.updateExtents()

        # Apply symbol: Transparent fill, dashed outline
        symbol = QgsFillSymbol.createSimple({
            "color": "0,0,0,0",  # Fully transparent fill
            "outline_color": color,
            "outline_style": "dash",
            "outline_width": str(width),
        })
        layer.renderer().setSymbol(symbol)
        
        return layer

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create_map_item(
        layout: QgsPrintLayout,
        rect_mm: Tuple[float, float, float, float],
    ) -> QgsLayoutItemMap:
        """Create a QgsLayoutItemMap at the given position and size."""
        map_item = QgsLayoutItemMap(layout)
        map_item.attemptMove(QgsLayoutPoint(rect_mm[0], rect_mm[1]))
        map_item.attemptResize(QgsLayoutSize(rect_mm[2], rect_mm[3]))
        layout.addLayoutItem(map_item)
        return map_item

    def _get_feature_extent(
        self,
        layer: QgsVectorLayer,
        id_field: str,
        feature_id: object,
    ) -> QgsRectangle:
        """Calculate a padded extent centered on a specific feature.

        Handles both numeric and string feature IDs correctly.
        """
        # Build filter expression that works for both numeric and string IDs
        if isinstance(feature_id, (int, float)):
            expr = f'"{id_field}" = {feature_id}'
        else:
            # Escape single quotes in string values
            safe_id = str(feature_id).replace("'", "''")
            expr = f'"{id_field}" = \'{safe_id}\''

        request = QgsFeatureRequest().setFilterExpression(expr)
        for feature in layer.getFeatures(request):
            geom = feature.geometry()
            if geom and not geom.isEmpty():
                bbox = geom.boundingBox()
                margin_x = bbox.width() * self.EXTENT_MARGIN_RATIO
                margin_y = bbox.height() * self.EXTENT_MARGIN_RATIO
                bbox.grow(max(margin_x, margin_y))
                return bbox

        # Fallback: entire layer extent
        return layer.extent()

    @staticmethod
    def _apply_graduated_renderer(
        layer: QgsVectorLayer,
        field_name: str,
        ramp_name: str,
        num_classes: int = 5,
        opacity: float = 1.0,
    ) -> None:
        """Apply a graduated renderer using standard deviation or quantiles."""
        layer.setOpacity(opacity)
        idx = layer.fields().indexFromName(field_name)
        if idx < 0:
            return

        values = []
        for feat in layer.getFeatures():
            val = feat[field_name]
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    continue

        if not values:
            return

        min_val = min(values)
        max_val = max(values)
        interval = (max_val - min_val) / num_classes if num_classes > 0 else 1.0

        ramp = QgsStyle.defaultStyle().colorRamp(ramp_name)
        if not ramp:
            ramp = QgsStyle.defaultStyle().colorRamp("Spectral")

        ranges = []
        for i in range(num_classes):
            lower = min_val + i * interval
            upper = min_val + (i + 1) * interval
            if i == num_classes - 1:
                upper = max_val

            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            if ramp:
                color = ramp.color(i / max(num_classes - 1, 1))
                symbol.setColor(color)

            label = f"{lower:,.1f} - {upper:,.1f}"
            ranges.append(QgsRendererRange(lower, upper, symbol, label))

        renderer = QgsGraduatedSymbolRenderer(field_name, ranges)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
