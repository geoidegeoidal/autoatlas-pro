"""Data models for AutoAtlas Pro.

All shared dataclasses used across the plugin: statistics, rankings,
report configuration, and template definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ======================================================================
# Enums
# ======================================================================


class MapStyle(Enum):
    """Available map rendering styles."""

    CHOROPLETH = auto()
    CATEGORICAL = auto()
    BIVARIATE = auto()


class BaseMapType(str, Enum):
    """Available base map providers."""

    NONE = "None"
    OSM = "OpenStreetMap"
    POSITRON = "CartoDB Positron"
    DARK_MATTER = "CartoDB Dark Matter"
    GOOGLE_MAPS = "Google Maps"
    GOOGLE_SATELLITE = "Google Satellite"
    GOOGLE_HYBRID = "Google Hybrid"
    ESRI_SATELLITE = "Esri Satellite"
    ESRI_STREET = "Esri Street Map"
    ESRI_TOPOGRAPHY = "Esri Topography"
    BING_SATELLITE = "Bing Satellite"


class ChartType(Enum):
    """Available chart types for reports."""

    DISTRIBUTION = auto()
    RANKING = auto()
    WAFFLE = auto()
    SUMMARY_TABLE = auto()


class OutputFormat(Enum):
    """Report output format."""

    PDF = auto()
    PNG = auto()


class DepStatus(Enum):
    """Dependency installation status."""

    INSTALLED = auto()
    MISSING = auto()
    INSTALLING = auto()
    ERROR = auto()


# ======================================================================
# Statistics
# ======================================================================


@dataclass(frozen=True)
class FieldStats:
    """Aggregated statistics for a single indicator field across all features.

    Attributes:
        field_name: Name of the attribute field.
        count: Number of non-null values.
        min_val: Minimum value.
        max_val: Maximum value.
        mean: Arithmetic mean.
        median: Median value.
        std: Standard deviation.
        percentiles: Dict mapping percentile (e.g., 25 → value).
        histogram_bins: Bin edges for histogram rendering.
        histogram_counts: Counts per histogram bin.
    """

    field_name: str
    count: int
    min_val: float
    max_val: float
    mean: float
    median: float
    std: float
    percentiles: Dict[int, float] = field(default_factory=dict)
    histogram_bins: List[float] = field(default_factory=list)
    histogram_counts: List[int] = field(default_factory=list)


@dataclass(frozen=True)
class RankEntry:
    """A single entry in a territorial ranking.

    Attributes:
        feature_id: Feature ID from the coverage layer.
        name: Display name of the territorial unit.
        value: Indicator value for this unit.
        rank: 1-indexed position in the ranking.
    """

    feature_id: Any
    name: str
    value: float
    rank: int


@dataclass(frozen=True)
class FeatureContext:
    """Contextual statistics for one feature within the full distribution.

    Attributes:
        feature_id: Feature ID.
        name: Display name of the territorial unit.
        value: Indicator value.
        rank: Position in ranking (1-indexed).
        total_features: Total number of features in the ranking.
        deviation_from_mean: How far this value is from the mean (in std units).
        percentile: Which percentile this value falls in.
        is_max: Whether this feature holds the maximum value.
        is_min: Whether this feature holds the minimum value.
    """

    feature_id: Any
    name: str
    value: float
    rank: int
    total_features: int
    deviation_from_mean: float
    percentile: float
    is_max: bool = False
    is_min: bool = False


# ======================================================================
# Configuration
# ======================================================================


@dataclass
class TemplateConfig:
    """Defines a report page template layout.

    Attributes:
        name: Template identifier (e.g., 'institutional').
        display_name: Human-readable name for the UI.
        page_width_mm: Page width in millimeters.
        page_height_mm: Page height in millimeters.
        map_rect: (x, y, width, height) in mm for the map item.
        chart_slots: List of (chart_type, x, y, w, h) for chart placement.
        title_rect: (x, y, w, h) for the title label.
        subtitle_rect: Optional (x, y, w, h) for subtitle.
        footer_rect: Optional (x, y, w, h) for footer.
        color_palette: Dict of named colors for the template theme.
        font_family: Primary font family name.
    """

    name: str
    display_name: str
    page_width_mm: float = 297.0  # A4 landscape
    page_height_mm: float = 210.0
    map_rect: Tuple[float, float, float, float] = (10.0, 30.0, 140.0, 160.0)
    chart_slots: List[Tuple[str, float, float, float, float]] = field(
        default_factory=list
    )
    title_rect: Tuple[float, float, float, float] = (10.0, 5.0, 277.0, 20.0)
    subtitle_rect: Optional[Tuple[float, float, float, float]] = None
    footer_rect: Optional[Tuple[float, float, float, float]] = None
    north_arrow_rect: Optional[Tuple[float, float, float, float]] = None
    color_palette: Dict[str, str] = field(default_factory=dict)
    font_family: str = "Arial"


@dataclass
class ReportConfig:
    """Full configuration for a report generation run.

    Attributes:
        layer_id: QGIS layer ID for the coverage layer.
        id_field: Field name used to identify each territorial unit.
        name_field: Field name for the display name of each unit.
        indicator_fields: List of attribute field names to analyze.
        map_style: Which map rendering approach to use.
        color_ramp_name: Name of the QGIS color ramp.
        chart_types: Which charts to include in each report page.
        template: Template layout configuration.
        output_format: PDF or PNG.
        output_dir: Directory to write report files.
        dpi: Resolution for rendered outputs.
        feature_ids: Optional subset of feature IDs to generate (None = all).
    """

    layer_id: str
    id_field: str
    name_field: str
    indicator_fields: List[str]
    map_style: MapStyle = MapStyle.CHOROPLETH
    color_ramp_name: str = "Spectral"
    chart_types: List[ChartType] = field(
        default_factory=lambda: [
            ChartType.DISTRIBUTION,
            ChartType.RANKING,
            ChartType.WAFFLE,
            ChartType.SUMMARY_TABLE,
        ]
    )
    template: Optional[TemplateConfig] = None
    output_format: OutputFormat = OutputFormat.PDF
    output_dir: Path = Path(".")
    dpi: int = 300
    feature_ids: Optional[List[Any]] = None
    feature_ids: Optional[List[Any]] = None
    variable_alias: str = ""
    base_map: BaseMapType = BaseMapType.NONE

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if not self.indicator_fields:
            raise ValueError("At least one indicator field is required.")
        if self.dpi < 72 or self.dpi > 1200:
            raise ValueError(f"DPI must be between 72 and 1200, got {self.dpi}.")
        self.output_dir = Path(self.output_dir)
