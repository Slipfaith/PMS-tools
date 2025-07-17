# sdlxliff_split_merge/validator.py
"""
Мягкий валидатор для SDLXLIFF файлов - проверяет только критически важные элементы
"""

import re
import logging
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)


class SdlxliffValidator:
    """Мягкий валидатор SDLXLIFF файлов"""

    def validate(self, xml_content: str) -> Tuple[bool, Optional[str]]:
        """
        Мягкая валидация SDLXLIFF файла - проверяет только критически важные элементы

        Args:
            xml_content: Содержимое файла как строка

        Returns:
            Кортеж (is_valid, error_message)
        """
        try:
            # 1. Проверяем наличие основных элементов
            if not self._has_xliff_root(xml_content):
                return False, "Отсутствует корневой элемент <xliff>"

            # 2. Проверяем наличие body
            if not self._has_body(xml_content):
                return False, "Отсутствует элемент <body>"

            # 3. Проверяем наличие хотя бы одного trans-unit
            if not self._has_trans_units(xml_content):
                return False, "В файле нет сегментов <trans-unit>"

            # 4. Проверяем базовую структуру trans-units
            if not self._validate_trans_units_structure(xml_content):
                return False, "Обнаружены некорректные trans-unit элементы"

            # 5. Проверяем кодировку
            if not self._validate_encoding(xml_content):
                return False, "Проблемы с кодировкой файла"

            return True, None

        except Exception as e:
            return False, f"Ошибка валидации: {str(e)}"

    def _has_xliff_root(self, xml_content: str) -> bool:
        """Проверяет наличие корневого элемента xliff"""
        return bool(re.search(r'<xliff[^>]*>', xml_content, re.IGNORECASE))

    def _has_body(self, xml_content: str) -> bool:
        """Проверяет наличие элемента body"""
        return bool(re.search(r'<body[^>]*>', xml_content, re.IGNORECASE))

    def _has_trans_units(self, xml_content: str) -> bool:
        """Проверяет наличие trans-unit элементов"""
        return bool(re.search(r'<trans-unit[^>]*>', xml_content, re.IGNORECASE))

    def _validate_trans_units_structure(self, xml_content: str) -> bool:
        """Проверяет базовую структуру trans-unit элементов"""
        # Находим все trans-unit элементы
        trans_units = re.findall(
            r'<trans-unit[^>]*id=["\']([^"\']+)["\'][^>]*>',
            xml_content,
            re.IGNORECASE
        )

        if not trans_units:
            return False

        # Проверяем уникальность ID
        if len(trans_units) != len(set(trans_units)):
            logger.warning("Обнаружены дублирующиеся ID trans-unit (продолжаем)")

        # Проверяем наличие source элементов
        source_count = len(re.findall(r'<source[^>]*>', xml_content, re.IGNORECASE))
        if source_count == 0:
            return False

        return True

    def _validate_encoding(self, xml_content: str) -> bool:
        """Проверяет кодировку файла"""
        try:
            # Пытаемся найти объявление кодировки
            encoding_match = re.search(r'encoding=["\']([^"\']+)["\']', xml_content)
            if encoding_match:
                declared_encoding = encoding_match.group(1).lower()
                logger.info(f"Declared encoding: {declared_encoding}")

            # Проверяем на наличие специальных символов
            if '\x00' in xml_content:
                return False

            return True
        except Exception:
            return False

    def is_split_part(self, xml_content: str) -> bool:
        """
        Проверяет, является ли файл частью разделенного SDLXLIFF

        Args:
            xml_content: Содержимое файла

        Returns:
            True если файл содержит метаданные разделения
        """
        return '<!-- SDLXLIFF_SPLIT_METADATA:' in xml_content

    def validate_split_parts(self, parts_content: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Валидирует набор частей для объединения

        Args:
            parts_content: Список содержимого частей

        Returns:
            Кортеж (is_valid, error_message)
        """
        if not parts_content:
            return False, "Список частей пуст"

        metadata_list = []

        # Извлекаем метаданные из каждой части
        for i, content in enumerate(parts_content):
            if not self.is_split_part(content):
                return False, f"Часть {i + 1} не содержит метаданных разделения"

            metadata = self._extract_split_metadata(content)
            if not metadata:
                return False, f"Не удалось извлечь метаданные из части {i + 1}"

            metadata_list.append(metadata)

        # Проверяем совместимость метаданных
        return self._validate_metadata_compatibility(metadata_list)

    def _extract_split_metadata(self, xml_content: str) -> Optional[Dict[str, str]]:
        """
        Извлекает метаданные разделения из части

        Args:
            xml_content: Содержимое части

        Returns:
            Словарь с метаданными или None
        """
        metadata_match = re.search(
            r'<!-- SDLXLIFF_SPLIT_METADATA:(.*?)-->',
            xml_content,
            re.DOTALL
        )

        if not metadata_match:
            return None

        metadata = {}
        metadata_str = metadata_match.group(1)

        # Парсим метаданные
        for line in metadata_str.strip().split('\n'):
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                metadata[key.strip()] = value.strip().strip('"')

        return metadata

    def _validate_metadata_compatibility(self, metadata_list: List[Dict[str, str]]) -> Tuple[bool, Optional[str]]:
        """
        Проверяет совместимость метаданных частей

        Args:
            metadata_list: Список метаданных частей

        Returns:
            Кортеж (is_valid, error_message)
        """
        # Проверяем GUID
        guids = set(m.get('split_id', '') for m in metadata_list)
        if len(guids) > 1:
            return False, "Части принадлежат разным операциям разделения"

        if not guids or '' in guids:
            return False, "Отсутствует идентификатор разделения"

        # Проверяем количество частей
        total_parts_set = set()
        for m in metadata_list:
            try:
                total_parts_set.add(int(m.get('total_parts', 0)))
            except ValueError:
                return False, "Некорректное количество частей в метаданных"

        if len(total_parts_set) > 1:
            return False, "Несовпадение общего количества частей"

        total_parts = total_parts_set.pop() if total_parts_set else 0

        if len(metadata_list) != total_parts:
            return False, f"Неполный набор: найдено {len(metadata_list)} частей, ожидалось {total_parts}"

        # Проверяем номера частей
        part_numbers = []
        for m in metadata_list:
            try:
                part_num = int(m.get('part_number', 0))
                part_numbers.append(part_num)
            except ValueError:
                return False, "Некорректный номер части"

        part_numbers.sort()
        expected = list(range(1, total_parts + 1))

        if part_numbers != expected:
            return False, f"Некорректная последовательность частей: {part_numbers}"

        # Проверяем непрерывность сегментов
        sorted_metadata = sorted(metadata_list, key=lambda m: int(m.get('part_number', 0)))

        for i in range(len(sorted_metadata) - 1):
            current = sorted_metadata[i]
            next_part = sorted_metadata[i + 1]

            try:
                current_last = int(current.get('last_segment_index', 0))
                next_first = int(next_part.get('first_segment_index', 0))

                if current_last + 1 != next_first:
                    return False, f"Разрыв в последовательности сегментов между частями {i + 1} и {i + 2}"
            except ValueError:
                return False, "Некорректные индексы сегментов в метаданных"

        return True, None

    def validate_merged_file(self, xml_content: str) -> Tuple[bool, Optional[str]]:
        """
        Валидирует объединенный файл

        Args:
            xml_content: Содержимое объединенного файла

        Returns:
            Кортеж (is_valid, error_message)
        """
        # Проверяем, что в файле нет метаданных разделения
        if self.is_split_part(xml_content):
            return False, "Объединенный файл содержит метаданные разделения"

        # Выполняем обычную валидацию
        return self.validate(xml_content)

    def quick_validate(self, xml_content: str) -> bool:
        """
        Быстрая валидация - проверяет только самое необходимое

        Args:
            xml_content: Содержимое файла

        Returns:
            True если файл выглядит как SDLXLIFF
        """
        # Проверяем наличие основных маркеров
        has_xliff = '<xliff' in xml_content.lower()
        has_body = '<body' in xml_content.lower()
        has_trans_unit = '<trans-unit' in xml_content.lower()

        return has_xliff and has_body and has_trans_unit

    def get_file_stats(self, xml_content: str) -> Dict[str, any]:
        """
        Получает базовую статистику файла

        Args:
            xml_content: Содержимое файла

        Returns:
            Словарь со статистикой
        """
        stats = {
            'total_segments': 0,
            'translated_segments': 0,
            'approved_segments': 0,
            'has_groups': False,
            'encoding': 'utf-8'
        }

        try:
            # Подсчитываем сегменты
            trans_units = re.findall(r'<trans-unit[^>]*>', xml_content, re.IGNORECASE)
            stats['total_segments'] = len(trans_units)

            # Подсчитываем переведенные
            targets = re.findall(r'<target[^>]*>.*?</target>', xml_content, re.DOTALL | re.IGNORECASE)
            non_empty_targets = [t for t in targets if re.sub(r'<[^>]*>', '', t).strip()]
            stats['translated_segments'] = len(non_empty_targets)

            # Подсчитываем утвержденные
            approved = re.findall(r'approved="yes"', xml_content, re.IGNORECASE)
            stats['approved_segments'] = len(approved)

            # Проверяем наличие групп
            groups = re.findall(r'<group[^>]*>', xml_content, re.IGNORECASE)
            stats['has_groups'] = len(groups) > 0

            # Определяем кодировку
            encoding_match = re.search(r'encoding=["\']([^"\']+)["\']', xml_content)
            if encoding_match:
                stats['encoding'] = encoding_match.group(1)

        except Exception as e:
            logger.warning(f"Error getting file stats: {e}")

        return stats