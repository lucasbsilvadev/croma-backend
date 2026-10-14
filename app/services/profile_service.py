from app.repositories.profile_repository import ProfileRepository
from app.repositories.terms_repository import TermsRepository
from app.utils.exceptions import ConflictError, NotFoundError
from app.utils.logging import get_logger
from app.utils.validators import derive_tipo_pessoa

logger = get_logger(__name__)


class ProfileService:
    """
    Regras de negócio relacionadas a profile.
    """

    def __init__(
        self,
        profile_repo: ProfileRepository | None = None,
        terms_repo: TermsRepository | None = None,
    ):
        self.profile_repo = profile_repo or ProfileRepository()
        self.terms_repo = terms_repo or TermsRepository()

    def get_me(self, user_id: str, email: str) -> dict:
        """
        Retorna dados do user logado (profile + email do auth + role + aceite).
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        if not profile:
            raise NotFoundError("Perfil não encontrado")

        latest_terms = self.terms_repo.get_latest_for_user(user_id)

        return {
            "user_id": user_id,
            "email": email,
            "nome": profile["nome"],
            "role": profile.get("role", "user"),
            "cpf_cnpj": profile.get("cpf_cnpj"),
            "tipo_pessoa": profile.get("tipo_pessoa"),
            "terms_version": latest_terms.get("terms_version") if latest_terms else None,
            "terms_accepted_at": latest_terms.get("accepted_at") if latest_terms else None,
        }

    def update_me(self, user_id: str, email: str, data: dict) -> dict:
        """
        Atualiza o profile do próprio usuário.

        Regras:
        - `nome`: sempre editável.
        - `cpf_cnpj`: editável apenas se ainda não foi definido. Uma vez
          definido, vira imutável pelo usuário (auditoria de pedidos pagos
          depende do CPF do pagador). Mudança de CPF exige fluxo separado.
        - `email`/`password`: fora deste endpoint.
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        if not profile:
            raise NotFoundError("Perfil não encontrado")

        payload: dict = {}

        if data.get("nome") is not None:
            payload["nome"] = data["nome"]

        if data.get("cpf_cnpj") is not None:
            if profile.get("cpf_cnpj"):
                raise ConflictError(
                    "CPF/CNPJ já cadastrado. Alteração exige fluxo específico."
                )
            cpf_cnpj = data["cpf_cnpj"]
            payload["cpf_cnpj"] = cpf_cnpj
            payload["tipo_pessoa"] = derive_tipo_pessoa(cpf_cnpj)

        if payload:
            self.profile_repo.update(user_id, payload)
            logger.info(
                "Perfil atualizado",
                extra={"event": "PROFILE_UPDATED", "user_id": user_id},
            )

        # Sempre devolve o estado atual (fresco, com aceite).
        return self.get_me(user_id, email)