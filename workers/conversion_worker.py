# workers/conversion_worker.py - ОКОНЧАТЕЛЬНО ИСПРАВЛЕННАЯ ВЕРСИЯ

from PySide6.QtCore import QObject, Signal, QTimer, QMutex, QMutexLocker
from pathlib import Path
from typing import List, Optional
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class ConversionWorker(QObject):
    """ИСПРАВЛЕНО: Worker с динамическим прогрессом"""

    # Сигналы
    progress_changed = Signal(int, str)
    file_started = Signal(Path)
    file_completed = Signal(Path, object)
    all_completed = Signal(list)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.should_stop = False
        self.converters = {}
        self.mutex = QMutex()
        self._init_converters()

        # Прогресс-таймер для плавного обновления
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._emit_progress_update)
        self.progress_timer.setInterval(200)  # Обновляем каждые 200мс

        # Текущий прогресс
        self.current_progress = 0
        self.current_message = ""
        self.current_file_index = 0
        self.total_files = 0
        self.file_start_time = None
        self.file_segments = {}
        self.total_segments = 0
        self.processed_segments = 0

    def _init_converters(self):
        """Инициализирует конвертеры"""
        try:
            from core.converters.sdltm import SdltmConverter
            self.converters['sdltm'] = SdltmConverter()
            logger.info("SDLTM converter loaded")
        except ImportError as e:
            logger.warning(f"Failed to load SDLTM converter: {e}")

    def convert_files(self, filepaths: List[Path], options, file_languages=None,
                      file_segments: Optional[dict] = None, total_segments: Optional[int] = None):
        """Конвертация с динамическим прогрессом"""
        with QMutexLocker(self.mutex):
            self.should_stop = False
            self.total_files = len(filepaths)
            self.current_file_index = 0
            self.file_segments = file_segments or {}
            self.total_segments = total_segments or self.total_files
            self.processed_segments = 0

        results = []

        try:
            logger.info(f"Starting conversion of {self.total_files} files")

            # Запускаем таймер прогресса
            self.progress_timer.start()

            # Начальный прогресс
            self._update_progress(0, f"Начинаем конвертацию {self.total_files} файлов...")

            for i, filepath in enumerate(filepaths):
                with QMutexLocker(self.mutex):
                    if self.should_stop:
                        logger.info("Conversion stopped by user")
                        break

                    self.current_file_index = i + 1
                    self.file_start_time = time.time()

                # Эмитим сигнал о начале файла
                self.file_started.emit(filepath)
                logger.info(f"Starting file {i + 1}/{self.total_files}: {filepath.name}")

                # Определяем конвертер
                converter = self._get_converter(filepath)
                if not converter:
                    error_msg = f"Неподдерживаемый формат: {filepath.suffix}"
                    logger.error(error_msg)

                    result = self._create_error_result(filepath, error_msg)
                    results.append(result)
                    self.file_completed.emit(filepath, result)
                    continue

                # Прогресс для текущего файла
                base_segments = self.processed_segments
                file_total = self.file_segments.get(filepath, 0)
                if self.total_segments:
                    base_progress = int((base_segments / self.total_segments) * 100)
                else:
                    base_progress = int((i / self.total_files) * 100)
                self._update_progress(base_progress, f"Обрабатывается: {filepath.name}")

                # Создаем опции с колбэками
                file_options = self._create_file_options(options, filepath, i, file_languages)

                # Конвертируем файл
                try:
                    result = converter.convert(filepath, file_options)
                    results.append(result)

                    self.processed_segments += file_total
                    if self.total_segments:
                        file_complete_progress = int((self.processed_segments / self.total_segments) * 100)
                    else:
                        file_complete_progress = int(((i + 1) / self.total_files) * 100)

                    if result.success:
                        self._update_progress(file_complete_progress, f"✅ Завершен: {filepath.name}")
                    else:
                        self._update_progress(file_complete_progress, f"❌ Ошибка: {filepath.name}")

                    self.file_completed.emit(filepath, result)

                    if result.success:
                        logger.info(f"Successfully converted {filepath.name}")
                    else:
                        logger.error(f"Failed to convert {filepath.name}: {result.errors}")

                except Exception as e:
                    error_msg = f"Неожиданная ошибка: {e}"
                    logger.exception(error_msg)

                    result = self._create_error_result(filepath, str(e))
                    results.append(result)
                    self.processed_segments += file_total
                    if self.total_segments:
                        file_complete_progress = int((self.processed_segments / self.total_segments) * 100)
                    else:
                        file_complete_progress = int(((i + 1) / self.total_files) * 100)
                    self._update_progress(file_complete_progress, f"❌ Ошибка: {filepath.name}")
                    self.file_completed.emit(filepath, result)

            # Останавливаем таймер
            self.progress_timer.stop()

            # ИСПРАВЛЕНО: Обязательно показываем 100%
            self._update_progress(100, "Конвертация завершена!")

            # Небольшая задержка перед финальным сигналом
            time.sleep(0.1)

            # Эмитим финальный сигнал
            self.all_completed.emit(results)

            successful = sum(1 for r in results if r.success)
            logger.info(f"Conversion batch completed: {successful}/{len(results)} successful")

        except Exception as e:
            self.progress_timer.stop()
            error_msg = f"Критическая ошибка: {e}"
            logger.exception(error_msg)
            self.error_occurred.emit(error_msg)

    def stop_conversion(self):
        """Останавливает конвертацию"""
        with QMutexLocker(self.mutex):
            self.should_stop = True
        logger.info("Conversion stop requested")

    def _get_converter(self, filepath: Path):
        """Определяет конвертер для файла"""
        suffix = filepath.suffix.lower()

        if suffix == '.sdltm' and 'sdltm' in self.converters:
            return self.converters['sdltm']

        for converter in self.converters.values():
            if converter.can_handle(filepath):
                return converter

        return None

    def _create_file_options(self, original_options, filepath: Path, file_index: int, file_languages=None):
        """ИСПРАВЛЕНО: Создает опции с прогресс-колбэками"""
        from core.base import ConversionOptions

        def file_progress_callback(progress: int, message: str):
            """Колбэк прогресса для файла с учетом сегментов"""
            file_total = self.file_segments.get(filepath, 0)
            base_segments = self.processed_segments

            if self.total_segments:
                base_progress = (base_segments / self.total_segments) * 100
                file_contrib = (progress / 100) * (file_total / self.total_segments) * 100
                total_progress = int(min(99, base_progress + file_contrib))
            else:
                base_progress = int((file_index / self.total_files) * 100)
                file_progress_weight = int((1 / self.total_files) * 100)
                file_contrib = int((progress / 100) * file_progress_weight)
                total_progress = min(99, base_progress + file_contrib)

            self._update_progress(total_progress, f"{filepath.name}: {message}")

        def should_stop_callback():
            with QMutexLocker(self.mutex):
                return self.should_stop

        src_lang = original_options.source_lang
        tgt_lang = original_options.target_lang
        if file_languages and filepath in file_languages:
            langs = file_languages[filepath]
            src_lang = langs.get('source', src_lang)
            tgt_lang = langs.get('target', tgt_lang)

        return ConversionOptions(
            export_tmx=original_options.export_tmx,
            export_xlsx=original_options.export_xlsx,
            export_json=getattr(original_options, 'export_json', False),
            source_lang=src_lang,
            target_lang=tgt_lang,
            batch_size=getattr(original_options, 'batch_size', 1000),
            progress_callback=file_progress_callback,
            should_stop_callback=should_stop_callback
        )

    def _create_error_result(self, filepath: Path, error_msg: str):
        """Создает результат с ошибкой"""
        from core.base import ConversionResult, ConversionStatus

        return ConversionResult(
            success=False,
            output_files=[],
            stats={"error": error_msg},
            errors=[error_msg],
            status=ConversionStatus.FAILED
        )

    def _update_progress(self, progress: int, message: str):
        """Обновляет прогресс"""
        with QMutexLocker(self.mutex):
            self.current_progress = progress
            self.current_message = message
            emit_progress = progress
            emit_message = message

        # Мгновенно отправляем обновление, чтобы индикатор не зависал
        self.progress_changed.emit(emit_progress, emit_message)

    def _emit_progress_update(self):
        """Эмитит обновление прогресса"""
        with QMutexLocker(self.mutex):
            progress = self.current_progress
            message = self.current_message

        self.progress_changed.emit(progress, message)


class BatchConversionWorker(QObject):
    """ИСПРАВЛЕНО: Пакетный worker с правильными сигналами"""

    # Сигналы
    progress_changed = Signal(int, str, int, int)  # progress, message, current_file, total_files
    file_started = Signal(Path)
    file_completed = Signal(Path, object)
    batch_completed = Signal(list)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.should_stop = False
        self.conversion_worker = ConversionWorker()
        self.mutex = QMutex()

        # Подключаем сигналы
        self.conversion_worker.progress_changed.connect(self._on_progress_changed)
        self.conversion_worker.file_started.connect(self._on_file_started)
        self.conversion_worker.file_completed.connect(self._on_file_completed)
        self.conversion_worker.all_completed.connect(self._on_batch_completed)
        self.conversion_worker.error_occurred.connect(self._on_error)

        # Состояние
        self.current_file_index = 0
        self.total_files = 0
        self.batch_start_time = None

    def convert_batch(self, filepaths: List[Path], options, file_languages=None):
        """Запуск пакетной конвертации с учетом сегментов"""
        with QMutexLocker(self.mutex):
            self.current_file_index = 0
            self.total_files = len(filepaths)
            self.should_stop = False
            self.batch_start_time = time.time()

        logger.info(f"Starting batch conversion of {self.total_files} files")

        file_segments = {}
        total_segments = 0
        for fp in filepaths:
            converter = self.conversion_worker._get_converter(fp)
            if converter:
                try:
                    segs = converter.get_progress_steps(fp)
                except Exception:
                    segs = 0
            else:
                segs = 0
            file_segments[fp] = segs
            total_segments += segs

        self.progress_changed.emit(0, "Подготовка к конвертации...", 0, self.total_files)

        self.conversion_worker.convert_files(filepaths, options, file_languages, file_segments, total_segments)

    def stop_batch(self):
        """Остановка пакетной конвертации"""
        with QMutexLocker(self.mutex):
            self.should_stop = True

        self.conversion_worker.stop_conversion()
        logger.info("Batch conversion stop requested")

    def _on_progress_changed(self, progress: int, message: str):
        """ИСПРАВЛЕНО: Обработка прогресса"""
        with QMutexLocker(self.mutex):
            current_file = self.current_file_index
            total_files = self.total_files

        # Эмитим детальный прогресс
        self.progress_changed.emit(progress, message, current_file, total_files)

    def _on_file_started(self, filepath: Path):
        """ИСПРАВЛЕНО: Начало файла"""
        # Увеличиваем счетчик текущего файла
        with QMutexLocker(self.mutex):
            self.current_file_index += 1
        self.file_started.emit(filepath)

    def _on_file_completed(self, filepath: Path, result):
        """ИСПРАВЛЕНО: Завершение файла"""
        self.file_completed.emit(filepath, result)

    def _on_batch_completed(self, results: list):
        """ИСПРАВЛЕНО: Завершение пакета"""
        batch_time = time.time() - self.batch_start_time if self.batch_start_time else 0

        logger.info(f"Batch conversion completed in {batch_time:.1f} seconds")

        # Финальный прогресс
        successful = sum(1 for r in results if r.success)
        final_message = f"Завершено: {successful}/{len(results)} файлов"

        with QMutexLocker(self.mutex):
            self.current_file_index = len(results)
        self.progress_changed.emit(100, final_message, len(results), len(results))

        # Эмитим сигнал завершения пакета
        self.batch_completed.emit(results)

    def _on_error(self, error_msg: str):
        """ИСПРАВЛЕНО: Обработка ошибок"""
        logger.error(f"Batch conversion error: {error_msg}")
        self.error_occurred.emit(error_msg)

    def is_running(self) -> bool:
        """Проверяет, запущена ли конвертация"""
        with QMutexLocker(self.mutex):
            return not self.should_stop

    def get_stats(self) -> dict:
        """Получает статистику конвертации"""
        with QMutexLocker(self.mutex):
            elapsed = time.time() - self.batch_start_time if self.batch_start_time else 0

            return {
                "current_file": self.current_file_index,
                "total_files": self.total_files,
                "elapsed_time": elapsed,
                "is_running": not self.should_stop
            }