from fastapi import APIRouter, Depends, status

from app.middleware.auth import get_current_user
from app.models.order import OrderCreateRequest, OrderResponse
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


def get_order_service() -> OrderService:
    return OrderService()


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreateRequest,
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """Cria um pedido. Valida endereço, estoque, calcula frete."""
    return service.create(current_user["user_id"], payload.model_dump())


@router.get("", response_model=list[OrderResponse])
async def list_my_orders(
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """Lista meus pedidos. Cliente só vê os dele."""
    return service.list_my(current_user["user_id"])


@router.get("/{order_id}", response_model=OrderResponse)
async def get_my_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """Ver um pedido específico. 404 se não for meu."""
    return service.get_one(current_user["user_id"], order_id)