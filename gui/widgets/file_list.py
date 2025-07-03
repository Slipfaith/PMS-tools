# gui/widgets/file_list.py - ИСПРАВЛЕННАЯ ВЕРСИЯ С ПРАВИЛЬНЫМ МАКЕТОМ

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QProgressBar, QFrame, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QFont, QIcon
from pathlib import Path
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class FileListItem(QWidget):
    """ИСПРАВЛЕНО: Виджет для отображения файла с правильным макетом"""

    remove_requested = Signal(Path)

    def __init__(self, filepath: Path):
        super().__init__()
        self.filepath = filepath
        self.setup_ui()
        self.analyze_file()

    def setup_ui(self):
        """ИСПРАВЛЕНО: Настройка интерфейса с правильными отступами"""
        # Основной макет с увеличенными отступами
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        # Верхняя строка - имя файла и кнопка удаления
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        # Иконка формата
        self.format_icon = QLabel(self.get_format_icon())
        self.format_icon.setStyleSheet("font-size: 18px; margin-right: 4px;")
        self.format_icon.setFixedSize(24, 24)
        self.format_icon.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(self.format_icon)

        # Имя файла
        self.name_label = QLabel(self.filepath.name)
        self.name_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 13px;
                color: #333;
                margin: 0px;
                padding: 2px;
            }
        """)
        self.name_label.setWordWrap(True)
        self.name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_layout.addWidget(self.name_label)

        top_layout.addStretch()

        # Кнопка удаления
        self.remove_btn = QPushButton("❌")
        self.remove_btn.setFixedSize(28, 28)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                font-size: 14px;
                border-radius: 14px;
                padding: 0px;
            }
            QPushButton:hover {
                background: #ffebee;
                color: #f44336;
            }
            QPushButton:pressed {
                background: #ffcdd2;
            }
        """)
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.filepath))
        top_layout.addWidget(self.remove_btn)

        main_layout.addLayout(top_layout)

        # Информация о файле
        self.info_label = QLabel()
        self.info_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #666;
                margin: 0px;
                padding: 2px;
            }
        """)
        self.info_label.setWordWrap(True)
        main_layout.addWidget(self.info_label)

        # Прогресс-бар (скрыт по умолчанию)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(8)
        self.progress_bar.setMinimumHeight(8)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #4CAF50;
                border-radius: 3px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # Статус конвертации
        self.status_label = QLabel()
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #999;
                margin: 0px;
                padding: 2px;
            }
        """)
        self.status_label.setVisible(False)
        main_layout.addWidget(self.status_label)

        # Рамка для всего элемента
        self.setStyleSheet("""
            FileListItem {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background: white;
                margin: 2px;
            }
            FileListItem:hover {
                border-color: #4CAF50;
                background: #f9fff9;
            }
        """)

        # Устанавливаем минимальную высоту
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def get_format_icon(self) -> str:
        """Возвращает иконку для формата файла"""
        suffix = self.filepath.suffix.lower()
        icons = {
            '.sdltm': '🗄️',
            '.xlsx': '📊',
            '.xls': '📊',
            '.tmx': '🔄',
            '.xml': '📋',
            '.mtf': '📖'
        }
        return icons.get(suffix, '📄')

    def analyze_file(self):
        """Анализирует файл и показывает информацию"""
        try:
            # Размер файла
            size_bytes = self.filepath.stat().st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

            # Формат
            format_name = self.get_format_name()

            # Дополнительная информация
            extra_info = self.get_extra_info()

            info_parts = [format_name, size_str]
            if extra_info:
                info_parts.append(extra_info)

            info_text = " • ".join(info_parts)
            self.info_label.setText(info_text)

        except Exception as e:
            logger.warning(f"Error analyzing file {self.filepath}: {e}")
            self.info_label.setText(f"Ошибка анализа: {e}")
            self.info_label.setStyleSheet("color: #f44336; font-size: 11px;")

    def get_format_name(self) -> str:
        """Возвращает название формата"""
        suffix = self.filepath.suffix.lower()
        formats = {
            '.sdltm': 'SDL Trados Memory',
            '.xlsx': 'Excel Workbook',
            '.xls': 'Excel Workbook',
            '.tmx': 'TMX Memory',
            '.xml': 'XML/Termbase',
            '.mtf': 'MultiTerm Format'
        }
        return formats.get(suffix, 'Unknown Format')

    def get_extra_info(self) -> str:
        """Получает дополнительную информацию о файле"""
        suffix = self.filepath.suffix.lower()

        if suffix == '.sdltm':
            return self.get_sdltm_info()
        elif suffix in ['.xlsx', '.xls']:
            return self.get_excel_info()

        return ""

    def get_sdltm_info(self) -> str:
        """Получает информацию об SDLTM файле"""
        try:
            import sqlite3
            with sqlite3.connect(str(self.filepath)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM translation_units")
                count = cursor.fetchone()[0]
                return f"{count:,} сегментов"
        except Exception:
            return "Недоступно"

    def get_excel_info(self) -> str:
        """Получает информацию об Excel файле"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(self.filepath), read_only=True)
            sheets = len(wb.sheetnames)
            wb.close()
            return f"{sheets} лист(ов)"
        except Exception:
            return "Недоступно"

    def set_conversion_progress(self, progress: int, message: str = ""):
        """Устанавливает прогресс конвертации"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(progress)

        if message:
            self.status_label.setText(message)
            self.status_label.setVisible(True)

    def set_conversion_completed(self, success: bool, message: str = ""):
        """Отмечает завершение конвертации"""
        self.progress_bar.setVisible(False)

        if success:
            self.status_label.setText(f"✅ {message}" if message else "✅ Завершено")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 10px; font-weight: bold;")
        else:
            self.status_label.setText(f"❌ {message}" if message else "❌ Ошибка")
            self.status_label.setStyleSheet("color: #f44336; font-size: 10px; font-weight: bold;")

        self.status_label.setVisible(True)

    def reset_status(self):
        """Сбрасывает статус конвертации"""
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)


class FileListWidget(QWidget):
    """ИСПРАВЛЕНО: Виджет для отображения списка файлов с правильным макетом"""

    files_changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.file_items: Dict[Path, FileListItem] = {}
        self.setup_ui()

    def setup_ui(self):
        """ИСПРАВЛЕНО: Настройка интерфейса с правильными отступами"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Заголовок
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.title_label = QLabel("📁 Файлы для конвертации")
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #333;
                padding: 8px;
                margin: 0px;
            }
        """)
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Счетчик файлов
        self.count_label = QLabel("0 файлов")
        self.count_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #666;
                padding: 8px;
                margin: 0px;
            }
        """)
        header_layout.addWidget(self.count_label)

        layout.addLayout(header_layout)

        # Список файлов
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background: #fafafa;
                padding: 4px;
            }
            QListWidget::item {
                border: none;
                padding: 0px;
                margin: 2px;
                background: transparent;
            }
            QListWidget::item:selected {
                background: transparent;
                border: none;
            }
            QListWidget::item:hover {
                background: transparent;
            }
        """)

        # ИСПРАВЛЕНО: Отключаем стандартное выделение
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        self.list_widget.setFocusPolicy(Qt.NoFocus)

        layout.addWidget(self.list_widget)

        # Кнопки управления
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)

        self.select_all_btn = QPushButton("Выбрать все")
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
                color: #333;
            }
            QPushButton:hover {
                background: #f5f5f5;
                border-color: #bbb;
            }
        """)
        self.select_all_btn.clicked.connect(self.select_all_files)
        buttons_layout.addWidget(self.select_all_btn)

        self.clear_all_btn = QPushButton("Очистить все")
        self.clear_all_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
                color: #333;
            }
            QPushButton:hover {
                background: #f5f5f5;
                border-color: #bbb;
            }
        """)
        self.clear_all_btn.clicked.connect(self.clear_all_files)
        buttons_layout.addWidget(self.clear_all_btn)

        buttons_layout.addStretch()

        layout.addLayout(buttons_layout)

    def update_files(self, filepaths: List[Path]):
        """Обновляет список файлов"""
        # Удаляем файлы, которых больше нет
        current_paths = set(self.file_items.keys())
        new_paths = set(filepaths)

        for path in current_paths - new_paths:
            self.remove_file(path)

        # Добавляем новые файлы
        for path in new_paths - current_paths:
            self.add_file(path)

        self.update_count()

    def add_file(self, filepath: Path):
        """Добавляет файл в список"""
        if filepath in self.file_items:
            return

        # Создаем виджет для файла
        file_item = FileListItem(filepath)
        file_item.remove_requested.connect(self.remove_file)

        # Создаем элемент списка
        list_item = QListWidgetItem()

        # ИСПРАВЛЕНО: Устанавливаем правильный размер
        item_size = file_item.sizeHint()
        item_size.setHeight(max(85, item_size.height()))  # Минимум 85px высоты
        list_item.setSizeHint(item_size)

        # Добавляем в список
        self.list_widget.addItem(list_item)
        self.list_widget.setItemWidget(list_item, file_item)

        # Сохраняем ссылки
        self.file_items[filepath] = file_item

        self.update_count()

    def remove_file(self, filepath: Path):
        """Удаляет файл из списка"""
        if filepath not in self.file_items:
            return

        # Находим и удаляем элемент из списка
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if isinstance(widget, FileListItem) and widget.filepath == filepath:
                self.list_widget.takeItem(i)
                break

        # Удаляем из словаря
        del self.file_items[filepath]

        self.update_count()

    def clear(self):
        """Очищает весь список"""
        self.list_widget.clear()
        self.file_items.clear()
        self.update_count()

    def clear_all_files(self):
        """Очищает все файлы"""
        self.clear()

    def select_all_files(self):
        """Выбирает все файлы (заглушка для будущего функционала)"""
        pass

    def update_count(self):
        """Обновляет счетчик файлов"""
        count = len(self.file_items)
        if count == 0:
            self.count_label.setText("Нет файлов")
        elif count == 1:
            self.count_label.setText("1 файл")
        elif count < 5:
            self.count_label.setText(f"{count} файла")
        else:
            self.count_label.setText(f"{count} файлов")

        self.files_changed.emit(count)

    def get_file_item(self, filepath: Path) -> FileListItem:
        """Возвращает виджет файла"""
        return self.file_items.get(filepath)

    def set_file_progress(self, filepath: Path, progress: int, message: str = ""):
        """Устанавливает прогресс для файла"""
        file_item = self.get_file_item(filepath)
        if file_item:
            file_item.set_conversion_progress(progress, message)

    def set_file_completed(self, filepath: Path, success: bool, message: str = ""):
        """Отмечает файл как завершенный"""
        file_item = self.get_file_item(filepath)
        if file_item:
            file_item.set_conversion_completed(success, message)

    def reset_all_status(self):
        """Сбрасывает статус всех файлов"""
        for file_item in self.file_items.values():
            file_item.reset_status()