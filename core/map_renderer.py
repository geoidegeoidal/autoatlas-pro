"""Map renderer for AutoAtlas Pro.

Creates thematic maps (choropleth, categorical) within QGIS print layouts,
with automated legend, scale bar, north arrow, and title generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

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

    # Default margin around the feature extent (as fraction of extent size)
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
        """Add a choropleth (graduated) map to the layout.

        Args:
            layout: Target print layout.
            layer: Vector layer to render.
            field_name: Numeric field for graduated symbology.
            color_ramp_name: Name of a QGIS style color ramp.
            rect_mm: (x, y, width, height) in millimeters for the map item.
            feature_id: If provided, center the map on this feature.
            id_field: Field name for identifying the feature to center on.
            num_classes: Number of graduated classes.

        Returns:
            The created QgsLayoutItemMap.
        """
        # Apply graduated renderer to the layer
        self._apply_graduated_renderer(layer, field_name, color_ramp_name, num_classes)

        # Create map item
        map_item = self._create_map_item(layout, rect_mm)

        # Set extent
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
        """Add a categorical map to the layout.

        Args:
            layout: Target print layout.
            layer: Vector layer to render.
            field_name: Categorical field for unique value symbology.
            rect_mm: (x, y, width, height) in mm.
            feature_id: If provided, center the map on this feature.
            id_field: Field name for identifying the feature.

        Returns:
            The created QgsLayoutItemMap.
        """
        self._apply_categorical_renderer(layer, field_name)

        map_item = self._create_map_item(layout, rect_mm)

        if feature_id is not None and id_field:
            extent = self._get_feature_extent(layer, id_field, feature_id)
        else:
            extent = layer.extent()

        map_item.setExtent(extent)
        map_item.setLayers([layer])

        return map_item

    @staticmethod
    def _apply_categorical_renderer(
        layer: QgsVectorLayer,
        field_name: str,
    ) -> None:
        """Apply a categorized renderer to the layer.

        Uses Spectral color ramp for unique values.
        """
        from qgis.core import QgsCategorizedSymbolRenderer, QgsRendererCategory

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
        """Add a title label to the layout.

        Args:
            layout: Target print layout.
            text: Title text.
            rect_mm: (x, y, w, h) in mm.
            font_size: Font point size.
            bold: Whether to use bold font.
            alignment: Text alignment.

        Returns:
            The created label item.
        """
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
    ) -> QgsLayoutItemLegend:
        """Add a legend linked to a map item.

        Args:
            layout: Target print layout.
            map_item: Map item the legend references.
            pos_mm: (x, y) position in mm.
            title: Optional title for the legend.

        Returns:
            The created legend item.
        """
        legend = QgsLayoutItemLegend(layout)
        legend.setLinkedMap(map_item)
        legend.attemptMove(QgsLayoutPoint(pos_mm[0], pos_mm[1]))
        legend.setAutoUpdateModel(True)
        if title:
            legend.setTitle(title)

        layout.addLayoutItem(legend)
        return legend

    def add_scale_bar(
        self,
        layout: QgsPrintLayout,
        map_item: QgsLayoutItemMap,
        pos_mm: Tuple[float, float],
    ) -> QgsLayoutItemScaleBar:
        """Add a scale bar linked to a map item.

        Args:
            layout: Target print layout.
            map_item: Map item the scale bar references.
            pos_mm: (x, y) position in mm.

        Returns:
            The created scale bar item.
        """
        scale_bar = QgsLayoutItemScaleBar(layout)
        scale_bar.setLinkedMap(map_item)
        scale_bar.attemptMove(QgsLayoutPoint(pos_mm[0], pos_mm[1]))
        scale_bar.setStyle("Single Box")
        scale_bar.setNumberOfSegments(4)
        scale_bar.setNumberOfSegmentsLeft(0)
        scale_bar.setUnitsPerSegment(1000)
        scale_bar.setMapUnitsPerScaleBarUnit(1000)
        scale_bar.setUnitLabel("km")

        layout.addLayoutItem(scale_bar)
        return scale_bar

    def add_north_arrow(
        self,
        layout: QgsPrintLayout,
        rect_mm: Tuple[float, float, float, float],
    ) -> QgsLayoutItemPicture:
        """Add a north arrow to the layout.

        Args:
            layout: Target print layout.
            rect_mm: (x, y, w, h) in mm.

        Returns:
            The created picture item.
        """
        from qgis.core import QgsApplication
        import os

        arrow = QgsLayoutItemPicture(layout)
        arrow.attemptMove(QgsLayoutPoint(rect_mm[0], rect_mm[1]))
        arrow.attemptResize(QgsLayoutSize(rect_mm[2], rect_mm[3]))

        # Find default north arrow
        svg_path = ""
        for path in QgsApplication.svgPaths():
            candidate = os.path.join(path, "north_arrows", "layout_default_north_arrow.svg")
            if os.path.exists(candidate):
                svg_path = candidate
                break
        
        if not svg_path:
             # Fallback check for common "arrows" folder if "north_arrows" fails
             for path in QgsApplication.svgPaths():
                candidate = os.path.join(path, "arrows", "NorthArrow_02.svg") # Common in older QGIS
                if os.path.exists(candidate):
                    svg_path = candidate
                    break

        if svg_path:
            arrow.setPicturePath(svg_path)
            
        layout.addLayoutItem(arrow)
        return arrow

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

        Args:
            layer: Source layer.
            id_field: Field to match feature_id against.
            feature_id: The value to match.

        Returns:
            QgsRectangle with margin applied.
        """
        request = QgsFeatureRequest().setFilterExpression(
            f'"{id_field}" = \'{feature_id}\''
        )
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
        color_ramp_name: str,
        num_classes: int,
    ) -> None:
        """Apply a graduated (choropleth) renderer to the layer.

        Uses equal interval classification with the specified color ramp.
        """
        idx = layer.fields().indexFromName(field_name)
        if idx < 0:
            return

        # Get values for range computation
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

        ramp = QgsStyle.defaultStyle().colorRamp(color_ramp_name)
        if not ramp:
            ramp = QgsStyle.defaultStyle().colorRamp("Spectral")

        ranges = []
        for i in range(num_classes):
            lower = min_val + i * interval
            upper = min_val + (i + 1) * interval
            if i == num_classes - 1:
                upper = max_val  # ensure last class captures max

            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            if ramp:
                color = ramp.color(i / max(num_classes - 1, 1))
                symbol.setColor(color)

            label = f"{lower:,.1f} - {upper:,.1f}"
            ranges.append(QgsRendererRange(lower, upper, symbol, label))

        renderer = QgsGraduatedSymbolRenderer(field_name, ranges)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
