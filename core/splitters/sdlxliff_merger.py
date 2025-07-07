from __future__ import annotations

from pathlib import Path

from .sdlxliff_utils import (
    parse_sdlxliff,
    read_text,
    reconstruct_sdlxliff,
    write_text,
)


class SdlxliffMerger:
    def merge(self, parts_dir: Path, output_file: Path) -> Path:
        part_paths = sorted(
            p for p in Path(parts_dir).glob('*.sdlxliff') if 'part' in p.stem
        )
        if not part_paths:
            raise FileNotFoundError('No parts provided')
        text, encoding, bom = read_text(part_paths[0])
        header, pres, segs, tail = parse_sdlxliff(text)
        all_pres = [pres[0]]
        all_segments = []
        for i, seg in enumerate(segs):
            all_segments.append(seg)
            all_pres.append(pres[i + 1])

        for p in part_paths[1:]:
            text, _, _ = read_text(p)
            _, pres, segs, _ = parse_sdlxliff(text)
            for i, seg in enumerate(segs):
                all_segments.append(seg)
                all_pres.append(pres[i + 1])

        merged_text = reconstruct_sdlxliff(header, all_pres, all_segments, tail)
        write_text(output_file, merged_text, encoding, bom)
        return output_file
