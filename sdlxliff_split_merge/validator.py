# sdlxliff_split_merge/validator.py
"""
Валидатор для SDLXLIFF файлов и их частей
"""

import re
import logging
from typing import List, Tuple, Dict, Optional
import hashlib

from .xml_utils import find_trans_units_and_groups, validate_sdlxliff_structure

logger = logging.getLogger(__name__)


class SdlxliffValidator:
    """Валидатор SDLXLIFF файлов с поддержкой split/merge операций"""

    def validate(self, xml_bytes: bytes) -> Tuple[bool, Optional[str]]:
        """
        Полная валидация SDLXLIFF файла

        Args:
            xml_bytes: Содержимое файла

        Returns:
            Кортеж (is_valid, error_message)
        """
        # Базовая структурная валидация
        is_valid, error_msg = validate_sdlxliff_structure(xml_bytes)
        if not is_valid:
            return False, error_msg

        # Проверяем наличие trans-units
        try:
            structure = find_trans_units_and_groups(xml_bytes)
            if not structure['trans_units']:
                return False, "В файле нет сегментов <trans-unit>"

            # Проверяем уникальность ID
            trans_unit_ids = [unit['id'] for unit in structure['trans_units']]
            if len(trans_unit_ids) != len(set(trans_unit_ids)):
                return False, "Обнаружены дублирующиеся ID у trans-unit элементов"

            logger.info(f"Validation successful: {len(structure['trans_units'])} trans-units")
            return True, None

        except Exception as e:
            return False, f"Ошибка при валидации: {str(e)}"

    def is_split_part(self, xml_bytes: bytes) -> bool:
        """
        Проверяет, является ли файл частью разделенного SDLXLIFF

        Args:
            xml_bytes: Содержимое файла

        Returns:
            True если файл содержит метаданные разделения
        """
        xml_str = xml_bytes.decode('utf-8')
        return '<!-- SDLXLIFF_SPLIT_INFO:' in xml_str

    def validate_split_parts(self, parts_bytes: List[bytes]) -> Tuple[bool, Optional[str]]:
        """
        Валидирует набор частей для объединения

        Args:
            parts_bytes: Список содержимого частей

        Returns:
            Кортеж (is_valid, error_message)
        """
        if not parts_bytes:
            return False, "Список частей пуст"

        metadata_list = []

        # Извлекаем и проверяем метаданные из каждой части
        for i, part_bytes in enumerate(parts_bytes):
            # Проверяем, что это часть
            if not self.is_split_part(part_bytes):
                return False, f"Часть {i + 1} не содержит метаданных SDLXLIFF_SPLIT_INFO"

            # Извлекаем метаданные
            metadata = self._extract_split_metadata(part_bytes)
            if not metadata:
                return False, f"Не удалось извлечь метаданные из части {i + 1}"

            metadata_list.append(metadata)

        # Проверяем совместимость
        return self._validate_parts_compatibility(metadata_list)

    def _extract_split_metadata(self, xml_bytes: bytes) -> Optional[Dict[str, str]]:
        """
        Извлекает метаданные разделения из части

        Args:
            xml_bytes: Содержимое части

        Returns:
            Словарь с метаданными или None
        """
        xml_str = xml_bytes.decode('utf-8')

        metadata_match = re.search(
            r'<!-- SDLXLIFF_SPLIT_INFO:(.*?)-->',
            xml_str,
            re.DOTALL
        )

        if not metadata_match:
            return None

        metadata = {}
        metadata_str = metadata_match.group(1)

        for line in metadata_str.strip().split('\n'):
            if '=' in line:
                key, value = line.strip().split('=', 1)
                metadata[key] = value.strip('"')

        return metadata

    def _validate_parts_compatibility(self, metadata_list: List[Dict[str, str]]) -> Tuple[bool, Optional[str]]:
        """
        Проверяет совместимость частей

        Args:
            metadata_list: Список метаданных частей

        Returns:
            Кортеж (is_valid, error_message)
        """
        # Проверяем GUID
        guids = set(m.get('guid', '') for m in metadata_list)
        if len(guids) > 1:
            return False, f"Части принадлежат разным операциям разделения (найдено {len(guids)} разных GUID)"

        if not guids or '' in guids:
            return False, "Отсутствует GUID в метаданных"

        # Проверяем количество частей
        total_parts_set = set(int(m.get('total', 0)) for m in metadata_list)
        if len(total_parts_set) > 1:
            return False, "Несовпадение общего количества частей в метаданных"

        total_parts = total_parts_set.pop() if total_parts_set else 0

        if len(metadata_list) != total_parts:
            return False, f"Неполный набор: найдено {len(metadata_list)} частей, ожидалось {total_parts}"

        # Проверяем номера частей
        part_numbers = []
        for m in metadata_list:
            try:
                part_num = int(m.get('part', 0))
                part_numbers.append(part_num)
            except ValueError:
                return False, "Некорректный номер части в метаданных"

        part_numbers.sort()
        expected = list(range(1, total_parts + 1))

        if part_numbers != expected:
            return False, f"Некорректная последовательность частей: {part_numbers}"

        # Проверяем непрерывность trans-units
        sorted_metadata = sorted(metadata_list, key=lambda m: int(m.get('part', 0)))

        for i in range(len(sorted_metadata) - 1):
            current = sorted_metadata[i]
            next_part = sorted_metadata[i + 1]

            current_last = int(current.get('last-unit', 0))
            next_first = int(next_part.get('first-unit', 0))

            if current_last + 1 != next_first:
                return False, (
                    f"Разрыв в последовательности trans-units между частями {i + 1} и {i + 2}: "
                    f"заканчивается на {current_last}, начинается с {next_first}"
                )

        # Проверяем контрольную сумму (если есть)
        checksums = set(m.get('checksum', '') for m in metadata_list)
        if len(checksums) > 1:
            return False, "Несовпадение контрольных сумм оригинального файла"

        return True, None

    def calculate_checksum(self, xml_bytes: bytes) -> str:
        """
        Вычисляет контрольную сумму файла

        Args:
            xml_bytes: Содержимое файла

        Returns:
            MD5 хеш в виде строки
        """
        return f"md5:{hashlib.md5(xml_bytes).hexdigest()}"

    def validate_merged_file(self, merged_bytes: bytes, original_checksum: Optional[str] = None) -> Tuple[
        bool, Optional[str]]:
        """
        Валидирует объединенный файл

        Args:
            merged_bytes: Содержимое объединенного файла
            original_checksum: Контрольная сумма оригинального файла (опционально)

        Returns:
            Кортеж (is_valid, error_message)
        """
        # Проверяем, что в файле нет метаданных разделения
        if self.is_split_part(merged_bytes):
            return False, "Объединенный файл содержит метаданные разделения"

        # Выполняем полную валидацию
        is_valid, error_msg = self.validate(merged_bytes)
        if not is_valid:
            return False, f"Ошибка валидации объединенного файла: {error_msg}"

        # Проверяем контрольную сумму если предоставлена
        if original_checksum:
            current_checksum = self.calculate_checksum(merged_bytes)
            if current_checksum != original_checksum:
                logger.warning(
                    f"Контрольная сумма объединенного файла ({current_checksum}) "
                    f"не совпадает с оригиналом ({original_checksum})"
                )

        return True, None