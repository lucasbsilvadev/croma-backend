"""
Cliente HTTP do Mercado Pago.

Responsabilidade ÚNICA: encapsular comunicação com a API do MP.
Não contém regra de negócio de pedido (isso é do PaymentService).

Referência: PAYMENT-06, PAYMENT-28.
"""
import hashlib
import hmac
import re
import uuid
from typing import Any

import httpx

from app.config.settings import settings
from app.utils.exceptions import InvalidSignatureError, PaymentError
from app.utils.logging import get_logger

logger = get_logger(__name__)

MP_BASE_URL_PROD = "https://api.mercadopago.com"
MP_BASE_URL_SANDBOX = "https://api.mercadopago.com"  # MP usa a mesma base; credencial define o ambiente


# ============================================================
# Sanitização de log (defesa em profundidade)
# ============================================================
#
# Aplicada ao corpo de erro do MP antes de virar log.
# Mesmo com o gate dev+sandbox, ainda passamos por aqui —
# porque o MP às vezes ecoa `payer.identification.number`
# dentro de `cause[].description`.
#
# Estes regex são deliberadamente conservadores: preferem
# redigir demais a deixar passar. Nunca são usados para
# ler secrets — secrets não são lidos em nenhum ponto deste
# módulo (access_token não é logado).

_SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{11}\b"),                       # CPF (11 dígitos)
    re.compile(r"\b\d{14}\b"),                       # CNPJ (14 dígitos)
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),     # email
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),       # Authorization Bearer
    re.compile(r"\bTEST-[A-Za-z0-9-]+"),             # MP access token sandbox
    re.compile(r"\bAPP_USR-[A-Za-z0-9-]+"),          # MP access token prod
]

_MAX_LOG_FIELD_LEN = 200


def _sanitize_log_string(value: Any, max_len: int = _MAX_LOG_FIELD_LEN) -> str:
    """
    Converte um valor arbitrário em string segura para log.

    - None vira string vazia.
    - Trunca em `max_len` com reticências.
    - Substitui padrões sensíveis por '<redacted>'.

    Nunca é usada sobre secrets — esses não são lidos.
    """
    if value is None:
        return ""
    s = str(value)
    if len(s) > max_len:
        s = s[:max_len] + "…"
    for pattern in _SENSITIVE_PATTERNS:
        s = pattern.sub("<redacted>", s)
    return s


def _should_log_mp_error_detail() -> bool:
    """
    Gate de segurança: detalhe do erro do MP só é logado em dev + sandbox.

    Fora desse cenário, o comportamento permanece genérico
    (apenas `status`), e o corpo do erro nem sequer é lido.
    """
    return settings.env == "dev" and settings.mp_env == "sandbox"


class MPClient:
    """Encapsula chamadas HTTP ao Mercado Pago."""

    def __init__(self, access_token: str | None = None, timeout: float = 15.0):
        self.access_token = access_token or settings.mp_access_token
        self.timeout = timeout
        self.base_url = MP_BASE_URL_SANDBOX if settings.is_mp_sandbox else MP_BASE_URL_PROD

        # Diagnóstico seguro do runtime.
        # Registra apenas presença/prefixo/comprimento — nunca o valor.
        # Também atrás do gate dev+sandbox.
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
        """
        Extrai um dict sanitizado do corpo de erro do MP.

        Retorna None se o corpo não for JSON parseável ou não tiver
        shape reconhecível. O chamador só invoca quando o gate
        dev+sandbox passa.

        Campos extraídos (todos sanitizados individualmente):
          - status: int HTTP
          - mp_request_id: header x-request-id do MP (correlação técnica)
          - error: campo `error` do body, quando string
          - message: campo `message` do body, quando string
          - cause_codes: lista de `cause[].code`
          - cause_descriptions: lista de `cause[].description`
        """
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
            # Log base: sempre. `status` não é sensível.
            extra: dict[str, Any] = {
                "event": "MP_REQUEST_FAILED",
                "status": response.status_code,
            }

            # Detalhe do erro: SOMENTE em dev + sandbox.
            # Em produção, `_extract_mp_error_detail` nem é chamado —
            # o corpo do erro não é lido nem processado.
            if _should_log_mp_error_detail():
                detail = self._extract_mp_error_detail(response)
                if detail is not None:
                    extra["mp_error_detail"] = detail

            logger.warning("MP retornou erro", extra=extra)

            # Cliente da API continua recebendo 502 genérico.
            # Detalhe real fica só no log interno (dev+sandbox).
            raise PaymentError(
                "Mercado Pago rejeitou a operação",
                status_code=502,
            )

        return response.json()

    # ============================================================
    # Pagamentos
    # ============================================================

    def create_pix_payment(self, payload: dict, idempotency_key: str) -> dict:
        """
        POST /v1/payments com payment_method_id=pix.

        Retorna o objeto do pagamento com:
          - id
          - point_of_interaction.transaction_data.qr_code
          - point_of_interaction.transaction_data.qr_code_base64
          - point_of_interaction.transaction_data.ticket_url
        """
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
        """
        POST /checkout/preferences.

        Retorna:
          - id (preference_id)
          - init_point
          - sandbox_init_point
        """
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
        """
        Valida a assinatura HMAC do webhook do Mercado Pago.

        Formato do header x-signature:
            ts=<timestamp>,v1=<hmac_sha256_hex>

        Manifest assinado (formato oficial do MP):
            id:<data_id>;request-id:<x_request_id>;ts:<ts>;

        `data_id` deve vir do QUERY STRING (?data.id=...) da request,
        não do body — o MP assina o valor que veio na URL.

        Levanta InvalidSignatureError se inválida.
        Nunca loga o secret nem o payload.
        """
        secret = secret or settings.mp_webhook_secret

        if not x_signature:
            logger.warning(
                "Webhook sem x-signature",
                extra={"event": "PAYMENT_WEBHOOK_INVALID_SIGNATURE"},
            )
            raise InvalidSignatureError()

        # Parse do header: "ts=...,v1=..."
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