# gui/windows/main_window.py

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
    """Главное окно приложения с исправленными соединениями сигналов"""

    def __init__(self):
        super().__init__()
        self.setup_window()
        self.setup_ui()
        self.setup_worker()
        self.setup_connections()

        # Список файлов для конвертации
        self.file_paths: List[Path] = []

        # Состояние конвертации
        self.is_converting = False
        self.current_batch_results = []

        logger.info("Main window initialized")

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
        self.drop_area.files_dropped.connect(self.add_files)
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
        """Настраивает worker для конвертации с правильными соединениями"""
        from workers.conversion_worker import BatchConversionWorker

        # Создаем worker и поток
        self.worker = BatchConversionWorker()
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        # ИСПРАВЛЕНО: Правильное подключение сигналов прогресса
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

    # ИСПРАВЛЕННЫЕ методы обработки сигналов

    def on_progress_update(self, progress: int, message: str, current_file: int, total_files: int):
        """ИСПРАВЛЕНО: Обработчик обновления прогресса"""
        logger.debug(f"Progress update: {progress}% - {message} ({current_file}/{total_files})")

        # Обновляем прогресс-виджет
        self.progress_widget.update_progress(progress, message, current_file, total_files)

        # Обновляем статус бар
        if total_files > 0:
            self.status_label.setText(f"Обработка файла {current_file}/{total_files}: {message}")
        else:
            self.status_label.setText(message)

    def on_file_started(self, filepath: Path):
        """ИСПРАВЛЕНО: Обработчик начала конвертации файла"""
        logger.info(f"File started: {filepath.name}")
        self.log_message(f"Начата обработка: {filepath.name}")

        # Обновляем прогресс для конкретного файла
        file_item = self.file_list.get_file_item(filepath)
        if file_item:
            file_item.set_conversion_progress(0, "Начинаем обработку...")

    def on_file_completed(self, filepath: Path, result):
        """ИСПРАВЛЕНО: Обработчик завершения конвертации файла"""
        logger.info(f"File completed: {filepath.name}, success: {result.success}")

        # Обновляем статистику в progress_widget
        self.progress_widget.on_file_completed(result.success)

        # Обновляем файл в списке
        file_item = self.file_list.get_file_item(filepath)
        if file_item:
            if result.success:
                stats = result.stats
                exported_count = stats.get('exported', 0)
                file_item.set_conversion_completed(True, f"Экспортировано: {exported_count}")
            else:
                error_msg = '; '.join(result.errors) if result.errors else "Неизвестная ошибка"
                file_item.set_conversion_completed(False, error_msg)

        # Логируем результат
        if result.success:
            self.log_message(f"✅ Завершено: {filepath.name}")

            # Показываем результаты
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
        """ИСПРАВЛЕНО: Обработчик завершения всей пакетной конвертации"""
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
        """ИСПРАВЛЕНО: Обработчик критических ошибок конвертации"""
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

    # Методы обработки событий

    def add_files(self, filepaths: List[str]):
        """Добавляет файлы в список"""
        new_paths = [Path(fp) for fp in filepaths if Path(fp).exists()]

        for path in new_paths:
            if path not in self.file_paths:
                self.file_paths.append(path)

        self.file_list.update_files(self.file_paths)
        self.log_message(f"Добавлено файлов: {len(new_paths)}")

        # Автоопределение языков из первого SDLTM файла
        self._auto_detect_languages()

    def open_file_dialog(self):
        """Открывает диалог выбора файлов"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы для конвертации",
            "",
            "Все поддерживаемые (*.sdltm *.xlsx *.xls);;SDLTM (*.sdltm);;Excel (*.xlsx *.xls)"
        )

        if files:
            self.add_files(files)

    def clear_files(self):
        """Очищает список файлов"""
        self.file_paths.clear()
        self.file_list.clear()
        self.progress_widget.reset()
        self.results_text.clear()
        self.log_message("Список файлов очищен")

        # Сбрасываем автоопределенные языки
        self.auto_langs_label.setText("Будут определены из файла")

    def _auto_detect_languages(self):
        """Автоматически определяет языки из SDLTM файлов"""
        sdltm_files = [f for f in self.file_paths if f.suffix.lower() == '.sdltm']
        if not sdltm_files:
            return

        try:
            import sqlite3
            import xml.etree.ElementTree as ET

            # Берем первый SDLTM файл для анализа
            sdltm_path = sdltm_files[0]

            with sqlite3.connect(str(sdltm_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT source_segment, target_segment FROM translation_units LIMIT 10")

                src_lang = "unknown"
                tgt_lang = "unknown"

                for src_xml, tgt_xml in cursor.fetchall():
                    try:
                        # Парсим source
                        if src_lang == "unknown":
                            root = ET.fromstring(src_xml)
                            lang_elem = root.find(".//CultureName")
                            if lang_elem is not None and lang_elem.text:
                                src_lang = self._normalize_language(lang_elem.text)

                        # Парсим target
                        if tgt_lang == "unknown":
                            root = ET.fromstring(tgt_xml)
                            lang_elem = root.find(".//CultureName")
                            if lang_elem is not None and lang_elem.text:
                                tgt_lang = self._normalize_language(lang_elem.text)

                        # Если нашли оба языка, прекращаем поиск
                        if src_lang != "unknown" and tgt_lang != "unknown":
                            break

                    except Exception:
                        continue

                if src_lang != "unknown" or tgt_lang != "unknown":
                    lang_text = f"{src_lang} → {tgt_lang}"
                    self.auto_langs_label.setText(lang_text)
                    self.auto_langs_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
                    self.log_message(f"Автоопределены языки: {lang_text}")

        except Exception as e:
            self.log_message(f"Ошибка автоопределения языков: {e}")

    def _normalize_language(self, lang_code: str) -> str:
        """Нормализует языковой код"""
        if not lang_code:
            return "unknown"

        # Стандартные замены
        lang_map = {
            "en": "en-US", "de": "de-DE", "fr": "fr-FR", "it": "it-IT",
            "es": "es-ES", "pt": "pt-PT", "ru": "ru-RU", "ja": "ja-JP",
            "ko": "ko-KR", "zh": "zh-CN", "pl": "pl-PL", "tr": "tr-TR"
        }

        code = lang_code.lower().replace("_", "-")

        # Если уже полный код
        if "-" in code and len(code) == 5:
            return code

        # Добавляем регион по умолчанию
        return lang_map.get(code, f"{code}-XX")

    def on_files_changed(self, file_count: int):
        """Обработчик изменения списка файлов"""
        self.start_btn.setEnabled(file_count > 0 and not self.is_converting)
        self.status_label.setText(f"Файлов в очереди: {file_count}")

    def start_conversion(self):
        """ИСПРАВЛЕНО: Запускает конвертацию с правильными опциями"""
        if not self.file_paths:
            QMessageBox.warning(self, "Ошибка", "Нет файлов для конвертации")
            return

        # Проверяем, что выбран хотя бы один формат экспорта
        if not (self.tmx_cb.isChecked() or self.xlsx_cb.isChecked() or self.json_cb.isChecked()):
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы один формат экспорта")
            return

        # Создаем правильные опции конвертации
        from core.base import ConversionOptions

        src_lang = self.src_lang_edit.text().strip() or "auto"
        tgt_lang = self.tgt_lang_edit.text().strip() or "auto"

        options = ConversionOptions(
            export_tmx=self.tmx_cb.isChecked(),
            export_xlsx=self.xlsx_cb.isChecked(),
            export_json=self.json_cb.isChecked(),
            source_lang=src_lang,
            target_lang=tgt_lang,
            batch_size=1000,
            # ИСПРАВЛЕНО: Передаем колбэки для обновления UI
            progress_callback=None,  # Не используем прямые колбэки, используем сигналы
            should_stop_callback=lambda: not self.is_converting
        )

        # Переключаем UI в режим конвертации
        self.is_converting = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.add_files_btn.setEnabled(False)

        # Очищаем предыдущие результаты
        self.results_text.clear()
        self.progress_widget.reset()
        self.file_list.reset_all_status()

        # ИСПРАВЛЕНО: Запускаем конвертацию через сигналы Qt
        self.worker.convert_batch(self.file_paths.copy(), options)
        self.log_message(f"🚀 Начата конвертация {len(self.file_paths)} файлов")

    def stop_conversion(self):
        """Останавливает конвертацию"""
        self.is_converting = False
        self.worker.stop_batch()
        self.log_message("🛑 Запрошена остановка конвертации...")

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