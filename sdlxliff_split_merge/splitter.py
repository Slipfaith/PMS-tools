# sdlxliff_split_merge/splitter.py
"""
Модуль для разделения SDLXLIFF файлов на части
"""

import re
from typing import List, Tuple
import logging

from .xml_utils import find_trans_units, extract_source_word_count, get_header_footer

logger = logging.getLogger(__name__)


class Splitter:
    """
    Разделитель SDLXLIFF файлов на части с сохранением структуры
    """

    def __init__(self, xml_bytes: bytes):
        """
        Инициализация с содержимым SDLXLIFF файла

        Args:
            xml_bytes: Содержимое SDLXLIFF файла в байтах
        """
        self.xml_bytes = xml_bytes
        self.trans_units = find_trans_units(xml_bytes)

        if not self.trans_units:
            raise ValueError("В файле не найдено сегментов <trans-unit>")

        self.header, self.footer = get_header_footer(xml_bytes, self.trans_units)

        logger.info(f"Splitter initialized: {len(self.trans_units)} segments found")

    def split(self, parts_count: int) -> List[bytes]:
        """
        Разделяет файл на указанное количество частей

        Args:
            parts_count: Количество частей для разделения

        Returns:
            Список частей в виде байтов
        """
        if parts_count < 2:
            raise ValueError("Количество частей должно быть не менее 2")

        if parts_count > len(self.trans_units):
            raise ValueError(
                f"Количество частей ({parts_count}) превышает количество сегментов ({len(self.trans_units)})")

        # Рассчитываем количество сегментов на часть
        segments_per_part = len(self.trans_units) // parts_count
        remainder = len(self.trans_units) % parts_count

        parts = []
        start_idx = 0

        for i in range(parts_count):
            # Добавляем дополнительный сегмент к первым частям если есть остаток
            current_segments = segments_per_part + (1 if i < remainder else 0)
            end_idx = start_idx + current_segments

            # Извлекаем сегменты для текущей части
            part_units = self.trans_units[start_idx:end_idx]

            # Собираем часть
            part_content = self._create_part(part_units)
            parts.append(part_content)

            start_idx = end_idx

        logger.info(f"Split into {parts_count} parts successfully")
        return parts

    def calculate_parts_by_words(self, words_per_part: int) -> int:
        """
        Рассчитывает количество частей на основе количества слов

        Args:
            words_per_part: Желаемое количество слов на часть

        Returns:
            Количество частей
        """
        total_words = 0

        for unit in self.trans_units:
            unit_bytes = self.xml_bytes[unit.start():unit.end()]
            word_count = extract_source_word_count(unit_bytes)
            total_words += word_count

        if total_words == 0:
            return 1

        parts_count = max(1, (total_words + words_per_part - 1) // words_per_part)

        logger.info(f"Calculated {parts_count} parts for {words_per_part} words per part (total: {total_words} words)")
        return parts_count

    def split_by_words(self, words_per_part: int) -> List[bytes]:
        """
        Разделяет файл по количеству слов на часть

        Args:
            words_per_part: Количество слов на часть

        Returns:
            Список частей в виде байтов
        """
        parts = []
        current_units = []
        current_words = 0

        for unit in self.trans_units:
            unit_bytes = self.xml_bytes[unit.start():unit.end()]
            word_count = extract_source_word_count(unit_bytes)

            # Если добавление этого сегмента превысит лимит и у нас уже есть сегменты
            if current_words + word_count > words_per_part and current_units:
                # Создаем часть из накопленных сегментов
                part_content = self._create_part(current_units)
                parts.append(part_content)

                # Начинаем новую часть
                current_units = [unit]
                current_words = word_count
            else:
                # Добавляем сегмент к текущей части
                current_units.append(unit)
                current_words += word_count

        # Добавляем последнюю часть если есть сегменты
        if current_units:
            part_content = self._create_part(current_units)
            parts.append(part_content)

        logger.info(f"Split by words: {len(parts)} parts created")
        return parts

    def _create_part(self, units: List) -> bytes:
        """
        Создает часть файла из списка trans-unit

        Args:
            units: Список Match объектов для trans-unit

        Returns:
            Содержимое части в байтах
        """
        if not units:
            raise ValueError("Список сегментов пуст")

        # Собираем контент между первым и последним сегментом
        first_unit = units[0]
        last_unit = units[-1]

        # Берем все от начала первого сегмента до конца последнего
        content_start = first_unit.start()
        content_end = last_unit.end()
        content = self.xml_bytes[content_start:content_end]

        # Собираем полную часть
        part = self.header + content + self.footer

        return part

    def get_segments_count(self) -> int:
        """Возвращает количество сегментов в файле"""
        return len(self.trans_units)

    def get_header(self) -> bytes:
        """Возвращает заголовок файла"""
        return self.header

    def get_footer(self) -> bytes:
        """Возвращает подвал файла"""
        return self.footer