import pytest

import sqlite3
from core.converters.sdltm import SdltmConverter
from core.base import ConversionOptions


def test_language_override_in_streaming(tmp_path):
    db_path = tmp_path / "mem.sdltm"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE translation_units (source_segment TEXT, target_segment TEXT)"
        )
        src_xml = '<segment><Text><Value>Hello</Value></Text><CultureName>en-US</CultureName></segment>'
        tgt_xml = '<segment><Text><Value>Salut</Value></Text><CultureName>fr-FR</CultureName></segment>'
        conn.execute(
            "INSERT INTO translation_units (source_segment, target_segment) VALUES (?, ?)",
            (src_xml, tgt_xml),
        )

    conv = SdltmConverter()
    opts = ConversionOptions(source_lang="de-DE", target_lang="ru-RU", export_tmx=False, export_xlsx=False)
    segs = list(conv.convert_streaming(db_path, opts))

    assert segs[0][2].lower() == "de-de"
    assert segs[0][3].lower() == "ru-ru"
