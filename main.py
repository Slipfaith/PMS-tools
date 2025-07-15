#!/usr/bin/env python3
# main.py - Converter Pro v2.0 с поддержкой SDLXLIFF

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

    # Добавляем путь к модулю sdlxliff_split_merge
    sdlxliff_module = app_dir / 'sdlxliff_split_merge'
    if sdlxliff_module.exists():
        sys.path.insert(0, str(sdlxliff_module))
        logger.info(f"Added SDLXLIFF module path: {sdlxliff_module}")


def check_dependencies():
    """Проверяет наличие необходимых зависимостей"""
    missing_deps = []
    optional_deps = []

    # Основные зависимости
    try:
        import PySide6
        logger.info(f"PySide6 version: {PySide6.__version__}")
    except ImportError:
        missing_deps.append("PySide6")

    try:
        import openpyxl
        logger.info(f"openpyxl version: {openpyxl.__version__}")
    except ImportError:
        missing_deps.append("openpyxl")

    # Опциональные зависимости
    try:
        import langcodes
        # langcodes не имеет __version__, просто проверяем импорт
        logger.info("langcodes available")
    except ImportError:
        optional_deps.append("langcodes")
        logger.warning("langcodes not found - language detection may be limited")

    try:
        import chardet
        # Пробуем получить версию, если есть
        try:
            version = chardet.__version__
            logger.info(f"chardet version: {version}")
        except AttributeError:
            logger.info("chardet available")
    except ImportError:
        optional_deps.append("chardet")
        logger.warning("chardet not found - encoding detection may be limited")

    try:
        import lxml
        # Пробуем получить версию из lxml.etree
        try:
            from lxml import etree
            logger.info(f"lxml version: {etree.__version__}")
        except (ImportError, AttributeError):
            logger.info("lxml available")
    except ImportError:
        optional_deps.append("lxml")
        logger.warning("lxml not found - using standard xml parser")

    # Проверяем наличие модуля SDLXLIFF
    try:
        from sdlxliff_split_merge import Splitter, Merger, SdlxliffValidator
        logger.info("SDLXLIFF module loaded successfully")
    except ImportError as e:
        logger.warning(f"SDLXLIFF module not found: {e}")
        logger.warning("SDLXLIFF split/merge functionality will be disabled")

    if missing_deps:
        print("\n⚠️  Missing required dependencies:")
        for dep in missing_deps:
            print(f"   ❌ {dep}")
        print("\n📦 Install required dependencies:")
        print(f"   pip install {' '.join(missing_deps)}")
        return False

    if optional_deps:
        print("\n💡 Optional dependencies not installed:")
        for dep in optional_deps:
            print(f"   ⚠️  {dep}")
        print("\n📦 For full functionality, install:")
        print(f"   pip install {' '.join(optional_deps)}")
        print("\n✅ Continuing without optional dependencies...\n")

    return True


def check_sdlxliff_module():
    """Проверяет наличие и структуру модуля SDLXLIFF"""
    app_dir = Path(__file__).parent
    sdlxliff_dir = app_dir / 'sdlxliff_split_merge'

    required_files = [
        '__init__.py',
        'splitter.py',
        'merger.py',
        'validator.py',
        'xml_utils.py',
        'io_utils.py'
    ]

    if not sdlxliff_dir.exists():
        logger.warning(f"SDLXLIFF module directory not found: {sdlxliff_dir}")
        print("\n⚠️  SDLXLIFF module not found!")
        print("   Please ensure 'sdlxliff_split_merge' folder exists with required files:")
        for file in required_files:
            print(f"   - {file}")
        return False

    missing_files = []
    for file in required_files:
        if not (sdlxliff_dir / file).exists():
            missing_files.append(file)

    if missing_files:
        logger.warning(f"Missing SDLXLIFF module files: {missing_files}")
        print(f"\n⚠️  Missing files in sdlxliff_split_merge:")
        for file in missing_files:
            print(f"   ❌ {file}")
        return False

    logger.info("SDLXLIFF module structure verified")
    return True


def create_application():
    """Создает и настраивает приложение"""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon

    app = QApplication(sys.argv)
    app.setApplicationName("Converter Pro")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("ConverterPro")
    app.setApplicationDisplayName("Converter Pro v2.0 - TM/TB/TMX/Excel/SDLXLIFF Converter")

    # Настраиваем стиль
    app.setStyle("Fusion")

    # Устанавливаем шрифт
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Пытаемся установить иконку приложения
    icon_path = Path(__file__).parent / "resources" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
        logger.info(f"Application icon set from {icon_path}")
    else:
        logger.info("Application icon not found, using default")

    # Включаем high DPI поддержку
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    return app


def show_startup_info():
    """Показывает информацию при запуске"""
    print("=" * 60)
    print("🚀 Converter Pro v2.0")
    print("=" * 60)
    print("Professional TM/TB/TMX/Excel/SDLXLIFF Converter")
    print("\nSupported formats:")
    print("  ✅ SDL Trados Memory (.sdltm)")
    print("  ✅ Excel Workbooks (.xlsx, .xls)")
    print("  ✅ Translation Memory eXchange (.tmx)")
    print("  ✅ SDL XLIFF (.sdlxliff) - Split/Merge")
    print("  ✅ MultiTerm XML/Termbase (.xml, .mtf, .tbx)")
    print("=" * 60)
    print()


def main():
    """Главная функция приложения"""
    logger.info("=" * 60)
    logger.info("Starting Converter Pro v2.0")
    logger.info("=" * 60)

    try:
        # Показываем информацию о запуске
        show_startup_info()

        # Настройка путей
        setup_app_paths()

        # Проверка зависимостей
        print("🔍 Checking dependencies...")
        if not check_dependencies():
            logger.error("Required dependencies not found")
            sys.exit(1)

        # Проверка модуля SDLXLIFF
        print("🔍 Checking SDLXLIFF module...")
        sdlxliff_available = check_sdlxliff_module()
        if not sdlxliff_available:
            print("\n⚠️  SDLXLIFF functionality will be limited!")
            print("   You can still use other conversion features.\n")

        print("\n✅ All checks passed!")
        print("\n🚀 Starting application...\n")

        # Создаем приложение
        app = create_application()

        # Пытаемся импортировать и создать главное окно
        try:
            from gui.windows.main_window import MainWindow
            logger.info("Creating main window...")

            main_window = MainWindow()

            # Устанавливаем заголовок окна
            main_window.setWindowTitle("Converter Pro v2.0 - Professional TM/TB/TMX/Excel/SDLXLIFF Converter")

            # Показываем окно
            main_window.show()
            main_window.raise_()  # Принудительно поднимаем окно наверх
            main_window.activateWindow()  # Активируем окно

            # Логируем информацию о системе
            from PySide6.QtCore import QSysInfo
            logger.info(f"System: {QSysInfo.prettyProductName()}")
            logger.info(f"Kernel: {QSysInfo.kernelType()} {QSysInfo.kernelVersion()}")
            logger.info(f"CPU Architecture: {QSysInfo.currentCpuArchitecture()}")

            # Принудительно обрабатываем события
            app.processEvents()

            logger.info("Main window created and shown successfully")
            print("✅ Application started successfully!")
            print("\n💡 Tip: Check 'converter.log' for detailed information")

        except ImportError as ie:
            logger.error(f"Failed to import main window: {ie}")
            print(f"\n❌ Error: Failed to import main window")
            print(f"   Details: {ie}")
            print("\n🔧 Please check that all GUI modules are present:")
            print("   - gui/windows/main_window.py")
            print("   - gui/widgets/")
            print("   - gui/dialogs/")
            return 1
        except Exception as e:
            logger.exception(f"Failed to create main window: {e}")
            print(f"\n❌ Error: Failed to create main window")
            print(f"   Details: {e}")
            return 1

        logger.info("Application started successfully, entering main event loop")

        # Запускаем цикл событий
        exit_code = app.exec()

        logger.info(f"Application finished with exit code: {exit_code}")
        logger.info("=" * 60)

        if exit_code == 0:
            print("\n👋 Thank you for using Converter Pro!")

        return exit_code

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        print("\n\n⚠️  Application interrupted by user")
        return 0
    except Exception as e:
        error_msg = f"Critical error during startup: {e}"
        logger.exception(error_msg)
        print(f"\n💥 CRITICAL ERROR: {error_msg}")
        print("\n📋 Please check 'converter.log' for details")

        # Пытаемся показать диалог с ошибкой
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                QMessageBox.critical(
                    None,
                    "Critical Error",
                    f"Failed to start Converter Pro:\n\n{e}\n\n"
                    f"Please check converter.log for details."
                )
        except:
            pass

        return 1


if __name__ == "__main__":
    sys.exit(main())