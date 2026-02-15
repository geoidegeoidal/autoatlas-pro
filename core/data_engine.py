"""Data engine for AutoAtlas Pro.

Loads vector layers, computes statistics, rankings, and per-feature
contextual information for report generation.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
from qgis.core import QgsVectorLayer

from .models import FeatureContext, FieldStats, RankEntry


class DataEngine:
    """Statistical computation engine over a QGIS vector layer.

    Usage:
        engine = DataEngine()
        engine.load(layer, id_field="CUT_COM", name_field="NOM_COM",
                     indicator_fields=["POB_TOTAL", "PCT_HOMBRES"])
        stats = engine.compute_stats("POB_TOTAL")
        ranking = engine.compute_ranking("POB_TOTAL")
        ctx = engine.get_feature_context(feature_id=13101, field="POB_TOTAL")
    """

    def __init__(self) -> None:
        self._layer: Optional[QgsVectorLayer] = None
        self._id_field: str = ""
        self._name_field: str = ""
        self._indicator_fields: List[str] = []
        self._data_cache: Dict[str, Dict[Any, float]] = {}
        self._names_cache: Dict[Any, str] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(
        self,
        layer: QgsVectorLayer,
        id_field: str,
        name_field: str,
        indicator_fields: List[str],
    ) -> None:
        """Load and cache data from the vector layer.

        Args:
            layer: Source vector layer with polygon geometries.
            id_field: Attribute field used as unique identifier per feature.
            name_field: Attribute field with display names.
            indicator_fields: List of numeric fields to analyze.

        Raises:
            ValueError: If the layer is invalid or fields are missing.
        """
        if not layer or not layer.isValid():
            raise ValueError("Invalid or null vector layer.")

        available_fields = {f.name() for f in layer.fields()}
        for fname in [id_field, name_field, *indicator_fields]:
            if fname not in available_fields:
                raise ValueError(
                    f"Field '{fname}' not found in layer '{layer.name()}'. "
                    f"Available: {sorted(available_fields)}"
                )

        self._layer = layer
        self._id_field = id_field
        self._name_field = name_field
        self._indicator_fields = list(indicator_fields)

        # Cache all data in a single pass for performance
        self._data_cache.clear()
        self._names_cache.clear()

        for field_name in indicator_fields:
            self._data_cache[field_name] = {}

        for feature in layer.getFeatures():
            fid = feature[id_field]
            self._names_cache[fid] = str(feature[name_field])
            for field_name in indicator_fields:
                raw_val = feature[field_name]
                if raw_val is not None and raw_val != "":
                    try:
                        self._data_cache[field_name][fid] = float(raw_val)
                    except (ValueError, TypeError):
                        pass  # Skip non-numeric values silently

    @property
    def feature_ids(self) -> List[Any]:
        """Return all cached feature IDs."""
        return list(self._names_cache.keys())

    @property
    def feature_count(self) -> int:
        """Return total number of features."""
        return len(self._names_cache)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def compute_stats(self, field_name: str, num_bins: int = 20) -> FieldStats:
        """Compute aggregated statistics for a single indicator field.

        Args:
            field_name: Name of the indicator field.
            num_bins: Number of histogram bins.

        Returns:
            FieldStats with all computed metrics.

        Raises:
            KeyError: If the field was not loaded.
        """
        if field_name not in self._data_cache:
            raise KeyError(
                f"Field '{field_name}' not loaded. "
                f"Loaded fields: {list(self._data_cache.keys())}"
            )

        values_dict = self._data_cache[field_name]
        if not values_dict:
            return FieldStats(
                field_name=field_name,
                count=0,
                min_val=0.0,
                max_val=0.0,
                mean=0.0,
                median=0.0,
                std=0.0,
            )

        arr = np.array(list(values_dict.values()), dtype=np.float64)

        percentile_keys = [5, 10, 25, 50, 75, 90, 95]
        percentile_values = np.percentile(arr, percentile_keys).tolist()
        percentiles = dict(zip(percentile_keys, percentile_values))

        counts, bin_edges = np.histogram(arr, bins=num_bins)

        return FieldStats(
            field_name=field_name,
            count=len(arr),
            min_val=float(np.min(arr)),
            max_val=float(np.max(arr)),
            mean=float(np.mean(arr)),
            median=float(np.median(arr)),
            std=float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
            percentiles=percentiles,
            histogram_bins=bin_edges.tolist(),
            histogram_counts=counts.tolist(),
        )

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def compute_ranking(
        self, field_name: str, ascending: bool = True
    ) -> List[RankEntry]:
        """Compute a ranked list of all features by indicator value.

        Args:
            field_name: Indicator field to rank by.
            ascending: If True, rank 1 = lowest value. If False, rank 1 = highest.

        Returns:
            Sorted list of RankEntry.

        Raises:
            KeyError: If the field was not loaded.
        """
        if field_name not in self._data_cache:
            raise KeyError(f"Field '{field_name}' not loaded.")

        values_dict = self._data_cache[field_name]

        items = [
            (fid, self._names_cache.get(fid, str(fid)), val)
            for fid, val in values_dict.items()
        ]
        items.sort(key=lambda x: x[2], reverse=not ascending)

        return [
            RankEntry(feature_id=fid, name=name, value=val, rank=i + 1)
            for i, (fid, name, val) in enumerate(items)
        ]

    # ------------------------------------------------------------------
    # Feature context
    # ------------------------------------------------------------------

    def get_feature_context(
        self, feature_id: Any, field_name: str
    ) -> FeatureContext:
        """Get contextual statistics for a single feature.

        Args:
            feature_id: ID of the feature to contextualize.
            field_name: Indicator field to analyze.

        Returns:
            FeatureContext with rank, deviation, percentile, etc.

        Raises:
            KeyError: If feature_id or field_name is not found.
        """
        if field_name not in self._data_cache:
            raise KeyError(f"Field '{field_name}' not loaded.")

        values_dict = self._data_cache[field_name]
        if feature_id not in values_dict:
            raise KeyError(
                f"Feature ID '{feature_id}' not found in field '{field_name}'."
            )

        value = values_dict[feature_id]
        name = self._names_cache.get(feature_id, str(feature_id))

        # Compute position
        all_values = np.array(list(values_dict.values()), dtype=np.float64)
        mean = float(np.mean(all_values))
        std = float(np.std(all_values, ddof=1)) if len(all_values) > 1 else 1.0

        deviation = (value - mean) / std if std > 0 else 0.0

        # Percentile: % of values <= this value
        percentile = float(np.sum(all_values <= value) / len(all_values) * 100)

        # Rank (descending — rank 1 = highest value)
        ranking = self.compute_ranking(field_name, ascending=False)
        rank = next(
            (r.rank for r in ranking if r.feature_id == feature_id),
            len(ranking),
        )

        return FeatureContext(
            feature_id=feature_id,
            name=name,
            value=value,
            rank=rank,
            total_features=len(values_dict),
            deviation_from_mean=round(deviation, 3),
            percentile=round(percentile, 1),
            is_max=bool(value == float(np.max(all_values))),
            is_min=bool(value == float(np.min(all_values))),
        )
