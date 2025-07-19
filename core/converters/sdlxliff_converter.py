import re
from pathlib import Path
from typing import List, Dict, Optional, Iterator
import logging
from dataclasses import dataclass

from ..base import (
    StreamingConverter, ConversionResult, ConversionOptions, ConversionStatus,
    ValidationError, ConversionError
)

logger = logging.getLogger(__name__)


@dataclass
class SdlxliffSplitSettings:
    """Настройки разделения SDLXLIFF файла"""
    parts_count: int = 2
    by_word_count: bool = False
    words_per_part: int = 1000
    output_dir: Optional[Path] = None
    preserve_groups: bool = True
    create_backup: bool = True

    def validate(self) -> tuple[bool, str]:
        """Валидация настроек"""
        if not self.by_word_count and self.parts_count < 2:
            return False, "Количество частей должно быть не менее 2"
        if not self.by_word_count and self.parts_count > 100:
            return False, "Количество частей не может превышать 100"
        if self.by_word_count and self.words_per_part < 10:
            return False, "Количество слов на часть должно быть не менее 10"
        if self.by_word_count and self.words_per_part > 50000:
            return False, "Количество слов на часть не может превышать 50,000"
        return True, "OK"


@dataclass
class SdlxliffMergeSettings:
    """Настройки объединения SDLXLIFF файлов"""
    output_path: Optional[Path] = None
    validate_parts: bool = True
    preserve_translations: bool = True
    create_backup: bool = True
    check_completeness: bool = False

    def validate(self) -> tuple[bool, str]:
        """Валидация настроек"""
        return True, "OK"


class SdlxliffConverter(StreamingConverter):
    """Обновленный конвертер для работы с SDLXLIFF файлами"""

    def __init__(self):
        super().__init__()
        self.supported_operations = {'split', 'merge'}

    def can_handle(self, filepath: Path) -> bool:
        """Проверяет, может ли конвертер обработать файл"""
        return filepath.suffix.lower() == '.sdlxliff'

    def validate(self, filepath: Path) -> bool:
        """ИСПРАВЛЕНО: Валидирует SDLXLIFF файл с мягкой валидацией"""
        if not filepath.exists():
            raise ValidationError("File not found: " + str(filepath))

        if not filepath.is_file():
            raise ValidationError("Not a file: " + str(filepath))

        try:
            content = self._read_file_safely(filepath)

            from sdlxliff_split_merge import SdlxliffValidator

            validator = SdlxliffValidator()
            is_valid, error_msg = validator.validate(content)

            if not is_valid:
                raise ValidationError("Invalid SDLXLIFF file: " + str(error_msg))

            return True

        except Exception as e:
            raise ValidationError("Error validating SDLXLIFF: " + str(e))

    def split_file(self, filepath: Path, settings: SdlxliffSplitSettings,
                   options: ConversionOptions) -> ConversionResult:
        """ИСПРАВЛЕНО: Разделяет SDLXLIFF файл на части с мягкой валидацией"""
        try:
            self._update_progress(0, "Проверка файла...", options)

            content = self._read_file_safely(filepath)

            from sdlxliff_split_merge import SdlxliffValidator
            validator = SdlxliffValidator()

            is_valid, error_msg = validator.validate_for_splitting(content)
            if not is_valid:
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": error_msg},
                    errors=[error_msg],
                    status=ConversionStatus.FAILED
                )

            is_valid, error_msg = settings.validate()
            if not is_valid:
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": error_msg},
                    errors=[error_msg],
                    status=ConversionStatus.FAILED
                )

            self._update_progress(20, "Анализ структуры...", options)

            from sdlxliff_split_merge import StructuralSplitter

            try:
                splitter = StructuralSplitter(content)
            except Exception as e:
                error_msg = f"Ошибка анализа структуры файла: {e}"
                logger.error(error_msg)
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": error_msg},
                    errors=[error_msg],
                    status=ConversionStatus.FAILED
                )

            if settings.by_word_count:
                estimated_parts = splitter.estimate_parts_by_words(settings.words_per_part)
                progress_msg = f"Разделение на ~{estimated_parts} частей по {settings.words_per_part} слов..."
                self._update_progress(30, progress_msg, options)
                try:
                    parts_content = splitter.split_by_word_count(settings.words_per_part)
                    actual_parts = len(parts_content)
                except Exception as e:
                    error_msg = f"Ошибка разделения по словам: {e}"
                    logger.error(error_msg)
                    return ConversionResult(
                        success=False,
                        output_files=[],
                        stats={"error": error_msg},
                        errors=[error_msg],
                        status=ConversionStatus.FAILED
                    )
            else:
                progress_msg = f"Разделение на {settings.parts_count} частей..."
                self._update_progress(30, progress_msg, options)
                try:
                    parts_content = splitter.split(settings.parts_count)
                    actual_parts = settings.parts_count
                except Exception as e:
                    error_msg = f"Ошибка разделения на части: {e}"
                    logger.error(error_msg)
                    return ConversionResult(
                        success=False,
                        output_files=[],
                        stats={"error": error_msg},
                        errors=[error_msg],
                        status=ConversionStatus.FAILED
                    )

            if self._should_stop(options):
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"cancelled": True},
                    errors=["Conversion cancelled by user"],
                    status=ConversionStatus.CANCELLED
                )

            self._update_progress(70, "Сохранение частей...", options)

            if settings.create_backup:
                try:
                    from sdlxliff_split_merge.io_utils import create_backup
                    create_backup(filepath)
                except Exception as e:
                    logger.warning(f"Не удалось создать резервную копию: {e}")

            output_dir = settings.output_dir or filepath.parent

            from sdlxliff_split_merge.io_utils import make_split_filenames, save_bytes_list

            output_paths = make_split_filenames(str(filepath), actual_parts)

            if settings.output_dir:
                output_paths = [
                    str(settings.output_dir / Path(p).name)
                    for p in output_paths
                ]

            try:
                save_bytes_list(parts_content, output_paths)
            except Exception as e:
                error_msg = f"Ошибка сохранения частей: {e}"
                logger.error(error_msg)
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": error_msg},
                    errors=[error_msg],
                    status=ConversionStatus.FAILED
                )

            self._update_progress(90, "Проверка результатов...", options)

            output_files = []
            for path in output_paths:
                p = Path(path)
                if p.exists():
                    output_files.append(p)

            if len(output_files) != actual_parts:
                error_msg = f"Не все части были сохранены: {len(output_files)} из {actual_parts}"
                logger.error(error_msg)
                return ConversionResult(
                    success=False,
                    output_files=output_files,
                    stats={"error": error_msg},
                    errors=[error_msg],
                    status=ConversionStatus.FAILED
                )

            self._update_progress(100, "Разделение завершено!", options)

            split_info = splitter.get_split_info()

            stats = {
                "operation": "split",
                "source_file": filepath.name,
                "source_size_mb": filepath.stat().st_size / (1024 * 1024),
                "parts_count": actual_parts,
                "segments_total": split_info['total_segments'],
                "words_total": split_info['total_words'],
                "by_word_count": settings.by_word_count,
                "words_per_part": settings.words_per_part if settings.by_word_count else None,
                "preserve_groups": settings.preserve_groups,
                "split_id": split_info['split_id'],
                "encoding": split_info['encoding'],
                "validation_warnings": split_info.get('validation_warnings', [])
            }

            return ConversionResult(
                success=True,
                output_files=output_files,
                stats=stats,
                status=ConversionStatus.COMPLETED
            )

        except Exception as e:
            logger.exception("Error splitting SDLXLIFF: " + str(e))
            return ConversionResult(
                success=False,
                output_files=[],
                stats={"error": str(e)},
                errors=[str(e)],
                status=ConversionStatus.FAILED
            )

    def merge_files(self, filepaths: List[Path], settings: SdlxliffMergeSettings,
                    options: ConversionOptions) -> ConversionResult:
        """ИСПРАВЛЕНО: Объединяет несколько SDLXLIFF файлов в один с мягкой валидацией"""
        try:
            self._update_progress(0, "Проверка файлов...", options)

            is_valid, error_msg = settings.validate()
            if not is_valid:
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": error_msg},
                    errors=[error_msg],
                    status=ConversionStatus.FAILED
                )

            for filepath in filepaths:
                if not filepath.exists():
                    error_msg = "File not found: " + str(filepath)
                    return ConversionResult(
                        success=False,
                        output_files=[],
                        stats={"error": error_msg},
                        errors=[error_msg],
                        status=ConversionStatus.FAILED
                    )

            self._update_progress(10, "Чтение файлов...", options)

            parts_content = []
            for filepath in filepaths:
                try:
                    content = self._read_file_safely(filepath)
                    parts_content.append(content)
                except Exception as e:
                    error_msg = f"Ошибка чтения файла {filepath.name}: {e}"
                    return ConversionResult(
                        success=False,
                        output_files=[],
                        stats={"error": error_msg},
                        errors=[error_msg],
                        status=ConversionStatus.FAILED
                    )

            self._update_progress(30, "Анализ структуры частей...", options)

            if settings.validate_parts:
                from sdlxliff_split_merge import SdlxliffValidator

                validator = SdlxliffValidator()
                is_valid, error_msg = validator.validate_for_merging(parts_content)

                if not is_valid:
                    return ConversionResult(
                        success=False,
                        output_files=[],
                        stats={"error": error_msg},
                        errors=[error_msg],
                        status=ConversionStatus.FAILED
                    )

            self._update_progress(50, "Объединение частей...", options)

            from sdlxliff_split_merge import StructuralMerger

            try:
                merger = StructuralMerger(parts_content)
                merged_content = merger.merge()
            except Exception as e:
                error_msg = f"Ошибка объединения частей: {e}"
                logger.error(error_msg)
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": error_msg},
                    errors=[error_msg],
                    status=ConversionStatus.FAILED
                )

            if self._should_stop(options):
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"cancelled": True},
                    errors=["Conversion cancelled by user"],
                    status=ConversionStatus.CANCELLED
                )

            self._update_progress(70, "Проверка результата...", options)

            merge_info = merger.get_merge_info()

            if settings.check_completeness:
                try:
                    is_complete, missing_segments = merger.validate_translation_completeness()
                    if not is_complete:
                        warning_msg = f"Translation incomplete: {len(missing_segments)} missing segments"
                        logger.warning(warning_msg)
                except Exception as e:
                    logger.warning(f"Не удалось проверить полноту переводов: {e}")

            self._update_progress(80, "Сохранение файла...", options)

            if settings.output_path:
                output_path = settings.output_path
            else:
                original_name = merge_info.get('original_name')
                if original_name:
                    if not original_name.lower().endswith('.sdlxliff'):
                        original_name = Path(original_name).stem + '.sdlxliff'
                    output_path = filepaths[0].parent / original_name
                else:
                    import re
                    base_name = filepaths[0].stem
                    base_name = re.sub(r'\.\d+of\d+', '', base_name)
                    output_path = filepaths[0].parent / (base_name + "_merged.sdlxliff")

                    if settings.create_backup and output_path.exists():
                        try:
                            from sdlxliff_split_merge.io_utils import create_backup
                            create_backup(output_path)
                        except Exception as e:
                            logger.warning(f"Не удалось создать резервную копию: {e}")

            encoding = merge_info.get('encoding', 'utf-8')
            try:
                with open(output_path, 'w', encoding=encoding, newline='') as f:
                    f.write(merged_content)
            except Exception as e:
                error_msg = f"Ошибка сохранения файла: {e}"
                logger.error(error_msg)
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": error_msg},
                    errors=[error_msg],
                    status=ConversionStatus.FAILED
                )

            self._update_progress(100, "Объединение завершено!", options)

            translation_stats = merger.get_translation_stats()

            stats = {
                "operation": "merge",
                "parts_count": len(filepaths),
                "total_segments": merge_info.get('total_segments', 0),
                "total_words": merge_info.get('total_words', 0),
                "translated_segments": merge_info.get('translated_segments', 0),
                "translation_progress": merge_info.get('translation_progress', 0),
                "output_size_mb": len(merged_content.encode(encoding)) / (1024 * 1024),
                "validated": settings.validate_parts,
                "split_id": merge_info.get('split_id'),
                "original_name": merge_info.get('original_name'),
                "encoding": encoding,
                "parts_stats": translation_stats.get('parts_stats', []),
                "validation_warnings": merge_info.get('validation_warnings', [])
            }

            return ConversionResult(
                success=True,
                output_files=[output_path],
                stats=stats,
                status=ConversionStatus.COMPLETED
            )

        except Exception as e:
            logger.exception("Error merging SDLXLIFF files: " + str(e))
            return ConversionResult(
                success=False,
                output_files=[],
                stats={"error": str(e)},
                errors=[str(e)],
                status=ConversionStatus.FAILED
            )

    def get_progress_steps(self, filepath: Path) -> int:
        """Возвращает количество шагов прогресса"""
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
        """ИСПРАВЛЕНО: Анализирует SDLXLIFF файл и возвращает информацию с обработкой ошибок"""
        try:
            content = self._read_file_safely(filepath)

            from sdlxliff_split_merge import SdlxliffValidator

            validator = SdlxliffValidator()
            is_part = validator.is_split_part(content)

            if is_part:
                metadata = validator._extract_split_metadata(content)
                return {
                    "valid": True,
                    "is_part": True,
                    "part_info": metadata,
                    "file_size_mb": len(content.encode('utf-8')) / (1024 * 1024)
                }
            else:
                try:
                    from sdlxliff_split_merge import StructuralSplitter

                    splitter = StructuralSplitter(content)
                    split_info = splitter.get_split_info()

                    return {
                        "valid": True,
                        "is_part": False,
                        "segments_count": split_info['total_segments'],
                        "words_count": split_info['total_words'],
                        "translated_count": split_info['translated_segments'],
                        "file_size_mb": len(content.encode(split_info['encoding'])) / (1024 * 1024),
                        "encoding": split_info['encoding'],
                        "has_groups": split_info['has_groups'],
                        "estimated_parts_1000_words": splitter.estimate_parts_by_words(1000),
                        "estimated_parts_2000_words": splitter.estimate_parts_by_words(2000),
                        "estimated_parts_5000_words": splitter.estimate_parts_by_words(5000),
                    }
                except Exception as e:
                    logger.warning(f"Не удалось проанализировать структуру файла: {e}")

                    file_size_mb = len(content.encode('utf-8')) / (1024 * 1024)
                    segments_count = len(re.findall(r'<trans-unit', content))

                    return {
                        "valid": True,
                        "is_part": False,
                        "segments_count": segments_count,
                        "words_count": segments_count * 10,
                        "translated_count": 0,
                        "file_size_mb": file_size_mb,
                        "encoding": "utf-8",
                        "has_groups": '<group' in content,
                        "estimated_parts_1000_words": max(1, segments_count // 100),
                        "estimated_parts_2000_words": max(1, segments_count // 200),
                        "estimated_parts_5000_words": max(1, segments_count // 500),
                        "analysis_warning": "Использована упрощенная оценка из-за ошибки анализа"
                    }

        except Exception as e:
            logger.error("Error analyzing SDLXLIFF: " + str(e))
            return {
                "valid": False,
                "error": str(e),
                "analysis_failed": True
            }

    def _read_file_safely(self, filepath: Path) -> str:
        """ИСПРАВЛЕНО: Безопасно читает файл с улучшенным определением кодировки"""
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                if content.strip():
                    return content
        except UnicodeDecodeError:
            pass
        except Exception as e:
            logger.warning(f"Ошибка чтения с UTF-8-sig: {e}")

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    return content
        except UnicodeDecodeError:
            pass
        except Exception as e:
            logger.warning(f"Ошибка чтения с UTF-8: {e}")

        try:
            with open(filepath, 'r', encoding='utf-16') as f:
                content = f.read()
                if content.strip():
                    return content
        except UnicodeDecodeError:
            pass
        except Exception as e:
            logger.warning(f"Ошибка чтения с UTF-16: {e}")

        try:
            with open(filepath, 'rb') as f:
                raw_data = f.read()

            if raw_data.startswith(b'\xff\xfe'):
                encoding = 'utf-16le'
            elif raw_data.startswith(b'\xfe\xff'):
                encoding = 'utf-16be'
            elif raw_data.startswith(b'\xef\xbb\xbf'):
                encoding = 'utf-8-sig'
            else:
                encoding = 'utf-8'

            content = raw_data.decode(encoding)
            if content.strip():
                return content

        except Exception as e:
            logger.warning(f"Ошибка автоопределения кодировки: {e}")

        try:
            logger.warning(f"Используем UTF-8 с игнорированием ошибок для {filepath}")
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                if content.strip():
                    return content
        except Exception as e:
            logger.error(f"Критическая ошибка чтения файла {filepath}: {e}")
            raise

        raise ValueError(f"Не удалось прочитать файл {filepath} ни с одной кодировкой")