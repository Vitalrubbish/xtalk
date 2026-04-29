import logging
import os
from datetime import datetime


def mute_other_logging():
    """Reduce noise from third-party loggers used by Xtalk.

    Notes
    -----
    This helper raises the root logger level to ``WARNING`` and applies the
    same threshold to common network and SDK loggers so sample applications
    can keep terminal output focused on Xtalk events.
    """
    logging.getLogger().setLevel(logging.WARNING)
    for name in [
        "httpx",
        "httpcore",
        "httpcore.http11",
        "openai",
        "openai._base_client",
        "urllib3.connectionpool",
    ]:
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)  # Keep WARNING+ only
        logger.propagate = True  # Let logs bubble to root handlers


def setup_logging():
    """Configure the process-wide Xtalk logger.

    Returns
    -------
    logging.Logger
        The configured ``xtalk`` logger instance.

    Notes
    -----
    A timestamped log file is created under ``logs/`` for every process start.
    """
    # Ensure logs directory exists
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    # Create timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"logs/xtalk_{timestamp}.log"

    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            # Console handler
            logging.StreamHandler(),
            # File handler
            logging.FileHandler(log_filename, encoding="utf-8"),
        ],
    )

    # Return xtalk logger
    logger = logging.getLogger("xtalk")

    return logger


# Initialize logger on import
logger = setup_logging()
