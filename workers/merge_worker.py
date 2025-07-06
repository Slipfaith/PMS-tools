from pathlib import Path
from typing import List
from PySide6.QtCore import QThread, Signal

from services.split_service import SplitService


class MergeWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(Path)
    error = Signal(str)

    def __init__(self, part_paths: List[Path], output_path: Path):
        super().__init__()
        self.part_paths = part_paths
        self.output_path = output_path
        self.service = SplitService()
        self.should_stop = False

    def run(self):
        try:
            path = self.service.merge(
                self.part_paths,
                self.output_path,
                progress_callback=self._progress,
                should_stop_callback=lambda: self.should_stop,
            )
            self.finished.emit(path)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self.should_stop = True

    def _progress(self, value: int, msg: str):
        self.progress.emit(value, msg)
