# gui/widgets/drop_area.py - БЕЗ МИНИМАЛЬНЫХ РАЗМЕРОВ

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPaintEvent, QPainter, QBrush, QPen
from pathlib import Path
from typing import List


class SmartDropArea(QWidget):
    """Область для перетаскивания файлов БЕЗ минимальных размеров"""

    files_dropped = Signal(list)  # List[str] - пути к файлам
    files_dragged = Signal(list)  # Сигнал для проверки файлов при перетаскивании

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setup_ui()
        self.setup_styles()

        # Состояния
        self.is_dragging = False
        self.detected_format = ""

    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # Уменьшены отступы
        layout.setSpacing(5)  # Уменьшены промежутки

        # Иконка
        self.icon_label = QLabel("📁")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("""
            QLabel {
                font-size: 36px;
                color: #666;
                background: transparent;
                margin: 0px;
            }
        """)
        layout.addWidget(self.icon_label)

        # Основной текст
        self.main_label = QLabel("Перетащите файлы сюда")
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #333;
                background: transparent;
                margin: 0px;
            }
        """)
        layout.addWidget(self.main_label)

        # Подсказка
        self.hint_label = QLabel("или нажмите для выбора")
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #666;
                background: transparent;
                margin: 0px;
            }
        """)
        layout.addWidget(self.hint_label)

        # Информация о формате
        self.format_label = QLabel("")
        self.format_label.setAlignment(Qt.AlignCenter)
        self.format_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #4CAF50;
                font-weight: bold;
                background: transparent;
                margin: 0px;
                min-height: 16px;
            }
        """)
        layout.addWidget(self.format_label)

        # Список поддерживаемых форматов
        formats_text = "SDLTM, Excel, TMX, XML/TB"
        self.formats_label = QLabel(formats_text)
        self.formats_label.setAlignment(Qt.AlignCenter)
        self.formats_label.setStyleSheet("""
            QLabel {
                font-size: 9px;
                color: #999;
                background: transparent;
                margin: 0px;
            }
        """)
        layout.addWidget(self.formats_label)

        # Добавляем растяжку, чтобы содержимое центрировалось
        layout.addStretch()

    def setup_styles(self):
        """Настройка стилей"""
        # Убираем минимальную высоту - виджет может быть любого размера
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.update_style_normal()

    def update_style_normal(self):
        """Обычный стиль"""
        self.setStyleSheet("""
            SmartDropArea {
                border: 2px dashed #ccc;
                border-radius: 8px;
                background-color: #fafafa;
                min-height: 100px;
            }
        """)

    def update_style_hover(self):
        """Стиль при наведении"""
        self.setStyleSheet("""
            SmartDropArea {
                border: 2px dashed #4CAF50;
                border-radius: 8px;
                background-color: #f0f8f0;
                min-height: 100px;
            }
        """)
        self.icon_label.setStyleSheet("""
            QLabel {
                font-size: 40px;
                color: #4CAF50;
                background: transparent;
                margin: 0px;
            }
        """)

    def update_style_error(self):
        """Стиль при ошибке"""
        self.setStyleSheet("""
            SmartDropArea {
                border: 2px dashed #f44336;
                border-radius: 8px;
                background-color: #fff0f0;
                min-height: 100px;
            }
        """)
        self.icon_label.setStyleSheet("""
            QLabel {
                font-size: 40px;
                color: #f44336;
                background: transparent;
                margin: 0px;
            }
        """)

    def set_format_info(self, format_name: str, is_valid: bool):
        """Устанавливает информацию о формате извне"""
        if is_valid:
            self.format_label.setText(f"Обнаружен: {format_name}")
            self.update_style_hover()
        else:
            self.format_label.setText("❌ Неподдерживаемые файлы")
            self.update_style_error()

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Обработчик входа перетаскивания"""
        if event.mimeData().hasUrls():
            filepaths = [url.toLocalFile() for url in event.mimeData().urls()]
            self.files_dragged.emit(filepaths)
            self.is_dragging = True
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Обработчик движения при перетаскивании"""
        if self.is_dragging:
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        """Обработчик выхода из области перетаскивания"""
        self.is_dragging = False
        self.detected_format = ""
        self.format_label.setText("")
        self.update_style_normal()
        self.icon_label.setStyleSheet("""
            QLabel {
                font-size: 36px;
                color: #666;
                background: transparent;
                margin: 0px;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        """Обработчик сброса файлов"""
        if event.mimeData().hasUrls():
            filepaths = [url.toLocalFile() for url in event.mimeData().urls()]
            self.files_dropped.emit(filepaths)
            self.format_label.setText(f"✅ Обрабатываем {len(filepaths)} файлов...")

            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, self.reset_style)

        self.is_dragging = False
        event.acceptProposedAction()

    def mousePressEvent(self, event):
        """Обработчик нажатия мыши для открытия диалога"""
        if event.button() == Qt.LeftButton:
            self.open_file_dialog()

    def open_file_dialog(self):
        """Открывает диалог выбора файлов"""
        from PySide6.QtWidgets import QFileDialog

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для конвертации",
            "",
            "Все поддерживаемые (*.sdltm *.xlsx *.xls *.tmx *.xml *.mtf);;"
            "SDLTM (*.sdltm);;"
            "Excel (*.xlsx *.xls);;"
            "TMX (*.tmx);;"
            "XML/Termbase (*.xml *.mtf)"
        )

        if files:
            self.files_dropped.emit(files)
            self.format_label.setText(f"✅ Выбрано файлов: {len(files)}")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, self.reset_style)

    def reset_style(self):
        """Сбрасывает стиль к обычному"""
        self.dragLeaveEvent(None)

    def sizeHint(self):
        """Предпочтительный размер"""
        from PySide6.QtCore import QSize
        return QSize(200, 120)  # Уменьшен предпочтительный размер

    def minimumSizeHint(self):
        """Минимальный размер"""
        from PySide6.QtCore import QSize
        return QSize(100, 80)  # Очень маленький минимальный размер


# Добавляем импорт для QSizePolicy
from PySide6.QtWidgets import QSizePolicy