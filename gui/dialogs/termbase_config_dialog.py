from __future__ import annotations

from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QCheckBox,
    QPushButton, QHBoxLayout, QLabel
)

from core.base import TermBaseConversionSettings


class TermbaseConfigDialog(QDialog):
    """Простое окно настройки конвертации терминологических баз."""

    def __init__(self, file_path: Path, languages: List[str], parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.languages = languages
        self.settings: TermBaseConversionSettings | None = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(f"Настройка Termbase: {self.file_path.name}")
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.lang_combo = QComboBox()
        for lang in self.languages:
            self.lang_combo.addItem(lang)
        form.addRow("Исходный язык:", self.lang_combo)

        self.tmx_cb = QCheckBox("Экспортировать TMX")
        self.tmx_cb.setChecked(True)
        form.addRow(self.tmx_cb)

        self.xlsx_cb = QCheckBox("Экспортировать XLSX")
        form.addRow(self.xlsx_cb)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        cancel_btn = QPushButton("Отмена")
        ok_btn = QPushButton("Конвертировать")
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self._on_accept)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(ok_btn)
        layout.addLayout(buttons)

    def _on_accept(self):
        self.settings = TermBaseConversionSettings(
            source_language=self.lang_combo.currentText(),
            export_tmx=self.tmx_cb.isChecked(),
            export_xlsx=self.xlsx_cb.isChecked(),
        )
        self.accept()

    def get_settings(self) -> TermBaseConversionSettings | None:
        return self.settings
