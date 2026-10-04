from app.config.supabase import supabase_admin
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ShippingRepository:
    """
    Único ponto de acesso à tabela `shipping_zones`.
    """

    def find_zone_by_cep(self, cep: str) -> dict | None:
        """
        Busca a zona de frete cujo intervalo de CEP contém o CEP informado.
        Retorna None se nenhuma zona cobrir.
        """
        # PostgREST: filtro por range usa lte/gte
        res = (
            supabase_admin.table("shipping_zones")
            .select("*")
            .eq("ativo", True)
            .lte("cep_prefixo_min", cep)
            .gte("cep_prefixo_max", cep)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None