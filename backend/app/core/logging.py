"""Logging for the app.* loggers.

Uvicorn configures only its own loggers, so without this our INFO messages
(for example the database startup report) would not be shown. The format
follows uvicorn's "LEVEL:     message" style.
"""

import logging

_FORMAT = "%(levelname)s:     [%(name)s] %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    logger = logging.getLogger("app")
    if logger.handlers:  # already configured (e.g. on a development reload)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
