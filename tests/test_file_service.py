import tempfile
from pathlib import Path
from services.file_service import FileService


def test_is_supported():
    service = FileService()
    tmp = tempfile.NamedTemporaryFile(suffix=".sdltm")
    assert service.is_supported(Path(tmp.name))
    assert not service.is_supported(Path(tmp.name + "x"))
    xml_tmp = tempfile.NamedTemporaryFile(suffix=".xml")
    assert service.is_supported(Path(xml_tmp.name))
    tbx_tmp = tempfile.NamedTemporaryFile(suffix=".tbx")
    assert service.is_supported(Path(tbx_tmp.name))
    sdx_tmp = tempfile.NamedTemporaryFile(suffix=".sdxliff")
    assert service.is_supported(Path(sdx_tmp.name))
    sdlx_tmp = tempfile.NamedTemporaryFile(suffix=".sdlxliff")
    assert service.is_supported(Path(sdlx_tmp.name))


def test_get_format_name_and_icon():
    service = FileService()
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx")
    path = Path(tmp.name)
    assert service.get_format_name(path) == "Excel Workbook"
    assert service.get_format_icon(path) == "📊"
    sdlx = tempfile.NamedTemporaryFile(suffix=".sdlxliff")
    spath = Path(sdlx.name)
    assert service.get_format_name(spath) == "SDXLIFF File"
    assert service.get_format_icon(spath) == "📄"
    unknown = Path(tmp.name + ".unknown")
    assert service.get_format_name(unknown) == "Unknown Format"
    assert service.get_format_icon(unknown) == "📄"


def test_detect_files_format_mixed(tmp_path):
    service = FileService()
    file1 = tmp_path / "a.sdltm"
    file1.write_text("test")
    file2 = tmp_path / "b.xlsx"
    file2.write_text("test")
    file3 = tmp_path / "c.sdlxliff"
    file3.write_text("test")
    name, valid = service.detect_files_format([str(file1), str(file2), str(file3)])
    assert "Смешанные форматы" in name
    assert set(valid) == {str(file1), str(file2), str(file3)}


def test_normalize_language():
    service = FileService()
    assert service._normalize_language("en") == "en-US"
    assert service._normalize_language("ru-RU") == "ru-ru"
    assert service._normalize_language("") == "unknown"
