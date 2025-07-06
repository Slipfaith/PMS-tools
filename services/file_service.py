# services/file_service.py - ОБНОВЛЕННАЯ ВЕРСИЯ

import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class FileService:
    """Сервис для работы с файлами. Вся логика анализа файлов здесь."""

    def __init__(self):
        self.supported_formats = {
            '.sdltm': 'SDL Trados Memory',
            '.sdxliff': 'SDXLIFF File',
            '.sdlxliff': 'SDXLIFF File',
            '.xlsx': 'Excel Workbook',
            '.xls': 'Excel Workbook',
            '.tmx': 'TMX Memory',
            '.xml': 'XML/Termbase',
            '.mtf': 'MultiTerm Format',
            '.tbx': 'TBX Termbase'
        }

    def get_file_info(self, filepath: Path) -> Dict[str, any]:
        """Получает всю информацию о файле для GUI"""
        try:
            info = {
                'name': filepath.name,
                'size_mb': filepath.stat().st_size / (1024 * 1024),
                'format': self.get_format_name(filepath),
                'format_icon': self.get_format_icon(filepath),
                'extra_info': '',
                'is_supported': self.is_supported(filepath)
            }

            # Дополнительная информация в зависимости от формата
            suffix = filepath.suffix.lower()
            if suffix == '.sdltm':
                info['extra_info'] = self._get_sdltm_info(filepath)
            elif suffix in ['.xlsx', '.xls']:
                info['extra_info'] = self._get_excel_info(filepath)
            elif suffix in ['.sdxliff', '.sdlxliff']:
                info['extra_info'] = self.get_sdxliff_info(filepath)

            return info

        except Exception as e:
            logger.warning(f"Error analyzing file {filepath}: {e}")
            return {
                'name': filepath.name,
                'size_mb': 0,
                'format': 'Unknown',
                'format_icon': '📄',
                'extra_info': f'Ошибка: {e}',
                'is_supported': False
            }

    def is_supported(self, filepath: Path) -> bool:
        """Проверяет, поддерживается ли формат"""
        return filepath.suffix.lower() in self.supported_formats

    def get_format_name(self, filepath: Path) -> str:
        """Возвращает название формата"""
        suffix = filepath.suffix.lower()
        return self.supported_formats.get(suffix, 'Unknown Format')

    def get_format_icon(self, filepath: Path) -> str:
        """Возвращает иконку для формата"""
        suffix = filepath.suffix.lower()
        icons = {
            '.sdltm': '🗄️',
            '.sdxliff': '📄',
            '.sdlxliff': '📄',
            '.xlsx': '📊',
            '.xls': '📊',
            '.tmx': '🔄',
            '.xml': '📋',
            '.mtf': '📖',
            '.tbx': '📖'
        }
        return icons.get(suffix, '📄')

    def detect_files_format(self, filepaths: List[str]) -> tuple[str, List[str]]:
        """Определяет формат файлов для drop area"""
        valid_files = []
        detected_formats = set()

        for filepath in filepaths:
            path = Path(filepath)
            if path.exists() and path.is_file() and self.is_supported(path):
                valid_files.append(filepath)
                detected_formats.add(self.get_format_name(path))

        if not valid_files:
            return "Неподдерживаемый формат", []

        if len(detected_formats) == 1:
            format_name = list(detected_formats)[0]
        else:
            format_name = f"Смешанные форматы ({len(detected_formats)})"

        return format_name, valid_files

    def auto_detect_languages(self, filepath: Path) -> Optional[Dict[str, str]]:
        """Автоопределение языков из SDLTM файла"""
        if filepath.suffix.lower() != '.sdltm':
            return None

        try:
            with sqlite3.connect(str(filepath)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT source_segment, target_segment FROM translation_units LIMIT 10")

                src_lang = "unknown"
                tgt_lang = "unknown"

                for src_xml, tgt_xml in cursor.fetchall():
                    try:
                        # Парсим source
                        if src_lang == "unknown":
                            root = ET.fromstring(src_xml)
                            lang_elem = root.find(".//CultureName")
                            if lang_elem is not None and lang_elem.text:
                                src_lang = self._normalize_language(lang_elem.text)

                        # Парсим target
                        if tgt_lang == "unknown":
                            root = ET.fromstring(tgt_xml)
                            lang_elem = root.find(".//CultureName")
                            if lang_elem is not None and lang_elem.text:
                                tgt_lang = self._normalize_language(lang_elem.text)

                        # Если нашли оба языка, прекращаем поиск
                        if src_lang != "unknown" and tgt_lang != "unknown":
                            break

                    except Exception:
                        continue

                if src_lang != "unknown" or tgt_lang != "unknown":
                    return {"source": src_lang, "target": tgt_lang}

        except Exception as e:
            logger.warning(f"Error detecting languages from {filepath}: {e}")

        return None

    def _get_sdltm_info(self, filepath: Path) -> str:
        """Получает информацию об SDLTM файле"""
        try:
            with sqlite3.connect(str(filepath)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM translation_units")
                count = cursor.fetchone()[0]
                return f"{count:,} сегментов"
        except Exception:
            return "Недоступно"

    def get_sdxliff_info(self, filepath: Path) -> str:
        """Возвращает краткую информацию о SDXLIFF файле"""
        try:
            from lxml import etree
            from core.splitters.sdxliff_splitter import count_words
            tree = etree.parse(str(filepath))
            units = tree.findall(".//{*}trans-unit")
            words = 0
            for u in units:
                src = u.find(".//{*}source")
                text = "" if src is None else "".join(src.itertext())
                words += count_words(text)
            return f"{len(units)} сегментов, {words} слов"
        except Exception:
            return "Недоступно"

    def _get_excel_info(self, filepath: Path) -> str:
        """ОБНОВЛЕНО: Получает информацию об Excel файле"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(filepath), read_only=True)

            sheets_count = len(wb.sheetnames)

            # Подсчитываем примерное количество строк
            total_rows = 0
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                if sheet.max_row > 1:  # Исключаем пустые листы
                    total_rows += sheet.max_row - 1  # Минус заголовок

            wb.close()

            if total_rows > 0:
                return f"{sheets_count} листов, ~{total_rows:,} строк"
            else:
                return f"{sheets_count} листов"

        except Exception as e:
            logger.warning(f"Error analyzing Excel file {filepath}: {e}")
            return "Требует настройки"

    def _normalize_language(self, lang_code: str) -> str:
        """Нормализует языковой код"""
        if not lang_code:
            return "unknown"

        # Стандартные замены
        lang_map = {
            "en": "en-US", "de": "de-DE", "fr": "fr-FR", "it": "it-IT",
            "es": "es-ES", "pt": "pt-PT", "ru": "ru-RU", "ja": "ja-JP",
            "ko": "ko-KR", "zh": "zh-CN", "pl": "pl-PL", "tr": "tr-TR"
        }

        code = lang_code.lower().replace("_", "-")

        # Если уже полный код
        if "-" in code and len(code) == 5:
            return code

        # Добавляем регион по умолчанию
        return lang_map.get(code, f"{code}-XX")