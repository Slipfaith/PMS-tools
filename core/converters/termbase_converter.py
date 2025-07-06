import xml.dom.minidom
from xml.etree.ElementTree import Element, SubElement, tostring
from pathlib import Path
from typing import List, Dict
import logging
import time

from ..base import (
    StreamingConverter,
    ConversionOptions,
    ConversionResult,
    ConversionStatus,
    ValidationError,
)
from openpyxl import Workbook
from utils.term_base import extract_tb_info
from utils.lang_utils import get_full_lang_tag

logger = logging.getLogger(__name__)


class TermBaseConverter(StreamingConverter):
    """Converter for SDL MultiTerm termbase XML/MTF files."""

    def __init__(self):
        super().__init__()
        self.supported_formats = {".xml", ".mtf"}

    def can_handle(self, filepath: Path) -> bool:
        return filepath.suffix.lower() in self.supported_formats

    def validate(self, filepath: Path) -> bool:
        if not filepath.exists():
            raise ValidationError(f"File not found: {filepath}")
        if not filepath.is_file():
            raise ValidationError(f"Not a file: {filepath}")
        try:
            info = extract_tb_info(filepath)
            if not info.get("rows"):
                raise ValidationError("No terms found in file")
            return True
        except Exception as e:
            raise ValidationError(f"Invalid termbase file: {e}")

    def get_progress_steps(self, filepath: Path) -> int:
        try:
            info = extract_tb_info(filepath)
            return len(info.get("rows", []))
        except Exception:
            return 0

    def convert(self, filepath: Path, options: ConversionOptions) -> ConversionResult:
        start_time = time.time()
        try:
            self.validate(filepath)
            self._update_progress(10, "Parsing termbase...", options)
            info = extract_tb_info(filepath)
            langs: List[str] = info["languages"]
            rows: List[Dict[str, str]] = info["rows"]
            output_files = []

            if options.export_xlsx:
                self._update_progress(40, "Exporting XLSX...", options)
                xlsx_path = filepath.with_suffix(".xlsx")
                src_code = options.source_lang or (langs[0] if langs else "en-US")
                self._write_xlsx(xlsx_path, rows, langs, src_code)
                output_files.append(xlsx_path)

            if options.export_tmx:
                self._update_progress(70, "Exporting TMX...", options)
                src_code = options.source_lang or (langs[0] if langs else "en-US")
                src_tag = get_full_lang_tag(src_code)
                exported = 0
                for tgt_code in langs:
                    if tgt_code == src_code:
                        continue
                    tgt_tag = get_full_lang_tag(tgt_code)
                    out_name = f"{filepath.stem}_{src_tag}-{tgt_tag}.tmx"
                    out_path = filepath.with_name(out_name)
                    self._write_tmx(rows, src_code, tgt_code, src_tag, tgt_tag, out_path)
                    output_files.append(out_path)
                    exported += 1
                logger.info(f"TMX files created: {exported}")

            elapsed = time.time() - start_time
            self._update_progress(100, "Done", options)
            stats = {"rows": len(rows), "languages": langs, "conversion_time": elapsed}
            return ConversionResult(True, output_files, stats, status=ConversionStatus.COMPLETED)
        except Exception as e:
            logger.exception(f"Error converting termbase {filepath}: {e}")
            return ConversionResult(False, [], {"error": str(e)}, errors=[str(e)], status=ConversionStatus.FAILED)

    # Internal helpers -----------------------------------------------------
    @staticmethod
    def _write_xlsx(path: Path, rows: List[Dict[str, str]], langs: List[str], src_code: str):
        from openpyxl import Workbook
        from utils.lang_utils import get_normalized_lang

        src_key = get_normalized_lang(src_code) or src_code.lower()
        ordered = [src_key] + [l for l in langs if l != src_key]

        wb = Workbook()
        ws = wb.active
        ws.append(ordered)
        for row in rows:
            ws.append([row.get(lang, "") for lang in ordered])
        wb.save(str(path))
        logger.info(f"XLSX saved: {path}")

    @staticmethod
    def _write_tmx(rows: List[Dict[str, str]], src_code: str, tgt_code: str, src_tag: str, tgt_tag: str, path: Path):
        tmx = Element("tmx", version="1.4")
        header = SubElement(
            tmx,
            "header",
            {
                "creationtool": "TermBaseConverter",
                "creationtoolversion": "1.0",
                "segtype": "sentence",
                "adminlang": "en-US",
                "srclang": src_tag,
                "datatype": "PlainText",
            },
        )
        body = SubElement(tmx, "body")
        from utils.lang_utils import get_normalized_lang

        src_key = get_normalized_lang(src_code) or src_code.lower()
        tgt_key = get_normalized_lang(tgt_code) or tgt_code.lower()
        for row in rows:
            src = row.get(src_key, "").strip()
            tgt = row.get(tgt_key, "").strip()
            if not src or not tgt:
                continue
            tu = SubElement(body, "tu")
            tuv_src = SubElement(tu, "tuv", {"xml:lang": src_tag})
            SubElement(tuv_src, "seg").text = src
            tuv_tgt = SubElement(tu, "tuv", {"xml:lang": tgt_tag})
            SubElement(tuv_tgt, "seg").text = tgt
        xml_bytes = tostring(tmx, encoding="utf-8", xml_declaration=True)
        pretty = xml.dom.minidom.parseString(xml_bytes).toprettyxml(indent="  ", encoding="utf-8")
        with open(path, "wb") as f:
            f.write(pretty)
        logger.info(f"TMX saved: {path}")

    def convert_streaming(self, filepath: Path, options: ConversionOptions):
        """Streaming is not implemented for termbase conversion."""
        return iter([])

