#!/usr/bin/env python3
import sys
import logging
import argparse
from pathlib import Path

# Старый логгер для GUI, осталось без изменений
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("converter.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

from core.services.sdlxliff_splitter_service import SdlXliffSplitterService
from core.services.sdlxliff_merger_service import SdlXliffMergerService
from utils.logger import logger as sdlx_logger

def setup_app_paths():
    app_dir = Path(__file__).parent
    sys.path.insert(0, str(app_dir))

def check_dependencies() -> bool:
    missing = []
    try:
        import PySide6  # noqa: F401
    except ImportError:
        missing.append("PySide6")
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        missing.append("openpyxl")
    if missing:
        print("Missing dependencies:", ", ".join(missing))
        print("pip install " + " ".join(missing))
        return False
    return True

def cli_mode():
    parser = argparse.ArgumentParser(description="PM-tool: split & merge SDLXLIFF")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("split-xliff", help="Разделить XLIFF")
    sp.add_argument("-i", "--input", type=Path, required=True)
    sp.add_argument("-o", "--output-dir", type=Path, required=True)
    sp.add_argument("-n", "--parts", type=int, default=2)

    mg = sub.add_parser("merge-xliff", help="Объединить XLIFF части")
    mg.add_argument("-i", "--input-dir", type=Path, required=True)
    mg.add_argument("-o", "--output", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.cmd == "split-xliff":
            service = SdlXliffSplitterService()
            parts = service.split(args.input, args.output_dir, args.parts)
            sdlx_logger.info(f"Split done: {len(parts)} parts")
        else:
            service = SdlXliffMergerService()
            out = service.merge(args.input_dir, args.output)
            sdlx_logger.info(f"Merge done: {out}")
        return 0
    except Exception as e:
        sdlx_logger.error(f"Error ({args.cmd}): {e}")
        return 1

def main():
    logger.info("Starting Converter Pro v2.0")
    setup_app_paths()
    if not check_dependencies():
        sys.exit(1)

    # Если вызван CLI-режим split/merge
    if len(sys.argv) > 1 and sys.argv[1] in ("split-xliff", "merge-xliff"):
        sys.exit(cli_mode())

    # Иначе запускаем GUI
    from gui.windows.main_window import MainWindow
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont

    app = QApplication(sys.argv)
    app.setApplicationName("Converter Pro")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("ConverterPro")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))

    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    exit_code = app.exec()
    logger.info(f"Application finished with exit code: {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
