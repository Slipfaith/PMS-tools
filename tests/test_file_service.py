import tempfile
from pathlib import Path
from services.file_service import FileService


def test_is_supported():
    service = FileService()
    tmp = tempfile.NamedTemporaryFile(suffix=".sdltm")
    assert service.is_supported(Path(tmp.name))
    assert not service.is_supported(Path(tmp.name + "x"))


def test_get_format_name_and_icon():
    service = FileService()
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx")
    path = Path(tmp.name)
    assert service.get_format_name(path) == "Excel Workbook"
    assert service.get_format_icon(path) == "📊"
    unknown = Path(tmp.name + ".unknown")
    assert service.get_format_name(unknown) == "Unknown Format"
    assert service.get_format_icon(unknown) == "📄"


def test_detect_files_format_mixed(tmp_path):
    service = FileService()
    file1 = tmp_path / "a.sdltm"
    file1.write_text("test")
    file2 = tmp_path / "b.xlsx"
    file2.write_text("test")
    name, valid = service.detect_files_format([str(file1), str(file2)])
    assert "Смешанные форматы" in name
    assert set(valid) == {str(file1), str(file2)}


def test_normalize_language():
    service = FileService()
    assert service._normalize_language("en") == "en-US"
    assert service._normalize_language("ru-RU") == "ru-ru"
    assert service._normalize_language("") == "unknown"
