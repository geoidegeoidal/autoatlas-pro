"""AutoAtlas Pro - Automated Cartographic Report Generator for QGIS."""


# noinspection PyPep8Naming
def classFactory(iface):  # noqa: N802
    """QGIS plugin entry point.

    Args:
        iface: QgisInterface instance providing access to the QGIS application.

    Returns:
        AutoAtlasProPlugin instance.
    """
    from .plugin import AutoAtlasProPlugin

    return AutoAtlasProPlugin(iface)
