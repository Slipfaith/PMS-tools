# core/exceptions.py

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


# core/base.py

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, Iterator, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class ConversionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
        return options.should_stop_callback and options.should_stop_callback()

    def _update_progress(self, progress: int, message: str, options: ConversionOptions):
        if options.progress_callback:
            options.progress_callback(progress, message)