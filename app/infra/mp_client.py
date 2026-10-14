"""
Cliente HTTP do Mercado Pago.

Responsabilidade ÚNICA: encapsular comunicação com a API do MP.
Não contém regra de negócio de pedido (isso é do PaymentService).

Referência: PAYMENT-06, PAYMENT-28.
"""
import hashlib
import hmac
import uuid
from typing import Any

import httpx

from app.config.settings import settings
from app.utils.exceptions import InvalidSignatureError, PaymentError
from app.utils.logging import get_logger, sanitize_log_string

logger = get_logger(__name__)

MP_BASE_URL_PROD = "https://api.mercadopago.com"
MP_BASE_URL_SANDBOX = "https://api.mercadopago.com"  # MP usa a mesma base; credencial define o ambiente


# Alias local: mantém o nome antigo pra não quebrar chamadas internas.
# A implementação real vive em app/utils/logging.py (LGPD-09/10).
_sanitize_log_string = sanitize_log_string


def _should_log_mp_error_detail() -> bool:
    """
    Habilita log detalhado do erro do MP quando MP_DEBUG_ERRORS=true.

    Independente de MP_ENV — assim dá pra debugar 401 em produção
    sem trocar ambiente. A sanitização de CPF/email/token continua
    sendo aplicada antes de qualquer coisa sair no log.
    """
    return settings.mp_debug_errors


class MPClient:
    """Encapsula chamadas HTTP ao Mercado Pago."""

    def __init__(self, access_token: str | None = None, timeout: float = 15.0):
        self.access_token = access_token or settings.mp_access_token
        self.timeout = timeout
        self.base_url = MP_BASE_URL_SANDBOX if settings.is_mp_sandbox else MP_BASE_URL_PROD

        # Diagnóstico seguro do runtime.
        # Registra apenas presença/prefixo/comprimento — nunca o valor.
        if _should_log_mp_error_detail():
            logger.debug(
                "MPClient inicializado",
                extra={
                    "event": "MP_CLIENT_INIT",
                    "mp_env": settings.mp_env,
                    "access_token_present": bool(self.access_token),
                    "access_token_prefix": (
                        self.access_token[:8] if self.access_token else ""
                    ),
                    "access_token_length": (
                        len(self.access_token) if self.access_token else 0
                    ),
                },
            )

    # ============================================================
    # Helpers internos
    # ============================================================

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        return headers

    @staticmethod
    def _extract_mp_error_detail(response: httpx.Response) -> dict | None:
        """Extrai dict sanitizado do corpo de erro do MP."""
        try:
            body = response.json()
        except Exception:
            return None

        if not isinstance(body, dict):
            return None

        cause_codes: list[str] = []
        cause_descriptions: list[str] = []
        cause = body.get("cause")
        if isinstance(cause, list):
            for item in cause:
                if not isinstance(item, dict):
                    continue
                code = item.get("code")
                if code is not None:
                    cause_codes.append(_sanitize_log_string(code, 50))
                desc = item.get("description")
                if desc is not None:
                    cause_descriptions.append(_sanitize_log_string(desc, 200))

        return {
            "status": response.status_code,
            "mp_request_id": _sanitize_log_string(
                response.headers.get("x-request-id"), 100
            ),
            "error": _sanitize_log_string(body.get("error"), 100),
            "message": _sanitize_log_string(body.get("message"), 200),
            "cause_codes": cause_codes,
            "cause_descriptions": cause_descriptions,
        }

    def _request(self, method: str, path: str, *,
                 json: dict | None = None,
                 idempotency_key: str | None = None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.request(
                method, url,
                headers=self._headers(idempotency_key),
                json=json,
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            logger.warning(
                "MP request falhou (rede)",
                extra={"event": "MP_REQUEST_FAILED", "error": type(e).__name__},
            )
            raise PaymentError("Falha de comunicação com o Mercado Pago",
                               status_code=502) from e

        if response.status_code >= 400:
            extra: dict[str, Any] = {
                "event": "MP_REQUEST_FAILED",
                "status": response.status_code,
            }

            # Detalhe do erro: controlado por MP_DEBUG_ERRORS.
            # Independente de MP_ENV — útil pra debugar 401 em prod.
            if _should_log_mp_error_detail():
                detail = self._extract_mp_error_detail(response)
                if detail is not None:
                    extra["mp_error_detail"] = detail

            logger.warning("MP retornou erro", extra=extra)

            raise PaymentError(
                "Mercado Pago rejeitou a operação",
                status_code=502,
            )

        return response.json()

    # ============================================================
    # Pagamentos
    # ============================================================

    def create_pix_payment(self, payload: dict, idempotency_key: str) -> dict:
        """POST /v1/payments com payment_method_id=pix."""
        return self._request(
            "POST", "/v1/payments",
            json=payload,
            idempotency_key=idempotency_key,
        )

    def get_payment(self, payment_id: str) -> dict:
        """GET /v1/payments/{id}. Fonte de verdade financeira."""
        return self._request("GET", f"/v1/payments/{payment_id}")

    # ============================================================
    # Checkout Pro (cartão)
    # ============================================================

    def create_card_preference(self, payload: dict, idempotency_key: str) -> dict:
        """POST /checkout/preferences."""
        return self._request(
            "POST", "/checkout/preferences",
            json=payload,
            idempotency_key=idempotency_key,
        )

    def get_merchant_order(self, merchant_order_id: str) -> dict:
        """GET /merchant_orders/{id}."""
        return self._request("GET", f"/merchant_orders/{merchant_order_id}")

    # ============================================================
    # Webhook signature (PAYMENT-06)
    # ============================================================

    @staticmethod
    def verify_webhook_signature(
        data_id: str,
        x_request_id: str,
        x_signature: str,
        secret: str | None = None,
    ) -> None:
        """Valida a assinatura HMAC do webhook do Mercado Pago."""
        secret = secret or settings.mp_webhook_secret

        if not x_signature:
            logger.warning(
                "Webhook sem x-signature",
                extra={"event": "PAYMENT_WEBHOOK_INVALID_SIGNATURE"},
            )
            raise InvalidSignatureError()

        parts: dict[str, str] = {}
        for chunk in x_signature.split(","):
            if "=" in chunk:
                k, _, v = chunk.partition("=")
                parts[k.strip()] = v.strip()

        ts = parts.get("ts")
        v1 = parts.get("v1")

        if not ts or not v1:
            logger.warning(
                "Webhook x-signature malformado",
                extra={"event": "PAYMENT_WEBHOOK_INVALID_SIGNATURE"},
            )
            raise InvalidSignatureError()

        manifest = f"id:{data_id};request-id:{x_request_id or ''};ts:{ts};"

        expected = hmac.new(
            secret.encode("utf-8"),
            manifest.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, v1):
            logger.warning(
                "Webhook assinatura não confere",
                extra={"event": "PAYMENT_WEBHOOK_INVALID_SIGNATURE"},
            )
            raise InvalidSignatureError()

    # ============================================================
    # Helper: gerar chave de idempotência
    # ============================================================

    @staticmethod
    def new_idempotency_key() -> str:
        return str(uuid.uuid4())