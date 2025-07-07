import hashlib
import json
import re
from pathlib import Path
from typing import Optional, Tuple


BOM_UTF8 = b"\xef\xbb\xbf"
BOM_UTF16_LE = b"\xff\xfe"
BOM_UTF16_BE = b"\xfe\xff"


def detect_bom(data: bytes) -> Tuple[Optional[bytes], str]:
    if data.startswith(BOM_UTF8):
        return BOM_UTF8, "utf-8"
    if data.startswith(BOM_UTF16_LE):
        return BOM_UTF16_LE, "utf-16le"
    if data.startswith(BOM_UTF16_BE):
        return BOM_UTF16_BE, "utf-16be"
    return None, "utf-8"


def bom_to_str(bom: Optional[bytes]) -> str:
    return bom.hex() if bom else ""


def str_to_bom(s: str) -> Optional[bytes]:
    return bytes.fromhex(s) if s else None


def read_text(path: Path) -> Tuple[str, str, Optional[bytes]]:
    data = path.read_bytes()
    bom, encoding = detect_bom(data)
    if bom:
        data = data[len(bom) :]
    else:
        m = re.search(br"encoding=['\"]([^'\"]+)['\"]", data[:100])
        if m:
            encoding = m.group(1).decode("ascii", errors="ignore")
    text = data.decode(encoding)
    return text, encoding, bom


def write_text(path: Path, text: str, encoding: str, bom: Optional[bytes]) -> None:
    data = text.encode(encoding)
    with open(path, "wb") as f:
        if bom:
            f.write(bom)
        f.write(data)


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


TRANS_UNIT_RE = re.compile(
    r"<(?:[\w.-]+:)?trans-unit\b[^>]*>.*?</(?:[\w.-]+:)?trans-unit>", re.DOTALL
)
BODY_START_RE = re.compile(r"<(?:[\w.-]+:)?body\b[^>]*>")
BODY_END_RE = re.compile(r"</(?:[\w.-]+:)?body>")


def parse_sdlxliff(text: str) -> Tuple[str, list[str], list[str], str]:
    start_m = BODY_START_RE.search(text)
    end_m = BODY_END_RE.search(text)
    if not start_m or not end_m:
        raise ValueError("No <body> element found")
    header = text[: start_m.end()]
    body_content = text[start_m.end() : end_m.start()]
    tail = text[end_m.start() :]

    segments: list[str] = []
    pres: list[str] = []
    pos = 0
    for m in TRANS_UNIT_RE.finditer(body_content):
        pres.append(body_content[pos : m.start()])
        segments.append(m.group(0))
        pos = m.end()
    pres.append(body_content[pos:])
    return header, pres, segments, tail


def reconstruct_sdlxliff(header: str, pres: list[str], segs: list[str], tail: str, include: Optional[set[int]] = None) -> str:
    include = include or set(range(len(segs)))
    parts = [header, pres[0]]
    for i, seg in enumerate(segs):
        if i in include:
            parts.append(seg)
        parts.append(pres[i + 1])
    parts.append(tail)
    return "".join(parts)


# SDXLIFF files share the same basic structure as SDLXLIFF. To avoid code
# duplication we simply expose aliases that reuse the SDLXLIFF parsing and
# reconstruction logic. This allows the split/merge logic for both file types to
# rely on the same byte preserving helpers.

def parse_sdxliff(text: str) -> Tuple[str, list[str], list[str], str]:
    """Alias of :func:`parse_sdlxliff` for SDXLIFF files."""

    return parse_sdlxliff(text)


def reconstruct_sdxliff(
    header: str,
    pres: list[str],
    segs: list[str],
    tail: str,
    include: Optional[set[int]] = None,
) -> str:
    """Alias of :func:`reconstruct_sdlxliff` for SDXLIFF files."""

    return reconstruct_sdlxliff(header, pres, segs, tail, include)
