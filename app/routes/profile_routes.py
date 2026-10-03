from fastapi import APIRouter, Depends

from app.middleware.auth import get_current_user
from app.models.profile import MeResponse
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
