from app.repositories.profile_repository import ProfileRepository
from app.utils.exceptions import NotFoundError


class ProfileService:
    """
    Regras de negócio relacionadas a profile.
    """

    def __init__(self, profile_repo: ProfileRepository | None = None):
        self.profile_repo = profile_repo or ProfileRepository()

    def get_me(self, user_id: str, email: str) -> dict:
        """
        Retorna dados do user logado (profile + email do auth + role).
        """
        profile = self.profile_repo.get_by_user_id(user_id)

        if not profile:
            raise NotFoundError("Perfil não encontrado")

        return {
            "user_id": user_id,
            "email": email,
            "nome": profile["nome"],
            "role": profile.get("role", "user"),
            "cpf_cnpj": profile.get("cpf_cnpj"),
            "tipo_pessoa": profile.get("tipo_pessoa"),
        }