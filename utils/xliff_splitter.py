"""Byte-accurate split and merge utilities for SDLXLIFF/XLIFF/XLP files."""

from __future__ import annotations

import re
from typing import List

GROUP_RE = re.compile(br"<group\b[\s\S]*?</group>", re.IGNORECASE)


def split_xliff_bytes(data: bytes, parts: int) -> List[bytes]:
    """Split a file into ``parts`` pieces on ``<group>`` boundaries.

    Parameters
    ----------
    data:
        Binary content of the source file.
    parts:
        Desired number of chunks (> 0).

    Returns
    -------
    list[bytes]
        Parts in order. Concatenation of all parts equals ``data``.

    Raises
    ------
    ValueError
        If the input can't be split (no groups, unbalanced tags, etc.).
    """
    if parts <= 0:
        raise ValueError("parts must be a positive integer")

    open_count = len(re.findall(br"<group\b", data, re.IGNORECASE))
    close_count = len(re.findall(br"</group>", data, re.IGNORECASE))

    if open_count == 0:
        raise ValueError("Файл не содержит тегов <group> — невозможно разрезать.")
    if open_count != close_count:
        raise ValueError("Обнаружены незакрытые/непарные теги <group>…")
    if parts > open_count:
        raise ValueError("Количество частей больше числа групп.")

    matches = list(GROUP_RE.finditer(data))

    # Header before first group
    header = data[: matches[0].start()]

    # Extract groups along with trailing bytes up to the next group
    group_blocks: List[bytes] = []
    last_end = matches[0].start()
    for m in matches:
        between = data[last_end : m.start()]
        if group_blocks:
            group_blocks[-1] += between
        else:
            header += between
        group_blocks.append(data[m.start() : m.end()])
        last_end = m.end()

    footer = data[last_end:]
    if footer:
        group_blocks[-1] += footer

    total_groups = len(group_blocks)
    base = total_groups // parts
    extra = total_groups % parts

    result: List[bytes] = []
    idx = 0
    for i in range(parts):
        count = base + (1 if i < extra else 0)
        if count == 0:
            result.append(b"")
            continue
        part_blocks = group_blocks[idx : idx + count]
        idx += count
        if i == 0:
            part_data = header + b"".join(part_blocks)
        else:
            part_data = b"".join(part_blocks)
        result.append(part_data)

    return result


def merge_xliff_parts(parts: List[bytes]) -> bytes:
    """Concatenate file parts back together."""
    return b"".join(parts)
