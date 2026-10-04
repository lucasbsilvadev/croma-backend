"""Testes das rotas de pedido. Foco: auth e autorização."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_service(client):
    from app.routes import order_routes
    svc = MagicMock()
    client.app.dependency_overrides[order_routes.get_order_service] = lambda: svc
    yield svc
    client.app.dependency_overrides.clear()


@pytest.fixture
def mock_user(client):
    from app.middleware.auth import get_current_user
    fake = {"user_id": "u1", "email": "a@b.com", "role": "user"}
    client.app.dependency_overrides[get_current_user] = lambda: fake
    yield fake
    client.app.dependency_overrides.clear()


def _order_response(id="o1"):
    return {
        "id": id, "user_id": "u1", "address_id": "a1",
        "status": "created", "subtotal": "100.00", "frete": "15.00",
        "total": "115.00", "notes": None, "payment_status": "pending",
        "payment_method": None, "created_at": "2026-10-04T00:00:00+00:00",
        "updated_at": "2026-10-04T00:00:00+00:00", "items": [],
    }


def test_create_without_token_returns_401(client, mock_service):
    res = client.post("/orders", json={
        "address_id": "a1",
        "items": [{"product_id": "p1", "quantidade": 1}],
    })
    assert res.status_code == 401


def test_create_with_token_returns_201(client, mock_service, mock_user):
    mock_service.create.return_value = _order_response()
    res = client.post("/orders", json={
        "address_id": "a1",
        "items": [{"product_id": "p1", "quantidade": 1}],
    })
    assert res.status_code == 201


def test_list_returns_only_my_orders(client, mock_service, mock_user):
    mock_service.list_my.return_value = [_order_response()]
    res = client.get("/orders")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_get_one_returns_404_for_other_user(client, mock_service, mock_user):
    from app.utils.exceptions import NotFoundError
    mock_service.get_one.side_effect = NotFoundError("Pedido não encontrado")

    res = client.get("/orders/o-do-outro")
    assert res.status_code == 404


def test_create_returns_422_for_empty_items(client, mock_service, mock_user):
    """Pydantic valida antes de chegar no service."""
    res = client.post("/orders", json={
        "address_id": "a1",
        "items": [],
    })
    assert res.status_code == 422
    mock_service.create.assert_not_called()


def test_create_returns_422_for_duplicate_products(client, mock_service, mock_user):
    """Não aceita o mesmo produto duas vezes."""
    res = client.post("/orders", json={
        "address_id": "a1",
        "items": [
            {"product_id": "p1", "quantidade": 1},
            {"product_id": "p1", "quantidade": 2},
        ],
    })
    assert res.status_code == 422
    mock_service.create.assert_not_called()