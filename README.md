# AutoAtlas Pro

**Automated Cartographic Report Generator for QGIS**

[![QGIS Version](https://img.shields.io/badge/QGIS-3.28%2B-green.svg)](https://qgis.org)
[![Qt6 Support](https://img.shields.io/badge/Qt6-supported-blue.svg)](https://doc.qt.io/qt-6/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

---

## 🚀 What is AutoAtlas Pro?

AutoAtlas Pro automates the generation of professional cartographic reports combining **thematic maps**, **statistical charts**, and **summary tables**. Generate hundreds of territorial reports in minutes, not days.

Perfect for:
- 📊 Census and demographic analysis
- 🏛️ Government municipal reports
- 🎓 Academic research
- 🌍 NGO territorial assessments

## ✨ Features

| Feature | Description |
|---------|-------------|
| **3-Step Wizard** | Intuitive guided workflow: Data → Style → Generate |
| **Choropleth Maps** | Graduated color maps with automatic legend, scale bar, and title |
| **Statistical Charts** | Distribution histogram, ranking lollipop, proportion donut, summary table |
| **Dual Chart Backend** | Premium Plotly charts when available, reliable matplotlib fallback |
| **Batch Generation** | Generate reports for all territorial units in one click |
| **Templates** | Institutional, Academic, and Minimal pre-built layouts |
| **PDF & PNG Export** | Configurable DPI (72–1200) |
| **Bilingual UI** | English and Spanish with auto-detection |
| **Dependency Installer** | Built-in one-click installer for optional packages |

## 📦 Installation

### From QGIS Plugin Manager
1. Open QGIS → `Plugins` → `Manage and Install Plugins`
2. Search for "AutoAtlas Pro"
3. Click **Install Plugin**

### Manual Installation
1. Download or clone this repository
2. Copy the `autoatlas-pro` folder to your QGIS plugins directory:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS and enable the plugin

## 🛠️ Optional Dependencies

AutoAtlas Pro works out of the box with matplotlib (bundled with QGIS). For premium chart quality, install optional packages via the built-in installer on first launch:

| Package | Purpose |
|---------|---------|
| `pandas` | Accelerated data aggregation |
| `plotly` | High-impact interactive charts |
| `kaleido` | Static image export for Plotly |

## 📖 Usage

1. **Load** a vector layer with polygon geometries (e.g., communes, districts)
2. **Open** AutoAtlas Pro from the Plugins menu or toolbar
3. **Step 1**: Select your layer, ID field, name field, and indicator fields
4. **Step 2**: Choose map style, color ramp, charts, and template
5. **Step 3**: Set output format (PDF/PNG), DPI, and destination folder
6. **Click Generate** — your reports are ready!

## 🏗️ Architecture

```
autoatlas-pro/
├── plugin.py              # QGIS plugin lifecycle
├── core/
│   ├── models.py          # Type-safe dataclasses
│   ├── data_engine.py     # Statistics & rankings
│   ├── map_renderer.py    # Thematic map generation
│   ├── chart_engine.py    # Dual-backend charts
│   ├── report_composer.py # Pipeline orchestration
│   └── dependency_manager.py
├── ui/
│   ├── wizard_dialog.py   # 3-step wizard
│   └── dependency_dialog.py
├── templates/             # Report layout definitions
└── i18n/                  # Translation files
```

## 📄 License

This plugin is licensed under the GNU General Public License v3.0.

## 🤝 Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.
