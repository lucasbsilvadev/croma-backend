from app.config.supabase import supabase_admin
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ProductRepository:
    """
    Único ponto de acesso às tabelas `products` e `product_images`.
    Nenhuma query Supabase fora daqui.
    """

    # ============================================================
    # products
    # ============================================================

    def create(self, data: dict) -> dict:
        res = supabase_admin.table("products").insert(data).execute()
        return res.data[0]

    def get_by_id(self, product_id: str) -> dict | None:
        res = (
            supabase_admin.table("products")
            .select("*")
            .eq("id", product_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def get_by_slug(self, slug: str) -> dict | None:
        res = (
            supabase_admin.table("products")
            .select("*")
            .eq("slug", slug)
            .execute()
        )
        return res.data[0] if res.data else None

    def list_active(self) -> list[dict]:
        res = (
            supabase_admin.table("products")
            .select("*")
            .eq("ativo", True)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []

    def list_all(self) -> list[dict]:
        res = (
            supabase_admin.table("products")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []

    def update(self, product_id: str, data: dict) -> dict:
        res = (
            supabase_admin.table("products")
            .update(data)
            .eq("id", product_id)
            .execute()
        )
        return res.data[0]

    def soft_delete(self, product_id: str) -> dict:
        return self.update(product_id, {"ativo": False})

    def exists_slug(self, slug: str) -> bool:
        return self.get_by_slug(slug) is not None

    # ============================================================
    # product_images
    # ============================================================

    def add_image(self, product_id: str, url: str, position: int) -> dict:
        res = (
            supabase_admin.table("product_images")
            .insert({
                "product_id": product_id,
                "url": url,
                "position": position,
            })
            .execute()
        )
        return res.data[0]

    def list_images(self, product_id: str) -> list[dict]:
        res = (
            supabase_admin.table("product_images")
            .select("*")
            .eq("product_id", product_id)
            .order("position")
            .execute()
        )
        return res.data or []

    def get_image(self, image_id: str) -> dict | None:
        res = (
            supabase_admin.table("product_images")
            .select("*")
            .eq("id", image_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def remove_image(self, image_id: str) -> None:
        supabase_admin.table("product_images").delete().eq("id", image_id).execute()