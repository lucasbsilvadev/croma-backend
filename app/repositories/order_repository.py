from app.config.supabase import supabase_admin
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OrderRepository:
    """
    Único ponto de acesso às tabelas `orders` e `order_items`.
    """

    # ============================================================
    # orders
    # ============================================================

    def create(self, data: dict) -> dict:
        res = supabase_admin.table("orders").insert(data).execute()
        return res.data[0]

    def get_by_id(self, order_id: str) -> dict | None:
        res = (
            supabase_admin.table("orders")
            .select("*")
            .eq("id", order_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_by_id_and_user(self, order_id: str, user_id: str) -> dict | None:
        """Filtra por user_id também — evita vazar pedido de outro user."""
        res = (
            supabase_admin.table("orders")
            .select("*")
            .eq("id", order_id)
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def list_by_user(self, user_id: str) -> list[dict]:
        res = (
            supabase_admin.table("orders")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []

    # ============================================================
    # order_items
    # ============================================================

    def create_items(self, items: list[dict]) -> list[dict]:
        """Insere múltiplos order_items de uma vez."""
        if not items:
            return []
        res = supabase_admin.table("order_items").insert(items).execute()
        return res.data or []

    def list_items_by_order(self, order_id: str) -> list[dict]:
        res = (
            supabase_admin.table("order_items")
            .select("*")
            .eq("order_id", order_id)
            .execute()
        )
        return res.data or []