# gui/windows/main_window.py

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QFileDialog, QMessageBox,
    QGroupBox, QCheckBox, QSplitter, QFrame
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

    def __init__(self):
        super().__init__()

        from controller import MainController
        self.controller = MainController()
        from services import ConversionManager
        self.manager = ConversionManager()

        self.setup_window()
        self.setup_ui()
        self.setup_worker()
        self.setup_connections()

        self.is_converting = False
        self.current_batch_results = []

        logger.info("Main window initialized with Excel and SDLXLIFF support")

    def setup_window(self):
        self.setWindowTitle("Converter Pro v2.0 - TM/TB/TMX/Excel/SDLXLIFF Converter")
        self.resize(1000, 700)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowFullscreenButtonHint)

    def showEvent(self, event):
        super().showEvent(event)
        self.ensure_window_in_screen()

    def ensure_window_in_screen(self):
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen:
            available_geometry = screen.availableGeometry()
            window_geometry = self.geometry()

            if not available_geometry.contains(window_geometry):
                self.move(available_geometry.center() - window_geometry.center())

                if (window_geometry.width() > available_geometry.width() or
                        window_geometry.height() > available_geometry.height()):
                    new_width = min(window_geometry.width(), available_geometry.width() - 20)
                    new_height = min(window_geometry.height(), available_geometry.height() - 20)
                    self.resize(new_width, new_height)
                    self.move(available_geometry.center() - self.rect().center())

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.WindowStateChange:
            if self.windowState() & Qt.WindowMaximized:
                from PySide6.QtWidgets import QApplication
                screen = QApplication.primaryScreen()
                if screen:
                    self.setGeometry(screen.availableGeometry())
        super().changeEvent(event)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.create_header(main_layout)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)

        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([600, 400])

        self.setup_status_bar()

    def create_header(self, layout):
        header_frame = QFrame()
        header_frame.setStyleSheet(HEADER_FRAME_STYLE)
        header_layout = QHBoxLayout(header_frame)

        title_label = QLabel("Converter Pro v2.0")
        title_label.setStyleSheet(TITLE_LABEL_STYLE)
        header_layout.addWidget(title_label)

        desc_label = QLabel("Professional TM/TB/TMX/Excel/SDLXLIFF Converter")
        desc_label.setStyleSheet(DESC_LABEL_STYLE)
        header_layout.addWidget(desc_label)

        header_layout.addStretch()
        layout.addWidget(header_frame)

    def create_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        from gui.widgets.drop_area import SmartDropArea
        self.drop_area = SmartDropArea()
        self.drop_area.files_dropped.connect(self.on_files_dropped)
        self.drop_area.files_dragged.connect(self.on_files_dragged)
        layout.addWidget(self.drop_area)

        file_buttons = QHBoxLayout()

        self.add_files_btn = QPushButton("Добавить файлы")
        self.add_files_btn.clicked.connect(self.open_file_dialog)
        file_buttons.addWidget(self.add_files_btn)

        self.add_excel_btn = QPushButton("📊 Добавить Excel")
        self.add_excel_btn.setStyleSheet(ADD_EXCEL_BUTTON_STYLE)
        self.add_excel_btn.clicked.connect(self.open_excel_dialog)
        file_buttons.addWidget(self.add_excel_btn)

        self.split_sdlxliff_btn = QPushButton("✂️ Разделить SDLXLIFF")
        self.split_sdlxliff_btn.setStyleSheet("""
            QPushButton {
                background: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1976D2;
            }
        """)
        self.split_sdlxliff_btn.clicked.connect(self.open_sdlxliff_split_dialog)
        file_buttons.addWidget(self.split_sdlxliff_btn)

        self.merge_sdlxliff_btn = QPushButton("🔗 Объединить SDLXLIFF")
        self.merge_sdlxliff_btn.setStyleSheet("""
            QPushButton {
                background: #9C27B0;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #7B1FA2;
            }
        """)
        self.merge_sdlxliff_btn.clicked.connect(self.open_sdlxliff_merge_dialog)
        file_buttons.addWidget(self.merge_sdlxliff_btn)

        self.clear_files_btn = QPushButton("Очистить")
        self.clear_files_btn.clicked.connect(self.clear_files)
        file_buttons.addWidget(self.clear_files_btn)

        file_buttons.addStretch()
        layout.addLayout(file_buttons)

        from gui.widgets.file_list import FileListWidget
        self.file_list = FileListWidget()
        self.file_list.file_remove_requested.connect(self.on_file_remove_requested)
        self.file_list.clear_all_btn.clicked.connect(self.clear_files)
        layout.addWidget(self.file_list)

        settings_group = self.create_settings_group()
        layout.addWidget(settings_group)

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
        panel = QWidget()
        layout = QVBoxLayout(panel)

        from gui.widgets.progress_widget import ProgressWidget
        self.progress_widget = ProgressWidget()
        layout.addWidget(self.progress_widget)

        logs_group = QGroupBox("Логи конвертации")
        logs_layout = QVBoxLayout(logs_group)

        self.log_text = QTextEdit()
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMaximumHeight(200)
        logs_layout.addWidget(self.log_text)

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

        return panel

    def create_settings_group(self) -> QGroupBox:
        group = QGroupBox("Настройки конвертации")
        layout = QVBoxLayout(group)

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

        self.auto_langs_label = QLabel()
        layout.addWidget(self.auto_langs_label)

        return group

    def setup_worker(self):
        self.manager.progress_changed.connect(self.on_progress_update)
        self.manager.file_started.connect(self.on_file_started)
        self.manager.file_completed.connect(self.on_file_completed)
        self.manager.batch_completed.connect(self.on_batch_completed)
        self.manager.error_occurred.connect(self.on_conversion_error)
        self.manager.excel_conversion_finished.connect(self.on_excel_conversion_finished)
        self.manager.excel_conversion_error.connect(self.on_excel_conversion_error)
        self.manager.tb_progress.connect(lambda p: self.progress_widget.update_progress(p, "TB", 1, 1))
        self.manager.tb_log.connect(self.log_message)
        self.manager.tb_finished.connect(self.on_tb_conversion_finished)
        self.manager.tb_error.connect(self.on_tb_conversion_error)
        self.manager.sdlxliff_progress.connect(self.on_sdlxliff_progress)
        self.manager.sdlxliff_log.connect(self.log_message)
        self.manager.sdlxliff_finished.connect(self.on_sdlxliff_finished)
        self.manager.sdlxliff_error.connect(self.on_sdlxliff_error)

    def setup_connections(self):
        self.file_list.files_changed.connect(self.on_files_changed)
        self.file_list.file_language_edit_requested.connect(self.edit_file_languages)

    def setup_status_bar(self):
        self.status_label = QLabel("Готов к работе")
        self.statusBar().addWidget(self.status_label)

        version_label = QLabel("v2.0 + Excel + SDLXLIFF")
        version_label.setStyleSheet("color: #666; font-size: 10px;")
        self.statusBar().addPermanentWidget(version_label)

    def save_logs(self):
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
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)

        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

        if self.log_text.document().lineCount() > 1000:
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, 100)
            cursor.removeSelectedText()

    def on_files_dropped(self, filepaths: List[str]):
        excel_files = []
        termbase_files = []
        regular_files = []
        sdlxliff_files = []

        for filepath in filepaths:
            path = Path(filepath)
            if self.controller.is_excel_file(path):
                excel_files.append(filepath)
            elif self.controller.is_termbase_file(path):
                termbase_files.append(filepath)
            elif self.controller.is_sdlxliff_file(path):
                sdlxliff_files.append(filepath)
            else:
                regular_files.append(filepath)

        for excel_file in excel_files:
            self.handle_excel_file(Path(excel_file))

        for tb_file in termbase_files:
            self.handle_termbase_file(Path(tb_file))

        for sdlxliff_file in sdlxliff_files:
            self.handle_sdlxliff_file(Path(sdlxliff_file))

        if regular_files:
            files_info = self.controller.add_files(regular_files)
            if files_info:
                self.file_list.update_files(files_info)
                self.log_message(f"Добавлено файлов: {len(files_info)}")
                self._update_auto_languages_display()

    def on_files_dragged(self, filepaths: List[str]):
        format_name, valid_files = self.controller.detect_drop_files(filepaths)
        is_valid = len(valid_files) > 0
        self.drop_area.set_format_info(format_name, is_valid)

    def on_file_remove_requested(self, filepath: Path):
        if self.controller.remove_file(filepath):
            self._refresh_file_list()
            self.log_message(f"Удален файл: {filepath.name}")

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для конвертации",
            "",
            "Все поддерживаемые (*.sdltm *.xlsx *.xls *.tmx *.xml *.mtf *.tbx *.sdlxliff);;SDLTM (*.sdltm);;Excel (*.xlsx *.xls);;TMX (*.tmx);;XML/Termbase (*.xml *.mtf *.tbx);;SDLXLIFF (*.sdlxliff)"
        )

        if files:
            self.on_files_dropped(files)

    def open_excel_dialog(self):
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
        self.controller.clear_files()
        self.file_list.clear()
        self.progress_widget.reset()
        self.log_message("Список файлов очищен")
        self._update_auto_languages_display()

    def handle_excel_file(self, filepath: Path):
        try:
            self.log_message(f"📊 Анализируем Excel файл: {filepath.name}")
            settings = self.controller.show_excel_config_dialog(filepath, self)

            if settings:
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

    def handle_termbase_file(self, filepath: Path):
        try:
            self.log_message(f"📖 Анализируем TB файл: {filepath.name}")
            settings = self.controller.show_termbase_config_dialog(filepath, self)
            if settings:
                self.log_message(f"✅ Настройки TB приняты: {filepath.name}")
                self.start_termbase_conversion(filepath, settings)
            else:
                self.log_message(f"❌ Конвертация TB отменена: {filepath.name}")
        except Exception as e:
            error_msg = f"Ошибка обработки TB файла: {e}"
            self.log_message(f"💥 {error_msg}")
            logger.exception(error_msg)
            QMessageBox.critical(
                self,
                "Ошибка TB",
                f"Не удалось обработать файл:\n\n{filepath.name}\n\n{e}"
            )

    def handle_sdlxliff_file(self, filepath: Path):
        try:
            if self.controller.is_sdlxliff_part_file(filepath):
                reply = QMessageBox.question(
                    self,
                    "Обнаружена часть SDLXLIFF",
                    f"Файл '{filepath.name}' является частью разделенного SDLXLIFF.\n\n"
                    f"Хотите найти все части и объединить их?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )

                if reply == QMessageBox.Yes:
                    parts = self.controller.find_sdlxliff_parts(filepath)
                    if len(parts) < 2:
                        QMessageBox.warning(
                            self,
                            "Части не найдены",
                            f"Не удалось найти все части файла.\n"
                            f"Найдено частей: {len(parts)}"
                        )
                        return

                    self.handle_sdlxliff_merge(parts)
                return

            reply = QMessageBox.question(
                self,
                "SDLXLIFF файл",
                f"Файл '{filepath.name}' является SDLXLIFF файлом.\n\n"
                f"Вы можете разделить его на несколько частей для распределенного перевода.\n\n"
                f"Хотите разделить файл?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self.handle_sdlxliff_split(filepath)

        except Exception as e:
            error_msg = f"Ошибка обработки SDLXLIFF файла: {e}"
            self.log_message(f"💥 {error_msg}")
            logger.exception(error_msg)

            QMessageBox.critical(
                self,
                "Ошибка SDLXLIFF",
                f"Не удалось обработать SDLXLIFF файл:\n\n{filepath.name}\n\n{e}"
            )

    def handle_sdlxliff_split(self, filepath: Path):
        try:
            self.log_message(f"✂️ Анализируем SDLXLIFF файл: {filepath.name}")
            settings = self.controller.show_sdlxliff_split_dialog(filepath, self)

            if settings:
                self.log_message(f"✅ Настройки разделения приняты: {filepath.name}")
                self.start_sdlxliff_split(filepath, settings)
            else:
                self.log_message(f"❌ Разделение SDLXLIFF отменено: {filepath.name}")

        except Exception as e:
            error_msg = f"Ошибка разделения SDLXLIFF: {e}"
            self.log_message(f"💥 {error_msg}")
            logger.exception(error_msg)

            QMessageBox.critical(
                self,
                "Ошибка разделения",
                f"Не удалось разделить SDLXLIFF файл:\n\n{e}"
            )

    def handle_sdlxliff_merge(self, filepaths: List[Path]):
        try:
            self.log_message(f"🔗 Подготовка к объединению {len(filepaths)} SDLXLIFF файлов")
            settings, ordered_files = self.controller.show_sdlxliff_merge_dialog(filepaths, self)

            if settings and ordered_files:
                self.log_message(f"✅ Настройки объединения приняты: {len(ordered_files)} файлов")
                self.start_sdlxliff_merge(ordered_files, settings)
            else:
                self.log_message("❌ Объединение SDLXLIFF отменено")

        except Exception as e:
            error_msg = f"Ошибка объединения SDLXLIFF: {e}"
            self.log_message(f"💥 {error_msg}")
            logger.exception(error_msg)

            QMessageBox.critical(
                self,
                "Ошибка объединения",
                f"Не удалось объединить SDLXLIFF файлы:\n\n{e}"
            )

    def open_sdlxliff_split_dialog(self):
        from gui.dialogs.sdlxliff_dialogs import SdlxliffSplitDialog
        from PySide6.QtWidgets import QDialog

        dialog = SdlxliffSplitDialog(self)
        if dialog.exec() == QDialog.Accepted:
            filepath = dialog.get_filepath()
            settings = dialog.get_settings()
            if filepath and settings:
                self.start_sdlxliff_split(filepath, settings)

    def open_sdlxliff_merge_dialog(self):
        from gui.dialogs.sdlxliff_dialogs import SdlxliffMergeDialog
        from PySide6.QtWidgets import QDialog

        dialog = SdlxliffMergeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            files = dialog.get_ordered_files()
            settings = dialog.get_settings()

            if files and settings:
                self.start_sdlxliff_merge(files, settings)

    def edit_file_languages(self, filepath: Path):
        langs = self.controller.get_file_languages(filepath) or {}
        src = langs.get('source', '')
        tgt = langs.get('target', '')
        from gui.dialogs import LanguageDialog
        from PySide6.QtWidgets import QDialog

        dialog = LanguageDialog(src, tgt, self)
        if dialog.exec() == QDialog.Accepted:
            src_lang, tgt_lang = dialog.get_languages()
            if src_lang or tgt_lang:
                self.controller.set_file_languages(filepath, src_lang, tgt_lang)
                self.file_list.set_file_languages(filepath, {'source': src_lang, 'target': tgt_lang})

    def start_excel_conversion(self, filepath: Path, settings):
        try:
            is_valid, error_msg = self.controller.validate_excel_conversion_settings(settings)
            if not is_valid:
                QMessageBox.warning(self, "Ошибка настроек", error_msg)
                return

            options = self.controller.prepare_excel_conversion_options(settings)

            options.progress_callback = lambda progress, message: self.progress_widget.update_progress(
                progress, f"Excel: {message}", 1, 1
            )
            options.should_stop_callback = lambda: not self.is_converting

            self.manager.start_excel(filepath, settings, options)

            self.is_converting = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.add_files_btn.setEnabled(False)
            self.add_excel_btn.setEnabled(False)
            self.split_sdlxliff_btn.setEnabled(False)
            self.merge_sdlxliff_btn.setEnabled(False)

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

    def start_termbase_conversion(self, filepath: Path, settings):
        try:
            is_valid, error_msg = self.controller.validate_termbase_conversion_settings(settings)
            if not is_valid:
                QMessageBox.warning(self, "Ошибка настроек", error_msg)
                return

            options = self.controller.prepare_termbase_conversion_options(settings)

            options.progress_callback = lambda p, msg: self.progress_widget.update_progress(p, f"TB: {msg}", 1, 1)
            options.should_stop_callback = lambda: not self.is_converting

            self.manager.start_termbase(filepath, options)

            self.is_converting = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.add_files_btn.setEnabled(False)
            self.add_excel_btn.setEnabled(False)
            self.split_sdlxliff_btn.setEnabled(False)
            self.merge_sdlxliff_btn.setEnabled(False)

            self.progress_widget.reset()
            self.log_message(f"🚀 Начата конвертация TB: {filepath.name}")
        except Exception as e:
            error_msg = f"Ошибка запуска TB конвертации: {e}"
            self.log_message(f"💥 {error_msg}")
            logger.exception(error_msg)
            QMessageBox.critical(
                self,
                "Ошибка запуска",
                f"Не удалось запустить конвертацию TB:\n\n{e}"
            )

    def start_sdlxliff_split(self, filepath: Path, settings):
        try:
            from core.base import ConversionOptions
            options = ConversionOptions()

            self.manager.start_sdlxliff_merge(filepaths, settings, options)

            self.is_converting = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.add_files_btn.setEnabled(False)
            self.add_excel_btn.setEnabled(False)
            self.split_sdlxliff_btn.setEnabled(False)
            self.merge_sdlxliff_btn.setEnabled(False)

            self.progress_widget.reset()
            self.log_message(f"🚀 Начато объединение {len(filepaths)} SDLXLIFF файлов")
            self.log_message(f"   ✅ Валидация: {'Да' if settings.validate_parts else 'Нет'}")
        except Exception as e:
            error_msg = f"Ошибка запуска объединения SDLXLIFF: {e}"
            self.log_message(f"💥 {error_msg}")
            logger.exception(error_msg)

            QMessageBox.critical(
                self,
                "Ошибка запуска",
                f"Не удалось запустить объединение SDLXLIFF:\n\n{e}"
            )

    def on_sdlxliff_progress(self, progress: int, message: str):
        self.progress_widget.update_progress(progress, f"SDLXLIFF: {message}", 1, 1)

    def on_sdlxliff_finished(self, result):
        try:
            self.is_converting = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.add_files_btn.setEnabled(True)
            self.add_excel_btn.setEnabled(True)
            self.split_sdlxliff_btn.setEnabled(True)
            self.merge_sdlxliff_btn.setEnabled(True)

            if result.success:
                stats = result.stats
                operation = stats.get('operation', 'unknown')

                if operation == 'split':
                    self.progress_widget.set_completion_status(True, "Разделение завершено!")
                    self.log_message(
                        f"✅ SDLXLIFF разделение завершено! "
                        f"Создано {stats.get('parts_count', 0)} частей"
                    )
                elif operation == 'merge' or operation == 'merge_with_original':
                    self.progress_widget.set_completion_status(True, "Объединение завершено!")
                    self.log_message(
                        f"✅ SDLXLIFF объединение завершено! "
                        f"Всего сегментов: {stats.get('total_segments', 0)}"
                    )
            else:
                self.progress_widget.set_completion_status(False, "Ошибка SDLXLIFF операции")

                error_msg = '; '.join(result.errors) if result.errors else "Неизвестная ошибка"
                self.log_message(f"❌ Ошибка SDLXLIFF операции: {error_msg}")

                QMessageBox.warning(
                    self,
                    "Ошибка операции",
                    f"Не удалось выполнить операцию с SDLXLIFF:\n\n{error_msg}"
                )

        except Exception as e:
            logger.exception(f"Error in SDLXLIFF finished handler: {e}")

    def on_sdlxliff_error(self, error_msg: str):
        try:
            self.is_converting = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.add_files_btn.setEnabled(True)
            self.add_excel_btn.setEnabled(True)
            self.split_sdlxliff_btn.setEnabled(True)
            self.merge_sdlxliff_btn.setEnabled(True)

            self.progress_widget.set_error_status(error_msg)
            self.log_message(f"💥 Критическая ошибка SDLXLIFF операции: {error_msg}")

            QMessageBox.critical(
                self,
                "Критическая ошибка",
                f"Произошла критическая ошибка при операции с SDLXLIFF:\n\n{error_msg}"
            )

        except Exception as e:
            logger.exception(f"Error in SDLXLIFF error handler: {e}")

    def start_conversion(self):
        gui_options = {
            'export_tmx': self.tmx_cb.isChecked(),
            'export_xlsx': self.xlsx_cb.isChecked(),
            'export_json': self.json_cb.isChecked()
        }

        is_valid, error_msg = self.controller.validate_conversion_request(gui_options)
        if not is_valid:
            QMessageBox.warning(self, "Ошибка", error_msg)
            return

        options = self.controller.prepare_conversion_options(gui_options)
        files = self.controller.get_files_for_conversion()

        self.is_converting = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.add_files_btn.setEnabled(False)
        self.add_excel_btn.setEnabled(False)
        self.split_sdlxliff_btn.setEnabled(False)
        self.merge_sdlxliff_btn.setEnabled(False)

        self.progress_widget.reset()
        self.file_list.reset_all_status()

        self.manager.start_batch(files, options, self.controller.get_file_language_mapping())
        self.log_message(f"🚀 Начата конвертация {len(files)} файлов")

    def stop_conversion(self):
        self.is_converting = False
        self.manager.stop_all()
        self.log_message("🛑 Запрошена остановка всех конвертаций...")

    def _refresh_file_list(self):
        files_info = []
        for filepath in self.controller.get_files_for_conversion():
            file_info = self.controller.file_service.get_file_info(filepath)
            files_info.append({
                'path': filepath,
                'name': file_info['name'],
                'size_mb': file_info['size_mb'],
                'format': file_info['format'],
                'format_icon': file_info['format_icon'],
                'extra_info': file_info['extra_info'],
                'languages': self.controller.get_file_languages(filepath)
            })

        self.file_list.update_files(files_info)

    def _update_auto_languages_display(self):
        languages = self.controller.get_auto_detected_languages()
        src_file = self.controller.auto_language_source

        if languages:
            lang_text = f"{languages['source']} → {languages['target']}"
            if src_file:
                lang_text += f" ({Path(src_file).name})"
            self.auto_langs_label.setText(lang_text)
            self.auto_langs_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.auto_langs_label.setText("Будут определены из файла")
            self.auto_langs_label.setStyleSheet("color: #666; font-style: italic;")

    def on_progress_update(self, progress: int, message: str, current_file: int, total_files: int):
        self.progress_widget.update_progress(progress, message, current_file, total_files)

        if total_files > 0:
            self.status_label.setText(f"Обработка файла {current_file}/{total_files}: {message}")
        else:
            self.status_label.setText(message)

    def on_file_started(self, filepath: Path):
        logger.info(f"File started: {filepath.name}")
        self.log_message(f"Начата обработка: {filepath.name}")

        file_item = self.file_list.get_file_item(filepath)
        if file_item:
            file_item.set_conversion_progress(0, "Начинаем обработку...")

    def on_file_completed(self, filepath: Path, result):
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
        successful = sum(1 for r in results if r.success)
        total = len(results)

        logger.info(f"Batch completed: {successful}/{total} successful")

        self.is_converting = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.add_files_btn.setEnabled(True)
        self.add_excel_btn.setEnabled(True)
        self.split_sdlxliff_btn.setEnabled(True)
        self.merge_sdlxliff_btn.setEnabled(True)

        if successful == total:
            self.progress_widget.set_completion_status(True, f"Все файлы успешно конвертированы!")
        else:
            self.progress_widget.set_completion_status(False, f"Конвертировано {successful} из {total} файлов")

        self.log_message(f"🎉 Конвертация завершена: {successful}/{total} успешно")

        if successful == 0:
            QMessageBox.warning(
                self,
                "Конвертация не удалась",
                f"Ни один файл не был успешно конвертирован.\n"
                f"Проверьте логи для подробностей."
            )

    def on_conversion_error(self, error_msg: str):
        logger.error(f"Conversion error: {error_msg}")

        self.is_converting = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.add_files_btn.setEnabled(True)
        self.add_excel_btn.setEnabled(True)
        self.split_sdlxliff_btn.setEnabled(True)
        self.merge_sdlxliff_btn.setEnabled(True)

        self.progress_widget.set_error_status(error_msg)

        self.log_message(f"💥 Критическая ошибка: {error_msg}")

        QMessageBox.critical(
            self,
            "Ошибка конвертации",
            f"Произошла критическая ошибка:\n\n{error_msg}\n\n"
            f"Проверьте логи для подробностей."
        )

    def on_files_changed(self, file_count: int):
        self.start_btn.setEnabled(file_count > 0 and not self.is_converting)
        self.status_label.setText(f"Файлов в очереди: {file_count}")

    def on_excel_conversion_finished(self, result):
        try:
            self.is_converting = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.add_files_btn.setEnabled(True)
            self.add_excel_btn.setEnabled(True)
            self.split_sdlxliff_btn.setEnabled(True)
            self.merge_sdlxliff_btn.setEnabled(True)

            if result.success:
                stats = result.stats

                self.progress_widget.set_completion_status(True, "Excel конвертация завершена!")

                self.log_message(
                    f"✅ Excel конвертация завершена за {stats.get('conversion_time', 0):.1f}с! "
                    f"Экспортировано: {stats.get('exported_segments', 0)} сегментов")

            else:
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
        try:
            self.is_converting = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.add_files_btn.setEnabled(True)
            self.add_excel_btn.setEnabled(True)
            self.split_sdlxliff_btn.setEnabled(True)
            self.merge_sdlxliff_btn.setEnabled(True)

            self.progress_widget.set_error_status(error_msg)
            self.log_message(f"💥 Критическая ошибка Excel конвертации: {error_msg}")

            QMessageBox.critical(
                self,
                "Критическая ошибка",
                f"Произошла критическая ошибка при конвертации Excel:\n\n{error_msg}"
            )

        except Exception as e:
            logger.exception(f"Error in Excel error handler: {e}")

    def on_tb_conversion_finished(self, success: bool, message: str):
        self.is_converting = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.add_files_btn.setEnabled(True)
        self.add_excel_btn.setEnabled(True)
        self.split_sdlxliff_btn.setEnabled(True)
        self.merge_sdlxliff_btn.setEnabled(True)

        if success:
            self.progress_widget.set_completion_status(True, "TB конвертация завершена!")
            self.log_message(f"✅ {message}")
        else:
            self.progress_widget.set_completion_status(False, "Ошибка TB конвертации")
            self.log_message(f"❌ {message}")
            QMessageBox.warning(self, "Ошибка конвертации", message)

    def on_tb_conversion_error(self, message: str):
        self.on_tb_conversion_finished(False, message)

    def closeEvent(self, event):
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
            options = ConversionOptions()

            self.manager.start_sdlxliff_split(filepath, settings, options)

            self.is_converting = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.add_files_btn.setEnabled(False)
            self.add_excel_btn.setEnabled(False)
            self.split_sdlxliff_btn.setEnabled(False)
            self.merge_sdlxliff_btn.setEnabled(False)

            self.progress_widget.reset()
            self.log_message(f"🚀 Начато разделение SDLXLIFF: {filepath.name}")

            if settings.by_word_count:
                self.log_message(f"   📝 Метод: по количеству слов ({settings.words_per_part} слов/часть)")
            else:
                self.log_message(f"   📋 Метод: на {settings.parts_count} равных частей")

        except Exception as e:
            error_msg = f"Ошибка запуска разделения SDLXLIFF: {e}"
            self.log_message(f"💥 {error_msg}")
            logger.exception(error_msg)

            QMessageBox.critical(
                self,
                "Ошибка запуска",
                f"Не удалось запустить разделение SDLXLIFF:\n\n{e}"
            )

    def start_sdlxliff_merge(self, filepaths: List[Path], settings):
        try:
            from core.base import ConversionOptions