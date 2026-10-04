from fastapi import APIRouter, Depends, status

from app.middleware.auth import get_current_user
from app.models.address import (
    AddressCreateRequest,
    AddressResponse,
    AddressUpdateRequest,
)
from app.services.address_service import AddressService

router = APIRouter(prefix="/addresses", tags=["addresses"])


def get_address_service() -> AddressService:
    return AddressService()


@router.post("", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(
    payload: AddressCreateRequest,
    current_user: dict = Depends(get_current_user),
    service: AddressService = Depends(get_address_service),
):
    """Cria um novo endereço/ponto de entrega. O primeiro vira principal."""
    return service.create(current_user["user_id"], payload.model_dump())


@router.get("", response_model=list[AddressResponse])
async def list_addresses(
    current_user: dict = Depends(get_current_user),
    service: AddressService = Depends(get_address_service),
):
    """Lista meus endereços. Principal vem primeiro."""
    return service.list_my(current_user["user_id"])


@router.get("/{address_id}", response_model=AddressResponse)
async def get_address(
    address_id: str,
    current_user: dict = Depends(get_current_user),
    service: AddressService = Depends(get_address_service),
):
    """Ver um endereço específico. 404 se não for meu."""
    return service.get_one(current_user["user_id"], address_id)


@router.patch("/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: str,
    payload: AddressUpdateRequest,
    current_user: dict = Depends(get_current_user),
    service: AddressService = Depends(get_address_service),
):
    """Atualização parcial. 404 se não for meu."""
    return service.update(current_user["user_id"], address_id, payload.model_dump())


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: str,
    current_user: dict = Depends(get_current_user),
    service: AddressService = Depends(get_address_service),
):
    """Deleta um endereço. Se era principal, promove o mais antigo."""
    service.delete(current_user["user_id"], address_id)