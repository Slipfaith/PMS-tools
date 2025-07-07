from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from .sdlxliff_utils import (
    parse_sdlxliff,
    read_text,
    reconstruct_sdlxliff,
    write_text,
    str_to_bom,
)


class SdlxliffMerger:
    def merge(self, parts_dir: Path, output_file: Path) -> Path:
        info_files = list(Path(parts_dir).glob('*.split-info.json'))
        if info_files:
            info = json.loads(info_files[0].read_text(encoding='utf-8'))

            header = info['header']
            pres = info['pre_segments']
            tail = info['tail']
            encoding = info['encoding']
            bom = str_to_bom(info['bom'])
            total_segments = len(pres) - 1

            segments: Dict[int, str] = {}
            for part in info['parts']:
                part_path = Path(parts_dir) / part['file']
                text, _, _ = read_text(part_path)
                _, _, segs, _ = parse_sdlxliff(text)
                if len(segs) != len(part['segment_indexes']):
                    raise ValueError('Part segment count mismatch')
                for idx, seg in zip(part['segment_indexes'], segs):
                    segments[idx] = seg

            if len(segments) != total_segments:
                raise ValueError('Missing segments for merge')

            ordered = [segments[i] for i in range(total_segments)]
            merged_text = reconstruct_sdlxliff(header, pres, ordered, tail)
            write_text(output_file, merged_text, encoding, bom)
            return output_file

        # Fallback: merge without split-info.json
        part_paths = sorted(Path(parts_dir).glob('*.sdlxliff'))
        if not part_paths:
            raise FileNotFoundError('No parts provided')
        text, encoding, bom = read_text(part_paths[0])
        header, _, _, tail = parse_sdlxliff(text)
        all_segments = []
        for p in part_paths:
            text, _, _ = read_text(p)
            _, _, segs, _ = parse_sdlxliff(text)
            all_segments.extend(segs)

        pres = ["" for _ in range(len(all_segments) + 1)]
        merged_text = reconstruct_sdlxliff(header, pres, all_segments, tail)
        write_text(output_file, merged_text, encoding, bom)
        return output_file
