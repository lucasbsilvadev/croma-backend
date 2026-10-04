"""
Testes do endpoint POST /auth/register.
Cobre contrato HTTP + política de senha no boundary.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_auth_service(client):
    """Mock do AuthService para não bater no Supabase."""
    from app.routes import auth_routes

    service = MagicMock()
    client.app.dependency_overrides[auth_routes.get_auth_service] = lambda: service
    yield service
    client.app.dependency_overrides.clear()


def test_register_success(client, fake_user, mock_auth_service):
    mock_auth_service.register.return_value = {
        "user_id": "uuid-123",
        "access_token": "tok",
        "refresh_token": "ref",
    }

    res = client.post("/auth/register", json=fake_user)

    assert res.status_code == 201
    assert res.json()["user_id"] == "uuid-123"
    mock_auth_service.register.assert_called_once()


def test_register_invalid_email_returns_422(client, fake_user):
    fake_user["email"] = "nao-e-email"
    res = client.post("/auth/register", json=fake_user)
    assert res.status_code == 422


# ============================================================
# Política de senha no boundary HTTP
# ============================================================


@pytest.mark.parametrize(
    "senha_invalida, motivo",
    [
        ("Ab1!", "menos de 8 caracteres"),
        ("senhasegura123!", "sem maiúscula"),
        ("SENHASEGURA123!", "sem minúscula"),
        ("SenhaSegura!!", "sem número"),
        ("SenhaSegura123", "sem caractere especial"),
    ],
)
def test_register_rejects_weak_password_with_422(
    client, fake_user, mock_auth_service, senha_invalida, motivo
):
    """Senha fraca é barrada pelo Pydantic ANTES de chegar no service."""
    fake_user["password"] = senha_invalida

    res = client.post("/auth/register", json=fake_user)

    assert res.status_code == 422, f"Esperava 422 para senha: {motivo}"
    # Garante que o service NUNCA foi chamado — a barreira é antes
    mock_auth_service.register.assert_not_called()


def test_register_rejects_password_over_72_chars(client, fake_user, mock_auth_service):
    """Senha >72 chars rejeitada (limite do hash bcrypt do Supabase)."""
    fake_user["password"] = "A1!" + "a" * 70  # 73 chars
    res = client.post("/auth/register", json=fake_user)
    assert res.status_code == 422
    mock_auth_service.register.assert_not_called()


def test_register_accepts_password_exactly_8_chars(client, fake_user, mock_auth_service):
    """Senha com exatamente 8 chars válidos deve passar."""
    fake_user["password"] = "Aa1!aaaa"
    mock_auth_service.register.return_value = {
        "user_id": "uuid-1",
        "access_token": "t",
        "refresh_token": "r",
    }
    res = client.post("/auth/register", json=fake_user)
    assert res.status_code == 201


def test_register_accepts_password_exactly_72_chars(client, fake_user, mock_auth_service):
    """Senha com exatamente 72 chars válidos deve passar."""
    fake_user["password"] = "Aa1!" + "a" * 68  # 72 chars
    mock_auth_service.register.return_value = {
        "user_id": "uuid-1",
        "access_token": "t",
        "refresh_token": "r",
    }
    res = client.post("/auth/register", json=fake_user)
    assert res.status_code == 201