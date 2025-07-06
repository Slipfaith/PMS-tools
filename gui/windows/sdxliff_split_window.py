from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QSpinBox,
    QLabel,
    QProgressBar,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
)

from gui.ui_constants import HEADER_FRAME_STYLE


class SdxliffSplitWindow(QWidget):
    """Window with tabs for splitting and merging SDXLIFF files."""

    def __init__(self, controller, files: List[Path], parent=None):
        super().__init__(parent)
        self.controller = controller
        self.files: List[Path] = files
        self.setWindowTitle("SDXLIFF Split & Merge")
        self.setStyleSheet(HEADER_FRAME_STYLE)
        self.resize(500, 300)
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._create_split_tab()
        self._create_merge_tab()
        self._populate_merge_files()

    # ------------------------------------------------------------------
    # Split Tab
    # ------------------------------------------------------------------
    def _create_split_tab(self):
        widget = QWidget()
        tab_layout = QVBoxLayout(widget)

        radio_layout = QHBoxLayout()
        self.parts_radio = QRadioButton("по частям")
        self.words_radio = QRadioButton("по словам")
        self.parts_radio.setChecked(True)
        self.radio_group = QButtonGroup(widget)
        self.radio_group.addButton(self.parts_radio)
        self.radio_group.addButton(self.words_radio)
        radio_layout.addWidget(self.parts_radio)
        radio_layout.addWidget(self.words_radio)
        radio_layout.addStretch()
        tab_layout.addLayout(radio_layout)

        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 9999)
        tab_layout.addWidget(self.count_spin)

        analyze_layout = QHBoxLayout()
        self.analyze_btn = QPushButton("Анализировать")
        self.analyze_btn.clicked.connect(self.analyze_file)
        analyze_layout.addWidget(self.analyze_btn)
        analyze_layout.addStretch()
        tab_layout.addLayout(analyze_layout)

        self.stats_table = QTableWidget(2, 2)
        self.stats_table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stats_table.setItem(0, 0, QTableWidgetItem("Сегментов"))
        self.stats_table.setItem(1, 0, QTableWidgetItem("Слов"))
        tab_layout.addWidget(self.stats_table)

        self.split_btn = QPushButton("Разделить")
        self.split_btn.clicked.connect(self.do_split)
        tab_layout.addWidget(self.split_btn)

        self.split_progress = QProgressBar()
        tab_layout.addWidget(self.split_progress)

        self.tabs.addTab(widget, "Разделить")

    # ------------------------------------------------------------------
    # Merge Tab
    # ------------------------------------------------------------------
    def _create_merge_tab(self):
        widget = QWidget()
        tab_layout = QVBoxLayout(widget)

        self.file_list = QListWidget()
        tab_layout.addWidget(self.file_list)

        self.merge_btn = QPushButton("Объединить")
        self.merge_btn.clicked.connect(self.do_merge)
        tab_layout.addWidget(self.merge_btn)

        self.merge_progress = QProgressBar()
        tab_layout.addWidget(self.merge_progress)

        self.tabs.addTab(widget, "Объединить")

    def set_files(self, files: List[Path]):
        self.files = files
        self._populate_merge_files()

    # ------------------------------------------------------------------
    def analyze_file(self):
        if not self.files:
            return
        try:
            info = self.controller.analyze_sdxliff_file(self.files[0])
            self.stats_table.setItem(
                0, 1, QTableWidgetItem(str(info.get("segments", 0)))
            )
            self.stats_table.setItem(1, 1, QTableWidgetItem(str(info.get("words", 0))))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def do_split(self):
        if not self.files:
            return
        kwargs = {}
        if self.parts_radio.isChecked():
            kwargs["parts"] = self.count_spin.value()
        else:
            kwargs["words"] = self.count_spin.value()
        try:
            out_paths = self.controller.split_sdxliff_file(self.files[0], **kwargs)
            QMessageBox.information(self, "Готово", f"Создано файлов: {len(out_paths)}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _populate_merge_files(self):
        self.file_list.clear()
        valid = self._validate_parts(self.files)
        for p in self.files:
            item = QListWidgetItem(p.name)
            item.setText(f"{'✅' if valid else '❌'} {p.name}")
            self.file_list.addItem(item)
        self.merge_btn.setEnabled(valid)

    def _validate_parts(self, files: List[Path]) -> bool:
        if not files:
            return False
        try:
            from lxml import etree

            metas = []
            for f in files:
                tree = etree.parse(str(f))
                file_elem = tree.getroot().find(".//{*}file")
                metas.append(
                    (
                        file_elem.get("original_file_id"),
                        int(file_elem.get("part_number", "0")),
                        int(file_elem.get("total_parts", "0")),
                    )
                )
            file_id = metas[0][0]
            total = metas[0][2]
            numbers = {m[1] for m in metas}
            if len(metas) != total:
                return False
            if numbers != set(range(1, total + 1)):
                return False
            for fid, _, t in metas:
                if fid != file_id or t != total:
                    return False
            return True
        except Exception:
            return False

    def do_merge(self):
        if not self.files:
            return
        out_file, _ = QFileDialog.getSaveFileName(
            self, "Выберите файл", "merged.sdxliff", "SDXLIFF (*.sdxliff)"
        )
        if not out_file:
            return
        try:
            out = self.controller.merge_sdxliff_parts(self.files, Path(out_file))
            QMessageBox.information(self, "Готово", f"Файл создан: {out.name}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
