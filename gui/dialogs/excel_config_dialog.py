# gui/dialogs/excel_config_dialog.py

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTabWidget, QGroupBox,
    QLabel, QLineEdit, QCheckBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QFormLayout, QMessageBox,
    QComboBox, QWidget, QDialog
)
from PySide6.QtCore import Qt
from typing import Dict
import logging

from core.base import ExcelAnalysis, ExcelConversionSettings, ColumnType, ColumnInfo

logger = logging.getLogger(__name__)


class ExcelConfigDialog(QDialog):
    """Диалог настройки конвертации Excel → TMX"""

    def __init__(self, excel_analysis: ExcelAnalysis, parent=None):
        super().__init__(parent)
        self.analysis = excel_analysis
        self.settings = None
        self.setup_ui()
        self.populate_data()

    def setup_ui(self):
        """Настройка интерфейса"""
        self.setWindowTitle(f"Настройка Excel → TMX: {self.analysis.file_path.name}")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Заголовок
        header = QLabel(f"📊 Настройка конвертации Excel файла")
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

        # Основные настройки
        main_settings = self.create_main_settings()
        layout.addWidget(main_settings)

        # Табы для листов Excel
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
           QTabWidget::pane {
               border: 1px solid #ddd;
               border-radius: 8px;
               background: white;
           }
           QTabBar::tab {
               padding: 8px 16px;
               margin-right: 2px;
               background: #f5f5f5;
               border: 1px solid #ddd;
               border-bottom: none;
               border-radius: 8px 8px 0 0;
           }
           QTabBar::tab:selected {
               background: white;
               border-bottom: 1px solid white;
           }
       """)
        layout.addWidget(self.tabs)

        # Кнопки
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        # Информация о выборе
        self.info_label = QLabel("Выберите листы и настройте колонки")
        self.info_label.setStyleSheet("color: #666; font-style: italic;")
        buttons_layout.addWidget(self.info_label)

        buttons_layout.addStretch()

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
        buttons_layout.addWidget(cancel_btn)

        self.convert_btn = QPushButton("✅ Конвертировать")
        self.convert_btn.setStyleSheet("""
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
           QPushButton:pressed {
               background: #3d8b40;
           }
       """)
        self.convert_btn.clicked.connect(self.accept_conversion)
        buttons_layout.addWidget(self.convert_btn)

        layout.addLayout(buttons_layout)

    def create_main_settings(self) -> QGroupBox:
        """Создает основные настройки"""
        group = QGroupBox("🌐 Основные настройки")
        group.setStyleSheet("""
           QGroupBox {
               font-weight: bold;
               font-size: 14px;
               margin-top: 10px;
               padding-top: 10px;
               border: 2px solid #ddd;
               border-radius: 8px;
           }
           QGroupBox::title {
               subcontrol-origin: margin;
               left: 10px;
               padding: 0 10px 0 10px;
               background: white;
           }
       """)

        layout = QFormLayout(group)
        layout.setSpacing(15)

        # Языки - простые поля ввода
        self.source_lang_edit = QLineEdit("ru-RU")
        self.source_lang_edit.setPlaceholderText("Например: ru-RU, en-US, de-DE")
        self.source_lang_edit.setStyleSheet("""
           QLineEdit {
               padding: 8px;
               border: 1px solid #ddd;
               border-radius: 4px;
               font-size: 13px;
           }
           QLineEdit:focus {
               border-color: #4CAF50;
           }
       """)
        layout.addRow("📥 Исходный язык:", self.source_lang_edit)

        self.target_lang_edit = QLineEdit("en-US")
        self.target_lang_edit.setPlaceholderText("Например: en-US, ru-RU, fr-FR")
        self.target_lang_edit.setStyleSheet(self.source_lang_edit.styleSheet())
        layout.addRow("📤 Целевой язык:", self.target_lang_edit)

        # Опции
        options_layout = QVBoxLayout()

        self.include_comments_cb = QCheckBox("💬 Включать комментарии в TMX")
        self.include_comments_cb.setChecked(True)
        self.include_comments_cb.setStyleSheet("font-weight: normal; margin: 5px;")
        options_layout.addWidget(self.include_comments_cb)

        self.include_context_cb = QCheckBox("📝 Включать контекст в TMX")
        self.include_context_cb.setChecked(True)
        self.include_context_cb.setStyleSheet("font-weight: normal; margin: 5px;")
        options_layout.addWidget(self.include_context_cb)

        self.skip_empty_cb = QCheckBox("🚫 Пропускать пустые сегменты")
        self.skip_empty_cb.setChecked(True)
        self.skip_empty_cb.setStyleSheet("font-weight: normal; margin: 5px;")
        options_layout.addWidget(self.skip_empty_cb)

        layout.addRow("⚙️ Опции:", options_layout)

        return group

    def populate_data(self):
        """Заполняет табы для каждого листа"""
        for sheet_info in self.analysis.sheets:
            if sheet_info.data_rows > 0:  # Только листы с данными
                sheet_widget = ExcelSheetWidget(sheet_info)
                tab_title = f"{sheet_info.name} ({sheet_info.data_rows} строк)"
                self.tabs.addTab(sheet_widget, tab_title)

        if self.tabs.count() == 0:
            # Если нет листов с данными
            empty_widget = QLabel("❌ В Excel файле не найдено листов с данными")
            empty_widget.setAlignment(Qt.AlignCenter)
            empty_widget.setStyleSheet("color: #999; font-size: 16px; margin: 50px;")
            self.tabs.addTab(empty_widget, "Нет данных")
            self.convert_btn.setEnabled(False)

    def accept_conversion(self):
        """Проверяет настройки и принимает диалог"""
        try:
            # Получаем языки
            source_lang = self.source_lang_edit.text().strip()
            target_lang = self.target_lang_edit.text().strip()

            # Простая валидация
            if not source_lang or not target_lang:
                QMessageBox.warning(self, "Ошибка",
                                    "Укажите исходный и целевой языки!\n\n"
                                    "Примеры: ru-RU, en-US, de-DE, fr-FR")
                return

            if source_lang == target_lang:
                QMessageBox.warning(self, "Ошибка",
                                    "Исходный и целевой языки не могут быть одинаковыми!")
                return

            # Собираем настройки листов
            selected_sheets = []
            column_mappings = {}

            valid_sheets = 0
            for i in range(self.tabs.count()):
                sheet_widget = self.tabs.widget(i)

                if not isinstance(sheet_widget, ExcelSheetWidget):
                    continue

                if sheet_widget.is_sheet_selected():
                    sheet_name = sheet_widget.sheet_info.name
                    selected_sheets.append(sheet_name)

                    # Получаем и проверяем маппинг колонок
                    column_mapping = sheet_widget.get_column_mapping()

                    # Проверяем, что есть хотя бы 2 текстовые колонки
                    text_columns = [col for col in column_mapping.values()
                                    if col.final_type == ColumnType.TEXT]

                    if len(text_columns) >= 2:
                        column_mappings[sheet_name] = column_mapping
                        valid_sheets += 1
                    else:
                        QMessageBox.warning(
                            self, "Ошибка конфигурации",
                            f"Лист '{sheet_name}': необходимо выбрать минимум 2 текстовые колонки "
                            f"для исходного и целевого языков!\n\n"
                            f"Сейчас выбрано: {len(text_columns)}"
                        )
                        return

            if valid_sheets == 0:
                QMessageBox.warning(self, "Ошибка",
                                    "Выберите хотя бы один лист с правильно настроенными колонками!\n\n"
                                    "Каждый лист должен иметь минимум 2 текстовые колонки.")
                return

            # Создаем настройки конвертации
            self.settings = ExcelConversionSettings(
                source_language=source_lang,
                target_language=target_lang,
                include_comments=self.include_comments_cb.isChecked(),
                include_context=self.include_context_cb.isChecked(),
                skip_empty_segments=self.skip_empty_cb.isChecked(),
                selected_sheets=selected_sheets,
                column_mappings=column_mappings
            )

            # Обновляем информационную строку
            self.info_label.setText(f"✅ Готово к конвертации: {valid_sheets} листов")

            logger.info(f"Excel conversion settings created: {valid_sheets} sheets, "
                        f"{source_lang} → {target_lang}")

            self.accept()

        except Exception as e:
            logger.exception(f"Error in accept_conversion: {e}")
            QMessageBox.critical(self, "Ошибка",
                                 f"Произошла ошибка при сохранении настроек:\n{e}")

    def get_settings(self) -> ExcelConversionSettings:
        """Возвращает настройки конвертации"""
        return self.settings


class ExcelSheetWidget(QWidget):
    """Виджет настройки отдельного листа Excel"""

    def __init__(self, sheet_info):
        super().__init__()
        self.sheet_info = sheet_info
        self.setup_ui()

    def setup_ui(self):
        """Настройка интерфейса листа"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Заголовок и чекбокс включения листа
        header_layout = QHBoxLayout()

        self.include_sheet_cb = QCheckBox(f"📋 Включить лист '{self.sheet_info.name}' в конвертацию")
        self.include_sheet_cb.setChecked(True)
        self.include_sheet_cb.setStyleSheet("""
           QCheckBox {
               font-weight: bold;
               font-size: 14px;
               margin: 5px;
               color: #333;
           }
           QCheckBox::indicator {
               width: 18px;
               height: 18px;
           }
       """)
        self.include_sheet_cb.toggled.connect(self.on_sheet_toggle)
        header_layout.addWidget(self.include_sheet_cb)

        header_layout.addStretch()

        # Информация о листе
        info_label = QLabel(f"📊 Строк данных: {self.sheet_info.data_rows} | "
                            f"📋 Колонок: {len(self.sheet_info.columns)}")
        info_label.setStyleSheet("""
           QLabel {
               color: #666;
               font-size: 12px;
               margin: 5px;
               padding: 5px 10px;
               background: #f9f9f9;
               border-radius: 4px;
           }
       """)
        header_layout.addWidget(info_label)

        layout.addLayout(header_layout)

        # Инструкция
        instruction = QLabel(
            "💡 Настройте колонки: выберите тип и язык для каждой колонки. "
            "Для конвертации нужно минимум 2 текстовые колонки."
        )
        instruction.setStyleSheet("""
           QLabel {
               color: #555;
               font-size: 11px;
               margin: 5px;
               padding: 8px;
               background: #fff8dc;
               border-left: 4px solid #ffa500;
               border-radius: 4px;
           }
       """)
        instruction.setWordWrap(True)
        layout.addWidget(instruction)

        # Таблица колонок
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "📋 Название колонки", "🔧 Тип", "🌐 Язык", "✅ Включить"
        ])

        # Настройка заголовков таблицы
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Название растягивается
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Тип по содержимому
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Язык по содержимому
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Чекбокс фиксированный

        # Стиль таблицы
        self.table.setStyleSheet("""
           QTableWidget {
               gridline-color: #e0e0e0;
               border: 1px solid #ddd;
               border-radius: 4px;
               background: white;
           }
           QTableWidget::item {
               padding: 8px;
               border: none;
           }
           QTableWidget::item:selected {
               background: #e3f2fd;
           }
           QHeaderView::section {
               background: #f5f5f5;
               padding: 8px;
               border: none;
               border-right: 1px solid #ddd;
               font-weight: bold;
           }
       """)

        self.populate_table()
        layout.addWidget(self.table)

        # Кнопки быстрой настройки
        quick_setup_layout = QHBoxLayout()

        auto_btn = QPushButton("🎯 Авто-настройка")
        auto_btn.setToolTip("Автоматически настроить первые две колонки как текст для перевода")
        auto_btn.clicked.connect(self.auto_setup_columns)
        auto_btn.setStyleSheet("""
           QPushButton {
               padding: 6px 12px;
               border: 1px solid #4CAF50;
               border-radius: 4px;
               background: #f0fff0;
               color: #2e7d32;
               font-size: 12px;
           }
           QPushButton:hover {
               background: #e8f5e8;
           }
       """)
        quick_setup_layout.addWidget(auto_btn)

        clear_btn = QPushButton("🗑️ Очистить")
        clear_btn.setToolTip("Сбросить все настройки колонок")
        clear_btn.clicked.connect(self.clear_column_settings)
        clear_btn.setStyleSheet("""
           QPushButton {
               padding: 6px 12px;
               border: 1px solid #f44336;
               border-radius: 4px;
               background: #fff5f5;
               color: #c62828;
               font-size: 12px;
           }
           QPushButton:hover {
               background: #ffebee;
           }
       """)
        quick_setup_layout.addWidget(clear_btn)

        quick_setup_layout.addStretch()
        layout.addLayout(quick_setup_layout)

    def populate_table(self):
        """Заполняет таблицу колонок"""
        self.table.setRowCount(len(self.sheet_info.columns))

        for row, col_info in enumerate(self.sheet_info.columns):
            # Название колонки (только для чтения)
            name_item = QTableWidgetItem(col_info.name)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_item.setToolTip(f"Колонка {col_info.index + 1}: {col_info.name}")
            self.table.setItem(row, 0, name_item)

            # Тип колонки
            type_combo = QComboBox()
            type_combo.addItems([
                "Текст для перевода",
                "Комментарий",
                "Контекст",
                "ID/Номер",
                "Игнорировать"
            ])
            type_combo.setCurrentText("Текст для перевода")
            type_combo.setStyleSheet("""
               QComboBox {
                   padding: 4px;
                   border: 1px solid #ddd;
                   border-radius: 3px;
               }
           """)
            self.table.setCellWidget(row, 1, type_combo)

            # Язык - простое поле ввода
            lang_edit = QLineEdit()
            lang_edit.setPlaceholderText("ru-RU, en-US, etc.")
            lang_edit.setStyleSheet("""
               QLineEdit {
                   padding: 4px;
                   border: 1px solid #ddd;
                   border-radius: 3px;
                   font-size: 11px;
               }
               QLineEdit:focus {
                   border-color: #4CAF50;
               }
           """)
            self.table.setCellWidget(row, 2, lang_edit)

            # Включить колонку
            include_cb = QCheckBox()
            include_cb.setChecked(True)
            include_cb.setStyleSheet("margin: 5px;")
            self.table.setCellWidget(row, 3, include_cb)

    def on_sheet_toggle(self, checked):
        """Обработчик переключения включения листа"""
        self.table.setEnabled(checked)

    def auto_setup_columns(self):
        """Автоматическая настройка колонок"""
        text_count = 0

        for row in range(self.table.rowCount()):
            if text_count < 2:
                # Первые две колонки - текст
                type_combo = self.table.cellWidget(row, 1)
                type_combo.setCurrentText("Текст для перевода")

                lang_edit = self.table.cellWidget(row, 2)
                if text_count == 0:
                    lang_edit.setText("ru-RU")
                else:
                    lang_edit.setText("en-US")

                include_cb = self.table.cellWidget(row, 3)
                include_cb.setChecked(True)

                text_count += 1
            else:
                # Остальные - игнорируем
                type_combo = self.table.cellWidget(row, 1)
                type_combo.setCurrentText("Игнорировать")

                include_cb = self.table.cellWidget(row, 3)
                include_cb.setChecked(False)

    def clear_column_settings(self):
        """Очищает настройки колонок"""
        for row in range(self.table.rowCount()):
            type_combo = self.table.cellWidget(row, 1)
            type_combo.setCurrentText("Текст для перевода")

            lang_edit = self.table.cellWidget(row, 2)
            lang_edit.clear()

            include_cb = self.table.cellWidget(row, 3)
            include_cb.setChecked(True)

    def is_sheet_selected(self) -> bool:
        """Проверяет, выбран ли лист для конвертации"""
        return self.include_sheet_cb.isChecked()

    def get_column_mapping(self) -> Dict[int, ColumnInfo]:
        """Возвращает маппинг колонок"""
        if not self.is_sheet_selected():
            return {}

        mapping = {}

        for row in range(self.table.rowCount()):
            include_cb = self.table.cellWidget(row, 3)
            if not include_cb.isChecked():
                continue

            type_combo = self.table.cellWidget(row, 1)
            lang_edit = self.table.cellWidget(row, 2)

            # Определяем тип колонки
            type_text = type_combo.currentText()
            if type_text == "Текст для перевода":
                col_type = ColumnType.TEXT
            elif type_text == "Комментарий":
                col_type = ColumnType.COMMENT
            elif type_text == "Контекст":
                col_type = ColumnType.CONTEXT
            elif type_text == "ID/Номер":
                col_type = ColumnType.ID
            else:  # "Игнорировать"
                col_type = ColumnType.IGNORE

            # Получаем язык
            user_lang = lang_edit.text().strip() or None

            # Создаем ColumnInfo на основе исходной информации
            original_col = self.sheet_info.columns[row]
            col_info = ColumnInfo(
                index=original_col.index,
                name=original_col.name,
                detected_language=original_col.detected_language,
                column_type=original_col.column_type,
                user_language=user_lang,
                user_type=col_type
            )

            mapping[original_col.index] = col_info

        return mapping