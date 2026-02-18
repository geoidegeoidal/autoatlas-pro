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
    QSizePolicy,
    QSpacerItem,
    QScrollArea,
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
    BaseMapType, ChartType, ContextLayerConfig, MapStyle, OutputFormat, ReportConfig,
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

        self.setWindowTitle(self.tr("AutoAtlas Pro — Report Wizard"))
        self.setMinimumSize(QSize(680, 520))
        self.setModal(True)

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
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: #0f3460; padding: 16px; }"
        )
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
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._lbl_step1_title = QLabel(
            f"<h3>{self.tr('Select Data Source')}</h3>"
            f"<p>{self.tr('Choose the vector layer and fields for your report.')}</p>"
        )
        layout.addWidget(self._lbl_step1_title)

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

    def _on_layer_changed(self, layer: Optional[QgsVectorLayer]) -> None:
        """Populate field combos when layer selection changes."""
        self._id_field_combo.clear()
        self._name_field_combo.clear()
        self._indicator_list.clear()

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

        # Row 1: Language & Template
        row_lt = QHBoxLayout()
        self._lbl_lang = QLabel(self.tr("Language:"))
        row_lt.addWidget(self._lbl_lang)
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["es", "en"])
        self._lang_combo.setToolTip(self.tr("Language for report text (Source, Date, etc.)"))
        self._lang_combo.currentTextChanged.connect(self._on_language_changed)
        row_lt.addWidget(self._lang_combo)

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
        
        # Row 1: Style & Ramp
        row1 = QHBoxLayout()
        self._lbl_style = QLabel(self.tr("Style:"))
        row1.addWidget(self._lbl_style)
        self._style_combo = QComboBox()
        for s in MapStyle:
            self._style_combo.addItem(s.value, s)
        row1.addWidget(self._style_combo)
        
        self._lbl_ramp = QLabel(self.tr("Ramp:"))
        row1.addWidget(self._lbl_ramp)
        self._ramp_combo = QComboBox()
        self._ramp_combo.addItems(["Spectral", "Viridis", "Plasma", "Blues", "Reds", "Greens", "Magma", "Inferno"])
        row1.addWidget(self._ramp_combo)
        map_layout.addLayout(row1)

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
            if not self._validate_step_data():
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

        if self._current_step == 1 and not self._validate_step_style():
            return
        if self._current_step == 2:
            self._generate_reports()
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
    # Validation
    # ------------------------------------------------------------------

    def _validate_step_data(self) -> bool:
        layer = self._layer_combo.currentLayer()
        if not layer:
            QMessageBox.warning(self, self.tr("Validation"), self.tr("Please select a coverage layer."))
            return False
            
        # Check indicators
        has_indic = False
        for i in range(self._indicator_list.count()):
            if self._indicator_list.item(i).checkState() == Qt.Checked:
                has_indic = True
                break
        
        if not has_indic:
            QMessageBox.warning(self, self.tr("Validation"), self.tr("Please select at least one indicator field."))
            return False

        return True

    def _validate_step_style(self) -> bool:
        # All style options have defaults, so always valid
        return True

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def _build_config(self) -> ReportConfig:
        """Build a ReportConfig from the wizard's current state."""
        layer = self._layer_combo.currentLayer()

        indicator_fields = []
        for i in range(self._indicator_list.count()):
            item = self._indicator_list.item(i)
            if item.checkState() == Qt.Checked:
                indicator_fields.append(item.text())

        # Map Style settings
        map_style = self._style_combo.currentData()
        ramp_name = self._ramp_combo.currentText()
        base_map = self._basemap_combo.currentData()
        
        # New Phase 11 settings
        map_opacity = self._opacity_widget.opacity()
        highlight = self._chk_highlight.isChecked()
        
        label_field = None
        if self._chk_labels.isChecked():
            label_field = self._label_field_combo.currentField()
            
        context_configs: List[ContextLayerConfig] = []
        for i in range(self._ctx_table.rowCount()):
            chk = self._ctx_table.item(i, 0)
            if chk and chk.checkState() == Qt.Checked:
                lid = chk.data(Qt.UserRole)
                alias = (self._ctx_table.item(i, 2).text() or "").strip()
                spin = self._ctx_table.cellWidget(i, 3)
                opa = spin.value() if spin else 1.0
                context_configs.append(
                    ContextLayerConfig(layer_id=lid, legend_alias=alias, opacity=opa)
                )

        show_overview_map = self._chk_overview.isChecked()
        show_overview_labels = self._chk_overview_labels.isChecked()
        layer_legend_alias = self._layer_alias_edit.text().strip()

        # Layout settings
        custom_title = self._title_edit.text()
        custom_footer = self._footer_edit.text()
        header_color = self._col_header.color().name()
        footer_color = self._col_footer.color().name()

        # General Settings
        language = self._lang_combo.currentText()
        template_name = self._template_combo.currentText()
        logo_path = self._logo_path_edit.text().strip()
        logo_pos = self._logo_pos_combo.currentText()
        variable_alias = self._alias_edit.text().strip()

        # Charts (removed in Phase 9)
        chart_types = []
        
        output_format = OutputFormat.PDF if self._radio_pdf.isChecked() else OutputFormat.PNG
        output_dir = Path(self._dir_edit.text().strip())

        return ReportConfig(
            layer_id=layer.id(),
            id_field=self._id_field_combo.currentText(),
            name_field=self._name_field_combo.currentText(),
            indicator_fields=indicator_fields,
            map_style=map_style,
            color_ramp_name=ramp_name,
            base_map=base_map,
            chart_types=chart_types,
            output_format=output_format,
            output_dir=output_dir,
            dpi=self._dpi_spin.value(),
            # Phase 11
            map_opacity=map_opacity,
            highlight_analyzed=highlight,
            label_field=label_field,
            context_layers_config=context_configs,
            show_overview_map=show_overview_map,
            show_overview_labels=show_overview_labels,
            layer_legend_alias=layer_legend_alias,
            custom_title=custom_title,
            custom_footer=custom_footer,
            header_color=header_color,
            footer_color=footer_color,
            language=language,
            template_name=template_name,
            logo_path=logo_path,
            logo_position=logo_pos,
            variable_alias=variable_alias,
        )

    def _generate_reports(self) -> None:
        """Validate output step and launch async generation."""
        output_dir = self._dir_edit.text().strip()
        if not output_dir:
            self._dir_edit.setText(str(Path.home() / "AutoAtlas_Output"))

        config = self._build_config()

        # Show progress UI
        self._progress_bar.setVisible(True)
        self._progress_label.setVisible(True)
        self._btn_next.setText(self.tr("Cancel"))
        self._btn_next.setEnabled(True)
        self._btn_back.setEnabled(False)

        # Disconnect old signal and connect cancel
        try:
            self._btn_next.clicked.disconnect()
        except TypeError:
            pass
        self._btn_next.clicked.connect(self._cancel_generation)

        # Initialize batch state
        self._cancelled = False
        self._batch_config = config
        self._batch_paths: list[Path] = []
        self._batch_errors: list[str] = []

        try:
            from ..core.report_composer import ReportComposer

            self._composer = ReportComposer()

            # Load data and apply renderer ONCE
            layer = self._composer._resolve_layer(config.layer_id)
            self._batch_layer = layer
            self._composer._data_engine.load(
                layer, config.id_field, config.name_field,
                config.indicator_fields,
            )

            primary = config.indicator_fields[0]
            self._batch_primary = primary

            # Apply renderer once (includes opacity)
            self._composer._apply_renderer(layer, config, primary)

            # Pre-compute shared data
            self._batch_stats = self._composer._data_engine.compute_stats(primary)
            self._batch_ranking = self._composer._data_engine.compute_ranking(
                primary, ascending=False,
            )

            feature_ids = (
                config.feature_ids
                or self._composer._data_engine.feature_ids
            )
            self._batch_ids = list(feature_ids)
            self._batch_index = 0
            self._batch_total = len(self._batch_ids)
            self._batch_template = config.template or None
            
            # Create base layer for the batch
            self._batch_base_layer = self._composer._create_base_map_layer(config.base_map)

            self._progress_bar.setRange(0, self._batch_total)
            self._progress_bar.setValue(0)

            config.output_dir.mkdir(parents=True, exist_ok=True)

            # Start async loop — process first report after yielding to event loop
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(0, self._process_next_report)

        except Exception as exc:
            self._on_batch_error(str(exc))

    def _process_next_report(self) -> None:
        """Process one report, then schedule the next via QTimer."""
        if self._cancelled:
            self._on_batch_cancelled()
            return

        if self._batch_index >= self._batch_total:
            self._on_batch_complete()
            return

        fid = self._batch_ids[self._batch_index]
        name = self._composer._data_engine._names_cache.get(fid, str(fid))

        # Update progress
        self._progress_bar.setValue(self._batch_index + 1)
        self._progress_label.setText(
            self.tr("Generating: {name} ({current}/{total})").format(
                name=name,
                current=self._batch_index + 1,
                total=self._batch_total,
            )
        )

        try:
            path = self._composer._generate_single(
                self._batch_config,
                self._batch_layer,
                self._batch_template or self._composer._resolve_template(),
                fid,
                name,
                self._batch_primary,
                self._batch_stats,
                self._batch_ranking,
                self._batch_base_layer,
            )
            self._batch_paths.append(path)
        except Exception as exc:
            self._batch_errors.append(f"{name}: {exc}")

        self._batch_index += 1

        # Periodic garbage collection
        if self._batch_index % 10 == 0:
            import gc
            gc.collect()

        # Schedule next report — yields back to Qt event loop
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(0, self._process_next_report)

    def _cancel_generation(self) -> None:
        """Set cancel flag — processing stops on next iteration."""
        self._cancelled = True
        self._progress_label.setText(self.tr("Cancelling..."))
        self._btn_next.setEnabled(False)

    def _on_batch_complete(self) -> None:
        """Called when all reports have been processed."""
        self._reset_buttons()
        n = len(self._batch_paths)
        msg = self.tr("Generated {n} reports in:\n{dir}").format(
            n=n, dir=self._batch_config.output_dir,
        )
        if self._batch_errors:
            msg += self.tr("\n\n{e} errors (skipped):").format(e=len(self._batch_errors))
            msg += "\n" + "\n".join(self._batch_errors[:10])

        QMessageBox.information(self, self.tr("Success"), msg)
        self.accept()

    def _on_batch_cancelled(self) -> None:
        """Called when user cancels mid-batch."""
        self._reset_buttons()
        n = len(self._batch_paths)
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
        # Cleanup base layer
        if getattr(self, "_batch_base_layer", None):
            try:
                self._composer._project.removeMapLayer(self._batch_base_layer.id())
            except Exception:
                pass
            self._batch_base_layer = None

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

            map_style = self._style_combo.currentData()
            if not map_style: # Fallback
                map_style = MapStyle.CHOROPLETH
                if self._radio_categorical.isChecked() if hasattr(self, '_radio_categorical') else False:
                    map_style = MapStyle.CATEGORICAL

            ramp = self._ramp_combo.currentText()

            chart_types: List[ChartType] = []
            # Charts removed (or logic moved to _build_config)
            # We should reuse _build_config() or logic here
            # using _build_config() is safer but it returns ReportConfig
            # So I will replicate logic or call it if possible.
            # But _build_config accesses all widgets, which is fine since we are in Step 2.
            
            # Update: I will use _build_config() logic but with checks?
            # actually _build_config reads from UI directly.
            
            config = self._build_config()
            
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
