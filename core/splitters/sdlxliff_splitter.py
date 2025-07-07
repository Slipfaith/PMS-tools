from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Set

from lxml import etree

from .sdlxliff_utils import (
    bom_to_str,
    md5_bytes,
    parse_sdlxliff,
    read_text,
    reconstruct_sdlxliff,
    write_text,
)


def count_words(text: str) -> int:
    return len(re.findall(r"\w+", text))


class SdlxliffSplitter:
    def split(
        self,
        file_path: Path,
        parts_count: int,
        output_dir: Path,
        *,
        by_words: bool = False,
    ) -> List[Path]:
        text, encoding, bom = read_text(file_path)
        header, pres, segments, tail = parse_sdlxliff(text)

        # compute words per segment
        words = []
        parser = etree.XMLParser(remove_blank_text=False, strip_cdata=False)
        for seg in segments:
            elem = etree.fromstring(seg.encode("utf-8"), parser)
            src = elem.find('.//{*}source')
            seg_text = "" if src is None else "".join(src.itertext())
            words.append(count_words(seg_text))

        total_segments = len(segments)
        total_words = sum(words)
        if parts_count < 1:
            raise ValueError('parts_count must be >=1')
        if by_words:
            target = total_words // parts_count
            assignments: List[Set[int]] = []
            idx = 0
            for p in range(parts_count):
                part_words = 0
                indices: Set[int] = set()
                while idx < total_segments and (part_words < target or not indices):
                    indices.add(idx)
                    part_words += words[idx]
                    idx += 1
                assignments.append(indices)
            if idx < total_segments:
                assignments[-1].update(range(idx, total_segments))
        else:
            base = total_segments // parts_count
            remainder = total_segments % parts_count
            assignments = []
            start = 0
            for p in range(parts_count):
                count = base + (1 if p < remainder else 0)
                indices = set(range(start, start + count))
                assignments.append(indices)
                start += count

        original_md5 = md5_bytes(file_path.read_bytes())
        info = {
            "bom": bom_to_str(bom),
            "encoding": encoding,
            "header": header,
            "pre_segments": pres,
            "tail": tail,
            "original_md5": original_md5,
            "parts": [],
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        part_paths: List[Path] = []
        for idx, indices in enumerate(assignments, 1):
            part_text = reconstruct_sdlxliff(header, pres, segments, tail, indices)
            part_name = f"{file_path.stem}.part{idx}{file_path.suffix}"
            part_path = output_dir / part_name
            write_text(part_path, part_text, encoding, bom)
            part_paths.append(part_path)
            info["parts"].append({"file": part_name, "segment_indexes": sorted(indices)})

        info_path = output_dir / f"{file_path.name}.split-info.json"
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        return part_paths
