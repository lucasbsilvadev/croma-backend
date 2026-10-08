from decimal import Decimal

from app.repositories.address_repository import AddressRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.services.shipping_service import ShippingService
from app.utils.exceptions import NotFoundError, ValidationError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OrderService:
    """
    Regras de negócio de pedidos.

    Fluxo de criação:
    1. Valida endereço (é do user?)
    2. Valida cada produto (existe? ativo? estoque suficiente?)
    3. Calcula subtotal com snapshot de preço
    4. Consulta frete pelo CEP do endereço
    5. Cria order + order_items
    6. Decrementa estoque de cada produto

    Tudo é validado ANTES de qualquer insert. Se falhar, nada é criado.
    """

    def __init__(
        self,
        order_repo: OrderRepository | None = None,
        address_repo: AddressRepository | None = None,
        product_repo: ProductRepository | None = None,
        shipping_service: ShippingService | None = None,
    ):
        self.order_repo = order_repo or OrderRepository()
        self.address_repo = address_repo or AddressRepository()
        self.product_repo = product_repo or ProductRepository()
        self.shipping_service = shipping_service or ShippingService()

    # ============================================================
    # Cliente
    # ============================================================

    def create(self, user_id: str, data: dict) -> dict:
        """Cria pedido. Valida tudo antes de inserir."""
        # 1. Endereço do user
        address = self.address_repo.get_by_id_and_user(
            data["address_id"], user_id
        )
        if not address:
            raise NotFoundError("Endereço não encontrado")

        # 2. Produtos — busca e valida (guarda estoque atual em memória)
        prepared_items = []
        subtotal = Decimal("0.00")

        for item in data["items"]:
            product = self.product_repo.get_by_id(item["product_id"])

            if not product or not product.get("ativo"):
                raise NotFoundError(
                    f"Produto não encontrado: {item['product_id']}"
                )

            quantidade = item["quantidade"]

            if product["estoque"] < quantidade:
                raise ValidationError(
                    f"Estoque insuficiente para {product['nome']}. "
                    f"Disponível: {product['estoque']}"
                )

            preco = Decimal(str(product["preco"]))
            subtotal += preco * quantidade

            prepared_items.append({
                "product_id": product["id"],
                "product_nome": product["nome"],
                "product_slug": product["slug"],
                "quantidade": quantidade,
                "preco_unitario": str(preco),
                "_estoque_atual": product["estoque"],
            })

        # 3. Frete pelo CEP
        frete_data = self.shipping_service.quote(address["cep"])
        frete = Decimal(frete_data["valor"])

        # 4. Total
        total = subtotal + frete
        
        # Snapshot do endereço (PAYMENT-21): fotografia histórica.
        # Não incluir id/user_id/principal.
        address_snapshot = {
            "nome_destinatario": address["nome_destinatario"],
            "cep": address["cep"],
            "logradouro": address["logradouro"],
            "numero": address.get("numero"),
            "complemento": address.get("complemento"),
            "bairro": address["bairro"],
            "cidade": address["cidade"],
            "estado": address["estado"],
        }

        # 5. Cria order
        order_payload = {
            "user_id": user_id,
            "address_id": address["id"],
            "status": "created",
            "subtotal": str(subtotal),
            "frete": str(frete),
            "total": str(total),
            "notes": data.get("notes"),
            "payment_status": "pending",
            "address_snapshot": address_snapshot,   # ← ESSENCIAL
        }

        order = self.order_repo.create(order_payload)

        # 6. Cria items (remove chaves internas antes de inserir)
        items_payload = [
            {k: v for k, v in item.items() if not k.startswith("_")}
            | {"order_id": order["id"]}
            for item in prepared_items
        ]
        self.order_repo.create_items(items_payload)

        # 7. Decrementa estoque sem buscar produto de novo
        for item in prepared_items:
            novo_estoque = item["_estoque_atual"] - item["quantidade"]
            self.product_repo.update(item["product_id"], {"estoque": novo_estoque})

        logger.info(
            "Pedido criado",
            extra={"event": "ORDER_CREATED", "user_id": user_id},
        )

        return self._hydrate(order)

    def list_my(self, user_id: str) -> list[dict]:
        """Lista pedidos do user logado."""
        orders = self.order_repo.list_by_user(user_id)
        return [self._hydrate(o) for o in orders]

    def get_one(self, user_id: str, order_id: str) -> dict:
        """Retorna pedido se for do user. 404 caso contrário."""
        order = self.order_repo.get_by_id_and_user(order_id, user_id)
        if not order:
            raise NotFoundError("Pedido não encontrado")
        return self._hydrate(order)

    # ============================================================
    # Helpers
    # ============================================================

    def _hydrate(self, order: dict) -> dict:
        """Adiciona itens ao pedido."""
        items = self.order_repo.list_items_by_order(order["id"])
        return {**order, "items": items}