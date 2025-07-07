from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .sdlxliff_utils import (
    parse_sdxliff,
    read_text,
    reconstruct_sdxliff,
    write_text,
    str_to_bom,
)


class SdxliffMerger:
    """Merge SDXLIFF parts produced by :class:`SdxliffSplitter`."""

    def merge(
        self,
        part_paths: List[Path],
        output_file: Path,
        *,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        should_stop_callback: Optional[Callable[[], bool]] = None,
    ) -> Path:
        if not part_paths:
            raise ValueError("No parts provided")

        parts_dir = part_paths[0].parent
        info_files = list(parts_dir.glob('*.split-info.json'))
        if not info_files:
            raise FileNotFoundError('split-info.json not found')
        info = json.loads(info_files[0].read_text(encoding='utf-8'))

        header = info['header']
        pres = info['pre_segments']
        tail = info['tail']
        encoding = info['encoding']
        bom = str_to_bom(info['bom'])
        total_segments = len(pres) - 1

        segments: Dict[int, str] = {}
        for part in info['parts']:
            part_path = parts_dir / part['file']
            text, _, _ = read_text(part_path)
            _, _, segs, _ = parse_sdxliff(text)
            if len(segs) != len(part['segment_indexes']):
                raise ValueError('Part segment count mismatch')
            for idx, seg in zip(part['segment_indexes'], segs):
                segments[idx] = seg

        if len(segments) != total_segments:
            raise ValueError('Missing segments for merge')

        ordered = [segments[i] for i in range(total_segments)]
        merged_text = reconstruct_sdxliff(header, pres, ordered, tail)
        write_text(output_file, merged_text, encoding, bom)
        if progress_callback:
            progress_callback(100, "merged")
        return output_file
