from fastapi import APIRouter, Depends, Request

from app.middleware.rate_limit import RATE_LIMITS, limiter
from app.models.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service() -> AuthService:
    """Factory para injeção de dependência. Facilita mock nos testes."""
    return AuthService()


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit(RATE_LIMITS["register"])
async def register(
    request: Request,
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
):
    """Cria conta. Retorna tokens se confirmação de email estiver desligada."""
    return service.register(payload.nome, payload.email, payload.password)


@router.post("/login", response_model=AuthResponse)
@limiter.limit(RATE_LIMITS["login"])
async def login(
    request: Request,
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    """Autentica e retorna access + refresh token."""
    return service.login(payload.email, payload.password)


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit(RATE_LIMITS["forgot_password"])
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    service: AuthService = Depends(get_auth_service),
):
    """Dispara email de recuperação. Sempre retorna a mesma mensagem."""
    service.forgot_password(payload.email)
    return {"message": "Se o email existir, enviaremos instruções"}