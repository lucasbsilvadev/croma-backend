from fastapi import APIRouter, Depends

from app.middleware.auth import get_current_user
from app.models.profile import MeResponse, ProfileUpdateRequest
from app.services.profile_service import ProfileService

router = APIRouter(tags=["profile"])


def get_profile_service() -> ProfileService:
    """Factory para injeção de dependência. Facilita mock nos testes."""
    return ProfileService()


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    """Retorna dados do usuário autenticado."""
    return service.get_me(current_user["user_id"], current_user["email"])


@router.patch("/me", response_model=MeResponse)
async def update_me(
    payload: ProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    """
    Atualiza o próprio perfil.

    - `nome`: sempre editável.
    - `cpf_cnpj`: só se ainda não definido. Depois de definido, 409.
    """
    return service.update_me(
        current_user["user_id"],
        current_user["email"],
        payload.model_dump(exclude_none=True),
    )