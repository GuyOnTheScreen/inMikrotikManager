# core/log.py

"""
Timestamped, rotating logger for Mikrotik Manager.

Changes vs. initial stub
------------------------
• Automatic rotation at 1 MiB, keeping the three most-recent backups
• Thread-safe because we delegate to Python’s logging infrastructure
• Same public append() signature, so other modules need no edits
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Log file lives beside the project root …/MikroTik_Manager_Log.txt
ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "Mikrotik_Manager_Log.txt"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# Private logger configuration (only runs once, even on reload)
# ------------------------------------------------------------------
_logger = logging.getLogger("mikrotik_manager")
if not _logger.handlers:        # avoid duplicate handlers on hot-reload
    _logger.setLevel(logging.INFO)

    _handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=1_048_576,     # 1 MiB
        backupCount=3,
        encoding="utf-8",
    )
    _handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s")
    )

    _logger.addHandler(_handler)
    _logger.propagate = False   # don’t echo to the root logger


# ------------------------------------------------------------------
# Public helper
# ------------------------------------------------------------------
def append(entry: str, level: int = logging.INFO) -> None:
    """
    Write a single timestamped line to the team log.

    Parameters
    ----------
    entry : str
        Message text. Leading/trailing whitespace is stripped.
    level : int, optional
        Logging level (e.g., logging.INFO, logging.WARNING). Defaults to INFO.
    """
    _logger.log(level, entry.strip())
