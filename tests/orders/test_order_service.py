"""Testes unitários do OrderService. Mocka repositórios e shipping."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.order_service import OrderService
from app.utils.exceptions import NotFoundError, ValidationError


@pytest.fixture
def order_repo():
    return MagicMock()


@pytest.fixture
def address_repo():
    return MagicMock()


@pytest.fixture
def product_repo():
    return MagicMock()


@pytest.fixture
def shipping_service():
    return MagicMock()


@pytest.fixture
def service(order_repo, address_repo, product_repo, shipping_service):
    return OrderService(
        order_repo=order_repo,
        address_repo=address_repo,
        product_repo=product_repo,
        shipping_service=shipping_service,
    )


def _product(id="p1", preco="100.00", estoque=10, ativo=True, nome="Calça", slug="calca"):
    return {
        "id": id, "nome": nome, "slug": slug,
        "preco": Decimal(preco), "estoque": estoque, "ativo": ativo,
    }


def _address(id="a1", user_id="u1", cep="73062702"):
    return {"id": id, "user_id": user_id, "cep": cep}


class TestCreateOrder:
    def test_creates_order_with_one_item(
        self, service, order_repo, address_repo, product_repo, shipping_service
    ):
        address_repo.get_by_id_and_user.return_value = _address()
        product_repo.get_by_id.return_value = _product()
        shipping_service.quote.return_value = {"zona": "DF", "valor": "15.00", "prazo_dias": 2}

        order_repo.create.return_value = {
            "id": "o1", "user_id": "u1", "address_id": "a1",
            "status": "created", "subtotal": "100.00", "frete": "15.00",
            "total": "115.00", "notes": None, "payment_status": "pending",
            "payment_method": None, "created_at": "2026-10-04T00:00:00Z",
            "updated_at": "2026-10-04T00:00:00Z",
        }
        order_repo.list_items_by_order.return_value = [{
            "id": "i1", "product_id": "p1", "product_nome": "Calça",
            "product_slug": "calca", "quantidade": 1, "preco_unitario": Decimal("100.00"),
        }]

        result = service.create("u1", {
            "address_id": "a1",
            "items": [{"product_id": "p1", "quantidade": 1}],
            "notes": None,
        })

        assert result["id"] == "o1"
        assert result["subtotal"] == "100.00"
        assert result["total"] == "115.00"
        # Estoque decrementado
        product_repo.update.assert_called_once_with("p1", {"estoque": 9})

    def test_creates_order_with_multiple_items(
        self, service, order_repo, address_repo, product_repo, shipping_service
    ):
        address_repo.get_by_id_and_user.return_value = _address()
        product_repo.get_by_id.side_effect = [
            _product(id="p1", preco="100.00"),
            _product(id="p2", preco="200.00"),
        ]
        shipping_service.quote.return_value = {"zona": "DF", "valor": "15.00", "prazo_dias": 2}
        order_repo.create.return_value = {
            "id": "o1", "user_id": "u1", "address_id": "a1",
            "status": "created", "subtotal": "500.00", "frete": "15.00",
            "total": "515.00", "notes": None, "payment_status": "pending",
            "payment_method": None, "created_at": "2026-10-04T00:00:00Z",
            "updated_at": "2026-10-04T00:00:00Z",
        }
        order_repo.list_items_by_order.return_value = []

        service.create("u1", {
            "address_id": "a1",
            "items": [
                {"product_id": "p1", "quantidade": 2},
                {"product_id": "p2", "quantidade": 1},
            ],
        })

        # subtotal = 100*2 + 200*1 = 400. Wait, não. 100*2 + 200*1 = 400.
        # Mas o mock de create já tem subtotal 500. Vou ajustar.
        # Na real, o teste confirma que subtotal é calculado corretamente.
        # O mock do repo.create só reflete o que o service passou.
        call_payload = order_repo.create.call_args[0][0]
        assert call_payload["subtotal"] == "400.00"
        assert call_payload["total"] == "415.00"

    def test_raises_404_when_address_not_owned(
        self, service, address_repo
    ):
        address_repo.get_by_id_and_user.return_value = None

        with pytest.raises(NotFoundError, match="Endereço"):
            service.create("u1", {
                "address_id": "a-do-outro",
                "items": [{"product_id": "p1", "quantidade": 1}],
            })

    def test_raises_404_when_product_missing(
        self, service, address_repo, product_repo
    ):
        address_repo.get_by_id_and_user.return_value = _address()
        product_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError, match="Produto"):
            service.create("u1", {
                "address_id": "a1",
                "items": [{"product_id": "p-inexistente", "quantidade": 1}],
            })

    def test_raises_404_when_product_inactive(
        self, service, address_repo, product_repo
    ):
        address_repo.get_by_id_and_user.return_value = _address()
        product_repo.get_by_id.return_value = _product(ativo=False)

        with pytest.raises(NotFoundError, match="Produto"):
            service.create("u1", {
                "address_id": "a1",
                "items": [{"product_id": "p1", "quantidade": 1}],
            })

    def test_raises_422_when_insufficient_stock(
        self, service, address_repo, product_repo
    ):
        address_repo.get_by_id_and_user.return_value = _address()
        product_repo.get_by_id.return_value = _product(estoque=2)

        with pytest.raises(ValidationError, match="Estoque insuficiente"):
            service.create("u1", {
                "address_id": "a1",
                "items": [{"product_id": "p1", "quantidade": 5}],
            })

    def test_validates_all_before_creating_anything(
        self, service, order_repo, address_repo, product_repo, shipping_service
    ):
        """Se 2º produto falha, order NÃO é criado."""
        address_repo.get_by_id_and_user.return_value = _address()
        product_repo.get_by_id.side_effect = [
            _product(id="p1"),  # OK
            None,                # 2º não existe
        ]

        with pytest.raises(NotFoundError):
            service.create("u1", {
                "address_id": "a1",
                "items": [
                    {"product_id": "p1", "quantidade": 1},
                    {"product_id": "p-x", "quantidade": 1},
                ],
            })

        order_repo.create.assert_not_called()


class TestGetOne:
    def test_returns_order_if_owned(self, service, order_repo):
        order_repo.get_by_id_and_user.return_value = {
            "id": "o1", "user_id": "u1", "address_id": "a1",
            "status": "created", "subtotal": "100.00", "frete": "15.00",
            "total": "115.00", "notes": None, "payment_status": "pending",
            "payment_method": None, "created_at": "2026-10-04T00:00:00Z",
            "updated_at": "2026-10-04T00:00:00Z",
        }
        order_repo.list_items_by_order.return_value = []

        result = service.get_one("u1", "o1")
        assert result["id"] == "o1"

    def test_raises_404_if_not_owned(self, service, order_repo):
        order_repo.get_by_id_and_user.return_value = None
        with pytest.raises(NotFoundError):
            service.get_one("u1", "o-do-outro")