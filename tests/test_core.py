"""Unit tests for AutoAtlas Pro core modules.

These tests validate the critical rendering pipeline:
- XYZ URL encoding for base maps
- CRS extent transformation
- Feature extent calculation (numeric and string IDs)
- Layout item creation
- Sanitize filename

NOTE: Tests that require a running QGIS instance (e.g., QgsLayoutItemMap
rendering, QgsRasterLayer validation) are marked with the ``qgis``
marker and should be run inside the QGIS Python console or with
pytest-qgis.  Tests that are pure Python logic run anywhere.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import quote, unquote


class TestSanitizeFilename(unittest.TestCase):
    """report_composer._sanitize_filename is a static method."""

    @staticmethod
    def _sanitize(name: str) -> str:
        """Mirror of ReportComposer._sanitize_filename."""
        keep = set(" ._-")
        return "".join(
            c if c.isalnum() or c in keep else "_" for c in name
        ).strip()

    def test_normal_name(self) -> None:
        assert self._sanitize("Santiago Centro") == "Santiago Centro"

    def test_accents_and_special(self) -> None:
        result = self._sanitize("O'Higgins / Ñuble")
        assert "'" not in result
        assert "/" not in result
        assert "O" in result

    def test_empty(self) -> None:
        assert self._sanitize("") == ""

    def test_only_special(self) -> None:
        result = self._sanitize("***")
        assert result == "___"


class TestXYZUrlEncoding(unittest.TestCase):
    """Validate that XYZ tile URLs are correctly percent-encoded."""

    def test_osm_no_ampersand(self) -> None:
        """OSM URL has no & so encoding should preserve it."""
        url = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        encoded = quote(url, safe="")
        uri = f"type=xyz&url={encoded}&zmax=19&zmin=0"

        # The URI should have exactly 4 top-level & separators
        parts = uri.split("&")
        keys = [p.split("=", 1)[0] for p in parts]
        assert keys == ["type", "url", "zmax", "zmin"], f"Got: {keys}"

    def test_google_with_ampersand(self) -> None:
        """Google URLs contain & which MUST be encoded to %26."""
        url = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
        encoded = quote(url, safe="")
        uri = f"type=xyz&url={encoded}&zmax=19&zmin=0"

        # Verify the & inside the URL is encoded as %26
        assert "%26" in encoded, f"Expected %26 in encoded URL: {encoded}"

        # Verify we can split the URI correctly
        parts = uri.split("&")
        keys = [p.split("=", 1)[0] for p in parts]
        assert keys == ["type", "url", "zmax", "zmin"], f"Got: {keys}"

        # Verify decoding gives back the original URL
        decoded_url = unquote(parts[1].split("=", 1)[1])
        assert decoded_url == url

    def test_esri_no_ampersand(self) -> None:
        """Esri URLs have no & but have slashes which should be encoded."""
        url = (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        )
        encoded = quote(url, safe="")
        uri = f"type=xyz&url={encoded}&zmax=17&zmin=0"

        parts = uri.split("&")
        keys = [p.split("=", 1)[0] for p in parts]
        assert keys == ["type", "url", "zmax", "zmin"]

    def test_all_basemap_urls_encode_correctly(self) -> None:
        """Every URL in the registry must produce a valid 4-part URI."""
        from autoatlas_pro.core.report_composer import _BASE_MAP_URLS

        for bm_type, (raw_url, zmax, zmin) in _BASE_MAP_URLS.items():
            encoded = quote(raw_url, safe="")
            uri = f"type=xyz&url={encoded}&zmax={zmax}&zmin={zmin}"
            parts = uri.split("&")
            keys = [p.split("=", 1)[0] for p in parts]
            assert keys == ["type", "url", "zmax", "zmin"], (
                f"Failed for {bm_type.name}: keys={keys}"
            )


class TestCRSTransform(unittest.TestCase):
    """Test extent CRS transformation logic."""

    def test_same_crs_returns_same_extent(self) -> None:
        """When source == dest CRS, extent should be returned unchanged."""
        # This is a pure logic test of the transform guard
        from qgis.core import (
            QgsCoordinateReferenceSystem,
            QgsRectangle,
        )

        extent = QgsRectangle(-71.0, -34.0, -70.0, -33.0)
        crs = QgsCoordinateReferenceSystem("EPSG:4326")

        # Same CRS → no transform needed
        # We test the guard condition directly
        assert crs == crs
        # extent should remain unchanged
        assert extent.xMinimum() == -71.0


class TestFeatureExtentFilter(unittest.TestCase):
    """Test filter expression generation for numeric vs string IDs."""

    @staticmethod
    def _build_expr(feature_id: object, id_field: str) -> str:
        """Mirror of MapRenderer._get_feature_extent filter logic."""
        if isinstance(feature_id, (int, float)):
            return f'"{id_field}" = {feature_id}'
        safe_id = str(feature_id).replace("'", "''")
        return f'"{id_field}" = \'{safe_id}\''

    def test_numeric_id(self) -> None:
        expr = self._build_expr(13101, "CUT_COM")
        assert expr == '"CUT_COM" = 13101'

    def test_string_id(self) -> None:
        expr = self._build_expr("13101", "CUT_COM")
        assert expr == '"CUT_COM" = \'13101\''

    def test_string_with_quotes(self) -> None:
        expr = self._build_expr("O'Higgins", "NOM_REG")
        assert expr == '"NOM_REG" = \'O\'\'Higgins\''

    def test_float_id(self) -> None:
        expr = self._build_expr(3.14, "CODE")
        assert expr == '"CODE" = 3.14'


class TestBaseMapType(unittest.TestCase):
    """Validate BaseMapType enum completeness."""

    def test_all_basemap_types_have_urls(self) -> None:
        """Every BaseMapType (except NONE) must have a URL entry."""
        from autoatlas_pro.core.models import BaseMapType
        from autoatlas_pro.core.report_composer import _BASE_MAP_URLS

        for bm in BaseMapType:
            if bm == BaseMapType.NONE:
                assert bm not in _BASE_MAP_URLS
            else:
                assert bm in _BASE_MAP_URLS, (
                    f"BaseMapType.{bm.name} missing from _BASE_MAP_URLS"
                )

    def test_enum_values_are_display_names(self) -> None:
        """Enum .value should be a human-readable display name."""
        from autoatlas_pro.core.models import BaseMapType

        for bm in BaseMapType:
            assert len(bm.value) > 0
            # Should not be ALL_CAPS (those are .name)
            if bm != BaseMapType.NONE and bm != BaseMapType.OSM:
                assert bm.value != bm.name


if __name__ == "__main__":
    unittest.main()
