import logging
import os
from pathlib import Path


class ContextFilter(logging.Filter):
    def filter(self, record):
        record.run_id = getattr(record, "run_id", os.getenv("RUN_ID", "unknown"))
        record.config_name = getattr(record, "config_name", os.getenv("CONFIG_NAME", "unknown"))
        return True


def configure_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    handlers = [logging.StreamHandler()]
    context_filter = ContextFilter()

    log_file = os.getenv("LOG_FILE")
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))

    for handler in handlers:
        handler.addFilter(context_filter)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - run_id=%(run_id)s - config=%(config_name)s - %(message)s',
        handlers=handlers,
        force=True,
    )
