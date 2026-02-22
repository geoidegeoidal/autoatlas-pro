"""Global Qt Style Sheets (QSS) for AutoAtlas Pro UI.

Design principles:
- Only style OUR dialog's widgets. Never use bare `QWidget {}` selectors
  as they bleed into QGIS-native widgets (QgsColorButton, QgsOpacityWidget,
  QgsFieldComboBox) and corrupt their rendering.
- All colors target WCAG AA contrast ratio (4.5:1 minimum for text).
- No QGraphicsOpacityEffect: it causes text-ghosting artefacts in Qt
  when applied to container widgets with complex children.
"""

DARK_CORPORATE_QSS = """
/* ─── Dialog root ─── */
QDialog {
    background-color: #1E293B;
    color: #F1F5F9;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

/* ─── Header frame ─── */
QFrame#header_frame {
    background-color: #0F172A;
}

/* ─── Stacked pages & scroll areas ─── */
QStackedWidget {
    background-color: #1E293B;
}
QScrollArea {
    background-color: #1E293B;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background-color: #1E293B;
}

/* ─── Group Boxes ─── */
QGroupBox {
    background-color: #273548;
    border: 1px solid #3B4F6B;
    border-radius: 6px;
    margin-top: 20px;
    padding: 20px 12px 12px 12px;
    font-weight: bold;
    font-size: 13px;
    color: #F1F5F9;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 2px 6px;
    color: #7DD3FC;
    background-color: #273548;
    border-radius: 3px;
}

/* ─── Labels ─── */
QLabel {
    color: #F1F5F9;
    background: transparent;
}

/* ─── Inputs ─── */
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #1E293B;
    border: 1px solid #475569;
    border-radius: 4px;
    padding: 6px 10px;
    color: #F1F5F9;
    selection-background-color: #0284C7;
}
QComboBox:hover, QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #7DD3FC;
}
QComboBox:focus, QLineEdit:focus {
    border: 1px solid #38BDF8;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background-color: #273548;
    color: #F1F5F9;
    selection-background-color: #0284C7;
    border: 1px solid #475569;
}

/* ─── Buttons ─── */
QPushButton {
    background-color: #334155;
    border: 1px solid #475569;
    color: #F1F5F9;
    padding: 7px 14px;
    border-radius: 4px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #475569;
    border-color: #7DD3FC;
}
QPushButton:pressed {
    background-color: #1E293B;
}
QPushButton:disabled {
    color: #64748B;
    background-color: #1E293B;
    border-color: #334155;
}

/* ─── Tables & Lists ─── */
QTableWidget, QListWidget {
    background-color: #1E293B;
    alternate-background-color: #273548;
    color: #F1F5F9;
    gridline-color: #334155;
    border: 1px solid #3B4F6B;
    border-radius: 4px;
}
QHeaderView::section {
    background-color: #273548;
    color: #CBD5E1;
    padding: 5px;
    border: 1px solid #3B4F6B;
    font-weight: bold;
}
QListWidget::item {
    padding: 3px;
}
QListWidget::item:selected {
    background-color: #0284C7;
}

/* ─── Scrollbars ─── */
QScrollBar:vertical {
    background: #1E293B;
    width: 12px;
}
QScrollBar::handle:vertical {
    background: #475569;
    min-height: 20px;
    border-radius: 6px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #64748B;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    height: 0px;
}

/* ─── Checkboxes & Radios ─── */
QCheckBox, QRadioButton {
    color: #F1F5F9;
    spacing: 6px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #475569;
    border-radius: 3px;
    background: #1E293B;
}
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: #0284C7;
    border-color: #38BDF8;
}

/* ─── Progress Bar ─── */
QProgressBar {
    border: 1px solid #334155;
    border-radius: 4px;
    background-color: #1E293B;
    text-align: center;
    color: #F1F5F9;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #38BDF8;
    border-radius: 3px;
}
"""
