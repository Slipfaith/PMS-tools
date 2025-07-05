#!/usr/bin/env python3
# main.py - Автономная версия

import sys
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('converter.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def setup_app_paths():
    """Настройка путей приложения"""
    app_dir = Path(__file__).parent
    sys.path.insert(0, str(app_dir))


def check_dependencies():
    """Проверяет наличие необходимых зависимостей"""
    missing_deps = []

    try:
        import PySide6
    except ImportError:
        missing_deps.append("PySide6")

    try:
        import openpyxl
    except ImportError:
        missing_deps.append("openpyxl")

    if missing_deps:
        print("Missing dependencies:")
        for dep in missing_deps:
            print(f"   - {dep}")
        print("\nInstall dependencies:")
        print("pip install PySide6 openpyxl")
        return False

    return True


def create_application():
    """Создает и настраивает приложение"""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

    app = QApplication(sys.argv)
    app.setApplicationName("Converter Pro")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("ConverterPro")

    # Настраиваем стиль
    app.setStyle("Fusion")

    # Устанавливаем шрифт
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    return app


def main():
    """Главная функция приложения"""
    logger.info("Starting Converter Pro v2.0")

    try:
        # Настройка путей
        setup_app_paths()

        # Проверка зависимостей
        if not check_dependencies():
            sys.exit(1)

        # Создаем приложение
        app = create_application()

        # Пытаемся импортировать и создать главное окно
        try:
            from gui.windows.main_window import MainWindow
            logger.info("Creating main window...")
            main_window = MainWindow()
            main_window.show()
            main_window.raise_()  # Принудительно поднимаем окно наверх
            main_window.activateWindow()  # Активируем окно

            # Принудительно обрабатываем события
            app.processEvents()

            logger.info("Main window created and shown")
        except ImportError as ie:
            logger.error(f"Failed to import main window: {ie}")
            return 1

        logger.info("Application started successfully")

        # Запускаем цикл событий
        exit_code = app.exec()

        logger.info(f"Application finished with exit code: {exit_code}")
        return exit_code

    except Exception as e:
        error_msg = f"Critical error during startup: {e}"
        logger.exception(error_msg)
        print(f"CRITICAL: {error_msg}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
