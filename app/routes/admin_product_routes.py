from fastapi import APIRouter, Depends, File, Form, UploadFile, status

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


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    service: ProductService = Depends(get_product_service),
):
    """Detalhe de um produto (admin). Inclui inativos."""
    return service.get_by_id_any_status(product_id)


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


# ============================================================
# Imagens
# ============================================================


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
    """
    Associa uma URL de imagem já existente ao produto.

    Útil para reimportar catálogo, seeds, ou quando a imagem já mora
    em outro lugar. Para upload de arquivo, use
    POST /{product_id}/images/upload.
    """
    return service.add_image(product_id, payload.url, payload.position)


@router.post(
    "/{product_id}/images/upload",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_product_image(
    product_id: str,
    file: UploadFile = File(...),
    position: int = Form(...),
    service: ProductService = Depends(get_product_service),
):
    """
    Faz upload de uma imagem pro storage e associa ao produto.

    Diferença pra `POST /{product_id}/images`: aquele aceita uma URL
    já existente; este aceita o arquivo (multipart/form-data) e faz
    o upload. Ambos terminam gravando em product_images.
    """
    content = await file.read()
    return service.add_image_from_upload(
        product_id=product_id,
        file_bytes=content,
        content_type=file.content_type or "",
        position=position,
    )


@router.delete(
    "/{product_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_product_image(
    product_id: str,
    image_id: str,
    service: ProductService = Depends(get_product_service),
):
    """Remove imagem do produto."""
    service.remove_image(product_id, image_id)