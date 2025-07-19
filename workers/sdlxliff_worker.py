from PySide6.QtCore import QThread, Signal
from pathlib import Path
from typing import List
import logging
import time

from core.base import ConversionResult, ConversionStatus
from sdlxliff_split_merge import (
    StructuralSplitter,
    merge_with_original,
    SdlxliffValidator,
    make_split_filenames,
    save_bytes_list,
    load_original_and_parts,
    create_backup
)

logger = logging.getLogger(__name__)


class SdlxliffSplitWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)
    log_written = Signal(str)

    def __init__(self, filepath: Path, settings, options):
        super().__init__()
        self.filepath = filepath
        self.settings = settings
        self.options = options
        self.should_stop = False

    def run(self):
        try:
            logger.info(f"SDLXLIFF split worker started: {self.filepath.name}")
            self.log_written.emit(f"🚀 Начато разделение файла: {self.filepath.name}")

            self.progress.emit(0, "Проверка файла...")

            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            validator = SdlxliffValidator()
            is_valid, error_msg = validator.validate_for_splitting(content)
            if not is_valid:
                self._handle_error(error_msg)
                return

            self.progress.emit(20, "Анализ структуры...")

            try:
                splitter = StructuralSplitter(content)
            except Exception as e:
                self._handle_error(f"Ошибка анализа структуры: {e}")
                return

            self.progress.emit(30, "Разделение файла...")

            try:
                if self.settings.by_word_count:
                    parts_content = splitter.split_by_word_count(self.settings.words_per_part)
                    actual_parts = len(parts_content)
                else:
                    parts_content = splitter.split(self.settings.parts_count)
                    actual_parts = self.settings.parts_count
            except Exception as e:
                self._handle_error(f"Ошибка разделения: {e}")
                return

            if self.should_stop:
                self._handle_cancelled()
                return

            self.progress.emit(70, "Сохранение частей...")

            if self.settings.create_backup:
                try:
                    create_backup(self.filepath)
                except Exception as e:
                    logger.warning(f"Не удалось создать резервную копию: {e}")

            output_paths = make_split_filenames(str(self.filepath), actual_parts)

            if self.settings.output_dir:
                output_paths = [
                    str(self.settings.output_dir / Path(p).name)
                    for p in output_paths
                ]

            try:
                save_bytes_list(parts_content, output_paths)
            except Exception as e:
                self._handle_error(f"Ошибка сохранения: {e}")
                return

            self.progress.emit(90, "Проверка результатов...")

            output_files = []
            for path in output_paths:
                p = Path(path)
                if p.exists():
                    output_files.append(p)

            if len(output_files) != actual_parts:
                self._handle_error(f"Не все части сохранены: {len(output_files)} из {actual_parts}")
                return

            self.progress.emit(100, "Разделение завершено!")

            split_info = splitter.get_split_info()

            stats = {
                "operation": "split",
                "source_file": self.filepath.name,
                "source_size_mb": self.filepath.stat().st_size / (1024 * 1024),
                "parts_count": actual_parts,
                "segments_total": split_info['total_segments'],
                "words_total": split_info['total_words'],
                "by_word_count": self.settings.by_word_count,
                "words_per_part": self.settings.words_per_part if self.settings.by_word_count else None,
                "split_id": split_info['split_id'],
                "encoding": split_info['encoding']
            }

            result = ConversionResult(
                success=True,
                output_files=output_files,
                stats=stats,
                status=ConversionStatus.COMPLETED
            )

            self.log_written.emit(f"✅ Разделение завершено! Создано {actual_parts} частей")
            for output_file in output_files:
                self.log_written.emit(f"   📄 {output_file.name}")

            self.finished.emit(result)
            logger.info(f"SDLXLIFF split worker finished: {self.filepath.name}")

        except Exception as e:
            self._handle_error(str(e))

    def _handle_error(self, error_msg: str):
        logger.error(error_msg)
        self.log_written.emit(f"❌ Ошибка: {error_msg}")
        result = ConversionResult(
            success=False,
            output_files=[],
            stats={"error": error_msg},
            errors=[error_msg],
            status=ConversionStatus.FAILED
        )
        self.finished.emit(result)
        self.error.emit(error_msg)

    def _handle_cancelled(self):
        result = ConversionResult(
            success=False,
            output_files=[],
            stats={"cancelled": True},
            errors=["Cancelled by user"],
            status=ConversionStatus.CANCELLED
        )
        self.finished.emit(result)

    def stop(self):
        self.should_stop = True
        logger.info(f"SDLXLIFF split worker stop requested: {self.filepath.name}")


class SdlxliffMergeWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)
    log_written = Signal(str)

    def __init__(self, filepaths: List[Path], settings, options):
        super().__init__()
        self.filepaths = filepaths
        self.settings = settings
        self.options = options
        self.should_stop = False

    def run(self):
        try:
            logger.info(f"SDLXLIFF merge worker started: {len(self.filepaths)} files")
            self.log_written.emit(f"🚀 Начато объединение {len(self.filepaths)} файлов")

            for i, filepath in enumerate(self.filepaths, 1):
                self.log_written.emit(f"   {i}. {filepath.name}")

            self.progress.emit(0, "Проверка файлов...")

            for filepath in self.filepaths:
                if not filepath.exists():
                    self._handle_error(f"Файл не найден: {filepath}")
                    return

            self.progress.emit(10, "Определение оригинала и частей...")

            try:
                original_content, parts_content = load_original_and_parts([str(fp) for fp in self.filepaths])
            except ValueError as e:
                self._handle_error(str(e))
                return

            self.progress.emit(30, f"Найден оригинал и {len(parts_content)} частей")

            if self.settings.validate_parts:
                validator = SdlxliffValidator()
                is_valid, error_msg = validator.validate_split_parts(parts_content)
                if not is_valid:
                    self._handle_error(error_msg)
                    return

            self.progress.emit(50, "Объединение переводов с оригиналом...")

            log_file = "merge_details.log"
            try:
                merged_content = merge_with_original(original_content, parts_content, log_file)
            except Exception as e:
                self._handle_error(f"Ошибка объединения: {e}")
                return

            if self.should_stop:
                self._handle_cancelled()
                return

            self.progress.emit(70, "Анализ результата...")

            validator = SdlxliffValidator()
            metadata = validator._extract_split_metadata(parts_content[0])
            original_name = metadata.get('original_name', 'merged.sdlxliff')
            encoding = metadata.get('encoding', 'utf-8')

            total_segments = len([1 for _ in re.finditer(r'<trans-unit[^>]*>', original_content)])
            translated_segments = len([1 for _ in re.finditer(r'<target[^>]*>.*?</target>', merged_content, re.DOTALL)])

            self.progress.emit(80, "Сохранение файла...")

            if self.settings.output_path:
                output_path = self.settings.output_path
            else:
                if not original_name.lower().endswith('.sdlxliff'):
                    original_name = Path(original_name).stem + '.sdlxliff'
                output_path = self.filepaths[0].parent / original_name

                if self.settings.create_backup and output_path.exists():
                    try:
                        create_backup(output_path)
                    except Exception as e:
                        logger.warning(f"Не удалось создать резервную копию: {e}")

            try:
                with open(output_path, 'w', encoding=encoding, newline='') as f:
                    f.write(merged_content)
            except Exception as e:
                self._handle_error(f"Ошибка сохранения: {e}")
                return

            self.progress.emit(100, "Объединение завершено!")

            stats = {
                "operation": "merge_with_original",
                "parts_count": len(parts_content),
                "total_segments": total_segments,
                "translated_segments": translated_segments,
                "translation_progress": (translated_segments / total_segments * 100) if total_segments > 0 else 0,
                "output_size_mb": len(merged_content.encode(encoding)) / (1024 * 1024),
                "original_file_used": True,
                "split_id": metadata.get('split_id'),
                "original_name": original_name,
                "encoding": encoding,
                "log_file": log_file
            }

            result = ConversionResult(
                success=True,
                output_files=[output_path],
                stats=stats,
                status=ConversionStatus.COMPLETED
            )

            self.log_written.emit(f"✅ Объединение завершено! Создан файл: {output_path.name}")
            self.log_written.emit(f"   📊 Всего сегментов: {total_segments}")
            self.log_written.emit(f"   ✅ Переведено: {translated_segments}")
            self.log_written.emit(f"   💾 Размер файла: {stats['output_size_mb']:.1f} MB")

            self.finished.emit(result)
            logger.info("SDLXLIFF merge worker finished")

        except Exception as e:
            self._handle_error(str(e))

    def _handle_error(self, error_msg: str):
        logger.error(error_msg)
        self.log_written.emit(f"❌ Ошибка: {error_msg}")
        result = ConversionResult(
            success=False,
            output_files=[],
            stats={"error": error_msg},
            errors=[error_msg],
            status=ConversionStatus.FAILED
        )
        self.finished.emit(result)
        self.error.emit(error_msg)

    def _handle_cancelled(self):
        result = ConversionResult(
            success=False,
            output_files=[],
            stats={"cancelled": True},
            errors=["Cancelled by user"],
            status=ConversionStatus.CANCELLED
        )
        self.finished.emit(result)

    def stop(self):
        self.should_stop = True
        logger.info("SDLXLIFF merge worker stop requested")