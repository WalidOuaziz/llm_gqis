import logging
import os
from datetime import datetime
from pathlib import Path


class ExecutionLogger:
    def __init__(self, log_dir=None):
        if log_dir is None:
            log_dir = Path(os.path.expanduser("~")) / ".qgis_llm_agent" / "logs"
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("qgis_llm_agent")
        self.logger.setLevel(logging.DEBUG)

        log_file = log_dir / f"session_{datetime.now():%Y%m%d_%H%M%S}.log"
        fh = logging.FileHandler(str(log_file), encoding="utf-8")
        fh.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        self._entries = []

    def info(self, message):
        self.logger.info(message)
        self._entries.append(("INFO", message))

    def warning(self, message):
        self.logger.warning(message)
        self._entries.append(("WARNING", message))

    def error(self, message):
        self.logger.error(message)
        self._entries.append(("ERROR", message))

    def debug(self, message):
        self.logger.debug(message)
        self._entries.append(("DEBUG", message))

    def get_recent(self, n=20):
        return self._entries[-n:]

    def get_all(self):
        return list(self._entries)
