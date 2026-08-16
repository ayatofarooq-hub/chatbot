"""Logging setup for the DOCX processing pipeline."""

import logging

from app.config import LOGS_FOLDER


PIPELINE_LOGGER_NAME = "app.pipeline"


def setup_pipeline_logging() -> logging.Logger:
    """Configure pipeline logging to console and data/logs."""

    LOGS_FOLDER.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(PIPELINE_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(message)s")
    log_file = LOGS_FOLDER / "pipeline.log"

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
