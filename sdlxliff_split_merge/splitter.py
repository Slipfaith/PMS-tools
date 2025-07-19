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
    def __init__(self, xml_content: str):
        self.xml_content = xml_content
        self.validator = SdlxliffValidator()

        is_valid, error_msg = self.validator.validate(xml_content)
        if not is_valid:
            raise ValueError(f"Некорректный SDLXLIFF файл: {error_msg}")

        self.structure = XmlStructure(xml_content)
        self.split_id = str(uuid.uuid4())
        self.original_checksum = hashlib.md5(xml_content.encode(self.structure.encoding)).hexdigest()
        self.split_timestamp = datetime.utcnow().isoformat() + "Z"

        logger.info(f"Splitter initialized: {self.structure.get_segments_count()} segments")

    def split(self, parts_count: int) -> List[str]:
        if parts_count < 2:
            raise ValueError("Количество частей должно быть не менее 2")

        if parts_count > self.structure.get_segments_count():
            raise ValueError(
                f"Количество частей ({parts_count}) больше количества сегментов ({self.structure.get_segments_count()})")

        distribution = self._distribute_segments(parts_count)
        parts = []

        for i, (start_idx, end_idx) in enumerate(distribution):
            part_content = self._create_part_preserving_structure(i + 1, parts_count, start_idx, end_idx)
            parts.append(part_content)

        logger.info(f"Split into {parts_count} parts successfully")
        return parts

    def split_by_word_count(self, words_per_part: int) -> List[str]:
        if words_per_part < 10:
            raise ValueError("Количество слов на часть должно быть не менее 10")

        total_words = self.structure.get_word_count()
        if total_words == 0:
            raise ValueError("В файле нет слов для разделения")

        parts_count = max(2, (total_words + words_per_part - 1) // words_per_part)
        logger.info(f"Calculated {parts_count} parts for {words_per_part} words per part")

        return self.split_by_words(parts_count)

    def split_by_words(self, parts_count: int) -> List[str]:
        if parts_count < 2:
            raise ValueError("Количество частей должно быть не менее 2")

        if parts_count > self.structure.get_segments_count():
            raise ValueError(
                f"Количество частей ({parts_count}) больше количества сегментов ({self.structure.get_segments_count()})"
            )

        distribution = self._distribute_segments_by_words(parts_count)
        parts = []

        for i, (start_idx, end_idx) in enumerate(distribution):
            part_content = self._create_part_preserving_structure(i + 1, parts_count, start_idx, end_idx)
            parts.append(part_content)

        logger.info(f"Split into {parts_count} parts by words successfully")
        return parts

    def _distribute_segments(self, parts_count: int) -> List[Tuple[int, int]]:
        total_segments = self.structure.get_segments_count()
        segments_per_part = total_segments // parts_count
        remainder = total_segments % parts_count

        distribution = []
        current_idx = 0

        for i in range(parts_count):
            part_size = segments_per_part + (1 if i < remainder else 0)
            end_idx = min(current_idx + part_size, total_segments)
            end_idx = self._adjust_for_groups(current_idx, end_idx, total_segments)
            distribution.append((current_idx, end_idx))
            current_idx = end_idx

        if distribution and distribution[-1][1] < total_segments:
            distribution[-1] = (distribution[-1][0], total_segments)

        return distribution

    def _distribute_segments_by_words(self, parts_count: int) -> List[Tuple[int, int]]:
        total_segments = self.structure.get_segments_count()
        total_words = self.structure.get_word_count()

        if total_words == 0:
            return self._distribute_segments(parts_count)

        words_per_part = total_words / parts_count

        distribution = []
        current_idx = 0

        for i in range(parts_count - 1):
            target_words = words_per_part * (i + 1)
            accumulated_words = 0
            end_idx = current_idx

            for j in range(current_idx, total_segments):
                accumulated_words += len(self.structure.trans_units[j].source_text.split())
                if accumulated_words >= target_words:
                    end_idx = j + 1
                    break
            else:
                end_idx = total_segments

            end_idx = self._adjust_for_groups(current_idx, end_idx, total_segments)
            distribution.append((current_idx, end_idx))
            current_idx = end_idx

        if current_idx < total_segments:
            distribution.append((current_idx, total_segments))

        return distribution

    def _adjust_for_groups(self, start_idx: int, end_idx: int, total_segments: int) -> int:
        if end_idx >= total_segments:
            return total_segments

        if end_idx > 0 and end_idx < len(self.structure.trans_units):
            for i in range(end_idx - 1, start_idx - 1, -1):
                unit = self.structure.trans_units[i]
                if unit.group_id is None:
                    return i + 1

                group_units = [j for j, u in enumerate(self.structure.trans_units)
                               if u.group_id == unit.group_id]
                if group_units:
                    last_in_group = max(group_units)
                    if last_in_group >= end_idx:
                        return last_in_group + 1
                    else:
                        return end_idx

        return end_idx

    def _create_part_preserving_structure(self, part_num: int, total_parts: int, start_idx: int, end_idx: int) -> str:
        metadata = self._create_split_metadata(part_num, total_parts, start_idx, end_idx)
        header_content = self._get_complete_original_header()
        body_content = self._create_body_content_for_part(start_idx, end_idx)
        footer_content = self._get_original_footer()

        part_content = self._assemble_part_with_metadata(header_content, metadata, body_content, footer_content)
        return part_content

    def _get_complete_original_header(self) -> str:
        body_start = re.search(r'<body[^>]*>', self.xml_content)
        if not body_start:
            raise ValueError("Не найден тег <body>")
        return self.xml_content[:body_start.end()]

    def _create_body_content_for_part(self, start_idx: int, end_idx: int) -> str:
        body_parts = []

        sdl_contexts = self._extract_sdl_contexts_from_body()
        if sdl_contexts:
            body_parts.append(sdl_contexts)

        if start_idx < len(self.structure.trans_units) and end_idx > start_idx:
            end_idx = min(end_idx, len(self.structure.trans_units))

            current_group_id = None
            group_started = False

            for i in range(start_idx, end_idx):
                unit = self.structure.trans_units[i]

                if unit.group_id != current_group_id:
                    if group_started:
                        body_parts.append('</group>')
                        group_started = False

                    if unit.group_id:
                        group_opening = self._find_group_opening_tag(unit.group_id)
                        if group_opening:
                            body_parts.append(group_opening)
                            group_started = True

                    current_group_id = unit.group_id

                body_parts.append(unit.full_xml)

            if group_started:
                body_parts.append('</group>')

        return '\n'.join(body_parts)

    def _extract_sdl_contexts_from_body(self) -> str:
        body_start = re.search(r'<body[^>]*>', self.xml_content)
        if not body_start:
            return ""

        body_start_pos = body_start.end()
        first_trans_unit = re.search(r'<trans-unit', self.xml_content[body_start_pos:])

        if first_trans_unit:
            context_area = self.xml_content[body_start_pos:body_start_pos + first_trans_unit.start()]

            group_sdl_pattern = r'<group[^>]*>\s*<sdl:cxts[^>]*>.*?</sdl:cxts>\s*</group>'
            group_matches = re.findall(group_sdl_pattern, context_area, re.DOTALL)

            if group_matches:
                return '\n'.join(group_matches)

            sdl_cxts_pattern = r'<sdl:cxts[^>]*>.*?</sdl:cxts>'
            cxts_matches = re.findall(sdl_cxts_pattern, context_area, re.DOTALL)

            if cxts_matches:
                return '\n'.join(cxts_matches)

        return ""

    def _find_group_opening_tag(self, group_id: str) -> str:
        pattern = f'<group[^>]*id=["\']' + re.escape(group_id) + '["\'][^>]*>'
        match = re.search(pattern, self.xml_content)
        if match:
            return match.group(0)
        return f'<group id="{group_id}">'

    def _get_original_footer(self) -> str:
        footer_match = re.search(r'</body>.*', self.xml_content, re.DOTALL)
        if footer_match:
            return footer_match.group(0)
        return '</body>\n</file>\n</xliff>'

    def _assemble_part_with_metadata(self, header: str, metadata: str, body_content: str, footer: str) -> str:
        body_tag_match = re.search(r'(<body[^>]*>)', header)
        if not body_tag_match:
            return metadata + '\n' + header + '\n' + body_content + '\n' + footer

        body_tag_end = body_tag_match.end()

        result = (header[:body_tag_end] +
                  '\n' + metadata + '\n' +
                  body_content + '\n' +
                  footer)

        return result

    def _create_split_metadata(self, part_num: int, total_parts: int, start_idx: int, end_idx: int) -> str:
        original_match = re.search(r'original="([^"]+)"', self.xml_content)
        original_name = original_match.group(1) if original_match else "unknown.sdlxliff"
        original_name = os.path.basename(original_name)

        if not original_name.lower().endswith('.sdlxliff'):
            original_name = os.path.splitext(original_name)[0] + '.sdlxliff'

        part_segments = end_idx - start_idx
        part_words = sum(len(self.structure.trans_units[i].source_text.split())
                         for i in range(start_idx, min(end_idx, len(self.structure.trans_units))))

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
        total_words = self.structure.get_word_count()
        if total_words == 0:
            return 1
        return max(2, (total_words + words_per_part - 1) // words_per_part)

    def get_segments_distribution(self, parts_count: int) -> List[Dict[str, any]]:
        distribution = self._distribute_segments(parts_count)
        result = []

        for i, (start_idx, end_idx) in enumerate(distribution):
            part_segments = end_idx - start_idx
            part_words = sum(len(self.structure.trans_units[j].source_text.split())
                             for j in range(start_idx, min(end_idx, len(self.structure.trans_units))))

            groups_in_part = set()
            for j in range(start_idx, end_idx):
                if j < len(self.structure.trans_units) and self.structure.trans_units[j].group_id:
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
        issues = []
        warnings = []

        for i, part in enumerate(parts):
            if 'SDLXLIFF_SPLIT_METADATA' not in part:
                issues.append(f"Часть {i + 1}: отсутствуют метаданные разделения")

            if '<trans-unit' not in part:
                issues.append(f"Часть {i + 1}: отсутствуют trans-unit элементы")

        try:
            from .merger import StructuralMerger
            merger = StructuralMerger(parts)
            merged_content = merger.merge()

            if '<trans-unit' not in merged_content:
                issues.append("Объединение не содержит trans-unit элементов")

            original_segments = len(re.findall(r'<trans-unit', self.xml_content))
            merged_segments = len(re.findall(r'<trans-unit', merged_content))

            if original_segments != merged_segments:
                issues.append(f"Потеря сегментов: оригинал {original_segments}, объединено {merged_segments}")

        except Exception as e:
            warnings.append(f"Ошибка тестирования объединения: {str(e)}")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'parts_count': len(parts),
            'total_size': sum(len(part) for part in parts)
        }