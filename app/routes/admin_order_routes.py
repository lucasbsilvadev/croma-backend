"""
Rotas administrativas de pedidos.
Referência: PAYMENT-23, PAYMENT-26.
"""
from fastapi import APIRouter, Depends, Query

from app.middleware.auth import get_current_admin_user
from app.models.payment import AdminOrderResponse, AdminOrderStatusUpdate
from app.repositories.order_repository import OrderRepository
from app.services.payment_service import PaymentService
from app.utils.exceptions import NotFoundError

router = APIRouter(
    prefix="/admin/orders",
    tags=["admin-orders"],
    dependencies=[Depends(get_current_admin_user)],
)


def get_payment_service() -> PaymentService:
    return PaymentService()


def get_order_repo() -> OrderRepository:
    return OrderRepository()


@router.get("", response_model=list[AdminOrderResponse])
async def list_orders(
    status: str | None = Query(default=None),
    payment_status: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repo: OrderRepository = Depends(get_order_repo),
):
    """Lista pedidos com filtros."""
    return repo.list_all(
        status=status,
        payment_status=payment_status,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{order_id}", response_model=AdminOrderResponse)
async def get_order(
    order_id: str,
    repo: OrderRepository = Depends(get_order_repo),
):
    """Detalhe do pedido pra admin."""
    order = repo.get_by_id(order_id)
    if not order:
        raise NotFoundError("Pedido não encontrado")
    items = repo.list_items_by_order(order_id)
    return {**order, "items": items}


@router.patch("/{order_id}/status", response_model=AdminOrderResponse)
async def update_status(
    order_id: str,
    payload: AdminOrderStatusUpdate,
    service: PaymentService = Depends(get_payment_service),
    repo: OrderRepository = Depends(get_order_repo),
):
    """Altera status operacional validando máquina de estados."""
    updated = service.admin_update_status(order_id, payload.status)
    items = repo.list_items_by_order(order_id)
    return {**updated, "items": items}


@router.post("/{order_id}/reconcile", response_model=AdminOrderResponse)
async def reconcile_order(
    order_id: str,
    service: PaymentService = Depends(get_payment_service),
    repo: OrderRepository = Depends(get_order_repo),
):
    """Consulta o MP e sincroniza estado financeiro."""
    order = service.reconcile(order_id)
    items = repo.list_items_by_order(order_id)
    return {**order, "items": items}