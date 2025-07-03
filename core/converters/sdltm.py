# core/converters/sdltm.py

import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator, Tuple
import logging

from ..base import (
    FileConverter, ConversionResult, ConversionOptions, StreamingConverter,
    ConversionError, ValidationError
)

logger = logging.getLogger(__name__)


class SdltmConverter(StreamingConverter):
    """Полный конвертер для SDLTM файлов с потоковой обработкой"""

    def can_handle(self, filepath: Path) -> bool:
        return filepath.suffix.lower() == '.sdltm'

    def validate(self, filepath: Path) -> bool:
        """Валидирует SDLTM файл"""
        try:
            with sqlite3.connect(str(filepath)) as conn:
                cursor = conn.cursor()

                # Проверяем наличие таблицы translation_units
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='translation_units'")
                if not cursor.fetchone():
                    raise ValidationError(f"No translation_units table in {filepath}")

                # Проверяем структуру
                cursor.execute("PRAGMA table_info(translation_units)")
                columns = {row[1] for row in cursor.fetchall()}
                required = {'source_segment', 'target_segment'}

                if not required.issubset(columns):
                    raise ValidationError(f"Missing columns {required - columns} in {filepath}")

                return True

        except sqlite3.Error as e:
            raise ValidationError(f"Database error in {filepath}: {e}")

    def get_progress_steps(self, filepath: Path) -> int:
        """Получает общее количество сегментов для прогресса"""
        try:
            with sqlite3.connect(str(filepath)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM translation_units")
                return cursor.fetchone()[0]
        except sqlite3.Error:
            return 0

    def convert(self, filepath: Path, options: ConversionOptions) -> ConversionResult:
        """Конвертирует SDLTM файл"""
        try:
            # Валидация
            if not self.validate(filepath):
                return ConversionResult(False, [], {"error": "Validation failed"}, ["File validation failed"])

            # Получаем общее количество сегментов
            total_segments = self.get_progress_steps(filepath)
            if total_segments == 0:
                return ConversionResult(False, [], {"total": 0}, ["No segments found"])

            self._update_progress(5, f"Found {total_segments} segments", options)

            # Извлекаем сегменты потоково
            segments = []
            seen_pairs = set()
            detected_src_lang = "unknown"
            detected_tgt_lang = "unknown"

            stats = {
                "total": total_segments,
                "processed": 0,
                "exported": 0,
                "skipped_empty": 0,
                "skipped_tags": 0,
                "skipped_duplicates": 0
            }

            for src_text, tgt_text, src_lang, tgt_lang in self.convert_streaming(filepath, options):
                # Автоопределение языков из первых сегментов
                if detected_src_lang == "unknown" and src_lang != "unknown":
                    detected_src_lang = src_lang
                    logger.info(f"Auto-detected source language: {src_lang}")

                if detected_tgt_lang == "unknown" and tgt_lang != "unknown":
                    detected_tgt_lang = tgt_lang
                    logger.info(f"Auto-detected target language: {tgt_lang}")

                # Проверяем на дубликаты
                pair_key = (src_text, tgt_text)
                if pair_key in seen_pairs:
                    stats["skipped_duplicates"] += 1
                    continue

                seen_pairs.add(pair_key)
                segments.append((src_text, tgt_text, src_lang, tgt_lang))
                stats["exported"] += 1

            if not segments:
                return ConversionResult(False, [], stats, ["No valid segments found"])

            # Определяем языки (используем автоопределенные если они есть)
            if detected_src_lang != "unknown":
                src_lang = detected_src_lang
            else:
                src_lang = options.source_lang

            if detected_tgt_lang != "unknown":
                tgt_lang = detected_tgt_lang
            else:
                tgt_lang = options.target_lang

            logger.info(f"Using languages: {src_lang} -> {tgt_lang}")

            self._update_progress(80, "Writing output files...", options)

            # Записываем файлы
            output_files = []

            if options.export_tmx:
                tmx_path = filepath.with_suffix('.tmx')
                self._write_tmx(tmx_path, segments, src_lang, tgt_lang)
                output_files.append(tmx_path)
                logger.info(f"TMX created: {tmx_path}")

            if options.export_xlsx:
                xlsx_path = filepath.with_suffix('.xlsx')
                self._write_xlsx(xlsx_path, segments, src_lang, tgt_lang)
                output_files.append(xlsx_path)
                logger.info(f"XLSX created: {xlsx_path}")

            self._update_progress(100, f"Completed! Exported {stats['exported']} segments", options)

            return ConversionResult(
                success=True,
                output_files=output_files,
                stats=stats
            )

        except Exception as e:
            logger.exception(f"Error converting {filepath}")
            return ConversionResult(
                success=False,
                output_files=[],
                stats={"error": str(e)},
                errors=[str(e)]
            )

    def convert_streaming(self, filepath: Path, options: ConversionOptions) -> Iterator[Tuple[str, str, str, str]]:
        """Потоковая обработка SDLTM с батчами (обычная версия)"""
        with sqlite3.connect(str(filepath)) as conn:
            cursor = conn.cursor()

            # Получаем общее количество для прогресса
            cursor.execute("SELECT COUNT(*) FROM translation_units")
            total = cursor.fetchone()[0]

            processed = 0
            batch_size = options.batch_size
            offset = 0

            while True:
                # Проверяем на остановку
                if self._should_stop(options):
                    logger.info("SDLTM conversion stopped by user")
                    break

                # Читаем батч
                cursor.execute(
                    "SELECT source_segment, target_segment FROM translation_units LIMIT ? OFFSET ?",
                    (batch_size, offset)
                )

                batch = cursor.fetchall()
                if not batch:
                    break

                # Обрабатываем батч
                for src_xml, tgt_xml in batch:
                    processed += 1

                    try:
                        src_text, src_lang = self._parse_segment_xml(src_xml)
                        tgt_text, tgt_lang = self._parse_segment_xml(tgt_xml)

                        # Пропускаем пустые
                        if not src_text.strip() or not tgt_text.strip():
                            continue

                        # Пропускаем сегменты только с тегами
                        if self._is_tags_only(src_xml) or self._is_tags_only(tgt_xml):
                            continue

                        yield (src_text, tgt_text, src_lang, tgt_lang)

                    except Exception as e:
                        logger.debug(f"Error parsing segment: {e}")
                        continue

                # Обновляем прогресс
                progress = min(75, int((processed / total) * 75))
                self._update_progress(progress, f"Processed {processed}/{total}", options)

                offset += batch_size

    def _parse_segment_xml(self, xml_segment: str) -> Tuple[str, str]:
        """Парсит XML сегмент SDLTM"""
        try:
            root = ET.fromstring(xml_segment)

            # Извлекаем текст
            text_elem = root.find(".//Text/Value")
            text = text_elem.text if text_elem is not None and text_elem.text else ""

            # Извлекаем язык
            lang_elem = root.find(".//CultureName")
            lang = lang_elem.text if lang_elem is not None and lang_elem.text else "unknown"

            # Нормализуем язык
            lang = self._normalize_language(lang)

            return text.strip(), lang

        except ET.ParseError:
            return "", "unknown"
        except Exception:
            return "", "unknown"
        """Потоковая обработка SDLTM с батчами"""
        with sqlite3.connect(str(filepath)) as conn:
            cursor = conn.cursor()

            # Получаем общее количество для прогресса
            cursor.execute("SELECT COUNT(*) FROM translation_units")
            total = cursor.fetchone()[0]

            processed = 0
            batch_size = options.batch_size
            offset = 0

            while True:
                # Проверяем на остановку
                if self._should_stop(options):
                    logger.info("SDLTM conversion stopped by user")
                    break

                # Читаем батч
                cursor.execute(
                    "SELECT source_segment, target_segment FROM translation_units LIMIT ? OFFSET ?",
                    (batch_size, offset)
                )

                batch = cursor.fetchall()
                if not batch:
                    break

                # Обрабатываем батч
                for src_xml, tgt_xml in batch:
                    processed += 1

                    try:
                        src_text, src_lang = self._parse_segment_xml(src_xml)
                        tgt_text, tgt_lang = self._parse_segment_xml(tgt_xml)

                        # Пропускаем пустые
                        if not src_text.strip() or not tgt_text.strip():
                            continue

                        # Пропускаем сегменты только с тегами
                        if self._is_tags_only(src_xml) or self._is_tags_only(tgt_xml):
                            continue

                        yield (src_text, tgt_text, src_lang, tgt_lang)

                    except Exception as e:
                        logger.debug(f"Error parsing segment: {e}")
                        continue

                # Обновляем прогресс
                progress = min(75, int((processed / total) * 75))
                self._update_progress(progress, f"Processed {processed}/{total}", options)

                offset += batch_size

    def convert_streaming_detailed(self, filepath: Path, options: ConversionOptions):
        """Потоковая обработка SDLTM с детальным анализом пропусков"""
        with sqlite3.connect(str(filepath)) as conn:
            cursor = conn.cursor()

            # Получаем общее количество для прогресса
            cursor.execute("SELECT COUNT(*) FROM translation_units")
            total = cursor.fetchone()[0]

            processed = 0
            batch_size = options.batch_size
            offset = 0

            while True:
                # Проверяем на остановку
                if self._should_stop(options):
                    logger.info("SDLTM conversion stopped by user")
                    break

                # Читаем батч
                cursor.execute(
                    "SELECT source_segment, target_segment FROM translation_units LIMIT ? OFFSET ?",
                    (batch_size, offset)
                )

                batch = cursor.fetchall()
                if not batch:
                    break

                # Обрабатываем батч
                for src_xml, tgt_xml in batch:
                    processed += 1

                    try:
                        src_text, src_lang = self._parse_segment_xml(src_xml)
                        tgt_text, tgt_lang = self._parse_segment_xml(tgt_xml)

                        # Проверяем причины пропуска
                        skip_reason = None

                        # Пропускаем пустые (и source, и target пустые)
                        if not src_text.strip() and not tgt_text.strip():
                            skip_reason = "empty"
                        # Пропускаем, если один из сегментов пустой
                        elif not src_text.strip() or not tgt_text.strip():
                            skip_reason = "empty"
                        # Пропускаем сегменты только с тегами
                        elif self._is_tags_only(src_xml) and self._is_tags_only(tgt_xml):
                            skip_reason = "tags_only"

                        yield (src_text, tgt_text, src_lang, tgt_lang, skip_reason)

                    except Exception as e:
                        logger.debug(f"Error parsing segment: {e}")
                        yield ("", "", "unknown", "unknown", "error")
                        continue

                # Обновляем прогресс
                progress = min(75, int((processed / total) * 75))
                self._update_progress(progress, f"Processed {processed}/{total}", options)

                offset += batch_size

    def _log_conversion_details(self, filepath: Path, stats: dict, skipped_details: dict, src_lang: str, tgt_lang: str):
        """Логирует подробную статистику конвертации"""

        # Основная статистика
        logger.info(f"=== Conversion Summary for {filepath.name} ===")
        logger.info(f"Languages: {src_lang} -> {tgt_lang}")
        logger.info(f"Total segments in SDLTM: {stats['total_in_sdltm']}")
        logger.info(f"Successfully exported to TMX: {stats['exported_to_tmx']}")
        logger.info(f"Skipped empty segments: {stats['skipped_empty']}")
        logger.info(f"Skipped tag-only segments: {stats['skipped_tags_only']}")
        logger.info(f"Skipped duplicate segments: {stats['skipped_duplicates']}")

        # Детальная информация о пропущенных сегментах (первые 5 из каждой категории)
        if skipped_details["empty"]:
            logger.info(f"--- Empty segments (showing first 5 of {len(skipped_details['empty'])}) ---")
            for i, (src, tgt) in enumerate(skipped_details["empty"][:5]):
                logger.info(f"  Empty #{i + 1}: '{src}' | '{tgt}'")

        if skipped_details["tags_only"]:
            logger.info(f"--- Tag-only segments (showing first 5 of {len(skipped_details['tags_only'])}) ---")
            for i, (src, tgt) in enumerate(skipped_details["tags_only"][:5]):
                logger.info(f"  Tags #{i + 1}: '{src}' | '{tgt}'")

        if skipped_details["duplicates"]:
            logger.info(f"--- Duplicate segments (showing first 5 of {len(skipped_details['duplicates'])}) ---")
            for i, (src, tgt) in enumerate(skipped_details["duplicates"][:5]):
                logger.info(f"  Duplicate #{i + 1}: '{src}' | '{tgt}'")

        logger.info("=== End Conversion Summary ===")

    def convert_streaming(self, filepath: Path, options: ConversionOptions) -> Iterator[Tuple[str, str, str, str]]:

    def _parse_segment_xml(self, xml_segment: str) -> Tuple[str, str]:
        """Парсит XML сегмент SDLTM"""
        try:
            root = ET.fromstring(xml_segment)

            # Извлекаем текст
            text_elem = root.find(".//Text/Value")
            text = text_elem.text if text_elem is not None and text_elem.text else ""

            # Извлекаем язык
            lang_elem = root.find(".//CultureName")
            lang = lang_elem.text if lang_elem is not None and lang_elem.text else "unknown"

            # Нормализуем язык
            lang = self._normalize_language(lang)

            return text.strip(), lang

        except ET.ParseError:
            return "", "unknown"
        except Exception:
            return "", "unknown"

    def _is_tags_only(self, xml_segment: str) -> bool:
        """Проверяет, состоит ли сегмент только из тегов"""
        try:
            root = ET.fromstring(xml_segment)
            text_elem = root.find(".//Text/Value")

            if text_elem is None or not text_elem.text:
                return True

            # Если есть теги, но нет текста
            has_tags = root.find(".//Tag") is not None
            has_text = bool(text_elem.text.strip())

            return has_tags and not has_text

        except:
            return False

    def _normalize_language(self, lang_code: str) -> str:
        """Нормализует языковой код"""
        if not lang_code or lang_code == "unknown":
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

    def _write_tmx(self, filepath: Path, segments, src_lang: str, tgt_lang: str):
        """Записывает TMX файл"""
        import xml.etree.ElementTree as ET

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

        for src_text, tgt_text, seg_src_lang, seg_tgt_lang in segments:
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

        # Форматируем с отступами
        self._indent_xml(tmx)

        # Записываем
        tree = ET.ElementTree(tmx)
        tree.write(str(filepath), encoding="utf-8", xml_declaration=True)

    def _write_xlsx(self, filepath: Path, segments, src_lang: str, tgt_lang: str):
        """Записывает XLSX файл"""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Translation Memory"

        # Заголовки
        ws.append([f"Source ({src_lang})", f"Target ({tgt_lang})"])

        # Данные
        for src_text, tgt_text, seg_src_lang, seg_tgt_lang in segments:
            ws.append([src_text, tgt_text])

        wb.save(str(filepath))

    @staticmethod
    def _indent_xml(elem, level=0):
        """Добавляет отступы для читаемости"""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            for child in elem:
                SdltmConverter._indent_xml(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i