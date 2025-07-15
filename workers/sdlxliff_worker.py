# workers/sdlxliff_worker.py

from PySide6.QtCore import QThread, Signal
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


class SdlxliffSplitWorker(QThread):
    """Worker для разделения SDLXLIFF файла в отдельном потоке"""
    
    progress = Signal(int, str)  # прогресс, сообщение
    finished = Signal(object)  # ConversionResult
    error = Signal(str)  # Строка с ошибкой
    log_written = Signal(str)  # Лог-сообщение
    
    def __init__(self, filepath: Path, settings, options):
        super().__init__()
        self.filepath = filepath
        self.settings = settings
        self.options = options
        self.should_stop = False
        
    def run(self):
        """Запускает разделение SDLXLIFF в отдельном потоке"""
        try:
            logger.info(f"SDLXLIFF split worker started: {self.filepath.name}")
            self.log_written.emit(f"🚀 Начато разделение файла: {self.filepath.name}")
            
            # Импортируем конвертер
            from core.converters.sdlxliff_converter import SdlxliffConverter
            
            # Добавляем колбэки для прогресса
            def progress_callback(progress: int, message: str):
                if not self.should_stop:
                    self.progress.emit(progress, message)
                    if progress % 20 == 0:  # Логируем каждые 20%
                        self.log_written.emit(f"📊 {message} ({progress}%)")
                        
            def should_stop_callback():
                return self.should_stop
                
            self.options.progress_callback = progress_callback
            self.options.should_stop_callback = should_stop_callback
            
            # Создаем конвертер и запускаем разделение
            converter = SdlxliffConverter()
            result = converter.split_file(self.filepath, self.settings, self.options)
            
            # Логируем результат
            if result.success:
                stats = result.stats
                self.log_written.emit(
                    f"✅ Разделение завершено! Создано {stats['parts_count']} частей"
                )
                for output_file in result.output_files:
                    self.log_written.emit(f"   📄 {output_file.name}")
            else:
                self.log_written.emit(f"❌ Ошибка разделения: {', '.join(result.errors)}")
            
            # Эмитим результат
            self.finished.emit(result)
            
            logger.info(f"SDLXLIFF split worker finished: {self.filepath.name}, success={result.success}")
            
        except Exception as e:
            error_msg = f"SDLXLIFF split worker error: {e}"
            logger.exception(error_msg)
            self.log_written.emit(f"💥 Критическая ошибка: {e}")
            self.error.emit(str(e))
            
    def stop(self):
        """Останавливает разделение"""
        self.should_stop = True
        logger.info(f"SDLXLIFF split worker stop requested: {self.filepath.name}")


class SdlxliffMergeWorker(QThread):
    """Worker для объединения SDLXLIFF файлов в отдельном потоке"""
    
    progress = Signal(int, str)  # прогресс, сообщение
    finished = Signal(object)  # ConversionResult
    error = Signal(str)  # Строка с ошибкой
    log_written = Signal(str)  # Лог-сообщение
    
    def __init__(self, filepaths: List[Path], settings, options):
        super().__init__()
        self.filepaths = filepaths
        self.settings = settings
        self.options = options
        self.should_stop = False
        
    def run(self):
        """Запускает объединение SDLXLIFF в отдельном потоке"""
        try:
            logger.info(f"SDLXLIFF merge worker started: {len(self.filepaths)} files")
            self.log_written.emit(f"🚀 Начато объединение {len(self.filepaths)} файлов")
            
            # Логируем файлы
            for i, filepath in enumerate(self.filepaths, 1):
                self.log_written.emit(f"   {i}. {filepath.name}")
            
            # Импортируем конвертер
            from core.converters.sdlxliff_converter import SdlxliffConverter
            
            # Добавляем колбэки для прогресса
            def progress_callback(progress: int, message: str):
                if not self.should_stop:
                    self.progress.emit(progress, message)
                    if progress % 20 == 0:  # Логируем каждые 20%
                        self.log_written.emit(f"📊 {message} ({progress}%)")
                        
            def should_stop_callback():
                return self.should_stop
                
            self.options.progress_callback = progress_callback
            self.options.should_stop_callback = should_stop_callback
            
            # Создаем конвертер и запускаем объединение
            converter = SdlxliffConverter()
            result = converter.merge_files(self.filepaths, self.settings, self.options)
            
            # Логируем результат
            if result.success:
                stats = result.stats
                output_file = result.output_files[0] if result.output_files else None
                self.log_written.emit(
                    f"✅ Объединение завершено! Создан файл: {output_file.name if output_file else 'unknown'}"
                )
                self.log_written.emit(
                    f"   📊 Всего сегментов: {stats.get('total_segments', 0)}"
                )
                self.log_written.emit(
                    f"   💾 Размер файла: {stats.get('output_size_mb', 0):.1f} MB"
                )
            else:
                self.log_written.emit(f"❌ Ошибка объединения: {', '.join(result.errors)}")
            
            # Эмитим результат
            self.finished.emit(result)
            
            logger.info(f"SDLXLIFF merge worker finished: success={result.success}")
            
        except Exception as e:
            error_msg = f"SDLXLIFF merge worker error: {e}"
            logger.exception(error_msg)
            self.log_written.emit(f"💥 Критическая ошибка: {e}")
            self.error.emit(str(e))
            
    def stop(self):
        """Останавливает объединение"""
        self.should_stop = True
        logger.info("SDLXLIFF merge worker stop requested")