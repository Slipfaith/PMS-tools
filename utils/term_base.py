from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Dict, List, Any

from .lang_utils import get_normalized_lang


def extract_tb_info(path: Path) -> Dict[str, Any]:
    """Universal parser for MultiTerm files (MTF/XML).

    Returns a dictionary with ``fields``, ``languages`` and ``rows``. Languages
    are normalized to ``xx`` or ``xx-YY`` format.
    """
    ext = path.suffix.lower()
    if ext == ".xml":
        return _extract_from_xml(path)
    if ext == ".mtf":
        return _extract_from_xml(path) if _is_xml(path) else _extract_from_mtf_plain(path)
    raise ValueError(f"Unsupported extension: {ext}")


def _is_xml(path: Path) -> bool:
    with open(path, "rb") as f:
        sig = f.read(200)
    return sig.strip().startswith(b"<?xml") or b"<mtf" in sig or b"<conceptGrp" in sig


def _extract_from_xml(path: Path) -> Dict[str, Any]:
    with open(path, "rb") as f:
        raw = f.read()
    enc = "utf-16" if b'encoding="UTF-16' in raw[:120] or raw.startswith(b"\xff\xfe") else "utf-8"
    text = raw.decode(enc, errors="replace")
    root = ET.fromstring(text)

    langs: List[str] = []
    terms_by_lang: Dict[str, List[str]] = {}

    for concept in root.findall("./conceptGrp"):
        for lang_grp in concept.findall("languageGrp"):
            lang_el = lang_grp.find("language")
            raw_code = (lang_el.attrib.get("lang") or lang_el.attrib.get("type") or "").strip()
            lang_code = get_normalized_lang(raw_code)
            if not lang_code:
                continue
            if lang_code not in langs:
                langs.append(lang_code)
            term_elems = lang_grp.findall("termGrp/term")
            terms = [t.text or "" for t in term_elems] if term_elems else [""]
            terms_by_lang.setdefault(lang_code, []).extend(terms)

    max_count = max((len(t) for t in terms_by_lang.values()), default=0)
    for terms in terms_by_lang.values():
        while len(terms) < max_count:
            terms.append("")

    rows = []
    for idx in range(max_count):
        row = {}
        for lang in langs:
            row[lang] = terms_by_lang.get(lang, [""] * max_count)[idx]
        rows.append(row)

    return {"fields": [], "languages": langs, "rows": rows}


def _extract_from_mtf_plain(path: Path) -> Dict[str, Any]:
    import csv

    with open(path, encoding="utf-8-sig") as f:
        sample = f.read(512)
        f.seek(0)
        delimiter = "\t" if "\t" in sample else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        fields = reader.fieldnames or []
        langs: List[str] = []
        norm_langs: List[str] = []
        for col in fields:
            code = get_normalized_lang(col)
            if code and code not in norm_langs:
                langs.append(col)
                norm_langs.append(code)
        rows_raw = list(reader)
        rows = []
        for row in rows_raw:
            new_row = {}
            for col, val in row.items():
                code = get_normalized_lang(col)
                if code:
                    new_row[code] = val
            rows.append(new_row)
    return {"fields": [], "languages": norm_langs, "rows": rows}
