import logging
from logging.handlers import RotatingFileHandler


def setup_logger(logfile: str = "split_merge.log", *, structured: bool = False) -> logging.Logger:
    """Configure root logger for console and file output.

    Parameters
    ----------
    logfile:
        Destination file for log messages.
    structured:
        If ``True`` use JSON formatted records.
    """
    fmt = (
        "{\"time\": \"%(asctime)s\", \"level\": \"%(levelname)s\", \"message\": \"%(message)s\"}"
        if structured
        else "%(asctime)s %(levelname)s: %(message)s"
    )
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[logging.FileHandler(logfile, encoding="utf-8"), logging.StreamHandler()],
    )
    return logging.getLogger("splitmerge")


def get_file_logger(logfile: str = "split_merge_details.log", *, structured: bool = False) -> logging.Logger:
    """Return a dedicated logger writing to ``logfile``.

    Parameters
    ----------
    logfile:
        Path to the log file.
    structured:
        If ``True`` the log records will be formatted as JSON.
    """
    logger = logging.getLogger(f"splitmerge.{logfile}")
    if not logger.handlers:
        handler = RotatingFileHandler(logfile, maxBytes=500000, backupCount=3, encoding="utf-8")
        fmt = (
            "{\"time\": \"%(asctime)s\", \"level\": \"%(levelname)s\", \"message\": \"%(message)s\"}"
            if structured
            else "%(asctime)s %(levelname)s: %(message)s"
        )
        formatter = logging.Formatter(fmt)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def get_json_logger(logfile: str = "split_merge.json.log") -> logging.Logger:
    """Shortcut to :func:`get_file_logger` with JSON formatting."""
    return get_file_logger(logfile, structured=True)
