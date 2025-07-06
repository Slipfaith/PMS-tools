from pathlib import Path
from typing import List, Optional, Callable
from copy import deepcopy
from lxml import etree


class SdxliffMerger:
    """Merge SDXLIFF parts created by ``SdxliffSplitter``."""

    def merge(
        self,
        part_paths: List[Path],
        output_path: Path,
        *,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        should_stop_callback: Optional[Callable[[], bool]] = None,
    ) -> Path:
        if not part_paths:
            raise ValueError("No parts provided")
        # parse all
        parts = []
        for p in part_paths:
            tree = etree.parse(str(p))
            root = tree.getroot()
            file_elem = root.find(".//{*}file")
            body = file_elem.find(".//{*}body")
            units = body.findall(".//{*}trans-unit")
            meta = {
                'file_id': file_elem.get('original_file_id'),
                'part_number': int(file_elem.get('part_number', '0')),
                'total_parts': int(file_elem.get('total_parts', '0')),
            }
            parts.append((meta, units, tree.docinfo.encoding))

        total_parts = parts[0][0]['total_parts']
        file_id = parts[0][0]['file_id']
        if len(parts) != total_parts:
            raise ValueError("Missing parts")
        for meta, _, _ in parts:
            if meta['file_id'] != file_id or meta['total_parts'] != total_parts:
                raise ValueError("Inconsistent parts")
        # sort by part_number
        parts.sort(key=lambda x: x[0]['part_number'])
        base_tree = etree.parse(str(part_paths[0]))
        base_root = base_tree.getroot()
        base_file = base_root.find(".//{*}file")
        base_body = base_file.find(".//{*}body")
        for child in list(base_body):
            base_body.remove(child)
        total = len(parts)
        for idx, (_, units, _) in enumerate(parts):
            for u in units:
                base_body.append(deepcopy(u))
            if progress_callback:
                progress_callback(int((idx + 1) / total * 100), f"part {idx + 1}")
            if should_stop_callback and should_stop_callback():
                break
        encoding = parts[0][2] or 'utf-8'
        with open(output_path, 'wb') as f:
            base_tree.write(f, encoding=encoding, xml_declaration=True)
        return output_path
