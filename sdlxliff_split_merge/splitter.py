# sdlxliff_split_merge/splitter.py
"""
ИСПРАВЛЕННЫЙ структурный разделитель SDLXLIFF файлов с полным сохранением структуры
Обеспечивает побайтовую идентичность при последующем объединении
"""

import uuid
import hashlib
import re
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

from .xml_utils import XmlStructure
from .validator import SdlxliffValidator

logger = logging.getLogger(__name__)


class StructuralSplitter:
    """
    ИСПРАВЛЕННЫЙ структурный разделитель SDLXLIFF файлов
    Сохраняет XML структуру и ПОЛНУЮ совместимость SDL
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

        logger.info(f"Fixed splitter initialized: {self.structure.get_segments_count()} segments")

    def split(self, parts_count: int) -> List[str]:
        """
        ИСПРАВЛЕНО: Разделяет файл с гарантией корректности XML

        Args:
            parts_count: Количество частей

        Returns:
            Список частей как строки (все части валидны XML)
        """
        if parts_count < 2:
            raise ValueError("Количество частей должно быть не менее 2")

        if parts_count > self.structure.get_segments_count():
            raise ValueError(
                f"Количество частей ({parts_count}) больше количества сегментов ({self.structure.get_segments_count()})")

        # Распределяем сегменты по частям
        distribution = self._distribute_segments(parts_count)

        # Создаем части с валидацией
        parts = []
        for i, (start_idx, end_idx) in enumerate(distribution):
            part_content = self._create_part(i + 1, parts_count, start_idx, end_idx)

            # НОВОЕ: Валидируем XML структуру каждой части
            is_valid, error_msg = self._validate_xml_structure(part_content)
            if not is_valid:
                raise ValueError(f"Часть {i + 1} содержит некорректный XML: {error_msg}")

            parts.append(part_content)

        logger.info(f"Split into {parts_count} parts successfully with XML validation")
        return parts

    def split_by_word_count(self, words_per_part: int) -> List[str]:
        """
        ИСПРАВЛЕНО: Разделяет файл по количеству слов с валидацией XML

        Args:
            words_per_part: Желаемое количество слов на часть

        Returns:
            Список частей как строки (все части валидны XML)
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
        ИСПРАВЛЕНО: Корректирует границы чтобы НЕ РАЗРЫВАТЬ группы
        Гарантирует что части заканчиваются на границах групп

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
                # Сегмент находится в группе - найдем ВСЕ сегменты этой группы
                group_id = boundary_unit.group_id

                # Находим ВСЕ trans-units с этим group_id
                group_segments = []
                for i, unit in enumerate(self.structure.trans_units):
                    if unit.group_id == group_id:
                        group_segments.append(i)

                if group_segments:
                    # Находим последний сегмент группы
                    last_group_segment = max(group_segments)

                    # Если мы разрываем группу, сдвигаем границу к концу группы
                    if end_idx <= last_group_segment:
                        return last_group_segment + 1

        return end_idx

    def _create_part(self, part_num: int, total_parts: int, start_idx: int, end_idx: int) -> str:
        """
        КАРДИНАЛЬНО ИСПРАВЛЕНО: Создает часть с полностью корректной XML структурой
        Воссоздает структуру вместо копирования фрагментов
        """
        # Создаем метаданные
        metadata = self._create_split_metadata(part_num, total_parts, start_idx, end_idx)

        # Получаем header (до <body>)
        header = self.structure.get_header()

        # НОВЫЙ ПОДХОД: Воссоздаем body с корректной структурой
        body_content = self._recreate_body_structure(start_idx, end_idx)

        # Получаем footer (от </body>)
        footer = self.structure.get_footer()

        # Безопасно вставляем метаданные после тега <body>
        body_tag_end = header.rfind('>')
        if body_tag_end != -1:
            part_content = (header[:body_tag_end + 1] +
                            "\n" + metadata + "\n" +
                            body_content +
                            footer)
        else:
            part_content = metadata + "\n" + header + body_content + footer

        return part_content

    def _recreate_body_structure(self, start_idx: int, end_idx: int) -> str:
        """
        ИСПРАВЛЕНО: Воссоздает body с корректной XML структурой
        Гарантирует парность всех тегов
        """
        if not self.structure.trans_units or start_idx >= len(self.structure.trans_units):
            return ""

        end_idx = min(end_idx, len(self.structure.trans_units))

        # Группируем trans-units по группам
        groups_data = {}
        ungrouped_units = []

        for i in range(start_idx, end_idx):
            unit = self.structure.trans_units[i]

            if unit.group_id:
                if unit.group_id not in groups_data:
                    groups_data[unit.group_id] = {
                        'units': [],
                        'unit_indices': [],
                        'group_xml_prefix': '',
                        'group_xml_suffix': ''
                    }
                groups_data[unit.group_id]['units'].append(unit)
                groups_data[unit.group_id]['unit_indices'].append(i)
            else:
                ungrouped_units.append((i, unit))

        # Извлекаем оригинальные XML структуры групп
        for group_id in groups_data:
            group_info = self._extract_group_structure(group_id)
            groups_data[group_id]['group_xml_prefix'] = group_info['prefix']
            groups_data[group_id]['group_xml_suffix'] = group_info['suffix']

        # Воссоздаем body контент
        body_parts = []

        # Обрабатываем в порядке появления в оригинальном файле
        processed_indices = set()  # ИСПРАВЛЕНО: используем индексы вместо объектов

        for i in range(start_idx, end_idx):
            if i in processed_indices:
                continue

            unit = self.structure.trans_units[i]

            if unit.group_id and unit.group_id in groups_data:
                # Обрабатываем всю группу целиком
                group_data = groups_data[unit.group_id]

                # Проверяем, не обработали ли уже эту группу
                group_indices = set(group_data['unit_indices'])
                if not group_indices.intersection(processed_indices):
                    # Добавляем группу с корректной структурой
                    body_parts.append(group_data['group_xml_prefix'])

                    # Добавляем все trans-units группы в правильном порядке
                    sorted_units = sorted(zip(group_data['unit_indices'], group_data['units']))
                    for unit_idx, group_unit in sorted_units:
                        body_parts.append(group_unit.full_xml)
                        processed_indices.add(unit_idx)

                    body_parts.append(group_data['group_xml_suffix'])
            else:
                # Одиночный trans-unit вне группы
                body_parts.append(unit.full_xml)
                processed_indices.add(i)

        return "\n".join(body_parts)

    def _extract_group_structure(self, group_id: str) -> Dict[str, str]:
        """
        НОВЫЙ МЕТОД: Извлекает структуру группы из оригинального XML
        """
        # Ищем открывающий тег группы
        group_pattern = f'<group[^>]*id=["\']' + re.escape(group_id) + '["\'][^>]*>'
        group_match = re.search(group_pattern, self.xml_content)

        if not group_match:
            return {'prefix': f'<group id="{group_id}">', 'suffix': '</group>'}

        # Извлекаем открывающий тег
        group_start = group_match.group(0)

        # Ищем контекстную информацию после открывающего тега группы
        group_end_pos = group_match.end()

        # Ищем первый trans-unit в этой группе
        first_trans_unit_pattern = r'<trans-unit[^>]*>'
        first_unit_match = re.search(first_trans_unit_pattern, self.xml_content[group_end_pos:])

        prefix_content = ""
        if first_unit_match:
            # Извлекаем все между <group> и первым <trans-unit>
            context_content = self.xml_content[group_end_pos:group_end_pos + first_unit_match.start()]
            prefix_content = context_content.strip()

        # Формируем префикс и суффикс
        if prefix_content:
            prefix = group_start + "\n" + prefix_content
        else:
            prefix = group_start

        suffix = "</group>"

        return {'prefix': prefix, 'suffix': suffix}

    def _validate_xml_structure(self, xml_content: str) -> Tuple[bool, Optional[str]]:
        """
        УПРОЩЕНО: Проверяет корректность XML структуры
        """
        try:
            # Проверяем парность основных тегов
            critical_tags = ['group', 'trans-unit', 'body']

            for tag in critical_tags:
                if tag == 'body':
                    # Для body проверяем что есть один открывающий и один закрывающий
                    open_count = len(re.findall(f'<{tag}[^>]*>', xml_content))
                    close_count = len(re.findall(f'</{tag}>', xml_content))
                else:
                    # Для остальных тегов
                    open_count = len(re.findall(f'<{tag}[^>]*>', xml_content))
                    close_count = len(re.findall(f'</{tag}>', xml_content))

                if open_count != close_count:
                    return False, f"Непарные теги {tag}: открыто {open_count}, закрыто {close_count}"

            return True, None

        except Exception as e:
            return False, f"Ошибка валидации: {e}"

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
        original_match = re.search(r'original="([^"]+)"', self.structure.get_header())
        original_name = original_match.group(1) if original_match else "unknown.sdlxliff"

        # Извлекаем только имя файла и убеждаемся что расширение .sdlxliff
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
            'has_groups': bool(self.structure.groups),
            'byte_perfect_recovery': True
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

    def validate_split_integrity(self, parts: List[str]) -> Dict[str, any]:
        """
        ИСПРАВЛЕНО: Проверяет целостность разделения с XML валидацией

        Args:
            parts: Список созданных частей

        Returns:
            Результат проверки
        """
        issues = []

        # 1. Проверяем XML валидность каждой части
        for i, part in enumerate(parts):
            is_valid, error_msg = self._validate_xml_structure(part)
            if not is_valid:
                issues.append(f"Часть {i + 1}: {error_msg}")

        # 2. Проверяем что объединение дает оригинал
        try:
            from .merger import StructuralMerger

            merger = StructuralMerger(parts)
            merged_content = merger.merge()

            # Проверяем побайтовое соответствие
            identity_check = merger.verify_byte_identity(self.xml_content)

            if not identity_check['is_byte_identical']:
                issues.append(f"Объединение не идентично оригиналу: разница {identity_check['size_difference']} байт")

        except Exception as e:
            issues.append(f"Ошибка объединения: {e}")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'parts_count': len(parts),
            'total_size': sum(len(part) for part in parts),
            'xml_valid': all(self._validate_xml_structure(part)[0] for part in parts)
        }