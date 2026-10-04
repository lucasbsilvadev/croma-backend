"""Testes das rotas de endereço. Foco: contrato HTTP e autorização."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_service(client):
    from app.routes import address_routes
    svc = MagicMock()
    client.app.dependency_overrides[address_routes.get_address_service] = lambda: svc
    yield svc
    client.app.dependency_overrides.clear()


@pytest.fixture
def mock_user(client):
    from app.middleware.auth import get_current_user
    fake = {"user_id": "u1", "email": "a@b.com", "role": "user"}
    client.app.dependency_overrides[get_current_user] = lambda: fake
    yield fake
    client.app.dependency_overrides.clear()


def _addr_body():
    return {
        "nome_destinatario": "Fulano",
        "cep": "70000000",
        "logradouro": "Rua X",
        "numero": "10",
        "bairro": "Centro",
        "cidade": "Brasília",
        "estado": "DF",
        "principal": False,
    }


def _addr_response(id="a1", principal=True):
    return {
        "id": id, "nome_destinatario": "Fulano", "cep": "70000000",
        "logradouro": "Rua X", "numero": "10", "complemento": None,
        "bairro": "Centro", "cidade": "Brasília", "estado": "DF",
        "principal": principal, "created_at": "2026-10-04T00:00:00+00:00",
    }


def test_create_without_token_returns_401(client, mock_service):
    res = client.post("/addresses", json=_addr_body())
    assert res.status_code == 401


def test_create_with_token_returns_201(client, mock_service, mock_user):
    mock_service.create.return_value = _addr_response()
    res = client.post("/addresses", json=_addr_body())
    assert res.status_code == 201
    assert res.json()["id"] == "a1"


def test_list_returns_only_my_addresses(client, mock_service, mock_user):
    mock_service.list_my.return_value = [_addr_response()]
    res = client.get("/addresses")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_get_one_returns_404_for_other_user(client, mock_service, mock_user):
    """Endereço de outro user → 404 (não vaza existência)."""
    from app.utils.exceptions import NotFoundError
    mock_service.get_one.side_effect = NotFoundError("Endereço não encontrado")

    res = client.get("/addresses/a-do-outro")
    assert res.status_code == 404


def test_update_returns_404_for_other_user(client, mock_service, mock_user):
    from app.utils.exceptions import NotFoundError
    mock_service.update.side_effect = NotFoundError("Endereço não encontrado")

    res = client.patch("/addresses/a-do-outro", json={"cidade": "X"})
    assert res.status_code == 404


def test_delete_returns_204(client, mock_service, mock_user):
    mock_service.delete.return_value = None
    res = client.delete("/addresses/a1")
    assert res.status_code == 204


def test_delete_returns_404_for_other_user(client, mock_service, mock_user):
    from app.utils.exceptions import NotFoundError
    mock_service.delete.side_effect = NotFoundError("Endereço não encontrado")

    res = client.delete("/addresses/a-do-outro")
    assert res.status_code == 404