from fastapi import APIRouter, Depends, status

from app.middleware.auth import get_current_admin_user
from app.models.product import (
    ProductCreateRequest,
    ProductImageCreateRequest,
    ProductImageResponse,
    ProductResponse,
    ProductUpdateRequest,
)
from app.services.product_service import ProductService

router = APIRouter(
    prefix="/admin/products",
    tags=["admin-products"],
    dependencies=[Depends(get_current_admin_user)],
)


def get_product_service() -> ProductService:
    return ProductService()


@router.get("", response_model=list[ProductResponse])
async def list_all_products(
    service: ProductService = Depends(get_product_service),
):
    """Lista TODOS os produtos, incluindo inativos."""
    return service.list_all()


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateRequest,
    service: ProductService = Depends(get_product_service),
):
    """Cria produto."""
    return service.create_product(payload.model_dump())


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    payload: ProductUpdateRequest,
    service: ProductService = Depends(get_product_service),
):
    """Atualização parcial."""
    return service.update_product(product_id, payload.model_dump())


@router.delete("/{product_id}", response_model=ProductResponse)
async def soft_delete_product(
    product_id: str,
    service: ProductService = Depends(get_product_service),
):
    """Soft delete: marca ativo=false. Produto continua no banco."""
    return service.soft_delete(product_id)


@router.post(
    "/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_product_image(
    product_id: str,
    payload: ProductImageCreateRequest,
    service: ProductService = Depends(get_product_service),
):
    """Adiciona URL de imagem ao produto."""
    return service.add_image(product_id, payload.url, payload.position)


@router.delete("/{product_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_product_image(
    product_id: str,
    image_id: str,
    service: ProductService = Depends(get_product_service),
):
    """Remove imagem do produto."""
    service.remove_image(product_id, image_id)