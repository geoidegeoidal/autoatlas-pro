"""Dependency installer dialog with premium UX.

Shows a card-based interface for optional dependency management,
with animated progress, status icons, and one-click install.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qgis.PyQt.QtCore import QSize, Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QFont, QIcon
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..core.dependency_manager import DependencyInfo, DependencyManager

from ..core.models import DepStatus


# ======================================================================
# Background installer thread
# ======================================================================


class _InstallerWorker(QThread):
    """Runs pip install in a background thread to keep the UI responsive."""

    progress = pyqtSignal(str)  # status message
    finished_dep = pyqtSignal(str, object)  # (package_name, DepStatus)
    all_done = pyqtSignal()

    def __init__(
        self, manager: DependencyManager, deps: list[DependencyInfo]
    ) -> None:
        super().__init__()
        self._manager = manager
        self._deps = deps

    def run(self) -> None:
        for dep in self._deps:
            status = self._manager.install(dep, self.progress.emit)
            self.finished_dep.emit(dep.package_name, status)
        self.all_done.emit()


# ======================================================================
# Dependency card widget
# ======================================================================


class _DepCard(QFrame):
    """A single dependency card showing name, description, and status."""

    _STATUS_ICONS = {
        DepStatus.INSTALLED: ("✅", "#2ecc71"),
        DepStatus.MISSING: ("⚠️", "#f39c12"),
        DepStatus.INSTALLING: ("🔄", "#3498db"),
        DepStatus.ERROR: ("❌", "#e74c3c"),
    }

    _STATUS_LABELS = {
        DepStatus.INSTALLED: "Installed",
        DepStatus.MISSING: "Not installed",
        DepStatus.INSTALLING: "Installing...",
        DepStatus.ERROR: "Error",
    }

    def __init__(self, dep: DependencyInfo, status: DepStatus) -> None:
        super().__init__()
        self._dep = dep
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            """
            _DepCard {
                background: palette(window);
                border: 1px solid palette(mid);
                border-radius: 8px;
                padding: 12px;
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # Left: info
        info_layout = QVBoxLayout()

        name_label = QLabel(f"<b>{dep.package_name}</b>")
        name_font = QFont()
        name_font.setPointSize(11)
        name_label.setFont(name_font)
        info_layout.addWidget(name_label)

        desc_label = QLabel(dep.description_en)
        desc_label.setStyleSheet("color: palette(shadow);")
        desc_label.setWordWrap(True)
        info_layout.addWidget(desc_label)
        self._desc_label = desc_label

        if dep.min_version:
            ver_label = QLabel(f"Minimum version: {dep.min_version}")
            ver_label.setStyleSheet("color: palette(shadow); font-size: 10px;")
            info_layout.addWidget(ver_label)

        layout.addLayout(info_layout, stretch=1)

        # Right: status
        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setMinimumWidth(120)
        layout.addWidget(self._status_label)

        self.set_status(status)

    def set_status(self, status: DepStatus) -> None:
        """Update the visual status indicator."""
        icon, color = self._STATUS_ICONS.get(
            status, ("❓", "#95a5a6")
        )
        label = self._STATUS_LABELS.get(status, "Unknown")
        self._status_label.setText(
            f'<span style="font-size: 18px;">{icon}</span>'
            f'<br><span style="color: {color}; font-weight: bold;">{label}</span>'
        )

    def set_description_locale(self, locale: str) -> None:
        """Switch description between 'en' and 'es'."""
        if locale == "es":
            self._desc_label.setText(self._dep.description_es)
        else:
            self._desc_label.setText(self._dep.description_en)


# ======================================================================
# Main dialog
# ======================================================================


class DependencyDialog(QDialog):
    """Premium dependency installer dialog.

    Shows status cards for each optional dependency with install/skip actions.
    """

    def __init__(
        self,
        manager: DependencyManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._worker: _InstallerWorker | None = None
        self._cards: dict[str, _DepCard] = {}

        self.setWindowTitle("AutoAtlas Pro — Setup")
        self.setMinimumSize(QSize(520, 400))
        self.setModal(True)

        self._build_ui()
        self._refresh_status()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QLabel(
            "<h2>📦 Optional Dependencies</h2>"
            "<p>AutoAtlas Pro works out of the box with basic charts. "
            "Install these packages to unlock <b>premium visualizations</b>.</p>"
        )
        header.setWordWrap(True)
        root.addWidget(header)

        # Cards
        from ..core.dependency_manager import OPTIONAL_DEPENDENCIES

        for dep in OPTIONAL_DEPENDENCIES:
            card = _DepCard(dep, DepStatus.MISSING)
            self._cards[dep.package_name] = card
            root.addWidget(card)

        # Progress bar (hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(False)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("Installing packages...")
        root.addWidget(self._progress_bar)

        # Status message
        self._status_msg = QLabel("")
        self._status_msg.setWordWrap(True)
        self._status_msg.setStyleSheet("color: palette(shadow); font-style: italic;")
        root.addWidget(self._status_msg)

        # Spacer
        root.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Buttons
        btn_layout = QHBoxLayout()

        self._skip_btn = QPushButton("Skip — Use basic charts")
        self._skip_btn.setStyleSheet(
            "QPushButton { padding: 8px 20px; border-radius: 4px; }"
        )
        self._skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(self._skip_btn)

        btn_layout.addItem(
            QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        self._install_btn = QPushButton("⬇ Install All")
        self._install_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                padding: 8px 24px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #27ae60; }
            QPushButton:disabled { background-color: #95a5a6; }
            """
        )
        self._install_btn.clicked.connect(self._on_install_all)
        btn_layout.addWidget(self._install_btn)

        root.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _refresh_status(self) -> None:
        """Re-check dependency statuses and update cards."""
        statuses = self._manager.check_all()
        for pkg_name, status in statuses.items():
            if pkg_name in self._cards:
                self._cards[pkg_name].set_status(status)

        all_ok = all(s == DepStatus.INSTALLED for s in statuses.values())
        if all_ok:
            self._install_btn.setEnabled(False)
            self._install_btn.setText("✅ All installed")
            self._status_msg.setText("All dependencies are installed. You're all set!")

    def _on_skip(self) -> None:
        """User chose to skip dependency installation."""
        self._manager.dismiss_prompt()
        self.accept()

    def _on_install_all(self) -> None:
        """Start installing all missing dependencies in a background thread."""
        missing = self._manager.get_missing()
        if not missing:
            self._refresh_status()
            return

        self._install_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._progress_bar.setVisible(True)

        for dep in missing:
            if dep.package_name in self._cards:
                self._cards[dep.package_name].set_status(DepStatus.INSTALLING)

        self._worker = _InstallerWorker(self._manager, missing)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_dep.connect(self._on_dep_finished)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_progress(self, msg: str) -> None:
        self._status_msg.setText(msg)

    def _on_dep_finished(self, pkg_name: str, status: object) -> None:
        if pkg_name in self._cards:
            self._cards[pkg_name].set_status(status)  # type: ignore[arg-type]

    def _on_all_done(self) -> None:
        self._progress_bar.setVisible(False)
        self._skip_btn.setEnabled(True)
        self._refresh_status()
        self._manager.dismiss_prompt()

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        """Treat closing the dialog as skipping."""
        self._manager.dismiss_prompt()
        super().closeEvent(event)
