# core/converters/excel_converter.py - ИСПРАВЛЕННАЯ ВЕРСИЯ ДЛЯ БОЛЬШИХ ФАЙЛОВ

import openpyxl
from pathlib import Path
from typing import Iterator, Tuple, Dict, List, Optional, Set
import logging
import time
import re

from ..base import (
    StreamingConverter, ConversionResult, ConversionOptions, ConversionStatus,
    ExcelAnalysis, SheetInfo, ColumnInfo, ColumnType, ExcelConversionSettings,
    TranslationSegment, ExcelStructureError, ValidationError, ConversionError
)
from ..formats.tmx_format import TmxWriter

logger = logging.getLogger(__name__)


class ExcelConverter(StreamingConverter):
    """Конвертер Excel в TMX с оптимизацией для больших файлов"""

    def __init__(self):
        super().__init__()
        self.supported_formats = {'.xlsx', '.xls'}

    def can_handle(self, filepath: Path) -> bool:
        """Проверяет, может ли конвертер обработать файл"""
        return filepath.suffix.lower() in self.supported_formats

    def validate(self, filepath: Path) -> bool:
        """БЫСТРАЯ валидация Excel файла"""
        if not filepath.exists():
            raise ValidationError(f"File not found: {filepath}")

        if not filepath.is_file():
            raise ValidationError(f"Not a file: {filepath}")

        # Проверяем размер файла
        file_size_mb = filepath.stat().st_size / (1024 * 1024)
        logger.info(f"Excel file size: {file_size_mb:.1f} MB")

        try:
            # БЫСТРАЯ проверка - только открываем и сразу закрываем
            wb = openpyxl.load_workbook(str(filepath), read_only=True, data_only=True)

            if not wb.sheetnames:
                wb.close()
                raise ValidationError(f"No sheets found in Excel file: {filepath}")

            sheet_count = len(wb.sheetnames)
            wb.close()  # СРАЗУ закрываем!

            logger.info(f"Excel validation successful: {filepath} ({sheet_count} sheets)")
            return True

        except openpyxl.utils.exceptions.InvalidFileException:
            raise ValidationError(f"Invalid Excel file format: {filepath}")
        except Exception as e:
            raise ValidationError(f"Error validating Excel file {filepath}: {e}")

    def analyze_excel_structure(self, filepath: Path) -> ExcelAnalysis:
        """ОПТИМИЗИРОВАННЫЙ анализ структуры Excel файла"""
        logger.info(f"Analyzing Excel structure: {filepath.name}")

        try:
            analysis = ExcelAnalysis(file_path=filepath)

            # ОПТИМИЗАЦИЯ: Открываем с минимальными настройками
            wb = openpyxl.load_workbook(
                str(filepath),
                read_only=True,  # Только для чтения
                data_only=True,  # Только значения, без формул
                keep_vba=False  # Не загружаем VBA
            )

            logger.info(f"Excel opened, analyzing {len(wb.sheetnames)} sheets...")

            # Анализируем только первые несколько листов для больших файлов
            sheets_to_analyze = wb.sheetnames[:10]  # Максимум 10 листов

            for i, sheet_name in enumerate(sheets_to_analyze):
                logger.info(f"Analyzing sheet {i + 1}/{len(sheets_to_analyze)}: {sheet_name}")

                try:
                    sheet = wb[sheet_name]
                    sheet_info = self._analyze_sheet_fast(sheet, sheet_name)
                    analysis.sheets.append(sheet_info)
                except Exception as e:
                    logger.warning(f"Error analyzing sheet '{sheet_name}': {e}")
                    # Создаем базовую информацию о листе
                    sheet_info = SheetInfo(
                        name=sheet_name,
                        data_rows=0,
                        columns=[]
                    )
                    analysis.sheets.append(sheet_info)

            wb.close()  # ОБЯЗАТЕЛЬНО закрываем

            logger.info(f"Excel analysis completed: {len(analysis.sheets)} sheets analyzed")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing Excel structure: {e}")
            raise ExcelStructureError(f"Failed to analyze Excel file: {e}", filepath)

    def _analyze_sheet_fast(self, sheet, sheet_name: str) -> SheetInfo:
        """БЫСТРЫЙ анализ листа - только первые строки"""
        logger.debug(f"Fast analyzing sheet: {sheet_name}")

        info = SheetInfo(name=sheet_name)
        info.header_row = 1

        # ОПТИМИЗАЦИЯ: Читаем только первые 10 колонок и 100 строк
        max_cols_to_check = min(10, sheet.max_column)
        max_rows_to_check = min(100, sheet.max_row)

        # Читаем заголовки из первой строки
        headers = []
        for col_idx in range(1, max_cols_to_check + 1):
            try:
                cell = sheet.cell(row=1, column=col_idx)
                header = str(cell.value).strip() if cell.value else f"Column_{col_idx}"

                if header and header != "None":
                    col_info = ColumnInfo(
                        index=col_idx - 1,
                        name=header,
                        detected_language=None,
                        column_type=ColumnType.TEXT
                    )
                    headers.append(col_info)
            except Exception as e:
                logger.debug(f"Error reading header at col {col_idx}: {e}")
                break

        info.columns = headers

        # БЫСТРЫЙ подсчет строк - проверяем только каждую 10-ю строку
        data_rows = 0
        for row_idx in range(2, max_rows_to_check + 1, 5):  # Каждые 5 строк
            try:
                has_data = False
                for col_idx in range(1, min(5, sheet.max_column + 1)):  # Только первые 5 колонок
                    cell = sheet.cell(row=row_idx, column=col_idx)
                    if cell.value and str(cell.value).strip():
                        has_data = True
                        break
                if has_data:
                    data_rows += 5  # Приблизительно
            except Exception:
                break

        # Приблизительная оценка общего количества строк
        if data_rows > 0:
            estimated_total = int((sheet.max_row - 1) * (data_rows / max_rows_to_check))
            info.data_rows = min(estimated_total, sheet.max_row - 1)
        else:
            info.data_rows = 0

        logger.debug(f"Sheet '{sheet_name}': {len(info.columns)} columns, ~{info.data_rows} data rows (estimated)")
        return info

    def convert_excel_to_tmx(self, filepath: Path, settings: ExcelConversionSettings,
                             options: ConversionOptions) -> ConversionResult:
        """ОПТИМИЗИРОВАННАЯ конвертация Excel в TMX"""
        start_time = time.time()

        try:
            self._update_progress(0, "Открываем Excel файл...", options)

            # ОПТИМИЗАЦИЯ: Открываем с минимальными настройками
            wb = openpyxl.load_workbook(
                str(filepath),
                read_only=True,
                data_only=True,
                keep_vba=False
            )

            all_segments = []
            processed_sheets = 0
            total_sheets = len(settings.selected_sheets)

            for sheet_name in settings.selected_sheets:
                if self._should_stop(options):
                    wb.close()
                    return self._create_cancelled_result()

                processed_sheets += 1
                base_progress = int((processed_sheets - 1) / total_sheets * 80)

                self._update_progress(base_progress, f"Обрабатываем лист '{sheet_name}'...", options)

                if sheet_name not in wb.sheetnames:
                    logger.warning(f"Sheet '{sheet_name}' not found in workbook")
                    continue

                try:
                    sheet = wb[sheet_name]
                    column_mapping = settings.get_sheet_column_mapping(sheet_name)

                    # ПОТОКОВАЯ обработка листа
                    sheet_segments = self._extract_segments_streaming(
                        sheet, sheet_name, column_mapping, settings, options
                    )
                    all_segments.extend(sheet_segments)

                except Exception as e:
                    logger.error(f"Error processing sheet '{sheet_name}': {e}")
                    continue

            wb.close()

            self._update_progress(80, "Фильтруем и сохраняем...", options)
            filtered_segments = self._filter_segments(all_segments, settings)

            if not filtered_segments:
                return ConversionResult(
                    success=False,
                    output_files=[],
                    stats={"total_segments": len(all_segments), "exported_segments": 0},
                    errors=["No valid segments found"],
                    status=ConversionStatus.FAILED
                )

            # Создаем TMX
            output_path = filepath.with_suffix('.tmx')
            tmx_segments = [
                (seg.source_text, seg.target_text, seg.source_lang, seg.target_lang)
                for seg in filtered_segments
            ]

            # ПОТОКОВАЯ запись TMX для больших файлов
            if len(tmx_segments) > 10000:
                logger.info("Using streaming TMX write for large file")
                TmxWriter.write_streaming(output_path, iter(tmx_segments),
                                          settings.source_language, settings.target_language)
            else:
                TmxWriter.write(output_path, tmx_segments,
                                settings.source_language, settings.target_language)

            stats = {
                "total_segments": len(all_segments),
                "exported_segments": len(filtered_segments),
                "processed_sheets": len(settings.selected_sheets),
                "conversion_time": time.time() - start_time,
                "source_language": settings.source_language,
                "target_language": settings.target_language
            }

            self._update_progress(100, f"Готово! {len(filtered_segments)} сегментов", options)

            return ConversionResult(
                success=True,
                output_files=[output_path],
                stats=stats,
                status=ConversionStatus.COMPLETED
            )

        except Exception as e:
            logger.exception(f"Error converting Excel: {e}")
            return ConversionResult(
                success=False,
                output_files=[],
                stats={"error": str(e)},
                errors=[str(e)],
                status=ConversionStatus.FAILED
            )

    def _extract_segments_streaming(self, sheet, sheet_name: str, column_mapping: Dict[int, ColumnInfo],
                                    settings: ExcelConversionSettings, options: ConversionOptions) -> List[
        TranslationSegment]:
        """ПОТОКОВОЕ извлечение сегментов порциями"""
        segments = []

        # Находим колонки
        source_col = None
        target_col = None
        comment_cols = []

        for col in column_mapping.values():
            if col.final_type == ColumnType.TEXT:
                if col.final_language == settings.source_language:
                    source_col = col
                elif col.final_language == settings.target_language:
                    target_col = col
            elif col.final_type == ColumnType.COMMENT:
                comment_cols.append(col)

        if not source_col or not target_col:
            text_cols = [col for col in column_mapping.values() if col.final_type == ColumnType.TEXT]
            if len(text_cols) >= 2:
                source_col = text_cols[0]
                target_col = text_cols[1]

        if not source_col or not target_col:
            logger.error(f"Sheet '{sheet_name}': source or target column not configured")
            return segments

        # ПОТОКОВАЯ обработка батчами по 1000 строк
        batch_size = 1000
        current_row = 2

        while current_row <= sheet.max_row:
            if self._should_stop(options):
                break

            end_row = min(current_row + batch_size - 1, sheet.max_row)

            logger.debug(f"Processing rows {current_row}-{end_row}")

            # Обрабатываем батч с помощью iter_rows (значительно быстрее в read_only)
            row_iter = sheet.iter_rows(
                min_row=current_row,
                max_row=end_row,
                values_only=True
            )

            row_idx = current_row
            for row_values in row_iter:
                try:
                    src_val = row_values[source_col.index] if source_col.index < len(row_values) else None
                    tgt_val = row_values[target_col.index] if target_col.index < len(row_values) else None

                    source_text = str(src_val).strip() if src_val else ''
                    target_text = str(tgt_val).strip() if tgt_val else ''

                    if not source_text and not target_text:
                        row_idx += 1
                        continue

                    segment = TranslationSegment(
                        source_text=source_text,
                        target_text=target_text,
                        source_lang=settings.source_language,
                        target_lang=settings.target_language
                    )

                    # Добавляем комментарии
                    for comment_col in comment_cols:
                        if comment_col.index < len(row_values):
                            comment_val = row_values[comment_col.index]
                            comment_text = str(comment_val).strip() if comment_val else ''
                            if comment_text:
                                segment.add_comment(comment_text)

                    segments.append(segment)

                except Exception as e:
                    logger.debug(f"Error processing row {row_idx}: {e}")

                row_idx += 1

            current_row = end_row + 1

            # Обновляем прогресс
            progress = int((current_row / sheet.max_row) * 100)
            if hasattr(options, 'progress_callback') and options.progress_callback:
                try:
                    options.progress_callback(progress, f"Обработано {current_row}/{sheet.max_row} строк")
                except Exception:
                    pass

        logger.info(f"Sheet '{sheet_name}': extracted {len(segments)} segments")
        return segments

    def _filter_segments(self, segments: List[TranslationSegment],
                         settings: ExcelConversionSettings) -> List[TranslationSegment]:
        """Фильтрует сегменты"""
        filtered = []
        seen_pairs = set()

        for segment in segments:
            if settings.skip_empty_segments and not segment.has_content():
                continue

            # Удаляем дубликаты
            pair_key = (segment.source_text.lower().strip(), segment.target_text.lower().strip())
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            filtered.append(segment)

        logger.info(f"Filtered segments: {len(segments)} -> {len(filtered)}")
        return filtered

    def _create_cancelled_result(self) -> ConversionResult:
        """Создает результат для отмененной конвертации"""
        return ConversionResult(
            success=False,
            output_files=[],
            stats={"cancelled": True},
            errors=["Conversion cancelled by user"],
            status=ConversionStatus.CANCELLED
        )

    # Остальные методы остаются без изменений...
    def convert(self, filepath: Path, options: ConversionOptions) -> ConversionResult:
        """Основной метод конвертации"""
        try:
            analysis = self.analyze_excel_structure(filepath)

            if not analysis.sheets:
                raise ConversionError("No sheets found in Excel file")

            settings = ExcelConversionSettings(
                source_language="ru-RU",
                target_language="en-US",
                selected_sheets=[sheet.name for sheet in analysis.sheets if sheet.is_selected]
            )

            for sheet in analysis.sheets:
                if sheet.is_selected:
                    column_mapping = {}
                    for col in sheet.columns:
                        column_mapping[col.index] = col
                    settings.column_mappings[sheet.name] = column_mapping

            return self.convert_excel_to_tmx(filepath, settings, options)

        except Exception as e:
            logger.exception(f"Error in Excel conversion: {e}")
            return ConversionResult(
                success=False,
                output_files=[],
                stats={"error": str(e)},
                errors=[str(e)],
                status=ConversionStatus.FAILED
            )

    def convert_streaming(self, filepath: Path, options: ConversionOptions) -> Iterator[Tuple[str, str, str, str]]:
        """Потоковая конвертация"""
        return iter([])  # Заглушка

    def get_progress_steps(self, filepath: Path) -> int:
        """Возвращает примерное количество шагов"""
        return 1000