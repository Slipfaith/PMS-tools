# workers/conversion_worker.py

from PySide6.QtCore import QObject, Signal, QTimer
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


class ConversionWorker(QObject):
    """Worker для конвертации файлов в фоновом режиме"""

    # Сигналы
    progress_changed = Signal(int, str)  # progress, message
    file_completed = Signal(Path, object)  # filepath, result
    all_completed = Signal(list)  # List results
    error_occurred = Signal(str)  # error message

    def __init__(self):
        super().__init__()
        self.should_stop = False
        self.converters = {}
        self._init_converters()

        # Таймер для обновления UI
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._emit_progress_update)
        self.current_progress = 0
        self.current_message = ""

    def _init_converters(self):
        """Инициализирует доступные конвертеры"""
        try:
            from core.converters.sdltm import SdltmConverter
            self.converters['sdltm'] = SdltmConverter()
            logger.info("SDLTM converter loaded")
        except ImportError as e:
            logger.warning(f"Failed to load SDLTM converter: {e}")

    def convert_files(self, filepaths: List[Path], options):
        """Конвертирует список файлов"""
        try:
            self.should_stop = False
            results = []
            total_files = len(filepaths)

            logger.info(f"Starting conversion of {total_files} files")
            self.progress_timer.start(100)  # Обновляем UI каждые 100мс

            for i, filepath in enumerate(filepaths):
                if self.should_stop:
                    logger.info("Conversion stopped by user")
                    break

                # Обновляем общий прогресс
                file_progress = int((i / total_files) * 100)
                self._update_progress(file_progress, f"Processing {filepath.name}...")

                # Определяем конвертер
                converter = self._get_converter(filepath)
                if not converter:
                    error_msg = f"Unsupported format: {filepath}"
                    logger.error(error_msg)
                    result = type('ConversionResult', (), {
                        'success': False,
                        'output_files': [],
                        'stats': {"error": error_msg},
                        'errors': [error_msg]
                    })()
                    results.append(result)
                    self.file_completed.emit(filepath, result)
                    continue

                # Создаем копию опций с колбэками для текущего файла
                file_options = type('ConversionOptions', (), {
                    'export_tmx': options.export_tmx,
                    'export_xlsx': options.export_xlsx,
                    'export_json': getattr(options, 'export_json', False),
                    'source_lang': options.source_lang,
                    'target_lang': options.target_lang,
                    'batch_size': getattr(options, 'batch_size', 1000),
                    'progress_callback': self._file_progress_callback,
                    'should_stop_callback': lambda: self.should_stop
                })()

                # Конвертируем файл
                try:
                    result = converter.convert(filepath, file_options)
                    results.append(result)
                    self.file_completed.emit(filepath, result)

                    if result.success:
                        logger.info(f"Successfully converted {filepath}")
                    else:
                        logger.error(f"Failed to convert {filepath}: {result.errors}")

                except Exception as e:
                    error_msg = f"Unexpected error converting {filepath}: {e}"
                    logger.exception(error_msg)
                    result = type('ConversionResult', (), {
                        'success': False,
                        'output_files': [],
                        'stats': {"error": str(e)},
                        'errors': [str(e)]
                    })()
                    results.append(result)
                    self.file_completed.emit(filepath, result)

            self.progress_timer.stop()
            self._update_progress(100, "All conversions completed!")
            self.all_completed.emit(results)

            # Статистика
            successful = sum(1 for r in results if r.success)
            logger.info(f"Conversion batch completed: {successful}/{len(results)} successful")

        except Exception as e:
            self.progress_timer.stop()
            error_msg = f"Fatal error during conversion: {e}"
            logger.exception(error_msg)
            self.error_occurred.emit(error_msg)

    def stop_conversion(self):
        """Останавливает конвертацию"""
        self.should_stop = True
        logger.info("Conversion stop requested")

    def _get_converter(self, filepath: Path):
        """Определяет подходящий конвертер для файла"""
        for format_name, converter in self.converters.items():
            if converter.can_handle(filepath):
                return converter
        return None

    def _file_progress_callback(self, progress: int, message: str):
        """Колбэк прогресса для отдельного файла"""
        self.current_message = message
        # Прогресс файла не обновляем общий прогресс напрямую

    def _update_progress(self, progress: int, message: str):
        """Обновляет текущий прогресс"""
        self.current_progress = progress
        self.current_message = message

    def _emit_progress_update(self):
        """Эмитит обновление прогресса для UI"""
        self.progress_changed.emit(self.current_progress, self.current_message)


class BatchConversionWorker(QObject):
    """Worker для пакетной конвертации с более детальным контролем"""

    progress_changed = Signal(int, str, int, int)  # overall_progress, message, current_file, total_files
    file_started = Signal(Path)  # filepath
    file_completed = Signal(Path, object)  # filepath, result
    batch_completed = Signal(list)  # List results
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.should_stop = False
        self.conversion_worker = ConversionWorker()

        # Подключаем сигналы
        self.conversion_worker.progress_changed.connect(self._on_progress_changed)
        self.conversion_worker.file_completed.connect(self._on_file_completed)
        self.conversion_worker.all_completed.connect(self._on_batch_completed)
        self.conversion_worker.error_occurred.connect(self._on_error)

        self.current_file_index = 0
        self.total_files = 0

    def convert_batch(self, filepaths: List[Path], options):
        """Запускает пакетную конвертацию"""
        self.current_file_index = 0
        self.total_files = len(filepaths)
        self.should_stop = False

        # Передаем опции как есть
        self.conversion_worker.convert_files(filepaths, options)

    def stop_batch(self):
        """Останавливает пакетную конвертацию"""
        self.should_stop = True
        self.conversion_worker.stop_conversion()

    def _on_progress_changed(self, progress: int, message: str):
        """Обработчик прогресса отдельного файла"""
        self.progress_changed.emit(
            progress, message, self.current_file_index, self.total_files
        )

    def _on_file_completed(self, filepath: Path, result):
        """Обработчик завершения файла"""
        self.current_file_index += 1
        self.file_completed.emit(filepath, result)

    def _on_batch_completed(self, results: list):
        """Обработчик завершения всей пакетной конвертации"""
        self.batch_completed.emit(results)

    def _on_error(self, error_msg: str):
        """Обработчик ошибок"""
        self.error_occurred.emit(error_msg)