"""Testes das rotas admin. Foco: autorização."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_service(client):
    from app.routes import admin_product_routes
    svc = MagicMock()
    client.app.dependency_overrides[admin_product_routes.get_product_service] = lambda: svc
    yield svc
    client.app.dependency_overrides.clear()


def _fake_user(role="user"):
    return {"user_id": "u1", "email": "a@b.com", "role": role}


def test_create_without_token_returns_401(client, mock_service):
    """Sem auth → 401 (dependência get_current_admin_user rejeita)."""
    res = client.post("/admin/products", json={
        "nome": "XY", "slug": "xy", "preco": "10.00", "estoque": 0,
    })
    assert res.status_code == 401


def test_create_with_non_admin_returns_403(client, mock_service):
    """User comum → 403."""
    from app.middleware.auth import get_current_user
    client.app.dependency_overrides[get_current_user] = lambda: _fake_user("user")

    res = client.post("/admin/products", json={
        "nome": "XY", "slug": "xy", "preco": "10.00", "estoque": 0,
    })
    assert res.status_code == 403


def test_create_with_admin_returns_201(client, mock_service):
    """Admin → 201."""
    from app.middleware.auth import get_current_user, get_current_admin_user
    fake_admin = _fake_user("admin")
    client.app.dependency_overrides[get_current_user] = lambda: fake_admin
    client.app.dependency_overrides[get_current_admin_user] = lambda: fake_admin

    mock_service.create_product.return_value = {
        "id": "p1", "nome": "XY", "slug": "xy",
        "descricao": None, "preco": "10.00", "estoque": 0,
        "ativo": True, "imagens": [],
        "created_at": "2026-10-04T00:00:00+00:00",
    }

    res = client.post("/admin/products", json={
        "nome": "XY", "slug": "xy", "preco": "10.00", "estoque": 0,
    })
    assert res.status_code == 201


def test_delete_returns_soft_deleted(client, mock_service):
    """DELETE retorna 200 com ativo=false."""
    from app.middleware.auth import get_current_user, get_current_admin_user
    fake_admin = _fake_user("admin")
    client.app.dependency_overrides[get_current_user] = lambda: fake_admin
    client.app.dependency_overrides[get_current_admin_user] = lambda: fake_admin

    mock_service.soft_delete.return_value = {
        "id": "p1", "nome": "X", "slug": "x",
        "descricao": None, "preco": "10.00", "estoque": 0,
        "ativo": False, "imagens": [],
        "created_at": "2026-10-04T00:00:00+00:00",
    }

    res = client.delete("/admin/products/p1")
    assert res.status_code == 200
    assert res.json()["ativo"] is False