import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Formatter que emite cada log como uma linha JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Campos extras injetados via `logger.info("...", extra={...})`
        for key in ("event", "request_id", "user_id", "endpoint", "status", "duration_ms", "error"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    """Configura o root logger para emitir JSON no stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Helper: logger nomeado."""
    return logging.getLogger(name)