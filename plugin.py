"""AutoAtlas Pro - Main plugin class.

Handles QGIS lifecycle: menu registration, toolbar, and launching the wizard.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from qgis.PyQt.QtCore import QCoreApplication, QLocale, QSettings, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

if TYPE_CHECKING:
    from qgis.gui import QgisInterface


class AutoAtlasProPlugin:
    """QGIS Plugin — Automated Cartographic Report Generator."""

    PLUGIN_NAME = "AutoAtlas Pro"

    def __init__(self, iface: QgisInterface) -> None:
        self.iface = iface
        self.plugin_dir = Path(__file__).resolve().parent
        self.actions: list[QAction] = []
        self.menu = self.PLUGIN_NAME
        self.toolbar = self.iface.addToolBar(self.PLUGIN_NAME)
        self.toolbar.setObjectName("AutoAtlasProToolbar")

        # --- i18n ---
        self._translator: Optional[QTranslator] = None
        self._setup_translation()

    # ------------------------------------------------------------------
    # i18n
    # ------------------------------------------------------------------

    def _setup_translation(self) -> None:
        """Load the appropriate translation file based on QGIS locale."""
        locale_str = QSettings().value("locale/userLocale", QLocale.system().name())
        locale_code = str(locale_str)[0:2]
        locale_path = self.plugin_dir / "i18n" / f"autoatlas_pro_{locale_code}.qm"

        if locale_path.exists():
            self._translator = QTranslator()
            self._translator.load(str(locale_path))
            QCoreApplication.installTranslator(self._translator)

    def tr(self, message: str) -> str:
        """Translate a UI string.

        Args:
            message: Source string to translate.

        Returns:
            Translated string if translation is available, otherwise the original.
        """
        return QCoreApplication.translate("AutoAtlasProPlugin", message)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initGui(self) -> None:  # noqa: N802
        """Called by QGIS when the plugin is loaded. Registers UI elements."""
        icon_path = str(self.plugin_dir / "icon.png")

        action = QAction(
            QIcon(icon_path),
            self.tr("AutoAtlas Pro"),
            self.iface.mainWindow(),
        )
        action.triggered.connect(self.run)
        action.setEnabled(True)
        action.setStatusTip(self.tr("Generate automated cartographic reports"))

        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)

    def unload(self) -> None:
        """Called by QGIS when the plugin is unloaded. Cleans up UI elements."""
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

        if self.toolbar:
            del self.toolbar

        if self._translator:
            QCoreApplication.removeTranslator(self._translator)

    def run(self) -> None:
        """Main entry point — opens the wizard dialog."""
        from .core.dependency_manager import DependencyManager
        from .ui.wizard_dialog import WizardDialog

        # Check optional dependencies on first launch
        dep_manager = DependencyManager()
        if dep_manager.should_prompt_install():
            from .ui.dependency_dialog import DependencyDialog

            dep_dialog = DependencyDialog(
                dep_manager, parent=self.iface.mainWindow()
            )
            dep_dialog.exec_()

        # Launch the main wizard
        wizard = WizardDialog(self.iface, parent=self.iface.mainWindow())
        wizard.exec_()
