from pathlib import Path
from services.split_service import SplitService
from lxml import etree

SAMPLE = '''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test" source-language="en-US" target-language="fr-FR">
    <body>
      <trans-unit id="1"><source>Hello world</source><target>Bonjour</target></trans-unit>
      <trans-unit id="2"><source>Goodbye</source><target>Au revoir</target></trans-unit>
    </body>
  </file>
</xliff>'''

SAMPLE_SEG_DEFS = '''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0">
  <file original="test" source-language="en" target-language="fr">
    <body>
      <trans-unit id="1">
        <sdl:seg-defs><sdl:seg id="1"/></sdl:seg-defs>
        <source>Hello</source><target>Bonjour</target>
      </trans-unit>
    </body>
  </file>
</xliff>'''

def test_split_and_merge(tmp_path: Path):
    src = tmp_path / "sample.sdxliff"
    src.write_text(SAMPLE, encoding="utf-8")

    service = SplitService()
    info = service.analyze(src)
    assert info["segments"] == 2
    assert info["words"] == 3
    assert info["characters"] == 18

    parts = service.split(src, parts=2)
    assert len(parts) == 2

    merged = tmp_path / "merged.sdxliff"
    service.merge(parts, merged)

    tree = etree.parse(str(merged))
    units = tree.findall(".//{*}trans-unit")
    assert len(units) == 2


def test_split_with_seg_defs(tmp_path: Path):
    src = tmp_path / "sample_defs.sdxliff"
    src.write_text(SAMPLE_SEG_DEFS, encoding="utf-8")

    service = SplitService()
    parts = service.split(src, parts=1)
    assert len(parts) == 1
