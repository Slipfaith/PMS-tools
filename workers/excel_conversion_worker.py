# workers/excel_conversion_worker.py

from PySide6.QtCore import QThread, Signal
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ExcelConversionWorker(QThread):
    """Worker для конвертации Excel файлов в отдельном потоке"""

    finished = Signal(object)  # ConversionResult
    error = Signal(str)  # Строка с ошибкой

    def __init__(self, filepath: Path, settings, options):
        super().__init__()
        self.filepath = filepath
        self.settings = settings
        self.options = options
        self.should_stop = False

    def run(self):
        """Запускает конвертацию Excel в отдельном потоке"""
        try:
            logger.info(f"Excel worker started: {self.filepath.name}")

            # Импортируем конвертер
            from core.converters.excel_converter import ExcelConverter

            # Создаем конвертер и запускаем конвертацию
            converter = ExcelConverter()
            result = converter.convert_excel_to_tmx(self.filepath, self.settings, self.options)

            # Эмитим результат
            self.finished.emit(result)

            logger.info(f"Excel worker finished: {self.filepath.name}, success={result.success}")

        except Exception as e:
            error_msg = f"Excel worker error: {e}"
            logger.exception(error_msg)
            self.error.emit(error_msg)

    def stop(self):
        """Останавливает конвертацию"""
        self.should_stop = True
        logger.info(f"Excel worker stop requested: {self.filepath.name}")