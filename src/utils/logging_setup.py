"""Application logging.

A single rotating log file replaces the scattered ``print`` calls: failures
that used to vanish (the app is usually started without a console) are now
written to ``%APPDATA%\\Hushmix\\hushmix.log``.

The file is always written at DEBUG level, whatever the console shows.  The
diagnostics that explain behaviour - which lane controls which application, why a
channel was skipped, which monitor scale was applied - are all debug records, and
logging the file at INFO meant they could never be read without editing the
source.  The console stays at INFO so a terminal is not flooded, and ``HUSH_DEBUG=1`` (or the
``verbose_logging`` setting) raises it.

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

#: What the rotating file always records.
FILE_LEVEL = logging.DEBUG
#: What the console shows unless verbose logging is on.
CONSOLE_LEVEL = logging.INFO
VERBOSE_CONSOLE_LEVEL = logging.DEBUG


def setup_logging(level=None, console=True, verbose=None):
    """Configure the ``hushmix`` logger once and return it.

    *level* overrides the file level; *verbose* forces the console to DEBUG.
    Both default to the behaviour described in the module docstring.
    """
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)

    if _configured:
        return logger

    # Start from a clean slate: without this, a module reload (or a second call
    # after the flag is reset) attached a second copy of every handler and each
    # record was written twice.
    #
    # The handlers are flushed and detached but deliberately not closed:
    # ``Handler.close()`` on a stream handler used to mark the *shared* stream as
    # finalized on some Python versions, after which every later record produced
    # "--- Logging error ---" instead of a log line.
    for existing in list(logger.handlers):
        logger.removeHandler(existing)
        try:
            existing.flush()
        except Exception:
            pass

    file_level = FILE_LEVEL if level is None else level
    if verbose is None:
        verbose = _verbose_requested()

    logger.setLevel(min(file_level, CONSOLE_LEVEL))

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler, log_path, failure = _build_file_handler(formatter)
    if handler is not None:
        # The file is the diagnostic record, so it is never filtered as tightly
        # as the console.
        handler.setLevel(file_level)
        logger.addHandler(handler)

    stream = getattr(sys, "stderr", None)
    if console and stream is not None:
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setLevel(VERBOSE_CONSOLE_LEVEL if verbose else CONSOLE_LEVEL)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    # Recorded after the handlers exist so it lands in the file too.
    logger.debug("Logging to %s (file level %s)", log_path, logging.getLevelName(file_level))
    if verbose:
        logger.debug("Verbose console logging is on")

    if failure:
        # Reported after the stream handler exists so the reason is at least
        # visible when a console is attached.
        logger.warning("File logging is unavailable: %s", failure)

    _configured = True
    return logger


#: Set any of these to a truthy value for debug output on the console.
VERBOSE_ENVIRONMENT_VARIABLES = ("HUSH_DEBUG", "HUSH_VERBOSE")

def _verbose_requested():
    """True when debug output was asked for through the environment."""
    for name in VERBOSE_ENVIRONMENT_VARIABLES:
        value = os.environ.get(name)
        if value and value.strip().lower() not in ("0", "false", "no"):
            return True
    return False


def set_console_verbose(enabled):
    """Turn verbose console logging on or off at runtime."""
    for handler in logging.getLogger(_LOGGER_NAME).handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.handlers.RotatingFileHandler
        ):
            handler.setLevel(VERBOSE_CONSOLE_LEVEL if enabled else CONSOLE_LEVEL)
    return bool(enabled)


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
