# core/converters/sdlxliff_converter.py
"""
Конвертер для работы с SDLXLIFF файлами (разделение/объединение)
"""

from pathlib import Path
from typing import List, Dict, Optional, Iterator
import logging
from dataclasses import dataclass

from ..base import (
    StreamingConverter, ConversionResult, ConversionOptions, ConversionStatus,
    ValidationError, ConversionError
)
from sdlxliff_split_merge.splitter import Splitter
from sdlxliff_split_merge.merger import Merger
from sdlxliff_split_merge.validator import SdlxliffValidator
from sdlxliff_split_merge.io_utils import save_bytes_list, read_bytes_list, make_split_filenames

logger = logging.getLogger(__name__)


@dataclass
class SdlxliffSplitSettings:
    """Настройки разделения SDLXLIFF файла"""
    parts_count: int = 2
    by_word_count: bool = False
    words_per_part: int = 1000
    output_dir: Optional[Path] = None
    preserve_groups: bool = True  # Новое: сохранять целостность групп

    def validate(self) -> tuple[bool, str]:
        """Валидация настроек"""
        if self.parts_count < 2:
            return False, "Количество частей должно быть не менее 2"
        if self.parts_count > 100:
            return False, "Количество частей не может превышать 100"
        if self.by_word_count and self.words_per_part < 10:
            return False, "Количество слов на часть должно быть не менее 10"
        return True, "OK"


@dataclass
class SdlxliffMergeSettings:
    """Настройки объединения SDLXLIFF файлов"""
    output_path: Optional[Path] = None
    validate_parts: bool = True
    auto_detect_parts: bool = True
    preserve_checksum: bool = True  # Новое: проверять контрольную сумму

    def validate(self) -> tuple[bool, str]:
        """Валидация настроек"""
        return True, "OK"


class SdlxliffConverter(StreamingConverter):
    """Конвертер для работы с SDLXLIFF файлами (разделение/объединение)"""

    def __init__(self):
        super().__init__()
        self.supported_operations = {'split', 'merge'}
        self.validator = SdlxliffValidator()

    def can_handle(self, filepath: Path) -> bool:
        """Проверяет, может ли конвертер обработать файл"""
        return filepath.suffix.lower() == '.sdlxliff'

    def validate(self, filepath: Path) -> bool:
        """Валидирует SDLXLIFF файл"""
        if not filepath.exists():
            raise ValidationError(f"File not found: {filepath}")

        if not filepath.is_file():
            raise ValidationError(f"Not a file: {filepath}")

        try:
            with open(filepath, 'rb') as f:
                xml_bytes = f.read()

            is_valid, error_msg = self.validator.validate(xml_bytes)
            if not is_valid:
                raise ValidationError(f"Invalid SDLXLIFF file: {error_msg}")

            return True

        except Exception as e:
            raise ValidationError(f"Error validating SDLXLIFF: {e}")

    def split_file(self, filepath: Path, settings: SdlxliffSplitSettings,
                   options: ConversionOptions) -> ConversionResult:
        """Разделяет SDLXLIFF файл на части"""
        try:
            self._update_progress(0, "Проверка файла...", options)

            # Валидация
            if not self.validate(filepath):
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": "Validation failed"},
                    errors=["File validation failed"],
                    status=ConversionStatus.FAILED
                )

            # Валидация настроек
            is_valid, error_msg = settings.validate()
            if not is_valid:
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": error_msg},
                    errors=[error_msg],
                    status=ConversionStatus.FAILED
                )

            self._update_progress(10, "Чтение файла...", options)

            # Читаем файл
            with open(filepath, 'rb') as f:
                xml_bytes = f.read()

            self._update_progress(20, "Анализ структуры...", options)

            # Создаем splitter
            splitter = Splitter(xml_bytes)

            # Получаем метаданные
            split_metadata = splitter.get_split_metadata()

            # Определяем количество частей
            if settings.by_word_count:
                # Разделение по количеству слов
                parts_count = splitter.calculate_parts_by_words(settings.words_per_part)
                logger.info(f"Calculated {parts_count} parts for {settings.words_per_part} words per part")
            else:
                parts_count = settings.parts_count

            self._update_progress(30, f"Разделение на {parts_count} частей...", options)

            # Разделяем
            parts_bytes = splitter.split(parts_count)

            if self._should_stop(options):
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"cancelled": True},
                    errors=["Conversion cancelled by user"],
                    status=ConversionStatus.CANCELLED
                )

            self._update_progress(70, "Сохранение частей...", options)

            # Определяем пути для сохранения
            output_dir = settings.output_dir or filepath.parent
            output_paths = make_split_filenames(str(filepath), parts_count)

            # Если указана директория, корректируем пути
            if settings.output_dir:
                output_paths = [
                    str(settings.output_dir / Path(p).name)
                    for p in output_paths
                ]

            # Сохраняем части
            save_bytes_list(parts_bytes, output_paths)

            self._update_progress(90, "Проверка результатов...", options)

            # Проверяем созданные файлы
            output_files = []
            for path in output_paths:
                p = Path(path)
                if p.exists():
                    output_files.append(p)

            self._update_progress(100, "Разделение завершено!", options)

            # Статистика
            stats = {
                "operation": "split",
                "source_file": filepath.name,
                "source_size_mb": filepath.stat().st_size / (1024 * 1024),
                "parts_count": parts_count,
                "segments_total": splitter.get_segments_count(),
                "groups_total": splitter.get_groups_count(),
                "by_word_count": settings.by_word_count,
                "words_per_part": settings.words_per_part if settings.by_word_count else None,
                "preserve_groups": settings.preserve_groups,
                "split_guid": split_metadata['guid'],
                "checksum": split_metadata['checksum']
            }

            return ConversionResult(
                success=True,
                output_files=output_files,
                stats=stats,
                status=ConversionStatus.COMPLETED
            )

        except Exception as e:
            logger.exception(f"Error splitting SDLXLIFF: {e}")
            return ConversionResult(
                success=False,
                output_files=[],
                stats={"error": str(e)},
                errors=[str(e)],
                status=ConversionStatus.FAILED
            )

    def merge_files(self, filepaths: List[Path], settings: SdlxliffMergeSettings,
                    options: ConversionOptions) -> ConversionResult:
        """Объединяет несколько SDLXLIFF файлов в один"""
        try:
            self._update_progress(0, "Проверка файлов...", options)

            # Валидация настроек
            is_valid, error_msg = settings.validate()
            if not is_valid:
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": error_msg},
                    errors=[error_msg],
                    status=ConversionStatus.FAILED
                )

            # Проверяем все файлы
            for filepath in filepaths:
                if not filepath.exists():
                    return ConversionResult(
                        success=False,
                        output_files=[],
                        stats={"error": f"File not found: {filepath}"},
                        errors=[f"File not found: {filepath}"],
                        status=ConversionStatus.FAILED
                    )

            self._update_progress(10, "Чтение файлов...", options)

            # Читаем все части
            parts_bytes = read_bytes_list([str(p) for p in filepaths])

            self._update_progress(30, "Анализ структуры частей...", options)

            # Валидируем части если нужно
            if settings.validate_parts:
                is_valid, error_msg = self.validator.validate_split_parts(parts_bytes)
                if not is_valid:
                    return ConversionResult(
                        success=False,
                        output_files=[],
                        stats={"error": error_msg},
                        errors=[error_msg],
                        status=ConversionStatus.FAILED
                    )

            self._update_progress(50, "Объединение частей...", options)

            # Создаем merger и объединяем
            merger = Merger(parts_bytes)
            merged_bytes = merger.merge()

            if self._should_stop(options):
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"cancelled": True},
                    errors=["Conversion cancelled by user"],
                    status=ConversionStatus.CANCELLED
                )

            self._update_progress(70, "Проверка результата...", options)

            # Валидируем результат
            merge_info = merger.get_merge_info()
            original_checksum = merge_info.get('checksum') if settings.preserve_checksum else None

            is_valid, error_msg = self.validator.validate_merged_file(
                merged_bytes,
                original_checksum
            )

            if not is_valid:
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": f"Merged file validation failed: {error_msg}"},
                    errors=[f"Merged file validation failed: {error_msg}"],
                    status=ConversionStatus.FAILED
                )

            self._update_progress(80, "Сохранение файла...", options)

            # Определяем путь для сохранения
            if settings.output_path:
                output_path = settings.output_path
            else:
                # Берем имя из метаданных или первого файла
                original_name = merge_info.get('original_name')
                if original_name:
                    output_path = filepaths[0].parent / original_name
                else:
                    # Убираем паттерн вида .1of3
                    import re
                    base_name = filepaths[0].stem
                    base_name = re.sub(r'\.\d+of\d+$', '', base_name)
                    output_path = filepaths[0].parent / f"{base_name}_merged.sdlxliff"

            # Сохраняем
            with open(output_path, 'wb') as f:
                f.write(merged_bytes)

            self._update_progress(100, "Объединение завершено!", options)

            # Статистика
            stats = {
                "operation": "merge",
                "parts_count": len(filepaths),
                "total_units": merge_info.get('total_units', 0),
                "output_size_mb": len(merged_bytes) / (1024 * 1024),
                "validated": settings.validate_parts,
                "guid": merge_info.get('guid'),
                "original_name": merge_info.get('original_name')
            }

            return ConversionResult(
                success=True,
                output_files=[output_path],
                stats=stats,
                status=ConversionStatus.COMPLETED
            )

        except Exception as e:
            logger.exception(f"Error merging SDLXLIFF files: {e}")
            return ConversionResult(
                success=False,
                output_files=[],
                stats={"error": str(e)},
                errors=[str(e)],
                status=ConversionStatus.FAILED
            )

    def get_progress_steps(self, filepath: Path) -> int:
        """Возвращает количество шагов прогресса"""
        # Для split/merge операций используем фиксированное значение
        return 100

    def convert(self, filepath: Path, options: ConversionOptions) -> ConversionResult:
        """Базовый метод конвертации - не используется напрямую"""
        return ConversionResult(
            success=False,
            output_files=[],
            stats={"error": "Use split_file or merge_files methods"},
            errors=["Direct conversion not supported"],
            status=ConversionStatus.FAILED
        )

    def convert_streaming(self, filepath: Path, options: ConversionOptions) -> Iterator:
        """Потоковая конвертация - не поддерживается"""
        return iter([])

    def analyze_file(self, filepath: Path) -> Dict[str, any]:
        """Анализирует SDLXLIFF файл и возвращает информацию"""
        try:
            with open(filepath, 'rb') as f:
                xml_bytes = f.read()

            # Проверяем, является ли файл частью
            is_part = self.validator.is_split_part(xml_bytes)

            if is_part:
                # Извлекаем метаданные части
                metadata = self.validator._extract_split_metadata(xml_bytes)
                return {
                    "valid": True,
                    "is_part": True,
                    "part_info": metadata,
                    "file_size_mb": len(xml_bytes) / (1024 * 1024)
                }
            else:
                # Анализируем обычный файл
                splitter = Splitter(xml_bytes)

                return {
                    "valid": True,
                    "is_part": False,
                    "segments_count": splitter.get_segments_count(),
                    "groups_count": splitter.get_groups_count(),
                    "file_size_mb": len(xml_bytes) / (1024 * 1024),
                    "estimated_parts_1000_words": splitter.calculate_parts_by_words(1000),
                    "estimated_parts_2000_words": splitter.calculate_parts_by_words(2000),
                    "estimated_parts_5000_words": splitter.calculate_parts_by_words(5000),
                }

        except Exception as e:
            logger.error(f"Error analyzing SDLXLIFF: {e}")
            return {
                "valid": False,
                "error": str(e)
            }