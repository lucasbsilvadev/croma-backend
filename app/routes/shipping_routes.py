from fastapi import APIRouter, Depends

from app.models.shipping import ShippingQuoteRequest, ShippingQuoteResponse
from app.services.shipping_service import ShippingService

router = APIRouter(prefix="/shipping", tags=["shipping"])


def get_shipping_service() -> ShippingService:
    return ShippingService()


@router.post("/quote", response_model=ShippingQuoteResponse)
async def quote_shipping(
    payload: ShippingQuoteRequest,
    service: ShippingService = Depends(get_shipping_service),
):
    """Consulta frete pelo CEP. Sem auth — cliente consulta antes de logar."""
    return service.quote(payload.cep)