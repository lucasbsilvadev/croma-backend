import httpx

from app.config.settings import settings
from app.repositories.profile_repository import ProfileRepository
from app.utils.exceptions import AuthError, ConflictError, ValidationError


class AuthService:
    """
    Regras de negócio de autenticação.
    Usa HTTP direto na Auth API do Supabase (GoTrue) em vez do SDK,
    porque o supabase-py 2.31 monta URL errada em auth.sign_up.
    """

    def __init__(self, profile_repo: ProfileRepository | None = None):
        self.profile_repo = profile_repo or ProfileRepository()

    def register(self, nome: str, email: str, password: str) -> dict:
        url = f"{settings.supabase_url.rstrip('/')}/auth/v1/signup"
        headers = {
            "apikey": settings.supabase_anon_key,
            "Content-Type": "application/json",
        }
        payload = {
            "email": email,
            "password": password,
            "data": {"nome": nome},
        }

        response = httpx.post(url, headers=headers, json=payload, timeout=15)

        if response.status_code >= 400:
            body = response.json() if response.content else {}
            msg = body.get("msg") or body.get("error_description") or "Falha ao criar conta"
            if "already" in msg.lower() or "registered" in msg.lower():
                raise ValidationError("Email já cadastrado")
            raise ValidationError(msg)

        data = response.json()

        if not data.get("id"):
            raise ValidationError("Falha ao criar conta")

        try:
            self.profile_repo.create(user_id=data["id"], nome=nome)
        except ConflictError:
            pass

        return {
            "user_id": data["id"],
            "access_token": data.get("access_token", ""),
            "refresh_token": data.get("refresh_token", ""),
        }

    def login(self, email: str, password: str) -> dict:
        url = f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password"
        headers = {
            "apikey": settings.supabase_anon_key,
            "Content-Type": "application/json",
        }
        payload = {"email": email, "password": password}

        response = httpx.post(url, headers=headers, json=payload, timeout=15)

        if response.status_code >= 400:
            raise AuthError("Email ou senha inválidos")

        data = response.json()

        if not data.get("access_token"):
            raise AuthError("Email não confirmado")

        return {
            "user_id": data["user"]["id"],
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
        }

    def forgot_password(self, email: str) -> None:
        url = f"{settings.supabase_url.rstrip('/')}/auth/v1/recover"
        headers = {
            "apikey": settings.supabase_anon_key,
            "Content-Type": "application/json",
        }
        try:
            httpx.post(url, headers=headers, json={"email": email}, timeout=15)
        except Exception:
            pass