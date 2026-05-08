"""Structured logging helper.

Emits one JSON line per log call so logs are machine-parseable in production.
Stdlib only — no new dependencies. Compatible with structlog adoption later
(swap `_JsonHandler` formatter for structlog's renderer).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


_BASE_FIELDS = ("timestamp", "level", "event", "service")


class _JsonFormatter(logging.Formatter):
    """Format every log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
            "service": record.name,
        }
        # Promote extra={} fields onto the payload, but never overwrite base fields.
        for key, value in record.__dict__.items():
            if key in payload or key in _RESERVED:
                continue
            payload[key] = value
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


# stdlib record attributes we don't want to propagate as log fields
_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}


def get_logger(service: str) -> logging.Logger:
    """Return a structured-JSON logger configured once per service.

    Use ``logger.info("event.name", extra={"key": "value"})`` to emit
    structured fields. The first positional arg is the event name; structured
    data lives in ``extra``.
    """
    logger = logging.getLogger(service)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    logger.propagate = False
    return logger
