from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class OrderItemRequest(BaseModel):
    """Item individual do pedido."""

    product_id: str
    quantidade: int = Field(gt=0)


class OrderCreateRequest(BaseModel):
    """Payload de criação de pedido."""

    address_id: str
    items: list[OrderItemRequest] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("items")
    @classmethod
    def no_duplicate_products(cls, v: list[OrderItemRequest]) -> list[OrderItemRequest]:
        """Não aceita o mesmo produto duas vezes. Front deve somar quantidades."""
        ids = [i.product_id for i in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Produto duplicado no pedido. Some as quantidades.")
        return v


class OrderItemResponse(BaseModel):
    """Item do pedido exposto pela API."""

    id: str
    product_id: str
    product_nome: str
    product_slug: str
    quantidade: int
    preco_unitario: str       # Decimal como string


class OrderResponse(BaseModel):
    """Pedido exposto pela API."""

    id: str
    user_id: str
    address_id: str | None
    status: str
    subtotal: str             # Decimal como string
    frete: str
    total: str
    notes: str | None
    payment_status: str
    payment_method: str | None
    created_at: datetime
    updated_at: datetime
    address_snapshot: dict | None = None
    items: list[OrderItemResponse] = []

    @field_validator("subtotal", "frete", "total", mode="before")
    @classmethod
    def decimal_to_str(cls, v):
        """Converte Decimal/float/str pra string com 2 casas."""
        if isinstance(v, Decimal):
            return f"{v:.2f}"
        if isinstance(v, (int, float)):
            return f"{Decimal(str(v)):.2f}"
        if isinstance(v, str):
            return f"{Decimal(v):.2f}"
        return v

    @field_validator("items", mode="before")
    @classmethod
    def items_decimal_to_str(cls, v):
        """Converte preco_unitario de cada item pra string."""
        if isinstance(v, list):
            return [
                {
                    **item,
                    "preco_unitario": (
                        f"{item['preco_unitario']:.2f}"
                        if isinstance(item.get("preco_unitario"), Decimal)
                        else f"{Decimal(str(item.get('preco_unitario'))):.2f}"
                    ),
                }
                for item in v
            ]
        return v