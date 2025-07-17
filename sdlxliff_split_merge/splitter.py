# sdlxliff_split_merge/splitter.py
"""
Модуль для разделения SDLXLIFF файлов на части с сохранением структуры
"""

import re
import uuid
import hashlib
from datetime import datetime
from typing import List, Tuple, Dict, Optional
import logging
import xml.etree.ElementTree as ET

from .xml_utils import find_trans_units_and_groups, extract_source_word_count, get_header_footer

logger = logging.getLogger(__name__)


class Splitter:
    """
    Разделитель SDLXLIFF файлов на части с сохранением структуры и валидности
    """

    def __init__(self, xml_bytes: bytes):
        """
        Инициализация с содержимым SDLXLIFF файла

        Args:
            xml_bytes: Содержимое SDLXLIFF файла в байтах
        """
        self.xml_bytes = xml_bytes
        self.xml_str = xml_bytes.decode('utf-8')

        # Парсим структуру файла
        self.structure = find_trans_units_and_groups(xml_bytes)

        if not self.structure['trans_units']:
            raise ValueError("В файле не найдено сегментов <trans-unit>")

        # Получаем header и footer
        self.header, self.footer = self._extract_header_footer()

        # Генерируем метаданные для split операции
        self.split_guid = str(uuid.uuid4())
        self.original_checksum = hashlib.md5(xml_bytes).hexdigest()

        logger.info(f"Splitter initialized: {len(self.structure['trans_units'])} trans-units, "
                    f"{len(self.structure['groups'])} groups found")

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

        # Распределяем trans-units по частям с учетом групп
        distribution = self._distribute_units(parts_count)

        # Создаем части
        parts = []
        for i, (start_idx, end_idx) in enumerate(distribution):
            part_content = self._create_part(i + 1, parts_count, start_idx, end_idx)
            parts.append(part_content)

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

        for unit in self.structure['trans_units']:
            unit_match = unit['match']
            unit_bytes = self.xml_bytes[unit_match.start():unit_match.end()]
            word_count = extract_source_word_count(unit_bytes)
            total_words += word_count

        if total_words == 0:
            return 1

        parts_count = max(1, (total_words + words_per_part - 1) // words_per_part)

        logger.info(f"Calculated {parts_count} parts for {words_per_part} words per part "
                    f"(total: {total_words} words)")
        return parts_count

    def _extract_header_footer(self) -> Tuple[str, str]:
        """
        Извлекает header и footer из XML

        Returns:
            Кортеж (header, footer) как строки
        """
        # Находим позицию <body>
        body_start = self.xml_str.find('<body>')
        body_end = self.xml_str.find('</body>') + len('</body>')

        if body_start == -1 or body_end == -1:
            raise ValueError("Не найдены теги <body> в файле")

        # Header - все до <body> включая сам тег
        header = self.xml_str[:body_start + len('<body>')]

        # Footer - все после </body>
        footer = self.xml_str[body_end:]

        return header, footer

    def _distribute_units(self, parts_count: int) -> List[Tuple[int, int]]:
        """
        Распределяет trans-units по частям с учетом групп

        Args:
            parts_count: Количество частей

        Returns:
            Список кортежей (start_index, end_index) для каждой части
        """
        total_units = len(self.structure['trans_units'])
        units_per_part = total_units // parts_count
        remainder = total_units % parts_count

        distribution = []
        current_idx = 0

        for i in range(parts_count):
            # Добавляем дополнительный unit к первым частям если есть остаток
            part_size = units_per_part + (1 if i < remainder else 0)
            end_idx = current_idx + part_size

            # Корректируем границы с учетом групп
            end_idx = self._adjust_for_groups(current_idx, end_idx)

            distribution.append((current_idx, end_idx))
            current_idx = end_idx

        # Убеждаемся, что последняя часть включает все оставшиеся units
        if distribution and distribution[-1][1] < total_units:
            distribution[-1] = (distribution[-1][0], total_units)

        return distribution

    def _adjust_for_groups(self, start_idx: int, end_idx: int) -> int:
        """
        Корректирует end_idx чтобы не разрывать группы

        Args:
            start_idx: Начальный индекс
            end_idx: Желаемый конечный индекс

        Returns:
            Скорректированный конечный индекс
        """
        if end_idx >= len(self.structure['trans_units']):
            return len(self.structure['trans_units'])

        # Проверяем, находится ли unit на границе внутри группы
        boundary_unit = self.structure['trans_units'][end_idx - 1]

        if boundary_unit['group_id'] is not None:
            # Unit находится в группе - включаем всю группу
            group_id = boundary_unit['group_id']

            # Находим последний unit этой группы
            for i in range(end_idx, len(self.structure['trans_units'])):
                if self.structure['trans_units'][i]['group_id'] != group_id:
                    return i

            # Если дошли до конца - возвращаем длину
            return len(self.structure['trans_units'])

        return end_idx

    def _create_part(self, part_num: int, total_parts: int,
                     start_idx: int, end_idx: int) -> bytes:
        """
        Создает часть файла

        Args:
            part_num: Номер части (начиная с 1)
            total_parts: Общее количество частей
            start_idx: Начальный индекс trans-unit
            end_idx: Конечный индекс trans-unit (не включительно)

        Returns:
            Содержимое части в байтах
        """
        # Создаем метаданные
        split_info = self._create_split_metadata(part_num, total_parts, start_idx, end_idx)

        # Вставляем метаданные после XML декларации
        xml_decl_end = self.header.find('?>') + 2
        header_with_meta = (
                self.header[:xml_decl_end] +
                f"\n{split_info}" +
                self.header[xml_decl_end:]
        )

        # Собираем контент части
        body_content = self._extract_body_content(start_idx, end_idx)

        # Собираем полную часть
        part_xml = header_with_meta + '\n' + body_content + '\n' + self.footer

        return part_xml.encode('utf-8')

    def _create_split_metadata(self, part_num: int, total_parts: int,
                               start_idx: int, end_idx: int) -> str:
        """
        Создает XML комментарий с метаданными разделения
        """
        # Получаем имя оригинального файла из header
        original_match = re.search(r'original="([^"]+)"', self.header)
        original_name = original_match.group(1) if original_match else "unknown.sdlxliff"

        # Извлекаем только имя файла из полного пути
        import os
        original_name = os.path.basename(original_name)

        metadata = f"""<!-- SDLXLIFF_SPLIT_INFO:
     part="{part_num}"
     total="{total_parts}"
     guid="{self.split_guid}"
     original-name="{original_name}"
     split-date="{datetime.utcnow().isoformat()}Z"
     split-by="trans-unit"
     first-unit="{start_idx + 1}"
     last-unit="{end_idx}"
     total-units="{len(self.structure['trans_units'])}"
     checksum="md5:{self.original_checksum}"
-->"""
        return metadata

    def _extract_body_content(self, start_idx: int, end_idx: int) -> str:
        """
        Извлекает содержимое body для указанного диапазона trans-units

        Args:
            start_idx: Начальный индекс
            end_idx: Конечный индекс (не включительно)

        Returns:
            XML строка с содержимым body
        """
        content_parts = []
        current_group_id = None

        for i in range(start_idx, end_idx):
            unit_info = self.structure['trans_units'][i]

            # Обработка групп
            if unit_info['group_id'] != current_group_id:
                # Закрываем предыдущую группу если нужно
                if current_group_id is not None:
                    content_parts.append('</group>')

                # Открываем новую группу если нужно
                if unit_info['group_id'] is not None:
                    group_info = self.structure['groups'][unit_info['group_id']]
                    group_match = group_info['match']

                    # Извлекаем открывающий тег группы с атрибутами и контекстами
                    group_start = group_match.start()
                    group_content_start = self.xml_bytes.find(b'<trans-unit', group_start)
                    group_header = self.xml_bytes[group_start:group_content_start].decode('utf-8')

                    content_parts.append(group_header.strip())

                current_group_id = unit_info['group_id']

            # Добавляем trans-unit
            unit_match = unit_info['match']
            unit_xml = self.xml_bytes[unit_match.start():unit_match.end()].decode('utf-8')
            content_parts.append(unit_xml)

        # Закрываем последнюю группу если нужно
        if current_group_id is not None:
            content_parts.append('</group>')

        return '\n'.join(content_parts)

    def get_segments_count(self) -> int:
        """Возвращает количество сегментов в файле"""
        return len(self.structure['trans_units'])

    def get_groups_count(self) -> int:
        """Возвращает количество групп в файле"""
        return len(self.structure['groups'])

    def get_split_metadata(self) -> Dict[str, any]:
        """Возвращает метаданные для операции разделения"""
        return {
            'guid': self.split_guid,
            'checksum': self.original_checksum,
            'total_units': len(self.structure['trans_units']),
            'total_groups': len(self.structure['groups']),
            'created_at': datetime.utcnow().isoformat()
        }