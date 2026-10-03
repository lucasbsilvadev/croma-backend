"""
Testes unitários do endpoint GET /me.
Mocka get_current_user — não bate no Supabase real.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_current_user(client):
    """
    Override do dependency `get_current_user` para retornar um user fake.
    Facilita testar rotas protegidas sem precisar gerar JWT real.
    """
    from app.middleware.auth import get_current_user

    fake = {"user_id": "uuid-abc", "email": "user@example.com"}
    client.app.dependency_overrides[get_current_user] = lambda: fake
    yield fake
    client.app.dependency_overrides.clear()


@pytest.fixture
def mock_profile_service(client):
    """Override do ProfileService para não bater no Supabase."""
    from app.routes.profile_routes import get_profile_service

    service = MagicMock()
    client.app.dependency_overrides[get_profile_service] = lambda: service
    yield service
    client.app.dependency_overrides.clear()


class TestGetMe:
    def test_me_without_token_returns_401(self, client):
        """Sem header Authorization → 401."""
        res = client.get("/me")
        assert res.status_code == 401

    def test_me_with_malformed_header_returns_401(self, client):
        """Header sem 'Bearer ' → 401."""
        res = client.get("/me", headers={"Authorization": "abc123"})
        assert res.status_code == 401

    def test_me_with_valid_token_returns_profile(
        self, client, mock_current_user, mock_profile_service
    ):
        """Com token válido → 200 com dados do user."""
        mock_profile_service.get_me.return_value = {
            "user_id": "uuid-abc",
            "email": "user@example.com",
            "nome": "Fulano",
        }

        res = client.get("/me", headers={"Authorization": "Bearer fake-token"})

        assert res.status_code == 200
        body = res.json()
        assert body["user_id"] == "uuid-abc"
        assert body["email"] == "user@example.com"
        assert body["nome"] == "Fulano"
        mock_profile_service.get_me.assert_called_once_with("uuid-abc", "user@example.com")