# sdlxliff_split_merge/io_utils.py

from pathlib import Path
import re
import logging
from typing import List

logger = logging.getLogger(__name__)


def make_split_filenames(src_path: str, parts_count: int) -> List[str]:
    p = Path(src_path)
    name = p.stem
    ext = p.suffix
    parent = p.parent

    return [
        str(parent / f"{name}.{i + 1}of{parts_count}{ext}")
        for i in range(parts_count)
    ]


def save_bytes_list(files_content: List[str], filenames: List[str]):
    for content, fname in zip(files_content, filenames):
        try:
            encoding = _detect_encoding_from_content(content)

            with open(fname, "w", encoding=encoding, newline='') as f:
                f.write(content)

            logger.info(f"Saved file: {fname} (encoding: {encoding})")

        except Exception as e:
            logger.error(f"Error saving file {fname}: {e}")
            raise


def read_bytes_list(paths: List[str]) -> List[str]:
    content_list = []

    for path in paths:
        try:
            content = read_file_with_encoding_detection(Path(path))
            content_list.append(content)
            logger.info(f"Read file: {path}")

        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            raise

    return content_list


def read_file_with_encoding_detection(file_path: Path) -> str:
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()

        if len(raw_data) == 0:
            raise ValueError(f"File {file_path} is empty")

        encoding = _detect_encoding_from_bom(raw_data)
        if encoding:
            content = raw_data.decode(encoding)
            if content.strip():
                return content

        encodings_to_try = ['utf-8', 'utf-8-sig', 'utf-16', 'utf-16le', 'utf-16be', 'cp1252', 'iso-8859-1']

        for encoding in encodings_to_try:
            try:
                content = raw_data.decode(encoding)
                if content.strip() and _validate_xml_content(content):
                    return content
            except UnicodeDecodeError:
                continue

        content = raw_data.decode('utf-8', errors='replace')
        logger.warning(f"Used UTF-8 with error replacement for {file_path}")
        return content

    except Exception as e:
        logger.error(f"Critical error reading file {file_path}: {e}")
        raise


def _detect_encoding_from_bom(raw_data: bytes) -> str:
    if raw_data.startswith(b'\xff\xfe\x00\x00'):
        return 'utf-32le'
    elif raw_data.startswith(b'\x00\x00\xfe\xff'):
        return 'utf-32be'
    elif raw_data.startswith(b'\xff\xfe'):
        return 'utf-16le'
    elif raw_data.startswith(b'\xfe\xff'):
        return 'utf-16be'
    elif raw_data.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    return None


def _detect_encoding_from_content(content: str) -> str:
    encoding_match = re.search(r'encoding=["\']([^"\']+)["\']', content[:1024])
    if encoding_match:
        declared_encoding = encoding_match.group(1).lower()

        encoding_map = {
            'utf-8': 'utf-8',
            'utf8': 'utf-8',
            'utf-16': 'utf-16',
            'utf16': 'utf-16',
            'windows-1252': 'cp1252',
            'cp1252': 'cp1252',
            'iso-8859-1': 'iso-8859-1',
            'latin-1': 'iso-8859-1'
        }

        return encoding_map.get(declared_encoding, declared_encoding)

    return 'utf-8'


def _validate_xml_content(content: str) -> bool:
    if not content.strip():
        return False

    if not re.search(r'<[^>]+>', content[:1024]):
        return False

    if 'xliff' in content.lower() or 'trans-unit' in content.lower():
        return True

    return True


def sort_split_filenames(file_list: List[str]) -> List[str]:
    pattern = re.compile(r'\.(\d+)of(\d+)\.sdlxliff$', re.IGNORECASE)

    def extract_part_number(fname: str) -> int:
        m = pattern.search(fname)
        if m:
            return int(m.group(1))
        return float('inf')

    sorted_list = sorted(file_list, key=extract_part_number)
    logger.info(f"Sorted {len(file_list)} files by part number")
    return sorted_list


def create_backup(file_path: Path, backup_suffix: str = ".backup") -> Path:
    backup_path = file_path.with_suffix(file_path.suffix + backup_suffix)

    try:
        counter = 1
        while backup_path.exists():
            backup_path = file_path.with_suffix(f"{file_path.suffix}{backup_suffix}.{counter}")
            counter += 1

        import shutil
        shutil.copy2(file_path, backup_path)

        logger.info(f"Created backup: {backup_path}")
        return backup_path

    except Exception as e:
        logger.error(f"Error creating backup for {file_path}: {e}")
        raise


def validate_file_path(file_path: Path) -> bool:
    if not file_path.exists():
        return False

    if not file_path.is_file():
        return False

    if file_path.stat().st_size == 0:
        return False

    return True


def get_file_encoding(file_path: Path) -> str:
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(1024)

        bom_encoding = _detect_encoding_from_bom(raw_data)
        if bom_encoding:
            return bom_encoding

        try:
            content = raw_data.decode('utf-8')
            return _detect_encoding_from_content(content)
        except UnicodeDecodeError:
            pass

        encodings_to_try = ['utf-16', 'cp1252', 'iso-8859-1']
        for encoding in encodings_to_try:
            try:
                raw_data.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue

        logger.warning(f"Could not detect encoding for {file_path}, defaulting to utf-8")
        return 'utf-8'

    except Exception as e:
        logger.warning(f"Error detecting encoding for {file_path}: {e}")
        return 'utf-8'


def ensure_directory_exists(file_path: Path) -> None:
    directory = file_path.parent
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {directory}")


def get_safe_filename(filename: str) -> str:
    safe_chars = re.compile(r'[^a-zA-Z0-9._-]')
    safe_filename = safe_chars.sub('_', filename)

    if len(safe_filename) > 255:
        name, ext = safe_filename.rsplit('.', 1) if '.' in safe_filename else (safe_filename, '')
        max_name_length = 255 - len(ext) - 1 if ext else 255
        safe_filename = name[:max_name_length] + ('.' + ext if ext else '')

    return safe_filename


def cleanup_temp_files(file_paths: List[Path]) -> None:
    for file_path in file_paths:
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Could not clean up temp file {file_path}: {e}")


def verify_file_integrity(file_path: Path, expected_size: int = None) -> bool:
    try:
        if not validate_file_path(file_path):
            return False

        if expected_size is not None:
            actual_size = file_path.stat().st_size
            if actual_size != expected_size:
                logger.warning(f"File size mismatch for {file_path}: expected {expected_size}, got {actual_size}")
                return False

        try:
            content = read_file_with_encoding_detection(file_path)
            if not content.strip():
                return False

            if not _validate_xml_content(content):
                return False

        except Exception as e:
            logger.error(f"Content validation failed for {file_path}: {e}")
            return False

        return True

    except Exception as e:
        logger.error(f"Integrity check failed for {file_path}: {e}")
        return False


def calculate_file_checksum(file_path: Path) -> str:
    import hashlib

    try:
        with open(file_path, 'rb') as f:
            content = f.read()

        return hashlib.md5(content).hexdigest()

    except Exception as e:
        logger.error(f"Error calculating checksum for {file_path}: {e}")
        return ""


def compare_files_binary(file1: Path, file2: Path) -> bool:
    try:
        if not (validate_file_path(file1) and validate_file_path(file2)):
            return False

        if file1.stat().st_size != file2.stat().st_size:
            return False

        with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
            chunk_size = 8192
            while True:
                chunk1 = f1.read(chunk_size)
                chunk2 = f2.read(chunk_size)

                if chunk1 != chunk2:
                    return False

                if not chunk1:
                    break

        return True

    except Exception as e:
        logger.error(f"Error comparing files {file1} and {file2}: {e}")
        return False