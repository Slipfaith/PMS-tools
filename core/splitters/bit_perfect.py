import re
from typing import List

class Splitter:
    """Bit-perfect splitter for SDLXLIFF-like XML.

    Splits raw XML bytes strictly at ``<group>`` boundaries without
    modifying the original bytes. Joining all parts back together with
    :class:`Merger` will recreate the original file byte-for-byte.
    """

    def __init__(self, xml_bytes: bytes):
        self.xml_bytes = xml_bytes
        # Find all <group ...>...</group> blocks with their positions
        self.group_matches = list(re.finditer(br'<group\b[\s\S]*?</group>', xml_bytes))
        if not self.group_matches:
            raise ValueError("Файл не содержит <group>")
        self.fragments = self._get_raw_fragments()

    def _get_raw_fragments(self) -> List[bytes]:
        """Split XML into header/gaps and groups preserving bytes exactly."""
        frags = []
        prev_end = 0
        for m in self.group_matches:
            start, end = m.start(), m.end()
            frags.append(self.xml_bytes[prev_end:start])  # gap before group
            frags.append(self.xml_bytes[start:end])       # the group itself
            prev_end = end
        frags.append(self.xml_bytes[prev_end:])           # tail after last group
        return frags

    def split_by_parts(self, num_parts: int) -> List[bytes]:
        """Split into ``num_parts`` parts keeping all gaps intact."""
        group_count = len(self.group_matches)
        groups_per_part = [
            group_count // num_parts + (1 if x < group_count % num_parts else 0)
            for x in range(num_parts)
        ]
        parts = []
        frag_idx = 1  # 0 = first gap/header, 1 = first group
        for part_size in groups_per_part:
            if frag_idx == 1:
                part = [self.fragments[0]]
            else:
                part = [self.fragments[frag_idx - 1]]
            for _ in range(part_size):
                part.append(self.fragments[frag_idx])
                part.append(self.fragments[frag_idx + 1])
                frag_idx += 2
            parts.append(b"".join(part))
        return parts


class Merger:
    """Bit-perfect Merger for files produced by :class:`Splitter`."""

    def __init__(self, parts_bytes: List[bytes]):
        self.parts = parts_bytes

    def merge(self) -> bytes:
        return b"".join(self.parts)
