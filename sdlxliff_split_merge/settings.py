# sdlxliff_split_merge/settings.py
"""
Настройки для операций разделения и объединения SDLXLIFF файлов
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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