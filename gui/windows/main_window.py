# gui/windows/main_window.py - БЕЗ МИНИМАЛЬНЫХ РАЗМЕРОВ

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QFileDialog, QMessageBox,
    QGroupBox, QCheckBox, QSplitter, QFrame, QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from gui.ui_constants import (
    HEADER_FRAME_STYLE,
    TITLE_LABEL_STYLE,
    DESC_LABEL_STYLE,
    ADD_EXCEL_BUTTON_STYLE,
    START_BUTTON_STYLE,
    STOP_BUTTON_STYLE,
)
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Главное окно с поддержкой Excel конвертации"""

    def __init__(self):
        super().__init__()

        # Создаем контроллер
        from controller import MainController
        self.controller = MainController()
        from services import ConversionManager
        self.manager = ConversionManager()

        self.setup_window()
        self.setup_ui()
        self.setup_worker()
        self.setup_connections()

        # Состояние конвертации
        self.is_converting = False
        self.current_batch_results = []

        logger.info("Main window initialized with Excel support")

    def setup_window(self):
        """Настройка основного окна"""
        self.setWindowTitle("Converter Pro v2.0 - TM/TB/TMX/Excel Converter")
        # Убираем минимальный размер - можно изменять размер как угодно
        self.resize(1000, 700)  # Только начальный размер

        # НОВОЕ: Отключаем полноэкранный режим, чтобы не заходить за панель задач
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowFullscreenButtonHint)

    def showEvent(self, event):
        """Обработчик показа окна"""
        super().showEvent(event)
        # Обеспечиваем, что окно не выходит за пределы доступной области экрана
        self.ensure_window_in_screen()

    def ensure_window_in_screen(self):
        """Убеждаемся, что окно находится в пределах доступной области экрана"""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QScreen

        # Получаем доступную геометрию экрана (без панели задач)
        screen = QApplication.primaryScreen()
        if screen:
            available_geometry = screen.availableGeometry()
            window_geometry = self.geometry()

            # Проверяем и корректируем положение окна
            if not available_geometry.contains(window_geometry):
                # Центрируем окно в доступной области
                self.move(available_geometry.center() - window_geometry.center())

                # Если окно больше доступной области, уменьшаем его
                if (window_geometry.width() > available_geometry.width() or
                        window_geometry.height() > available_geometry.height()):
                    new_width = min(window_geometry.width(), available_geometry.width() - 20)
                    new_height = min(window_geometry.height(), available_geometry.height() - 20)
                    self.resize(new_width, new_height)
                    self.move(available_geometry.center() - self.rect().center())

    def changeEvent(self, event):
        """Обработчик изменения состояния окна"""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.WindowStateChange:
            if self.windowState() & Qt.WindowMaximized:
                # При максимизации используем доступную область экрана
                from PySide6.QtWidgets import QApplication
                screen = QApplication.primaryScreen()
                if screen:
                    # Используем availableGeometry вместо geometry
                    self.setGeometry(screen.availableGeometry())
        super().changeEvent(event)

    def setup_ui(self):
        """Создание пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной макет
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Заголовок
        self.create_header(main_layout)

        # Основная область - разделенная на две части
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Левая панель - файлы и настройки
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)

        # Правая панель - прогресс и логи
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        # Устанавливаем пропорции
        splitter.setSizes([600, 400])

        # Статус бар
        self.setup_status_bar()

    def create_header(self, layout):
        """Создает заголовок приложения"""
        header_frame = QFrame()
        header_frame.setStyleSheet(HEADER_FRAME_STYLE)
        header_layout = QHBoxLayout(header_frame)

        # Заголовок
        title_label = QLabel("Converter Pro v2.0")
        title_label.setStyleSheet(TITLE_LABEL_STYLE)
        header_layout.addWidget(title_label)

        # Описание
        desc_label = QLabel("Professional TM/TB/TMX/Excel Converter")
        desc_label.setStyleSheet(DESC_LABEL_STYLE)
        header_layout.addWidget(desc_label)

        header_layout.addStretch()
        layout.addWidget(header_frame)

    def create_left_panel(self) -> QWidget:
        """Создает левую панель с файлами и настройками"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Область для перетаскивания файлов
        from gui.widgets.drop_area import SmartDropArea
        self.drop_area = SmartDropArea()
        # Подключаем к контроллеру
        self.drop_area.files_dropped.connect(self.on_files_dropped)
        self.drop_area.files_dragged.connect(self.on_files_dragged)
        layout.addWidget(self.drop_area)

        # Кнопки управления файлами
        file_buttons = QHBoxLayout()

        self.add_files_btn = QPushButton("Добавить файлы")
        self.add_files_btn.clicked.connect(self.open_file_dialog)
        file_buttons.addWidget(self.add_files_btn)

        # НОВАЯ кнопка для Excel
        self.add_excel_btn = QPushButton("📊 Добавить Excel")
        self.add_excel_btn.setStyleSheet(ADD_EXCEL_BUTTON_STYLE)
        self.add_excel_btn.clicked.connect(self.open_excel_dialog)
        file_buttons.addWidget(self.add_excel_btn)

        self.clear_files_btn = QPushButton("Очистить")
        self.clear_files_btn.clicked.connect(self.clear_files)
        file_buttons.addWidget(self.clear_files_btn)

        file_buttons.addStretch()
        layout.addLayout(file_buttons)

        # Список файлов
        from gui.widgets.file_list import FileListWidget
        self.file_list = FileListWidget()
        self.file_list.file_remove_requested.connect(self.on_file_remove_requested)
        self.file_list.clear_all_btn.clicked.connect(self.clear_files)
        layout.addWidget(self.file_list)

        # Настройки конвертации
        settings_group = self.create_settings_group()
        layout.addWidget(settings_group)

        # Кнопки действий
        action_buttons = QHBoxLayout()

        self.start_btn = QPushButton("Начать конвертацию")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet(START_BUTTON_STYLE)
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setEnabled(False)
        action_buttons.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setStyleSheet(STOP_BUTTON_STYLE)
        self.stop_btn.clicked.connect(self.stop_conversion)
        self.stop_btn.setEnabled(False)
        action_buttons.addWidget(self.stop_btn)

        layout.addLayout(action_buttons)
        return panel

    def create_right_panel(self) -> QWidget:
        """Создает правую панель с прогрессом и логами"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Виджет прогресса
        from gui.widgets.progress_widget import ProgressWidget
        self.progress_widget = ProgressWidget()
        layout.addWidget(self.progress_widget)

        # Логи
        logs_group = QGroupBox("Логи конвертации")
        logs_layout = QVBoxLayout(logs_group)

        self.log_text = QTextEdit()
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMaximumHeight(200)
        logs_layout.addWidget(self.log_text)

        # Кнопки для логов
        log_buttons = QHBoxLayout()

        clear_log_btn = QPushButton("Очистить логи")
        clear_log_btn.clicked.connect(self.log_text.clear)
        log_buttons.addWidget(clear_log_btn)

        save_log_btn = QPushButton("Сохранить логи")
        save_log_btn.clicked.connect(self.save_logs)
        log_buttons.addWidget(save_log_btn)

        log_buttons.addStretch()
        logs_layout.addLayout(log_buttons)

        layout.addWidget(logs_group)

        # Removed results widget
        return panel

    def create_settings_group(self) -> QGroupBox:
        """Создает группу настроек конвертации"""
        group = QGroupBox("Настройки конвертации")
        layout = QVBoxLayout(group)

        # Форматы экспорта
        export_layout = QHBoxLayout()
        export_layout.addWidget(QLabel("Экспортировать:"))

        self.tmx_cb = QCheckBox("TMX")
        self.tmx_cb.setChecked(True)
        export_layout.addWidget(self.tmx_cb)

        self.xlsx_cb = QCheckBox("XLSX")
        export_layout.addWidget(self.xlsx_cb)

        self.json_cb = QCheckBox("JSON")
        export_layout.addWidget(self.json_cb)

        export_layout.addStretch()
        layout.addLayout(export_layout)

        # Автоопределенные языки
        auto_lang_layout = QHBoxLayout()
        auto_lang_layout.addWidget(QLabel("Автоопределенные языки:"))
        self.auto_langs_label = QLabel("Будут определены из файла")
        self.auto_langs_label.setStyleSheet("color: #666; font-style: italic;")
        auto_lang_layout.addWidget(self.auto_langs_label)
        auto_lang_layout.addStretch()
        layout.addLayout(auto_lang_layout)

        # Переопределение языков
        override_label = QLabel("Переопределить (оставьте пустым для автоопределения):")
        override_label.setStyleSheet("font-size: 11px; color: #666; margin-top: 5px;")
        layout.addWidget(override_label)

        manual_layout = QHBoxLayout()
        manual_layout.addWidget(QLabel("Исходный:"))

        self.src_lang_edit = QLineEdit()
        self.src_lang_edit.setPlaceholderText("например: en-US")
        self.src_lang_edit.setMaximumWidth(120)
        manual_layout.addWidget(self.src_lang_edit)

        manual_layout.addWidget(QLabel("Целевой:"))
        self.tgt_lang_edit = QLineEdit()
        self.tgt_lang_edit.setPlaceholderText("например: ru-RU")
        self.tgt_lang_edit.setMaximumWidth(120)
        manual_layout.addWidget(self.tgt_lang_edit)

        manual_layout.addStretch()
        layout.addLayout(manual_layout)

        return group

    def setup_worker(self):
        """Connects conversion manager signals."""
        self.manager.progress_changed.connect(self.on_progress_update)
        self.manager.file_started.connect(self.on_file_started)
        self.manager.file_completed.connect(self.on_file_completed)
        self.manager.batch_completed.connect(self.on_batch_completed)
        self.manager.error_occurred.connect(self.on_conversion_error)
        self.manager.excel_conversion_finished.connect(self.on_excel_conversion_finished)
        self.manager.excel_conversion_error.connect(self.on_excel_conversion_error)

    def setup_connections(self):
        """Настраивает дополнительные соединения сигналов"""
        self.file_list.files_changed.connect(self.on_files_changed)

    def setup_status_bar(self):
        """Настраивает статус бар"""
        self.status_label = QLabel("Готов к работе")
        self.statusBar().addWidget(self.status_label)

        # Индикатор версии
        version_label = QLabel("v2.0 + Excel")
        version_label.setStyleSheet("color: #666; font-size: 10px;")
        self.statusBar().addPermanentWidget(version_label)

    def save_logs(self):
        """Сохраняет логи в файл"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Сохранить логи", "conversion_logs.txt", "Text files (*.txt)"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                self.log_message(f"Логи сохранены в: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить логи: {e}")

    def log_message(self, message: str):
        """Добавляет сообщение в лог"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)

        # Автоскролл к концу
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

        # Ограничиваем количество строк в логе
        if self.log_text.document().lineCount() > 1000:
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, 100)
            cursor.removeSelectedText()

    # ===========================================
    # МЕТОДЫ ДЛЯ РАБОТЫ С ФАЙЛАМИ
    # ===========================================

    def on_files_dropped(self, filepaths: List[str]):
        """Обработчик добавления файлов с поддержкой Excel"""
        excel_files = []
        regular_files = []

        # Разделяем файлы на Excel и обычные
        for filepath in filepaths:
            path = Path(filepath)
            if self.controller.is_excel_file(path):
                excel_files.append(filepath)
            else:
                regular_files.append(filepath)

        # Обрабатываем Excel файлы через диалог настройки
        for excel_file in excel_files:
            self.handle_excel_file(Path(excel_file))

        # Обычные файлы добавляем как раньше
        if regular_files:
            files_info = self.controller.add_files(regular_files)
            if files_info:
                self.file_list.update_files(files_info)
                self.log_message(f"Добавлено файлов: {len(files_info)}")
                self._update_auto_languages_display()

    def on_files_dragged(self, filepaths: List[str]):
        """Обработчик проверки файлов при перетаскивании"""
        format_name, valid_files = self.controller.detect_drop_files(filepaths)
        is_valid = len(valid_files) > 0
        self.drop_area.set_format_info(format_name, is_valid)

    def on_file_remove_requested(self, filepath: Path):
        """Обработчик удаления файла"""
        if self.controller.remove_file(filepath):
            self._refresh_file_list()
            self.log_message(f"Удален файл: {filepath.name}")

    def open_file_dialog(self):
        """Открывает диалог выбора обычных файлов"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для конвертации",
            "",
            "Все поддерживаемые (*.sdltm *.xlsx *.xls *.tmx *.xml);;SDLTM (*.sdltm);;Excel (*.xlsx *.xls);;TMX (*.tmx);;XML (*.xml)"
        )

        if files:
            self.on_files_dropped(files)

    def open_excel_dialog(self):
        """Диалог выбора Excel файлов"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите Excel файлы для конвертации",
            "",
            "Excel файлы (*.xlsx *.xls);;XLSX (*.xlsx);;XLS (*.xls)"
        )

        if files:
            for excel_file in files:
                self.handle_excel_file(Path(excel_file))

    def clear_files(self):
        """Очищает список файлов"""
        self.controller.clear_files()
        self.file_list.clear()
        self.progress_widget.reset()
        self.log_message("Список файлов очищен")
        self._update_auto_languages_display()

    # ===========================================
    # МЕТОДЫ ДЛЯ EXCEL
    # ===========================================

    def handle_excel_file(self, filepath: Path):
        """Обрабатывает Excel файл через диалог настройки"""
        try:
            self.log_message(f"📊 Анализируем Excel файл: {filepath.name}")

            # Показываем диалог настройки
            settings = self.controller.show_excel_config_dialog(filepath, self)

            if settings:
                # Пользователь настроил - запускаем конвертацию
                self.log_message(f"✅ Настройки Excel приняты: {filepath.name}")
                self.start_excel_conversion(filepath, settings)
            else:
                self.log_message(f"❌ Конвертация Excel отменена: {filepath.name}")

        except Exception as e:
            error_msg = f"Ошибка обработки Excel файла: {e}"
            self.log_message(f"💥 {error_msg}")
            logger.exception(error_msg)

            QMessageBox.critical(
                self,
                "Ошибка Excel",
                f"Не удалось обработать Excel файл:\n\n{filepath.name}\n\n{e}"
            )

    def start_excel_conversion(self, filepath: Path, settings):
        """Запускает конвертацию Excel файла"""
        try:
            # Валидируем настройки
            is_valid, error_msg = self.controller.validate_excel_conversion_settings(settings)
            if not is_valid:
                QMessageBox.warning(self, "Ошибка настроек", error_msg)
                return

            # Создаем опции конвертации
            options = self.controller.prepare_excel_conversion_options(settings)

            # Добавляем колбэки прогресса
            options.progress_callback = lambda progress, message: self.progress_widget.update_progress(
                progress, f"Excel: {message}", 1, 1
            )
            options.should_stop_callback = lambda: not self.is_converting

            # Создаем и запускаем Excel worker
            self.manager.start_excel(filepath, settings, options)

            # Переключаем UI в режим конвертации
            self.is_converting = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.add_files_btn.setEnabled(False)
            self.add_excel_btn.setEnabled(False)

            self.progress_widget.reset()
            self.log_message(f"🚀 Начата конвертация Excel: {filepath.name}")
            self.log_message(f"   📊 Листов: {len(settings.selected_sheets)}")
            self.log_message(f"   🌐 Языки: {settings.source_language} → {settings.target_language}")

        except Exception as e:
            error_msg = f"Ошибка запуска Excel конвертации: {e}"
            self.log_message(f"💥 {error_msg}")
            logger.exception(error_msg)

            QMessageBox.critical(
                self,
                "Ошибка запуска",
                f"Не удалось запустить конвертацию Excel:\n\n{e}"
            )

    def on_excel_conversion_finished(self, result):
        """Обработчик завершения Excel конвертации"""
        try:

            # Возвращаем UI в обычный режим
            self.is_converting = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.add_files_btn.setEnabled(True)
            self.add_excel_btn.setEnabled(True)

            if result.success:
                # Успешная конвертация
                stats = result.stats

                self.progress_widget.set_completion_status(True, "Excel конвертация завершена!")

                self.log_message(
                    f"✅ Excel конвертация завершена за {stats.get('conversion_time', 0):.1f}с! "
                    f"Экспортировано: {stats.get('exported_segments', 0)} сегментов")

                # Показываем уведомление
                QMessageBox.information(
                    self,
                    "Конвертация завершена",
                    f"Excel файл успешно конвертирован!\n\n"
                    f"Экспортировано: {stats.get('exported_segments', 0)} сегментов\n"
                    f"Время: {stats.get('conversion_time', 0):.1f} секунд\n"
                    f"Результаты сохранены в папке с исходным файлом."
                )

            else:
                # Ошибка конвертации
                self.progress_widget.set_completion_status(False, "Ошибка Excel конвертации")

                error_msg = '; '.join(result.errors) if result.errors else "Неизвестная ошибка"
                self.log_message(f"❌ Ошибка Excel конвертации: {error_msg}")

                QMessageBox.warning(
                    self,
                    "Ошибка конвертации",
                    f"Не удалось конвертировать Excel файл:\n\n{error_msg}"
                )

        except Exception as e:
            logger.exception(f"Error in Excel conversion finished handler: {e}")

    def on_excel_conversion_error(self, error_msg: str):
        """Обработчик ошибок Excel конвертации"""
        try:

            # Возвращаем UI в обычный режим
            self.is_converting = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.add_files_btn.setEnabled(True)
            self.add_excel_btn.setEnabled(True)

            self.progress_widget.set_error_status(error_msg)
            self.log_message(f"💥 Критическая ошибка Excel конвертации: {error_msg}")

            QMessageBox.critical(
                self,
                "Критическая ошибка",
                f"Произошла критическая ошибка при конвертации Excel:\n\n{error_msg}"
            )

        except Exception as e:
            logger.exception(f"Error in Excel error handler: {e}")

    # ===========================================
    # КОНВЕРТАЦИЯ ОБЫЧНЫХ ФАЙЛОВ
    # ===========================================

    def start_conversion(self):
        """Запускает конвертацию обычных файлов"""
        # Собираем опции из GUI
        gui_options = {
            'export_tmx': self.tmx_cb.isChecked(),
            'export_xlsx': self.xlsx_cb.isChecked(),
            'export_json': self.json_cb.isChecked(),
            'source_lang': self.src_lang_edit.text().strip(),
            'target_lang': self.tgt_lang_edit.text().strip()
        }

        # Валидируем через контроллер
        is_valid, error_msg = self.controller.validate_conversion_request(gui_options)
        if not is_valid:
            QMessageBox.warning(self, "Ошибка", error_msg)
            return

        # Подготавливаем опции через контроллер
        options = self.controller.prepare_conversion_options(gui_options)
        files = self.controller.get_files_for_conversion()

        # Переключаем UI в режим конвертации
        self.is_converting = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.add_files_btn.setEnabled(False)
        self.add_excel_btn.setEnabled(False)

        # Очищаем состояние виджетов
        self.progress_widget.reset()
        self.file_list.reset_all_status()

        # Запускаем конвертацию через worker
        self.manager.start_batch(files, options)
        self.log_message(f"🚀 Начата конвертация {len(files)} файлов")

    def stop_conversion(self):
        """Останавливает конвертацию"""
        self.is_converting = False

        # Останавливаем обычные workers
        self.manager.stop_all()

        self.log_message("🛑 Запрошена остановка всех конвертаций...")

    def _refresh_file_list(self):
        """Обновляет отображение списка файлов"""
        files_info = []
        for filepath in self.controller.get_files_for_conversion():
            file_info = self.controller.file_service.get_file_info(filepath)
            files_info.append({
                'path': filepath,
                'name': file_info['name'],
                'size_mb': file_info['size_mb'],
                'format': file_info['format'],
                'format_icon': file_info['format_icon'],
                'extra_info': file_info['extra_info']
            })

        self.file_list.update_files(files_info)

    def _update_auto_languages_display(self):
        """Обновляет отображение автоопределенных языков"""
        languages = self.controller.get_auto_detected_languages()

        if languages:
            lang_text = f"{languages['source']} → {languages['target']}"
            self.auto_langs_label.setText(lang_text)
            self.auto_langs_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.auto_langs_label.setText("Будут определены из файла")
            self.auto_langs_label.setStyleSheet("color: #666; font-style: italic;")

    # ===========================================
    # ОБРАБОТЧИКИ WORKER'А ДЛЯ ОБЫЧНЫХ ФАЙЛОВ
    # ===========================================

    def on_progress_update(self, progress: int, message: str, current_file: int, total_files: int):
        """Обработчик обновления прогресса"""
        self.progress_widget.update_progress(progress, message, current_file, total_files)

        if total_files > 0:
            self.status_label.setText(f"Обработка файла {current_file}/{total_files}: {message}")
        else:
            self.status_label.setText(message)

    def on_file_started(self, filepath: Path):
        """Обработчик начала конвертации файла"""
        logger.info(f"File started: {filepath.name}")
        self.log_message(f"Начата обработка: {filepath.name}")

        file_item = self.file_list.get_file_item(filepath)
        if file_item:
            file_item.set_conversion_progress(0, "Начинаем обработку...")

    def on_file_completed(self, filepath: Path, result):
        """Обработчик завершения конвертации файла"""
        self.progress_widget.on_file_completed(result.success)

        file_item = self.file_list.get_file_item(filepath)
        if file_item:
            if result.success:
                stats = result.stats
                exported_count = stats.get('exported', 0)
                file_item.set_conversion_completed(True, f"Экспортировано: {exported_count}")
            else:
                error_msg = '; '.join(result.errors) if result.errors else "Неизвестная ошибка"
                file_item.set_conversion_completed(False, error_msg)

        if result.success:
            self.log_message(f"✅ Завершено: {filepath.name}")

            stats = result.stats
            for out in result.output_files:
                self.log_message(f"  📄 {out.name}")
            self.log_message(
                f"   Экспортировано: {stats.get('exported', 0)} | "
                f"Всего: {stats.get('total_in_sdltm', stats.get('total', 0))} | "
                f"Время: {stats.get('conversion_time', 0):.1f}с")
        else:
            error_msg = '; '.join(result.errors) if result.errors else "Неизвестная ошибка"
            self.log_message(f"❌ Ошибка: {filepath.name} - {error_msg}")

    def on_batch_completed(self, results: List):
        """Обработчик завершения всей пакетной конвертации"""
        successful = sum(1 for r in results if r.success)
        total = len(results)

        logger.info(f"Batch completed: {successful}/{total} successful")

        # Обновляем UI
        self.is_converting = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.add_files_btn.setEnabled(True)
        self.add_excel_btn.setEnabled(True)

        # Финальный статус в progress_widget
        if successful == total:
            self.progress_widget.set_completion_status(True, f"Все файлы успешно конвертированы!")
        else:
            self.progress_widget.set_completion_status(False, f"Конвертировано {successful} из {total} файлов")

        # Итоговое сообщение
        self.log_message(f"🎉 Конвертация завершена: {successful}/{total} успешно")

        # Показываем диалог с итогами
        if successful > 0:
            QMessageBox.information(
                self,
                "Конвертация завершена",
                f"Успешно конвертировано: {successful} из {total} файлов"
            )
        else:
            QMessageBox.warning(
                self,
                "Конвертация не удалась",
                f"Ни один файл не был успешно конвертирован.\n"
                f"Проверьте логи для подробностей."
            )

    def on_conversion_error(self, error_msg: str):
        """Обработчик критических ошибок конвертации"""
        logger.error(f"Conversion error: {error_msg}")

        # Возвращаем UI в обычный режим
        self.is_converting = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.add_files_btn.setEnabled(True)
        self.add_excel_btn.setEnabled(True)

        # Показываем ошибку в progress_widget
        self.progress_widget.set_error_status(error_msg)

        # Логируем ошибку
        self.log_message(f"💥 Критическая ошибка: {error_msg}")

        # Показываем диалог с ошибкой
        QMessageBox.critical(
            self,
            "Ошибка конвертации",
            f"Произошла критическая ошибка:\n\n{error_msg}\n\n"
            f"Проверьте логи для подробностей."
        )

    def on_files_changed(self, file_count: int):
        """Обработчик изменения списка файлов"""
        self.start_btn.setEnabled(file_count > 0 and not self.is_converting)
        self.status_label.setText(f"Файлов в очереди: {file_count}")

    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        # Останавливаем конвертацию если она идет
        if self.is_converting:
            reply = QMessageBox.question(
                self,
                "Конвертация в процессе",
                "Конвертация еще не завершена. Остановить и закрыть приложение?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.No:
                event.ignore()
                return

            self.stop_conversion()

        self.manager.shutdown()
        event.accept()
        logger.info("Main window closed")

