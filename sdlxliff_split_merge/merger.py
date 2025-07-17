# sdlxliff_split_merge/merger.py
"""
Структурный объединитель SDLXLIFF файлов с поддержкой переводов
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from .xml_utils import XmlStructure, TransUnitParser
from .validator import SdlxliffValidator

logger = logging.getLogger(__name__)


class StructuralMerger:
    """
    Структурный объединитель SDLXLIFF файлов
    Поддерживает объединение переведенных частей с сохранением переводов
    """

    def __init__(self, parts_content: List[str]):
        """
        Инициализация объединителя

        Args:
            parts_content: Список содержимого частей как строки
        """
        self.parts_content = parts_content
        self.validator = SdlxliffValidator()

        # Валидируем части
        is_valid, error_msg = self.validator.validate_split_parts(parts_content)
        if not is_valid:
            raise ValueError(f"Некорректные части для объединения: {error_msg}")

        # Извлекаем метаданные
        self.parts_metadata = []
        for content in parts_content:
            metadata = self.validator._extract_split_metadata(content)
            self.parts_metadata.append(metadata)

        # Сортируем части по номерам
        self.sorted_parts = self._sort_parts()

        logger.info(f"Merger initialized with {len(parts_content)} parts")

    def merge(self) -> str:
        """
        Объединяет части в единый файл

        Returns:
            Объединенный SDLXLIFF файл как строка
        """
        # Получаем базовую структуру из первой части
        base_structure = self._get_base_structure()

        # Собираем все trans-units с переводами
        all_trans_units = self._collect_all_trans_units()

        # Создаем объединенный файл
        merged_content = self._create_merged_file(base_structure, all_trans_units)

        # Валидируем результат
        is_valid, error_msg = self.validator.validate_merged_file(merged_content)
        if not is_valid:
            logger.warning(f"Merged file validation warning: {error_msg}")

        logger.info("Merge completed successfully")
        return merged_content

    def _sort_parts(self) -> List[Tuple[str, Dict[str, str]]]:
        """
        Сортирует части по номерам

        Returns:
            Список кортежей (content, metadata) отсортированных по номерам
        """
        parts_with_metadata = list(zip(self.parts_content, self.parts_metadata))

        # Сортируем по номеру части
        return sorted(parts_with_metadata, key=lambda x: int(x[1]['part_number']))

    def _get_base_structure(self) -> Dict[str, str]:
        """
        Извлекает базовую структуру из первой части

        Returns:
            Словарь с header и footer
        """
        first_part_content = self.sorted_parts[0][0]

        # Удаляем метаданные разделения
        clean_content = re.sub(
            r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
            '',
            first_part_content,
            flags=re.DOTALL
        )

        # Парсим структуру
        structure = XmlStructure(clean_content)

        return {
            'header': structure.get_header(),
            'footer': structure.get_footer(),
            'encoding': structure.encoding
        }

    def _collect_all_trans_units(self) -> List[Dict[str, any]]:
        """
        Собирает все trans-units из всех частей с сохранением переводов

        Returns:
            Список словарей с информацией о trans-units
        """
        all_trans_units = []

        for part_content, metadata in self.sorted_parts:
            # Удаляем метаданные
            clean_content = re.sub(
                r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
                '',
                part_content,
                flags=re.DOTALL
            )

            # Парсим структуру части
            structure = XmlStructure(clean_content)

            # Добавляем информацию о части к каждому trans-unit
            for trans_unit in structure.trans_units:
                unit_info = {
                    'trans_unit': trans_unit,
                    'part_number': int(metadata['part_number']),
                    'original_index': self._calculate_original_index(trans_unit, metadata)
                }
                all_trans_units.append(unit_info)

        # Сортируем по оригинальному индексу
        all_trans_units.sort(key=lambda x: x['original_index'])

        return all_trans_units

    def _calculate_original_index(self, trans_unit, metadata: Dict[str, str]) -> int:
        """
        Вычисляет оригинальный индекс trans-unit в исходном файле

        Args:
            trans_unit: TransUnit объект
            metadata: Метаданные части

        Returns:
            Оригинальный индекс
        """
        # Находим позицию в текущей части
        part_content = next(content for content, meta in self.sorted_parts
                            if meta['part_number'] == metadata['part_number'])

        clean_content = re.sub(
            r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
            '',
            part_content,
            flags=re.DOTALL
        )

        structure = XmlStructure(clean_content)

        # Находим индекс в части
        part_index = None
        for i, unit in enumerate(structure.trans_units):
            if unit.id == trans_unit.id:
                part_index = i
                break

        if part_index is None:
            logger.warning(f"Could not find trans-unit {trans_unit.id} in part")
            return 0

        # Вычисляем оригинальный индекс
        first_segment_index = int(metadata['first_segment_index'])
        return first_segment_index + part_index

    def _create_merged_file(self, base_structure: Dict[str, str],
                            all_trans_units: List[Dict[str, any]]) -> str:
        """
        Создает объединенный файл БЕЗ ИЗМЕНЕНИЯ структуры SDL
        """
        # Начинаем с header
        merged_content = base_structure['header']

        # Добавляем все trans-units В ТОЧНОСТИ как они были
        for unit_info in all_trans_units:
            trans_unit = unit_info['trans_unit']

            # Добавляем trans-unit БЕЗ ИЗМЕНЕНИЙ отступов и структуры
            # SDL очень чувствителен к форматированию!
            merged_content += trans_unit.full_xml

        # Добавляем footer
        merged_content += base_structure['footer']

        return merged_content

    def _indent_trans_unit(self, xml_content: str, indent_level: int) -> str:
        """
        Добавляет правильные отступы к trans-unit

        Args:
            xml_content: XML содержимое trans-unit
            indent_level: Уровень отступов

        Returns:
            XML с правильными отступами
        """
        indent = "  " * indent_level
        lines = xml_content.split('\n')

        # Добавляем отступы к каждой строке
        indented_lines = []
        for line in lines:
            if line.strip():
                indented_lines.append(indent + line.strip())

        return '\n'.join(indented_lines)

    def get_merge_info(self) -> Dict[str, any]:
        """
        Возвращает информацию об объединении

        Returns:
            Словарь с информацией
        """
        if not self.parts_metadata:
            return {}

        first_metadata = self.parts_metadata[0]

        # Подсчитываем статистику
        total_segments = 0
        total_words = 0
        translated_segments = 0

        for part_content, metadata in self.sorted_parts:
            clean_content = re.sub(
                r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
                '',
                part_content,
                flags=re.DOTALL
            )

            structure = XmlStructure(clean_content)
            total_segments += structure.get_segments_count()
            total_words += structure.get_word_count()
            translated_segments += structure.get_translated_count()

        return {
            'split_id': first_metadata.get('split_id'),
            'original_name': first_metadata.get('original_name'),
            'parts_count': len(self.sorted_parts),
            'total_segments': total_segments,
            'total_words': total_words,
            'translated_segments': translated_segments,
            'translation_progress': (translated_segments / total_segments * 100) if total_segments > 0 else 0,
            'merged_at': datetime.utcnow().isoformat() + "Z",
            'encoding': first_metadata.get('encoding', 'utf-8')
        }

    def get_translation_stats(self) -> Dict[str, any]:
        """
        Возвращает детальную статистику переводов

        Returns:
            Словарь со статистикой
        """
        stats = {
            'total_segments': 0,
            'translated_segments': 0,
            'approved_segments': 0,
            'empty_segments': 0,
            'parts_stats': []
        }

        for part_content, metadata in self.sorted_parts:
            clean_content = re.sub(
                r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
                '',
                part_content,
                flags=re.DOTALL
            )

            structure = XmlStructure(clean_content)

            part_stats = {
                'part_number': int(metadata['part_number']),
                'segments_count': structure.get_segments_count(),
                'translated_count': structure.get_translated_count(),
                'approved_count': sum(1 for unit in structure.trans_units if unit.approved),
                'empty_count': sum(1 for unit in structure.trans_units if not unit.target_text.strip())
            }

            stats['parts_stats'].append(part_stats)
            stats['total_segments'] += part_stats['segments_count']
            stats['translated_segments'] += part_stats['translated_count']
            stats['approved_segments'] += part_stats['approved_count']
            stats['empty_segments'] += part_stats['empty_count']

        return stats

    def validate_translation_completeness(self) -> Tuple[bool, List[str]]:
        """
        Проверяет полноту переводов

        Returns:
            Кортеж (is_complete, missing_segments_ids)
        """
        missing_segments = []

        for part_content, metadata in self.sorted_parts:
            clean_content = re.sub(
                r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
                '',
                part_content,
                flags=re.DOTALL
            )

            structure = XmlStructure(clean_content)

            for trans_unit in structure.trans_units:
                if not trans_unit.target_text.strip():
                    missing_segments.append(trans_unit.id)

        return len(missing_segments) == 0, missing_segments