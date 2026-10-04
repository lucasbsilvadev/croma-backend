from fastapi import APIRouter, Depends

from app.models.product import ProductResponse
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["products"])


def get_product_service() -> ProductService:
    return ProductService()


@router.get("", response_model=list[ProductResponse])
async def list_products(
    service: ProductService = Depends(get_product_service),
):
    """Lista produtos ativos. Sem auth — catálogo é público."""
    return service.list_active()


@router.get("/{slug}", response_model=ProductResponse)
async def get_product(
    slug: str,
    service: ProductService = Depends(get_product_service),
):
    """Detalhe de um produto pelo slug. 404 se inativo ou inexistente."""
    return service.get_active_by_slug(slug)