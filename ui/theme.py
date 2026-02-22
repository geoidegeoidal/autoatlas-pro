"""Global Qt Style Sheets (QSS) for AutoAtlas Pro UI."""

DARK_CORPORATE_QSS = """
QDialog {
    background-color: #0F172A;
    color: #E2E8F0;
    font-family: "Inter", "Segoe UI", sans-serif;
}

/* Group Boxes: Clean corporate cards */
QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 24px;
    padding-top: 18px;
    font-weight: 600;
    color: #94A3B8;
    background-color: #1E293B;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 4px;
    color: #38BDF8;
}

/* Typography & Labels */
QLabel {
    color: #E2E8F0;
    font-size: 13px;
}
QLabel h3 {
    color: #F8FAFC;
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 4px;
}

/* Inputs & Comboboxes */
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #0F172A;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 8px 12px;
    color: #F8FAFC;
    selection-background-color: #0284C7;
    font-size: 13px;
}
QComboBox:hover, QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #64748B;
}
QComboBox:focus, QLineEdit:focus {
    border: 2px solid #38BDF8;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #1E293B;
    color: #F8FAFC;
    selection-background-color: #0284C7;
    border: 1px solid #334155;
}

/* Standard Buttons */
QPushButton {
    background-color: #334155;
    border: 1px solid #475569;
    color: #F8FAFC;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #475569;
    border: 1px solid #94A3B8;
}
QPushButton:pressed {
    background-color: #1E293B;
}
QPushButton:disabled {
    background-color: #0F172A;
    color: #64748B;
    border: 1px solid #334155;
}

/* Primary Generate Button Override (Done inline usually, but base class here) */
QPushButton#primary_action {
    background-color: #0284C7;
    color: white;
    border: none;
    font-size: 14px;
}
QPushButton#primary_action:hover {
    background-color: #0369A1;
}

/* Tables */
QTableWidget {
    background-color: #0F172A;
    color: #E2E8F0;
    gridline-color: #334155;
    border: 1px solid #334155;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #1E293B;
    color: #94A3B8;
    padding: 6px;
    border: 1px solid #334155;
    font-weight: bold;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #0F172A;
    width: 14px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #475569;
    min-height: 20px;
    border-radius: 7px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #64748B;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Checkboxes and Radio buttons */
QCheckBox, QRadioButton {
    color: #E2E8F0;
    spacing: 8px;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #475569;
    border-radius: 4px;
    background: #0F172A;
}
QRadioButton::indicator {
    border-radius: 9px;
}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border: 1px solid #38BDF8;
}
QCheckBox::indicator:checked {
    background: #0284C7;
    image: url(:/images/themes/default/algorithms/mAlgorithmCheckGeometry.svg); /* Native QGIS icon fallback */
}
QRadioButton::indicator:checked {
    background: #0284C7;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #334155;
    border-radius: 6px;
    background-color: #0F172A;
    text-align: center;
    color: white;
    font-weight: bold;
}
QProgressBar::chunk {
    background-color: #38BDF8;
    border-radius: 5px;
}
"""
