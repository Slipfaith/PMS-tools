from .drop_area import SmartDropArea


class SdxliffDropArea(SmartDropArea):
    """Drop area that accepts only SDXLIFF files."""

    def __init__(self):
        super().__init__()
        self.main_label.setText("Перетащите SDXLIFF файлы")
        self.formats_label.setText("SDXLIFF")

    def open_file_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите SDXLIFF файлы",
            "",
            "SDXLIFF (*.sdxliff *.sdlxliff)"
        )
        if files:
            self.files_dropped.emit(files)
            self.format_label.setText(f"✅ Выбрано файлов: {len(files)}")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, self.reset_style)
