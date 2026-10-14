"""
Acesso às tabelas `terms_acceptances` e `terms_versions`.

Único ponto de acesso a aceites e versões de Termos de Uso.
Escrita via service_role (bypassa RLS) — a tabela não tem policy de INSERT.
Leitura também via service_role, pois o backend só consulta aceite
do próprio usuário autenticado (validado antes de chegar aqui).

Referência: LGPD-01.
"""
from app.config.supabase import supabase_admin
from app.utils.exceptions import ConflictError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TermsRepository:
    """Único ponto de acesso às tabelas `terms_acceptances` e `terms_versions`."""

    # ============================================================
    # terms_acceptances
    # ============================================================

    def create_acceptance(
        self,
        user_id: str,
        terms_version: str,
        document_hash: str | None = None,
    ) -> dict:
        """
        Registra um aceite.

        Idempotência: se o usuário já aceitou esta versão, devolve a linha
        existente em vez de levantar erro. A constraint UNIQUE
        (user_id, terms_version) garante que não há duplicata.

        Aceitar a mesma versão duas vezes é cenário legítimo (retry de
        request, clique duplo), então tratamos como sucesso.

        `document_hash` é o hash do texto aceito (LGPD-01). Nullable porque
        aceites antigos não têm como recuperar o texto original.
        """
        try:
            res = (
                supabase_admin.table("terms_acceptances")
                .insert({
                    "user_id": user_id,
                    "terms_version": terms_version,
                    "document_hash": document_hash,
                })
                .execute()
            )
            return res.data[0]
        except Exception as e:
            code = getattr(e, "code", None)
            if code == "23505":
                # Unique violation: já aceitou esta versão. Devolve a existente.
                existing = self.get_acceptance(user_id, terms_version)
                if existing:
                    return existing
                # Se não achou mesmo assim, é race rara — propaga.
                raise
            if code == "23503":
                # FK violation: user_id ainda não commitou em auth.users.
                # Não deveria acontecer no fluxo de register (auth.users é
                # criado ANTES de chamarmos ensure_profile/aceite), mas
                # tratamos como erro real — não engolir.
                raise ConflictError(
                    "Usuário ainda não está pronto para aceite"
                ) from None
            raise

    def get_acceptance(self, user_id: str, terms_version: str) -> dict | None:
        """Busca um aceite específico (user + versão)."""
        res = (
            supabase_admin.table("terms_acceptances")
            .select("*")
            .eq("user_id", user_id)
            .eq("terms_version", terms_version)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_latest_for_user(self, user_id: str) -> dict | None:
        """
        Aceite mais recente do usuário (qualquer versão).

        Usado pelo /me para expor `terms_version` e `terms_accepted_at`.
        Ordena por accepted_at desc, desempata por created_at desc.
        """
        res = (
            supabase_admin.table("terms_acceptances")
            .select("*")
            .eq("user_id", user_id)
            .order("accepted_at", desc=True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def list_for_user(self, user_id: str) -> list[dict]:
        """Histórico completo de aceites do usuário (auditoria futura)."""
        res = (
            supabase_admin.table("terms_acceptances")
            .select("*")
            .eq("user_id", user_id)
            .order("accepted_at", desc=True)
            .execute()
        )
        return res.data or []

    # ============================================================
    # terms_versions
    # ============================================================

    def get_active_version(self, version: str) -> dict | None:
        """
        Busca uma versão de termos ativa pelo nome exato.

        Usado pelo TermsService.validate_version (fail-closed).
        Retorna None se a versão não existir OU estiver inativa.
        """
        res = (
            supabase_admin.table("terms_versions")
            .select("*")
            .eq("version", version)
            .eq("ativo", True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_current_version(self) -> dict | None:
        """
        Versão vigente: a mais recente ativa por effective_at.

        Usado pelo GET /terms/current (endpoint público).
        """
        res = (
            supabase_admin.table("terms_versions")
            .select("*")
            .eq("ativo", True)
            .order("effective_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None