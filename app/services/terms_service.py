"""
Regras de negócio de Termos de Uso versionados.
Referência: LGPD-01.
"""
from app.repositories.terms_repository import TermsRepository
from app.utils.exceptions import NotFoundError, ValidationError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TermsService:
    """Regras de negócio de Termos de Uso versionados."""

    def __init__(self, terms_repo: TermsRepository | None = None):
        self.terms_repo = terms_repo or TermsRepository()

    def get_current(self) -> dict:
        """
        Versão vigente (mais recente ativa por effective_at).
        Usado pelo GET /terms/current (público).
        """
        current = self.terms_repo.get_current_version()
        if not current:
            # Fail-closed: sem versão vigente, o app não pode operar.
            # Isso é bug de operação (admin esqueceu de cadastrar).
            logger.warning(
                "Nenhuma versão de termos vigente",
                extra={"event": "TERMS_NO_CURRENT_VERSION"},
            )
            raise NotFoundError("Nenhuma versão de termos vigente")

        return {
            "version": current["version"],
            "effective_at": current["effective_at"],
            "url": current.get("url"),
        }

    def validate_version(self, version: str) -> dict:
        """
        Valida que `version` existe e está ativa.
        Fail-closed: desconhecida/inativa → ValidationError.

        Retorna a linha da versão (pra o caller pegar document_hash).
        """
        row = self.terms_repo.get_active_version(version)
        if not row:
            logger.warning(
                "terms_version inválida no register",
                extra={"event": "TERMS_VERSION_INVALID"},
            )
            raise ValidationError("Versão dos termos inválida ou expirada")
        return row