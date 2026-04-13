import logging
import os
from pathlib import Path


class ContextFilter(logging.Filter):
    def filter(self, record):
        record.run_id = os.getenv("RUN_ID", "unknown")
        record.config_name = os.getenv("CONFIG_NAME", "unknown")
        return True


def configure_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE")

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(run_id)s - %(config_name)s - %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)

    logging.basicConfig(level=log_level, handlers=[handler])
    logging.getLogger().addFilter(ContextFilter())
