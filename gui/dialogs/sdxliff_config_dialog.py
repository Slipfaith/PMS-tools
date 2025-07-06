from pathlib import Path
from typing import List, Tuple
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSpinBox, QLabel, QPushButton,
    QLineEdit, QFormLayout
)


class SdxliffConfigDialog(QDialog):
    """Simple dialog to configure splitting or merging SDXLIFF files."""

    def __init__(self, filepaths: List[Path], parent=None):
        super().__init__(parent)
        self.filepaths = filepaths
        self.action: str | None = None
        self.parts: int = 2
        self.output: Path | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        if len(self.filepaths) == 1:
            self.setWindowTitle("Разделить SDXLIFF")
            form = QHBoxLayout()
            form.addWidget(QLabel("Части:"))
            self.parts_spin = QSpinBox()
            self.parts_spin.setRange(2, 100)
            form.addWidget(self.parts_spin)
            layout.addLayout(form)
            btn = QPushButton("Разделить")
            btn.clicked.connect(self._on_split)
            layout.addWidget(btn)
        else:
            self.setWindowTitle("Объединить SDXLIFF")
            form = QFormLayout()
            self.out_edit = QLineEdit(str(self.filepaths[0].parent / "merged.sdxliff"))
            form.addRow("Выходной файл:", self.out_edit)
            layout.addLayout(form)
            btn = QPushButton("Объединить")
            btn.clicked.connect(self._on_merge)
            layout.addWidget(btn)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)

    def _on_split(self):
        self.action = "split"
        self.parts = self.parts_spin.value()
        self.accept()

    def _on_merge(self):
        self.action = "merge"
        self.output = Path(self.out_edit.text())
        self.accept()

    def get_result(self) -> Tuple[str, int | Path]:
        return self.action, (self.parts if self.action == "split" else self.output)
