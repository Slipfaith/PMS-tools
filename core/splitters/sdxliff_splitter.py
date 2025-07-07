from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, List, Optional, Set

from lxml import etree

from .sdlxliff_utils import (
    bom_to_str,
    md5_bytes,
    parse_sdxliff,
    read_text,
    extract_namespaces,
    reconstruct_sdxliff,
    write_text,
)


def count_words(text: str) -> int:
    return len(re.findall(r"\w+", text))


class SdxliffSplitter:
    """Byte preserving splitter for SDXLIFF files."""

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
        text, encoding, bom = read_text(filepath)
        header, pres, segments, tail = parse_sdxliff(text)

        words = []
        parser = etree.XMLParser(remove_blank_text=False, strip_cdata=False)
        namespaces = extract_namespaces(header)
        ns_attrs = " ".join(
            [f'xmlns="{uri}"' if not prefix else f"xmlns:{prefix}=\"{uri}\"" for prefix, uri in namespaces.items()]
        )
        for seg in segments:
            wrapped = f"<wrapper {ns_attrs}>{seg}</wrapper>"
            elem = etree.fromstring(wrapped.encode("utf-8"), parser)
            src = elem.find('.//{*}source')
            seg_text = "" if src is None else "".join(src.itertext())
            words.append(count_words(seg_text))

        total_segments = len(segments)

        assignments: List[Set[int]] = []
        if parts is not None:
            base = total_segments // parts
            remainder = total_segments % parts
            start = 0
            for p in range(parts):
                count = base + (1 if p < remainder else 0)
                assignments.append(set(range(start, start + count)))
                start += count
        else:
            idx = 0
            while idx < total_segments:
                part_words = 0
                indices: Set[int] = set()
                while idx < total_segments and (part_words < words_per_file or not indices):
                    indices.add(idx)
                    part_words += words[idx]
                    idx += 1
                assignments.append(indices)

        info = {
            "bom": bom_to_str(bom),
            "encoding": encoding,
            "header": header,
            "pre_segments": pres,
            "tail": tail,
            "original_md5": md5_bytes(filepath.read_bytes()),
            "parts": [],
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        part_paths: List[Path] = []
        for idx, indices in enumerate(assignments, 1):
            part_text = reconstruct_sdxliff(header, pres, segments, tail, indices)
            part_name = f"{filepath.stem}_part{idx}of{len(assignments)}{filepath.suffix}"
            part_path = output_dir / part_name
            write_text(part_path, part_text, encoding, bom)
            part_paths.append(part_path)
            info["parts"].append({"file": part_name, "segment_indexes": sorted(indices)})
            if progress_callback:
                progress_callback(int(idx / len(assignments) * 100), f"part {idx}")
            if should_stop_callback and should_stop_callback():
                break

        info_path = output_dir / f"{filepath.name}.split-info.json"
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        return part_paths
