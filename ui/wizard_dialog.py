"""Multi-step wizard dialog for AutoAtlas Pro.

Three-step workflow:
  1. Data — Select layer, ID field, name field, indicator fields
  2. Style — Map style, color ramp, chart selection, template
  3. Output — Format, directory, batch options
"""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import TYPE_CHECKING, List, Optional

from .wizard_controller import WizardController

from qgis.core import (
    QgsMapLayerProxyModel,
    QgsProject,
    QgsStyle,
    QgsVectorLayer,
)
from qgis.gui import (
    QgsColorButton,
    QgsFieldComboBox,
    QgsOpacityWidget,
    QgsMapLayerComboBox,
)
from qgis.PyQt.QtCore import QCoreApplication, QSize, Qt
from qgis.PyQt.QtGui import QColor, QFont, QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,

    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from qgis.gui import (
        QgisInterface,
        QgsColorButton,
        QgsFieldComboBox,
        QgsMapLayerComboBox,
        QgsOpacityWidget,
        QgsVectorLayer,
    )

TRANS_UI = {
    "es": {
        "title": "Asistente AutoAtlas Pro",
        "step1_title": "Configuración de Datos",
        "step1_desc": "Selecciona la capa vectorial y los campos para generar el reporte.",
        "grp_layer": "Capa de Cobertura",
        "layer": "Capa Vectorial:",
        "grp_fields": "Campos",
        "id_field": "Campo ID (Iterador):",
        "name_field": "Campo Nombre (Título):",
        "indicators": "Indicadores Estadísticos:",
        "step2_title": "Configuración de Estilo",
        "step2_desc": "Define la apariencia de mapas y gráficos.",
        "grp_gen": "Configuración General",
        "language": "Idioma:",
        "template": "Plantilla:",
        "logo": "Logotipo:",
        "grp_map": "Estilo del Mapa",
        "style": "Estilo:",
        "ramp": "Rampa de Color:",
        "opacity": "Opacidad (%):",
        "highlight": "Resaltar elemento analizado",
        "labels": "Etiquetas:",
        "basemap": "Mapa Base:",
        "grp_ctx": "Capas de Contexto",
        "overview": "Incluir mapa de contexto (inset)",
        "overview_labels": "Mostrar etiquetas en overview",
        "grp_legend": "Configuración de Leyenda",
        "legend_title": "Título de Leyenda:",
        "layer_alias": "Alias de Capa Análisis:",
        "grp_layout": "Configuración de Diseño",
        "title_override": "Título Personalizado:",
        "footer_override": "Texto del Pie de Página:",
        "col_header": "Color Encabezado:",
        "col_footer": "Color Pie de Página:",
        "step3_title": "Configuración de Salida",
        "step3_desc": "Elige formato y destino.",
        "grp_format": "Formato de Salida",
        "grp_dir": "Directorio de Salida",
        "browse": "Examinar...",
        "next": "Siguiente >",
        "back": "< Atrás",
        "generate": "Generar Reportes",
        "cancel": "Cancelar",
        "close": "Cerrar",
        "preview": "Actualizar Vista Previa",
    },
    "en": {
        "title": "AutoAtlas Pro Wizard",
        "step1_title": "Data Configuration",
        "step1_desc": "Select vector layer and fields for the report.",
        "grp_layer": "Coverage Layer",
        "layer": "Vector Layer:",
        "grp_fields": "Fields",
        "id_field": "ID Field (Iterator):",
        "name_field": "Name Field (Title):",
        "indicators": "Statistical Indicators:",
        "step2_title": "Style Configuration",
        "step2_desc": "Define appearance for maps and charts.",
        "grp_gen": "General Settings",
        "language": "Language:",
        "template": "Template:",
        "logo": "Logo:",
        "grp_map": "Map Styling",
        "style": "Style:",
        "ramp": "Color Ramp:",
        "opacity": "Opacity (%):",
        "highlight": "Highlight analyzed feature",
        "labels": "Labels:",
        "basemap": "Base Map:",
        "grp_ctx": "Context Layers",
        "overview": "Include overview map (inset)",
        "overview_labels": "Show labels on overview",
        "grp_legend": "Legend Settings",
        "legend_title": "Legend Title:",
        "layer_alias": "Analysis Layer Alias:",
        "grp_layout": "Layout Settings",
        "title_override": "Title Override:",
        "footer_override": "Footer Text:",
        "col_header": "Header Color:",
        "col_footer": "Footer Color:",
        "step3_title": "Output Configuration",
        "step3_desc": "Choose format and destination.",
        "grp_format": "Output Format",
        "grp_dir": "Output Directory",
        "browse": "Browse...",
        "next": "Next >",
        "back": "< Back",
        "generate": "Generate Reports",
        "cancel": "Cancel",
        "close": "Close",
        "preview": "Refresh Preview",
    }
}

from ..core.models import (
    BaseMapType,
    ChartType,
    ContextLayerConfig,
    GraduatedMode,
    MapStyle,
    OutputFormat,
    ReportConfig,
    TemplateConfig,
)


class WizardDialog(QDialog):
    """Three-step wizard for configuring and launching report generation."""

    def __init__(
        self,
        iface: QgisInterface,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._iface = iface
        self._current_step = 0
        self._controller = WizardController(self)

        self.setWindowTitle(self.tr("AutoAtlas Pro — Report Wizard"))
        self.setMinimumSize(QSize(680, 520))
        self.setModal(True)
        
        from .theme import DARK_CORPORATE_QSS
        self.setStyleSheet(DARK_CORPORATE_QSS)

        self._build_ui()

    def tr(self, message: str) -> str:
        return QCoreApplication.translate("WizardDialog", message)

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # --- Header with step indicators ---
        self._header = self._build_header()
        root.addWidget(self._header)

        # --- Stacked content area ---
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_step_data())
        self._stack.addWidget(self._build_step_style())
        self._stack.addWidget(self._build_step_output())
        
        root.addWidget(self._stack, stretch=1)

        # --- Footer with navigation buttons ---
        footer = self._build_footer()
        root.addWidget(footer)
        
        # Initial UI text update (defaults to Spanish)
        self._update_ui_text()

    # ------------------------------------------------------------------
    # Header (step indicator)
    # ------------------------------------------------------------------

    def _build_header(self) -> QWidget:
        """Build the top header with step progress indicators."""
        header = QFrame()
        header.setObjectName("header_frame")
        header.setFixedHeight(56)
        layout = QHBoxLayout(header)

        self._step_labels: list[QLabel] = []
        steps = [
            self.tr("① Data"),
            self.tr("② Style"),
            self.tr("③ Output"),
        ]
        for i, text in enumerate(steps):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignCenter)
            font = QFont("Arial", 12, QFont.Bold if i == 0 else QFont.Normal)
            lbl.setFont(font)
            lbl.setStyleSheet(
                "color: white;" if i == 0 else "color: rgba(255,255,255,0.5);"
            )
            self._step_labels.append(lbl)
            layout.addWidget(lbl)

        return header

    def _update_step_indicator(self) -> None:
        """Update the visual state of step labels based on current step."""
        for i, lbl in enumerate(self._step_labels):
            if i == self._current_step:
                lbl.setStyleSheet("color: white;")
                font = lbl.font()
                font.setBold(True)
                lbl.setFont(font)
            elif i < self._current_step:
                lbl.setStyleSheet("color: rgba(255,255,255,0.7);")
                font = lbl.font()
                font.setBold(False)
                lbl.setFont(font)
            else:
                lbl.setStyleSheet("color: rgba(255,255,255,0.4);")
                font = lbl.font()
                font.setBold(False)
                lbl.setFont(font)

    # ------------------------------------------------------------------
    # Step 1: Data Selection
    # ------------------------------------------------------------------

    def _build_step_data(self) -> QWidget:
        """Build Step 1 UI: Layer, Fields, and Language selection."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._lbl_step1_title = QLabel(
            f"<h3>{self.tr('Select Data Source')}</h3>"
            f"<p>{self.tr('Choose the vector layer and fields for your report.')}</p>"
        )
        layout.addWidget(self._lbl_step1_title)

        # Language Selection
        row_lang = QHBoxLayout()
        self._lbl_lang = QLabel(self.tr("Language:"))
        row_lang.addWidget(self._lbl_lang)
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["es", "en"])
        self._lang_combo.setToolTip(self.tr("Select interface and report language"))
        self._lang_combo.currentTextChanged.connect(self._on_language_changed)
        row_lang.addWidget(self._lang_combo)
        row_lang.addStretch()
        layout.addLayout(row_lang)

        # Layer selection
        self._grp_layer = QGroupBox(self.tr("Coverage Layer"))
        grp_layout = QVBoxLayout(self._grp_layer)

        from qgis.gui import QgsMapLayerComboBox
        self._layer_combo = QgsMapLayerComboBox()
        self._layer_combo.setFilters(
            QgsMapLayerProxyModel.PolygonLayer |
            QgsMapLayerProxyModel.PointLayer |
            QgsMapLayerProxyModel.LineLayer
        )
        self._layer_combo.layerChanged.connect(self._on_layer_changed)
        grp_layout.addWidget(self._layer_combo)
        layout.addWidget(self._grp_layer)

        # Fields
        self._grp_fields = QGroupBox(self.tr("Fields"))
        fields_layout = QVBoxLayout(self._grp_fields)

        # ID field
        row_id = QHBoxLayout()
        self._lbl_id = QLabel(self.tr("Unique Identifier (ID):"))
        self._lbl_id.setToolTip(self.tr(
            "Select the field that uniquely identifies each feature.\n"
            "This field is used to split the layer into individual reports."
        ))
        row_id.addWidget(self._lbl_id)
        self._id_field_combo = QComboBox()
        self._id_field_combo.setToolTip(self.tr(
            "This field drives the iteration. One report will be generated per unique value."
        ))
        row_id.addWidget(self._id_field_combo, stretch=1)
        fields_layout.addLayout(row_id)

        # Name field
        row_name = QHBoxLayout()
        self._lbl_name = QLabel(self.tr("Name Field:"))
        row_name.addWidget(self._lbl_name)
        self._name_field_combo = QComboBox()
        row_name.addWidget(self._name_field_combo, stretch=1)
        fields_layout.addLayout(row_name)

        # Indicator fields (multi-select)
        self._lbl_indicators = QLabel(self.tr("Indicator Fields (select one or more):"))
        fields_layout.addWidget(self._lbl_indicators)
        self._indicator_list = QListWidget()
        self._indicator_list.setSelectionMode(QListWidget.MultiSelection)
        self._indicator_list.setMaximumHeight(150)
        fields_layout.addWidget(self._indicator_list)

        layout.addWidget(self._grp_fields)
        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Populate if a layer is already selected
        self._on_layer_changed(self._layer_combo.currentLayer())

        return page

    def _on_style_changed(self, idx: int) -> None:
        """Show/hide style controls based on selected map style."""
        style_data = self._style_combo.itemData(idx)
        if not style_data:
            return

        # Hide all first
        self._wdg_single.setVisible(False)
        self._wdg_graduated.setVisible(False)
        self._wdg_categorized.setVisible(False)
        
        # Show relevant
        if style_data == MapStyle.SINGLE:
            self._wdg_single.setVisible(True)
        elif style_data == MapStyle.GRADUATED:
            self._wdg_graduated.setVisible(True)
        elif style_data == MapStyle.CATEGORIZED:
            self._wdg_categorized.setVisible(True)

    def _on_layer_changed(self, layer: Optional[QgsVectorLayer]) -> None:
        """Populate field combos when layer selection changes."""
        self._id_field_combo.clear()
        self._name_field_combo.clear()
        self._indicator_list.clear()
        
        # Update Categorized Column Combo (only if Step 2 is built)
        if hasattr(self, "_cat_col_combo"):
            self._cat_col_combo.setLayer(layer)

        if not layer:
            return

        fields = layer.fields()
        for f in fields:
            fname = f.name()
            self._id_field_combo.addItem(fname)
            self._name_field_combo.addItem(fname)

            # Only show numeric fields in indicator list
            if f.isNumeric():
                item = QListWidgetItem(fname)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self._indicator_list.addItem(item)
        
        # Check default item (first one)
        if self._indicator_list.count() > 0:
            self._indicator_list.item(0).setCheckState(Qt.Checked)

    # ------------------------------------------------------------------
    # Step 2: Style Configuration
    # ------------------------------------------------------------------

    def _build_step_style(self) -> QWidget:
        """Build Step 2 UI: Map style, customization, and general settings."""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        scroll_layout = QVBoxLayout(content)
        scroll_layout.setContentsMargins(24, 24, 24, 24)
        scroll_layout.setSpacing(16)
        
        self._lbl_step2_title = QLabel(
            f"<h3>{self.tr('Configure Style')}</h3>"
            f"<p>{self.tr('Choose how your maps and charts will look.')}</p>"
        )
        scroll_layout.addWidget(self._lbl_step2_title)

        # 0. General Settings (Group)
        self._grp_gen = QGroupBox(self.tr("General Report Settings"))
        gen_layout = QVBoxLayout(self._grp_gen)

        # Row 1: Template
        row_lt = QHBoxLayout()

        self._lbl_template = QLabel(self.tr("Template:"))
        row_lt.addWidget(self._lbl_template)
        self._template_combo = QComboBox()
        self._template_combo.addItems(["A4 Landscape", "A4 Vertical"])
        self._template_combo.setToolTip(self.tr("Page layout orientation"))
        row_lt.addWidget(self._template_combo)
        gen_layout.addLayout(row_lt)

        # Row 2: Logo
        row_logo = QHBoxLayout()
        self._lbl_logo = QLabel(self.tr("Logo:"))
        row_logo.addWidget(self._lbl_logo)
        self._logo_path_edit = QLineEdit()
        self._logo_path_edit.setPlaceholderText(self.tr("Select image (PNG/SVG)..."))
        row_logo.addWidget(self._logo_path_edit)

        btn_logo = QPushButton("...")
        btn_logo.clicked.connect(self._select_logo)
        btn_logo.setFixedWidth(30)
        row_logo.addWidget(btn_logo)

        self._logo_pos_combo = QComboBox()
        self._logo_pos_combo.addItems(["Right", "Left"])
        self._logo_pos_combo.setToolTip(self.tr("Logo position in header"))
        row_logo.addWidget(self._logo_pos_combo)
        gen_layout.addLayout(row_logo)

        scroll_layout.addWidget(self._grp_gen)

        # 1. Map Styling (Group)
        # 1. Map Styling (Group)
        self._grp_map = QGroupBox(self.tr("Map Styling"))
        map_layout = QVBoxLayout(self._grp_map)
        
        # Row 1: Layer Styling Config
        # ---------------------------
        # Style Type
        row_style = QHBoxLayout()
        self._lbl_style = QLabel(self.tr("Style:"))
        row_style.addWidget(self._lbl_style)
        self._style_combo = QComboBox()
        for s in MapStyle:
            self._style_combo.addItem(s.value, s)
        self._style_combo.currentIndexChanged.connect(self._on_style_changed)
        row_style.addWidget(self._style_combo, stretch=1)
        map_layout.addLayout(row_style)

        # Dynamic Controls Container
        self._wdg_style_details = QWidget()
        self._lay_style_details = QVBoxLayout(self._wdg_style_details)
        self._lay_style_details.setContentsMargins(0, 0, 0, 0)
        
        # -- Single Symbol Controls --
        self._wdg_single = QWidget()
        lay_single = QHBoxLayout(self._wdg_single)
        lay_single.setContentsMargins(0, 0, 0, 0)
        lay_single.addWidget(QLabel(self.tr("Color:")))
        self._color_btn_single = QgsColorButton()
        self._color_btn_single.setColor(QColor("#3388FF"))
        lay_single.addWidget(self._color_btn_single)
        lay_single.addStretch()
        self._lay_style_details.addWidget(self._wdg_single)

        # -- Graduated Controls --
        self._wdg_graduated = QWidget()
        lay_grad = QVBoxLayout(self._wdg_graduated)
        lay_grad.setContentsMargins(0, 0, 0, 0)
        
        row_grad_1 = QHBoxLayout()
        row_grad_1.addWidget(QLabel(self.tr("Mode:")))
        self._mode_combo = QComboBox()
        for m in GraduatedMode:
            self._mode_combo.addItem(m.value, m)
        row_grad_1.addWidget(self._mode_combo, stretch=1)
        
        row_grad_1.addWidget(QLabel(self.tr("Classes:")))
        self._classes_spin = QSpinBox()
        self._classes_spin.setRange(2, 12)
        self._classes_spin.setValue(5)
        row_grad_1.addWidget(self._classes_spin)
        lay_grad.addLayout(row_grad_1)
        
        row_grad_2 = QHBoxLayout()
        row_grad_2.addWidget(QLabel(self.tr("Ramp:")))
        self._ramp_combo = QComboBox()
        self._ramp_combo.addItems(["Spectral", "Viridis", "Plasma", "Blues", "Reds", "Greens", "Magma", "Inferno"])
        row_grad_2.addWidget(self._ramp_combo, stretch=1)
        lay_grad.addLayout(row_grad_2)
        
        self._lay_style_details.addWidget(self._wdg_graduated)

        # -- Categorized Controls --
        self._wdg_categorized = QWidget()
        lay_cat = QVBoxLayout(self._wdg_categorized)
        lay_cat.setContentsMargins(0, 0, 0, 0)
        
        row_cat_1 = QHBoxLayout()
        row_cat_1.addWidget(QLabel(self.tr("Column:")))
        self._cat_col_combo = QgsFieldComboBox()
        # Initialize with current layer since _on_layer_changed skipped it (was not built yet)
        if self._layer_combo.currentLayer():
            self._cat_col_combo.setLayer(self._layer_combo.currentLayer())
        row_cat_1.addWidget(self._cat_col_combo, stretch=1)
        lay_cat.addLayout(row_cat_1)
        
        row_cat_2 = QHBoxLayout()
        row_cat_2.addWidget(QLabel(self.tr("Ramp:")))
        self._cat_ramp_combo = QComboBox()
        self._cat_ramp_combo.addItems(["Spectral", "Viridis", "Plasma", "Random"]) # Simplified
        row_cat_2.addWidget(self._cat_ramp_combo, stretch=1)
        lay_cat.addLayout(row_cat_2)
        
        self._lay_style_details.addWidget(self._wdg_categorized)
        
        map_layout.addWidget(self._wdg_style_details)

        # Trigger initial state update
        self._on_style_changed(0)

        # Row 2: Opacity & Highlight
        row2 = QHBoxLayout()
        self._lbl_opacity = QLabel(self.tr("Opacity:"))
        row2.addWidget(self._lbl_opacity)
        self._opacity_widget = QgsOpacityWidget()
        self._opacity_widget.setOpacity(0.6)
        row2.addWidget(self._opacity_widget)
        
        self._chk_highlight = QCheckBox(self.tr("Highlight Analyzed Object"))
        self._chk_highlight.setChecked(True)
        self._chk_highlight.setToolTip(self.tr("Draw a dashed outline around the current feature"))
        row2.addWidget(self._chk_highlight)
        map_layout.addLayout(row2)

        # Row 3: Labeling
        row3 = QHBoxLayout()
        self._chk_labels = QCheckBox(self.tr("Labels:"))
        row3.addWidget(self._chk_labels)
        self._label_field_combo = QgsFieldComboBox()
        self._label_field_combo.setEnabled(False)
        self._chk_labels.toggled.connect(self._label_field_combo.setEnabled)
        row3.addWidget(self._label_field_combo, stretch=1)
        map_layout.addLayout(row3)

        # Row 4: Base Map
        row4 = QHBoxLayout()
        self._lbl_basemap = QLabel(self.tr("Base Map:"))
        row4.addWidget(self._lbl_basemap)
        self._basemap_combo = QComboBox()
        for bm in BaseMapType:
            self._basemap_combo.addItem(bm.value, bm)
        row4.addWidget(self._basemap_combo)
        map_layout.addLayout(row4)

        scroll_layout.addWidget(self._grp_map)

        # 2. Context Layers (Group) — Table with opacity and alias per layer
        self._grp_ctx = QGroupBox(self.tr("Context Layers"))
        ctx_layout = QVBoxLayout(self._grp_ctx)
        self._ctx_table = QTableWidget(0, 4)
        self._ctx_table.setHorizontalHeaderLabels([
            self.tr("✓"), self.tr("Layer"),
            self.tr("Legend Alias"), self.tr("Opacity"),
        ])
        hdr = self._ctx_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._ctx_table.setFixedHeight(120)
        self._ctx_table.verticalHeader().setVisible(False)
        self._ctx_table.setDragDropMode(QTableWidget.NoDragDrop)

        # Table + reorder buttons side by side
        ctx_row = QHBoxLayout()
        ctx_row.addWidget(self._ctx_table)

        btn_col = QVBoxLayout()
        btn_col.addStretch()
        self._btn_ctx_up = QPushButton("▲")
        self._btn_ctx_up.setFixedSize(28, 28)
        self._btn_ctx_up.setToolTip(self.tr("Move selected layer up"))
        self._btn_ctx_up.clicked.connect(lambda: self._move_ctx_row(-1))
        btn_col.addWidget(self._btn_ctx_up)

        self._btn_ctx_down = QPushButton("▼")
        self._btn_ctx_down.setFixedSize(28, 28)
        self._btn_ctx_down.setToolTip(self.tr("Move selected layer down"))
        self._btn_ctx_down.clicked.connect(lambda: self._move_ctx_row(1))
        btn_col.addWidget(self._btn_ctx_down)
        btn_col.addStretch()

        ctx_row.addLayout(btn_col)
        ctx_layout.addLayout(ctx_row)

        # Overview Map checkbox
        self._chk_overview = QCheckBox(self.tr("Include overview map (inset)"))
        self._chk_overview.setToolTip(self.tr(
            "Show a small regional map with the feature highlighted"
        ))
        ctx_layout.addWidget(self._chk_overview)

        self._chk_overview_labels = QCheckBox(self.tr("Show labels on overview map"))
        self._chk_overview_labels.setChecked(False)
        self._chk_overview_labels.setToolTip(self.tr(
            "Enable or disable labels on the overview inset map"
        ))
        ctx_layout.addWidget(self._chk_overview_labels)
        scroll_layout.addWidget(self._grp_ctx)

        # 3. Legend Settings (Group)
        self._grp_legend = QGroupBox(self.tr("Legend Settings"))
        legend_layout = QVBoxLayout(self._grp_legend)

        # Legend Title
        row_alias = QHBoxLayout()
        self._lbl_legend_title = QLabel(self.tr("Legend Title:"))
        row_alias.addWidget(self._lbl_legend_title)
        self._alias_edit = QLineEdit()
        self._alias_edit.setPlaceholderText(self.tr("e.g. Total Population 2024"))
        row_alias.addWidget(self._alias_edit)
        legend_layout.addLayout(row_alias)

        # Analysis Layer Name in Legend
        row_lyr_alias = QHBoxLayout()
        self._lbl_layer_alias = QLabel(self.tr("Analysis Layer Name:"))
        row_lyr_alias.addWidget(self._lbl_layer_alias)
        self._layer_alias_edit = QLineEdit()
        self._layer_alias_edit.setPlaceholderText(self.tr("e.g. Communes"))
        row_lyr_alias.addWidget(self._layer_alias_edit)
        legend_layout.addLayout(row_lyr_alias)

        scroll_layout.addWidget(self._grp_legend)

        # 4. Layout Customization (Group)
        self._grp_layout_settings = QGroupBox(self.tr("Layout Settings"))
        lay_layout = QVBoxLayout(self._grp_layout_settings)
        
        # Title Override
        row_title = QHBoxLayout()
        self._lbl_title_override = QLabel(self.tr("Title Override:"))
        row_title.addWidget(self._lbl_title_override)
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText(self.tr("Leave empty for feature name"))
        row_title.addWidget(self._title_edit)
        lay_layout.addLayout(row_title)

        # Subtitle Override
        row_subtitle = QHBoxLayout()
        self._lbl_subtitle_override = QLabel(self.tr("Subtitle Override:"))
        row_subtitle.addWidget(self._lbl_subtitle_override)
        self._subtitle_edit = QLineEdit()
        self._subtitle_edit.setPlaceholderText(self.tr("Leave empty to use variable name"))
        row_subtitle.addWidget(self._subtitle_edit)
        lay_layout.addLayout(row_subtitle)

        # Footer Override
        row_footer = QHBoxLayout()
        self._lbl_footer_override = QLabel(self.tr("Footer Text:"))
        row_footer.addWidget(self._lbl_footer_override)
        self._footer_edit = QLineEdit()
        self._footer_edit.setPlaceholderText(self.tr("Leave empty for default footer"))
        row_footer.addWidget(self._footer_edit)
        lay_layout.addLayout(row_footer)

        # Colors
        row_colors = QHBoxLayout()
        self._lbl_col_header = QLabel(self.tr("Header Color:"))
        row_colors.addWidget(self._lbl_col_header)
        self._col_header = QgsColorButton()
        self._col_header.setColor(QColor("#1B2838"))
        row_colors.addWidget(self._col_header)
        
        self._lbl_col_footer = QLabel(self.tr("Footer Color:"))
        row_colors.addWidget(self._lbl_col_footer)
        self._col_footer = QgsColorButton()
        self._col_footer.setColor(QColor("#1B2838"))
        row_colors.addWidget(self._col_footer)
        lay_layout.addLayout(row_colors)

        scroll_layout.addWidget(self._grp_layout_settings)
        


        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Preview Button
        self._btn_preview = QPushButton(self.tr("Refresh Preview"))
        self._btn_preview.clicked.connect(self._on_preview_clicked)
        layout.addWidget(self._btn_preview)

        return page

    # ------------------------------------------------------------------
    # Step 3: Output Configuration
    # ------------------------------------------------------------------

    def _build_step_output(self) -> QWidget:
        """Build Step 3 UI: Output format and directory selection."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._lbl_step3_title = QLabel(
            f"<h3>{self.tr('Configure Output')}</h3>"
            f"<p>{self.tr('Choose format and destination for your reports.')}</p>"
        )
        layout.addWidget(self._lbl_step3_title)

        # Format
        self._grp_format = QGroupBox(self.tr("Output Format"))
        fmt_layout = QVBoxLayout(self._grp_format)
        self._radio_pdf = QRadioButton("PDF")
        self._radio_pdf.setChecked(True)
        self._radio_png = QRadioButton("PNG")
        fmt_layout.addWidget(self._radio_pdf)
        fmt_layout.addWidget(self._radio_png)
        
        # DPI
        dpi_layout = QHBoxLayout()
        dpi_layout.addWidget(QLabel("DPI:"))
        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(72, 600)
        self._dpi_spin.setValue(150)
        dpi_layout.addWidget(self._dpi_spin)
        fmt_layout.addLayout(dpi_layout)
        
        layout.addWidget(self._grp_format)

        # Directory
        self._grp_dir = QGroupBox(self.tr("Output Directory"))
        dir_layout = QHBoxLayout(self._grp_dir)
        self._dir_edit = QLineEdit()
        self._dir_edit.setText(str(Path.home() / "AutoAtlas_Output"))
        dir_layout.addWidget(self._dir_edit, stretch=1)
        self._btn_browse = QPushButton(self.tr("Browse..."))
        self._btn_browse.clicked.connect(self._browse_output_dir)
        dir_layout.addWidget(self._btn_browse)
        layout.addWidget(self._grp_dir)

        # Progress (shown during generation)
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setVisible(False)
        self._progress_label.setStyleSheet("font-style: italic; color: gray;")
        layout.addWidget(self._progress_label)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))
        return page

    def _browse_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, self.tr("Select Output Directory"),
            str(Path.home()),
        )
        if directory:
            self._dir_edit.setText(directory)

    # ------------------------------------------------------------------
    # Footer (navigation)
    # ------------------------------------------------------------------

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setStyleSheet("QFrame { border-top: 1px solid palette(mid); padding: 12px; }")
        layout = QHBoxLayout(footer)

        self._btn_back = QPushButton(self.tr("← Back"))
        self._btn_back.setEnabled(False)
        self._btn_back.clicked.connect(self._go_back)
        layout.addWidget(self._btn_back)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self._btn_next = QPushButton(self.tr("Next →"))
        self._btn_next.setStyleSheet(
            """
            QPushButton {
                background-color: #0f3460;
                color: white;
                font-weight: bold;
                padding: 8px 24px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #1a4a7a; }
            QPushButton:disabled { background-color: #95a5a6; }
            """
        )
        self._btn_next.clicked.connect(self._go_next)
        layout.addWidget(self._btn_next)

        return footer

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _select_logo(self) -> None:
        """Open file dialog to select a logo image."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Logo Image"),
            "",
            self.tr("Images (*.png *.svg *.jpg *.jpeg);;All Files (*)")
        )
        if path:
            self._logo_path_edit.setText(path)

    def _on_language_changed(self, text: str) -> None:
        """Update UI text when language changes."""
        self._update_ui_text()

    def _update_ui_text(self) -> None:
        """Update all UI labels based on selected language."""
        if not hasattr(self, "_lang_combo"):
            return
            
        lang = self._lang_combo.currentText()
        if lang not in TRANS_UI:
            lang = "es"
        tr = TRANS_UI[lang]
        
        self.setWindowTitle(tr["title"])
        
        # Navigation
        if hasattr(self, "_btn_back"):
            self._btn_back.setText(tr["back"])
        
        if hasattr(self, "_btn_next"):
            is_last = self._stack.currentIndex() == self._stack.count() - 1
            if is_last:
                self._btn_next.setText(tr["generate"])
            else:
                self._btn_next.setText(tr["next"])
        
        if hasattr(self, "_btn_cancel"):
             self._btn_cancel.setText(tr["cancel"])

        # Step 1
        if hasattr(self, "_lbl_step1_title"): self._lbl_step1_title.setText(f"<h3>{tr['step1_title']}</h3><p>{tr['step1_desc']}</p>")
        if hasattr(self, "_grp_layer"): self._grp_layer.setTitle(tr["grp_layer"])
        if hasattr(self, "_lbl_layer"): self._lbl_layer.setText(tr["layer"])
        if hasattr(self, "_grp_fields"): self._grp_fields.setTitle(tr["grp_fields"])
        if hasattr(self, "_lbl_id"): self._lbl_id.setText(tr["id_field"])
        if hasattr(self, "_lbl_name"): self._lbl_name.setText(tr["name_field"])
        if hasattr(self, "_grp_indicators"): self._grp_indicators.setTitle(tr["indicators"])
        
        # Step 2
        if hasattr(self, "_lbl_step2_title"): self._lbl_step2_title.setText(f"<h3>{tr['step2_title']}</h3><p>{tr['step2_desc']}</p>")
        if hasattr(self, "_grp_gen"): self._grp_gen.setTitle(tr["grp_gen"])
        if hasattr(self, "_lbl_lang"): self._lbl_lang.setText(tr["language"])
        if hasattr(self, "_lbl_template"): self._lbl_template.setText(tr["template"])
        if hasattr(self, "_lbl_logo"): self._lbl_logo.setText(tr["logo"])
        if hasattr(self, "_grp_map"): self._grp_map.setTitle(tr["grp_map"])
        if hasattr(self, "_lbl_style"): self._lbl_style.setText(tr["style"])
        if hasattr(self, "_lbl_ramp"): self._lbl_ramp.setText(tr["ramp"])
        if hasattr(self, "_chk_highlight"): self._chk_highlight.setText(tr["highlight"])
        if hasattr(self, "_chk_labels"): self._chk_labels.setText(tr["labels"])
        if hasattr(self, "_lbl_basemap"): self._lbl_basemap.setText(tr["basemap"])
        if hasattr(self, "_grp_ctx"): self._grp_ctx.setTitle(tr["grp_ctx"])
        if hasattr(self, "_chk_overview"): self._chk_overview.setText(tr["overview"])
        if hasattr(self, "_chk_overview_labels"): self._chk_overview_labels.setText(tr["overview_labels"])
        if hasattr(self, "_grp_legend"): self._grp_legend.setTitle(tr["grp_legend"])
        if hasattr(self, "_lbl_legend_title"): self._lbl_legend_title.setText(tr["legend_title"])
        if hasattr(self, "_lbl_layer_alias"): self._lbl_layer_alias.setText(tr["layer_alias"])
        if hasattr(self, "_grp_layout_settings"): self._grp_layout_settings.setTitle(tr["grp_layout"])
        if hasattr(self, "_lbl_title_override"): self._lbl_title_override.setText(tr["title_override"])
        if hasattr(self, "_lbl_footer_override"): self._lbl_footer_override.setText(tr["footer_override"])
        if hasattr(self, "_lbl_col_header"): self._lbl_col_header.setText(tr["col_header"])
        if hasattr(self, "_lbl_col_footer"): self._lbl_col_footer.setText(tr["col_footer"])
        
        # Step 3
        if hasattr(self, "_lbl_step3_title"): self._lbl_step3_title.setText(f"<h3>{tr['step3_title']}</h3><p>{tr['step3_desc']}</p>")
        if hasattr(self, "_grp_format"): self._grp_format.setTitle(tr["grp_format"])
        if hasattr(self, "_grp_dir"): self._grp_dir.setTitle(tr["grp_dir"])
        if hasattr(self, "_btn_browse"): self._btn_browse.setText(tr["browse"])

        if hasattr(self, "_btn_preview"): self._btn_preview.setText(tr["preview"])

    # ------------------------------------------------------------------
    # Context Layer Reorder
    # ------------------------------------------------------------------

    def _move_ctx_row(self, direction: int) -> None:
        """Move the selected context layer row up (-1) or down (+1)."""
        row = self._ctx_table.currentRow()
        if row < 0:
            return
        target = row + direction
        if target < 0 or target >= self._ctx_table.rowCount():
            return

        # Swap all column data between row and target
        for col in range(self._ctx_table.columnCount()):
            widget_a = self._ctx_table.cellWidget(row, col)
            widget_b = self._ctx_table.cellWidget(target, col)

            if widget_a or widget_b:
                # Spinbox column — swap values
                val_a = widget_a.value() if widget_a else 1.0
                val_b = widget_b.value() if widget_b else 1.0
                if widget_a:
                    widget_a.setValue(val_b)
                if widget_b:
                    widget_b.setValue(val_a)
            else:
                # QTableWidgetItem columns — swap items
                item_a = self._ctx_table.takeItem(row, col)
                item_b = self._ctx_table.takeItem(target, col)
                self._ctx_table.setItem(row, col, item_b)
                self._ctx_table.setItem(target, col, item_a)

        self._ctx_table.setCurrentCell(target, 0)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_next(self) -> None:
        if self._current_step == 0:
            is_valid, err_msg = self._controller.validate_step_data()
            if not is_valid:
                QMessageBox.warning(self, self.tr("Validation"), err_msg)
                return
            
            # Prepare Step 2 (Style)
            layer = self._layer_combo.currentLayer()
            if layer:
                # 1. Label Field
                self._label_field_combo.setLayer(layer)
                
                # 2. Context Layers — populate table
                self._ctx_table.setRowCount(0)
                project = QgsProject.instance()
                for lyr in project.mapLayers().values():
                    if lyr.id() == layer.id():
                        continue
                    row = self._ctx_table.rowCount()
                    self._ctx_table.insertRow(row)

                    # Col 0: Checkbox
                    chk_item = QTableWidgetItem()
                    chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    chk_item.setCheckState(Qt.Unchecked)
                    chk_item.setData(Qt.UserRole, lyr.id())
                    self._ctx_table.setItem(row, 0, chk_item)

                    # Col 1: Layer name (read-only)
                    name_item = QTableWidgetItem(lyr.name())
                    name_item.setFlags(Qt.ItemIsEnabled)
                    self._ctx_table.setItem(row, 1, name_item)

                    # Col 2: Legend Alias (editable)
                    alias_item = QTableWidgetItem("")
                    alias_item.setToolTip(self.tr("Custom name in legend"))
                    self._ctx_table.setItem(row, 2, alias_item)

                    # Col 3: Opacity spinner
                    spin = QDoubleSpinBox()
                    spin.setRange(0.0, 1.0)
                    spin.setSingleStep(0.1)
                    spin.setValue(1.0)
                    spin.setDecimals(1)
                    self._ctx_table.setCellWidget(row, 3, spin)

        if self._current_step == 1:
            pass # Style validation is implicitly true
        if self._current_step == 2:
            self._progress_bar.setVisible(True)
            self._progress_label.setVisible(True)
            self._btn_next.setText(self.tr("Cancel"))
            self._btn_next.setEnabled(True)
            self._btn_back.setEnabled(False)
            try:
                self._btn_next.clicked.disconnect()
            except TypeError:
                pass
            self._btn_next.clicked.connect(self._controller.cancel_generation)
            self._controller.start_generation()
            return

        self._current_step += 1
        self._stack.setCurrentIndex(self._current_step)
        self._btn_back.setEnabled(True)

        self._update_step_indicator()
        self._update_ui_text()

    def _go_back(self) -> None:
        if self._current_step <= 0:
            return

        self._current_step -= 1
        self._stack.setCurrentIndex(self._current_step)
        self._btn_back.setEnabled(self._current_step > 0)

        self._update_step_indicator()
        self._update_ui_text()



    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def update_progress(self, current: int, total: int, name: str) -> None:
        self._progress_bar.setValue(current)
        self._progress_label.setText(
            self.tr("Generating: {name} ({current}/{total})").format(
                name=name,
                current=current,
                total=total,
            )
        )

    def _on_batch_complete(self, paths: list, errors: list) -> None:
        """Called when all reports have been processed."""
        self._reset_buttons()
        n = len(paths)
        msg = self.tr("Generated {n} reports in:\n{dir}").format(
            n=n, dir=self._controller._batch_config.output_dir,
        )
        if errors:
            msg += self.tr("\n\n{e} errors (skipped):").format(e=len(errors))
            msg += "\n" + "\n".join(errors[:10])

        QMessageBox.information(self, self.tr("Success"), msg)
        self.accept()

    def _on_batch_cancelled(self) -> None:
        """Called when user cancels mid-batch."""
        self._reset_buttons()
        n = len(self._controller._batch_paths)
        QMessageBox.information(
            self,
            self.tr("Cancelled"),
            self.tr("Cancelled. {n} reports were generated before stopping.").format(n=n),
        )

    def _on_batch_error(self, error: str) -> None:
        """Called on fatal setup error."""
        self._reset_buttons()
        QMessageBox.critical(
            self,
            self.tr("Error"),
            self.tr("Report generation failed:\n{err}").format(err=error),
        )

    def _reset_buttons(self) -> None:
        """Restore footer buttons to normal state."""
        self._controller.cleanup()

        self._progress_bar.setVisible(False)
        self._progress_label.setVisible(False)
        self._btn_next.setText(self.tr("🚀 Generate"))
        self._btn_next.setEnabled(True)
        self._btn_back.setEnabled(True)
        try:
            self._btn_next.clicked.disconnect()
        except TypeError:
            pass
        self._btn_next.clicked.connect(self._go_next)

    def _on_preview_clicked(self) -> None:
        """Generate and show a preview of the report."""
        try:
            # 1. Build partial config from current UI state
            # Validation similar to _validate_step_data but permissive
            layer_name = self._layer_combo.currentText()
            layer = self._layer_combo.currentLayer()
            if not layer:
                QMessageBox.warning(self, self.tr("Warning"), self.tr("Please select a layer."))
                return

            id_field = self._id_field_combo.currentText()
            name_field = self._name_field_combo.currentText()
            
            indicators = []
            for i in range(self._indicator_list.count()):
                item = self._indicator_list.item(i)
                if item.checkState() == Qt.Checked:
                    indicators.append(item.text())
            
            if not indicators:
                QMessageBox.warning(self, self.tr("Warning"), self.tr("Please select at least one indicator."))
                return

            config = self._controller.build_config()
            
            # Override for preview (temp dir)
            from dataclasses import replace
            config = replace(
                config, 
                output_format=OutputFormat.PNG,
                output_dir=Path(tempfile.gettempdir()),
                dpi=96
            )

            # 2. Generate
            from qgis.PyQt.QtWidgets import QApplication
            
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                from ..core.report_composer import ReportComposer
                composer = ReportComposer()
                # Ensure layer is loaded in data engine
                # layout generation needs data
                preview_path = composer.generate_preview(config)
            finally:
                QApplication.restoreOverrideCursor()

            # 3. Show Dialog
            dlg = PreviewDialog(str(preview_path), self)
            dlg.exec_()

        except Exception as exc:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, self.tr("Preview Error"), str(exc))



class PreviewDialog(QDialog):
    """Dialog to display a generated report preview image."""

    def __init__(self, image_path: str, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Report Layout Preview"))
        self.resize(1000, 750)

        layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignCenter)
        
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.img_label.setPixmap(pixmap)
        else:
            self.img_label.setText(self.tr("Failed to load preview image."))
            
        scroll.setWidget(self.img_label)
        layout.addWidget(scroll)
        
        btn_close = QPushButton(self.tr("Close"))
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)
