"""Simplified logging helpers used by worker classes."""

import logging

logger = logging.getLogger(__name__)


def log_info(message: str) -> None:
    logger.info(message)


def log_export(message: str) -> None:
    logger.info(message)


def log_error(message: str) -> None:
    logger.error(message)
