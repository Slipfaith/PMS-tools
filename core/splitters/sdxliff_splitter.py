import hashlib
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from lxml import etree

NS_XLIFF = "urn:oasis:names:tc:xliff:document:1.2"
SPLIT_NS = "http://pms.tools/sdxliff-split"


def _is_group(elem: etree._Element) -> bool:
    return etree.QName(elem).localname == "group"


def _is_trans_unit(elem: etree._Element) -> bool:
    return etree.QName(elem).localname == "trans-unit"


def _read_bom(filepath: Path) -> bool:
    with open(filepath, 'rb') as f:
        first = f.read(3)
    return first == b'\xef\xbb\xbf'


def _compute_file_id(filepath: Path) -> str:
    data = filepath.read_bytes()
    return hashlib.sha256(data).hexdigest()


def count_words(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _collect_units(body: etree._Element) -> List[dict]:
    """Return metadata for all trans-unit elements in document order."""

    units = []

    def walk(elem: etree._Element, path: List[str]) -> None:
        group_count = 0
        for idx, child in enumerate(list(elem)):
            if _is_group(child):
                ident = child.get("id") or f"idx{group_count}"
                group_count += 1
                walk(child, path + [ident])
            elif _is_trans_unit(child):
                units.append({"element": child, "path": tuple(path), "index": idx})

    walk(body, [])
    return units


class SdxliffSplitter:
    """Split SDXLIFF files preserving structure."""

    def __init__(self):
        pass

    def split(
        self,
        filepath: Path,
        *,
        parts: Optional[int] = None,
        words_per_file: Optional[int] = None,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        should_stop_callback: Optional[Callable[[], bool]] = None,
    ) -> List[Path]:
        if parts is None and words_per_file is None:
            raise ValueError("Either parts or words_per_file must be set")
        if parts is not None and parts < 1:
            raise ValueError("parts must be >= 1")
        if words_per_file is not None and words_per_file < 1:
            raise ValueError("words_per_file must be >= 1")

        output_dir = output_dir or filepath.parent
        bom = _read_bom(filepath)
        parser = etree.XMLParser(remove_blank_text=False)
        tree = etree.parse(str(filepath), parser)
        root = tree.getroot()
        file_elem = root.find(".//{*}file")
        body = file_elem.find(".//{*}body")

        unit_infos = _collect_units(body)
        total_units = len(unit_infos)
        unit_words = []
        for info in unit_infos:
            src = info["element"].find(".//{*}source")
            text = "" if src is None else "".join(src.itertext())
            unit_words.append(count_words(text))
        total_words = sum(unit_words)

        if parts:
            base = total_units // parts
            counts = [base] * parts
            for i in range(total_units - base * parts):
                counts[i] += 1
        else:
            counts = []
            acc = 0
            current = 0
            for w in unit_words:
                if current >= words_per_file and acc:
                    counts.append(acc)
                    acc = 0
                    current = 0
                acc += 1
                current += w
            if acc:
                counts.append(acc)
            parts = len(counts)

        file_id = _compute_file_id(filepath)
        timestamp = datetime.utcnow().isoformat()
        encoding = tree.docinfo.encoding or "utf-8"

        # mark units with part assignment
        idx_start = 0
        for part_idx, cnt in enumerate(counts):
            for i in range(cnt):
                unit_infos[idx_start + i]["part"] = part_idx
            idx_start += cnt

        encoding = tree.docinfo.encoding or "utf-8"
        output_paths = []

        def filter_for_part(part_number: int) -> etree.ElementTree:
            new_tree = etree.ElementTree(deepcopy(root))
            new_root = new_tree.getroot()
            new_body = new_root.find(".//{*}body")

            unit_idx = 0

            def walk(elem: etree._Element, path: List[str]) -> None:
                nonlocal unit_idx
                group_counter = 0
                for idx, child in enumerate(list(elem)):
                    if _is_group(child):
                        ident = child.get("id") or f"idx{group_counter}"
                        group_counter += 1
                        walk(child, path + [ident])
                    elif _is_trans_unit(child):
                        info = unit_infos[unit_idx]
                        assert info["index"] == idx and info["path"] == tuple(path)
                        keep = info.get("part") == part_number
                        unit_idx += 1
                        if not keep:
                            elem.remove(child)
                        else:
                            child.set(f"{{{SPLIT_NS}}}path", "/".join(path))
                            child.set(f"{{{SPLIT_NS}}}pos", str(idx))

            walk(new_body, [])
            return new_tree

        for part_idx in range(parts):
            new_tree = filter_for_part(part_idx)
            new_root = new_tree.getroot()
            new_file = new_root.find(".//{*}file")

            part_units = [u for u in unit_infos if u.get("part") == part_idx]
            words_in_part = sum(unit_words[unit_infos.index(u)] for u in part_units)

            new_file.set("original_file_id", file_id)
            new_file.set("part_number", str(part_idx + 1))
            new_file.set("total_parts", str(parts))
            new_file.set("split_timestamp", timestamp)
            new_file.set("segments_in_part", str(len(part_units)))
            new_file.set("words_in_part", str(words_in_part))

            out_name = f"{filepath.stem}_part{part_idx + 1}of{parts}{filepath.suffix}"
            out_path = output_dir / out_name
            with open(out_path, "wb") as f:
                if bom:
                    f.write(b"\xef\xbb\xbf")
                new_tree.write(f, encoding=encoding, xml_declaration=True)
            output_paths.append(out_path)
            if progress_callback:
                progress_callback(int((part_idx + 1) / parts * 100), f"part {part_idx + 1}")
            if should_stop_callback and should_stop_callback():
                break

        return output_paths
