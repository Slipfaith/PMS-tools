from pathlib import Path
import pytest
from core.splitters.sdxliff_splitter import SdxliffSplitter
from core.splitters.sdxliff_merger import SdxliffMerger
from core.splitters.sdlxliff_utils import md5_bytes


def _write(path: Path, text: str, encoding: str = "utf-8", bom: bool = False) -> Path:
    data = text.encode(encoding)
    if bom:
        if encoding.lower().startswith("utf-16le"):
            data = b"\xff\xfe" + data
        elif encoding.lower().startswith("utf-16be"):
            data = b"\xfe\xff" + data
        else:
            data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    return path


def _basic_sample() -> str:
    return (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<xliff version='1.2' xmlns='urn:oasis:names:tc:xliff:document:1.2'>\n"
        "  <file original='test' source-language='en' target-language='fr'>\n"
        "    <body>\n"
        "      <group id='g1'>\n"
        "        <trans-unit id='1'><source>A</source><target>a</target></trans-unit>\n"
        "        <trans-unit id='2'><source>B</source><target>b</target></trans-unit>\n"
        "      </group>\n"
        "      <trans-unit id='3'><source>C</source><target>c</target></trans-unit>\n"
        "    </body>\n"
        "  </file>\n"
        "</xliff>\n"
    )


def test_split_merge_utf8(tmp_path: Path):
    src = _write(tmp_path / "sample.sdxliff", _basic_sample(), "utf-8", False)
    splitter = SdxliffSplitter()
    parts = splitter.split(src, parts=2, output_dir=tmp_path)
    merger = SdxliffMerger()
    out = tmp_path / "merged.sdxliff"
    merger.merge(parts, out)
    assert md5_bytes(src.read_bytes()) == md5_bytes(out.read_bytes())


def test_split_merge_utf16(tmp_path: Path):
    src = _write(tmp_path / "sample_utf16.sdxliff", _basic_sample(), "utf-16le", True)
    splitter = SdxliffSplitter()
    parts = splitter.split(src, parts=3, output_dir=tmp_path)
    assert len(parts) == 1


def test_large_file(tmp_path: Path):
    segments = []
    for i in range(1, 1001):
        segments.append(f"<trans-unit id='{i}'><source>S{i}</source><target>T{i}</target></trans-unit>")
    body = "\n".join(segments)
    sample = (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<xliff version='1.2' xmlns='urn:oasis:names:tc:xliff:document:1.2'>\n"
        "  <file original='t' source-language='en' target-language='fr'>\n"
        "    <body>\n" + body + "\n    </body>\n  </file>\n</xliff>\n"
    )
    src = _write(tmp_path / "big.sdxliff", sample)
    splitter = SdxliffSplitter()
    parts = splitter.split(src, parts=5, output_dir=tmp_path)
    merger = SdxliffMerger()
    out = tmp_path / "merged.sdxliff"
    merger.merge(parts, out)
    assert md5_bytes(src.read_bytes()) == md5_bytes(out.read_bytes())
