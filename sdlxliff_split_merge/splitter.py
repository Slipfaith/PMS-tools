# sdlxliff_split_merge/splitter.py
"""
Структурный разделитель SDLXLIFF файлов с поддержкой переводов
"""

import uuid
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

from .xml_utils import XmlStructure
from .validator import SdlxliffValidator

logger = logging.getLogger(__name__)


class StructuralSplitter:
    """
    Структурный разделитель SDLXLIFF файлов
    Сохраняет XML структуру и поддерживает последующее объединение переводов
    """

    def __init__(self, xml_content: str):
        """
        Инициализация разделителя

        Args:
            xml_content: Содержимое SDLXLIFF файла как строка
        """
        self.xml_content = xml_content
        self.validator = SdlxliffValidator()

        # Валидируем файл
        is_valid, error_msg = self.validator.validate(xml_content)
        if not is_valid:
            raise ValueError(f"Некорректный SDLXLIFF файл: {error_msg}")

        # Парсим структуру
        self.structure = XmlStructure(xml_content)

        # Метаданные для разделения
        self.split_id = str(uuid.uuid4())
        self.original_checksum = hashlib.md5(xml_content.encode(self.structure.encoding)).hexdigest()
        self.split_timestamp = datetime.utcnow().isoformat() + "Z"

        logger.info(f"Splitter initialized: {self.structure.get_segments_count()} segments")

    def split(self, parts_count: int) -> List[str]:
        """
        Разделяет файл на указанное количество частей

        Args:
            parts_count: Количество частей

        Returns:
            Список частей как строки
        """
        if parts_count < 2:
            raise ValueError("Количество частей должно быть не менее 2")

        if parts_count > self.structure.get_segments_count():
            raise ValueError(
                f"Количество частей ({parts_count}) больше количества сегментов ({self.structure.get_segments_count()})")

        # Распределяем сегменты по частям
        distribution = self._distribute_segments(parts_count)

        # Создаем части
        parts = []
        for i, (start_idx, end_idx) in enumerate(distribution):
            part_content = self._create_part(i + 1, parts_count, start_idx, end_idx)
            parts.append(part_content)

        logger.info(f"Split into {parts_count} parts successfully")
        return parts

    def split_by_word_count(self, words_per_part: int) -> List[str]:
        """
        Разделяет файл по количеству слов на часть

        Args:
            words_per_part: Желаемое количество слов на часть

        Returns:
            Список частей как строки
        """
        if words_per_part < 10:
            raise ValueError("Количество слов на часть должно быть не менее 10")

        total_words = self.structure.get_word_count()
        if total_words == 0:
            raise ValueError("В файле нет слов для разделения")

        # Рассчитываем количество частей
        parts_count = max(1, (total_words + words_per_part - 1) // words_per_part)

        logger.info(f"Calculated {parts_count} parts for {words_per_part} words per part (total: {total_words} words)")

        return self.split(parts_count)

    def _distribute_segments(self, parts_count: int) -> List[Tuple[int, int]]:
        """
        Распределяет сегменты по частям с учетом групп

        Args:
            parts_count: Количество частей

        Returns:
            Список кортежей (start_index, end_index) для каждой части
        """
        total_segments = self.structure.get_segments_count()
        segments_per_part = total_segments // parts_count
        remainder = total_segments % parts_count

        distribution = []
        current_idx = 0

        for i in range(parts_count):
            # Добавляем дополнительный сегмент к первым частям если есть остаток
            part_size = segments_per_part + (1 if i < remainder else 0)
            end_idx = min(current_idx + part_size, total_segments)

            # Корректируем границы с учетом групп
            end_idx = self._adjust_for_groups(current_idx, end_idx, total_segments)

            distribution.append((current_idx, end_idx))
            current_idx = end_idx

        # Убеждаемся, что последняя часть включает все оставшиеся сегменты
        if distribution and distribution[-1][1] < total_segments:
            distribution[-1] = (distribution[-1][0], total_segments)

        return distribution

    def _adjust_for_groups(self, start_idx: int, end_idx: int, total_segments: int) -> int:
        """
        Корректирует границы чтобы не разрывать группы

        Args:
            start_idx: Начальный индекс
            end_idx: Желаемый конечный индекс
            total_segments: Общее количество сегментов

        Returns:
            Скорректированный конечный индекс
        """
        if end_idx >= total_segments:
            return total_segments

        # Проверяем, находится ли граница внутри группы
        if end_idx > 0 and end_idx < len(self.structure.trans_units):
            boundary_unit = self.structure.trans_units[end_idx - 1]

            if boundary_unit.group_id is not None:
                # Сегмент находится в группе - найдем конец группы
                group_id = boundary_unit.group_id

                # Находим последний сегмент этой группы
                for i in range(end_idx, len(self.structure.trans_units)):
                    if self.structure.trans_units[i].group_id != group_id:
                        return i

                # Если дошли до конца - возвращаем общую длину
                return total_segments

        return end_idx

    def _create_part(self, part_num: int, total_parts: int, start_idx: int, end_idx: int) -> str:
        """
        Создает часть файла с метаданными БЕЗ НАРУШЕНИЯ SDL структуры
        """
        # Создаем метаданные
        metadata = self._create_split_metadata(part_num, total_parts, start_idx, end_idx)

        # Получаем компоненты БЕЗ ИЗМЕНЕНИЙ
        header = self.structure.get_header()
        body_content = self.structure.get_body_content(start_idx, end_idx)
        footer = self.structure.get_footer()

        # Вставляем метаданные ПОСЛЕ header, но ДО body
        # Это безопаснее для SDL
        header_body_split = header.rfind('>')
        if header_body_split != -1:
            safe_header = header[:header_body_split + 1]
            remaining_header = header[header_body_split + 1:]

            # Собираем полную часть с метаданными в безопасном месте
            part_content = (safe_header +
                            "\n" + metadata + "\n" +
                            remaining_header +
                            body_content +
                            footer)
        else:
            # Fallback - добавляем в начало
            part_content = metadata + "\n" + header + body_content + footer

        return part_content

    def _create_split_metadata(self, part_num: int, total_parts: int, start_idx: int, end_idx: int) -> str:
        """
        Создает метаданные для части

        Args:
            part_num: Номер части
            total_parts: Общее количество частей
            start_idx: Начальный индекс сегмента
            end_idx: Конечный индекс сегмента

        Returns:
            XML комментарий с метаданными
        """
        # Получаем имя оригинального файла из header
        import re
        original_match = re.search(r'original="([^"]+)"', self.structure.get_header())
        original_name = original_match.group(1) if original_match else "unknown.sdlxliff"

        # Извлекаем только имя файла и убеждаемся что расширение .sdlxliff
        import os
        original_name = os.path.basename(original_name)
        if not original_name.lower().endswith('.sdlxliff'):
            # Если имя содержит другое расширение (например .xlsx), заменяем на .sdlxliff
            original_name = os.path.splitext(original_name)[0] + '.sdlxliff'

        # Статистика части
        part_segments = end_idx - start_idx
        part_words = sum(len(self.structure.trans_units[i].source_text.split())
                         for i in range(start_idx, end_idx))

        metadata = f"""<!-- SDLXLIFF_SPLIT_METADATA:
     split_id="{self.split_id}"
     part_number="{part_num}"
     total_parts="{total_parts}"
     original_name="{original_name}"
     split_timestamp="{self.split_timestamp}"
     first_segment_index="{start_idx}"
     last_segment_index="{end_idx - 1}"
     part_segments_count="{part_segments}"
     part_words_count="{part_words}"
     total_segments_count="{self.structure.get_segments_count()}"
     total_words_count="{self.structure.get_word_count()}"
     original_checksum="{self.original_checksum}"
     encoding="{self.structure.encoding}"
-->"""

        return metadata

    def get_split_info(self) -> Dict[str, any]:
        """
        Возвращает информацию о разделении

        Returns:
            Словарь с информацией
        """
        return {
            'split_id': self.split_id,
            'original_checksum': self.original_checksum,
            'split_timestamp': self.split_timestamp,
            'total_segments': self.structure.get_segments_count(),
            'total_words': self.structure.get_word_count(),
            'translated_segments': self.structure.get_translated_count(),
            'encoding': self.structure.encoding,
            'has_groups': bool(self.structure.groups)
        }

    def estimate_parts_by_words(self, words_per_part: int) -> int:
        """
        Оценивает количество частей при разделении по словам

        Args:
            words_per_part: Слов на часть

        Returns:
            Предполагаемое количество частей
        """
        total_words = self.structure.get_word_count()
        if total_words == 0:
            return 1

        return max(1, (total_words + words_per_part - 1) // words_per_part)

    def get_segments_distribution(self, parts_count: int) -> List[Dict[str, any]]:
        """
        Возвращает подробную информацию о распределении сегментов

        Args:
            parts_count: Количество частей

        Returns:
            Список словарей с информацией о каждой части
        """
        distribution = self._distribute_segments(parts_count)

        result = []
        for i, (start_idx, end_idx) in enumerate(distribution):
            part_segments = end_idx - start_idx
            part_words = sum(len(self.structure.trans_units[j].source_text.split())
                             for j in range(start_idx, end_idx))

            # Определяем группы в части
            groups_in_part = set()
            for j in range(start_idx, end_idx):
                if self.structure.trans_units[j].group_id:
                    groups_in_part.add(self.structure.trans_units[j].group_id)

            result.append({
                'part_number': i + 1,
                'start_index': start_idx,
                'end_index': end_idx - 1,
                'segments_count': part_segments,
                'words_count': part_words,
                'groups_count': len(groups_in_part),
                'groups': list(groups_in_part)
            })

        return result