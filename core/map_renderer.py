"""Map renderer for AutoAtlas Pro.

Creates thematic maps (choropleth, categorical) within QGIS print layouts,
with automated legend, scale bar, north arrow, and title generation.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
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
    QgsRendererCategory,
    QgsSingleSymbolRenderer,
    QgsStyle,
    QgsSymbol,
    QgsUnitTypes,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont

from .models import MapStyle, GraduatedMode


class MapRenderer:
    """Renders thematic maps within a QgsPrintLayout.

    Supports choropleth (graduated) and categorical map styles,
    with automatic extent calculation per feature.
    """

    EXTENT_MARGIN_RATIO = 0.25

    def __init__(self, project: Optional[QgsProject] = None) -> None:
        self._project = project or QgsProject.instance()

    # ------------------------------------------------------------------
    # Render API
    # ------------------------------------------------------------------

    def apply_style(
        self,
        layer: QgsVectorLayer,
        style: MapStyle,
        field_name: str,
        color_ramp: str = "Spectral",
        # Detailed config
        graduated_mode: GraduatedMode = GraduatedMode.QUANTILE,
        classes: int = 5,
        single_color: str = "#3388FF",
        category_field: Optional[str] = None,
        opacity: float = 1.0,
    ) -> None:
        """Apply the specified map style to the vector layer.
        
        Args:
            layer: Target vector layer.
            style: Map styling mode (Single, Graduated, Categorized).
            field_name: Primary attribute field for visualization.
            color_ramp: Name of the QGIS color ramp to use.
            graduated_mode: Classification method for Graduated style.
            classes: Number of classes for Graduated style.
            single_color: Hex color string for Single Symbol style.
            category_field: Specific field for Categorized style (optional override).
            opacity: Layer opacity (0.0 to 1.0).
        """
        layer.setOpacity(opacity)
        
        if style == MapStyle.SINGLE:
            self._apply_single_symbol(layer, single_color)
        elif style == MapStyle.GRADUATED:
            self._apply_graduated_symbol(
                layer, field_name, graduated_mode, classes, color_ramp
            )
        elif style == MapStyle.CATEGORIZED:
            # Use specific category field if provided, else fallback to indicator
            target_field = category_field if category_field else field_name
            self._apply_categorized_symbol(layer, target_field, color_ramp)
        
        layer.triggerRepaint()

    def _apply_single_symbol(self, layer: QgsVectorLayer, color_hex: str) -> None:
        """Apply single symbol renderer with specified color."""
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        if symbol:
            symbol.setColor(QColor(color_hex))
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)

    def _apply_graduated_symbol(
        self,
        layer: QgsVectorLayer,
        field_name: str,
        mode: GraduatedMode,
        classes: int,
        ramp_name: str,
    ) -> None:
        """Apply graduated symbol renderer using specified classification mode."""
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        ramp = QgsStyle.defaultStyle().colorRamp(ramp_name)
        if not ramp:
            ramp = QgsStyle.defaultStyle().colorRamp("Spectral")

        renderer = QgsGraduatedSymbolRenderer()
        renderer.setClassAttribute(field_name)
        renderer.setSourceSymbol(symbol)
        renderer.setSourceColorRamp(ramp)
        
        # Map GraduatedMode enum to QgsGraduatedSymbolRenderer constants
        qgis_mode = QgsGraduatedSymbolRenderer.Quantile
        if mode == GraduatedMode.EQUAL_INTERVAL:
            qgis_mode = QgsGraduatedSymbolRenderer.EqualInterval
        elif mode == GraduatedMode.JENKS:
            qgis_mode = QgsGraduatedSymbolRenderer.Jenks
        elif mode == GraduatedMode.PRETTY:
            qgis_mode = QgsGraduatedSymbolRenderer.Pretty
            
        renderer.setMode(qgis_mode)
        renderer.updateClasses(layer, classes)
        
        layer.setRenderer(renderer)

    def _apply_categorized_symbol(
        self,
        layer: QgsVectorLayer,
        field_name: str,
        ramp_name: str,
    ) -> None:
        """Apply categorized renderer with unique values from field."""
        categories = []
        unique_values = set()
        
        idx = layer.fields().indexOf(field_name)
        if idx != -1:
            unique_values = layer.uniqueValues(idx)
        
        try:
            sorted_values = sorted(unique_values)
        except TypeError:
            # Fallback for mixed types that cannot be sorted
            sorted_values = list(unique_values)

        ramp = QgsStyle.defaultStyle().colorRamp(ramp_name)
        if not ramp and ramp_name != "Random":
             ramp = QgsStyle.defaultStyle().colorRamp("Spectral")

        for i, val in enumerate(sorted_values):
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            
            if ramp_name == "Random":
                from random import randint
                color = QColor(randint(0, 255), randint(0, 255), randint(0, 255))
                symbol.setColor(color)
            elif ramp and len(sorted_values) > 1:
                color = ramp.color(i / max(len(sorted_values) - 1, 1))
                symbol.setColor(color)
            
            label_val = str(val) if val is not None else ""
            categories.append(QgsRendererCategory(val, symbol, label_val))

        renderer = QgsCategorizedSymbolRenderer(field_name, categories)
        layer.setRenderer(renderer)

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
        max_width_mm: float = 0.0,
        columns: int = 1,
    ) -> QgsLayoutItemLegend:
        """Add a legend linked to a map item.

        Args:
            layout: Target print layout.
            map_item: Map item the legend references.
            pos_mm: (x, y) position in mm.
            title: Optional title for the legend.
            layers: If set, only show these layers (excludes all others).
            max_width_mm: If > 0, constrain legend width to this value.
            columns: Number of columns for the legend layout.

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

        # Configure columns but prevent splitting individual layers (keeps ramps vertical)
        legend.setColumnCount(columns)
        legend.setSplitLayer(False)

        # ── Responsive font hierarchy ──
        n = len(layers) if layers else 1
        if n <= 3:
            t_sz, sub_sz, sym_sz = 11, 9, 8
        elif n <= 6:
            t_sz, sub_sz, sym_sz = 10, 8, 7
        else:
            t_sz, sub_sz, sym_sz = 9, 7, 6

        legend.setStyleFont(QgsLegendStyle.Title, QFont("Arial", t_sz, QFont.Bold))
        legend.setStyleFont(QgsLegendStyle.Subgroup, QFont("Arial", sub_sz))
        legend.setStyleFont(QgsLegendStyle.SymbolLabel, QFont("Arial", sym_sz))

        # Transparent background (parent will provide bg panel)
        legend.setBackgroundEnabled(False)
        legend.setFrameEnabled(False)

        # Constrain width so text wraps inside the legend panel
        if max_width_mm > 0:
            legend.setResizeToContents(False)
            legend.attemptResize(
                QgsLayoutSize(max_width_mm, 200, Qgis.LayoutUnit.Millimeters)
            )

        layout.addLayoutItem(legend)
        return legend

    def add_scale_bar(
        self,
        layout: QgsPrintLayout,
        map_item: QgsLayoutItemMap,
        pos_mm: Tuple[float, float],
    ) -> QgsLayoutItemScaleBar:
        """Add a scale bar linked to a map item.

        The bar auto-sizes relative to the map extent, capping its
        physical width so it never dominates the layout.
        """
        scale_bar = QgsLayoutItemScaleBar(layout)
        scale_bar.setLinkedMap(map_item)
        scale_bar.attemptMove(QgsLayoutPoint(pos_mm[0], pos_mm[1]))
        scale_bar.setStyle("Single Box")
        scale_bar.setNumberOfSegmentsLeft(0)

        # ── Compute extent width in metres ──
        extent = map_item.extent()
        extent_width = extent.width()

        crs = map_item.crs()
        if crs.isValid() and crs.mapUnits() == QgsUnitTypes.DistanceDegrees:
            extent_width_m = extent_width * 111000
        else:
            extent_width_m = extent_width

        # ── Pick a clean segment size (~15% of extent) ──
        target = extent_width_m * 0.15
        nice_values = [
            0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500,
            1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000,
        ]
        seg_size = min(nice_values, key=lambda v: abs(v - target))

        # ── Determine how many segments fit within ~25% of map width on paper ──
        map_width_mm = map_item.rect().width()
        max_bar_width_mm = min(map_width_mm * 0.25, 60.0)  # cap at 60mm

        # Metres per mm on paper
        m_per_mm = extent_width_m / map_width_mm if map_width_mm > 0 else 1.0
        seg_width_mm = seg_size / m_per_mm if m_per_mm > 0 else 30.0

        # Scale down segments if too wide, up if too narrow
        num_segments = max(1, min(4, int(max_bar_width_mm / seg_width_mm)))

        scale_bar.setNumberOfSegments(num_segments)

        if seg_size >= 1000:
            scale_bar.setUnitsPerSegment(seg_size)
            scale_bar.setMapUnitsPerScaleBarUnit(1000)
            scale_bar.setUnitLabel("km")
        else:
            scale_bar.setUnitsPerSegment(seg_size)
            scale_bar.setMapUnitsPerScaleBarUnit(1)
            scale_bar.setUnitLabel("m")

        # ── Constrain physical height for compactness ──
        scale_bar.setHeight(2.0)  # mm

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
        """Create a transient memory layer highlighting the geometry.

        Supports Polygon, LineString, and Point geometries.
        """
        from qgis.core import (
            QgsFeature, QgsFillSymbol, QgsLineSymbol,
            QgsMarkerSymbol, QgsVectorLayer, QgsWkbTypes,
        )

        if not geometry or geometry.isEmpty():
            return None

        # Detect geometry type for the memory layer URI and symbol
        geom_type = QgsWkbTypes.geometryType(geometry.wkbType())
        is_multi = QgsWkbTypes.isMultiType(geometry.wkbType())

        if geom_type == QgsWkbTypes.PolygonGeometry:
            uri_type = "MultiPolygon" if is_multi else "Polygon"
        elif geom_type == QgsWkbTypes.LineGeometry:
            uri_type = "MultiLineString" if is_multi else "LineString"
        elif geom_type == QgsWkbTypes.PointGeometry:
            uri_type = "MultiPoint" if is_multi else "Point"
        else:
            return None

        # Create memory layer
        uri = f"{uri_type}?crs={crs.authid()}"
        layer = QgsVectorLayer(uri, "Highlight", "memory")
        if not layer.isValid():
            return None

        prov = layer.dataProvider()
        feat = QgsFeature()
        feat.setGeometry(geometry)
        prov.addFeatures([feat])
        layer.updateExtents()

        # Apply symbol based on geometry type
        if geom_type == QgsWkbTypes.PolygonGeometry:
            symbol = QgsFillSymbol.createSimple({
                "color": "0,0,0,0",
                "outline_color": color,
                "outline_style": "dash",
                "outline_width": str(width),
            })
        elif geom_type == QgsWkbTypes.LineGeometry:
            symbol = QgsLineSymbol.createSimple({
                "color": color,
                "width": str(width * 2),
                "line_style": "dash",
            })
        else:  # Point
            symbol = QgsMarkerSymbol.createSimple({
                "color": color,
                "size": str(max(width * 5, 3.0)),
                "outline_color": color,
                "outline_width": "0.5",
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

    @staticmethod
    def _build_filter_expression(feature_id: object, id_field: str) -> str:
        """Build a QGIS expression to select a specific feature by ID."""
        if isinstance(feature_id, (int, float)):
            return f'"{id_field}" = {feature_id}'
        else:
            # Escape single quotes in string values
            safe_id = str(feature_id).replace("'", "''")
            return f'"{id_field}" = \'{safe_id}\''

    def _get_feature_extent(
        self,
        layer: QgsVectorLayer,
        id_field: str,
        feature_id: object,
    ) -> QgsRectangle:
        """Calculate a padded extent centered on a specific feature.

        Handles both numeric and string feature IDs correctly.
        """
        expr = self._build_filter_expression(feature_id, id_field)

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
        """Apply a graduated renderer.

        Opacity is applied per-symbol fill (alpha channel) so polygon
        borders remain fully opaque and always visible.
        """
        from qgis.PyQt.QtGui import QColor as _QColor

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

        alpha = int(opacity * 255)
        ranges = []
        for i in range(num_classes):
            lower = min_val + i * interval
            upper = min_val + (i + 1) * interval
            if i == num_classes - 1:
                upper = max_val

            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            if ramp:
                color = ramp.color(i / max(num_classes - 1, 1))
                color.setAlpha(alpha)
                symbol.setColor(color)

            # Keep borders opaque so adjacent polygons are always visible
            sl = symbol.symbolLayer(0)
            if sl:
                sl.setStrokeColor(_QColor(80, 80, 80, 255))
                sl.setStrokeWidth(0.2)

            label = f"{lower:,.1f} - {upper:,.1f}"
            ranges.append(QgsRendererRange(lower, upper, symbol, label))

        renderer = QgsGraduatedSymbolRenderer(field_name, ranges)
        layer.setRenderer(renderer)
        # Reset layer-level opacity to 1.0 (transparency is handled per-symbol)
        layer.setOpacity(1.0)
        layer.triggerRepaint()
