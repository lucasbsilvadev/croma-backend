from decimal import Decimal

from app.repositories.shipping_repository import ShippingRepository
from app.utils.exceptions import ValidationError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ShippingService:
    """
    Regras de negócio de frete.
    Consulta tabela `shipping_zones` por faixa de CEP.
    """

    def __init__(self, shipping_repo: ShippingRepository | None = None):
        self.shipping_repo = shipping_repo or ShippingRepository()

    def quote(self, cep: str) -> dict:
        """
        Consulta frete pelo CEP. Retorna zona, valor e prazo.
        CEP é normalizado (só dígitos) antes da busca.
        """
        cep_clean = self._normalize_cep(cep)

        if len(cep_clean) != 8:
            raise ValidationError("CEP inválido. Use 8 dígitos.")

        zone = self.shipping_repo.find_zone_by_cep(cep_clean)

        if not zone:
            logger.info(
                "Frete indisponível para CEP",
                extra={"event": "SHIPPING_QUOTE_UNAVAILABLE"},
            )
            raise ValidationError("Frete indisponível para este CEP")

        logger.info(
            "Frete consultado",
            extra={"event": "SHIPPING_QUOTE_OK"},
        )

        return {
            "zona": zone["nome"],
            "valor": f"{Decimal(zone['valor_cents']) / 100:.2f}",
            "prazo_dias": zone["prazo_dias"],
        }

    @staticmethod
    def _normalize_cep(cep: str) -> str:
        """Remove hífen e espaços. Só dígitos."""
        return "".join(c for c in cep if c.isdigit())