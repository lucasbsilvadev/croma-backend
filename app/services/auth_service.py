from app.config.supabase import supabase_admin, supabase_public
from app.repositories.profile_repository import ProfileRepository
from app.utils.exceptions import AuthError, ConflictError, ValidationError


class AuthService:
    """
    Regras de negócio de autenticação.
    Não conhece FastAPI. Não conhece SQL. Só orquestra.
    """

    def __init__(self, profile_repo: ProfileRepository | None = None):
        self.profile_repo = profile_repo or ProfileRepository()

    def register(self, nome: str, email: str, password: str) -> dict:
        try:
            res = supabase_admin.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {"data": {"nome": nome}},
                }
            )
        except Exception as e:
            msg = str(e).lower()
            if "already" in msg or "registered" in msg:
                raise ValidationError("Email já cadastrado") from e
            raise ValidationError("Falha ao criar conta") from e

        if not res.user:
            raise ValidationError("Falha ao criar conta")

        # Garante profile (caso não exista trigger no Supabase).
        # Se já existir (trigger rodou), ignora silenciosamente.
        try:
            self.profile_repo.create(user_id=res.user.id, nome=nome)
        except ConflictError:
            pass

        return {
            "user_id": res.user.id,
            "access_token": res.session.access_token if res.session else "",
            "refresh_token": res.session.refresh_token if res.session else "",
        }

    def login(self, email: str, password: str) -> dict:
        try:
            res = supabase_public.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
        except Exception as e:
            raise AuthError("Email ou senha inválidos") from e

        if not res.session:
            raise AuthError("Email não confirmado")

        return {
            "user_id": res.user.id,
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token,
        }

    def forgot_password(self, email: str) -> None:
        """
        Nunca revela se o email existe (anti user-enumeration).
        Nunca lança erro pro cliente.
        """
        try:
            supabase_public.auth.reset_password_email(email)
        except Exception:
            pass