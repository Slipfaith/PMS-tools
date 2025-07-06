from pathlib import Path
from PySide6.QtWidgets import QWidget
from gui.ui_constants import HEADER_FRAME_STYLE


class SdxliffSplitWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SDXLIFF Split & Merge")
        self.setStyleSheet(HEADER_FRAME_STYLE)
        # Placeholder GUI implementation
        self.resize(400, 300)
        # Real GUI is not implemented in tests
