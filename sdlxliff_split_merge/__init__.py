# sdlxliff_split_merge/__init__.py
"""
SDLXLIFF Split/Merge Module - Структурное разделение с поддержкой переводов
Модуль для разделения и объединения SDLXLIFF файлов с сохранением структуры
"""

from .splitter import StructuralSplitter
from .merger import StructuralMerger
from .validator import SdlxliffValidator
from .io_utils import make_split_filenames, save_bytes_list, read_bytes_list, sort_split_filenames
from .xml_utils import TransUnitParser, XmlStructure

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
    # Старые имена для совместимости
    "Splitter",
    "Merger"
]