from app.config.supabase import supabase_admin
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AddressRepository:
    """
    Único ponto de acesso à tabela `addresses`.
    Nenhuma query Supabase fora daqui.
    """

    def create(self, user_id: str, data: dict) -> dict:
        payload = {**data, "user_id": user_id}
        res = supabase_admin.table("addresses").insert(payload).execute()
        return res.data[0]

    def list_by_user(self, user_id: str) -> list[dict]:
        """
        Lista endereços do user. Principal primeiro, depois mais antigo.

        Nota: o SDK Python do Supabase NÃO suporta múltiplas colunas em
        uma única string de .order(). A sintaxe `order("col1.desc,col2.asc")`
        quebra. Solução: chama .order() duas vezes com kwargs explícitos.
        """
        res = (
            supabase_admin.table("addresses")
            .select("*")
            .eq("user_id", user_id)
            .order("principal", desc=True)
            .order("created_at", desc=False)
            .execute()
        )
        return res.data or []

    def get_by_id(self, address_id: str) -> dict | None:
        res = (
            supabase_admin.table("addresses")
            .select("*")
            .eq("id", address_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_by_id_and_user(self, address_id: str, user_id: str) -> dict | None:
        """Filtra por user_id também — evita vazar endereço de outro user."""
        res = (
            supabase_admin.table("addresses")
            .select("*")
            .eq("id", address_id)
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def update(self, address_id: str, data: dict) -> dict:
        res = (
            supabase_admin.table("addresses")
            .update(data)
            .eq("id", address_id)
            .execute()
        )
        return res.data[0]

    def delete(self, address_id: str) -> None:
        supabase_admin.table("addresses").delete().eq("id", address_id).execute()

    def clear_principal(self, user_id: str) -> None:
        """Desmarca todos os endereços principais do user."""
        (
            supabase_admin.table("addresses")
            .update({"principal": False})
            .eq("user_id", user_id)
            .eq("principal", True)
            .execute()
        )

    def count_by_user(self, user_id: str) -> int:
        res = (
            supabase_admin.table("addresses")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        return res.count or 0

    def get_oldest_by_user(self, user_id: str) -> dict | None:
        """Endereço mais antigo do user. Usado pra promover a principal após delete."""
        res = (
            supabase_admin.table("addresses")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at.asc")
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None