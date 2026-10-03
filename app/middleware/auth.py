import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.settings import settings
from app.utils.exceptions import AuthError

# Declara o esquema de segurança pra que o Swagger mostre o botão Authorize.
# auto_error=False: deixa o get_current_user tratar o erro (401 em vez de 403).
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """
    Valida o access_token do Supabase via Auth API e retorna os dados do user.

    Espera header: 'Authorization: Bearer <access_token>'
    Retorno: {'user_id': str, 'email': str}
    """
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
    except httpx.HTTPError as e:
        raise AuthError("Falha ao validar token") from e

    if response.status_code != 200:
        raise AuthError("Token inválido ou expirado")

    data = response.json()

    user_id = data.get("id")
    email = data.get("email")

    if not user_id:
        raise AuthError("Token inválido")

    return {"user_id": user_id, "email": email}
