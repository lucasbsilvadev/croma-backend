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
        if self.get_by_user_id(user_id):
            raise ConflictError("Perfil já existe")

        res = (
            supabase_admin.table("profiles")
            .insert({"user_id": user_id, "nome": nome})
            .execute()
        )
        return res.data[0]
