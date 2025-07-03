#!/usr/bin/env python3
# debug_main.py - Отладочная версия для поиска проблем

import sys
import logging
from pathlib import Path

# Подробное логирование
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def test_pyside6():
    """Тестирует PySide6"""
    try:
        logger.info("Testing PySide6 import...")
        from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
        from PySide6.QtCore import Qt
        logger.info("✓ PySide6 imported successfully")
        return True
    except ImportError as e:
        logger.error(f"✗ PySide6 import failed: {e}")
        return False


def test_simple_window():
    """Тестирует простое окно"""
    try:
        logger.info("Creating simple test window...")
        from PySide6.QtWidgets import QApplication, QMainWindow, QLabel

        app = QApplication(sys.argv)

        window = QMainWindow()
        window.setWindowTitle("Test Window")
        window.resize(400, 300)

        label = QLabel("Test Window - If you see this, PySide6 works!")
        window.setCentralWidget(label)

        window.show()
        logger.info("✓ Simple window created and shown")

        # Запускаем на 3 секунды для проверки
        from PySide6.QtCore import QTimer
        timer = QTimer()
        timer.timeout.connect(app.quit)
        timer.start(3000)  # 3 секунды

        result = app.exec()
        logger.info(f"✓ Simple window test completed, exit code: {result}")
        return True

    except Exception as e:
        logger.error(f"✗ Simple window test failed: {e}")
        return False


def test_imports():
    """Тестирует импорты модулей"""
    imports_to_test = [
        ("core.base", "ConversionOptions"),
        ("core.converters.sdltm", "SdltmConverter"),
        ("workers.conversion_worker", "ConversionWorker"),
        ("gui.widgets.drop_area", "SmartDropArea"),
        ("gui.windows.main_window", "MainWindow")
    ]

    failed_imports = []

    for module_name, class_name in imports_to_test:
        try:
            logger.info(f"Testing import: {module_name}.{class_name}")
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            logger.info(f"✓ {module_name}.{class_name} imported successfully")
        except Exception as e:
            logger.error(f"✗ {module_name}.{class_name} failed: {e}")
            failed_imports.append((module_name, class_name, str(e)))

    return failed_imports


def test_main_window():
    """Тестирует главное окно"""
    try:
        logger.info("Testing main window import...")
        from gui.windows.main_window import MainWindow
        logger.info("✓ MainWindow imported")

        logger.info("Creating QApplication...")
        from PySide6.QtWidgets import QApplication
        app = QApplication(sys.argv)
        logger.info("✓ QApplication created")

        logger.info("Creating MainWindow instance...")
        window = MainWindow()
        logger.info("✓ MainWindow instance created")

        logger.info("Showing window...")
        window.show()
        logger.info("✓ Window shown")

        # Быстрый тест - закрываем через 2 секунды
        from PySide6.QtCore import QTimer
        timer = QTimer()
        timer.timeout.connect(app.quit)
        timer.start(2000)

        result = app.exec()
        logger.info(f"✓ Main window test completed, exit code: {result}")
        return True

    except Exception as e:
        logger.exception(f"✗ Main window test failed: {e}")
        return False


def main():
    """Главная функция отладки"""
    logger.info("=== Debug Main Started ===")

    # Добавляем текущий путь
    app_dir = Path(__file__).parent
    sys.path.insert(0, str(app_dir))
    logger.info(f"Added to path: {app_dir}")

    # Тест 1: PySide6
    logger.info("\n--- Test 1: PySide6 ---")
    if not test_pyside6():
        logger.error("PySide6 test failed, stopping")
        return 1

    # Тест 2: Простое окно
    logger.info("\n--- Test 2: Simple Window ---")
    if not test_simple_window():
        logger.error("Simple window test failed, stopping")
        return 1

    # Тест 3: Импорты модулей
    logger.info("\n--- Test 3: Module Imports ---")
    failed_imports = test_imports()
    if failed_imports:
        logger.error(f"Failed imports: {len(failed_imports)}")
        for module, cls, error in failed_imports:
            logger.error(f"  {module}.{cls}: {error}")
        logger.error("Some imports failed, but continuing...")

    # Тест 4: Главное окно
    logger.info("\n--- Test 4: Main Window ---")
    if not test_main_window():
        logger.error("Main window test failed")
        return 1

    logger.info("\n=== All Tests Passed! ===")
    logger.info("Your setup should work. Try running: python main.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())