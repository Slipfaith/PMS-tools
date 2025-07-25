import textwrap
from pathlib import Path
from core.converters.termbase_converter import TermBaseConverter
from core.base import ConversionOptions
import openpyxl


def create_simple_xml(path: Path):
    xml = textwrap.dedent(
        """
        <?xml version='1.0' encoding='UTF-8'?>
        <mtf>
          <conceptGrp>
            <languageGrp>
              <language lang='en'/>
              <termGrp><term>Hello</term></termGrp>
            </languageGrp>
            <languageGrp>
              <language lang='de'/>
              <termGrp><term>Hallo</term></termGrp>
            </languageGrp>
          </conceptGrp>
        </mtf>
        """
    ).strip()
    path.write_text(xml, encoding="utf-8")


def test_termbase_to_xlsx(tmp_path):
    xml_path = tmp_path / "tb.xml"
    create_simple_xml(xml_path)

    converter = TermBaseConverter()
    opts = ConversionOptions(export_tmx=False, export_xlsx=True, source_lang="en")
    result = converter.convert(xml_path, opts)

    assert result.success
    xlsx_path = tmp_path / "tb.xlsx"
    assert xlsx_path.exists()
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    headers = [cell.value for cell in ws[1]]
    assert headers[0].lower().startswith("en")


def test_termbase_to_tmx_has_segments(tmp_path):
    xml_path = tmp_path / "tb.xml"
    create_simple_xml(xml_path)

    converter = TermBaseConverter()
    opts = ConversionOptions(export_tmx=True, export_xlsx=False, source_lang="en")
    result = converter.convert(xml_path, opts)

    assert result.success
    tmx_path = tmp_path / "tb_en-US-de-DE.tmx"
    assert tmx_path.exists()
    text = tmx_path.read_text(encoding="utf-8")
    assert "<tuv" in text and "Hello" in text and "Hallo" in text

