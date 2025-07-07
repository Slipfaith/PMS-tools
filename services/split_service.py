from pathlib import Path
from typing import List, Optional, Callable

from core.splitters.sdxliff_splitter import SdxliffSplitter, count_words
from core.splitters.sdxliff_merger import SdxliffMerger
from lxml import etree


class SplitService:
    """Business logic for splitting and merging SDXLIFF files."""

    def __init__(self):
        self.splitter = SdxliffSplitter()
        self.merger = SdxliffMerger()

    def analyze(self, filepath: Path) -> dict:
        parser = etree.XMLParser(remove_blank_text=False)
        tree = etree.parse(str(filepath), parser)
        units = tree.findall(".//{*}trans-unit")
        word_count = 0
        char_count = 0
        for u in units:
            src = u.find(".//{*}source")
            text = "" if src is None else "".join(src.itertext())
            word_count += count_words(text)
            char_count += len(text)
        return {"segments": len(units), "words": word_count, "characters": char_count}

    def split(
        self,
        filepath: Path,
        *,
        parts: Optional[int] = None,
        words_per_file: Optional[int] = None,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        should_stop_callback: Optional[Callable[[], bool]] = None,
    ) -> List[Path]:
        return self.splitter.split(
            filepath,
            parts=parts,
            words_per_file=words_per_file,
            output_dir=output_dir,
            progress_callback=progress_callback,
            should_stop_callback=should_stop_callback,
        )

    def merge(
        self,
        part_paths: List[Path],
        output_path: Path,
        *,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        should_stop_callback: Optional[Callable[[], bool]] = None,
    ) -> Path:
        return self.merger.merge(
            part_paths,
            output_path,
            progress_callback=progress_callback,
            should_stop_callback=should_stop_callback,
        )
