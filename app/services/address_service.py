from app.repositories.address_repository import AddressRepository
from app.utils.exceptions import NotFoundError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AddressService:
    """
    Regras de negócio de endereços/pontos de entrega.

    Regras:
    - Primeiro endereço do user vira principal automaticamente.
    - Só um principal por user. Marcar novo desmarca anterior.
    - Cliente só vê/edita/deleta endereço dele.
    - Delete do principal promove o mais antigo remanescente.
    """

    def __init__(self, address_repo: AddressRepository | None = None):
        self.address_repo = address_repo or AddressRepository()

    def create(self, user_id: str, data: dict) -> dict:
        """Cria endereço. Primeiro vira principal automaticamente."""
        is_first = self.address_repo.count_by_user(user_id) == 0
        wants_principal = data.get("principal", False)

        if is_first:
            data["principal"] = True
        elif wants_principal:
            self.address_repo.clear_principal(user_id)

        address = self.address_repo.create(user_id, data)

        logger.info(
            "Endereço criado",
            extra={"event": "ADDRESS_CREATED", "user_id": user_id},
        )

        return address

    def list_my(self, user_id: str) -> list[dict]:
        """Lista endereços do user. Principal primeiro."""
        return self.address_repo.list_by_user(user_id)

    def get_one(self, user_id: str, address_id: str) -> dict:
        """Retorna endereço se for do user. 404 caso contrário."""
        address = self.address_repo.get_by_id_and_user(address_id, user_id)

        if not address:
            raise NotFoundError("Endereço não encontrado")

        return address

    def update(self, user_id: str, address_id: str, data: dict) -> dict:
        """Atualização parcial. Só campos enviados."""
        existing = self.address_repo.get_by_id_and_user(address_id, user_id)
        if not existing:
            raise NotFoundError("Endereço não encontrado")

        payload = {k: v for k, v in data.items() if v is not None}

        if not payload:
            return existing

        if payload.get("principal") is True:
            self.address_repo.clear_principal(user_id)

        updated = self.address_repo.update(address_id, payload)

        logger.info(
            "Endereço atualizado",
            extra={"event": "ADDRESS_UPDATED", "user_id": user_id},
        )

        return updated

    def delete(self, user_id: str, address_id: str) -> None:
        """Deleta endereço. Se era principal, promove o mais antigo."""
        existing = self.address_repo.get_by_id_and_user(address_id, user_id)
        if not existing:
            raise NotFoundError("Endereço não encontrado")

        was_principal = existing.get("principal", False)

        self.address_repo.delete(address_id)

        if was_principal:
            next_addr = self.address_repo.get_oldest_by_user(user_id)
            if next_addr:
                self.address_repo.update(next_addr["id"], {"principal": True})

        logger.info(
            "Endereço deletado",
            extra={"event": "ADDRESS_DELETED", "user_id": user_id},
        )