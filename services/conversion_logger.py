# services/conversion_logger.py

from pathlib import Path
from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConversionLogger:
    """Сервис для создания детальных логов конвертации"""

    @staticmethod
    def write_conversion_log(
            log_path: Path,
            source_file: Path,
            stats: Dict,
            detailed_stats: Dict,
            src_lang: str,
            tgt_lang: str,
            output_files: List[Path]
    ):
        """Создает красивый и читаемый лог конвертации"""
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                ConversionLogger._write_header(f, source_file, src_lang, tgt_lang)
                ConversionLogger._write_statistics(f, stats)
                ConversionLogger._write_output_files(f, output_files, log_path)
                ConversionLogger._write_skipped_examples(f, detailed_stats)
                ConversionLogger._write_recommendations(f, stats)
                ConversionLogger._write_footer(f)

            logger.info(f"Conversion log created: {log_path}")

        except Exception as e:
            logger.error(f"Error writing conversion log: {e}")

    @staticmethod
    def _write_header(f, source_file: Path, src_lang: str, tgt_lang: str):
        """Записывает заголовок лога"""
        f.write("=" * 80 + "\n")
        f.write("🔄 CONVERSION LOG - CONVERTER PRO v2.0\n")
        f.write("=" * 80 + "\n")
        f.write(f"📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"📁 Исходный файл: {source_file.name}\n")
        f.write(f"📂 Путь: {source_file.parent}\n")
        f.write(f"🗂️ Размер файла: {source_file.stat().st_size / (1024 * 1024):.1f} MB\n")
        f.write("\n")

        # Языки
        f.write("🌐 ЯЗЫКИ\n")
        f.write("-" * 40 + "\n")
        f.write(f"📥 Исходный язык: {src_lang}\n")
        f.write(f"📤 Целевой язык: {tgt_lang}\n")
        f.write("\n")

    @staticmethod
    def _write_statistics(f, stats: Dict):
        """Записывает общую статистику"""
        f.write("📊 ОБЩАЯ СТАТИСТИКА\n")
        f.write("-" * 40 + "\n")
        f.write(f"📋 Всего сегментов в SDLTM: {stats['total_in_sdltm']:,}\n")
        f.write(f"⚙️ Обработано сегментов: {stats['processed']:,}\n")
        f.write(f"✅ Экспортировано в TMX: {stats['exported']:,}\n")
        f.write(f"⏱️ Время конвертации: {stats['conversion_time']:.2f} секунд\n")
        f.write(f"🧠 Использовано памяти: {stats['memory_used_mb']:.1f} MB\n")
        f.write("\n")

        # Статистика пропусков
        f.write("⚠️ ПРОПУЩЕННЫЕ СЕГМЕНТЫ\n")
        f.write("-" * 40 + "\n")
        f.write(f"🔸 Пустые сегменты: {stats['skipped_empty']:,}\n")
        f.write(f"🔸 Только теги (без текста): {stats['skipped_tags_only']:,}\n")
        f.write(f"🔸 Дубликаты: {stats['skipped_duplicates']:,}\n")
        f.write(f"🔸 Ошибки парсинга: {stats['skipped_errors']:,}\n")

        total_skipped = (stats['skipped_empty'] + stats['skipped_tags_only'] +
                         stats['skipped_duplicates'] + stats['skipped_errors'])
        f.write(f"📊 Итого пропущено: {total_skipped:,}\n")
        f.write(f"📈 Эффективность: {(stats['exported'] / stats['total_in_sdltm'] * 100):.1f}%\n")
        f.write("\n")

    @staticmethod
    def _write_output_files(f, output_files: List[Path], log_path: Path):
        """Записывает список созданных файлов"""
        f.write("📤 СОЗДАННЫЕ ФАЙЛЫ\n")
        f.write("-" * 40 + "\n")
        for output_file in output_files:
            file_size = output_file.stat().st_size / (1024 * 1024) if output_file.exists() else 0
            f.write(f"📄 {output_file.name} ({file_size:.1f} MB)\n")
        f.write(f"📄 {log_path.name} (этот лог)\n")
        f.write("\n")

    @staticmethod
    def _write_skipped_examples(f, detailed_stats: Dict):
        """Записывает примеры пропущенных сегментов"""
        skipped_details = detailed_stats.get("skipped_details", {})

        if skipped_details.get("empty"):
            f.write("🔍 ПРИМЕРЫ ПУСТЫХ СЕГМЕНТОВ\n")
            f.write("-" * 40 + "\n")
            for i, (src, tgt) in enumerate(skipped_details["empty"][:5], 1):
                f.write(f"  {i}. Source: '{src}'\n")
                f.write(f"     Target: '{tgt}'\n")
                f.write("\n")

        if skipped_details.get("tags_only"):
            f.write("🏷️ ПРИМЕРЫ СЕГМЕНТОВ ТОЛЬКО С ТЕГАМИ\n")
            f.write("-" * 40 + "\n")
            for i, (src, tgt) in enumerate(skipped_details["tags_only"][:5], 1):
                f.write(f"  {i}. Source: '{src}'\n")
                f.write(f"     Target: '{tgt}'\n")
                f.write("\n")

        if skipped_details.get("duplicates"):
            f.write("🔄 ПРИМЕРЫ ДУБЛИКАТОВ\n")
            f.write("-" * 40 + "\n")
            for i, (src, tgt) in enumerate(skipped_details["duplicates"][:5], 1):
                f.write(f"  {i}. Source: '{src}'\n")
                f.write(f"     Target: '{tgt}'\n")
                f.write("\n")

        if skipped_details.get("errors"):
            f.write("❌ ПРИМЕРЫ ОШИБОК ПАРСИНГА\n")
            f.write("-" * 40 + "\n")
            for i, (src, tgt) in enumerate(skipped_details["errors"][:5], 1):
                f.write(f"  {i}. Source: '{src}'\n")
                f.write(f"     Target: '{tgt}'\n")
                f.write("\n")

    @staticmethod
    def _write_recommendations(f, stats: Dict):
        """Записывает рекомендации"""
        f.write("💡 РЕКОМЕНДАЦИИ\n")
        f.write("-" * 40 + "\n")

        if stats['skipped_empty'] > 0:
            f.write(f"• Найдено {stats['skipped_empty']:,} пустых сегментов. Это нормально для SDLTM файлов.\n")

        if stats['skipped_duplicates'] > stats['exported'] * 0.1:
            f.write(f"• Много дубликатов ({stats['skipped_duplicates']:,}). Рассмотрите очистку исходной TM.\n")

        if stats['skipped_tags_only'] > 0:
            f.write(f"• Найдено {stats['skipped_tags_only']:,} сегментов только с тегами. Это технические сегменты.\n")

        efficiency = (stats['exported'] / stats['total_in_sdltm'] * 100)
        if efficiency > 80:
            f.write("• ✅ Отличная эффективность конвертации!\n")
        elif efficiency > 60:
            f.write("• ⚠️ Умеренная эффективность. Возможно, много служебных сегментов.\n")
        else:
            f.write("• ❌ Низкая эффективность. Проверьте качество исходного файла.\n")

        f.write("\n")

    @staticmethod
    def _write_footer(f):
        """Записывает подвал лога"""
        f.write("=" * 80 + "\n")
        f.write("🔧 Создано Converter Pro v2.0 - Professional TM/TB/TMX Converter\n")
        f.write("=" * 80 + "\n")

    @staticmethod
    def log_conversion_summary(filepath: Path, stats: Dict, src_lang: str, tgt_lang: str):
        """Логирует краткую статистику в обычный лог"""
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
        logger.info("=" * 60)