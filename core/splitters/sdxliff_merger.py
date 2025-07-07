from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from .sdlxliff_utils import (
    parse_sdxliff,
    read_text,
    reconstruct_sdxliff,
    write_text,
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

        part_paths = sorted(part_paths)
        text, encoding, bom = read_text(part_paths[0])
        header, pres, segs, tail = parse_sdxliff(text)
        all_pres = [pres[0]]
        all_segments = []
        for i, seg in enumerate(segs):
            all_segments.append(seg)
            all_pres.append(pres[i + 1])

        for path in part_paths[1:]:
            text, _, _ = read_text(path)
            _, pres, segs, _ = parse_sdxliff(text)
            for i, seg in enumerate(segs):
                all_segments.append(seg)
                all_pres.append(pres[i + 1])

        merged_text = reconstruct_sdxliff(header, all_pres, all_segments, tail)
        write_text(output_file, merged_text, encoding, bom)
        if progress_callback:
            progress_callback(100, "merged")
        return output_file
