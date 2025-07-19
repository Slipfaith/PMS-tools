import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from .xml_utils import XmlStructure, TransUnitParser
from .validator import SdlxliffValidator

logger = logging.getLogger(__name__)


class StructuralMerger:
    def __init__(self, parts_content: List[str]):
        self.parts_content = parts_content
        self.validator = SdlxliffValidator()

        is_valid, error_msg = self.validator.validate_split_parts(parts_content)
        if not is_valid:
            logger.info(f"Skipping metadata validation: {error_msg}")

        self.parts_metadata = []
        for content in parts_content:
            metadata = self.validator._extract_split_metadata(content) or {}
            self.parts_metadata.append(metadata)

        self.sorted_parts = self._sort_parts()
        logger.info(f"Merger initialized with {len(parts_content)} parts")

    def merge(self) -> str:
        original_header = self._get_original_header_from_first_part()
        all_trans_units = self._collect_all_trans_units_in_order()
        merged_content = self._reconstruct_file_with_original_structure(original_header, all_trans_units)

        is_valid, error_msg = self.validator.validate_merged_file(merged_content)
        if not is_valid:
            logger.warning(f"Merged file validation warning: {error_msg}")

        logger.info("Merge completed successfully")
        return merged_content

    def _sort_parts(self) -> List[Tuple[str, Dict[str, str]]]:
        parts_with_metadata = list(zip(self.parts_content, self.parts_metadata))

        def get_part_number(item: Tuple[str, Dict[str, str]]) -> int:
            md = item[1]
            try:
                return int(md.get('part_number', 0))
            except Exception:
                return 0

        return sorted(parts_with_metadata, key=get_part_number)

    def _get_original_header_from_first_part(self) -> str:
        first_part_content = self.sorted_parts[0][0]

        clean_content = re.sub(
            r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
            '',
            first_part_content,
            flags=re.DOTALL
        )

        body_start = re.search(r'<body[^>]*>', clean_content)
        if not body_start:
            raise ValueError("Не найден тег <body> в первой части")

        return clean_content[:body_start.end()]

    def _collect_all_trans_units_in_order(self) -> List[str]:
        all_trans_units = []

        for idx, (part_content, metadata) in enumerate(self.sorted_parts, 1):
            clean_content = re.sub(
                r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
                '',
                part_content,
                flags=re.DOTALL
            )

            trans_unit_pattern = r'<trans-unit[^>]*id=[^>]*>.*?</trans-unit>'
            trans_units = re.findall(trans_unit_pattern, clean_content, re.DOTALL)

            all_trans_units.extend(trans_units)
            logger.debug(
                "Collected %d trans-units from part %s",
                len(trans_units),
                metadata.get('part_number', idx),
            )

        logger.info(f"Total collected trans-units: {len(all_trans_units)}")
        return all_trans_units

    def _reconstruct_file_with_original_structure(self, original_header: str, all_trans_units: List[str]) -> str:
        body_content = self._create_body_content_with_structure(original_header, all_trans_units)
        footer = self._get_footer_from_first_part()

        result = original_header + '\n' + body_content + '\n' + footer
        return result

    def _create_body_content_with_structure(self, original_header: str, all_trans_units: List[str]) -> str:
        body_parts = []

        sdl_contexts = self._extract_sdl_contexts_from_header(original_header)
        if sdl_contexts:
            body_parts.append(sdl_contexts)

        groups_structure = self._analyze_groups_structure()

        if groups_structure:
            body_parts.extend(self._reconstruct_with_groups(all_trans_units, groups_structure))
        else:
            body_parts.extend(all_trans_units)

        return '\n'.join(body_parts)

    def _extract_sdl_contexts_from_header(self, header: str) -> str:
        first_part_content = self.sorted_parts[0][0]

        clean_content = re.sub(
            r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
            '',
            first_part_content,
            flags=re.DOTALL
        )

        body_start = re.search(r'<body[^>]*>', clean_content)
        if not body_start:
            return ""

        body_start_pos = body_start.end()
        first_trans_unit = re.search(r'<trans-unit', clean_content[body_start_pos:])

        if first_trans_unit:
            context_area = clean_content[body_start_pos:body_start_pos + first_trans_unit.start()]

            group_sdl_pattern = r'<group[^>]*>\s*<sdl:cxts[^>]*>.*?</sdl:cxts>\s*</group>'
            group_matches = re.findall(group_sdl_pattern, context_area, re.DOTALL)

            if group_matches:
                return '\n'.join(group_matches)

            sdl_cxts_pattern = r'<sdl:cxts[^>]*>.*?</sdl:cxts>'
            cxts_matches = re.findall(sdl_cxts_pattern, context_area, re.DOTALL)

            if cxts_matches:
                return '\n'.join(cxts_matches)

        return ""

    def _analyze_groups_structure(self) -> Dict[str, List[str]]:
        groups_structure = {}

        for part_content, metadata in self.sorted_parts:
            clean_content = re.sub(
                r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
                '',
                part_content,
                flags=re.DOTALL
            )

            group_pattern = re.compile(r'<group[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</group>', re.DOTALL)

            for group_match in group_pattern.finditer(clean_content):
                group_id = group_match.group(1)
                group_content = group_match.group(2)

                trans_unit_pattern = r'<trans-unit[^>]*id=[^>]*>.*?</trans-unit>'
                trans_units_in_group = re.findall(trans_unit_pattern, group_content, re.DOTALL)

                if group_id not in groups_structure:
                    groups_structure[group_id] = []

                groups_structure[group_id].extend(trans_units_in_group)

        return groups_structure

    def _reconstruct_with_groups(self, all_trans_units: List[str], groups_structure: Dict[str, List[str]]) -> List[str]:
        result = []
        processed_units = set()

        for group_id, group_trans_units in groups_structure.items():
            if group_trans_units:
                group_opening = self._find_group_opening_tag(group_id)
                result.append(group_opening)

                for unit in group_trans_units:
                    if unit not in processed_units:
                        result.append(unit)
                        processed_units.add(unit)

                result.append('</group>')

        for unit in all_trans_units:
            if unit not in processed_units:
                result.append(unit)

        return result

    def _find_group_opening_tag(self, group_id: str) -> str:
        for part_content, metadata in self.sorted_parts:
            pattern = f'<group[^>]*id=["\']' + re.escape(group_id) + '["\'][^>]*>'
            match = re.search(pattern, part_content)
            if match:
                return match.group(0)

        return f'<group id="{group_id}">'

    def _get_footer_from_first_part(self) -> str:
        first_part_content = self.sorted_parts[0][0]

        clean_content = re.sub(
            r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
            '',
            first_part_content,
            flags=re.DOTALL
        )

        footer_match = re.search(r'</body>.*', clean_content, re.DOTALL)
        if footer_match:
            return footer_match.group(0)

        return '</body>\n</file>\n</xliff>'

    def get_merge_info(self) -> Dict[str, any]:
        if not self.parts_metadata:
            return {}

        first_metadata = self.parts_metadata[0] or {}

        total_segments = 0
        total_words = 0

        for metadata in self.parts_metadata:
            try:
                total_segments += int(metadata.get('part_segments_count', 0))
                total_words += int(metadata.get('part_words_count', 0))
            except (ValueError, TypeError):
                pass

        return {
            'split_id': first_metadata.get('split_id'),
            'original_name': first_metadata.get('original_name'),
            'parts_count': len(self.sorted_parts),
            'total_segments': total_segments,
            'total_words': total_words,
            'merged_at': datetime.utcnow().isoformat() + "Z",
            'encoding': first_metadata.get('encoding', 'utf-8')
        }

    def get_translation_stats(self) -> Dict[str, any]:
        stats = {
            'total_segments': 0,
            'total_words': 0,
            'parts_stats': []
        }

        for idx, metadata in enumerate(self.parts_metadata, 1):
            try:
                part_segments = int(metadata.get('part_segments_count', 0))
                part_words = int(metadata.get('part_words_count', 0))

                part_stats = {
                    'part_number': int(metadata.get('part_number', idx)),
                    'segments_count': part_segments,
                    'words_count': part_words
                }

                stats['parts_stats'].append(part_stats)
                stats['total_segments'] += part_segments
                stats['total_words'] += part_words

            except (ValueError, TypeError):
                continue

        return stats

    def validate_translation_completeness(self) -> Tuple[bool, List[str]]:
        missing_segments = []

        for part_content, metadata in self.sorted_parts:
            trans_unit_pattern = r'<trans-unit[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</trans-unit>'
            trans_units = re.findall(trans_unit_pattern, part_content, re.DOTALL)

            for unit_id, unit_content in trans_units:
                target_pattern = r'<target[^>]*>.*?</target>'
                if not re.search(target_pattern, unit_content, re.DOTALL):
                    missing_segments.append(unit_id)

        return len(missing_segments) == 0, missing_segments

    def verify_byte_identity(self, original_content: str) -> Dict[str, any]:
        merged_content = self.merge()

        clean_original = re.sub(
            r'<!-- SDLXLIFF_SPLIT_METADATA:.*?-->\s*',
            '',
            original_content,
            flags=re.DOTALL
        )

        is_identical = merged_content == clean_original

        result = {
            'is_byte_identical': is_identical,
            'original_size': len(clean_original),
            'merged_size': len(merged_content),
            'size_difference': len(clean_original) - len(merged_content)
        }

        if not is_identical:
            for i, (orig_char, merged_char) in enumerate(zip(clean_original, merged_content)):
                if orig_char != merged_char:
                    result['first_difference_at'] = i
                    result['first_diff_context'] = clean_original[max(0, i - 200):i + 200]
                    result['merged_diff_context'] = merged_content[max(0, i - 200):i + 200]
                    break

        return result

    def _analyze_structure_differences(self, original: str, merged: str) -> Dict[str, any]:
        analysis = {}

        orig_trans_units = len(re.findall(r'<trans-unit', original))
        merged_trans_units = len(re.findall(r'<trans-unit', merged))
        analysis['trans_units_identical'] = orig_trans_units == merged_trans_units
        analysis['trans_units_original'] = orig_trans_units
        analysis['trans_units_merged'] = merged_trans_units

        orig_groups = len(re.findall(r'<group', original))
        merged_groups = len(re.findall(r'<group', merged))
        analysis['groups_preserved'] = orig_groups == merged_groups
        analysis['groups_original'] = orig_groups
        analysis['groups_merged'] = merged_groups

        orig_sdl_elements = len(re.findall(r'<sdl:', original))
        merged_sdl_elements = len(re.findall(r'<sdl:', merged))
        analysis['sdl_elements_preserved'] = orig_sdl_elements == merged_sdl_elements
        analysis['sdl_elements_original'] = orig_sdl_elements
        analysis['sdl_elements_merged'] = merged_sdl_elements

        analysis['all_elements_preserved'] = (
                analysis['trans_units_identical'] and
                analysis['groups_preserved'] and
                analysis['sdl_elements_preserved']
        )

        return analysis


def _extract_trans_units(parts: List[str], log) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    tu_pattern = re.compile(
        r'<trans-unit\s+[^>]*id=["\']([^"\']+)["\'][^>]*>.*?</trans-unit>',
        re.DOTALL,
    )

    for idx, content in enumerate(parts, 1):
        for match in tu_pattern.finditer(content):
            unit_id = match.group(1)
            unit_xml = match.group(0)
            if unit_id in mapping:
                log.warning(f"Duplicate segment {unit_id} in part {idx}")
            mapping[unit_id] = unit_xml

    log.info(f"Collected {len(mapping)} translated segments")
    return mapping

def merge_with_original(
        original_content: str, parts_content: List[str], log_file: str = "merge_details.log"
) -> str:
    from .logger import get_file_logger
    from .diagnostics import take_structure_snapshot, compare_snapshots, log_lost_elements

    log = get_file_logger(log_file)
    log.info("Starting merge with original")

    structure = XmlStructure(original_content)
    orig_snapshot = take_structure_snapshot(original_content)
    replacements = _extract_trans_units(parts_content, log)

    orig_ids = {u.id for u in structure.trans_units}
    unknown_ids = set(replacements) - orig_ids
    for uid in unknown_ids:
        log.warning(f"Translation id {uid} not present in original")

    result_parts = []
    last_pos = 0
    updated = 0
    missing = []

    for unit in structure.trans_units:
        result_parts.append(original_content[last_pos: unit.start_pos])
        if unit.id in replacements:
            new_unit = replacements[unit.id]
            if new_unit != unit.full_xml:
                log.debug(f"Segment {unit.id} replaced")
                updated += 1
            result_parts.append(new_unit)
        else:
            missing.append(unit.id)
            log.debug(f"Segment {unit.id} not found in parts")
            result_parts.append(unit.full_xml)
        last_pos = unit.end_pos

    result_parts.append(original_content[last_pos:])
    merged = "".join(result_parts)

    new_snapshot = take_structure_snapshot(merged)
    lost = compare_snapshots(orig_snapshot, new_snapshot)
    if any(lost.values()):
        log_lost_elements(lost, original_content)

    log.info(
        "Merge finished, %d segments updated, %d untouched", updated, len(missing)
    )
    return merged