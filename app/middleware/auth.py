import httpx
from fastapi import Header

from app.config.settings import settings
from app.utils.exceptions import AuthError


async def get_current_user(authorization: str | None = Header(None)) -> dict:
    """
    Valida o access_token do Supabase via Auth API e retorna os dados do user.

    Header esperado: 'Authorization: Bearer <access_token>'
    Retorno: {'user_id': str, 'email': str}
    """
    if not authorization:
        raise AuthError("Token ausente")

    if not authorization.startswith("Bearer "):
        raise AuthError("Token malformado")

    token = authorization.removeprefix("Bearer ").strip()

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