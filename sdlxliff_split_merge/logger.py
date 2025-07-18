import logging
from logging.handlers import RotatingFileHandler


def setup_logger(logfile: str = "split_merge.log") -> logging.Logger:
    """Configure root logger for console and file output."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=[logging.FileHandler(logfile, encoding="utf-8"), logging.StreamHandler()],
    )
    return logging.getLogger("splitmerge")


def get_file_logger(logfile: str = "split_merge_details.log") -> logging.Logger:
    """Return a dedicated logger writing to ``logfile``."""
    logger = logging.getLogger(f"splitmerge.{logfile}")
    if not logger.handlers:
        handler = RotatingFileHandler(logfile, maxBytes=500000, backupCount=3, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
