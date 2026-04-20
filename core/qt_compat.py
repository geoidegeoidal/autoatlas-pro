from qgis.PyQt.QtCore import Qt

try:
    ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
    ALIGN_LEFT = Qt.AlignmentFlag.AlignLeft
    ALIGN_RIGHT = Qt.AlignmentFlag.AlignRight
    ALIGN_VCENTER = Qt.AlignmentFlag.AlignVCenter
    CHECKED = Qt.CheckState.Checked
    UNCHECKED = Qt.CheckState.Unchecked
    ITEM_IS_USER_CHECKABLE = Qt.ItemFlag.ItemIsUserCheckable
    ITEM_IS_ENABLED = Qt.ItemFlag.ItemIsEnabled
    WAIT_CURSOR = Qt.CursorShape.WaitCursor
    USER_ROLE = Qt.ItemDataRole.UserRole
except AttributeError:
    ALIGN_CENTER = Qt.AlignCenter
    ALIGN_LEFT = Qt.AlignLeft
    ALIGN_RIGHT = Qt.AlignRight
    ALIGN_VCENTER = Qt.AlignVCenter
    CHECKED = Qt.Checked
    UNCHECKED = Qt.Unchecked
    ITEM_IS_USER_CHECKABLE = Qt.ItemIsUserCheckable
    ITEM_IS_ENABLED = Qt.ItemIsEnabled
    WAIT_CURSOR = Qt.WaitCursor
    USER_ROLE = Qt.UserRole

try:
    from qgis.PyQt.QtWidgets import QAbstractItemView, QFrame, QHeaderView, QSizePolicy
    MULTI_SELECTION = QAbstractItemView.SelectionMode.MultiSelection
    NO_FRAME = QFrame.Shape.NoFrame
    STYLED_PANEL = QFrame.Shape.StyledPanel
    RESIZE_TO_CONTENTS = QHeaderView.ResizeMode.ResizeToContents
    STRETCH = QHeaderView.ResizeMode.Stretch
    NO_DRAG_DROP = QAbstractItemView.DragDropMode.NoDragDrop
    POLICY_MINIMUM = QSizePolicy.Policy.Minimum
    POLICY_EXPANDING = QSizePolicy.Policy.Expanding
except AttributeError:
    from qgis.PyQt.QtWidgets import QAbstractItemView, QFrame, QHeaderView, QSizePolicy
    MULTI_SELECTION = QAbstractItemView.MultiSelection
    NO_FRAME = QFrame.NoFrame
    STYLED_PANEL = QFrame.StyledPanel
    RESIZE_TO_CONTENTS = QHeaderView.ResizeToContents
    STRETCH = QHeaderView.Stretch
    NO_DRAG_DROP = QAbstractItemView.NoDragDrop
    POLICY_MINIMUM = QSizePolicy.Minimum
    POLICY_EXPANDING = QSizePolicy.Expanding
