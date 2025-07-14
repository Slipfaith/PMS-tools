from pathlib import Path
from typing import Callable, List, Optional

from ..io_utils import read_bytes_list, sort_split_filenames


class SdxliffMerger:
    """Bit-perfect merger that concatenates split SDXLIFF parts."""

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

        ordered = sort_split_filenames([str(p) for p in part_paths])
        parts = read_bytes_list(ordered)

        with open(output_path, "wb") as out:
            for idx, chunk in enumerate(parts):
                out.write(chunk)
                if progress_callback:
                    progress_callback(int((idx + 1) / len(parts) * 100), f"part {idx + 1}")
                if should_stop_callback and should_stop_callback():
                    break

        return output_path
