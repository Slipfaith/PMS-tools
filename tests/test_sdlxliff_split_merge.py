from pathlib import Path
from core.splitters import SdlxliffSplitter, SdlxliffMerger
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
    src = _write(tmp_path / "sample.sdlxliff", _basic_sample(), "utf-8", False)
    splitter = SdlxliffSplitter()
    parts = splitter.split(src, 2, tmp_path)
    merger = SdlxliffMerger()
    out = tmp_path / "merged.sdlxliff"
    merger.merge(tmp_path, out)
    assert md5_bytes(src.read_bytes()) == md5_bytes(out.read_bytes())


def test_split_merge_utf16(tmp_path: Path):
    src = _write(tmp_path / "sample_utf16.sdlxliff", _basic_sample(), "utf-16le", True)
    splitter = SdlxliffSplitter()
    parts = splitter.split(src, 3, tmp_path)
    merger = SdlxliffMerger()
    out = tmp_path / "merged.sdlxliff"
    merger.merge(tmp_path, out)
    assert md5_bytes(src.read_bytes()) == md5_bytes(out.read_bytes())


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
    src = _write(tmp_path / "big.sdlxliff", sample)
    splitter = SdlxliffSplitter()
    splitter.split(src, 5, tmp_path)
    merger = SdlxliffMerger()
    out = tmp_path / "merged.sdlxliff"
    merger.merge(tmp_path, out)
    assert md5_bytes(src.read_bytes()) == md5_bytes(out.read_bytes())
