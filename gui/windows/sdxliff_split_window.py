from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QMessageBox
)

from gui.ui_constants import HEADER_FRAME_STYLE
from gui.widgets.sdxliff_drop_area import SdxliffDropArea
from gui.dialogs.sdxliff_config_dialog import SdxliffConfigDialog


class SdxliffSplitWindow(QWidget):
    """Window providing drag&drop for SDXLIFF split/merge."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("SDXLIFF Split & Merge")
        self.setStyleSheet(HEADER_FRAME_STYLE)
        self.resize(400, 200)
        layout = QVBoxLayout(self)
        self.drop_area = SdxliffDropArea()
        layout.addWidget(self.drop_area)
        self.drop_area.files_dropped.connect(self.handle_files)

    def handle_files(self, files: List[str]):
        paths = [Path(f) for f in files if Path(f).suffix.lower() in {'.sdxliff', '.sdlxliff'}]
        if not paths:
            return
        dialog = SdxliffConfigDialog(paths, self)
        from PySide6.QtWidgets import QDialog
        if dialog.exec() == QDialog.Accepted:
            action, value = dialog.get_result()
            try:
                if action == 'split':
                    out_paths = self.controller.split_sdxliff_file(paths[0], parts=value)
                    QMessageBox.information(self, 'Готово', f'Создано файлов: {len(out_paths)}')
                else:
                    output = self.controller.merge_sdxliff_parts(paths, value)
                    QMessageBox.information(self, 'Готово', f'Файл создан: {output.name}')
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', str(e))

