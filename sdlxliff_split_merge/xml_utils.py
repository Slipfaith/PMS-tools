# sdlxliff_split_merge/xml_utils.py
"""
ИСПРАВЛЕННЫЕ утилиты для работы с XML структурой SDLXLIFF файлов
Полное сохранение структуры SDL включая группы и контексты
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransUnit:
    """Структура trans-unit элемента с полным сохранением данных"""
    id: str
    full_xml: str  # Полный XML с отступами и ВСЕМИ тегами
    start_pos: int
    end_pos: int
    group_id: Optional[str] = None
    source_text: str = ""
    target_text: str = ""
    approved: bool = False
    translated: bool = False

    def is_translated(self) -> bool:
        """Проверяет, переведен ли сегмент"""
        return bool(self.target_text.strip()) or self.translated


class XmlStructure:
    """ИСПРАВЛЕННАЯ структура SDLXLIFF файла с полным сохранением SDL"""

    def __init__(self, xml_content: str):
        self.xml_content = xml_content
        self.trans_units: List[TransUnit] = []
        self.groups: Dict[str, List[int]] = {}  # group_id -> [trans_unit_indices]
        self.header_end_pos = 0
        self.footer_start_pos = 0
        self.encoding = "utf-8"

        self._parse_structure()

    def _parse_structure(self):
        """Парсит структуру файла с полным сохранением SDL элементов"""
        # Определяем кодировку
        encoding_match = re.search(r'encoding=["\']([^"\']+)["\']', self.xml_content)
        if encoding_match:
            self.encoding = encoding_match.group(1)

        # Находим body
        body_match = re.search(r'<body[^>]*>', self.xml_content)
        if body_match:
            self.header_end_pos = body_match.end()

        body_close_match = re.search(r'</body>', self.xml_content)
        if body_close_match:
            self.footer_start_pos = body_close_match.start()

        # Парсим trans-units с сохранением позиций
        self._parse_trans_units()

        # Парсим группы
        self._parse_groups()

    def _parse_trans_units(self):
        """Парсит все trans-unit элементы с сохранением ПОЛНОЙ структуры"""
        pattern = re.compile(
            r'<trans-unit\s+[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</trans-unit>',
            re.DOTALL
        )

        for match in pattern.finditer(self.xml_content):
            trans_unit_id = match.group(1)
            full_xml = match.group(0)

            # Извлекаем source и target БЕЗ ПОТЕРИ тегов
            source_text = self._extract_segment_text_safe(full_xml, 'source')
            target_text = self._extract_segment_text_safe(full_xml, 'target')

            # Проверяем статус
            approved = 'approved="yes"' in full_xml
            translated = bool(target_text.strip())

            trans_unit = TransUnit(
                id=trans_unit_id,
                full_xml=full_xml,
                start_pos=match.start(),
                end_pos=match.end(),
                source_text=source_text,
                target_text=target_text,
                approved=approved,
                translated=translated
            )

            self.trans_units.append(trans_unit)

    def _extract_segment_text_safe(self, xml: str, segment_type: str) -> str:
        """ИСПРАВЛЕНО: Извлекает текст из source или target БЕЗ ПОТЕРИ SDL тегов"""
        pattern = f'<{segment_type}[^>]*>(.*?)</{segment_type}>'
        match = re.search(pattern, xml, re.DOTALL)

        if not match:
            return ""

        content = match.group(1)

        # НЕ убираем SDL теги - они критичны!
        # Убираем только внешние XML декларации если есть
        content = re.sub(r'<\?xml[^>]*\?>', '', content)
        content = content.strip()

        # Для отображения извлекаем только текст (без изменения оригинала)
        # НО сохраняем SDL теги как <g>, <x/>, <mrk>, etc.
        display_text = re.sub(r'<(?!/?[gx]|/?mrk|/?bpt|/?ept)[^>]+>', '', content)
        return display_text.strip()

    def _parse_groups(self):
        """Парсит группы и связывает их с trans-units"""
        group_pattern = re.compile(r'<group[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</group>', re.DOTALL)

        for group_match in group_pattern.finditer(self.xml_content):
            group_id = group_match.group(1)

            # Находим все trans-units внутри этой группы
            group_trans_units = []
            for i, trans_unit in enumerate(self.trans_units):
                if group_match.start() <= trans_unit.start_pos <= group_match.end():
                    trans_unit.group_id = group_id
                    group_trans_units.append(i)

            self.groups[group_id] = group_trans_units

    def get_header(self) -> str:
        """Возвращает header файла с ВСЕМИ метаданными SDL"""
        return self.xml_content[:self.header_end_pos]

    def get_footer(self) -> str:
        """Возвращает footer файла"""
        return self.xml_content[self.footer_start_pos:]

    def get_body_content_with_structure(self, start_idx: int, end_idx: int) -> str:
        """
        НОВЫЙ МЕТОД: Возвращает body контент с ПОЛНЫМ сохранением структуры SDL
        Включая группы, контексты, отступы и ВСЕ SDL теги
        """
        if not self.trans_units or start_idx >= len(self.trans_units):
            return ""

        end_idx = min(end_idx, len(self.trans_units))

        # ИСПРАВЛЕНО: Находим границы с учетом групп и контекстов
        start_pos, end_pos = self._find_structure_boundaries(start_idx, end_idx)

        # Извлекаем контент ТОЧНО как в оригинале - со всеми группами и контекстами
        content = self.xml_content[start_pos:end_pos]

        return content

    def _find_structure_boundaries(self, start_idx: int, end_idx: int) -> Tuple[int, int]:
        """
        НОВЫЙ МЕТОД: Находит границы с учетом SDL структуры
        Обеспечивает включение групп и контекстов
        """
        if not self.trans_units:
            return 0, 0

        # Начальная позиция - ищем начало группы если trans-unit входит в группу
        start_unit = self.trans_units[start_idx]
        start_pos = start_unit.start_pos

        if start_unit.group_id:
            # Ищем начало группы
            group_pattern = f'<group[^>]*id=["\']' + re.escape(start_unit.group_id) + '["\'][^>]*>'
            group_match = re.search(group_pattern, self.xml_content)
            if group_match and group_match.start() < start_pos:
                start_pos = group_match.start()

        # Конечная позиция - ищем конец группы если trans-unit входит в группу
        end_unit = self.trans_units[end_idx - 1]
        end_pos = end_unit.end_pos

        if end_unit.group_id:
            # Ищем конец группы
            group_start_pattern = f'<group[^>]*id=["\']' + re.escape(end_unit.group_id) + '["\'][^>]*>'
            group_start = re.search(group_start_pattern, self.xml_content)
            if group_start:
                # Ищем соответствующий </group>
                group_content = self.xml_content[group_start.start():]
                group_end_match = re.search(r'</group>', group_content)
                if group_end_match:
                    group_end_pos = group_start.start() + group_end_match.end()
                    if group_end_pos > end_pos:
                        end_pos = group_end_pos

        return start_pos, end_pos

    def get_body_content(self, start_idx: int, end_idx: int) -> str:
        """
        СТАРЫЙ МЕТОД: Возвращает body контент (для обратной совместимости)
        """
        return self.get_body_content_with_structure(start_idx, end_idx)

    def get_segments_count(self) -> int:
        """Возвращает количество сегментов"""
        return len(self.trans_units)

    def get_translated_count(self) -> int:
        """Возвращает количество переведенных сегментов"""
        return sum(1 for unit in self.trans_units if unit.is_translated())

    def get_word_count(self) -> int:
        """Подсчитывает приблизительное количество слов"""
        total_words = 0
        for unit in self.trans_units:
            words = len(unit.source_text.split())
            total_words += words
        return total_words

    def validate_structure_integrity(self) -> Dict[str, any]:
        """
        НОВЫЙ МЕТОД: Проверяет целостность SDL структуры
        """
        issues = []

        # Проверяем группы
        for group_id, unit_indices in self.groups.items():
            if not unit_indices:
                issues.append(f"Пустая группа: {group_id}")
                continue

            # Проверяем что все trans-units группы существуют
            for idx in unit_indices:
                if idx >= len(self.trans_units):
                    issues.append(f"Неверный индекс в группе {group_id}: {idx}")

        # Проверяем контексты SDL
        sdl_contexts = re.findall(r'<sdl:cxts[^>]*>.*?</sdl:cxts>', self.xml_content, re.DOTALL)

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'groups_count': len(self.groups),
            'sdl_contexts_count': len(sdl_contexts),
            'total_segments': len(self.trans_units)
        }


class TransUnitParser:
    """Парсер отдельных trans-unit элементов с сохранением SDL"""

    @staticmethod
    def parse_trans_unit(xml_content: str) -> Optional[TransUnit]:
        """Парсит отдельный trans-unit с сохранением SDL тегов"""
        pattern = re.compile(
            r'<trans-unit\s+[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</trans-unit>',
            re.DOTALL
        )

        match = pattern.search(xml_content)
        if not match:
            return None

        trans_unit_id = match.group(1)
        full_xml = match.group(0)

        # Извлекаем source и target с сохранением SDL тегов
        source_text = TransUnitParser._extract_segment_text_safe(full_xml, 'source')
        target_text = TransUnitParser._extract_segment_text_safe(full_xml, 'target')

        # Проверяем статус
        approved = 'approved="yes"' in full_xml
        translated = bool(target_text.strip())

        return TransUnit(
            id=trans_unit_id,
            full_xml=full_xml,
            start_pos=match.start(),
            end_pos=match.end(),
            source_text=source_text,
            target_text=target_text,
            approved=approved,
            translated=translated
        )

    @staticmethod
    def _extract_segment_text_safe(xml: str, segment_type: str) -> str:
        """Извлекает текст из source или target с сохранением SDL тегов"""
        pattern = f'<{segment_type}[^>]*>(.*?)</{segment_type}>'
        match = re.search(pattern, xml, re.DOTALL)

        if not match:
            return ""

        content = match.group(1)

        # Сохраняем SDL теги, убираем только лишние XML декларации
        content = re.sub(r'<\?xml[^>]*\?>', '', content)

        # Для отображения убираем только не-SDL теги
        text = re.sub(r'<(?!/?[gx]|/?mrk|/?bpt|/?ept|/?ph|/?it)[^>]+>', '', content)
        return text.strip()

    @staticmethod
    def update_trans_unit_target(xml_content: str, new_target: str) -> str:
        """Обновляет target в trans-unit с сохранением SDL структуры"""
        # Находим target элемент
        target_pattern = r'<target[^>]*>.*?</target>'

        # Если target уже существует, заменяем
        if re.search(target_pattern, xml_content, re.DOTALL):
            return re.sub(target_pattern, f'<target>{new_target}</target>', xml_content, flags=re.DOTALL)

        # Если target не существует, добавляем после source
        source_pattern = r'(<source[^>]*>.*?</source>)'
        replacement = r'\1\n      <target>' + new_target + '</target>'

        return re.sub(source_pattern, replacement, xml_content, flags=re.DOTALL)

    @staticmethod
    def mark_as_translated(xml_content: str) -> str:
        """Помечает trans-unit как переведенный"""
        # Обновляем атрибуты
        xml_content = re.sub(r'approved="[^"]*"', 'approved="yes"', xml_content)

        # Добавляем approved если его нет
        if 'approved=' not in xml_content:
            xml_content = xml_content.replace('<trans-unit ', '<trans-unit approved="yes" ')

        return xml_content


# =============================================================================
# LEGACY FUNCTIONS - для обратной совместимости со старым кодом
# =============================================================================

def find_trans_units_and_groups(xml_bytes: bytes) -> Dict[str, Any]:
    """
    Legacy функция - находит все trans-unit и group элементы
    Оставлена для совместимости
    """
    try:
        xml_str = xml_bytes.decode('utf-8')
    except UnicodeDecodeError:
        xml_str = xml_bytes.decode('utf-16', errors='replace')

    structure = XmlStructure(xml_str)

    # Преобразуем в старый формат
    trans_units = []
    for i, unit in enumerate(structure.trans_units):
        # Создаем объект-заглушку с нужными атрибутами
        class MockMatch:
            def __init__(self, start, end):
                self._start = start
                self._end = end

            def start(self):
                return self._start

            def end(self):
                return self._end

        trans_units.append({
            'match': MockMatch(unit.start_pos, unit.end_pos),
            'id': unit.id,
            'group_id': structure.groups.get(unit.group_id, []).index(i) if unit.group_id else None
        })

    groups = []
    for group_id, unit_indices in structure.groups.items():
        if unit_indices:
            start_pos = min(structure.trans_units[i].start_pos for i in unit_indices)
            end_pos = max(structure.trans_units[i].end_pos for i in unit_indices)

            class MockMatch:
                def __init__(self, start, end):
                    self._start = start
                    self._end = end

                def start(self):
                    return self._start

                def end(self):
                    return self._end

            groups.append({
                'match': MockMatch(start_pos, end_pos),
                'trans_unit_indices': unit_indices
            })

    return {
        'trans_units': trans_units,
        'groups': groups
    }


def extract_source_word_count(trans_unit_bytes: bytes) -> int:
    """Legacy функция - подсчитывает слова в source"""
    try:
        trans_unit_str = trans_unit_bytes.decode('utf-8')
    except UnicodeDecodeError:
        trans_unit_str = trans_unit_bytes.decode('utf-16', errors='replace')

    unit = TransUnitParser.parse_trans_unit(trans_unit_str)
    if unit:
        return len(unit.source_text.split())
    return 0


def validate_sdlxliff_structure(xml_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """Legacy функция - валидирует структуру"""
    try:
        xml_str = xml_bytes.decode('utf-8')
    except UnicodeDecodeError:
        try:
            xml_str = xml_bytes.decode('utf-16')
        except UnicodeDecodeError:
            return False, "Encoding error"

    from .validator import SdlxliffValidator
    validator = SdlxliffValidator()
    return validator.validate(xml_str)


def get_header_footer(xml_bytes: bytes, units_list: List[dict]) -> Tuple[bytes, bytes]:
    """Legacy функция - возвращает header и footer"""
    try:
        xml_str = xml_bytes.decode('utf-8')
    except UnicodeDecodeError:
        xml_str = xml_bytes.decode('utf-16', errors='replace')

    structure = XmlStructure(xml_str)

    header = structure.get_header().encode(structure.encoding)
    footer = structure.get_footer().encode(structure.encoding)

    return header, footer


def extract_metadata_from_header(header_str: str) -> Dict[str, str]:
    """Извлекает метаданные из header SDLXLIFF"""
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