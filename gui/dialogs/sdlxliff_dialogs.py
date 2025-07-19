# gui/dialogs/sdlxliff_dialogs.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QSpinBox, QRadioButton, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QMessageBox, QCheckBox,
    QLineEdit, QFormLayout
)
from PySide6.QtCore import Qt, Signal
import re
from gui.widgets.drop_area import SmartDropArea
from pathlib import Path
from typing import List, Optional
import logging

from sdlxliff_split_merge import SdlxliffSplitSettings, SdlxliffMergeSettings, SdlxliffAnalyzer

logger = logging.getLogger(__name__)


class SdlxliffSplitDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filepath = None
        self.file_info = None
        self.settings = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Разделение SDLXLIFF файла")
        self.resize(400, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        header = QLabel("✂️ Настройка разделения SDLXLIFF файла")
        header.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #333;
                margin: 10px 0;
                padding: 10px;
                background: #f0f8ff;
                border-radius: 8px;
                border: 1px solid #ddd;
            }
        """)
        layout.addWidget(header)

        # Группа с drop area
        self.drop_group = self.create_drop_area_group()
        layout.addWidget(self.drop_group)

        self.info_group = self.create_file_info_group()
        layout.addWidget(self.info_group)

        self.split_group = self.create_split_settings_group()
        layout.addWidget(self.split_group)

        self.output_group = self.create_output_group()
        layout.addWidget(self.output_group)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 1px solid #ddd;
                border-radius: 5px;
                background: #f5f5f5;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #e5e5e5;
                border-color: #bbb;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        self.split_btn = QPushButton("✂️ Разделить")
        self.split_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                padding: 10px 30px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #45a049;
            }
        """)
        self.split_btn.clicked.connect(self.accept_split)
        self.split_btn.setEnabled(False)

        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(self.split_btn)

        layout.addLayout(buttons_layout)

        self.info_group.hide()
        self.split_group.hide()
        self.output_group.hide()

    def create_drop_area_group(self) -> QGroupBox:
        group = QGroupBox("📄 Выберите SDLXLIFF файл")
        layout = QVBoxLayout(group)

        self.drop_area = SmartDropArea()
        self.drop_area.files_dropped.connect(self.on_file_dropped)
        self.drop_area.files_dragged.connect(self.on_files_dragged)

        layout.addWidget(self.drop_area)

        return group

    def create_file_info_group(self) -> QGroupBox:
        group = QGroupBox("📄 Информация о файле")
        layout = QFormLayout(group)

        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-weight: bold;")
        layout.addRow("Имя файла:", self.name_label)

        self.size_label = QLabel()
        layout.addRow("Размер:", self.size_label)

        self.segments_label = QLabel()
        layout.addRow("Сегментов:", self.segments_label)

        # Добавляем строку с количеством слов
        self.words_label = QLabel()
        self.words_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        layout.addRow("Всего слов:", self.words_label)

        self.est_label = QLabel()
        self.est_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addRow("Оценка:", self.est_label)

        return group

    def create_split_settings_group(self) -> QGroupBox:
        group = QGroupBox("⚙️ Метод разделения")
        layout = QVBoxLayout(group)

        self.equal_parts_radio = QRadioButton("На равные части")
        self.equal_parts_radio.setChecked(True)
        self.equal_parts_radio.toggled.connect(self.on_method_changed)
        layout.addWidget(self.equal_parts_radio)

        parts_layout = QHBoxLayout()
        parts_layout.setContentsMargins(20, 0, 0, 0)

        parts_layout.addWidget(QLabel("Количество частей:"))

        self.parts_spin = QSpinBox()
        self.parts_spin.setMinimum(2)
        self.parts_spin.setMaximum(100)
        self.parts_spin.setValue(2)
        self.parts_spin.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        parts_layout.addWidget(self.parts_spin)

        parts_layout.addStretch()
        layout.addLayout(parts_layout)

        self.by_words_radio = QRadioButton("По количеству слов")
        self.by_words_radio.toggled.connect(self.on_method_changed)
        layout.addWidget(self.by_words_radio)

        words_layout = QHBoxLayout()
        words_layout.setContentsMargins(20, 0, 0, 0)

        words_layout.addWidget(QLabel("Слов на часть:"))

        self.words_spin = QSpinBox()
        self.words_spin.setMinimum(100)
        self.words_spin.setMaximum(50000)
        self.words_spin.setValue(2000)
        self.words_spin.setSingleStep(100)
        self.words_spin.setEnabled(False)
        self.words_spin.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QSpinBox:disabled {
                background: #f5f5f5;
            }
        """)
        words_layout.addWidget(self.words_spin)

        words_layout.addStretch()
        layout.addLayout(words_layout)

        self.result_info = QLabel("")
        self.result_info.setStyleSheet("color: #666; font-style: italic; margin-top: 10px;")
        layout.addWidget(self.result_info)

        self.parts_spin.valueChanged.connect(self.update_result_info)
        self.words_spin.valueChanged.connect(self.update_result_info)

        return group

    def create_output_group(self) -> QGroupBox:
        group = QGroupBox("📁 Директория для сохранения")
        layout = QVBoxLayout(group)

        path_layout = QHBoxLayout()

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("По умолчанию - папка исходного файла")
        self.output_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        path_layout.addWidget(self.output_edit)

        browse_btn = QPushButton("📂 Обзор...")
        browse_btn.clicked.connect(self.browse_output_dir)
        browse_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
            }
            QPushButton:hover {
                background: #f5f5f5;
                border-color: #bbb;
            }
        """)
        path_layout.addWidget(browse_btn)

        layout.addLayout(path_layout)

        info_label = QLabel("💡 Файлы будут названы: filename.1of3.sdlxliff, filename.2of3.sdlxliff, ...")
        info_label.setStyleSheet("color: #666; font-size: 11px; margin-top: 5px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        return group

    def on_files_dragged(self, filepaths: List[str]):
        valid_files = [f for f in filepaths if f.lower().endswith('.sdlxliff')]
        if valid_files:
            self.drop_area.set_format_info("SDLXLIFF", True)
        else:
            self.drop_area.set_format_info("Неподдерживаемые файлы", False)

    def on_file_dropped(self, filepaths: List[str]):
        valid_files = [f for f in filepaths if f.lower().endswith('.sdlxliff')]

        if not valid_files:
            QMessageBox.warning(self, "Ошибка", "Выберите SDLXLIFF файл")
            return

        if len(valid_files) > 1:
            QMessageBox.warning(self, "Ошибка", "Выберите только один файл для разделения")
            return

        filepath = Path(valid_files[0])
        self.set_file(filepath)

    def set_file(self, filepath: Path):
        try:
            from sdlxliff_split_merge import SdlxliffAnalyzer
            converter = SdlxliffAnalyzer()

            if not converter.can_handle(filepath):
                QMessageBox.warning(self, "Ошибка", "Файл не является SDLXLIFF")
                return

            self.file_info = converter.analyze_file(filepath)

            if not self.file_info.get('valid', False):
                error = self.file_info.get('error', 'Неизвестная ошибка')
                QMessageBox.warning(self, "Ошибка", f"Некорректный SDLXLIFF файл:\n{error}")
                return

            self.filepath = filepath
            self.update_file_info()

            # Скрываем drop area после успешной загрузки файла
            self.drop_group.hide()

            self.info_group.show()
            self.split_group.show()
            self.output_group.show()

            self.split_btn.setEnabled(True)
            self.update_result_info()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка анализа файла:\n{e}")

    def update_file_info(self):
        if not self.filepath or not self.file_info:
            return

        self.name_label.setText(self.filepath.name)

        size_mb = self.file_info.get('file_size_mb', 0)
        self.size_label.setText(f"{size_mb:.1f} MB")

        segments = self.file_info.get('segments_count', 0)
        self.segments_label.setText(f"{segments:,}")

        # Добавляем общее количество слов
        total_words = self.file_info.get('words_count', 0)
        self.words_label.setText(f"{total_words:,}")

        if self.file_info.get('valid', False):
            est_1000 = self.file_info.get('estimated_parts_1000_words', 0)
            est_2000 = self.file_info.get('estimated_parts_2000_words', 0)
            est_5000 = self.file_info.get('estimated_parts_5000_words', 0)

            est_text = f"1000 слов: {est_1000} частей | 2000 слов: {est_2000} частей | 5000 слов: {est_5000} частей"
            self.est_label.setText(est_text)

    def on_method_changed(self):
        by_words = self.by_words_radio.isChecked()
        self.parts_spin.setEnabled(not by_words)
        self.words_spin.setEnabled(by_words)
        self.update_result_info()

    def update_result_info(self):
        if not self.file_info:
            return

        segments = self.file_info.get('segments_count', 0)
        words = self.file_info.get('words_count', 0)

        if self.equal_parts_radio.isChecked():
            parts = self.parts_spin.value()
            segments_per_part = segments // parts if parts > 0 else 0
            words_per_part = words // parts if parts > 0 else 0
            self.result_info.setText(
                f"≈ {segments_per_part} сегментов и {words_per_part:,} слов на часть"
            )
        else:
            # Для разделения по словам рассчитываем количество частей
            words_per_part = self.words_spin.value()
            if words > 0 and words_per_part > 0:
                estimated_parts = max(2, (words + words_per_part - 1) // words_per_part)
                self.result_info.setText(
                    f"Будет создано примерно {estimated_parts} частей по {words_per_part:,} слов"
                )
            else:
                self.result_info.setText("Количество частей будет определено автоматически")

    def browse_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Выберите директорию для сохранения частей",
            str(self.filepath.parent) if self.filepath else ""
        )

        if dir_path:
            self.output_edit.setText(dir_path)

    def accept_split(self):
        try:
            if not self.filepath:
                QMessageBox.warning(self, "Ошибка", "Не выбран файл")
                return

            self.settings = SdlxliffSplitSettings()

            if self.equal_parts_radio.isChecked():
                self.settings.by_word_count = False
                self.settings.parts_count = self.parts_spin.value()
            else:
                self.settings.by_word_count = True
                self.settings.words_per_part = self.words_spin.value()

            output_path = self.output_edit.text().strip()
            if output_path:
                self.settings.output_dir = Path(output_path)

                if not self.settings.output_dir.exists():
                    reply = QMessageBox.question(
                        self,
                        "Создать директорию?",
                        f"Директория '{output_path}' не существует.\nСоздать её?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )

                    if reply == QMessageBox.Yes:
                        self.settings.output_dir.mkdir(parents=True, exist_ok=True)
                    else:
                        return

            is_valid, error_msg = self.settings.validate()
            if not is_valid:
                QMessageBox.warning(self, "Ошибка", error_msg)
                return

            self.accept()

        except Exception as e:
            logger.exception(f"Error accepting split settings: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения настроек:\n{e}")

    def get_settings(self) -> Optional[SdlxliffSplitSettings]:
        return self.settings

    def get_filepath(self) -> Optional[Path]:
        return self.filepath


class SdlxliffMergeDialog(QDialog):
    files_reordered = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filepaths = []
        self.settings = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Объединение SDLXLIFF файлов")
        self.resize(700, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        header = QLabel("🔗 Настройка объединения SDLXLIFF файлов")
        header.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #333;
                margin: 10px 0;
                padding: 10px;
                background: #f0f8ff;
                border-radius: 8px;
                border: 1px solid #ddd;
            }
        """)
        layout.addWidget(header)

        drop_group = self.create_drop_area_group()
        layout.addWidget(drop_group)

        self.files_group = self.create_files_group()
        layout.addWidget(self.files_group)

        self.settings_group = self.create_settings_group()
        layout.addWidget(self.settings_group)

        self.output_group = self.create_output_group()
        layout.addWidget(self.output_group)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        cancel_btn = QPushButton("❌ Отмена")
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 1px solid #ddd;
                border-radius: 5px;
                background: #f5f5f5;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #e5e5e5;
                border-color: #bbb;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        self.merge_btn = QPushButton("🔗 Объединить")
        self.merge_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                padding: 10px 30px;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #45a049;
            }
        """)
        self.merge_btn.clicked.connect(self.accept_merge)
        self.merge_btn.setEnabled(False)

        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(self.merge_btn)

        layout.addLayout(buttons_layout)

        self.files_group.hide()
        self.settings_group.hide()
        self.output_group.hide()

    def create_drop_area_group(self) -> QGroupBox:
        group = QGroupBox("📄 Выберите SDLXLIFF файлы для объединения")
        layout = QVBoxLayout(group)

        instruction = QLabel("💡 Перетащите несколько SDLXLIFF файлов или частей для объединения")
        instruction.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        layout.addWidget(instruction)

        self.drop_area = SmartDropArea()
        self.drop_area.files_dropped.connect(self.on_files_dropped)
        self.drop_area.files_dragged.connect(self.on_files_dragged)

        layout.addWidget(self.drop_area)

        return group

    def create_files_group(self) -> QGroupBox:
        group = QGroupBox("📄 Файлы для объединения")
        layout = QVBoxLayout(group)

        instruction = QLabel("💡 Перетащите файлы для изменения порядка объединения")
        instruction.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        layout.addWidget(instruction)

        self.files_list = QListWidget()
        self.files_list.setDragDropMode(QListWidget.InternalMove)
        self.files_list.setSelectionMode(QListWidget.SingleSelection)
        self.files_list.setAlternatingRowColors(True)
        self.files_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
            }
        """)

        self.files_list.model().rowsMoved.connect(self.on_files_reordered)

        layout.addWidget(self.files_list)

        self.original_file_label = QLabel("")
        self.original_file_label.setStyleSheet(
            "color: #2e7d32; font-size: 11px; font-weight: bold;"
        )
        self.original_file_label.setVisible(False)
        layout.addWidget(self.original_file_label)

        order_buttons = QHBoxLayout()

        move_up_btn = QPushButton("⬆️ Вверх")
        move_up_btn.clicked.connect(self.move_file_up)
        move_up_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 10px;
                border: 1px solid #ddd;
                border-radius: 3px;
                background: white;
            }
            QPushButton:hover {
                background: #f5f5f5;
            }
        """)
        order_buttons.addWidget(move_up_btn)

        move_down_btn = QPushButton("⬇️ Вниз")
        move_down_btn.clicked.connect(self.move_file_down)
        move_down_btn.setStyleSheet(move_up_btn.styleSheet())
        order_buttons.addWidget(move_down_btn)

        order_buttons.addStretch()

        auto_order_btn = QPushButton("🔢 Автопорядок")
        auto_order_btn.setToolTip("Автоматически упорядочить файлы по номерам в имени")
        auto_order_btn.clicked.connect(self.auto_order_files)
        auto_order_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #4CAF50;
                border-radius: 3px;
                background: #f0fff0;
                color: #2e7d32;
            }
            QPushButton:hover {
                background: #e8f5e8;
            }
        """)
        order_buttons.addWidget(auto_order_btn)

        layout.addLayout(order_buttons)

        return group

    def create_settings_group(self) -> QGroupBox:
        group = QGroupBox("⚙️ Настройки объединения")
        layout = QVBoxLayout(group)

        self.validate_cb = QCheckBox("Проверять совместимость частей перед объединением")
        self.validate_cb.setChecked(False)
        self.validate_cb.setToolTip(
            "Проверяет, что все части имеют одинаковую структуру\n"
            "и могут быть безопасно объединены"
        )
        layout.addWidget(self.validate_cb)

        self.auto_detect_cb = QCheckBox("Автоматически определять части по именам файлов")
        self.auto_detect_cb.setChecked(True)
        self.auto_detect_cb.setToolTip(
            "Ищет файлы вида filename.1of3.sdlxliff и автоматически\n"
            "добавляет недостающие части"
        )
        layout.addWidget(self.auto_detect_cb)

        return group

    def create_output_group(self) -> QGroupBox:
        group = QGroupBox("💾 Выходной файл")
        layout = QVBoxLayout(group)

        path_layout = QHBoxLayout()

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("По умолчанию - filename_merged.sdlxliff")
        self.output_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        path_layout.addWidget(self.output_edit)

        browse_btn = QPushButton("📄 Обзор...")
        browse_btn.clicked.connect(self.browse_output_file)
        browse_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
            }
            QPushButton:hover {
                background: #f5f5f5;
                border-color: #bbb;
            }
        """)
        path_layout.addWidget(browse_btn)

        layout.addLayout(path_layout)

        return group

    def on_files_dragged(self, filepaths: List[str]):
        valid_files = [f for f in filepaths if f.lower().endswith('.sdlxliff')]
        if len(valid_files) >= 2:
            self.drop_area.set_format_info(f"SDLXLIFF ({len(valid_files)} файлов)", True)
        elif len(valid_files) == 1:
            self.drop_area.set_format_info("SDLXLIFF (нужно минимум 2)", False)
        else:
            self.drop_area.set_format_info("Неподдерживаемые файлы", False)

    def on_files_dropped(self, filepaths: List[str]):
        valid_files = [f for f in filepaths if f.lower().endswith('.sdlxliff')]

        if len(valid_files) < 2:
            QMessageBox.warning(self, "Ошибка", "Для объединения нужно минимум 2 SDLXLIFF файла")
            return

        self.filepaths = [Path(f) for f in valid_files]
        self.update_files_list()

        self.files_group.show()
        self.settings_group.show()
        self.output_group.show()

        self.merge_btn.setEnabled(True)

        group_title = self.files_group.title().split(" (")[0]
        self.files_group.setTitle(f"{group_title} ({len(self.filepaths)} файлов)")

    def update_files_list(self):
        self.files_list.clear()
        original_name = None
        for i, filepath in enumerate(self.filepaths):
            display = f"{i + 1}. {filepath.name}"
            if not self._is_split_part_filename(filepath.name) and original_name is None:
                display += " (оригинал)"
                original_name = filepath.name
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, filepath)
            self.files_list.addItem(item)

        if original_name:
            self.original_file_label.setText(f"Оригинальный файл: {original_name}")
            self.original_file_label.setVisible(True)
        else:
            self.original_file_label.setText("Оригинальный файл не найден")
            self.original_file_label.setVisible(True)

    def highlight_original_in_list(self):
        original_name = None
        for i in range(self.files_list.count()):
            item = self.files_list.item(i)
            filepath = item.data(Qt.UserRole)
            display = f"{i + 1}. {filepath.name}"
            if not self._is_split_part_filename(filepath.name) and original_name is None:
                display += " (оригинал)"
                original_name = filepath.name
            item.setText(display)

        if original_name:
            self.original_file_label.setText(f"Оригинальный файл: {original_name}")
            self.original_file_label.setVisible(True)
        else:
            self.original_file_label.setText("Оригинальный файл не найден")
            self.original_file_label.setVisible(True)

    def on_files_reordered(self):
        self.filepaths.clear()
        for i in range(self.files_list.count()):
            item = self.files_list.item(i)
            filepath = item.data(Qt.UserRole)
            self.filepaths.append(filepath)
            item.setText(f"{i + 1}. {filepath.name}")

        self.highlight_original_in_list()
        self.files_reordered.emit(self.filepaths)

    def move_file_up(self):
        current = self.files_list.currentRow()
        if current > 0:
            item = self.files_list.takeItem(current)
            self.files_list.insertItem(current - 1, item)
            self.files_list.setCurrentRow(current - 1)
            self.on_files_reordered()

    def move_file_down(self):
        current = self.files_list.currentRow()
        if current < self.files_list.count() - 1:
            item = self.files_list.takeItem(current)
            self.files_list.insertItem(current + 1, item)
            self.files_list.setCurrentRow(current + 1)
            self.on_files_reordered()

    def auto_order_files(self):
        try:
            from sdlxliff_split_merge.io_utils import sort_split_filenames

            file_paths = [str(fp) for fp in self.filepaths]
            sorted_paths = sort_split_filenames(file_paths)
            self.filepaths = [Path(p) for p in sorted_paths]

            self.update_files_list()
            self.files_reordered.emit(self.filepaths)

            QMessageBox.information(
                self,
                "Автоупорядочивание",
                "Файлы упорядочены по номерам частей"
            )

        except Exception as e:
            logger.error(f"Error auto-ordering files: {e}")
            QMessageBox.warning(
                self,
                "Ошибка",
                f"Не удалось автоматически упорядочить файлы:\n{e}"
            )

    def browse_output_file(self):
        default_name = "merged.sdlxliff"
        if self.filepaths:
            default_name = f"{self.filepaths[0].stem}_merged.sdlxliff"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Выберите файл для сохранения",
            str(self.filepaths[0].parent / default_name) if self.filepaths else default_name,
            "SDLXLIFF Files (*.sdlxliff)"
        )

        if file_path:
            self.output_edit.setText(file_path)

    def accept_merge(self):
        try:
            if len(self.filepaths) < 2:
                QMessageBox.warning(self, "Ошибка", "Для объединения нужно минимум 2 файла")
                return

            self.settings = SdlxliffMergeSettings()
            self.settings.validate_parts = self.validate_cb.isChecked()
            self.settings.auto_detect_parts = self.auto_detect_cb.isChecked()

            output_path = self.output_edit.text().strip()
            if output_path:
                self.settings.output_path = Path(output_path)

            is_valid, error_msg = self.settings.validate()
            if not is_valid:
                QMessageBox.warning(self, "Ошибка", error_msg)
                return

            self.accept()

        except Exception as e:
            logger.exception(f"Error accepting merge settings: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения настроек:\n{e}")

    def get_settings(self) -> Optional[SdlxliffMergeSettings]:
        return self.settings

    def get_ordered_files(self) -> List[Path]:
        return self.filepaths.copy()

    @staticmethod
    def _is_split_part_filename(name: str) -> bool:
        return bool(re.search(r"\.\d+of\d+\.sdlxliff$", name, re.IGNORECASE))