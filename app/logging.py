"""Structured JSON logging with request-ID propagation.

structlog over the stdlib because every line needs to be machine-parseable
JSON carrying the same request_id the client saw in its error envelope. That
correlation is what makes a breach notification under Law 2024/017 possible
at all: without it, "what did this user's session do" is unanswerable.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

import structlog

# Bound per request by RequestIdMiddleware, read by the log processor below.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def _add_request_id(_logger: object, _name: str, event_dict: dict) -> dict:
    event_dict["request_id"] = request_id_ctx.get()
    return event_dict


def configure_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_request_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "vora") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
