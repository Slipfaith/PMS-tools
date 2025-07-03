# core/converters/sdltm.py

import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator, Tuple, Dict, Set, Optional
import logging
import time
from datetime import datetime

from ..base import (
    FileConverter, ConversionResult, ConversionOptions, StreamingConverter,
    ConversionError, ValidationError, ConversionStatus
)
from ..formats.tmx_format import TmxWriter
from ..formats.xlsx_format import XlsxWriter

logger = logging.getLogger(__name__)


class SdltmConverter(StreamingConverter):
    """
    Полный конвертер для SDLTM файлов с потоковой обработкой.

    Поддерживает:
    - Потоковую обработку больших файлов
    - Автоопределение языков
    - Экспорт в TMX, XLSX, JSON
    - Дедупликацию сегментов
    - Детальную статистику
    - Обработку ошибок и восстановление
    """

    def __init__(self):
        super().__init__()
        self.supported_exports = {'tmx', 'xlsx', 'json'}
        self.language_cache = {}  # Кэш для определения языков

    def can_handle(self, filepath: Path) -> bool:
        """Проверяет, может ли конвертер обработать файл"""
        return filepath.suffix.lower() == '.sdltm'

    def validate(self, filepath: Path) -> bool:
        """
        Валидирует SDLTM файл на корректность структуры

        Args:
            filepath: Путь к SDLTM файлу

        Returns:
            True если файл валиден

        Raises:
            ValidationError: При ошибках валидации
        """
        if not filepath.exists():
            raise ValidationError(f"File not found: {filepath}")

        if not filepath.is_file():
            raise ValidationError(f"Not a file: {filepath}")

        try:
            with sqlite3.connect(str(filepath)) as conn:
                cursor = conn.cursor()

                # Проверяем, что это SQLite файл
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = {row[0] for row in cursor.fetchall()}

                # Проверяем наличие обязательной таблицы
                if 'translation_units' not in tables:
                    raise ValidationError(f"Missing translation_units table in {filepath}")

                # Проверяем структуру таблицы
                cursor.execute("PRAGMA table_info(translation_units)")
                columns = {row[1] for row in cursor.fetchall()}

                required_columns = {'source_segment', 'target_segment'}
                missing_columns = required_columns - columns

                if missing_columns:
                    raise ValidationError(f"Missing columns {missing_columns} in {filepath}")

                # Проверяем, что есть данные
                cursor.execute("SELECT COUNT(*) FROM translation_units")
                count = cursor.fetchone()[0]

                if count == 0:
                    logger.warning(f"Empty SDLTM file: {filepath}")
                    return True  # Пустой файл технически валиден

                # Проверяем первые несколько записей на корректность XML
                cursor.execute("SELECT source_segment, target_segment FROM translation_units LIMIT 10")

                valid_segments = 0
                for src_xml, tgt_xml in cursor.fetchall():
                    try:
                        self._parse_segment_xml(src_xml)
                        self._parse_segment_xml(tgt_xml)
                        valid_segments += 1
                    except Exception as e:
                        logger.debug(f"Invalid segment XML: {e}")
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
        """
        Получает общее количество сегментов для расчета прогресса

        Args:
            filepath: Путь к SDLTM файлу

        Returns:
            Количество сегментов в файле
        """
        try:
            with sqlite3.connect(str(filepath)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM translation_units")
                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            logger.error(f"Error getting progress steps for {filepath}: {e}")
            return 0

    def convert(self, filepath: Path, options: ConversionOptions) -> ConversionResult:
        """
        Конвертирует SDLTM файл в указанные форматы

        Args:
            filepath: Путь к SDLTM файлу
            options: Опции конвертации

        Returns:
            Результат конвертации
        """
        start_time = time.time()

        try:
            # Валидация файла
            self._update_progress(0, "Validating file...", options)
            if not self.validate(filepath):
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"error": "Validation failed"},
                    errors=["File validation failed"],
                    status=ConversionStatus.FAILED
                )

            # Получаем общее количество сегментов
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

            # Инициализируем статистику
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

            # Определяем языки
            self._update_progress(10, "Detecting languages...", options)
            detected_languages = self._detect_languages(filepath)
            stats["languages_detected"] = detected_languages

            src_lang = self._resolve_language(options.source_lang, detected_languages.get('source', 'en-US'))
            tgt_lang = self._resolve_language(options.target_lang, detected_languages.get('target', 'ru-RU'))

            logger.info(f"Using languages: {src_lang} → {tgt_lang}")

            # Потоковая обработка сегментов
            self._update_progress(15, "Processing segments...", options)

            segments = []
            seen_pairs = set()

            # Обрабатываем сегменты потоково
            for segment_data in self.convert_streaming(filepath, options):
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

                # Обрабатываем пропуски
                if skip_reason:
                    if skip_reason == "empty":
                        stats["skipped_empty"] += 1
                    elif skip_reason == "tags_only":
                        stats["skipped_tags_only"] += 1
                    elif skip_reason == "error":
                        stats["skipped_errors"] += 1
                    continue

                # Проверяем на дубликаты
                pair_key = (src_text.strip(), tgt_text.strip())
                if pair_key in seen_pairs:
                    stats["skipped_duplicates"] += 1
                    continue

                seen_pairs.add(pair_key)

                # Используем детектированные языки или переопределенные
                final_src_lang = seg_src_lang if seg_src_lang != "unknown" else src_lang
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

            # Экспорт в различные форматы
            self._update_progress(80, "Writing output files...", options)
            output_files = []

            try:
                # TMX экспорт
                if options.export_tmx:
                    tmx_path = filepath.with_suffix('.tmx')
                    TmxWriter.write(tmx_path, segments, src_lang, tgt_lang)
                    output_files.append(tmx_path)
                    logger.info(f"TMX created: {tmx_path}")

                # XLSX экспорт
                if options.export_xlsx:
                    xlsx_path = filepath.with_suffix('.xlsx')
                    XlsxWriter.write(xlsx_path, segments, src_lang, tgt_lang)
                    output_files.append(xlsx_path)
                    logger.info(f"XLSX created: {xlsx_path}")

                # JSON экспорт
                if getattr(options, 'export_json', False):
                    json_path = filepath.with_suffix('.json')
                    self._write_json(json_path, segments, src_lang, tgt_lang)
                    output_files.append(json_path)
                    logger.info(f"JSON created: {json_path}")

            except Exception as e:
                logger.error(f"Error writing output files: {e}")
                return ConversionResult(
                    success=False,
                    output_files=output_files,  # Частично созданные файлы
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

    def convert_streaming(self, filepath: Path, options: ConversionOptions) -> Iterator[
        Tuple[str, str, str, str, Optional[str]]]:
        """
        Потоковая обработка SDLTM файла с батчами

        Args:
            filepath: Путь к SDLTM файлу
            options: Опции конвертации

        Yields:
            Tuple[src_text, tgt_text, src_lang, tgt_lang, skip_reason]
            skip_reason: None если сегмент валиден, иначе причина пропуска
        """
        try:
            with sqlite3.connect(str(filepath)) as conn:
                # Настраиваем соединение для лучшей производительности
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=10000")
                conn.execute("PRAGMA temp_store=MEMORY")

                cursor = conn.cursor()

                # Получаем общее количество для прогресса
                cursor.execute("SELECT COUNT(*) FROM translation_units")
                total = cursor.fetchone()[0]

                processed = 0
                batch_size = getattr(options, 'batch_size', 1000)
                offset = 0

                while True:
                    # Проверяем на остановку
                    if self._should_stop(options):
                        logger.info("SDLTM streaming conversion stopped by user")
                        break

                    # Читаем батч с обработкой ошибок
                    try:
                        cursor.execute(
                            "SELECT source_segment, target_segment FROM translation_units LIMIT ? OFFSET ?",
                            (batch_size, offset)
                        )
                        batch = cursor.fetchall()

                        if not batch:
                            break

                    except sqlite3.Error as e:
                        logger.error(f"Database error at offset {offset}: {e}")
                        break

                    # Обрабатываем батч
                    for src_xml, tgt_xml in batch:
                        processed += 1

                        try:
                            # Парсим сегменты
                            src_text, src_lang = self._parse_segment_xml(src_xml)
                            tgt_text, tgt_lang = self._parse_segment_xml(tgt_xml)

                            # Проверяем на пустые сегменты
                            if not src_text.strip() or not tgt_text.strip():
                                yield (src_text, tgt_text, src_lang, tgt_lang, "empty")
                                continue

                            # Проверяем сегменты только с тегами
                            if self._is_tags_only(src_xml) or self._is_tags_only(tgt_xml):
                                yield (src_text, tgt_text, src_lang, tgt_lang, "tags_only")
                                continue

                            # Валидный сегмент
                            yield (src_text, tgt_text, src_lang, tgt_lang, None)

                        except Exception as e:
                            logger.debug(f"Error parsing segment {processed}: {e}")
                            yield ("", "", "unknown", "unknown", "error")
                            continue

                    # Обновляем прогресс
                    if total > 0:
                        progress = 15 + int((processed / total) * 60)  # 15-75% диапазон
                        self._update_progress(progress, f"Processed {processed:,}/{total:,} segments", options)

                    offset += batch_size

        except Exception as e:
            logger.error(f"Critical error in streaming conversion: {e}")
            raise ConversionError(f"Streaming conversion failed: {e}", filepath)

    def _parse_segment_xml(self, xml_segment: str) -> Tuple[str, str]:
        """
        Парсит XML сегмент SDLTM с улучшенной обработкой ошибок

        Args:
            xml_segment: XML строка сегмента

        Returns:
            Tuple[text, language_code]
        """
        if not xml_segment or not xml_segment.strip():
            return "", "unknown"

        try:
            # Кэшируем результаты парсинга для повышения производительности
            if xml_segment in self.language_cache:
                return self.language_cache[xml_segment]

            root = ET.fromstring(xml_segment)

            # Извлекаем текст различными способами
            text = ""

            # Основной способ - Text/Value
            text_elem = root.find(".//Text/Value")
            if text_elem is not None and text_elem.text:
                text = text_elem.text
            else:
                # Альтернативные способы
                for xpath in [".//Value", ".//Text", ".//Content"]:
                    elem = root.find(xpath)
                    if elem is not None and elem.text:
                        text = elem.text
                        break

            # Извлекаем язык
            lang = "unknown"
            for xpath in [".//CultureName", ".//Culture", ".//Language", ".//Lang"]:
                lang_elem = root.find(xpath)
                if lang_elem is not None and lang_elem.text:
                    lang = self._normalize_language(lang_elem.text)
                    break

            result = (text.strip(), lang)

            # Кэшируем результат
            if len(self.language_cache) < 1000:  # Ограничиваем размер кэша
                self.language_cache[xml_segment] = result

            return result

        except ET.ParseError as e:
            logger.debug(f"XML parsing error: {e}")
            return "", "unknown"
        except Exception as e:
            logger.debug(f"Unexpected error parsing XML: {e}")
            return "", "unknown"

    def _is_tags_only(self, xml_segment: str) -> bool:
        """
        Проверяет, состоит ли сегмент только из тегов без текста

        Args:
            xml_segment: XML строка сегмента

        Returns:
            True если сегмент содержит только теги
        """
        if not xml_segment or not xml_segment.strip():
            return True

        try:
            root = ET.fromstring(xml_segment)

            # Проверяем наличие текста
            text_elem = root.find(".//Text/Value")
            if text_elem is None:
                return True

            text_content = text_elem.text or ""
            text_content = text_content.strip()

            if not text_content:
                return True

            # Проверяем наличие тегов
            tags = root.findall(".//Tag")

            # Если есть теги, но нет значимого текста
            if tags and len(text_content) < 3:
                return True

            # Проверяем, что текст не состоит только из пробелов и символов
            if text_content and not any(c.isalnum() for c in text_content):
                return True

            return False

        except ET.ParseError:
            return True
        except Exception:
            return True

    def _detect_languages(self, filepath: Path) -> Dict[str, str]:
        """
        Автоматически определяет языки из SDLTM файла

        Args:
            filepath: Путь к SDLTM файлу

        Returns:
            Dict с ключами 'source' и 'target'
        """
        detected = {"source": "unknown", "target": "unknown"}

        try:
            with sqlite3.connect(str(filepath)) as conn:
                cursor = conn.cursor()

                # Анализируем первые 50 сегментов для определения языков
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

                # Выбираем наиболее частые языки
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
        """
        Определяет финальный язык из опций или автоопределения

        Args:
            option_lang: Язык из опций
            detected_lang: Автоопределенный язык

        Returns:
            Финальный код языка
        """
        if option_lang and option_lang.lower() not in ["auto", "unknown", ""]:
            return self._normalize_language(option_lang)
        return detected_lang

    def _normalize_language(self, lang_code: str) -> str:
        """
        Нормализует языковой код к стандартному формату

        Args:
            lang_code: Исходный код языка

        Returns:
            Нормализованный код языка
        """
        if not lang_code or lang_code.lower() in ["unknown", ""]:
            return "unknown"

        # Стандартные замены
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

        # Если уже полный код (например, en-US)
        if "-" in code and len(code) == 5:
            return code

        # Ищем в карте замен
        if code in lang_map:
            return lang_map[code]

        # Если это двухбуквенный код, добавляем регион по умолчанию
        if len(code) == 2 and code.isalpha():
            return lang_map.get(code, f"{code}-XX")

        # Если ничего не подошло, возвращаем как есть
        return lang_code

    def _write_json(self, filepath: Path, segments, src_lang: str, tgt_lang: str):
        """
        Записывает JSON файл с сегментами

        Args:
            filepath: Путь к JSON файлу
            segments: Список сегментов
            src_lang: Исходный язык
            tgt_lang: Целевой язык
        """
        import json

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

    def _get_memory_usage(self) -> float:
        """
        Получает текущее использование памяти в МБ

        Returns:
            Использование памяти в МБ
        """
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
        except Exception:
            return 0.0

    def _log_conversion_summary(self, filepath: Path, stats: Dict, src_lang: str, tgt_lang: str):
        """
        Логирует подробную статистику конвертации

        Args:
            filepath: Путь к файлу
            stats: Статистика конвертации
            src_lang: Исходный язык
            tgt_lang: Целевой язык
        """
        logger.info("=" * 60)
        logger.info(f"CONVERSION SUMMARY: {filepath.name}")
        logger.info("=" * 60)
        logger.info(f"Languages: {src_lang} → {tgt_lang}")
        logger.info(f"Total segments in SDLTM: {stats['total_in_sdltm']:,}")
        logger.info(f"Segments processed: {stats['processed']:,}")
        logger.info(f"Segments exported: {stats['exported']:,}")
        logger.info(f"Conversion time: {stats['conversion_time']:.2f} seconds")
        logger.info(f"Memory used: {stats['memory_used_mb']:.1f} MB")
        logger.info("")
        logger.info("SKIPPED SEGMENTS:")
        logger.info(f"  Empty segments: {stats['skipped_empty']:,}")
        logger.info(f"  Tag-only segments: {stats['skipped_tags_only']:,}")
        logger.info(f"  Duplicate segments: {stats['skipped_duplicates']:,}")
        logger.info(f"  Error segments: {stats['skipped_errors']:,}")
        logger.info("")
        logger.info("DETECTED LANGUAGES:")
        for lang_type, lang_code in stats['languages_detected'].items():
            logger.info(f"  {lang_type.capitalize()}: {lang_code}")
        logger.info("=" * 60)

    def get_supported_formats(self) -> Set[str]:
        """
        Возвращает поддерживаемые форматы экспорта

        Returns:
            Множество поддерживаемых форматов
        """
        return self.supported_exports.copy()

    def estimate_conversion_time(self, filepath: Path) -> float:
        """
        Оценивает время конвертации на основе размера файла

        Args:
            filepath: Путь к файлу

        Returns:
            Примерное время в секундах
        """
        try:
            file_size_mb = filepath.stat().st_size / (1024 * 1024)
            # Примерная оценка: 1 МБ = 5 секунд
            return file_size_mb * 5
        except Exception:
            return 0.0