from pathlib import Path
import pytest
from services.split_service import SplitService

SAMPLE_GROUPS = '''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:sdl="http://sdl.com/FileTypes/SdlXliff/1.0">
  <file original="test" source-language="en-US" target-language="fr-FR">
    <body>
      <group id="g1">
        <sdl:cxts>ctx</sdl:cxts>
        <trans-unit id="1"><source>A</source><target>a</target></trans-unit>
        <group id="g2">
          <trans-unit id="2"><source>B</source><target>b</target></trans-unit>
        </group>
      </group>
      <trans-unit id="3"><source>C</source><target>c</target></trans-unit>
    </body>
  </file>
</xliff>'''

SAMPLE_DEEP = '''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test" source-language="en" target-language="fr">
    <body>
      <group id="a">
        <group id="b">
          <group id="c">
            <trans-unit id="1"><source>a</source><target>a</target></trans-unit>
            <trans-unit id="2"><source>b</source><target>b</target></trans-unit>
          </group>
        </group>
      </group>
    </body>
  </file>
</xliff>'''

def _write_sample(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_recursive_split_and_merge(tmp_path: Path):
    src = _write_sample(tmp_path / "sample.sdxliff", SAMPLE_GROUPS)
    service = SplitService()
    info = service.analyze(src)
    assert info["segments"] == 3

    parts = service.split(src, parts=2)
    merged = tmp_path / "merged.sdxliff"
    service.merge(parts, merged)

    from lxml import etree
    orig = etree.tostring(etree.parse(str(src)), method="c14n")
    merged_data = etree.tostring(etree.parse(str(merged)), method="c14n")
    assert orig == merged_data


def test_deep_groups(tmp_path: Path):
    src = _write_sample(tmp_path / "deep.sdxliff", SAMPLE_DEEP)
    service = SplitService()
    parts = service.split(src, parts=2)
    assert len(parts) == 1
