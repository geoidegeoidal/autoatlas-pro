"""Dependency manager for AutoAtlas Pro.

Handles detection, installation, and status tracking of optional
Python packages (pandas, plotly, kaleido) within QGIS's Python environment.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from qgis.PyQt.QtCore import QSettings

from .models import DepStatus


@dataclass
class DependencyInfo:
    """Metadata for an optional dependency.

    Attributes:
        package_name: pip install name.
        import_name: Python import name (may differ from package_name).
        min_version: Minimum acceptable version string.
        description_en: English description of what the package provides.
        description_es: Spanish description.
    """

    package_name: str
    import_name: str
    min_version: Optional[str]
    description_en: str
    description_es: str


# Registry of optional dependencies
OPTIONAL_DEPENDENCIES: List[DependencyInfo] = [
    DependencyInfo(
        package_name="pandas",
        import_name="pandas",
        min_version="1.5.0",
        description_en="Accelerated data aggregation and statistical computation",
        description_es="Agregación de datos y cálculos estadísticos acelerados",
    ),
    DependencyInfo(
        package_name="plotly",
        import_name="plotly",
        min_version="5.0.0",
        description_en="High-impact interactive charts with premium styling",
        description_es="Gráficos interactivos de alto impacto con estilo premium",
    ),
    DependencyInfo(
        package_name="kaleido",
        import_name="kaleido",
        min_version="0.2.0",
        description_en="Static image export for Plotly charts (required for PDF reports)",
        description_es="Exportación de imágenes estáticas para gráficos Plotly (requerido para reportes PDF)",
    ),
]

_SETTINGS_KEY = "AutoAtlasPro/dependency_prompt_dismissed"


class DependencyManager:
    """Detects and installs optional Python packages in QGIS's environment."""

    def __init__(self) -> None:
        self._status_cache: Dict[str, DepStatus] = {}

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def check_all(self) -> Dict[str, DepStatus]:
        """Check the installation status of all optional dependencies.

        Returns:
            Mapping from package_name to its current DepStatus.
        """
        self._status_cache = {
            dep.package_name: self._check_single(dep)
            for dep in OPTIONAL_DEPENDENCIES
        }
        return dict(self._status_cache)

    @staticmethod
    def _check_single(dep: DependencyInfo) -> DepStatus:
        """Check whether a single dependency is importable.

        Args:
            dep: Dependency metadata.

        Returns:
            DepStatus.INSTALLED or DepStatus.MISSING.
        """
        try:
            mod = importlib.import_module(dep.import_name)
            # Version check if available
            version = getattr(mod, "__version__", None)
            if version and dep.min_version:
                from packaging.version import Version

                if Version(version) < Version(dep.min_version):
                    return DepStatus.MISSING
            return DepStatus.INSTALLED
        except ImportError:
            return DepStatus.MISSING
        except Exception:  # noqa: BLE001 — graceful fallback
            return DepStatus.MISSING

    def all_installed(self) -> bool:
        """Return True if all optional dependencies are installed."""
        statuses = self.check_all()
        return all(s == DepStatus.INSTALLED for s in statuses.values())

    def get_missing(self) -> List[DependencyInfo]:
        """Return list of dependencies that are not installed."""
        statuses = self.check_all()
        return [
            dep
            for dep in OPTIONAL_DEPENDENCIES
            if statuses.get(dep.package_name) != DepStatus.INSTALLED
        ]

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------

    def install(
        self,
        dep: DependencyInfo,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> DepStatus:
        """Install a single dependency using pip.

        Args:
            dep: Dependency to install.
            progress_callback: Optional callable receiving status messages.

        Returns:
            DepStatus.INSTALLED on success, DepStatus.ERROR on failure.
        """
        self._status_cache[dep.package_name] = DepStatus.INSTALLING
        if progress_callback:
            progress_callback(f"Installing {dep.package_name}...")

        cmd = self.get_install_command(dep)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if result.returncode == 0:
                # Verify the import actually works now
                importlib.invalidate_caches()
                try:
                    importlib.import_module(dep.import_name)
                    self._status_cache[dep.package_name] = DepStatus.INSTALLED
                    if progress_callback:
                        progress_callback(f"✅ {dep.package_name} installed successfully")
                    return DepStatus.INSTALLED
                except ImportError:
                    self._status_cache[dep.package_name] = DepStatus.ERROR
                    if progress_callback:
                        progress_callback(
                            f"⚠️ {dep.package_name} installed but import failed"
                        )
                    return DepStatus.ERROR
            else:
                self._status_cache[dep.package_name] = DepStatus.ERROR
                if progress_callback:
                    progress_callback(
                        f"❌ {dep.package_name} installation failed: {result.stderr[:200]}"
                    )
                return DepStatus.ERROR

        except subprocess.TimeoutExpired:
            self._status_cache[dep.package_name] = DepStatus.ERROR
            if progress_callback:
                progress_callback(f"❌ {dep.package_name} installation timed out")
            return DepStatus.ERROR
        except Exception as exc:  # noqa: BLE001
            self._status_cache[dep.package_name] = DepStatus.ERROR
            if progress_callback:
                progress_callback(f"❌ {dep.package_name} error: {exc}")
            return DepStatus.ERROR

    def install_all(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, DepStatus]:
        """Install all missing dependencies.

        Args:
            progress_callback: Optional callable receiving status messages.

        Returns:
            Final status mapping for all dependencies.
        """
        missing = self.get_missing()
        for dep in missing:
            self.install(dep, progress_callback)
        return dict(self._status_cache)

    @staticmethod
    def _find_python() -> str:
        """Locate the real python.exe inside QGIS's bundled Python.

        In QGIS, ``sys.executable`` points to ``qgis-bin.exe``, NOT to
        ``python.exe``.  Running ``qgis-bin.exe -m pip`` opens a new QGIS
        window instead of installing packages.  We probe several known
        locations to find the actual Python interpreter.

        Returns:
            Absolute path to python.exe.

        Raises:
            FileNotFoundError: If no Python interpreter could be located.
        """
        import os

        # 1. Try sys.prefix (e.g. C:\PROGRA~1\QGIS3~1\apps\Python312)
        candidates = [
            os.path.join(sys.prefix, "python.exe"),
            os.path.join(sys.prefix, "python3.exe"),
        ]

        # 2. Try relative to sys.executable
        #    qgis-bin.exe is typically in apps/qgis-ltr/ or apps/qgis/
        #    python.exe is in apps/Python3XX/
        exe_dir = os.path.dirname(sys.executable)
        apps_dir = os.path.dirname(exe_dir)
        if os.path.isdir(apps_dir):
            for entry in os.listdir(apps_dir):
                if entry.lower().startswith("python3"):
                    candidates.append(os.path.join(apps_dir, entry, "python.exe"))

        # 3. Try PYTHONHOME environment variable
        py_home = os.environ.get("PYTHONHOME", "")
        if py_home:
            candidates.append(os.path.join(py_home, "python.exe"))

        for path in candidates:
            if os.path.isfile(path):
                return path

        raise FileNotFoundError(
            "Could not locate Python interpreter in QGIS environment. "
            f"sys.executable={sys.executable}, sys.prefix={sys.prefix}"
        )

    @staticmethod
    def get_install_command(dep: DependencyInfo) -> List[str]:
        """Build the pip install command for a dependency.

        Args:
            dep: Dependency metadata.

        Returns:
            Command as a list of strings suitable for subprocess.run.
        """
        python_path = DependencyManager._find_python()
        pkg_spec = dep.package_name
        if dep.min_version:
            pkg_spec = f"{dep.package_name}>={dep.min_version}"
        return [
            python_path,
            "-m",
            "pip",
            "install",
            "--user",
            "--quiet",
            "--trusted-host", "pypi.org",
            "--trusted-host", "files.pythonhosted.org",
            pkg_spec,
        ]

    # ------------------------------------------------------------------
    # UX gating
    # ------------------------------------------------------------------

    def should_prompt_install(self) -> bool:
        """Check if the dependency dialog should be shown.

        Returns True only when:
        1. At least one optional dep is missing, AND
        2. The user has not previously dismissed the prompt.
        """
        dismissed = QSettings().value(_SETTINGS_KEY, False, type=bool)
        if dismissed:
            return False
        return not self.all_installed()

    @staticmethod
    def dismiss_prompt() -> None:
        """Record that the user has dismissed the dependency prompt."""
        QSettings().setValue(_SETTINGS_KEY, True)

    @staticmethod
    def reset_prompt() -> None:
        """Reset the dismiss flag (e.g., after a plugin update)."""
        QSettings().remove(_SETTINGS_KEY)
