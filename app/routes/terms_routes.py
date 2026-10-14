"""
Rotas públicas de termos de uso.
Referência: LGPD-01.
"""
from fastapi import APIRouter, Depends

from app.models.terms import TermsCurrentResponse
from app.services.terms_service import TermsService

router = APIRouter(prefix="/terms", tags=["terms"])


def get_terms_service() -> TermsService:
    """Factory para injeção de dependência. Facilita mock nos testes."""
    return TermsService()


@router.get("/current", response_model=TermsCurrentResponse)
async def get_current_terms(
    service: TermsService = Depends(get_terms_service),
):
    """
    Retorna a versão vigente dos termos.
    Público — o front consome antes do cadastro.
    """
    return service.get_current()