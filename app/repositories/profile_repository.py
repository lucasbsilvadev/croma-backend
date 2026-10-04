from app.config.supabase import supabase_admin
from app.utils.exceptions import ConflictError


class ProfileRepository:
    """
    Único ponto de acesso à tabela `profiles`.
    Nenhuma query SQL fora daqui.
    """

    def get_by_user_id(self, user_id: str) -> dict | None:
        res = (
            supabase_admin.table("profiles")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def create(self, user_id: str, nome: str) -> dict:
        """
        Cria um profile. Levanta ConflictError se já existir.
        Para criação idempotente (incluindo race conditions), use `ensure_profile`.
        """
        if self.get_by_user_id(user_id):
            raise ConflictError("Perfil já existe")

        res = (
            supabase_admin.table("profiles")
            .insert({"user_id": user_id, "nome": nome})
            .execute()
        )
        return res.data[0]

    def ensure_profile(self, user_id: str, nome: str) -> dict:
        """
        Garante que existe um profile para o user_id.
        Idempotente: se já existir, retorna o existente.
        Trata race condition: dois requests simultâneos criam 1 só.

        Códigos tratados:
          23505 = unique violation (alguém criou entre o get e o insert)
          23503 = FK violation (user ainda não commitou em auth.users)
        """
        existing = self.get_by_user_id(user_id)
        if existing:
            return existing

        try:
            return self.create(user_id=user_id, nome=nome)
        except ConflictError:
            # Corrida: alguém criou entre nosso get e o insert
            retry = self.get_by_user_id(user_id)
            if retry:
                return retry
            raise
        except Exception as e:
            # postgrest.APIError expõe `code` como atributo próprio
            code = getattr(e, "code", None)
            if code in ("23505", "23503"):
                retry = self.get_by_user_id(user_id)
                if retry:
                    return retry
            raise