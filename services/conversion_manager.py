"""Conversion manager handling business logic for conversions."""

from pathlib import Path
from typing import List
from PySide6.QtCore import QObject, QThread, Signal

from workers.conversion_worker import BatchConversionWorker
from workers.excel_conversion_worker import ExcelConversionWorker
from workers.tb_worker import TbWorker


class ConversionManager(QObject):
    """Separate business logic from GUI for conversion tasks."""

    # Signals re-emitted from workers
    progress_changed = Signal(int, str, int, int)
    file_started = Signal(Path)
    file_completed = Signal(Path, object)
    batch_completed = Signal(list)
    error_occurred = Signal(str)

    # Internal signals to execute worker methods in its thread
    _start_batch = Signal(list, object, object)
    _stop_batch = Signal()

    excel_conversion_finished = Signal(object)
    excel_conversion_error = Signal(str)

    tb_progress = Signal(int)
    tb_log = Signal(str)
    tb_finished = Signal(bool, str)
    tb_error = Signal(str)

    # Signals for SDLXLIFF operations
    sdlxliff_progress = Signal(int, str)  # progress, message
    sdlxliff_log = Signal(str)  # log message
    sdlxliff_finished = Signal(object)  # ConversionResult
    sdlxliff_error = Signal(str)  # error message

    def __init__(self):
        super().__init__()
        # batch worker
        self._batch_worker = BatchConversionWorker()
        self._thread = QThread()
        self._batch_worker.moveToThread(self._thread)

        # connect internal signals to run in worker thread
        self._start_batch.connect(self._batch_worker.convert_batch)
        self._stop_batch.connect(self._batch_worker.stop_batch)

        # re-emit signals
        self._batch_worker.progress_changed.connect(self.progress_changed)
        self._batch_worker.file_started.connect(self.file_started)
        self._batch_worker.file_completed.connect(self.file_completed)
        self._batch_worker.batch_completed.connect(self.batch_completed)
        self._batch_worker.error_occurred.connect(self.error_occurred)

        self._thread.start()

        self._excel_workers: List[ExcelConversionWorker] = []
        self._tb_workers: List[TbWorker] = []
        self._sdlxliff_workers: List = []

    def start_batch(self, files: List[Path], options, file_languages=None):
        """Start batch conversion."""
        # Invoke conversion in the worker thread
        self._start_batch.emit(files, options, file_languages)

    def stop_all(self):
        """Stop all running conversions."""
        self._stop_batch.emit()
        for worker in list(self._excel_workers):
            worker.stop()
        for worker in list(self._tb_workers):
            worker.terminate()
        for worker in list(self._sdlxliff_workers):
            worker.stop()

    def start_excel(self, filepath: Path, settings, options):
        """Start Excel conversion in a separate worker."""
        worker = ExcelConversionWorker(filepath, settings, options)
        worker.finished.connect(self._on_excel_finished)
        worker.error.connect(self._on_excel_error)
        self._excel_workers.append(worker)
        worker.start()

    def start_termbase(self, filepath: Path, options):
        """Start termbase conversion in a separate worker."""
        worker = TbWorker(
            filepath,
            options.source_lang,
            output_dir=None,
            export_tmx=options.export_tmx,
            export_xlsx=options.export_xlsx,
        )
        worker.progress.connect(self.tb_progress)
        worker.log_written.connect(self.tb_log)
        worker.finished.connect(self._on_tb_finished)
        self._tb_workers.append(worker)
        worker.start()

    def start_sdlxliff_split(self, filepath: Path, settings, options):
        """Start SDLXLIFF split operation in a separate worker."""
        from workers.sdlxliff_worker import SdlxliffSplitWorker

        worker = SdlxliffSplitWorker(filepath, settings, options)
        worker.finished.connect(self._on_sdlxliff_finished)
        worker.error.connect(self._on_sdlxliff_error)
        worker.progress.connect(self.sdlxliff_progress)
        worker.log_written.connect(self.sdlxliff_log)
        self._sdlxliff_workers.append(worker)
        worker.start()

    def start_sdlxliff_merge(self, filepaths: List[Path], settings, options):
        """Start SDLXLIFF merge operation in a separate worker."""
        from workers.sdlxliff_worker import SdlxliffMergeWorker

        worker = SdlxliffMergeWorker(filepaths, settings, options)
        worker.finished.connect(self._on_sdlxliff_finished)
        worker.error.connect(self._on_sdlxliff_error)
        worker.progress.connect(self.sdlxliff_progress)
        worker.log_written.connect(self.sdlxliff_log)
        self._sdlxliff_workers.append(worker)
        worker.start()

    def _on_tb_finished(self, success: bool, message: str):
        sender = self.sender()
        if sender in self._tb_workers:
            self._tb_workers.remove(sender)
        if success:
            self.tb_finished.emit(True, message)
        else:
            self.tb_error.emit(message)

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

    def _on_sdlxliff_finished(self, result):
        """Handle SDLXLIFF operation completion."""
        sender = self.sender()
        if sender in self._sdlxliff_workers:
            self._sdlxliff_workers.remove(sender)
        self.sdlxliff_finished.emit(result)

    def _on_sdlxliff_error(self, message: str):
        """Handle SDLXLIFF operation error."""
        sender = self.sender()
        if sender in self._sdlxliff_workers:
            self._sdlxliff_workers.remove(sender)
        self.sdlxliff_error.emit(message)

    def shutdown(self):
        """Stop workers and close threads."""
        self.stop_all()
        self._thread.quit()
        self._thread.wait(3000)
        for worker in list(self._excel_workers):
            worker.wait(1000)
        for worker in list(self._tb_workers):
            worker.wait(1000)
        for worker in list(self._sdlxliff_workers):
            worker.wait(1000)