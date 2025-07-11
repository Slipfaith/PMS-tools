import re
from typing import List

class Splitter:
    """Bit-perfect splitter for SDLXLIFF files."""

    def __init__(self, xml_bytes: bytes):
        self.xml_bytes = xml_bytes
        self.group_matches = list(re.finditer(br'<group\b[\s\S]*?</group>', xml_bytes))
        if not self.group_matches:
            raise ValueError("Файл не содержит <group>")
        self.fragments = self._get_raw_fragments()

    def _get_raw_fragments(self) -> List[bytes]:
        """Return [gap0], [group0], [gap1], [group1], ..., [gapN], [footer]."""
        frags = []
        prev_end = 0
        for m in self.group_matches:
            start, end = m.start(), m.end()
            frags.append(self.xml_bytes[prev_end:start])
            frags.append(self.xml_bytes[start:end])
            prev_end = end
        frags.append(self.xml_bytes[prev_end:])
        return frags

    def split_by_parts(self, num_parts: int) -> List[bytes]:
        """Split file by groups preserving gaps byte-for-byte."""
        group_count = len(self.group_matches)
        groups_per_part = [
            group_count // num_parts + (1 if x < group_count % num_parts else 0)
            for x in range(num_parts)
        ]
        parts = []
        frag_idx = 1
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
