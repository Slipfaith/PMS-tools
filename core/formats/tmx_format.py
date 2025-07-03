# core/formats/tmx_format.py

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class TmxWriter:
    """Полный TMX writer с поддержкой потоковой записи"""

    @classmethod
    def write(cls, filepath: Path, segments: List[Tuple[str, str, str, str]],
              src_lang: str, tgt_lang: str) -> int:
        """
        Записывает TMX файл

        Args:
            filepath: Путь к файлу
            segments: [(src_text, tgt_text, src_lang, tgt_lang), ...]
            src_lang: Исходный язык по умолчанию
            tgt_lang: Целевой язык по умолчанию

        Returns:
            Количество записанных сегментов
        """
        # Создаем TMX структуру
        tmx = ET.Element("tmx", version="1.4")

        # Заголовок
        header = ET.SubElement(tmx, "header", {
            "creationtool": "ConverterPro",
            "creationtoolversion": "2.0",
            "segtype": "sentence",
            "adminlang": "en-US",
            "srclang": src_lang,
            "datatype": "PlainText"
        })

        # Тело
        body = ET.SubElement(tmx, "body")

        written = 0
        seen = set()

        for src_text, tgt_text, seg_src_lang, seg_tgt_lang in segments:
            # Избегаем дубликатов
            key = (src_text.strip(), tgt_text.strip())
            if key in seen:
                continue
            seen.add(key)

            # Используем языки из сегмента или дефолтные
            actual_src = seg_src_lang if seg_src_lang != "unknown" else src_lang
            actual_tgt = seg_tgt_lang if seg_tgt_lang != "unknown" else tgt_lang

            # Создаем TU
            tu = ET.SubElement(body, "tu")

            # Source TUV
            src_tuv = ET.SubElement(tu, "tuv", {"xml:lang": actual_src})
            src_seg = ET.SubElement(src_tuv, "seg")
            src_seg.text = src_text

            # Target TUV
            tgt_tuv = ET.SubElement(tu, "tuv", {"xml:lang": actual_tgt})
            tgt_seg = ET.SubElement(tgt_tuv, "seg")
            tgt_seg.text = tgt_text

            written += 1

        # Форматируем с отступами
        cls._indent(tmx)

        # Записываем
        tree = ET.ElementTree(tmx)
        tree.write(str(filepath), encoding="utf-8", xml_declaration=True)

        logger.info(f"TMX written: {filepath} ({written} segments)")
        return written

    @classmethod
    def write_streaming(cls, filepath: Path, segments_iter, src_lang: str, tgt_lang: str) -> int:
        """Потоковая запись TMX для очень больших файлов"""
        written = 0
        seen = set()

        with open(filepath, 'w', encoding='utf-8') as f:
            # XML заголовок
            f.write('<?xml version="1.0" encoding="utf-8"?>\n')
            f.write('<tmx version="1.4">\n')
            f.write('  <header creationtool="ConverterPro" creationtoolversion="2.0" ')
            f.write(f'segtype="sentence" adminlang="en-US" srclang="{src_lang}" datatype="PlainText"/>\n')
            f.write('  <body>\n')

            # Записываем сегменты
            for src_text, tgt_text, seg_src_lang, seg_tgt_lang in segments_iter:
                # Избегаем дубликатов
                key = (src_text.strip(), tgt_text.strip())
                if key in seen:
                    continue
                seen.add(key)

                # Определяем языки
                actual_src = seg_src_lang if seg_src_lang != "unknown" else src_lang
                actual_tgt = seg_tgt_lang if seg_tgt_lang != "unknown" else tgt_lang

                # Записываем TU
                f.write('    <tu>\n')
                f.write(f'      <tuv xml:lang="{actual_src}"><seg>{cls._escape_xml(src_text)}</seg></tuv>\n')
                f.write(f'      <tuv xml:lang="{actual_tgt}"><seg>{cls._escape_xml(tgt_text)}</seg></tuv>\n')
                f.write('    </tu>\n')

                written += 1

            # Закрываем
            f.write('  </body>\n')
            f.write('</tmx>\n')

        logger.info(f"TMX written (streaming): {filepath} ({written} segments)")
        return written

    @staticmethod
    def _escape_xml(text: str) -> str:
        """Экранирует XML символы"""
        if not text:
            return ""
        return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))

    @staticmethod
    def _indent(elem, level=0):
        """Добавляет отступы для читаемости"""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            for child in elem:
                TmxWriter._indent(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i