"""
Testes do logging estruturado.

Foco: comportamento real do JsonFormatter, não "o format retornou string".
Cobrimos:
- JSON válido em cada linha
- Campos essenciais (timestamp, level, logger, message)
- Campos extras (event, request_id, user_id, status, error)
- NÃO vaza campos arbitrários (segurança)
- Exception formatting
- setup_logging() realmente configura o root logger
"""

import json
import logging

import pytest

from app.utils.logging import JsonFormatter, get_logger, setup_logging


def _record(
    msg: str = "test",
    level: int = logging.INFO,
    name: str = "test.logger",
    extra: dict | None = None,
    exc_info: tuple | None = None,
) -> logging.LogRecord:
    """Cria um LogRecord com extras opcionais para testar o formatter."""
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=exc_info,
    )
    if extra:
        for k, v in extra.items():
            setattr(record, k, v)
    return record


# ============================================================
# JsonFormatter.format — estrutura básica
# ============================================================


class TestJsonFormatterStructure:
    def test_outputs_valid_json(self):
        """A saída precisa ser JSON parseável — essencial pra log agregator."""
        formatter = JsonFormatter()
        line = formatter.format(_record("hello"))
        parsed = json.loads(line)  # ← explodiria se não fosse JSON
        assert isinstance(parsed, dict)

    def test_includes_required_fields(self):
        """Os 4 campos essenciais estão sempre presentes."""
        formatter = JsonFormatter()
        parsed = json.loads(formatter.format(_record("hello")))

        assert "timestamp" in parsed
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "hello"

    def test_level_reflects_record(self):
        formatter = JsonFormatter()
        parsed = json.loads(formatter.format(_record("x", level=logging.ERROR)))
        assert parsed["level"] == "ERROR"

    def test_timestamp_is_iso_utc(self):
        """Timestamp em ISO 8601 (com T e offset de UTC)."""
        formatter = JsonFormatter()
        parsed = json.loads(formatter.format(_record()))
        # Não testa o valor exato, mas o formato
        assert "T" in parsed["timestamp"]
        assert parsed["timestamp"].endswith("+00:00")


# ============================================================
# JsonFormatter.format — campos extras
# ============================================================


class TestJsonFormatterExtras:
    def test_includes_known_extra_fields(self):
        """
        Campos injetados via `logger.info(..., extra={...})` aparecem no JSON.
        Esses são os campos que a gente quer pra correlacionar eventos.
        """
        formatter = JsonFormatter()
        record = _record(
            "event happened",
            extra={
                "event": "AUTH_LOGIN_SUCCESS",
                "request_id": "req-123",
                "user_id": "u1",
                "status": "success",
                "error": None,
                "endpoint": "/auth/login",
                "duration_ms": 42,
            },
        )
        parsed = json.loads(formatter.format(record))

        assert parsed["event"] == "AUTH_LOGIN_SUCCESS"
        assert parsed["request_id"] == "req-123"
        assert parsed["user_id"] == "u1"
        assert parsed["status"] == "success"
        assert parsed["endpoint"] == "/auth/login"
        assert parsed["duration_ms"] == 42

    def test_ignores_unknown_extra_fields(self):
        """
        SEGURANÇA: campos arbitrários injetados via extra não vazam pro log.
        Só a allowlist do formatter passa. Isso impede que alguém, por engano,
        faça logger.info(..., extra={"password": "..."}) e vaze credencial.
        """
        formatter = JsonFormatter()
        record = _record(
            "test",
            extra={
                "password": "SuperSecret123!",
                "access_token": "eyJhbGc...",
                "refresh_token": "v1-xyz",
                "authorization": "Bearer TOKEN",
                "internal_field": "should-not-leak",
            },
        )
        parsed = json.loads(formatter.format(record))

        assert "password" not in parsed
        assert "access_token" not in parsed
        assert "refresh_token" not in parsed
        assert "authorization" not in parsed
        assert "internal_field" not in parsed

        # Belt and suspenders: verifica que nem o valor em si vazou
        line = formatter.format(record)
        assert "SuperSecret123!" not in line
        assert "eyJhbGc..." not in line
        assert "v1-xyz" not in line

    def test_none_extra_field_is_included(self):
        """None é valor válido — não confundir com ausente."""
        formatter = JsonFormatter()
        record = _record("test", extra={"error": None})
        parsed = json.loads(formatter.format(record))
        assert parsed["error"] is None


# ============================================================
# JsonFormatter.format — exceptions
# ============================================================


class TestJsonFormatterExceptions:
    def test_formats_exception_traceback(self):
        """exc_info é serializado como string legível no campo 'exception'."""
        formatter = JsonFormatter()

        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = _record("failed", exc_info=exc_info)
        parsed = json.loads(formatter.format(record))

        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "boom" in parsed["exception"]

    def test_no_exception_field_when_no_exc_info(self):
        """Sem exceção, sem campo 'exception' — não poluir."""
        formatter = JsonFormatter()
        parsed = json.loads(formatter.format(_record("ok")))
        assert "exception" not in parsed


# ============================================================
# setup_logging
# ============================================================


class TestSetupLogging:
    def test_configures_root_logger_with_json_formatter(self):
        """setup_logging() instala um handler com JsonFormatter no root."""
        # Guarda estado atual pra restaurar depois
        root = logging.getLogger()
        original_handlers = list(root.handlers)

        try:
            setup_logging()
            assert len(root.handlers) == 1
            handler = root.handlers[0]
            assert isinstance(handler.formatter, JsonFormatter)
        finally:
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)

    def test_sets_level(self):
        root = logging.getLogger()
        original_level = root.level
        try:
            setup_logging(level=logging.WARNING)
            assert root.level == logging.WARNING
        finally:
            root.setLevel(original_level)

    def test_clears_previous_handlers(self):
        """Não acumular handlers em chamadas sucessivas (evita log duplicado)."""
        root = logging.getLogger()
        original_handlers = list(root.handlers)

        try:
            # Adiciona um handler dummy
            root.addHandler(logging.NullHandler())
            before = len(root.handlers)
            assert before >= 1

            setup_logging()
            # Depois do setup: só 1 handler (o JsonFormatter)
            assert len(root.handlers) == 1
        finally:
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)


# ============================================================
# get_logger
# ============================================================


class TestGetLogger:
    def test_returns_named_logger(self):
        logger = get_logger("app.test")
        assert logger.name == "app.test"
        assert isinstance(logger, logging.Logger)