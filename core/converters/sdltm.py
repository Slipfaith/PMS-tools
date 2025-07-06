# core/converters/sdltm.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator, Tuple, Dict, Set, Optional, List
import logging
import time

from ..base import (
    FileConverter, ConversionResult, ConversionOptions, StreamingConverter,
    ConversionError, ValidationError, ConversionStatus
)
from ..formats.tmx_format import TmxWriter
from ..formats.xlsx_format import XlsxWriter

logger = logging.getLogger(__name__)


class SdltmConverter(StreamingConverter):
    """
    Конвертер для SDLTM файлов с потоковой обработкой.
    """

    def __init__(self):
        super().__init__()
        self.supported_exports = {'tmx', 'xlsx', 'json'}
        self.language_cache = {}

    def can_handle(self, filepath: Path) -> bool:
        """Проверяет, может ли конвертер обработать файл"""
        return filepath.suffix.lower() == '.sdltm'

    def validate(self, filepath: Path) -> bool:
        """Валидирует SDLTM файл"""
        if not filepath.exists():
            raise ValidationError(f"File not found: {filepath}")

        if not filepath.is_file():
            raise ValidationError(f"Not a file: {filepath}")

        try:
            with sqlite3.connect(str(filepath)) as conn:
                cursor = conn.cursor()

                # Проверяем таблицы
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = {row[0] for row in cursor.fetchall()}

                if 'translation_units' not in tables:
                    raise ValidationError(f"Missing translation_units table in {filepath}")

                # Проверяем структуру
                cursor.execute("PRAGMA table_info(translation_units)")
                columns = {row[1] for row in cursor.fetchall()}

                required_columns = {'source_segment', 'target_segment'}
                missing_columns = required_columns - columns

                if missing_columns:
                    raise ValidationError(f"Missing columns {missing_columns} in {filepath}")

                # Проверяем данные
                cursor.execute("SELECT COUNT(*) FROM translation_units")
                count = cursor.fetchone()[0]

                if count == 0:
                    logger.warning(f"Empty SDLTM file: {filepath}")
                    return True

                # Проверяем XML
                cursor.execute("SELECT source_segment, target_segment FROM translation_units LIMIT 10")
                valid_segments = 0

                for src_xml, tgt_xml in cursor.fetchall():
                    try:
                        self._parse_segment_xml(src_xml)
                        self._parse_segment_xml(tgt_xml)
                        valid_segments += 1
                    except Exception:
                        continue

                if valid_segments == 0:
                    raise ValidationError(f"No valid segments found in {filepath}")

                logger.info(f"SDLTM validation successful: {filepath} ({count} segments)")
                return True

        except sqlite3.Error as e:
            raise ValidationError(f"Database error in {filepath}: {e}")
        except Exception as e:
            raise ValidationError(f"Unexpected error validating {filepath}: {e}")

    def get_progress_steps(self, filepath: Path) -> int:
        """Получает количество сегментов"""
        try:
            with sqlite3.connect(str(filepath)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM translation_units")
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error(f"Error getting progress steps for {filepath}: {e}")
            return 0

    def convert(self, filepath: Path, options: ConversionOptions) -> ConversionResult:
        """Основной метод конвертации"""
        start_time = time.time()

        # Детальная статистика для отчетов
        detailed_stats = {
            "skipped_details": {
                "empty": [],
                "tags_only": [],
                "duplicates": [],
                "errors": []
            }
        }

        try:
            # Валидация
            self._update_progress(0, "Validating file...", options)
            if not self.validate(filepath):
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": "Validation failed"},
                    errors=["File validation failed"],
                    status=ConversionStatus.FAILED
                )

            # Количество сегментов
            total_segments = self.get_progress_steps(filepath)
            if total_segments == 0:
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"total": 0},
                    errors=["No segments found"],
                    status=ConversionStatus.FAILED
                )

            self._update_progress(5, f"Found {total_segments:,} segments", options)

            # Статистика
            stats = {
                "total_in_sdltm": total_segments,
                "processed": 0,
                "exported": 0,
                "skipped_empty": 0,
                "skipped_tags_only": 0,
                "skipped_duplicates": 0,
                "skipped_errors": 0,
                "languages_detected": {},
                "conversion_time": 0,
                "memory_used_mb": 0
            }

            # Языки
            self._update_progress(10, "Detecting languages...", options)
            detected_languages = self._detect_languages(filepath)
            stats["languages_detected"] = detected_languages

            src_lang = self._resolve_language(options.source_lang, detected_languages.get('source', 'en-US'))
            tgt_lang = self._resolve_language(options.target_lang, detected_languages.get('target', 'ru-RU'))

            # Если пользователь явно указал язык, игнорируем языки сегментов
            override_src = options.source_lang and options.source_lang.lower() not in ["auto", "unknown", ""]
            override_tgt = options.target_lang and options.target_lang.lower() not in ["auto", "unknown", ""]

            logger.info(f"Using languages: {src_lang} → {tgt_lang}")

            # Обработка сегментов
            self._update_progress(15, "Processing segments...", options)

            segments = []
            seen_pairs = set()

            for segment_data in self.convert_streaming_detailed(filepath, options):
                if self._should_stop(options):
                    logger.info("Conversion stopped by user")
                    return ConversionResult(
                        success=False,
                        output_files=[],
                        stats=stats,
                        errors=["Conversion cancelled by user"],
                        status=ConversionStatus.CANCELLED
                    )

                src_text, tgt_text, seg_src_lang, seg_tgt_lang, skip_reason = segment_data
                stats["processed"] += 1

                # Собираем примеры для отчета
                if skip_reason:
                    example = (src_text[:100] + "..." if len(src_text) > 100 else src_text,
                               tgt_text[:100] + "..." if len(tgt_text) > 100 else tgt_text)

                    if skip_reason == "empty":
                        stats["skipped_empty"] += 1
                        # ИЗМЕНЕНО: Собираем ВСЕ пустые сегменты
                        detailed_stats["skipped_details"]["empty"].append(example)
                    elif skip_reason == "tags_only":
                        stats["skipped_tags_only"] += 1
                        # ИЗМЕНЕНО: Собираем ВСЕ сегменты только с тегами
                        detailed_stats["skipped_details"]["tags_only"].append(example)
                    elif skip_reason == "error":
                        stats["skipped_errors"] += 1
                        # ИЗМЕНЕНО: Собираем ВСЕ ошибки парсинга
                        detailed_stats["skipped_details"]["errors"].append(example)
                    continue

                # Дубликаты
                pair_key = (src_text.strip(), tgt_text.strip())
                if pair_key in seen_pairs:
                    stats["skipped_duplicates"] += 1
                    # ИЗМЕНЕНО: Собираем ВСЕ дубликаты
                    example = (src_text[:100] + "..." if len(src_text) > 100 else src_text,
                               tgt_text[:100] + "..." if len(tgt_text) > 100 else tgt_text)
                    detailed_stats["skipped_details"]["duplicates"].append(example)
                    continue

                seen_pairs.add(pair_key)

                if override_src:
                    final_src_lang = src_lang
                else:
                    final_src_lang = seg_src_lang if seg_src_lang != "unknown" else src_lang

                if override_tgt:
                    final_tgt_lang = tgt_lang
                else:
                    final_tgt_lang = seg_tgt_lang if seg_tgt_lang != "unknown" else tgt_lang

                segments.append((src_text, tgt_text, final_src_lang, final_tgt_lang))
                stats["exported"] += 1

            if not segments:
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats=stats,
                    errors=["No valid segments found after processing"],
                    status=ConversionStatus.FAILED
                )

            # Экспорт файлов
            self._update_progress(80, "Writing output files...", options)
            output_files = []

            try:
                if options.export_tmx:
                    tmx_path = filepath.with_suffix('.tmx')
                    TmxWriter.write(tmx_path, segments, src_lang, tgt_lang)
                    output_files.append(tmx_path)
                    logger.info(f"TMX created: {tmx_path}")

                if options.export_xlsx:
                    xlsx_path = filepath.with_suffix('.xlsx')
                    XlsxWriter.write(xlsx_path, segments, src_lang, tgt_lang)
                    output_files.append(xlsx_path)
                    logger.info(f"XLSX created: {xlsx_path}")

                if getattr(options, 'export_json', False):
                    json_path = filepath.with_suffix('.json')
                    self._write_json(json_path, segments, src_lang, tgt_lang)
                    output_files.append(json_path)
                    logger.info(f"JSON created: {json_path}")

                # Создаем отчет
                report_path = filepath.with_suffix('.conversion-report.txt')
                self._create_conversion_report(report_path, filepath, stats, detailed_stats, src_lang, tgt_lang,
                                               output_files)

            except Exception as e:
                logger.error(f"Error writing output files: {e}")
                return ConversionResult(
                    success=False,
                    output_files=output_files,
                    stats=stats,
                    errors=[f"Export error: {e}"],
                    status=ConversionStatus.FAILED
                )

            # Финальная статистика
            stats["conversion_time"] = time.time() - start_time
            stats["memory_used_mb"] = self._get_memory_usage()

            self._update_progress(100, f"Completed! Exported {stats['exported']:,} segments", options)

            # Подробная статистика в лог
            self._log_conversion_summary(filepath, stats, src_lang, tgt_lang)

            return ConversionResult(
                success=True,
                output_files=output_files,
                stats=stats,
                status=ConversionStatus.COMPLETED
            )

        except Exception as e:
            logger.exception(f"Critical error converting {filepath}")
            return ConversionResult(
                success=False,
                output_files=[],
                stats={"error": str(e), "conversion_time": time.time() - start_time},
                errors=[str(e)],
                status=ConversionStatus.FAILED
            )

    def convert_streaming(self, filepath: Path, options: ConversionOptions) -> Iterator[Tuple[str, str, str, str]]:
        """Потоковая обработка"""
        detected_languages = self._detect_languages(filepath)
        src_lang = self._resolve_language(options.source_lang, detected_languages.get('source', 'en-US'))
        tgt_lang = self._resolve_language(options.target_lang, detected_languages.get('target', 'ru-RU'))

        override_src = options.source_lang and options.source_lang.lower() not in ["auto", "unknown", ""]
        override_tgt = options.target_lang and options.target_lang.lower() not in ["auto", "unknown", ""]

        for segment_data in self.convert_streaming_detailed(filepath, options):
            src_text, tgt_text, seg_src_lang, seg_tgt_lang, skip_reason = segment_data
            if skip_reason is None:
                if override_src:
                    final_src = src_lang
                else:
                    final_src = seg_src_lang if seg_src_lang != "unknown" else src_lang

                if override_tgt:
                    final_tgt = tgt_lang
                else:
                    final_tgt = seg_tgt_lang if seg_tgt_lang != "unknown" else tgt_lang

                yield (src_text, tgt_text, final_src, final_tgt)

    def convert_streaming_detailed(self, filepath: Path, options: ConversionOptions):
        """Потоковая обработка с деталями"""
        conn = None
        cursor = None

        try:
            conn = sqlite3.connect(str(filepath))
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA read_uncommitted=1")

            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM translation_units")
            total = cursor.fetchone()[0]

            logger.info(f"Starting streaming conversion of {total:,} segments")

            processed = 0
            batch_size = getattr(options, 'batch_size', 1000)
            offset = 0

            while True:
                if self._should_stop(options):
                    logger.info("SDLTM streaming conversion stopped by user")
                    break

                try:
                    cursor.execute(
                        "SELECT source_segment, target_segment FROM translation_units LIMIT ? OFFSET ?",
                        (batch_size, offset)
                    )
                    batch = cursor.fetchall()

                    if not batch:
                        logger.info(f"Finished reading all segments at offset {offset}")
                        break

                except sqlite3.Error as e:
                    logger.error(f"Database error at offset {offset}: {e}")
                    try:
                        if cursor:
                            cursor.close()
                        if conn:
                            conn.close()
                        conn = sqlite3.connect(str(filepath))
                        cursor = conn.cursor()
                        continue
                    except Exception:
                        break

                batch_processed = 0
                for src_xml, tgt_xml in batch:
                    processed += 1
                    batch_processed += 1

                    try:
                        src_text, src_lang = self._parse_segment_xml(src_xml)
                        tgt_text, tgt_lang = self._parse_segment_xml(tgt_xml)

                        if not src_text.strip() or not tgt_text.strip():
                            yield (src_text, tgt_text, src_lang, tgt_lang, "empty")
                            continue

                        if self._is_tags_only(src_xml) or self._is_tags_only(tgt_xml):
                            yield (src_text, tgt_text, src_lang, tgt_lang, "tags_only")
                            continue

                        yield (src_text, tgt_text, src_lang, tgt_lang, None)

                    except Exception as e:
                        logger.debug(f"Error parsing segment {processed}: {e}")
                        yield ("", "", "unknown", "unknown", "error")
                        continue

                if total > 0:
                    progress = 15 + int((processed / total) * 60)
                    self._update_progress(progress, f"Processed {processed:,}/{total:,} segments", options)

                logger.debug(f"Processed batch: {batch_processed} segments, total: {processed}/{total}")
                offset += batch_size

            logger.info(f"Streaming conversion completed: {processed} segments processed")

        except Exception as e:
            logger.error(f"Critical error in streaming conversion: {e}")
            raise ConversionError(f"Streaming conversion failed: {e}", filepath)

        finally:
            try:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
                self._cleanup_sqlite_temp_files(filepath)
            except Exception as e:
                logger.debug(f"Error closing database connection: {e}")

    def _cleanup_sqlite_temp_files(self, filepath: Path):
        """Очистка SQLite временных файлов"""
        try:
            time.sleep(0.1)
            cleaned_files = []
            for suffix in ['-wal', '-shm', '-journal']:
                temp_file = Path(str(filepath) + suffix)
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                        cleaned_files.append(temp_file.name)
                    except Exception:
                        pass
            if cleaned_files:
                logger.info(f"Cleaned up SQLite temporary files: {', '.join(cleaned_files)}")
        except Exception:
            pass

    def _parse_segment_xml(self, xml_segment: str) -> Tuple[str, str]:
        """Парсит XML сегмент"""
        if not xml_segment or not xml_segment.strip():
            return "", "unknown"

        try:
            if xml_segment in self.language_cache:
                return self.language_cache[xml_segment]

            root = ET.fromstring(xml_segment)
            text = ""

            text_elem = root.find(".//Text/Value")
            if text_elem is not None and text_elem.text:
                text = text_elem.text
            else:
                for xpath in [".//Value", ".//Text", ".//Content"]:
                    elem = root.find(xpath)
                    if elem is not None and elem.text:
                        text = elem.text
                        break

            lang = "unknown"
            for xpath in [".//CultureName", ".//Culture", ".//Language", ".//Lang"]:
                lang_elem = root.find(xpath)
                if lang_elem is not None and lang_elem.text:
                    lang = self._normalize_language(lang_elem.text)
                    break

            result = (text.strip(), lang)

            if len(self.language_cache) < 1000:
                self.language_cache[xml_segment] = result

            return result

        except ET.ParseError:
            return "", "unknown"
        except Exception:
            return "", "unknown"

    def _is_tags_only(self, xml_segment: str) -> bool:
        """Проверяет сегменты только с тегами"""
        if not xml_segment or not xml_segment.strip():
            return True

        try:
            root = ET.fromstring(xml_segment)
            text_elem = root.find(".//Text/Value")
            if text_elem is None:
                return True

            text_content = text_elem.text or ""
            text_content = text_content.strip()

            if not text_content:
                return True

            tags = root.findall(".//Tag")
            if tags and len(text_content) < 3:
                return True

            if text_content and not any(c.isalnum() for c in text_content):
                return True

            return False

        except ET.ParseError:
            return True
        except Exception:
            return True

    def _detect_languages(self, filepath: Path) -> Dict[str, str]:
        """Определяет языки из файла"""
        detected = {"source": "unknown", "target": "unknown"}

        try:
            with sqlite3.connect(str(filepath)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT source_segment, target_segment FROM translation_units LIMIT 50")

                src_langs = {}
                tgt_langs = {}

                for src_xml, tgt_xml in cursor.fetchall():
                    try:
                        _, src_lang = self._parse_segment_xml(src_xml)
                        _, tgt_lang = self._parse_segment_xml(tgt_xml)

                        if src_lang != "unknown":
                            src_langs[src_lang] = src_langs.get(src_lang, 0) + 1

                        if tgt_lang != "unknown":
                            tgt_langs[tgt_lang] = tgt_langs.get(tgt_lang, 0) + 1

                    except Exception:
                        continue

                if src_langs:
                    detected["source"] = max(src_langs, key=src_langs.get)
                    logger.info(f"Auto-detected source language: {detected['source']}")

                if tgt_langs:
                    detected["target"] = max(tgt_langs, key=tgt_langs.get)
                    logger.info(f"Auto-detected target language: {detected['target']}")

        except Exception as e:
            logger.warning(f"Error detecting languages: {e}")

        return detected

    def _resolve_language(self, option_lang: str, detected_lang: str) -> str:
        """Определяет финальный язык"""
        if option_lang and option_lang.lower() not in ["auto", "unknown", ""]:
            return self._normalize_language(option_lang)
        return detected_lang

    def _normalize_language(self, lang_code: str) -> str:
        """Нормализует языковой код"""
        if not lang_code or lang_code.lower() in ["unknown", ""]:
            return "unknown"

        lang_map = {
            "en": "en-US", "english": "en-US",
            "de": "de-DE", "german": "de-DE", "deutsch": "de-DE",
            "fr": "fr-FR", "french": "fr-FR", "français": "fr-FR",
            "it": "it-IT", "italian": "it-IT", "italiano": "it-IT",
            "es": "es-ES", "spanish": "es-ES", "español": "es-ES",
            "pt": "pt-PT", "portuguese": "pt-PT", "português": "pt-PT",
            "ru": "ru-RU", "russian": "ru-RU", "русский": "ru-RU",
            "ja": "ja-JP", "japanese": "ja-JP", "日本語": "ja-JP",
            "ko": "ko-KR", "korean": "ko-KR", "한국어": "ko-KR",
            "zh": "zh-CN", "chinese": "zh-CN", "中文": "zh-CN",
            "pl": "pl-PL", "polish": "pl-PL", "polski": "pl-PL",
            "tr": "tr-TR", "turkish": "tr-TR", "türkçe": "tr-TR",
            "nl": "nl-NL", "dutch": "nl-NL", "nederlands": "nl-NL",
            "sv": "sv-SE", "swedish": "sv-SE", "svenska": "sv-SE",
            "da": "da-DK", "danish": "da-DK", "dansk": "da-DK",
            "no": "no-NO", "norwegian": "no-NO", "norsk": "no-NO",
            "fi": "fi-FI", "finnish": "fi-FI", "suomi": "fi-FI"
        }

        code = lang_code.lower().strip().replace("_", "-")

        if "-" in code and len(code) == 5:
            return code

        if code in lang_map:
            return lang_map[code]

        if len(code) == 2 and code.isalpha():
            return lang_map.get(code, f"{code}-XX")

        return lang_code

    def _write_json(self, filepath: Path, segments, src_lang: str, tgt_lang: str):
        """Записывает JSON файл"""
        import json
        from datetime import datetime

        data = {
            "metadata": {
                "source_language": src_lang,
                "target_language": tgt_lang,
                "created_at": datetime.now().isoformat(),
                "total_segments": len(segments),
                "created_by": "Converter Pro v2.0"
            },
            "segments": []
        }

        for i, (src_text, tgt_text, seg_src_lang, seg_tgt_lang) in enumerate(segments):
            data["segments"].append({
                "id": i + 1,
                "source": {
                    "text": src_text,
                    "language": seg_src_lang
                },
                "target": {
                    "text": tgt_text,
                    "language": seg_tgt_lang
                }
            })

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _create_conversion_report(self, report_path: Path, source_file: Path, stats: Dict,
                                  detailed_stats: Dict, src_lang: str, tgt_lang: str, output_files: List[Path]):
        """Создает отчет через внешний сервис"""
        try:
            from services.conversion_report_generator import ConversionReportGenerator
            ConversionReportGenerator.create_detailed_report(
                report_path, source_file, stats, detailed_stats,
                src_lang, tgt_lang, output_files
            )
        except Exception as e:
            logger.error(f"Error creating conversion report: {e}")

    def _log_conversion_summary(self, filepath: Path, stats: Dict, src_lang: str, tgt_lang: str):
        """Краткая статистика через сервис логирования"""
        try:
            from services.conversion_logger import ConversionLogger
            ConversionLogger.log_conversion_summary(filepath, stats, src_lang, tgt_lang)
        except Exception as e:
            logger.error(f"Error logging conversion summary: {e}")

    def _get_memory_usage(self) -> float:
        """Получает использование памяти"""
        try:
            from services.conversion_report_generator import ConversionReportGenerator
            return ConversionReportGenerator.get_memory_usage()
        except Exception:
            try:
                import psutil
                process = psutil.Process()
                return process.memory_info().rss / 1024 / 1024
            except ImportError:
                return 0.0
            except Exception:
                return 0.0

    # Дополнительные методы

    def get_supported_formats(self) -> Set[str]:
        return self.supported_exports.copy()

    def estimate_conversion_time(self, filepath: Path) -> float:
        try:
            file_size_mb = filepath.stat().st_size / (1024 * 1024)
            return file_size_mb * 5
        except Exception:
            return 0.0

    def get_file_info(self, filepath: Path) -> Dict[str, any]:
        info = {
            "file_size_mb": 0,
            "total_segments": 0,
            "source_language": "unknown",
            "target_language": "unknown",
            "creation_date": None,
            "database_version": "unknown"
        }

        try:
            info["file_size_mb"] = filepath.stat().st_size / (1024 * 1024)

            with sqlite3.connect(str(filepath)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM translation_units")
                info["total_segments"] = cursor.fetchone()[0]

                detected_langs = self._detect_languages(filepath)
                info["source_language"] = detected_langs.get("source", "unknown")
                info["target_language"] = detected_langs.get("target", "unknown")

                cursor.execute("SELECT sqlite_version()")
                info["database_version"] = cursor.fetchone()[0]

        except Exception as e:
            logger.warning(f"Could not get file info for {filepath}: {e}")

        return info