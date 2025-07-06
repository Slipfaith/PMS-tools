# gui/windows/main_window.py - ОБНОВЛЕННАЯ ВЕРСИЯ

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QFileDialog, QMessageBox,
    QGroupBox, QCheckBox, QSplitter, QFrame, QLineEdit
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """ОБНОВЛЕНО: Главное окно с контроллером, БЕЗ прямой бизнес-логики"""

    def __init__(self):
        super().__init__()

        # НОВОЕ: Создаем контроллер
        from controller import MainController
        self.controller = MainController()

        self.setup_window()
        self.setup_ui()
        self.setup_worker()
        self.setup_connections()

        # Состояние конвертации
        self.is_converting = False
        self.current_batch_results = []

        logger.info("Main window initialized with controller")

    def setup_window(self):
        """Настройка основного окна"""
        self.setWindowTitle("Converter Pro v2.0 - TM/TB/TMX Converter")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

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
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a90e2, stop:1 #357abd);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        header_layout = QHBoxLayout(header_frame)

        # Заголовок
        title_label = QLabel("Converter Pro v2.0")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 24px;
                font-weight: bold;
                background: transparent;
            }
        """)
        header_layout.addWidget(title_label)

        # Описание
        desc_label = QLabel("Professional TM/TB/TMX Converter")
        desc_label.setStyleSheet("""
            QLabel {
                color: #e8f4fd;
                font-size: 14px;
                background: transparent;
            }
        """)
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
        # НОВОЕ: Подключаем к контроллеру вместо прямой обработки
        self.drop_area.files_dropped.connect(self.on_files_dropped)
        self.drop_area.files_dragged.connect(self.on_files_dragged)  # Для проверки при перетаскивании
        layout.addWidget(self.drop_area)

        # Кнопки управления файлами
        file_buttons = QHBoxLayout()

        self.add_files_btn = QPushButton("Добавить файлы")
        self.add_files_btn.clicked.connect(self.open_file_dialog)
        file_buttons.addWidget(self.add_files_btn)

        self.clear_files_btn = QPushButton("Очистить")
        self.clear_files_btn.clicked.connect(self.clear_files)
        file_buttons.addWidget(self.clear_files_btn)

        file_buttons.addStretch()
        layout.addLayout(file_buttons)

        # Список файлов
        from gui.widgets.file_list import FileListWidget
        self.file_list = FileListWidget()
        # НОВОЕ: Подключаем к контроллеру
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
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #45a049;
            }
            QPushButton:disabled {
                background: #cccccc;
                color: #666666;
            }
        """)
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setEnabled(False)
        action_buttons.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #f44336;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #da190b;
            }
            QPushButton:disabled {
                background: #cccccc;
                color: #666666;
            }
        """)
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

        # Результаты
        results_group = QGroupBox("Результаты")
        results_layout = QVBoxLayout(results_group)

        self.results_text = QTextEdit()
        self.results_text.setFont(QFont("Consolas", 9))
        self.results_text.setMaximumHeight(150)
        results_layout.addWidget(self.results_text)

        layout.addWidget(results_group)
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
        """Настраивает worker для конвертации"""
        from workers.conversion_worker import BatchConversionWorker

        # Создаем worker и поток
        self.worker = BatchConversionWorker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        # Подключение сигналов прогресса
        self.worker.progress_changed.connect(self.on_progress_update)
        self.worker.file_started.connect(self.on_file_started)
        self.worker.file_completed.connect(self.on_file_completed)
        self.worker.batch_completed.connect(self.on_batch_completed)
        self.worker.error_occurred.connect(self.on_conversion_error)

        # Запускаем поток
        self.worker_thread.start()

        logger.info("Worker thread started and signals connected")

    def setup_connections(self):
        """Настраивает дополнительные соединения сигналов"""
        self.file_list.files_changed.connect(self.on_files_changed)

    def setup_status_bar(self):
        """Настраивает статус бар"""
        self.status_label = QLabel("Готов к работе")
        self.statusBar().addWidget(self.status_label)

        # Индикатор версии
        version_label = QLabel("v2.0")
        version_label.setStyleSheet("color: #666; font-size: 10px;")
        self.statusBar().addPermanentWidget(version_label)

    # НОВЫЕ методы для работы с контроллером

    def on_files_dropped(self, filepaths: List[str]):
        """НОВОЕ: Обработчик добавления файлов через контроллер"""
        files_info = self.controller.add_files(filepaths)

        if files_info:
            self.file_list.update_files(files_info)
            self.log_message(f"Добавлено файлов: {len(files_info)}")
        else:
            self.log_message("Не найдено поддерживаемых файлов")

    def on_files_dragged(self, filepaths: List[str]):
        """НОВОЕ: Обработчик проверки файлов при перетаскивании"""
        format_name, valid_files = self.controller.detect_drop_files(filepaths)
        is_valid = len(valid_files) > 0
        self.drop_area.set_format_info(format_name, is_valid)

    def on_file_remove_requested(self, filepath: Path):
        """НОВОЕ: Обработчик удаления файла через контроллер"""
        if self.controller.remove_file(filepath):
            # Обновляем отображение - получаем все файлы заново
            self._refresh_file_list()
            self.log_message(f"Удален файл: {filepath.name}")

    def open_file_dialog(self):
        """ОБНОВЛЕНО: Открывает диалог выбора файлов через контроллер"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для конвертации",
            "",
            "Все поддерживаемые (*.sdltm *.xlsx *.xls);;SDLTM (*.sdltm);;Excel (*.xlsx *.xls)"
        )

        if files:
            self.on_files_dropped(files)

    def clear_files(self):
        """ОБНОВЛЕНО: Очищает список файлов через контроллер"""
        self.controller.clear_files()
        self.file_list.clear()
        self.progress_widget.reset()
        self.results_text.clear()
        self.log_message("Список файлов очищен")

    def start_conversion(self):
        """ОБНОВЛЕНО: Запускает конвертацию через контроллер"""
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
        # Добавляем языки для каждого файла
        options.file_languages = self.file_list.get_all_languages()
        files = self.controller.get_files_for_conversion()

        # Переключаем UI в режим конвертации
        self.is_converting = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.add_files_btn.setEnabled(False)

        # Очищаем предыдущие результаты
        self.results_text.clear()
        self.progress_widget.reset()
        self.file_list.reset_all_status()

        # Запускаем конвертацию через worker
        self.worker.convert_batch(files, options)
        self.log_message(f"🚀 Начата конвертация {len(files)} файлов")

    def _refresh_file_list(self):
        """Обновляет отображение списка файлов"""
        # Создаем файловую информацию для всех текущих файлов
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

    # Остальные методы без изменений (обработчики worker'а и UI)

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
            output_info = "\n".join([f"  📄 {f.name}" for f in result.output_files])
            result_text = f"""
📁 {filepath.name}:
{output_info}
📊 Статистика:
  • Экспортировано: {stats.get('exported', 0):,}
  • Всего в SDLTM: {stats.get('total_in_sdltm', stats.get('total', 0)):,}
  • Пропущено пустых: {stats.get('skipped_empty', 0):,}
  • Пропущено дублей: {stats.get('skipped_duplicates', 0):,}
  • Время: {stats.get('conversion_time', 0):.1f}с
"""
            self.results_text.append(result_text)
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

        # Финальный статус в progress_widget
        if successful == total:
            self.progress_widget.set_completion_status(True, f"Все файлы успешно конвертированы!")
        else:
            self.progress_widget.set_completion_status(False, f"Конвертировано {successful} из {total} файлов")

        # Итоговое сообщение
        self.log_message(f"🎉 Конвертация завершена: {successful}/{total} успешно")

        # Показываем диалог с результатами
        if successful > 0:
            QMessageBox.information(
                self,
                "Конвертация завершена",
                f"Успешно конвертировано: {successful} из {total} файлов\n\n"
                f"Результаты смотрите в панели справа."
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

    def stop_conversion(self):
        """Останавливает конвертацию"""
        self.is_converting = False
        self.worker.stop_batch()
        self.log_message("🛑 Запрошена остановка конвертации...")

    def on_files_changed(self, file_count: int):
        """Обработчик изменения списка файлов"""
        self.start_btn.setEnabled(file_count > 0 and not self.is_converting)
        self.status_label.setText(f"Файлов в очереди: {file_count}")

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

    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        # Останавливаем конвертацию если она идет
        if self.is_converting:
            self.stop_conversion()

        # Останавливаем worker thread
        if hasattr(self, 'worker_thread'):
            self.worker_thread.quit()
            self.worker_thread.wait(3000)  # Ждем до 3 секунд

        event.accept()
        logger.info("Main window closed")