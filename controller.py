# controller.py

from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging
import re

logger = logging.getLogger(__name__)


class MainController:

    def __init__(self):
        from services.file_service import FileService
        from core.converters.sdltm import SdltmConverter

        self.file_service = FileService()
        self.converter = SdltmConverter()

        self.files: List[Path] = []
        self.auto_detected_languages: Optional[Dict[str, str]] = None
        self.auto_language_source: Optional[Path] = None
        self.file_languages: Dict[Path, Dict[str, str]] = {}

    def add_files(self, filepaths: List[str]) -> List[Dict]:
        files_info = []
        new_files = []

        for filepath_str in filepaths:
            filepath = Path(filepath_str)

            if not filepath.exists() or filepath in self.files:
                continue

            file_info = self.file_service.get_file_info(filepath)
            languages = None
            if filepath.suffix.lower() == '.sdltm':
                languages = self.file_service.auto_detect_languages(filepath)
                if languages:
                    self.file_languages[filepath] = languages

            if file_info['is_supported']:
                self.files.append(filepath)
                new_files.append(filepath)
                files_info.append({
                    'path': filepath,
                    'name': file_info['name'],
                    'size_mb': file_info['size_mb'],
                    'format': file_info['format'],
                    'format_icon': file_info['format_icon'],
                    'extra_info': file_info['extra_info'],
                    'languages': languages
                })

        if new_files:
            self._auto_detect_languages_from_files(new_files)

        logger.info(f"Added {len(files_info)} files")
        return files_info

    def remove_file(self, filepath: Path) -> bool:
        if filepath in self.files:
            self.files.remove(filepath)
            logger.info(f"Removed file: {filepath.name}")
            return True
        return False

    def clear_files(self):
        self.files.clear()
        self.auto_detected_languages = None
        self.auto_language_source = None
        self.file_languages.clear()
        logger.info("All files cleared")

    def get_file_count(self) -> int:
        return len(self.files)

    def detect_drop_files(self, filepaths: List[str]) -> tuple[str, List[str]]:
        return self.file_service.detect_files_format(filepaths)

    def get_auto_detected_languages(self) -> Optional[Dict[str, str]]:
        return self.auto_detected_languages

    def prepare_conversion_options(self, gui_options: Dict) -> 'ConversionOptions':
        from core.base import ConversionOptions

        src_lang = gui_options.get('source_lang', '').strip()
        tgt_lang = gui_options.get('target_lang', '').strip()

        if not src_lang and self.auto_detected_languages:
            src_lang = self.auto_detected_languages.get('source', 'auto')
        if not tgt_lang and self.auto_detected_languages:
            tgt_lang = self.auto_detected_languages.get('target', 'auto')

        return ConversionOptions(
            export_tmx=gui_options.get('export_tmx', True),
            export_xlsx=gui_options.get('export_xlsx', False),
            export_json=gui_options.get('export_json', False),
            source_lang=src_lang or 'auto',
            target_lang=tgt_lang or 'auto',
            batch_size=1000
        )

    def get_files_for_conversion(self) -> List[Path]:
        return self.files.copy()

    def get_file_languages(self, filepath: Path) -> Optional[Dict[str, str]]:
        return self.file_languages.get(filepath)

    def set_file_languages(self, filepath: Path, source: str, target: str):
        if filepath in self.files:
            self.file_languages[filepath] = {'source': source, 'target': target}

    def get_file_language_mapping(self) -> Dict[Path, Dict[str, str]]:
        return self.file_languages.copy()

    def validate_conversion_request(self, gui_options: Dict) -> tuple[bool, str]:
        if not self.files:
            return False, "Нет файлов для конвертации"

        formats_selected = (
                gui_options.get('export_tmx', False) or
                gui_options.get('export_xlsx', False) or
                gui_options.get('export_json', False)
        )

        if not formats_selected:
            return False, "Выберите хотя бы один формат экспорта"

        return True, "OK"

    def is_excel_file(self, filepath: Path) -> bool:
        return filepath.suffix.lower() in ['.xlsx', '.xls']

    def is_termbase_file(self, filepath: Path) -> bool:
        return filepath.suffix.lower() in ['.xml', '.mtf', '.tbx']

    def analyze_excel_file(self, filepath: Path):
        try:
            from core.converters.excel_converter import ExcelConverter

            converter = ExcelConverter()

            if not converter.validate(filepath):
                raise ValueError("Excel file validation failed")

            analysis = converter.analyze_excel_structure(filepath)

            logger.info(f"Excel analysis completed: {filepath.name}, {len(analysis.sheets)} sheets")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing Excel file {filepath}: {e}")
            raise

    def show_excel_config_dialog(self, filepath: Path, parent_widget):
        try:
            analysis = self.analyze_excel_file(filepath)

            from gui.dialogs.excel_config_dialog import ExcelConfigDialog
            from PySide6.QtWidgets import QDialog

            dialog = ExcelConfigDialog(analysis, parent_widget)

            if dialog.exec() == QDialog.Accepted:
                settings = dialog.get_settings()
                logger.info(f"Excel conversion settings accepted for {filepath.name}")
                return settings
            else:
                logger.info(f"Excel conversion cancelled for {filepath.name}")
                return None

        except Exception as e:
            logger.error(f"Error in Excel config dialog for {filepath}: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent_widget,
                "Ошибка анализа Excel",
                f"Не удалось проанализировать Excel файл:\n\n{e}\n\n"
                f"Убедитесь, что файл не поврежден и содержит данные."
            )
            return None

    def show_termbase_config_dialog(self, filepath: Path, parent_widget):
        try:
            from utils.term_base import extract_tb_info
            info = extract_tb_info(filepath)

            from gui.dialogs.termbase_config_dialog import TermbaseConfigDialog
            from PySide6.QtWidgets import QDialog

            dialog = TermbaseConfigDialog(filepath, info.get("languages", []), parent_widget)

            if dialog.exec() == QDialog.Accepted:
                return dialog.get_settings()
            return None
        except Exception as e:
            logger.error(f"Error in termbase config dialog for {filepath}: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent_widget,
                "Ошибка анализа Termbase",
                f"Не удалось прочитать файл:\n\n{e}"
            )
            return None

    def convert_excel_file(self, filepath: Path, settings, options):
        try:
            from core.converters.excel_converter import ExcelConverter

            converter = ExcelConverter()
            result = converter.convert_excel_to_tmx(filepath, settings, options)

            logger.info(f"Excel conversion result: success={result.success}, "
                        f"output_files={len(result.output_files)}")
            return result

        except Exception as e:
            logger.error(f"Error converting Excel file {filepath}: {e}")
            raise

    def convert_termbase_file(self, filepath: Path, options):
        try:
            from core.converters.termbase_converter import TermBaseConverter

            converter = TermBaseConverter()
            return converter.convert(filepath, options)

        except Exception as e:
            logger.error(f"Error converting termbase {filepath}: {e}")
            raise

    def prepare_excel_conversion_options(self, settings) -> 'ConversionOptions':
        from core.base import ConversionOptions

        return ConversionOptions(
            export_tmx=True,
            export_xlsx=False,
            export_json=False,
            source_lang=settings.source_language,
            target_lang=settings.target_language,
            batch_size=1000
        )

    def prepare_termbase_conversion_options(self, settings) -> 'ConversionOptions':
        from core.base import ConversionOptions

        return ConversionOptions(
            export_tmx=settings.export_tmx,
            export_xlsx=settings.export_xlsx,
            export_json=False,
            source_lang=settings.source_language,
            target_lang='',
            batch_size=1000,
        )

    def validate_excel_conversion_settings(self, settings) -> tuple[bool, str]:
        try:
            if not settings:
                return False, "Настройки конвертации не указаны"

            if not settings.source_language or not settings.target_language:
                return False, "Не указаны исходный или целевой языки"

            if settings.source_language == settings.target_language:
                return False, "Исходный и целевой языки не могут быть одинаковыми"

            if not settings.selected_sheets:
                return False, "Не выбраны листы для конвертации"

            if not settings.column_mappings:
                return False, "Не настроены колонки для конвертации"

            for sheet_name in settings.selected_sheets:
                if sheet_name not in settings.column_mappings:
                    return False, f"Не настроены колонки для листа '{sheet_name}'"

                from core.base import ColumnType
                text_columns = [
                    col for col in settings.column_mappings[sheet_name].values()
                    if col.final_type == ColumnType.TEXT
                ]

                if len(text_columns) < 2:
                    return False, f"Лист '{sheet_name}': недостаточно текстовых колонок (нужно минимум 2)"

            return True, "OK"

        except Exception as e:
            logger.error(f"Error validating Excel settings: {e}")
            return False, f"Ошибка валидации: {e}"

    def validate_termbase_conversion_settings(self, settings) -> tuple[bool, str]:
        try:
            if not settings:
                return False, "Настройки не указаны"

            if not settings.source_language:
                return False, "Не выбран исходный язык"

            if not settings.export_tmx and not settings.export_xlsx:
                return False, "Нужно выбрать хотя бы один формат экспорта"

            return True, "OK"
        except Exception as e:
            logger.error(f"Error validating termbase settings: {e}")
            return False, f"Ошибка валидации: {e}"

    def get_excel_file_info(self, filepath: Path) -> Dict:
        try:
            analysis = self.analyze_excel_file(filepath)

            total_segments = analysis.get_total_segments()
            sheets_info = f"{len(analysis.sheets)} листов"

            return {
                'path': filepath,
                'name': filepath.name,
                'size_mb': filepath.stat().st_size / (1024 * 1024),
                'format': 'Excel Workbook',
                'format_icon': '📊',
                'extra_info': f"{sheets_info}, ~{total_segments} сегментов",
                'is_supported': True,
                'is_excel': True,
                'analysis': analysis
            }

        except Exception as e:
            logger.error(f"Error getting Excel file info: {e}")
            return {
                'path': filepath,
                'name': filepath.name,
                'size_mb': filepath.stat().st_size / (1024 * 1024),
                'format': 'Excel Workbook (ошибка)',
                'format_icon': '⚠️',
                'extra_info': f"Ошибка анализа: {e}",
                'is_supported': False,
                'is_excel': True
            }

    def is_sdlxliff_file(self, filepath: Path) -> bool:
        return filepath.suffix.lower() == '.sdlxliff'

    def is_sdlxliff_part_file(self, filepath: Path) -> bool:
        pattern = r'\.\d+of\d+\.sdlxliff$'
        return bool(re.search(pattern, str(filepath), re.IGNORECASE))

    def find_sdlxliff_parts(self, filepath: Path) -> List[Path]:
        match = re.search(r'(.+)\.(\d+)of(\d+)\.sdlxliff$', str(filepath), re.IGNORECASE)
        if not match:
            return []

        base_name = match.group(1)
        total_parts = int(match.group(3))

        parts = []
        for i in range(1, total_parts + 1):
            part_path = Path(f"{base_name}.{i}of{total_parts}.sdlxliff")
            if part_path.exists():
                parts.append(part_path)

        logger.info(f"Found {len(parts)} parts of {total_parts} for {filepath.name}")
        return parts

    def analyze_sdlxliff_file(self, filepath: Path):
        try:
            from core.converters.sdlxliff_converter import SdlxliffConverter

            converter = SdlxliffConverter()
            analysis = converter.analyze_file(filepath)

            logger.info(f"SDLXLIFF analysis completed: {filepath.name}, valid={analysis.get('valid', False)}")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing SDLXLIFF file {filepath}: {e}")
            raise

    def show_sdlxliff_split_dialog(self, filepath: Path, parent_widget):
        from gui.dialogs.sdlxliff_dialogs import SdlxliffSplitDialog
        from PySide6.QtWidgets import QDialog

        dialog = SdlxliffSplitDialog(parent_widget)

        if dialog.exec() == QDialog.Accepted:
            return dialog.get_settings()

        return None

    def show_sdlxliff_merge_dialog(self, filepaths: List[Path], parent_widget):
        from gui.dialogs.sdlxliff_dialogs import SdlxliffMergeDialog
        from PySide6.QtWidgets import QDialog

        dialog = SdlxliffMergeDialog(parent_widget)

        if dialog.exec() == QDialog.Accepted:
            return dialog.get_settings(), dialog.get_ordered_files()

        return None, None

    def validate_sdlxliff_split_settings(self, settings) -> tuple[bool, str]:
        try:
            if not settings:
                return False, "Настройки не указаны"

            is_valid, error_msg = settings.validate()
            if not is_valid:
                return False, error_msg

            return True, "OK"

        except Exception as e:
            logger.error(f"Error validating SDLXLIFF split settings: {e}")
            return False, f"Ошибка валидации: {e}"

    def validate_sdlxliff_merge_settings(self, settings, filepaths: List[Path]) -> tuple[bool, str]:
        try:
            if not settings:
                return False, "Настройки не указаны"

            is_valid, error_msg = settings.validate()
            if not is_valid:
                return False, error_msg

            if len(filepaths) < 2:
                return False, "Для объединения нужно минимум 2 файла"

            for filepath in filepaths:
                if not filepath.exists():
                    return False, f"Файл не найден: {filepath.name}"

            return True, "OK"

        except Exception as e:
            logger.error(f"Error validating SDLXLIFF merge settings: {e}")
            return False, f"Ошибка валидации: {e}"

    def get_sdlxliff_file_info(self, filepath: Path) -> Dict:
        try:
            analysis = self.analyze_sdlxliff_file(filepath)

            is_part = self.is_sdlxliff_part_file(filepath)

            if is_part:
                match = re.search(r'\.(\d+)of(\d+)\.sdlxliff$', str(filepath), re.IGNORECASE)
                if match:
                    part = match.group(1)
                    total = match.group(2)
                    extra_info = f"Часть {part} из {total}"
                else:
                    extra_info = "Часть файла"
            else:
                segments = analysis.get('segments_count', 0) if analysis.get('valid', False) else 0
                extra_info = f"{segments:,} сегментов" if segments > 0 else "Требует анализа"

            return {
                'path': filepath,
                'name': filepath.name,
                'size_mb': filepath.stat().st_size / (1024 * 1024),
                'format': 'SDL XLIFF',
                'format_icon': '✂️',
                'extra_info': extra_info,
                'is_supported': True,
                'is_sdlxliff': True,
                'is_part': is_part,
                'analysis': analysis
            }

        except Exception as e:
            logger.error(f"Error getting SDLXLIFF file info: {e}")
            return {
                'path': filepath,
                'name': filepath.name,
                'size_mb': filepath.stat().st_size / (1024 * 1024),
                'format': 'SDL XLIFF (ошибка)',
                'format_icon': '⚠️',
                'extra_info': f"Ошибка анализа: {e}",
                'is_supported': False,
                'is_sdlxliff': True
            }

    def _auto_detect_languages_from_files(self, new_files: List[Path]):
        if self.auto_detected_languages:
            return

        for filepath in new_files:
            if filepath.suffix.lower() == '.sdltm':
                languages = self.file_service.auto_detect_languages(filepath)
                if languages:
                    self.auto_detected_languages = languages
                    self.auto_language_source = filepath
                    logger.info(f"Auto-detected languages from {filepath.name}: {languages}")
                    break
            elif self.is_excel_file(filepath):
                try:
                    analysis = self.analyze_excel_file(filepath)
                    if analysis.detected_source_lang and analysis.detected_target_lang:
                        self.auto_detected_languages = {
                            'source': analysis.detected_source_lang,
                            'target': analysis.detected_target_lang
                        }
                        self.auto_language_source = filepath
                        logger.info(f"Auto-detected languages from Excel: {self.auto_detected_languages}")
                        break
                except Exception:
                    continue