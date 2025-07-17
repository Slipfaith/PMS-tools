# sdlxliff_split_merge/io_utils.py
"""
Утилиты для ввода/вывода SDLXLIFF файлов
"""

from pathlib import Path
import re
import logging
from typing import List

logger = logging.getLogger(__name__)


def make_split_filenames(src_path: str, parts_count: int) -> List[str]:
    """
    Создает имена файлов для разделенных частей

    Args:
        src_path: Путь к исходному файлу
        parts_count: Количество частей

    Returns:
        Список путей для частей
    """
    p = Path(src_path)
    name = p.stem
    ext = p.suffix
    parent = p.parent

    return [
        str(parent / f"{name}.{i + 1}of{parts_count}{ext}")
        for i in range(parts_count)
    ]


def save_bytes_list(files_content: List[str], filenames: List[str]):
    """
    Сохраняет список содержимого в файлы

    Args:
        files_content: Список содержимого файлов как строки
        filenames: Список имен файлов
    """
    for content, fname in zip(files_content, filenames):
        try:
            # Определяем кодировку из содержимого
            encoding = _detect_encoding(content)

            with open(fname, "w", encoding=encoding) as f:
                f.write(content)

            logger.info(f"Saved file: {fname} (encoding: {encoding})")

        except Exception as e:
            logger.error(f"Error saving file {fname}: {e}")
            raise


def read_bytes_list(paths: List[str]) -> List[str]:
    """
    Читает список файлов и возвращает их содержимое

    Args:
        paths: Список путей к файлам

    Returns:
        Список содержимого файлов как строки
    """
    content_list = []

    for path in paths:
        try:
            # Определяем кодировку файла
            encoding = _detect_file_encoding(Path(path))

            with open(path, "r", encoding=encoding) as f:
                content = f.read()

            content_list.append(content)
            logger.info(f"Read file: {path} (encoding: {encoding})")

        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            raise

    return content_list


def sort_split_filenames(file_list: List[str]) -> List[str]:
    """
    Сортирует список split-файлов по суффиксу "NofM" в имени

    Args:
        file_list: Список путей к файлам

    Returns:
        Отсортированный список путей
    """
    pattern = re.compile(r"\.(\d+)of(\d+)\.sdlxliff$", re.IGNORECASE)

    def extract_part_number(fname: str) -> int:
        """Извлекает номер части из имени файла"""
        m = pattern.search(fname)
        if m:
            return int(m.group(1))
        return float('inf')  # Если паттерн не найден - в конец списка

    sorted_list = sorted(file_list, key=extract_part_number)

    logger.info(f"Sorted {len(file_list)} files by part number")
    return sorted_list


def _detect_encoding(content: str) -> str:
    """
    Определяет кодировку из содержимого XML

    Args:
        content: Содержимое файла как строка

    Returns:
        Название кодировки
    """
    # Ищем объявление кодировки в XML
    encoding_match = re.search(r'encoding=["\']([^"\']+)["\']', content)
    if encoding_match:
        declared_encoding = encoding_match.group(1).lower()

        # Нормализуем название кодировки
        if declared_encoding in ['utf-8', 'utf8']:
            return 'utf-8'
        elif declared_encoding in ['utf-16', 'utf16']:
            return 'utf-16'
        elif declared_encoding in ['windows-1252', 'cp1252']:
            return 'cp1252'
        else:
            return declared_encoding

    return 'utf-8'  # По умолчанию


def _detect_file_encoding(file_path: Path) -> str:
    """
    Определяет кодировку файла

    Args:
        file_path: Путь к файлу

    Returns:
        Название кодировки
    """
    try:
        # Читаем первые 1KB для определения кодировки
        with open(file_path, 'rb') as f:
            raw_data = f.read(1024)

        # Проверяем BOM для UTF-16
        if raw_data.startswith(b'\xff\xfe') or raw_data.startswith(b'\xfe\xff'):
            return 'utf-16'

        # Проверяем BOM для UTF-8
        if raw_data.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'

        # Пытаемся декодировать как UTF-8
        try:
            text = raw_data.decode('utf-8')

            # Ищем объявление кодировки
            encoding_match = re.search(r'encoding=["\']([^"\']+)["\']', text)
            if encoding_match:
                declared_encoding = encoding_match.group(1).lower()

                if declared_encoding in ['utf-8', 'utf8']:
                    return 'utf-8'
                elif declared_encoding in ['utf-16', 'utf16']:
                    return 'utf-16'
                else:
                    return declared_encoding

            return 'utf-8'

        except UnicodeDecodeError:
            pass

        # Пытаемся другие кодировки
        for encoding in ['utf-16', 'cp1252', 'iso-8859-1']:
            try:
                raw_data.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue

        # Если ничего не подошло, используем UTF-8 с игнорированием ошибок
        logger.warning(f"Could not detect encoding for {file_path}, using utf-8")
        return 'utf-8'

    except Exception as e:
        logger.warning(f"Error detecting encoding for {file_path}: {e}")
        return 'utf-8'


def create_backup(file_path: Path, backup_suffix: str = ".backup") -> Path:
    """
    Создает резервную копию файла

    Args:
        file_path: Путь к исходному файлу
        backup_suffix: Суффикс для резервной копии

    Returns:
        Путь к резервной копии
    """
    backup_path = file_path.with_suffix(file_path.suffix + backup_suffix)

    try:
        # Если резервная копия уже существует, добавляем номер
        counter = 1
        while backup_path.exists():
            backup_path = file_path.with_suffix(f"{file_path.suffix}{backup_suffix}.{counter}")
            counter += 1

        # Копируем файл
        import shutil
        shutil.copy2(file_path, backup_path)

        logger.info(f"Created backup: {backup_path}")
        return backup_path

    except Exception as e:
        logger.error(f"Error creating backup for {file_path}: {e}")
        raise