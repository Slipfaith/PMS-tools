from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from copy import deepcopy
from collections import defaultdict
from lxml import etree

from .sdxliff_splitter import SPLIT_NS, _is_group, _is_trans_unit


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

        parsed_parts: List[Tuple[dict, etree._ElementTree]] = []
        for p in part_paths:
            tree = etree.parse(str(p))
            root = tree.getroot()
            file_elem = root.find(".//{*}file")
            meta = {
                "file_id": file_elem.get("original_file_id"),
                "part_number": int(file_elem.get("part_number", "0")),
                "total_parts": int(file_elem.get("total_parts", "0")),
            }
            parsed_parts.append((meta, tree))

        total_parts = parsed_parts[0][0]["total_parts"]
        file_id = parsed_parts[0][0]["file_id"]
        if len(parsed_parts) != total_parts:
            raise ValueError("Missing parts")
        for meta, _ in parsed_parts:
            if meta["file_id"] != file_id or meta["total_parts"] != total_parts:
                raise ValueError("Inconsistent parts")

        parsed_parts.sort(key=lambda x: x[0]["part_number"])

        base_tree = deepcopy(parsed_parts[0][1])
        base_root = base_tree.getroot()
        base_file = base_root.find(".//{*}file")
        base_body = base_file.find(".//{*}body")

        def clear_units(elem: etree._Element) -> None:
            for child in list(elem):
                if _is_group(child):
                    clear_units(child)
                elif _is_trans_unit(child):
                    elem.remove(child)

        clear_units(base_body)

        units_by_path: Dict[str, List[Tuple[int, etree._Element]]] = defaultdict(list)

        def collect(elem: etree._Element, path: List[str]) -> None:
            group_counter = 0
            for idx, child in enumerate(list(elem)):
                if _is_group(child):
                    ident = child.get("id") or f"idx{group_counter}"
                    group_counter += 1
                    collect(child, path + [ident])
                elif _is_trans_unit(child):
                    p = child.get(f"{{{SPLIT_NS}}}path")
                    pos = child.get(f"{{{SPLIT_NS}}}pos")
                    gpath = tuple(p.split("/")) if p else tuple(path)
                    index = int(pos) if pos is not None else idx
                    units_by_path["/".join(gpath)].append((index, deepcopy(child)))

        for meta, tree in parsed_parts:
            part_body = tree.getroot().find(".//{*}body")
            collect(part_body, [])

        def find_group(current: etree._Element, tokens: List[str]) -> etree._Element:
            elem = current
            for token in tokens:
                group_idx = 0
                found = None
                for child in elem:
                    if _is_group(child):
                        gid = child.get("id")
                        if gid == token:
                            found = child
                            break
                        if gid is None and token.startswith("idx") and group_idx == int(token[3:]):
                            found = child
                            break
                        group_idx += 1
                if found is None:
                    raise ValueError(f"Group path {'/'.join(tokens)} not found")
                elem = found
            return elem

        for gpath, items in units_by_path.items():
            group_elem = find_group(base_body, [t for t in gpath.split("/") if t])
            items.sort(key=lambda x: x[0])
            for index, unit in items:
                unit.attrib.pop(f"{{{SPLIT_NS}}}path", None)
                unit.attrib.pop(f"{{{SPLIT_NS}}}pos", None)
                group_elem.insert(index, unit)

        # clean metadata attributes from <file>
        for attr in [
            "original_file_id",
            "part_number",
            "total_parts",
            "split_timestamp",
            "segments_in_part",
            "words_in_part",
        ]:
            if attr in base_file.attrib:
                base_file.attrib.pop(attr)

        etree.cleanup_namespaces(base_tree)

        encoding = parsed_parts[0][1].docinfo.encoding or "utf-8"
        with open(output_path, "wb") as f:
            base_tree.write(f, encoding=encoding, xml_declaration=True)

        if progress_callback:
            progress_callback(100, "merged")
        return output_path
