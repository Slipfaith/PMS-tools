import re
from typing import List, Dict
import logging

from .xml_utils import XmlStructure
from .logger import get_file_logger


logger = logging.getLogger(__name__)


def _extract_targets(parts: List[str], log) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    tu_pattern = re.compile(r'<trans-unit\s+[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</trans-unit>', re.DOTALL)
    tgt_pattern = re.compile(r'<target[^>]*>.*?</target>', re.DOTALL)

    for idx, content in enumerate(parts, 1):
        for m in tu_pattern.finditer(content):
            unit_id = m.group(1)
            target_m = tgt_pattern.search(m.group(0))
            if not target_m:
                log.warning(f"Part {idx}: segment {unit_id} has no target")
                continue
            if unit_id in mapping:
                log.warning(f"Duplicate translation for id {unit_id} in part {idx}")
            mapping[unit_id] = target_m.group(0)
    log.info(f"Collected targets for {len(mapping)} segments")
    return mapping


def _replace_target(xml: str, new_target: str) -> str:
    if re.search(r'<target[^>]*>.*?</target>', xml, re.DOTALL):
        return re.sub(r'<target[^>]*>.*?</target>', new_target, xml, count=1, flags=re.DOTALL)
    return re.sub(r'(</trans-unit>)', new_target + r'\1', xml, count=1, flags=re.DOTALL)


def merge_with_original(original_content: str, parts_content: List[str], log_file: str = "merge_details.log") -> str:
    """Merge translations from ``parts_content`` into ``original_content``."""
    log = get_file_logger(log_file)
    structure = XmlStructure(original_content)
    replacements = _extract_targets(parts_content, log)

    result_parts = []
    last_pos = 0
    updated = 0

    for unit in structure.trans_units:
        result_parts.append(original_content[last_pos:unit.start_pos])
        if unit.id in replacements:
            new_unit = _replace_target(unit.full_xml, replacements[unit.id])
            if new_unit == unit.full_xml:
                log.error(f"Failed to insert translation for id {unit.id}")
            else:
                log.info(f"Segment {unit.id} updated")
                updated += 1
            result_parts.append(new_unit)
        else:
            log.debug(f"Segment {unit.id} not found in parts")
            result_parts.append(unit.full_xml)
        last_pos = unit.end_pos

    result_parts.append(original_content[last_pos:])
    log.info(f"Merge finished, {updated} segments updated")
    return "".join(result_parts)
