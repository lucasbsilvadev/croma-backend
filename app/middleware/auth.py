import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.settings import settings
from app.repositories.profile_repository import ProfileRepository
from app.utils.exceptions import AuthError, PermissionDeniedError
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Declara o esquema de segurança pra que o Swagger mostre o botão Authorize.
# auto_error=False: deixa o get_current_user tratar o erro (401 em vez de 403).
bearer_scheme = HTTPBearer(auto_error=False)


def _get_profile_repo() -> ProfileRepository:
    """Factory separada para facilitar override em testes."""
    return ProfileRepository()


def _extract_nome_from_metadata(data: dict, email: str | None) -> str:
    """
    Deriva um nome razoável para o profile a partir do metadata do Supabase.
    Google preenche 'full_name' e 'name'; outros providers variam.
    Fallback: prefixo do email.
    """
    metadata = data.get("user_metadata") or {}
    for key in ("nome", "full_name", "name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    if email:
        return email.split("@")[0]

    return "Usuário"


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    profile_repo: ProfileRepository = Depends(_get_profile_repo),
) -> dict:
    """
    Valida o access_token do Supabase, garante que o profile existe e
    retorna os dados do user.

    Espera header: 'Authorization: Bearer <access_token>'
    Retorno: {'user_id': str, 'email': str, 'role': str}
    """
    request_id = getattr(request.state, "request_id", None)

    if not credentials:
        raise AuthError("Token ausente")

    token = credentials.credentials
    if not token:
        raise AuthError("Token vazio")

    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/user"
    headers = {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {token}",
    }

    try:
        response = httpx.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.warning(
            "Token inválido ou expirado",
            extra={"event": "AUTH_TOKEN_INVALID", "request_id": request_id},
        )
        raise AuthError("Token inválido ou expirado") from e
    except httpx.HTTPError as e:
        logger.warning(
            "Falha ao validar token",
            extra={"event": "AUTH_TOKEN_INVALID", "request_id": request_id, "error": type(e).__name__},
        )
        raise AuthError("Falha ao validar token") from e

    data = response.json()
    user_id = data.get("id")
    email = data.get("email")

    if not user_id:
        logger.warning(
            "Resposta do Supabase sem user_id",
            extra={"event": "AUTH_TOKEN_INVALID", "request_id": request_id},
        )
        raise AuthError("Token inválido")

    # Busca o profile. Se não existir, cria idempotentemente.
    # Isso cobre o caso de usuário OAuth (Google) que loga pela primeira vez:
    # o Supabase Auth cria o auth.users, mas não conhece nossa tabela profiles.
    profile = profile_repo.get_by_user_id(user_id)

    if not profile:
        nome = _extract_nome_from_metadata(data, email)
        profile = profile_repo.ensure_profile(user_id=user_id, nome=nome)

        # Se ainda veio None/erro, é problema real — não esconder.
        if not profile:
            raise AuthError("Falha ao criar perfil de usuário")

        logger.info(
            "Profile criado via OAuth/primeiro acesso",
            extra={
                "event": "AUTH_OAUTH_PROFILE_CREATED",
                "request_id": request_id,
                "user_id": user_id,
            },
        )

    return {
        "user_id": user_id,
        "email": email,
        "role": profile.get("role", "user"),
    }


async def get_current_admin_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Dependência que garante que o usuário autenticado é um admin.
    """
    if current_user.get("role") != "admin":
        raise PermissionDeniedError("Acesso restrito a administradores")
    return current_user