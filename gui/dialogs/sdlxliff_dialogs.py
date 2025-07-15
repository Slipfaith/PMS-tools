# gui/dialogs/sdlxliff_dialogs.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, 
    QSpinBox, QRadioButton, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QMessageBox, QCheckBox,
    QLineEdit, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from pathlib import Path
from typing import List, Optional
import logging

from core.converters.sdlxliff_converter import SdlxliffSplitSettings, SdlxliffMergeSettings

logger = logging.getLogger(__name__)


class SdlxliffSplitDialog(QDialog):
    """Диалог настройки разделения SDLXLIFF файла"""
    
    def __init__(self, filepath: Path, file_info: dict, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.file_info = file_info
        self.settings = None
        self.setup_ui()
        
    def setup_ui(self):
        """Настройка интерфейса"""
        self.setWindowTitle(f"Разделение SDLXLIFF: {self.filepath.name}")
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Заголовок
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
        
        # Информация о файле
        info_group = self.create_file_info_group()
        layout.addWidget(info_group)
        
        # Настройки разделения
        split_group = self.create_split_settings_group()
        layout.addWidget(split_group)
        
        # Директория вывода
        output_group = self.create_output_group()
        layout.addWidget(output_group)
        
        # Кнопки
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
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(self.split_btn)
        
        layout.addLayout(buttons_layout)
        
    def create_file_info_group(self) -> QGroupBox:
        """Создает группу с информацией о файле"""
        group = QGroupBox("📄 Информация о файле")
        layout = QFormLayout(group)
        
        # Имя файла
        name_label = QLabel(self.filepath.name)
        name_label.setStyleSheet("font-weight: bold;")
        layout.addRow("Имя файла:", name_label)
        
        # Размер
        size_mb = self.file_info.get('file_size_mb', 0)
        size_label = QLabel(f"{size_mb:.1f} MB")
        layout.addRow("Размер:", size_label)
        
        # Количество сегментов
        segments = self.file_info.get('segments_count', 0)
        segments_label = QLabel(f"{segments:,}")
        layout.addRow("Сегментов:", segments_label)
        
        # Оценка частей по словам
        if self.file_info.get('valid', False):
            est_1000 = self.file_info.get('estimated_parts_1000_words', 0)
            est_2000 = self.file_info.get('estimated_parts_2000_words', 0)
            est_5000 = self.file_info.get('estimated_parts_5000_words', 0)
            
            est_label = QLabel(f"1000 слов: {est_1000} частей | "
                             f"2000 слов: {est_2000} частей | "
                             f"5000 слов: {est_5000} частей")
            est_label.setStyleSheet("color: #666; font-size: 11px;")
            layout.addRow("Оценка:", est_label)
            
        return group
        
    def create_split_settings_group(self) -> QGroupBox:
        """Создает группу настроек разделения"""
        group = QGroupBox("⚙️ Метод разделения")
        layout = QVBoxLayout(group)
        
        # Разделение на равные части
        self.equal_parts_radio = QRadioButton("На равные части")
        self.equal_parts_radio.setChecked(True)
        self.equal_parts_radio.toggled.connect(self.on_method_changed)
        layout.addWidget(self.equal_parts_radio)
        
        # Количество частей
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
        
        # Разделение по количеству слов
        self.by_words_radio = QRadioButton("По количеству слов")
        self.by_words_radio.toggled.connect(self.on_method_changed)
        layout.addWidget(self.by_words_radio)
        
        # Количество слов на часть
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
        
        # Информация о результате
        self.result_info = QLabel("")
        self.result_info.setStyleSheet("color: #666; font-style: italic; margin-top: 10px;")
        layout.addWidget(self.result_info)
        
        # Обновляем информацию
        self.update_result_info()
        self.parts_spin.valueChanged.connect(self.update_result_info)
        self.words_spin.valueChanged.connect(self.update_result_info)
        
        return group
        
    def create_output_group(self) -> QGroupBox:
        """Создает группу настроек вывода"""
        group = QGroupBox("📁 Директория для сохранения")
        layout = QVBoxLayout(group)
        
        # Путь вывода
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
        
        # Информация о именах файлов
        info_label = QLabel("💡 Файлы будут названы: filename.1of3.sdlxliff, filename.2of3.sdlxliff, ...")
        info_label.setStyleSheet("color: #666; font-size: 11px; margin-top: 5px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        return group
        
    def on_method_changed(self):
        """Обработчик изменения метода разделения"""
        by_words = self.by_words_radio.isChecked()
        self.parts_spin.setEnabled(not by_words)
        self.words_spin.setEnabled(by_words)
        self.update_result_info()
        
    def update_result_info(self):
        """Обновляет информацию о результате"""
        segments = self.file_info.get('segments_count', 0)
        
        if self.equal_parts_radio.isChecked():
            parts = self.parts_spin.value()
            segments_per_part = segments // parts if parts > 0 else 0
            self.result_info.setText(f"≈ {segments_per_part} сегментов на часть")
        else:
            # Для разделения по словам показываем оценку
            self.result_info.setText("Количество частей будет определено автоматически")
            
    def browse_output_dir(self):
        """Открывает диалог выбора директории"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Выберите директорию для сохранения частей",
            str(self.filepath.parent)
        )
        
        if dir_path:
            self.output_edit.setText(dir_path)
            
    def accept_split(self):
        """Принимает настройки и закрывает диалог"""
        try:
            # Создаем настройки
            self.settings = SdlxliffSplitSettings()
            
            if self.equal_parts_radio.isChecked():
                self.settings.by_word_count = False
                self.settings.parts_count = self.parts_spin.value()
            else:
                self.settings.by_word_count = True
                self.settings.words_per_part = self.words_spin.value()
                
            # Директория вывода
            output_path = self.output_edit.text().strip()
            if output_path:
                self.settings.output_dir = Path(output_path)
                
                # Проверяем существование директории
                if not self.settings.output_dir.exists():
                    reply = QMessageBox.question(
                        self,
                        "Создать директорию?",
                        f"Директория '{output_path}' не существует.\n"
                        f"Создать её?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    
                    if reply == QMessageBox.Yes:
                        self.settings.output_dir.mkdir(parents=True, exist_ok=True)
                    else:
                        return
                        
            # Валидация настроек
            is_valid, error_msg = self.settings.validate()
            if not is_valid:
                QMessageBox.warning(self, "Ошибка", error_msg)
                return
                
            self.accept()
            
        except Exception as e:
            logger.exception(f"Error accepting split settings: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения настроек:\n{e}")
            
    def get_settings(self) -> Optional[SdlxliffSplitSettings]:
        """Возвращает настройки разделения"""
        return self.settings


class SdlxliffMergeDialog(QDialog):
    """Диалог настройки объединения SDLXLIFF файлов"""
    
    files_reordered = Signal(list)  # List[Path]
    
    def __init__(self, filepaths: List[Path], parent=None):
        super().__init__(parent)
        self.filepaths = filepaths.copy()
        self.settings = None
        self.setup_ui()
        
    def setup_ui(self):
        """Настройка интерфейса"""
        self.setWindowTitle(f"Объединение SDLXLIFF файлов ({len(self.filepaths)} файлов)")
        self.resize(700, 600)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Заголовок
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
        
        # Список файлов
        files_group = self.create_files_group()
        layout.addWidget(files_group)
        
        # Настройки объединения
        settings_group = self.create_settings_group()
        layout.addWidget(settings_group)
        
        # Выходной файл
        output_group = self.create_output_group()
        layout.addWidget(output_group)
        
        # Кнопки
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
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(self.merge_btn)
        
        layout.addLayout(buttons_layout)
        
    def create_files_group(self) -> QGroupBox:
        """Создает группу со списком файлов"""
        group = QGroupBox(f"📄 Файлы для объединения ({len(self.filepaths)})")
        layout = QVBoxLayout(group)
        
        # Инструкция
        instruction = QLabel("💡 Перетащите файлы для изменения порядка объединения")
        instruction.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        layout.addWidget(instruction)
        
        # Список файлов
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
        
        # Добавляем файлы
        for i, filepath in enumerate(self.filepaths):
            item = QListWidgetItem(f"{i+1}. {filepath.name}")
            item.setData(Qt.UserRole, filepath)
            self.files_list.addItem(item)
            
        self.files_list.model().rowsMoved.connect(self.on_files_reordered)
        
        layout.addWidget(self.files_list)
        
        # Кнопки управления порядком
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
        
        # Автоопределение порядка
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
        """Создает группу настроек объединения"""
        group = QGroupBox("⚙️ Настройки объединения")
        layout = QVBoxLayout(group)
        
        # Валидация частей
        self.validate_cb = QCheckBox("Проверять совместимость частей перед объединением")
        self.validate_cb.setChecked(True)
        self.validate_cb.setToolTip(
            "Проверяет, что все части имеют одинаковую структуру\n"
            "и могут быть безопасно объединены"
        )
        layout.addWidget(self.validate_cb)
        
        # Автоопределение частей
        self.auto_detect_cb = QCheckBox("Автоматически определять части по именам файлов")
        self.auto_detect_cb.setChecked(True)
        self.auto_detect_cb.setToolTip(
            "Ищет файлы вида filename.1of3.sdlxliff и автоматически\n"
            "добавляет недостающие части"
        )
        layout.addWidget(self.auto_detect_cb)
        
        return group
        
    def create_output_group(self) -> QGroupBox:
        """Создает группу настроек выходного файла"""
        group = QGroupBox("💾 Выходной файл")
        layout = QVBoxLayout(group)
        
        # Путь вывода
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
        
    def on_files_reordered(self):
        """Обработчик изменения порядка файлов"""
        # Обновляем список filepaths
        self.filepaths.clear()
        for i in range(self.files_list.count()):
            item = self.files_list.item(i)
            filepath = item.data(Qt.UserRole)
            self.filepaths.append(filepath)
            # Обновляем номер в тексте
            item.setText(f"{i+1}. {filepath.name}")
            
        self.files_reordered.emit(self.filepaths)
        
    def move_file_up(self):
        """Перемещает выбранный файл вверх"""
        current = self.files_list.currentRow()
        if current > 0:
            item = self.files_list.takeItem(current)
            self.files_list.insertItem(current - 1, item)
            self.files_list.setCurrentRow(current - 1)
            self.on_files_reordered()
            
    def move_file_down(self):
        """Перемещает выбранный файл вниз"""
        current = self.files_list.currentRow()
        if current < self.files_list.count() - 1:
            item = self.files_list.takeItem(current)
            self.files_list.insertItem(current + 1, item)
            self.files_list.setCurrentRow(current + 1)
            self.on_files_reordered()
            
    def auto_order_files(self):
        """Автоматически упорядочивает файлы"""
        try:
            from sdlxliff_split_merge.io_utils import sort_split_filenames
            
            # Получаем пути как строки
            file_paths = [str(fp) for fp in self.filepaths]
            
            # Сортируем
            sorted_paths = sort_split_filenames(file_paths)
            
            # Обновляем порядок
            self.filepaths = [Path(p) for p in sorted_paths]
            
            # Обновляем список
            self.files_list.clear()
            for i, filepath in enumerate(self.filepaths):
                item = QListWidgetItem(f"{i+1}. {filepath.name}")
                item.setData(Qt.UserRole, filepath)
                self.files_list.addItem(item)
                
            self.files_reordered.emit(self.filepaths)
            
            QMessageBox.information(
                self,
                "Автоупорядочивание",
                f"Файлы упорядочены по номерам частей"
            )
            
        except Exception as e:
            logger.error(f"Error auto-ordering files: {e}")
            QMessageBox.warning(
                self,
                "Ошибка",
                f"Не удалось автоматически упорядочить файлы:\n{e}"
            )
            
    def browse_output_file(self):
        """Открывает диалог выбора выходного файла"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Выберите файл для сохранения",
            str(self.filepaths[0].parent / f"{self.filepaths[0].stem}_merged.sdlxliff"),
            "SDLXLIFF Files (*.sdlxliff)"
        )
        
        if file_path:
            self.output_edit.setText(file_path)
            
    def accept_merge(self):
        """Принимает настройки и закрывает диалог"""
        try:
            # Создаем настройки
            self.settings = SdlxliffMergeSettings()
            self.settings.validate_parts = self.validate_cb.isChecked()
            self.settings.auto_detect_parts = self.auto_detect_cb.isChecked()
            
            # Выходной файл
            output_path = self.output_edit.text().strip()
            if output_path:
                self.settings.output_path = Path(output_path)
                
            # Валидация настроек
            is_valid, error_msg = self.settings.validate()
            if not is_valid:
                QMessageBox.warning(self, "Ошибка", error_msg)
                return
                
            # Проверяем, что есть файлы
            if len(self.filepaths) < 2:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Для объединения нужно минимум 2 файла"
                )
                return
                
            self.accept()
            
        except Exception as e:
            logger.exception(f"Error accepting merge settings: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения настроек:\n{e}")
            
    def get_settings(self) -> Optional[SdlxliffMergeSettings]:
        """Возвращает настройки объединения"""
        return self.settings
        
    def get_ordered_files(self) -> List[Path]:
        """Возвращает упорядоченный список файлов"""
        return self.filepaths.copy()