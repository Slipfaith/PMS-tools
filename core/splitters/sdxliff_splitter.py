import hashlib
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable

from lxml import etree


def _read_bom(filepath: Path) -> bool:
    with open(filepath, 'rb') as f:
        first = f.read(3)
    return first == b'\xef\xbb\xbf'


def _compute_file_id(filepath: Path) -> str:
    data = filepath.read_bytes()
    return hashlib.sha256(data).hexdigest()


def count_words(text: str) -> int:
    return len(re.findall(r"\w+", text))


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
        units = body.findall(".//{*}trans-unit")
        total_units = len(units)
        unit_words = []
        for u in units:
            src = u.find(".//{*}source")
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

        output_paths = []
        start = 0
        for idx, count in enumerate(counts):
            part_units = units[start:start + count]
            start += count
            new_tree = etree.ElementTree(deepcopy(root))
            new_root = new_tree.getroot()
            new_file = new_root.find(".//{*}file")
            new_body = new_file.find(".//{*}body")
            for child in list(new_body):
                new_body.remove(child)
            for u in part_units:
                new_body.append(deepcopy(u))
            new_file.set("original_file_id", file_id)
            new_file.set("part_number", str(idx + 1))
            new_file.set("total_parts", str(parts))
            new_file.set("split_timestamp", timestamp)
            new_file.set("segments_in_part", str(len(part_units)))
            words_in_part = sum(unit_words[start - count:start])
            new_file.set("words_in_part", str(words_in_part))
            out_name = f"{filepath.stem}_part{idx + 1}of{parts}{filepath.suffix}"
            out_path = output_dir / out_name
            with open(out_path, "wb") as f:
                if bom:
                    f.write(b"\xef\xbb\xbf")
                new_tree.write(f, encoding=encoding, xml_declaration=True)
            output_paths.append(out_path)
            if progress_callback:
                progress_callback(int((idx + 1) / parts * 100), f"part {idx + 1}")
            if should_stop_callback and should_stop_callback():
                break
        return output_paths
