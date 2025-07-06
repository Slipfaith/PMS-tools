"""Utility functions for language code handling."""

from __future__ import annotations

import langcodes

LANG_MAP = {
    "en": "en-US",
    "de": "de-DE",
    "fr": "fr-FR",
    "it": "it-IT",
    "es": "es-ES",
    "pt": "pt-PT",
    "ru": "ru-RU",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "zh": "zh-CN",
    "pl": "pl-PL",
    "ar": "ar-SA",
    "tr": "tr-TR",
    "uk": "uk-UA",
    "ms": "ms-MY",
    "id": "id-ID",
    "th": "th-TH",
}


def get_normalized_lang(lang_code: str | None) -> str | None:
    """Return language code normalized to ``xx`` or ``xx-YY``.

    Unrecognized or empty values return ``None``.
    """
    if not lang_code:
        return None
    code = lang_code.strip().replace("_", "-").lower()
    if "-" in code and len(code) == 5:
        return code
    if code in LANG_MAP:
        return LANG_MAP[code].lower()
    if len(code) == 2 and code.isalpha():
        return f"{code}-xx"
    return None


def get_full_lang_tag(code: str, ask_fn=None) -> str:
    """Return a full language tag for TMX/TBX export."""
    code = code.replace("_", "-").strip()
    try:
        tag = langcodes.standardize_tag(code)
    except Exception:
        tag = code
    if "-" not in tag:
        if tag.lower() in LANG_MAP:
            tag = LANG_MAP[tag.lower()]
        elif ask_fn:
            tag = ask_fn(code)
        else:
            tag = tag + "-XX"
    return tag
