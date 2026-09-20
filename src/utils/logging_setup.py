"""Application logging.

A single rotating log file replaces the scattered ``print`` calls: failures
that used to vanish (the app is usually started without a console) are now
written to ``%APPDATA%\\Hushmix\\hushmix.log``.

The app data directory is created here before the handler is attached.  Without
that, the very first run on a clean machine silently lost every log record: the
directory only came into existence later, when the settings file was written,
and ``RotatingFileHandler`` had already failed to open its file.
"""

import logging
import logging.handlers
import os
import sys

from utils.log_path import resolve_log_file

_LOGGER_NAME = "hushmix"
_configured = False


def setup_logging(level=logging.INFO, console=True):
    """Configure the ``hushmix`` logger once and return it."""
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)

    if _configured:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler, log_path, failure = _build_file_handler(formatter)
    if handler is not None:
        logger.addHandler(handler)
        logger.debug("Logging to %s", log_path)

    stream = getattr(sys, "stderr", None)
    if console and stream is not None:
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if failure:
        # Reported after the stream handler exists so the reason is at least
        # visible when a console is attached.
        logger.warning("File logging is unavailable: %s", failure)

    _configured = True
    return logger


def _build_file_handler(formatter):
    """Create the rotating file handler, trying the fallback location too.

    Returns ``(handler_or_None, path, error_message_or_None)``.
    """
    last_error = None

    for path in resolve_log_file():
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                path, maxBytes=512 * 1024, backupCount=2, encoding="utf-8"
            )
            handler.setFormatter(formatter)
            return handler, path, None
        except OSError as error:
            last_error = f"{path}: {error}"
            continue

    return None, None, last_error


def get_logger(name=None):
    """Return a child logger of the application logger."""
    if not _configured:
        setup_logging()
    return logging.getLogger(f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME)
