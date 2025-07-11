from pathlib import Path
import re
from typing import List


def make_split_filenames(src_path: str, parts_count: int) -> List[str]:
    p = Path(src_path)
    name = p.stem
    ext = p.suffix
    parent = p.parent
    return [
        str(parent / f"{name}.{i+1}of{parts_count}{ext}")
        for i in range(parts_count)
    ]


def save_bytes_list(files_bytes: List[bytes], filenames: List[str]) -> None:
    for data, fname in zip(files_bytes, filenames):
        with open(fname, "wb") as f:
            f.write(data)


def read_bytes_list(paths: List[str]) -> List[bytes]:
    return [Path(p).read_bytes() for p in paths]


def sort_split_filenames(file_list: List[str]) -> List[str]:
    pattern = re.compile(r"\.(\d+)of(\d+)\.sdlxliff$", re.IGNORECASE)

    def extract_idx(fname: str):
        m = pattern.search(fname)
        if m:
            return int(m.group(1))
        return float("inf")

    return sorted(file_list, key=extract_idx)
