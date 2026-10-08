"""
Webhook público do Mercado Pago.
Referência: PAYMENT-04 a PAYMENT-08, PAYMENT-32.
"""
import json

from fastapi import APIRouter, Depends, Request

from app.infra.mp_client import MPClient
from app.services.payment_service import PaymentService
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_payment_service() -> PaymentService:
    return PaymentService()


def get_mp_client() -> MPClient:
    return MPClient()


@router.post("/mercadopago")
async def mercadopago_webhook(
    request: Request,
    service: PaymentService = Depends(get_payment_service),
    mp: MPClient = Depends(get_mp_client),
):
    """
    Recebe webhook do MP. Autenticação é HMAC, não JWT.

    Passos:
    1. Lê body cru (auditoria) + headers + query
    2. Valida assinatura (MPClient) — 401 se inválida
    3. Extrai tipo do evento e IDs
    4. Delega pro PaymentService (persiste + processa)
    """
    raw_body = await request.body()

    x_signature = request.headers.get("x-signature") or ""
    x_request_id = request.headers.get("x-request-id") or ""

    # `data.id` chega no QUERY STRING (formato oficial do MP)
    data_id = request.query_params.get("data.id") or ""

    # Fallback: alguns formatos antigos mandam só no body
    if not data_id:
        try:
            body_for_id = json.loads(raw_body.decode("utf-8") or "{}")
            data_id = str((body_for_id.get("data") or {}).get("id") or "")
        except Exception:
            data_id = ""

    # 1. Valida assinatura ANTES de qualquer coisa
    mp.verify_webhook_signature(
        data_id=data_id,
        x_request_id=x_request_id,
        x_signature=x_signature,
    )

    # 2. Parse do body (pra extrair tipo e ids)
    try:
        body = json.loads(raw_body.decode("utf-8") or "{}")
    except Exception:
        body = {}

    event_type = body.get("type") or body.get("topic") or "unknown"
    external_resource_id = (
        str((body.get("data") or {}).get("id") or body.get("id") or data_id) or None
    )

    # external_event_id é o que garante idempotência via unique constraint.
    # MP manda `id` no body OU usamos x-request-id como fallback.
    external_event_id = str(
        body.get("id")
        or request.headers.get("x-request-id")
        or data_id
    )

    logger.info(
        "Webhook recebido",
        extra={"event": "PAYMENT_WEBHOOK_RECEIVED"},
    )

    service.process_webhook(
        event_type=event_type,
        external_event_id=external_event_id,
        external_resource_id=external_resource_id,
        payload=body,
    )

    return {"received": True}