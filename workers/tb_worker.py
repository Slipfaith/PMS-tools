from pathlib import Path
from PySide6.QtCore import QThread, Signal
import xml.etree.ElementTree as ET
from typing import List

import langcodes

from utils.logger import log_info, log_export, log_error
from utils.lang_utils import get_full_lang_tag


def parse_multiterm_xml(xml_path: Path):
    with open(xml_path, "rb") as f:
        raw = f.read()
    enc = "utf-16" if b'encoding="UTF-16' in raw[:120] or raw.startswith(b"\xff\xfe") else "utf-8"
    text = raw.decode(enc, errors="replace")
    root = ET.fromstring(text)

    all_langs = set()
    for concept in root.findall("./conceptGrp"):
        for lang_grp in concept.findall("languageGrp"):
            lang_el = lang_grp.find("language")
            lang_code = lang_el.attrib.get("lang") or lang_el.attrib.get("type")
            if lang_code:
                all_langs.add(lang_code)
    langs = sorted(all_langs)

    rows = []
    for concept in root.findall("./conceptGrp"):
        row = {lang: "" for lang in langs}
        for lang_grp in concept.findall("languageGrp"):
            lang_el = lang_grp.find("language")
            lang_code = lang_el.attrib.get("lang") or lang_el.attrib.get("type")
            if not lang_code:
                continue
            term_elems = lang_grp.findall("termGrp/term")
            terms = [t.text or "" for t in term_elems] if term_elems else [""]
            row[lang_code] = terms[0]
        rows.append(row)
    return langs, rows


def export_tmx(rows, src_code, tgt_code, src_norm, tgt_norm, out_path: Path):
    import xml.dom.minidom
    from xml.etree.ElementTree import Element, SubElement, tostring

    tmx = Element("tmx", version="1.4")
    header = SubElement(
        tmx,
        "header",
        {
            "creationtool": "SDLTMConverter",
            "creationtoolversion": "1.0",
            "segtype": "sentence",
            "adminlang": "en-US",
            "srclang": src_norm,
            "datatype": "PlainText",
        },
    )
    body = SubElement(tmx, "body")
    for row in rows:
        src = row.get(src_code, "").strip()
        tgt = row.get(tgt_code, "").strip()
        if not src or not tgt:
            continue
        tu = SubElement(body, "tu")
        tuv_src = SubElement(tu, "tuv", {"xml:lang": src_norm})
        SubElement(tuv_src, "seg").text = src
        tuv_tgt = SubElement(tu, "tuv", {"xml:lang": tgt_norm})
        SubElement(tuv_tgt, "seg").text = tgt
    xml_bytes = tostring(tmx, encoding="utf-8", xml_declaration=True)
    pretty = xml.dom.minidom.parseString(xml_bytes).toprettyxml(indent="  ", encoding="utf-8")
    with open(out_path, "wb") as f:
        f.write(pretty)


def export_xlsx(rows, langs: List[str], out_path: Path):
    import pandas as pd

    data = []
    for row in rows:
        data.append({lang: row.get(lang, "") for lang in langs})
    df = pd.DataFrame(data, columns=langs)
    df.to_excel(out_path, index=False)


class TbWorker(QThread):
    progress = Signal(int)
    finished = Signal(bool, str)
    log_written = Signal(str)

    def __init__(self, xml_path: Path, src_lang: str, ask_fn=None, output_dir=None, export_tmx=True, export_xlsx=False):
        super().__init__()
        self.xml_path = xml_path
        self.src_lang = src_lang
        self.ask_fn = ask_fn
        self.output_dir = output_dir
        self.export_tmx = export_tmx
        self.export_xlsx = export_xlsx

    def run(self):
        try:
            log_info(f"TbWorker started: {self.xml_path}")
            langs, rows = parse_multiterm_xml(self.xml_path)
            src_tag = get_full_lang_tag(self.src_lang, self.ask_fn)
            exported = 0

            src_code = self.src_lang
            src_norm = src_tag

            if self.export_tmx:
                for tgt_code in langs:
                    if tgt_code == src_code:
                        continue
                    tgt_tag = get_full_lang_tag(tgt_code, self.ask_fn)
                    out_name = f"{Path(self.xml_path).stem}_{src_tag}-{tgt_tag}.tmx"
                    out_dir = self.output_dir or str(Path(self.xml_path).parent)
                    out_path = Path(out_dir) / out_name
                    export_tmx(rows, src_code, tgt_code, src_tag, tgt_tag, out_path)
                    self.log_written.emit(f"{src_tag} → {tgt_tag}: {out_path}")
                    log_export(f"TMX saved: {out_path}")
                    exported += 1
                    self.progress.emit(int(100 * exported / (len(langs) - 1)))
            if self.export_xlsx:
                out_name = f"{Path(self.xml_path).stem}_terms.xlsx"
                out_dir = self.output_dir or str(Path(self.xml_path).parent)
                out_path = Path(out_dir) / out_name
                export_xlsx(rows, langs, out_path)
                self.log_written.emit(f"XLSX: {out_path}")
                log_export(f"XLSX saved: {out_path}")
            log_info(f"TbWorker finished: {exported} files")
            self.finished.emit(True, f"Готово! Всего файлов: {exported}")
        except Exception as e:
            log_error(f"TbWorker error: {e}")
            self.finished.emit(False, f"Ошибка: {e}")
