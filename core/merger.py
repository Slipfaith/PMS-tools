from typing import List

class Merger:
    """Bit-perfect SDLXLIFF merger."""

    def __init__(self, parts_bytes: List[bytes]):
        self.parts = parts_bytes

    def merge(self) -> bytes:
        """Return concatenated bytes of all parts."""
        return b"".join(self.parts)
