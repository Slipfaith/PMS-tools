#!/usr/bin/env python3
# minimal_converter.py - Минимальная версия для тестирования

import sys
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTextEdit, QFileDialog, QMessageBox
)
from PySide6.QtCore import QThread, QObject, Signal
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SdltmConverter:
    """Простой SDLTM конвертер"""

    def convert_to_tmx(self, sdltm_path: Path, tmx_path: Path, progress_callback=None):
        """Конвертирует SDLTM в TMX"""
        try:
            with sqlite3.connect(str(sdltm_path)) as conn:
                cursor = conn.cursor()

                # Получаем общее количество
                cursor.execute("SELECT COUNT(*) FROM translation_units")
                total = cursor.fetchone()[0]

                if progress_callback:
                    progress_callback(10, f"Found {total} segments")

                # Читаем сегменты батчами
                segments = []
                seen = set()
                batch_size = 1000

                for offset in range(0, total, batch_size):
                    cursor.execute(
                        "SELECT source_segment, target_segment FROM translation_units LIMIT ? OFFSET ?",
                        (batch_size, offset)
                    )

                    batch = cursor.fetchall()
                    for src_xml, tgt_xml in batch:
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

                    # Обновляем прогресс
                    progress = 10 + int((offset / total) * 70)
                    if progress_callback: