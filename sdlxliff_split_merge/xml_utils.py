# sdlxliff_split_merge/xml_utils.py
"""
Утилиты для работы с XML структурой SDLXLIFF файлов
"""

import re
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def find_trans_units_and_groups(xml_bytes: bytes) -> Dict[str, Any]:
    """
    Находит все trans-unit и group элементы в SDLXLIFF файле

    Args:
        xml_bytes: Содержимое файла в байтах

    Returns:
        Словарь со структурой:
        {
            'trans_units': [
                {
                    'match': Match объект,
                    'id': str,
                    'group_id': Optional[int] - индекс группы или None
                },
                ...
            ],
            'groups': [
                {
                    'match': Match объект,
                    'trans_unit_indices': List[int] - индексы trans-unit в группе
                },
                ...
            ]
        }
    """
    xml_str = xml_bytes.decode('utf-8')

    # Находим все trans-unit элементы
    trans_unit_pattern = re.compile(
        r'<trans-unit\s+[^>]*id="([^"]+)"[^>]*>.*?</trans-unit>',
        re.DOTALL
    )

    # Находим все group элементы
    group_pattern = re.compile(
        r'<group[^>]*>.*?</group>',
        re.DOTALL
    )

    # Собираем информацию о trans-units
    trans_units = []
    for match in trans_unit_pattern.finditer(xml_str):
        trans_units.append({
            'match': match,
            'id': match.group(1),
            'group_id': None  # Заполним позже
        })

    # Собираем информацию о группах
    groups = []
    for group_match in group_pattern.finditer(xml_str):
        group_start = group_match.start()
        group_end = group_match.end()

        # Находим trans-units внутри этой группы
        trans_unit_indices = []
        for i, unit in enumerate(trans_units):
            unit_start = unit['match'].start()
            if group_start < unit_start < group_end:
                trans_unit_indices.append(i)
                unit['group_id'] = len(groups)  # Индекс текущей группы

        groups.append({
            'match': group_match,
            'trans_unit_indices': trans_unit_indices
        })

    logger.debug(f"Found {len(trans_units)} trans-units and {len(groups)} groups")

    return {
        'trans_units': trans_units,
        'groups': groups
    }


def extract_source_word_count(trans_unit_bytes: bytes) -> int:
    """
    Подсчитывает количество слов в source элементе trans-unit

    Args:
        trans_unit_bytes: Байты trans-unit элемента

    Returns:
        Количество слов
    """
    trans_unit_str = trans_unit_bytes.decode('utf-8')

    # Извлекаем содержимое <source> тега
    source_pattern = re.compile(r'<source[^>]*>(.*?)</source>', re.DOTALL)
    source_match = source_pattern.search(trans_unit_str)

    if not source_match:
        return 0

    source_content = source_match.group(1)

    # Удаляем вложенные теги (например, <g>, <mrk>)
    clean_content = re.sub(r'<[^>]+>', ' ', source_content)

    # Считаем слова
    words = clean_content.split()
    return len(words)


def validate_sdlxliff_structure(xml_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Валидирует структуру SDLXLIFF файла

    Args:
        xml_bytes: Содержимое файла

    Returns:
        Кортеж (is_valid, error_message)
    """
    try:
        xml_str = xml_bytes.decode('utf-8')

        # Проверяем наличие обязательных элементов
        if not re.search(r'<xliff[^>]*>', xml_str):
            return False, "Отсутствует корневой элемент <xliff>"

        if not re.search(r'<file[^>]*>', xml_str):
            return False, "Отсутствует элемент <file>"

        if not re.search(r'<body[^>]*>', xml_str):
            return False, "Отсутствует элемент <body>"

        # Проверяем namespace SDL
        if 'xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0"' not in xml_str:
            return False, "Отсутствует SDL namespace декларация"

        # Проверяем парность тегов
        for tag in ['xliff', 'file', 'header', 'body', 'trans-unit', 'group']:
            open_count = len(re.findall(f'<{tag}[^>]*>', xml_str))
            close_count = len(re.findall(f'</{tag}>', xml_str))

            if open_count != close_count:
                return False, f"Непарные теги <{tag}>: открыто {open_count}, закрыто {close_count}"

        return True, None

    except Exception as e:
        return False, f"Ошибка парсинга: {str(e)}"


def extract_metadata_from_header(header_str: str) -> Dict[str, str]:
    """
    Извлекает метаданные из header SDLXLIFF

    Args:
        header_str: Строка с header частью

    Returns:
        Словарь с метаданными
    """
    metadata = {}

    # Извлекаем атрибуты из <file>
    file_match = re.search(r'<file([^>]+)>', header_str)
    if file_match:
        attrs_str = file_match.group(1)

        # Парсим атрибуты
        attr_pattern = re.compile(r'(\w+)="([^"]+)"')
        for match in attr_pattern.finditer(attrs_str):
            metadata[match.group(1)] = match.group(2)

    # Извлекаем file-info если есть
    file_info_match = re.search(
        r'<file-info[^>]*>(.*?)</file-info>',
        header_str,
        re.DOTALL
    )

    if file_info_match:
        file_info_content = file_info_match.group(1)

        # Извлекаем значения
        value_pattern = re.compile(r'<value key="([^"]+)">([^<]+)</value>')
        for match in value_pattern.finditer(file_info_content):
            metadata[f'file-info:{match.group(1)}'] = match.group(2)

    return metadata


def get_header_footer(xml_bytes: bytes, units_list: List[dict]) -> Tuple[bytes, bytes]:
    """
    Legacy функция для обратной совместимости
    """
    if not units_list:
        raise ValueError("Список trans-units пуст")

    first_match = units_list[0]['match'] if isinstance(units_list[0], dict) else units_list[0]
    last_match = units_list[-1]['match'] if isinstance(units_list[-1], dict) else units_list[-1]

    # Ищем начало body
    body_start = xml_bytes.find(b'<body>')
    if body_start == -1:
        raise ValueError("Не найден тег <body>")

    # Header включает все до конца <body>
    header_end = body_start + len(b'<body>')
    header = xml_bytes[:header_end]

    # Footer начинается с </body>
    body_end = xml_bytes.find(b'</body>')
    if body_end == -1:
        raise ValueError("Не найден закрывающий тег </body>")

    footer = xml_bytes[body_end:]

    return header, footer