"""Testes das rotas de frete. Público, sem auth."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_service(client):
    from app.routes import shipping_routes
    svc = MagicMock()
    client.app.dependency_overrides[shipping_routes.get_shipping_service] = lambda: svc
    yield svc
    client.app.dependency_overrides.clear()


def test_quote_without_auth(client, mock_service):
    """Frete é público."""
    mock_service.quote.return_value = {
        "zona": "DF", "valor": "15.00", "prazo_dias": 2,
    }

    res = client.post("/shipping/quote", json={"cep": "73062702"})

    assert res.status_code == 200
    assert res.json()["valor"] == "15.00"


def test_quote_returns_422_for_bad_cep(client, mock_service):
    from app.utils.exceptions import ValidationError
    mock_service.quote.side_effect = ValidationError("CEP inválido")

    res = client.post("/shipping/quote", json={"cep": "abc"})

    assert res.status_code == 422