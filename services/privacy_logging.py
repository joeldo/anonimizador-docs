import logging
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

_sensitive = ContextVar("sensitive_processing", default=False)


class _SensitiveLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not _sensitive.get()


_filter = _SensitiveLogFilter()


@contextmanager
def sensitive_processing() -> Generator[None, None, None]:
    handlers = set(logging.getLogger().handlers)
    for logger in tuple(logging.Logger.manager.loggerDict.values()):
        if isinstance(logger, logging.Logger):
            handlers.update(logger.handlers)
    if logging.lastResort is not None:
        handlers.add(logging.lastResort)
    for handler in handlers:
        handler.addFilter(_filter)
    token = _sensitive.set(True)
    try:
        yield
    finally:
        _sensitive.reset(token)
