# sdlxliff_split_merge/__init__.py
"""
SDLXLIFF Split/Merge Module
Модуль для разделения и объединения SDLXLIFF файлов
"""

from .splitter import Splitter
from .merger import Merger
from .validator import SdlxliffValidator
from .io_utils import make_split_filenames, save_bytes_list, read_bytes_list, sort_split_filenames

__version__ = "1.0.0"
__all__ = [
    "Splitter",
    "Merger",
    "SdlxliffValidator",
    "make_split_filenames",
    "save_bytes_list",
    "read_bytes_list",
    "sort_split_filenames"
]
