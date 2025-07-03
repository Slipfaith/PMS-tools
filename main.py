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
            # Fallback к минимальной версии
            logger.info("Falling back to built-in converter...")
            main_window = minimal_converter.MainWindow()
            main_window.show()
            main_window.raise_()
            main_window.activateWindow()
            app.processEvents()

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


# Встроенная минимальная версия как fallback
class minimal_converter:
    """Встроенная минимальная версия конвертера"""

    import sqlite3
    import xml.etree.ElementTree as ET
    from pathlib import Path
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QProgressBar, QTextEdit, QFileDialog, QMessageBox
    )
    from PySide6.QtCore import QThread, QObject, Signal

    class SdltmConverter:
        """Простой SDLTM конвертер"""

        def convert_to_tmx(self, sdltm_path, tmx_path, progress_callback=None):
            """Конвертирует SDLTM в TMX"""
            import sqlite3
            import xml.etree.ElementTree as ET

            with sqlite3.connect(str(sdltm_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM translation_units")
                total = cursor.fetchone()[0]

                if progress_callback:
                    progress_callback(10, f"Found {total} segments")

                segments = []
                seen = set()

                cursor.execute("SELECT source_segment, target_segment FROM translation_units")
                for i, (src_xml, tgt_xml) in enumerate(cursor.fetchall()):
                    try:
                        src_text = self._extract_text(src_xml)
                        tgt_text = self._extract_text(tgt_xml)

                        if src_text and tgt_text:
                            key = (src_text, tgt_text)
                            if key not in seen:
                                seen.add(key)
                                segments.append((src_text, tgt_text))
                    except Exception:
                        continue

                    if progress_callback and i % 1000 == 0:
                        progress = 10 + int((i / total) * 70)
                        progress_callback(progress, f"Processed {i}/{total}")

                if progress_callback:
                    progress_callback(80, "Writing TMX file...")

                self._write_tmx(tmx_path, segments)

                if progress_callback:
                    progress_callback(100, f"Completed! Exported {len(segments)} segments")

                return len(segments)

        def _extract_text(self, xml_segment):
            import xml.etree.ElementTree as ET
            try:
                root = ET.fromstring(xml_segment)
                text_elem = root.find(".//Text/Value")
                return text_elem.text.strip() if text_elem is not None and text_elem.text else ""
            except:
                return ""

        def _write_tmx(self, tmx_path, segments):
            import xml.etree.ElementTree as ET

            tmx = ET.Element("tmx", version="1.4")
            header = ET.SubElement(tmx, "header", {
                "creationtool": "ConverterPro",
                "creationtoolversion": "2.0",
                "segtype": "sentence",
                "adminlang": "en-US",
                "srclang": "en-US",
                "datatype": "PlainText"
            })
            body = ET.SubElement(tmx, "body")

            for src_text, tgt_text in segments:
                tu = ET.SubElement(body, "tu")

                src_tuv = ET.SubElement(tu, "tuv", {"xml:lang": "en-US"})
                src_seg = ET.SubElement(src_tuv, "seg")
                src_seg.text = src_text

                tgt_tuv = ET.SubElement(tu, "tuv", {"xml:lang": "ru-RU"})
                tgt_seg = ET.SubElement(tgt_tuv, "seg")
                tgt_seg.text = tgt_text

            tree = ET.ElementTree(tmx)
            tree.write(str(tmx_path), encoding="utf-8", xml_declaration=True)

    class ConversionWorker(QObject):
        from PySide6.QtCore import Signal
        progress_changed = Signal(int, str)
        finished = Signal(int)
        error_occurred = Signal(str)

        def __init__(self, sdltm_path, tmx_path):
            super().__init__()
            self.sdltm_path = sdltm_path
            self.tmx_path = tmx_path
            self.converter = minimal_converter.SdltmConverter()

        def run(self):
            try:
                count = self.converter.convert_to_tmx(
                    self.sdltm_path,
                    self.tmx_path,
                    progress_callback=self.progress_changed.emit
                )
                self.finished.emit(count)
            except Exception as e:
                self.error_occurred.emit(str(e))

    class MainWindow(QMainWindow):
        from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QProgressBar, QTextEdit, \
            QFileDialog, QMessageBox
        from PySide6.QtCore import QThread

        def __init__(self):
            super().__init__()
            self.setWindowTitle("Converter Pro v2.0 (Built-in)")
            self.setMinimumSize(600, 400)
            self.setup_ui()
            self.worker = None
            self.thread = None

        def setup_ui(self):
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QProgressBar, QTextEdit

            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)

            title = QLabel("SDLTM to TMX Converter")
            title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
            layout.addWidget(title)

            self.select_btn = QPushButton("Select SDLTM File")
            self.select_btn.clicked.connect(self.select_file)
            layout.addWidget(self.select_btn)

            self.file_label = QLabel("No file selected")
            layout.addWidget(self.file_label)

            self.convert_btn = QPushButton("Convert to TMX")
            self.convert_btn.clicked.connect(self.start_conversion)
            self.convert_btn.setEnabled(False)
            layout.addWidget(self.convert_btn)

            self.progress = QProgressBar()
            layout.addWidget(self.progress)

            self.status_label = QLabel("Ready")
            layout.addWidget(self.status_label)

            self.log = QTextEdit()
            self.log.setMaximumHeight(150)
            layout.addWidget(self.log)

            self.selected_file = None

        def select_file(self):
            from PySide6.QtWidgets import QFileDialog
            file, _ = QFileDialog.getOpenFileNames(
                self, "Select SDLTM file", "", "SDLTM (*.sdltm)"
            )

            if file:
                from pathlib import Path
                self.selected_file = Path(file[0])
                self.file_label.setText(f"Selected: {self.selected_file.name}")
                self.convert_btn.setEnabled(True)
                self.log_message(f"Selected file: {file[0]}")

        def start_conversion(self):
            if not self.selected_file:
                return

            from PySide6.QtCore import QThread
            tmx_path = self.selected_file.with_suffix('.tmx')

            self.worker = minimal_converter.ConversionWorker(self.selected_file, tmx_path)
            self.thread = QThread()
            self.worker.moveToThread(self.thread)

            self.thread.started.connect(self.worker.run)
            self.worker.progress_changed.connect(self.on_progress)
            self.worker.finished.connect(self.on_finished)
            self.worker.error_occurred.connect(self.on_error)

            self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)

            self.convert_btn.setEnabled(False)
            self.thread.start()
            self.log_message("Starting conversion...")

        def on_progress(self, progress, message):
            self.progress.setValue(progress)
            self.status_label.setText(message)

        def on_finished(self, count):
            from PySide6.QtWidgets import QMessageBox
            self.convert_btn.setEnabled(True)
            self.progress.setValue(100)
            self.status_label.setText(f"Completed! Exported {count} segments")
            self.log_message(f"Conversion completed! {count} segments exported.")
            QMessageBox.information(self, "Success", f"Exported {count} segments to TMX file.")

        def on_error(self, error):
            from PySide6.QtWidgets import QMessageBox
            self.convert_btn.setEnabled(True)
            self.progress.setValue(0)
            self.status_label.setText("Error occurred")
            self.log_message(f"Error: {error}")
            QMessageBox.critical(self, "Error", f"Conversion failed:\n{error}")

        def log_message(self, message):
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log.append(f"[{timestamp}] {message}")


if __name__ == "__main__":
    sys.exit(main())