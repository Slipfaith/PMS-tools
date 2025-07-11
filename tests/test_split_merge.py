from core import Splitter, Merger
from utils import sort_split_filenames


def test_split_merge_roundtrip():
    xml = (
        b"<file>header"
        b"<group id='1'>A</group>"
        b"<group id='2'>B</group>"
        b"footer</file>"
    )
    splitter = Splitter(xml)
    parts = splitter.split_by_parts(2)
    merger = Merger(parts)
    merged = merger.merge()
    assert merged == xml


def test_sort_split_filenames():
    names = ["file.2of3.sdlxliff", "file.1of3.sdlxliff"]
    sorted_names = sort_split_filenames(names)
    assert sorted_names == ["file.1of3.sdlxliff", "file.2of3.sdlxliff"]
