# sdlxliff_split_merge/merger.py
"""
Модуль для объединения разделенных SDLXLIFF файлов
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class Merger:
    """
    Объединитель разделенных SDLXLIFF файлов с проверкой целостности
    """

    def __init__(self, parts_bytes: List[bytes]):
        """
        Инициализация с содержимым частей

        Args:
            parts_bytes: Список содержимого частей в байтах
        """
        self.parts_bytes = parts_bytes
        self.parts_metadata = []

        # Извлекаем и проверяем метаданные
        self._extract_metadata()
        self._validate_parts()

        logger.info(f"Merger initialized with {len(parts_bytes)} parts")

    def merge(self) -> bytes:
        """
        Объединяет части обратно в единый файл

        Returns:
            Объединенный SDLXLIFF файл в байтах
        """
        # Сортируем части по номеру
        sorted_parts = sorted(
            zip(self.parts_bytes, self.parts_metadata),
            key=lambda x: x[1]['part']
        )

        # Берем header из первой части (без метаданных)
        first_part_str = sorted_parts[0][0].decode('utf-8')
        header = self._extract_header_without_metadata(first_part_str)

        # Берем footer из последней части
        last_part_str = sorted_parts[-1][0].decode('utf-8')
        footer = self._extract_footer(last_part_str)

        # Собираем все body контенты
        body_content = []

        for part_bytes, metadata in sorted_parts:
            part_str = part_bytes.decode('utf-8')
            body = self._extract_body_content(part_str)
            body_content.append(body)

        # Объединяем body контенты, убирая дублирующиеся закрывающие/открывающие теги групп
        merged_body = self._merge_body_contents(body_content)

        # Собираем финальный файл
        merged_xml = header + merged_body + footer

        logger.info("Merge completed successfully")
        return merged_xml.encode('utf-8')

    def _extract_metadata(self):
        """Извлекает метаданные из всех частей"""
        for part_bytes in self.parts_bytes:
            part_str = part_bytes.decode('utf-8')

            # Ищем метаданные SDLXLIFF_SPLIT_INFO
            metadata_match = re.search(
                r'<!-- SDLXLIFF_SPLIT_INFO:(.*?)-->',
                part_str,
                re.DOTALL
            )

            if not metadata_match:
                raise ValueError("Часть не содержит метаданных SDLXLIFF_SPLIT_INFO")

            # Парсим метаданные
            metadata_str = metadata_match.group(1)
            metadata = {}

            for line in metadata_str.strip().split('\n'):
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    metadata[key] = value.strip('"')

            self.parts_metadata.append(metadata)

    def _validate_parts(self):
        """Проверяет целостность и совместимость частей"""
        if not self.parts_metadata:
            raise ValueError("Нет метаданных для проверки")

        # Проверяем GUID
        guids = set(m.get('guid') for m in self.parts_metadata)
        if len(guids) > 1:
            raise ValueError("Части принадлежат разным операциям разделения")

        # Проверяем количество частей
        total_parts = int(self.parts_metadata[0].get('total', 0))
        if len(self.parts_metadata) != total_parts:
            raise ValueError(
                f"Неполный набор частей: найдено {len(self.parts_metadata)}, "
                f"ожидалось {total_parts}"
            )

        # Проверяем номера частей
        part_numbers = sorted(int(m.get('part', 0)) for m in self.parts_metadata)
        expected_numbers = list(range(1, total_parts + 1))

        if part_numbers != expected_numbers:
            raise ValueError("Пропущены или дублированы номера частей")

        # Проверяем непрерывность trans-unit индексов
        for i in range(len(self.parts_metadata) - 1):
            current_last = int(self.parts_metadata[i].get('last-unit', 0))
            next_first = int(self.parts_metadata[i + 1].get('first-unit', 0))

            if current_last != next_first - 1:
                raise ValueError(
                    f"Разрыв в последовательности trans-unit между "
                    f"частями {i + 1} и {i + 2}"
                )

        logger.info("Parts validation successful")

    def _extract_header_without_metadata(self, part_str: str) -> str:
        """Извлекает header без метаданных разделения"""
        # Находим и удаляем метаданные
        clean_str = re.sub(
            r'<!-- SDLXLIFF_SPLIT_INFO:.*?-->\s*',
            '',
            part_str,
            flags=re.DOTALL
        )

        # Извлекаем header до <body>
        body_pos = clean_str.find('<body>') + len('<body>')
        return clean_str[:body_pos]

    def _extract_footer(self, part_str: str) -> str:
        """Извлекает footer из части"""
        footer_pos = part_str.find('</body>')
        return part_str[footer_pos:]

    def _extract_body_content(self, part_str: str) -> str:
        """Извлекает содержимое body из части"""
        body_start = part_str.find('<body>') + len('<body>')
        body_end = part_str.find('</body>')

        return part_str[body_start:body_end].strip()

    def _merge_body_contents(self, body_contents: List[str]) -> str:
        """
        Объединяет содержимое body, обрабатывая группы

        Args:
            body_contents: Список содержимого body из каждой части

        Returns:
            Объединенное содержимое body
        """
        if not body_contents:
            return ""

        # Для первой части берем как есть
        merged = [body_contents[0]]

        # Для последующих частей проверяем группы на стыках
        for i in range(1, len(body_contents)):
            current_content = body_contents[i]

            # Проверяем, есть ли незакрытая группа в конце предыдущей части
            # и открывающаяся группа в начале текущей части
            prev_ends_with_group = merged[-1].rstrip().endswith('</group>')
            curr_starts_with_group = current_content.lstrip().startswith('<group')

            # Если предыдущая часть заканчивается </group>, а текущая начинается с <group,
            # то это разные группы - добавляем как есть
            if prev_ends_with_group or not curr_starts_with_group:
                merged.append('\n' + current_content)
            else:
                # Возможно, группа была разорвана между частями
                # Проверяем, нужно ли убрать лишний </group> из конца предыдущей части
                last_group_close = merged[-1].rfind('</group>')

                # Ищем соответствующий открывающий тег
                test_content = '\n'.join(merged)
                open_groups = test_content.count('<group')
                close_groups = test_content.count('</group>')

                if close_groups > open_groups:
                    # Убираем лишний закрывающий тег
                    merged[-1] = merged[-1][:last_group_close] + merged[-1][last_group_close + 8:]

                merged.append('\n' + current_content)

        return '\n'.join(merged)

    def get_merge_info(self) -> Dict[str, any]:
        """Возвращает информацию об объединении"""
        return {
            'parts_count': len(self.parts_bytes),
            'guid': self.parts_metadata[0].get('guid') if self.parts_metadata else None,
            'original_name': self.parts_metadata[0].get('original-name') if self.parts_metadata else None,
            'total_units': self.parts_metadata[-1].get('last-unit') if self.parts_metadata else None,
            'merged_at': datetime.utcnow().isoformat()
        }