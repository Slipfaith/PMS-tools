import logging
import re
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def take_structure_snapshot(xml_content: str) -> Dict[str, Any]:
    """Takes a simplified snapshot of the SDLXLIFF structure."""
    header_match = re.search(r"^(.*?<body[^>]*>)", xml_content, re.DOTALL)
    snapshot = {
        "header": header_match.group(1) if header_match else "",
        "sdl_blocks": re.findall(r"<sdl:[^>]+>.*?</sdl:[^>]+>", xml_content, re.DOTALL),
        "group_ids": re.findall(r"<group[^>]*id=['\"]([^'\"]+)['\"]", xml_content),
        "cxt_defs": re.findall(r"<cxt-defs[^>]*>.*?</cxt-defs>", xml_content, re.DOTALL),
    }
    logger.debug(
        "Snapshot: %d sdl blocks, %d groups, %d cxt-defs",
        len(snapshot["sdl_blocks"]),
        len(snapshot["group_ids"]),
        len(snapshot["cxt_defs"]),
    )
    return snapshot


def compare_snapshots(original: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, List[str]]:
    """Compares two snapshots and returns lists of lost elements."""
    lost = {
        "sdl_blocks": [b for b in original.get("sdl_blocks", []) if b not in new.get("sdl_blocks", [])],
        "group_ids": [g for g in original.get("group_ids", []) if g not in new.get("group_ids", [])],
        "cxt_defs": [c for c in original.get("cxt_defs", []) if c not in new.get("cxt_defs", [])],
    }
    return lost


def log_lost_elements(lost: Dict[str, List[str]], original_xml: str) -> None:
    """Logs information about lost elements with line references."""
    for block in lost.get("sdl_blocks", []):
        pos = original_xml.find(block)
        line_no = original_xml.count("\n", 0, pos) + 1
        tag_match = re.match(r"<([^\s>]+)", block)
        tag_name = tag_match.group(1) if tag_match else block[:20]
        logger.warning("Lost SDL block %s at line %d", tag_name, line_no)

    for gid in lost.get("group_ids", []):
        pattern = rf"<group[^>]*id=['\"]{re.escape(gid)}['\"]"
        match = re.search(pattern, original_xml)
        if match:
            line_no = original_xml.count("\n", 0, match.start()) + 1
            logger.warning("Lost group id=%s at line %d", gid, line_no)

    for cxt in lost.get("cxt_defs", []):
        pos = original_xml.find(cxt)
        line_no = original_xml.count("\n", 0, pos) + 1
        logger.warning("Lost cxt-defs block at line %d", line_no)
