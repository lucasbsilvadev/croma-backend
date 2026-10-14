import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# ============================================================
# Sanitização de log (fonte única — LGPD-09/LGPD-10)
# ============================================================
# Antes vivia no MPClient; agora vive aqui pra valer globalmente.
# O JsonFormatter aplica em message + campos string da allowlist.
#
# Por que sanitizar só strings?
# - Strings livres (mensagem, event, error) podem conter CPF/email/token
#   por acidente. Regex nelas é defesa em profundidade.
# - Campos numéricos (duration_ms) não têm risco de PII e precisam manter
#   o tipo pra observabilidade (ex: p95 de latência em log aggregator).
# - mp_error_detail é dict com strings internas — sanitização recursiva.

_SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{11}\b"),                       # CPF (11 dígitos)
    re.compile(r"\b\d{14}\b"),                       # CNPJ (14 dígitos)
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),     # email
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),       # Authorization Bearer
    re.compile(r"\bTEST-[A-Za-z0-9-]+"),             # MP access token sandbox
    re.compile(r"\bAPP_USR-[A-Za-z0-9-]+"),          # MP access token prod
]

_MAX_LOG_FIELD_LEN = 200


def sanitize_log_string(value: Any, max_len: int = _MAX_LOG_FIELD_LEN) -> str:
    """
    Converte um valor arbitrário em string segura para log.

    Aplica truncamento + regex de dados sensíveis (CPF, CNPJ, email, tokens).
    Nunca lança: se a entrada for estranha, devolve string vazia ou truncada.
    """
    if value is None:
        return ""
    s = str(value)
    if len(s) > max_len:
        s = s[:max_len] + "…"
    for pattern in _SENSITIVE_PATTERNS:
        s = pattern.sub("<redacted>", s)
    return s


class JsonFormatter(logging.Formatter):
    """Formatter que emite cada log como uma linha JSON sanitizada."""

    # Campos string da allowlist → sanitizados (podem conter PII por acidente).
    _STRING_EXTRA_FIELDS = (
        "event",
        "request_id",
        "user_id",
        "endpoint",
        "status",
        "error",
    )

    # Campos numéricos/estruturados da allowlist → passam sem sanitização.
    # - duration_ms: int, tem que continuar int pra observabilidade.
    # - mp_error_detail: dict, sanitizado recursivamente (strings internas).
    _PASSTHROUGH_EXTRA_FIELDS = (
        "duration_ms",
        "mp_error_detail",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_log_string(record.getMessage()),
        }

        # Strings: sanitiza (podem conter CPF/email/token por acidente).
        for key in self._STRING_EXTRA_FIELDS:
            if hasattr(record, key):
                value = getattr(record, key)
                payload[key] = (
                    sanitize_log_string(value) if value is not None else None
                )

        # Numéricos/estruturados: passam direto (sem risco de PII).
        for key in self._PASSTHROUGH_EXTRA_FIELDS:
            if hasattr(record, key):
                value = getattr(record, key)
                # mp_error_detail é dict com strings internas — sanitiza
                # recursivamente (mensagem de erro do MP pode ter CPF).
                if key == "mp_error_detail" and isinstance(value, dict):
                    payload[key] = {
                        k: (
                            [sanitize_log_string(i) for i in v]
                            if isinstance(v, list)
                            else sanitize_log_string(v)
                        )
                        for k, v in value.items()
                    }
                else:
                    payload[key] = value

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