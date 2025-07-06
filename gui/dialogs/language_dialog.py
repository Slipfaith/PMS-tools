from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QHBoxLayout, QPushButton
)
from PySide6.QtCore import Qt


class LanguageDialog(QDialog):
    """Диалог ручной настройки языков"""

    def __init__(self, source: str = "", target: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Языки файла")
        self.source = source
        self.target = target
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.src_edit = QLineEdit(self.source)
        self.tgt_edit = QLineEdit(self.target)
        form.addRow("Исходный:", self.src_edit)
        form.addRow("Целевой:", self.tgt_edit)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Отмена")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(ok_btn)
        layout.addLayout(buttons)

    def get_languages(self) -> tuple[str, str]:
        return self.src_edit.text().strip(), self.tgt_edit.text().strip()
