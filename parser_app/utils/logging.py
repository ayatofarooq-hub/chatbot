"""Logging helpers for parser_app."""

from __future__ import annotations

import logging

from config import LOG_DIR


def get_parser_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("parser_app")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

        processing_handler = logging.FileHandler(LOG_DIR / "processing.log", encoding="utf-8")
        processing_handler.setFormatter(formatter)
        logger.addHandler(processing_handler)

        error_handler = logging.FileHandler(LOG_DIR / "validation_errors.log", encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)

    return logger


def log_stage_start(logger: logging.Logger, filename: str, stage: str) -> None:
    logger.info("[%s] %s...", filename, stage)


def log_stage_complete(logger: logging.Logger, filename: str, stage: str) -> None:
    logger.info("[%s] %s completed.", filename, stage)


def log_stage_error(logger: logging.Logger, filename: str, stage: str, error: Exception) -> None:
    logger.exception("[%s] %s failed: %s", filename, stage, error)
