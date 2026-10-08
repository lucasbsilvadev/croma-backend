"""
Rotas de pagamento do cliente.
Referência: PAYMENT-22, PAYMENT-26.
"""
from fastapi import APIRouter, Depends, Header, status

from app.middleware.auth import get_current_user
from app.models.payment import CardPaymentResponse, PixPaymentResponse
from app.services.payment_service import PaymentService
from app.utils.exceptions import ValidationError

router = APIRouter(prefix="/orders", tags=["payments"])


def get_payment_service() -> PaymentService:
    return PaymentService()


def _validate_idempotency_key(key: str | None) -> str:
    """Valida formato UUID v4 no boundary HTTP (PAYMENT-13)."""
    if not key:
        raise ValidationError("Header Idempotency-Key é obrigatório")
    # Validação simples de formato UUID
    import uuid as _uuid
    try:
        _uuid.UUID(key)
    except ValueError:
        raise ValidationError("Idempotency-Key deve ser um UUID")
    return key


@router.post(
    "/{order_id}/pay/pix",
    response_model=PixPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def pay_with_pix(
    order_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: dict = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """Cria cobrança PIX. Retorna QR code."""
    _validate_idempotency_key(idempotency_key)
    return service.create_pix(
        user_id=current_user["user_id"],
        user_email=current_user["email"],
        order_id=order_id,
    )


@router.post(
    "/{order_id}/pay/card",
    response_model=CardPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def pay_with_card(
    order_id: str,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: dict = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """Cria preferência do Checkout Pro. Retorna init_point."""
    _validate_idempotency_key(idempotency_key)
    return service.create_card_preference(
        user_id=current_user["user_id"],
        user_email=current_user["email"],
        order_id=order_id,
    )