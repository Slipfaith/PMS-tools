"""Conversion manager handling business logic for conversions."""

from pathlib import Path
from typing import List
from PySide6.QtCore import QObject, QThread, Signal

from workers.conversion_worker import BatchConversionWorker
from workers.excel_conversion_worker import ExcelConversionWorker


class ConversionManager(QObject):
    """Separate business logic from GUI for conversion tasks."""

    # Signals re-emitted from workers
    progress_changed = Signal(int, str, int, int)
    file_started = Signal(Path)
    file_completed = Signal(Path, object)
    batch_completed = Signal(list)
    error_occurred = Signal(str)

    excel_conversion_finished = Signal(object)
    excel_conversion_error = Signal(str)

    def __init__(self):
        super().__init__()
        # batch worker
        self._batch_worker = BatchConversionWorker()
        self._thread = QThread()
        self._batch_worker.moveToThread(self._thread)

        # re-emit signals
        self._batch_worker.progress_changed.connect(self.progress_changed)
        self._batch_worker.file_started.connect(self.file_started)
        self._batch_worker.file_completed.connect(self.file_completed)
        self._batch_worker.batch_completed.connect(self.batch_completed)
        self._batch_worker.error_occurred.connect(self.error_occurred)

        self._thread.start()

        self._excel_workers: List[ExcelConversionWorker] = []

    def start_batch(self, files: List[Path], options):
        """Start batch conversion."""
        self._batch_worker.convert_batch(files, options)

    def stop_all(self):
        """Stop all running conversions."""
        self._batch_worker.stop_batch()
        for worker in list(self._excel_workers):
            worker.stop()

    def start_excel(self, filepath: Path, settings, options):
        """Start Excel conversion in a separate worker."""
        worker = ExcelConversionWorker(filepath, settings, options)
        worker.finished.connect(self._on_excel_finished)
        worker.error.connect(self._on_excel_error)
        self._excel_workers.append(worker)
        worker.start()

    def _on_excel_finished(self, result):
        sender = self.sender()
        if sender in self._excel_workers:
            self._excel_workers.remove(sender)
        self.excel_conversion_finished.emit(result)

    def _on_excel_error(self, message: str):
        sender = self.sender()
        if sender in self._excel_workers:
            self._excel_workers.remove(sender)
        self.excel_conversion_error.emit(message)


    def shutdown(self):
        """Stop workers and close threads."""
        self.stop_all()
        self._thread.quit()
        self._thread.wait(3000)
        for worker in list(self._excel_workers):
            worker.wait(1000)

