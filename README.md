# AutoAtlas Pro

**Automated Cartographic Report Generator for QGIS**

[![QGIS Version](https://img.shields.io/badge/QGIS-3.28%2B-green.svg)](https://qgis.org)
[![Qt6 Support](https://img.shields.io/badge/Qt6-supported-blue.svg)](https://doc.qt.io/qt-6/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

---

## 🚀 What is AutoAtlas Pro?

AutoAtlas Pro automates the generation of professional cartographic reports. Generate hundreds of territorial reports in minutes, not days.

Perfect for:
- 📊 Census and demographic analysis
- 🏛️ Government municipal reports
- 🎓 Academic research
- 🌍 NGO territorial assessments

## ✨ Features

| Feature | Description |
|---------|-------------|
| **3-Step Wizard** | Intuitive guided workflow: Data → Style → Generate |
| **Dark Corporate UI** | Beautiful *Neo-Brutalist* Dark Theme with opacity micro-animations |
| **Smart Highlighting** | Automatically highlights the analyzed feature with a dashed outline against the context |
| **Context Layers** | Overlay additional reference layers (roads, rivers) with custom opacity and ordering |
| **Flexible Layouts** | Support for **A4 Vertical** and **A4 Landscape** orientations |
| **Magazine Styling** | High contrast palettes, Segoe UI typography and dynamic slate backgrounds for empty tiles |
| **Custom Branding** | Add your organization's **Logo**, custom title, and footer text |
| **Bilingual UI** | Instant switching between **English** and **Spanish** |
| **Resilient Batch** | Built-in *Circuit Breaker* and *Graceful Degradation* timeouts to prevent QGIS crashes |
| **PDF & PNG Export** | Configurable DPI (72–1200) |

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



## 📖 Usage

1. **Load** a vector layer with polygon geometries (e.g., communes, districts)
2. **Open** AutoAtlas Pro from the Plugins menu or toolbar
3. **Step 1 (Data)**: Select your coverage layer, ID field, and indicator fields.
4. **Step 2 (Style)**: 
    - Configure the **Language** (ES/EN) and **Template** (Vertical/Horizontal).
    - Add your **Logo** and custom titles.
    - Set up **Context Layers** to provide geographical reference.
    - Customize map style/colors.
5. **Step 3 (Output)**: Set output format (PDF/PNG), DPI, and destination folder.
6. **Click Generate** — your reports are ready!

## 🏗️ Architecture

```
autoatlas-pro/
├── plugin.py              # QGIS plugin lifecycle
├── core/
│   ├── models.py          # Strict-typing dataclasses
│   ├── data_engine.py     # Statistics & rankings
│   ├── map_renderer.py    # Thematic map generation
│   ├── chart_engine.py    # Dual-backend charts
│   ├── report_composer.py # Resilience & Pipeline orchestration
│   └── dependency_manager.py
├── ui/
│   ├── wizard_controller.py # Logic delegation (MVC)
│   ├── wizard_dialog.py   # PyQt Dark Corporate UI
│   ├── theme.py           # QSS Global Stylesheet
│   └── dependency_dialog.py
├── templates/             # Premium layout definitions
└── i18n/                  # Translation files
```

## 📄 License

This plugin is licensed under the GNU General Public License v3.0.

## 🤝 Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.
