# gui/widgets/file_list.py - БЕЗ МИНИМАЛЬНЫХ РАЗМЕРОВ

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
    """Виджет для отображения файла"""

    remove_requested = Signal(Path)

    def __init__(self, file_info: Dict):
        super().__init__()
        self.filepath = file_info['path']
        self.file_info = file_info
        self.setup_ui()

    def setup_ui(self):
        """Настройка интерфейса"""
        # Основной макет с уменьшенными отступами
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 6, 8, 6)  # Уменьшены отступы
        main_layout.setSpacing(4)  # Уменьшены промежутки

        # Верхняя строка - имя файла и кнопка удаления
        top_layout = QHBoxLayout()
        top_layout.setSpacing(4)

        # Иконка формата
        self.format_icon = QLabel(self.file_info['format_icon'])
        self.format_icon.setStyleSheet("font-size: 16px; margin-right: 2px;")
        self.format_icon.setFixedSize(20, 20)
        self.format_icon.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(self.format_icon)

        # Имя файла
        self.name_label = QLabel(self.file_info['name'])
        self.name_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 12px;
                color: #333;
                margin: 0px;
                padding: 1px;
            }
        """)
        self.name_label.setWordWrap(True)
        self.name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_layout.addWidget(self.name_label)

        top_layout.addStretch()

        # Кнопка удаления
        self.remove_btn = QPushButton("❌")
        self.remove_btn.setFixedSize(24, 24)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                font-size: 12px;
                border-radius: 12px;
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
        size_str = f"{self.file_info['size_mb']:.1f} MB" if self.file_info['size_mb'] > 0 else "< 1 MB"
        info_parts = [self.file_info['format'], size_str]

        if self.file_info['extra_info']:
            info_parts.append(self.file_info['extra_info'])

        info_text = " • ".join(info_parts)

        self.info_label = QLabel(info_text)
        self.info_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #666;
                margin: 0px;
                padding: 1px;
            }
        """)
        self.info_label.setWordWrap(True)
        main_layout.addWidget(self.info_label)

        # Прогресс-бар (скрыт по умолчанию)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(6)
        self.progress_bar.setMinimumHeight(6)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 3px;
                background: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #4CAF50;
                border-radius: 2px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # Статус конвертации
        self.status_label = QLabel()
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 9px;
                color: #999;
                margin: 0px;
                padding: 1px;
            }
        """)
        self.status_label.setVisible(False)
        main_layout.addWidget(self.status_label)

        # Рамка для всего элемента
        self.setStyleSheet("""
            FileListItem {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background: white;
                margin: 1px;
            }
            FileListItem:hover {
                border-color: #4CAF50;
                background: #f9fff9;
            }
        """)

        # Убираем минимальную высоту
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

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
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 9px; font-weight: bold;")
        else:
            self.status_label.setText(f"❌ {message}" if message else "❌ Ошибка")
            self.status_label.setStyleSheet("color: #f44336; font-size: 9px; font-weight: bold;")

        self.status_label.setVisible(True)

    def reset_status(self):
        """Сбрасывает статус конвертации"""
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)

    def sizeHint(self):
        """Предпочтительный размер"""
        return QSize(300, 60)  # Уменьшен размер

    def minimumSizeHint(self):
        """Минимальный размер"""
        return QSize(150, 50)  # Минимальный размер


class FileListWidget(QWidget):
    """Виджет для отображения списка файлов"""

    files_changed = Signal(int)
    file_remove_requested = Signal(Path)

    def __init__(self):
        super().__init__()
        self.file_items: Dict[Path, FileListItem] = {}
        self.setup_ui()

    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Заголовок
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)

        self.title_label = QLabel("📁 Файлы для конвертации")
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: bold;
                color: #333;
                padding: 4px;
                margin: 0px;
            }
        """)
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Счетчик файлов
        self.count_label = QLabel("0 файлов")
        self.count_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #666;
                padding: 4px;
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
                border-radius: 6px;
                background: #fafafa;
                padding: 2px;
            }
            QListWidget::item {
                border: none;
                padding: 0px;
                margin: 1px;
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

        # Отключаем стандартное выделение
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        self.list_widget.setFocusPolicy(Qt.NoFocus)

        # Убираем минимальный размер
        self.list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(self.list_widget)

        # Кнопки управления
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(4)

        self.clear_all_btn = QPushButton("Очистить все")
        self.clear_all_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                border: 1px solid #ddd;
                border-radius: 3px;
                background: white;
                color: #333;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #f5f5f5;
                border-color: #bbb;
            }
        """)
        buttons_layout.addWidget(self.clear_all_btn)

        buttons_layout.addStretch()

        layout.addLayout(buttons_layout)

    def update_files(self, files_info: List[Dict]):
        """Обновляет список файлов"""
        # Получаем новые пути
        new_paths = {info['path'] for info in files_info}
        current_paths = set(self.file_items.keys())

        # Удаляем файлы, которых больше нет
        for path in current_paths - new_paths:
            self.remove_file(path)

        # Добавляем новые файлы
        for file_info in files_info:
            path = file_info['path']
            if path not in current_paths:
                self.add_file(file_info)

        self.update_count()

    def add_file(self, file_info: Dict):
        """Добавляет файл"""
        filepath = file_info['path']

        if filepath in self.file_items:
            return

        # Создаем виджет для файла
        file_item = FileListItem(file_info)
        file_item.remove_requested.connect(self.file_remove_requested.emit)

        # Создаем элемент списка
        list_item = QListWidgetItem()

        # Устанавливаем размер
        item_size = file_item.sizeHint()
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

    def sizeHint(self):
        """Предпочтительный размер"""
        return QSize(400, 300)

    def minimumSizeHint(self):
        """Минимальный размер"""
        return QSize(200, 100)