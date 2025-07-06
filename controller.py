# controller.py - НОВЫЙ ФАЙЛ

from pathlib import Path
from typing import List, Dict
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
        logger.info("All files cleared")

    def get_file_count(self) -> int:
        """Возвращает количество файлов"""
        return len(self.files)

    def detect_drop_files(self, filepaths: List[str]) -> tuple[str, List[str]]:
        """Определяет формат перетаскиваемых файлов"""
        return self.file_service.detect_files_format(filepaths)

    def prepare_conversion_options(self, gui_options: Dict) -> 'ConversionOptions':
        """
        Создает опции конвертации из данных GUI
        """
        from core.base import ConversionOptions

        src_lang = gui_options.get('source_lang', '').strip() or 'auto'
        tgt_lang = gui_options.get('target_lang', '').strip() or 'auto'

        return ConversionOptions(
            export_tmx=gui_options.get('export_tmx', True),
            export_xlsx=gui_options.get('export_xlsx', False),
            export_json=gui_options.get('export_json', False),
            source_lang=src_lang,
            target_lang=tgt_lang,
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
