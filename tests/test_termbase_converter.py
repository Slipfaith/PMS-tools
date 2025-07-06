import textwrap
from pathlib import Path
from core.converters.termbase_converter import TermBaseConverter
from core.base import ConversionOptions


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
    opts = ConversionOptions(export_tmx=False, export_xlsx=True)
    result = converter.convert(xml_path, opts)

    assert result.success
    assert (tmp_path / "tb.xlsx").exists()

