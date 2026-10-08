import httpx

from app.config.settings import settings
from app.repositories.profile_repository import ProfileRepository
from app.utils.exceptions import AuthError, ValidationError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AuthService:
    """
    Regras de negócio de autenticação.
    Usa HTTP direto na Auth API do Supabase (GoTrue) em vez do SDK,
    porque o supabase-py 2.31 monta URL errada em auth.sign_up.
    """

    def __init__(self, profile_repo: ProfileRepository | None = None):
        self.profile_repo = profile_repo or ProfileRepository()

    def register(self, nome: str, email: str, password: str, cpf_cnpj: str) -> dict:
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
                logger.info(
                    "Register falhou: email duplicado",
                    extra={"event": "AUTH_REGISTER_FAILED", "error": "duplicate_email"},
                )
                raise ValidationError("Email já cadastrado")

            logger.warning(
                "Register falhou: erro do Supabase",
                extra={
                    "event": "AUTH_REGISTER_FAILED",
                    "error": f"supabase_{response.status_code}",
                },
            )
            raise ValidationError(msg)

        data = response.json()

        # Supabase muda o shape da resposta conforme 'Confirm email':
        #   OFF: {"user": {...}, "access_token": ..., "refresh_token": ...}
        #   ON:  {"id": ..., "email": ..., "confirmation_sent_at": ...}
        # O objeto do user está em data["user"] OU no top-level.
        user = data.get("user") or data

        if not user.get("id"):
            logger.warning(
                "Register falhou: resposta sem user_id",
                extra={"event": "AUTH_REGISTER_FAILED", "error": "missing_user_id"},
            )
            raise ValidationError("Falha ao criar conta")

        user_id = user["id"]

        # Cria profile idempotentemente. Se um trigger já criou, retorna o existente.
        # Se deu FK race (23503), tenta de novo dentro do ensure_profile.
        self.profile_repo.ensure_profile(
            user_id=user_id, nome=nome, cpf_cnpj=cpf_cnpj
        )

        logger.info(
            "Register bem-sucedido",
            extra={"event": "AUTH_REGISTER_SUCCESS", "user_id": user_id},
        )

        return {
            "user_id": user_id,
            "access_token": data.get("access_token") or "",
            "refresh_token": data.get("refresh_token") or "",
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
            # Nunca logar email nem password. Evento genérico é suficiente.
            logger.warning(
                "Login falhou",
                extra={"event": "AUTH_LOGIN_FAILED"},
            )
            raise AuthError("Email ou senha inválidos")

        data = response.json()

        if not data.get("access_token"):
            logger.warning(
                "Login sem token (email não confirmado?)",
                extra={
                    "event": "AUTH_LOGIN_FAILED",
                    "user_id": (data.get("user") or {}).get("id"),
                },
            )
            raise AuthError("Email não confirmado")

        user_id = data["user"]["id"]
        logger.info(
            "Login bem-sucedido",
            extra={"event": "AUTH_LOGIN_SUCCESS", "user_id": user_id},
        )

        return {
            "user_id": user_id,
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
            logger.info(
                "Forgot password solicitado",
                extra={"event": "AUTH_FORGOT_PASSWORD_REQUESTED"},
            )
        except Exception as e:
            # Nunca vazar se o email existe. Log interno registra a falha técnica.
            logger.warning(
                "Forgot password falhou (silencioso para o cliente)",
                extra={"event": "AUTH_FORGOT_PASSWORD_FAILED", "error": type(e).__name__},
            )
            # Não re-raise: resposta pública continua genérica.