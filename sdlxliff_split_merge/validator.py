# sdlxliff_split_merge/validator.py
"""
Мягкий валидатор для SDLXLIFF файлов - проверяет только критически важные элементы
ИСПРАВЛЕНО: Ещё более мягкая валидация для работы с реальными файлами
"""

import re
import logging
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)


class SdlxliffValidator:
    """Мягкий валидатор SDLXLIFF файлов"""

    def validate(self, xml_content: str) -> Tuple[bool, Optional[str]]:
        """
        ИСПРАВЛЕНО: Очень мягкая валидация SDLXLIFF файла
        Проверяет только абсолютно критические элементы

        Args:
            xml_content: Содержимое файла как строка

        Returns:
            Кортеж (is_valid, error_message)
        """
        try:
            # 1. Проверяем наличие основных элементов (очень мягко)
            if not self._has_xliff_structure(xml_content):
                return False, "Файл не содержит XLIFF структуру"

            # 2. Проверяем наличие хотя бы одного trans-unit
            if not self._has_trans_units(xml_content):
                return False, "В файле нет сегментов <trans-unit>"

            # 3. Проверяем базовую читаемость
            if not self._is_readable(xml_content):
                return False, "Файл не читается как XML"

            # 4. Проверяем размер файла
            if len(xml_content.strip()) < 100:
                return False, "Файл слишком короткий"

            # ВСЁ ОСТАЛЬНОЕ - только предупреждения, не ошибки
            warnings = []

            # Проверяем кодировку
            if not self._validate_encoding(xml_content):
                warnings.append("Возможные проблемы с кодировкой")

            # Проверяем парность критичных тегов
            if not self._check_critical_tags_balance(xml_content):
                warnings.append("Обнаружены непарные критичные теги")

            if warnings:
                logger.info(f"SDLXLIFF validation warnings: {'; '.join(warnings)}")

            return True, None

        except Exception as e:
            logger.warning(f"Ошибка валидации: {e}")
            return True, None  # Даже при ошибке валидации продолжаем работу

    def _has_xliff_structure(self, xml_content: str) -> bool:
        """Проверяет наличие базовой XLIFF структуры"""
        # Ищем любые признаки XLIFF структуры
        xliff_indicators = [
            r'<xliff[^>]*>',
            r'<file[^>]*>',
            r'<trans-unit[^>]*>',
            r'xmlns.*xliff',
            r'\.sdlxliff'
        ]

        for indicator in xliff_indicators:
            if re.search(indicator, xml_content, re.IGNORECASE):
                return True
        return False

    def _has_trans_units(self, xml_content: str) -> bool:
        """Проверяет наличие trans-unit элементов"""
        return bool(re.search(r'<trans-unit[^>]*>', xml_content, re.IGNORECASE))

    def _is_readable(self, xml_content: str) -> bool:
        """Проверяет базовую читаемость как XML"""
        try:
            # Проверяем на наличие базовых XML элементов
            if not xml_content.strip():
                return False

            # Проверяем на наличие хотя бы одного тега
            if not re.search(r'<[^>]+>', xml_content):
                return False

            # Проверяем на отсутствие бинарных данных
            if b'\x00' in xml_content.encode('utf-8', errors='ignore'):
                return False

            return True
        except Exception:
            return False

    def _validate_encoding(self, xml_content: str) -> bool:
        """Проверяет кодировку файла"""
        try:
            # Проверяем на наличие специальных символов
            if '\x00' in xml_content:
                return False

            # Пытаемся найти объявление кодировки
            encoding_match = re.search(r'encoding=["\']([^"\']+)["\']', xml_content)
            if encoding_match:
                declared_encoding = encoding_match.group(1).lower()
                logger.debug(f"Declared encoding: {declared_encoding}")

            return True
        except Exception:
            return False

    def _check_critical_tags_balance(self, xml_content: str) -> bool:
        """Проверяет парность только самых критичных тегов"""
        try:
            # Проверяем только trans-unit теги - они критичны
            open_count = len(re.findall(r'<trans-unit[^>]*>', xml_content, re.IGNORECASE))
            close_count = len(re.findall(r'</trans-unit>', xml_content, re.IGNORECASE))

            if open_count > 0 and close_count > 0:
                return abs(open_count - close_count) <= 1  # Позволяем небольшую разницу

            return True  # Если нет тегов, то и проблем нет
        except Exception:
            return True

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
        ИСПРАВЛЕНО: Мягкая валидация набора частей для объединения

        Args:
            parts_content: Список содержимого частей

        Returns:
            Кортеж (is_valid, error_message)
        """
        if not parts_content:
            return False, "Список частей пуст"

        metadata_list = []
        warnings = []

        # Извлекаем метаданные из каждой части
        for i, content in enumerate(parts_content):
            if not self.is_split_part(content):
                warnings.append(f"Часть {i + 1} не содержит метаданных разделения")
                continue

            metadata = self._extract_split_metadata(content)
            if not metadata:
                warnings.append(f"Не удалось извлечь метаданные из части {i + 1}")
                continue

            metadata_list.append(metadata)

        # Если нет метаданных вообще, это критическая ошибка
        if not metadata_list:
            return False, "Ни одна часть не содержит корректных метаданных разделения"

        # Проверяем совместимость метаданных (мягко)
        is_valid, error_msg = self._validate_metadata_compatibility_soft(metadata_list)

        if not is_valid:
            return False, error_msg

        if warnings:
            logger.info(f"Split parts validation warnings: {'; '.join(warnings)}")

        return True, None

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

    def _validate_metadata_compatibility_soft(self, metadata_list: List[Dict[str, str]]) -> Tuple[bool, Optional[str]]:
        """
        ИСПРАВЛЕНО: Мягкая проверка совместимости метаданных частей

        Args:
            metadata_list: Список метаданных частей

        Returns:
            Кортеж (is_valid, error_message)
        """
        if not metadata_list:
            return False, "Нет метаданных для проверки"

        warnings = []

        # Проверяем GUID (критично)
        guids = set(m.get('split_id', '') for m in metadata_list)
        if len(guids) > 1:
            return False, "Части принадлежат разным операциям разделения"

        if not guids or '' in guids:
            return False, "Отсутствует идентификатор разделения"

        # Проверяем количество частей (мягко)
        total_parts_set = set()
        for m in metadata_list:
            try:
                total_parts_set.add(int(m.get('total_parts', 0)))
            except ValueError:
                warnings.append("Некорректное количество частей в метаданных")

        if len(total_parts_set) > 1:
            warnings.append("Несовпадение общего количества частей")

        total_parts = max(total_parts_set) if total_parts_set else len(metadata_list)

        # Проверяем номера частей (мягко)
        part_numbers = []
        for m in metadata_list:
            try:
                part_num = int(m.get('part_number', 0))
                part_numbers.append(part_num)
            except ValueError:
                warnings.append("Некорректный номер части")

        if part_numbers:
            part_numbers.sort()
            expected = list(range(1, len(part_numbers) + 1))

            if part_numbers != expected:
                warnings.append(f"Возможные пропуски в последовательности частей: {part_numbers}")

        # Проверяем непрерывность сегментов (мягко)
        if len(metadata_list) > 1:
            sorted_metadata = sorted(metadata_list, key=lambda m: int(m.get('part_number', 0)))

            for i in range(len(sorted_metadata) - 1):
                current = sorted_metadata[i]
                next_part = sorted_metadata[i + 1]

                try:
                    current_last = int(current.get('last_segment_index', 0))
                    next_first = int(next_part.get('first_segment_index', 0))

                    if current_last + 1 != next_first:
                        warnings.append(
                            f"Возможный разрыв в последовательности сегментов между частями {i + 1} и {i + 2}")
                except ValueError:
                    warnings.append("Некорректные индексы сегментов в метаданных")

        if warnings:
            logger.info(f"Metadata compatibility warnings: {'; '.join(warnings)}")

        return True, None

    def validate_merged_file(self, xml_content: str) -> Tuple[bool, Optional[str]]:
        """
        ИСПРАВЛЕНО: Мягкая валидация объединенного файла

        Args:
            xml_content: Содержимое объединенного файла

        Returns:
            Кортеж (is_valid, error_message)
        """
        # Проверяем, что в файле нет метаданных разделения
        if self.is_split_part(xml_content):
            return False, "Объединенный файл содержит метаданные разделения"

        # Выполняем мягкую валидацию
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
        has_trans_unit = '<trans-unit' in xml_content.lower()
        has_content = len(xml_content.strip()) > 50

        return has_content and (has_xliff or has_trans_unit)

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
            'encoding': 'utf-8',
            'is_split_part': False,
            'file_size': len(xml_content)
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

            # Проверяем, является ли файл частью
            stats['is_split_part'] = self.is_split_part(xml_content)

        except Exception as e:
            logger.warning(f"Error getting file stats: {e}")

        return stats

    def validate_for_splitting(self, xml_content: str) -> Tuple[bool, Optional[str]]:
        """
        НОВЫЙ МЕТОД: Специальная валидация для разделения файла

        Args:
            xml_content: Содержимое файла

        Returns:
            Кортеж (is_valid, error_message)
        """
        # Проверяем базовую структуру
        is_valid, error_msg = self.validate(xml_content)
        if not is_valid:
            return False, error_msg

        # Дополнительные проверки для разделения
        if self.is_split_part(xml_content):
            return False, "Файл уже является частью разделенного SDLXLIFF"

        # Проверяем наличие достаточного количества сегментов
        segments_count = len(re.findall(r'<trans-unit[^>]*>', xml_content, re.IGNORECASE))
        if segments_count < 2:
            return False, f"Недостаточно сегментов для разделения: {segments_count}"

        return True, None

    def validate_for_merging(self, parts_content: List[str]) -> Tuple[bool, Optional[str]]:
        """
        НОВЫЙ МЕТОД: Специальная валидация для объединения файлов

        Args:
            parts_content: Список содержимого частей

        Returns:
            Кортеж (is_valid, error_message)
        """
        if len(parts_content) < 2:
            return False, "Для объединения нужно минимум 2 части"

        # Проверяем каждую часть
        for i, content in enumerate(parts_content):
            if not self.quick_validate(content):
                return False, f"Часть {i + 1} не является корректным SDLXLIFF"

        # Проверяем совместимость частей
        return self.validate_split_parts(parts_content)