# core/base.py - ПРОВЕРЬТЕ ЧТО ЭТО ЕСТЬ

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, Iterator, Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum


class ConversionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ColumnType(Enum):
    TEXT = "text"
    COMMENT = "comment"
    CONTEXT = "context"
    ID = "id"
    IGNORE = "ignore"


@dataclass
class ConversionResult:
    """Результат конвертации файла"""
    success: bool
    output_files: list[Path]
    stats: Dict[str, Any]
    errors: list[str] = None
    status: ConversionStatus = ConversionStatus.COMPLETED

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class ConversionOptions:
    """Опции конвертации"""
    export_tmx: bool = True
    export_xlsx: bool = False
    export_json: bool = False
    source_lang: str = "en-US"
    target_lang: str = "ru-RU"
    batch_size: int = 1000
    progress_callback: Optional[Callable[[int, str], None]] = None
    should_stop_callback: Optional[Callable[[], bool]] = None


@dataclass
class ColumnInfo:
    """Информация о колонке Excel"""
    index: int
    name: str
    detected_language: Optional[str] = None
    column_type: ColumnType = ColumnType.TEXT
    user_language: Optional[str] = None
    user_type: Optional[ColumnType] = None

    @property
    def final_language(self) -> Optional[str]:
        """Возвращает финальный язык"""
        return self.user_language or self.detected_language

    @property
    def final_type(self) -> ColumnType:
        """Возвращает финальный тип колонки"""
        return self.user_type or self.column_type


@dataclass
class SheetInfo:
    """Информация о листе Excel"""
    name: str
    header_row: int = 1
    columns: List[ColumnInfo] = None
    data_rows: int = 0
    is_selected: bool = True

    def __post_init__(self):
        if self.columns is None:
            self.columns = []

    def get_text_columns(self) -> List[ColumnInfo]:
        """Возвращает только текстовые колонки"""
        return [col for col in self.columns if col.final_type == ColumnType.TEXT]

    def get_comment_columns(self) -> List[ColumnInfo]:
        """Возвращает колонки с комментариями"""
        return [col for col in self.columns if col.final_type == ColumnType.COMMENT]


@dataclass
class ExcelAnalysis:
    """Результат анализа Excel файла"""
    sheets: List[SheetInfo] = None
    detected_source_lang: Optional[str] = None
    detected_target_lang: Optional[str] = None
    file_path: Optional[Path] = None

    def __post_init__(self):
        if self.sheets is None:
            self.sheets = []

    def get_selected_sheets(self) -> List[SheetInfo]:
        """Возвращает выбранные для конвертации листы"""
        return [sheet for sheet in self.sheets if sheet.is_selected]

    def get_total_segments(self) -> int:
        """Возвращает общее количество сегментов во всех выбранных листах"""
        return sum(sheet.data_rows for sheet in self.get_selected_sheets())


@dataclass
class ExcelConversionSettings:
    """Настройки конвертации Excel"""
    source_language: str
    target_language: str
    include_comments: bool = True
    include_context: bool = True
    skip_empty_segments: bool = True
    selected_sheets: List[str] = None
    column_mappings: Dict[str, Dict[int, ColumnInfo]] = None

    def __post_init__(self):
        if self.selected_sheets is None:
            self.selected_sheets = []
        if self.column_mappings is None:
            self.column_mappings = {}

    def get_sheet_column_mapping(self, sheet_name: str) -> Dict[int, ColumnInfo]:
        """Возвращает маппинг колонок для листа"""
        return self.column_mappings.get(sheet_name, {})


@dataclass
class TermBaseConversionSettings:
    """Настройки конвертации терминологических баз"""
    source_language: str
    export_tmx: bool = True
    export_xlsx: bool = False


@dataclass
class TranslationSegment:
    """Сегмент перевода"""
    source_text: str
    target_text: str
    source_lang: str
    target_lang: str
    comments: List[str] = None
    context: str = None
    segment_id: str = None

    def __post_init__(self):
        if self.comments is None:
            self.comments = []

    def has_content(self) -> bool:
        """Проверяет, есть ли содержимое в сегменте"""
        return bool(self.source_text.strip() and self.target_text.strip())

    def add_comment(self, comment: str):
        """Добавляет комментарий"""
        if comment and comment.strip():
            self.comments.append(comment.strip())


class FileConverter(Protocol):
    """Протокол для всех конвертеров файлов"""

    def can_handle(self, filepath: Path) -> bool: ...

    def validate(self, filepath: Path) -> bool: ...

    def convert(self, filepath: Path, options: ConversionOptions) -> ConversionResult: ...

    def get_progress_steps(self, filepath: Path) -> int: ...


class StreamingConverter(ABC):
    """Базовый класс для потоковой конвертации"""

    @abstractmethod
    def convert_streaming(self, filepath: Path, options: ConversionOptions) -> Iterator[Any]:
        pass

    def _should_stop(self, options: ConversionOptions) -> bool:
        if hasattr(options, 'should_stop_callback') and options.should_stop_callback:
            try:
                return options.should_stop_callback()
            except TypeError:
                return False
        return False

    def _update_progress(self, progress: int, message: str, options: ConversionOptions):
        if hasattr(options, 'progress_callback') and options.progress_callback:
            try:
                options.progress_callback(progress, message)
            except TypeError:
                pass


# Исключения
class ConversionError(Exception):
    """Базовое исключение для ошибок конвертации"""

    def __init__(self, message: str, filepath=None, details=None):
        super().__init__(message)
        self.filepath = filepath
        self.details = details or {}


class ValidationError(ConversionError):
    """Ошибка валидации файла"""
    pass


class UnsupportedFormatError(ConversionError):
    """Неподдерживаемый формат файла"""
    pass


class ExcelStructureError(ConversionError):
    """Ошибка структуры Excel файла"""
    pass