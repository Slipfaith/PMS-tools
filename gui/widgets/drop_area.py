# gui/widgets/drop_area.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPaintEvent, QPainter, QBrush, QPen
from pathlib import Path
from typing import List


class SmartDropArea(QWidget):
    """Умная область для перетаскивания файлов с автоопределением формата"""

    files_dropped = Signal(list)  # List[str] - пути к файлам

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setup_ui()
        self.setup_styles()

        # Состояния
        self.is_dragging = False
        self.detected_format = ""

        # Поддерживаемые форматы
        self.supported_formats = {
            '.sdltm': 'SDL Trados Memory',
            '.xlsx': 'Excel Workbook',
            '.xls': 'Excel Workbook',
            '.tmx': 'Translation Memory eXchange',
            '.xml': 'XML/Termbase',
            '.mtf': 'MultiTerm Format'
        }

    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Иконка
        self.icon_label = QLabel("📁")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("""
            QLabel {
                font-size: 48px;
                color: #666;
                background: transparent;
            }
        """)
        layout.addWidget(self.icon_label)

        # Основной текст
        self.main_label = QLabel("Перетащите файлы сюда")
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #333;
                background: transparent;
            }
        """)
        layout.addWidget(self.main_label)

        # Подсказка
        self.hint_label = QLabel("или нажмите для выбора файлов")
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                background: transparent;
            }
        """)
        layout.addWidget(self.hint_label)

        # Информация о формате
        self.format_label = QLabel("")
        self.format_label.setAlignment(Qt.AlignCenter)
        self.format_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #4CAF50;
                font-weight: bold;
                background: transparent;
            }
        """)
        layout.addWidget(self.format_label)

        # Список поддерживаемых форматов
        formats_text = "Поддерживаемые форматы: SDLTM, Excel, TMX, XML/TB"
        self.formats_label = QLabel(formats_text)
        self.formats_label.setAlignment(Qt.AlignCenter)
        self.formats_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                color: #999;
                background: transparent;
            }
        """)
        layout.addWidget(self.formats_label)

    def setup_styles(self):
        """Настройка стилей"""
        self.setMinimumHeight(200)
        self.update_style_normal()

    def update_style_normal(self):
        """Обычный стиль"""
        self.setStyleSheet("""
            SmartDropArea {
                border: 2px dashed #ccc;
                border-radius: 12px;
                background-color: #fafafa;
            }
        """)

    def update_style_hover(self):
        """Стиль при наведении"""
        self.setStyleSheet("""
            SmartDropArea {
                border: 2px dashed #4CAF50;
                border-radius: 12px;
                background-color: #f0f8f0;
            }
        """)
        self.icon_label.setStyleSheet("""
            QLabel {
                font-size: 52px;
                color: #4CAF50;
                background: transparent;
            }
        """)

    def update_style_error(self):
        """Стиль при ошибке"""
        self.setStyleSheet("""
            SmartDropArea {
                border: 2px dashed #f44336;
                border-radius: 12px;
                background-color: #fff0f0;
            }
        """)
        self.icon_label.setStyleSheet("""
            QLabel {
                font-size: 52px;
                color: #f44336;
                background: transparent;
            }
        """)

    def detect_format(self, filepaths: List[str]) -> tuple[str, List[str]]:
        """
        Определяет формат файлов
        Returns: (format_name, valid_files)
        """
        valid_files = []
        detected_formats = set()

        for filepath in filepaths:
            path = Path(filepath)
            if not path.exists() or not path.is_file():
                continue

            suffix = path.suffix.lower()
            if suffix in self.supported_formats:
                valid_files.append(filepath)
                detected_formats.add(self.supported_formats[suffix])

        if not valid_files:
            return "Неподдерживаемый формат", []

        if len(detected_formats) == 1:
            format_name = list(detected_formats)[0]
        else:
            format_name = f"Смешанные форматы ({len(detected_formats)})"

        return format_name, valid_files

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Обработчик входа перетаскивания"""
        if event.mimeData().hasUrls():
            filepaths = [url.toLocalFile() for url in event.mimeData().urls()]
            format_name, valid_files = self.detect_format(filepaths)

            if valid_files:
                self.detected_format = format_name
                self.format_label.setText(f"Обнаружен формат: {format_name}")
                self.update_style_hover()
                self.is_dragging = True
                event.acceptProposedAction()
            else:
                self.format_label.setText("❌ Неподдерживаемые файлы")
                self.update_style_error()
                event.ignore()
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
                font-size: 48px;
                color: #666;
                background: transparent;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        """Обработчик сброса файлов"""
        if event.mimeData().hasUrls():
            filepaths = [url.toLocalFile() for url in event.mimeData().urls()]
            format_name, valid_files = self.detect_format(filepaths)

            if valid_files:
                self.files_dropped.emit(valid_files)
                self.format_label.setText(f"✅ Добавлено файлов: {len(valid_files)}")

                # Возвращаем стиль через секунду
                from PySide6.QtCore import QTimer
                QTimer.singleShot(2000, self.reset_style)
            else:
                self.format_label.setText("❌ Нет поддерживаемых файлов")
                QTimer.singleShot(3000, self.reset_style)

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