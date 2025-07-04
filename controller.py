# controller.py - ОБНОВЛЕННАЯ ВЕРСИЯ

from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MainController:
    """Простой контроллер, который связывает GUI и бизнес-логику"""

    def __init__(self):
        from services.file_service import FileService
        from core.converters.sdltm import SdltmConverter

        self.file_service = FileService()
        self.converter = SdltmConverter()

        # Состояние приложения
        self.files: List[Path] = []
        self.auto_detected_languages: Optional[Dict[str, str]] = None

    def add_files(self, filepaths: List[str]) -> List[Dict]:
        """
        Добавляет файлы и возвращает информацию для GUI
        """
        files_info = []
        new_files = []

        for filepath_str in filepaths:
            filepath = Path(filepath_str)

            # Проверяем, что файл существует и не добавлен уже
            if not filepath.exists() or filepath in self.files:
                continue

            # Получаем информацию о файле
            file_info = self.file_service.get_file_info(filepath)

            # Добавляем только поддерживаемые файлы
            if file_info['is_supported']:
                self.files.append(filepath)
                new_files.append(filepath)
                files_info.append({
                    'path': filepath,
                    'name': file_info['name'],
                    'size_mb': file_info['size_mb'],
                    'format': file_info['format'],
                    'format_icon': file_info['format_icon'],
                    'extra_info': file_info['extra_info']
                })

        # Автоопределение языков из первого SDLTM файла
        if new_files:
            self._auto_detect_languages_from_files(new_files)

        logger.info(f"Added {len(files_info)} files")
        return files_info

    def remove_file(self, filepath: Path) -> bool:
        """Удаляет файл из списка"""
        if filepath in self.files:
            self.files.remove(filepath)
            logger.info(f"Removed file: {filepath.name}")
            return True
        return False

    def clear_files(self):
        """Очищает все файлы"""
        self.files.clear()
        self.auto_detected_languages = None
        logger.info("All files cleared")

    def get_file_count(self) -> int:
        """Возвращает количество файлов"""
        return len(self.files)

    def detect_drop_files(self, filepaths: List[str]) -> tuple[str, List[str]]:
        """Определяет формат перетаскиваемых файлов"""
        return self.file_service.detect_files_format(filepaths)

    def get_auto_detected_languages(self) -> Optional[Dict[str, str]]:
        """Возвращает автоопределенные языки"""
        return self.auto_detected_languages

    def prepare_conversion_options(self, gui_options: Dict) -> 'ConversionOptions':
        """
        Создает опции конвертации из данных GUI
        """
        from core.base import ConversionOptions

        # Используем языки из GUI или автоопределенные
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
        """Возвращает список файлов для конвертации"""
        return self.files.copy()

    def validate_conversion_request(self, gui_options: Dict) -> tuple[bool, str]:
        """
        Валидирует запрос на конвертацию
        """
        if not self.files:
            return False, "Нет файлов для конвертации"

        # Проверяем, что выбран хотя бы один формат экспорта
        formats_selected = (
                gui_options.get('export_tmx', False) or
                gui_options.get('export_xlsx', False) or
                gui_options.get('export_json', False)
        )

        if not formats_selected:
            return False, "Выберите хотя бы один формат экспорта"

        return True, "OK"

    # ===========================================
    # НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С EXCEL
    # ===========================================

    def is_excel_file(self, filepath: Path) -> bool:
        """Проверяет, является ли файл Excel"""
        return filepath.suffix.lower() in ['.xlsx', '.xls']

    def analyze_excel_file(self, filepath: Path):
        """Анализирует Excel файл для настройки конвертации"""
        try:
            from core.converters.excel_converter import ExcelConverter

            converter = ExcelConverter()

            # Сначала валидируем файл
            if not converter.validate(filepath):
                raise ValueError("Excel file validation failed")

            # Анализируем структуру
            analysis = converter.analyze_excel_structure(filepath)

            logger.info(f"Excel analysis completed: {filepath.name}, {len(analysis.sheets)} sheets")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing Excel file {filepath}: {e}")
            raise

    def show_excel_config_dialog(self, filepath: Path, parent_widget):
        """Показывает диалог настройки Excel конвертации"""
        try:
            # Анализируем Excel файл
            analysis = self.analyze_excel_file(filepath)

            # Показываем диалог настройки
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
            # Показываем ошибку пользователю
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent_widget,
                "Ошибка анализа Excel",
                f"Не удалось проанализировать Excel файл:\n\n{e}\n\n"
                f"Убедитесь, что файл не поврежден и содержит данные."
            )
            return None

    def convert_excel_file(self, filepath: Path, settings, options):
        """Конвертирует Excel файл с заданными настройками"""
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

    def prepare_excel_conversion_options(self, settings) -> 'ConversionOptions':
        """Создает опции конвертации для Excel"""
        from core.base import ConversionOptions

        return ConversionOptions(
            export_tmx=True,  # Excel всегда конвертируется в TMX
            export_xlsx=False,
            export_json=False,
            source_lang=settings.source_language,
            target_lang=settings.target_language,
            batch_size=1000
        )

    def validate_excel_conversion_settings(self, settings) -> tuple[bool, str]:
        """Валидирует настройки Excel конвертации"""
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

            # Проверяем, что для каждого выбранного листа есть маппинг
            for sheet_name in settings.selected_sheets:
                if sheet_name not in settings.column_mappings:
                    return False, f"Не настроены колонки для листа '{sheet_name}'"

                # Проверяем наличие текстовых колонок
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

    def get_excel_file_info(self, filepath: Path) -> Dict:
        """Получает информацию об Excel файле для GUI"""
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

    # ===========================================
    # ОБНОВЛЕННЫЕ МЕТОДЫ
    # ===========================================

    def _auto_detect_languages_from_files(self, new_files: List[Path]):
        """Автоопределение языков из новых файлов"""
        if self.auto_detected_languages:
            return  # Уже определены

        # Ищем первый SDLTM файл
        for filepath in new_files:
            if filepath.suffix.lower() == '.sdltm':
                languages = self.file_service.auto_detect_languages(filepath)
                if languages:
                    self.auto_detected_languages = languages
                    logger.info(f"Auto-detected languages: {languages}")
                    break
            elif self.is_excel_file(filepath):
                # Для Excel файлов тоже можем попробовать определить языки
                try:
                    analysis = self.analyze_excel_file(filepath)
                    if analysis.detected_source_lang and analysis.detected_target_lang:
                        self.auto_detected_languages = {
                            'source': analysis.detected_source_lang,
                            'target': analysis.detected_target_lang
                        }
                        logger.info(f"Auto-detected languages from Excel: {self.auto_detected_languages}")
                        break
                except Exception:
                    continue  # Игнорируем ошибки автоопределения для Excel