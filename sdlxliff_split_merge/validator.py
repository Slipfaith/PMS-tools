import re
import logging
from typing import List, Tuple, Dict, Optional
from lxml import etree

logger = logging.getLogger(__name__)


class SdlxliffValidator:

    def validate(self, xml_content: str) -> Tuple[bool, Optional[str]]:
        try:
            if not self._has_xliff_structure(xml_content):
                return False, "Файл не содержит XLIFF структуру"
            if not self._has_required_elements(xml_content):
                return False, "Отсутствуют обязательные элементы"
            if not self._check_xml_structure(xml_content):
                return False, "Ошибка структуры XML: файл повреждён или содержит непарные теги"
            if not self._has_trans_units(xml_content):
                return False, "В файле нет сегментов <trans-unit>"
            if len(xml_content.strip()) < 100:
                return False, "Файл слишком короткий"
            return True, None
        except Exception as e:
            logger.error(f"Ошибка валидации: {e}")
            return False, f"Ошибка валидации: {e}"

    def _has_xliff_structure(self, xml_content: str) -> bool:
        xliff_pattern = r'<xliff[^>]*xmlns[^>]*xliff[^>]*>'
        return bool(re.search(xliff_pattern, xml_content, re.IGNORECASE))

    def _has_required_elements(self, xml_content: str) -> bool:
        required_elements = ['<file', '<header', '<body', '<trans-unit']
        for element in required_elements:
            if element not in xml_content.lower():
                return False
        return True

    def _check_xml_structure(self, xml_content: str) -> bool:
        try:
            etree.fromstring(xml_content.encode("utf-8"))
            return True
        except Exception as e:
            logger.error(f"Ошибка парсинга XML: {e}")
            return False

    def _has_trans_units(self, xml_content: str) -> bool:
        return bool(re.search(r'<trans-unit[^>]*>', xml_content, re.IGNORECASE))

    def is_split_part(self, xml_content: str) -> bool:
        return '<!-- SDLXLIFF_SPLIT_METADATA:' in xml_content

    def validate_split_parts(self, parts_content: List[str]) -> Tuple[bool, Optional[str]]:
        if not parts_content:
            return False, "Список частей пуст"
        metadata_list = []
        for i, content in enumerate(parts_content):
            if not self.is_split_part(content):
                return False, f"Часть {i + 1} не содержит метаданных разделения"
            metadata = self._extract_split_metadata(content)
            if not metadata:
                return False, f"Не удалось извлечь метаданные из части {i + 1}"
            metadata_list.append(metadata)
        if not metadata_list:
            return False, "Ни одна часть не содержит корректных метаданных разделения"
        is_valid, error_msg = self._validate_metadata_compatibility(metadata_list)
        if not is_valid:
            return False, error_msg
        return True, None

    def _extract_split_metadata(self, xml_content: str) -> Optional[Dict[str, str]]:
        metadata_match = re.search(
            r'<!-- SDLXLIFF_SPLIT_METADATA:(.*?)-->',
            xml_content,
            re.DOTALL
        )
        if not metadata_match:
            return None
        metadata = {}
        metadata_str = metadata_match.group(1)
        for line in metadata_str.strip().split('\n'):
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                metadata[key.strip()] = value.strip().strip('"')
        return metadata

    def _validate_metadata_compatibility(self, metadata_list: List[Dict[str, str]]) -> Tuple[bool, Optional[str]]:
        if not metadata_list:
            return False, "Нет метаданных для проверки"
        guids = set(m.get('split_id', '') for m in metadata_list)
        if len(guids) > 1:
            return False, "Части принадлежат разным операциям разделения"
        if not guids or '' in guids:
            return False, "Отсутствует идентификатор разделения"
        total_parts_set = set()
        for m in metadata_list:
            try:
                total_parts_set.add(int(m.get('total_parts', 0)))
            except ValueError:
                return False, "Некорректное количество частей в метаданных"
        if len(total_parts_set) > 1:
            return False, "Несовпадение общего количества частей"
        part_numbers = []
        for m in metadata_list:
            try:
                part_num = int(m.get('part_number', 0))
                part_numbers.append(part_num)
            except ValueError:
                return False, "Некорректный номер части"
        if part_numbers:
            part_numbers.sort()
            expected = list(range(1, len(part_numbers) + 1))
            if part_numbers != expected:
                return False, f"Пропуски в последовательности частей: {part_numbers}"
        if len(metadata_list) > 1:
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
        if self.is_split_part(xml_content):
            return False, "Объединенный файл содержит метаданные разделения"
        return self.validate(xml_content)

    def quick_validate(self, xml_content: str) -> bool:
        has_xliff = '<xliff' in xml_content.lower()
        has_trans_unit = '<trans-unit' in xml_content.lower()
        has_content = len(xml_content.strip()) > 50
        return has_content and (has_xliff or has_trans_unit)

    def get_file_stats(self, xml_content: str) -> Dict[str, any]:
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
            trans_units = re.findall(r'<trans-unit[^>]*>', xml_content, re.IGNORECASE)
            stats['total_segments'] = len(trans_units)
            targets = re.findall(r'<target[^>]*>.*?</target>', xml_content, re.DOTALL | re.IGNORECASE)
            non_empty_targets = [t for t in targets if re.sub(r'<[^>]*>', '', t).strip()]
            stats['translated_segments'] = len(non_empty_targets)
            approved = re.findall(r'approved="yes"', xml_content, re.IGNORECASE)
            stats['approved_segments'] = len(approved)
            groups = re.findall(r'<group[^>]*>', xml_content, re.IGNORECASE)
            stats['has_groups'] = len(groups) > 0
            encoding_match = re.search(r'encoding=["\']([^"\']+)["\']', xml_content)
            if encoding_match:
                stats['encoding'] = encoding_match.group(1)
            stats['is_split_part'] = self.is_split_part(xml_content)
        except Exception as e:
            logger.warning(f"Error getting file stats: {e}")
        return stats

    def validate_for_splitting(self, xml_content: str) -> Tuple[bool, Optional[str]]:
        is_valid, error_msg = self.validate(xml_content)
        if not is_valid:
            return False, error_msg
        if self.is_split_part(xml_content):
            return False, "Файл уже является частью разделенного SDLXLIFF"
        segments_count = len(re.findall(r'<trans-unit[^>]*>', xml_content, re.IGNORECASE))
        if segments_count < 2:
            return False, f"Недостаточно сегментов для разделения: {segments_count}"
        return True, None

    def validate_for_merging(self, parts_content: List[str]) -> Tuple[bool, Optional[str]]:
        if len(parts_content) < 2:
            return False, "Для объединения нужно минимум 2 части"
        for i, content in enumerate(parts_content):
            if not self.quick_validate(content):
                return False, f"Часть {i + 1} не является корректным SDLXLIFF"
        return self.validate_split_parts(parts_content)
