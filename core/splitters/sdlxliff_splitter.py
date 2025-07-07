from __future__ import annotations

import re
from pathlib import Path
from typing import List, Set

from lxml import etree

from .sdlxliff_utils import (
    parse_sdlxliff,
    read_text,
    slice_sdlxliff,
    write_text,
    compute_group_stacks,
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
        stacks = compute_group_stacks(pres)
        valid_boundaries = [i for i, st in enumerate(stacks) if not st]
        valid_boundaries = [b for b in valid_boundaries if b <= len(segments)]

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
            boundaries = [0]
            last = 0
            for p in range(1, parts_count):
                target = int(round(p * total_segments / parts_count))
                candidates = [b for b in valid_boundaries if b > last]
                if not candidates:
                    break
                boundary = min(candidates, key=lambda b: abs(b - target))
                if boundary == last:
                    break
                boundaries.append(boundary)
                last = boundary
            if boundaries[-1] != total_segments:
                boundaries.append(total_segments)
            assignments = []
            for i in range(len(boundaries) - 1):
                indices = set(range(boundaries[i], boundaries[i + 1]))
                assignments.append(indices)

        output_dir.mkdir(parents=True, exist_ok=True)
        part_paths: List[Path] = []
        for idx, indices in enumerate(assignments, 1):
            start = min(indices)
            end = max(indices) + 1
            part_text = slice_sdlxliff(header, pres, segments, tail, start, end)
            part_name = f"{file_path.stem}.part{idx}{file_path.suffix}"
            part_path = output_dir / part_name
            write_text(part_path, part_text, encoding, bom)
            part_paths.append(part_path)

        return part_paths
