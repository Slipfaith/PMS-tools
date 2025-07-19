# sdlxliff_split_merge/__init__.py
"""
SDLXLIFF Split/Merge Module - Структурное разделение с поддержкой переводов
Модуль для разделения и объединения SDLXLIFF файлов с сохранением структуры
"""

from .splitter import StructuralSplitter
from .merger import StructuralMerger
from .validator import SdlxliffValidator
from .io_utils import (
    make_split_filenames,
    save_bytes_list,
    read_bytes_list,
    sort_split_filenames,
    load_original_and_parts,
    create_backup,  # Добавляем импорт create_backup
)
from .merger import merge_with_original
from .xml_utils import TransUnitParser, XmlStructure
from .settings import SdlxliffSplitSettings, SdlxliffMergeSettings  # Добавляем импорт настроек
from .analyzer import SdlxliffAnalyzer  # Добавляем импорт анализатора

# Импорты для обратной совместимости с main.py
# Создаем алиасы для старых имен
Splitter = StructuralSplitter
Merger = StructuralMerger

__version__ = "2.0.0"
__all__ = [
    "StructuralSplitter",
    "StructuralMerger",
    "SdlxliffValidator",
    "TransUnitParser",
    "XmlStructure",
    "make_split_filenames",
    "save_bytes_list",
    "read_bytes_list",
    "sort_split_filenames",
    "load_original_and_parts",
    "merge_with_original",
    "create_backup",  # Добавляем в список экспортируемых
    "SdlxliffSplitSettings",  # Добавляем настройки разделения
    "SdlxliffMergeSettings",  # Добавляем настройки объединения
    "SdlxliffAnalyzer",  # Добавляем анализатор
    # Старые имена для совместимости
    "Splitter",
    "Merger"
]