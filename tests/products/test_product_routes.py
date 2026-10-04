"""Testes das rotas públicas de produtos. Mocka service."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_service(client):
    from app.routes import product_routes
    svc = MagicMock()
    client.app.dependency_overrides[product_routes.get_product_service] = lambda: svc
    yield svc
    client.app.dependency_overrides.clear()


def test_list_products_without_auth(client, mock_service):
    """Catálogo é público — sem token funciona."""
    mock_service.list_active.return_value = [{
        "id": "p1", "nome": "NØ CAP", "slug": "no-cap",
        "descricao": None, "preco": "112.00", "estoque": 5,
        "ativo": True, "imagens": [],
        "created_at": "2026-10-04T00:00:00+00:00",
    }]
    res = client.get("/products")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_get_product_by_slug(client, mock_service):
    mock_service.get_active_by_slug.return_value = {
        "id": "p1", "nome": "NØ CAP", "slug": "no-cap",
        "descricao": None, "preco": "112.00", "estoque": 5,
        "ativo": True, "imagens": [],
        "created_at": "2026-10-04T00:00:00+00:00",
    }
    res = client.get("/products/no-cap")
    assert res.status_code == 200
    assert res.json()["slug"] == "no-cap"


def test_get_product_inactive_returns_404(client, mock_service):
    from app.utils.exceptions import NotFoundError
    mock_service.get_active_by_slug.side_effect = NotFoundError("Produto não encontrado")

    res = client.get("/products/produto-inativo")
    assert res.status_code == 404