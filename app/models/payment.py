"""
Contratos HTTP do módulo de pagamento.
Referência: PAYMENT-22, PAYMENT-31.
"""
from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================
# PIX
# ============================================================


class PixPaymentResponse(BaseModel):
    """Resposta de POST /orders/{id}/pay/pix."""

    payment_id: str
    status: str                # 'pending', 'approved', ...
    qr_code: str | None
    qr_code_base64: str | None
    ticket_url: str | None
    expires_at: datetime | None = None


# ============================================================
# Cartão (Checkout Pro)
# ============================================================


class CardPaymentResponse(BaseModel):
    """Resposta de POST /orders/{id}/pay/card."""

    preference_id: str
    init_point: str            # URL pro front redirecionar
    sandbox_init_point: str | None = None


# ============================================================
# Webhook
# ============================================================


class WebhookResponse(BaseModel):
    """Resposta padrão do webhook (200 OK)."""

    received: bool = True


# ============================================================
# Admin
# ============================================================


class AdminOrderStatusUpdate(BaseModel):
    """Body de PATCH /admin/orders/{id}/status."""

    status: str = Field(
        pattern="^(created|paid|production|shipped|delivered|cancelled)$"
    )


class AdminOrderResponse(BaseModel):
    """
    Pedido visto por admin — inclui campos operacionais.
    Reutiliza o shape do OrderResponse + address_snapshot.
    """
    id: str
    user_id: str
    address_id: str | None
    address_snapshot: dict | None = None
    status: str
    subtotal: str
    frete: str
    total: str
    notes: str | None
    payment_status: str
    payment_method: str | None
    payment_external_id: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[dict] = []