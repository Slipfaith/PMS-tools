from pathlib import Path
from typing import Optional
from PySide6.QtCore import QThread, Signal

from services.split_service import SplitService


class SplitWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        filepath: Path,
        parts: Optional[int] = None,
        words: Optional[int] = None,
        output_dir: Optional[Path] = None,
    ):
        super().__init__()
        self.filepath = filepath
        self.parts = parts
        self.words = words
        self.output_dir = output_dir
        self.service = SplitService()
        self.should_stop = False

    def run(self):
        try:
            paths = self.service.split(
                self.filepath,
                parts=self.parts,
                words_per_file=self.words,
                output_dir=self.output_dir,
                progress_callback=self._progress,
                should_stop_callback=lambda: self.should_stop,
            )
            self.finished.emit(paths)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self.should_stop = True

    def _progress(self, value: int, msg: str):
        self.progress.emit(value, msg)
