# sdlxliff_split_merge/analyzer.py
"""
Анализатор SDLXLIFF файлов
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any

from .validator import SdlxliffValidator
from .splitter import StructuralSplitter

logger = logging.getLogger(__name__)


class SdlxliffAnalyzer:
    """Класс для анализа SDLXLIFF файлов"""

    def can_handle(self, filepath: Path) -> bool:
        """Проверяет, может ли анализатор обработать файл"""
        return filepath.suffix.lower() == '.sdlxliff'

    def analyze_file(self, filepath: Path) -> Dict[str, Any]:
        """Анализирует SDLXLIFF файл и возвращает информацию с обработкой ошибок"""
        try:
            content = self._read_file_safely(filepath)

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
            logger.error(f"Error analyzing SDLXLIFF: {e}")
            return {
                "valid": False,
                "error": str(e),
                "analysis_failed": True
            }

    def _read_file_safely(self, filepath: Path) -> str:
        """Безопасно читает файл с улучшенным определением кодировки"""
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