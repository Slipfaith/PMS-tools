import pytest

from utils.xliff_splitter import split_xliff_bytes, merge_xliff_parts


def _make_sample(groups: int) -> bytes:
    header = b"<xliff><file><body>"
    footer = b"</body></file></xliff>"
    blocks = []
    for i in range(1, groups + 1):
        blocks.append(f"<group id='{i}'>t{i}</group>".encode())
    return header + b"".join(b + b"\n" for b in blocks) + footer


def test_split_merge_roundtrip():
    data = _make_sample(5)
    parts = split_xliff_bytes(data, 3)
    assert len(parts) == 3
    result = merge_xliff_parts(parts)
    assert result == data


def test_split_no_groups_error():
    data = b"<xliff></xliff>"
    with pytest.raises(ValueError, match="Файл не содержит тегов <group>"):
        split_xliff_bytes(data, 2)


def test_split_unpaired_groups_error():
    data = b"<group>"  # missing closing tag
    with pytest.raises(ValueError, match="Обнаружены незакрытые/непарные теги"):
        split_xliff_bytes(data, 1)


def test_split_parts_more_than_groups_error():
    data = _make_sample(2)
    with pytest.raises(ValueError, match="Количество частей больше числа групп"):
        split_xliff_bytes(data, 5)
