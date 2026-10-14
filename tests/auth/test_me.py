"""
Testes unitários dos endpoints GET /me e PATCH /me.
Mocka get_current_user — não bate no Supabase real.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_current_user(client):
    from app.middleware.auth import get_current_user

    fake = {"user_id": "uuid-abc", "email": "user@example.com", "role": "user"}
    client.app.dependency_overrides[get_current_user] = lambda: fake
    yield fake
    client.app.dependency_overrides.clear()


@pytest.fixture
def mock_profile_service(client):
    from app.routes.profile_routes import get_profile_service

    service = MagicMock()
    client.app.dependency_overrides[get_profile_service] = lambda: service
    yield service
    client.app.dependency_overrides.clear()


def _me_response(**overrides):
    base = {
        "user_id": "uuid-abc",
        "email": "user@example.com",
        "nome": "Fulano",
        "role": "user",
        "cpf_cnpj": None,
        "tipo_pessoa": None,
        "terms_version": None,
        "terms_accepted_at": None,
    }
    base.update(overrides)
    return base


class TestGetMe:
    def test_me_without_token_returns_401(self, client):
        res = client.get("/me")
        assert res.status_code == 401

    def test_me_with_malformed_header_returns_401(self, client):
        res = client.get("/me", headers={"Authorization": "abc123"})
        assert res.status_code == 401

    def test_me_returns_full_profile(
        self, client, mock_current_user, mock_profile_service
    ):
        mock_profile_service.get_me.return_value = _me_response()

        res = client.get("/me", headers={"Authorization": "Bearer fake-token"})

        assert res.status_code == 200
        body = res.json()
        assert body["user_id"] == "uuid-abc"
        assert body["email"] == "user@example.com"
        assert body["nome"] == "Fulano"
        assert body["role"] == "user"
        mock_profile_service.get_me.assert_called_once_with(
            "uuid-abc", "user@example.com"
        )

    def test_me_reflects_admin_role(self, client, mock_current_user, mock_profile_service):
        mock_profile_service.get_me.return_value = _me_response(
            nome="Admin", role="admin"
        )

        res = client.get("/me", headers={"Authorization": "Bearer fake-token"})

        assert res.status_code == 200
        assert res.json()["role"] == "admin"

    def test_me_includes_terms_acceptance(
        self, client, mock_current_user, mock_profile_service
    ):
        """Se o usuário aceitou termos, /me devolve versão e timestamp."""
        mock_profile_service.get_me.return_value = _me_response(
            terms_version="v0-template",
            terms_accepted_at="2026-10-13T12:00:00+00:00",
        )

        res = client.get("/me", headers={"Authorization": "Bearer fake-token"})

        assert res.status_code == 200
        body = res.json()
        assert body["terms_version"] == "v0-template"
        # FastAPI/Pydantic serializa UTC como "Z" (ISO 8601).
        # Aceitamos tanto "Z" quanto "+00:00" — são equivalentes.
        accepted = body["terms_accepted_at"]
        assert accepted in (
            "2026-10-13T12:00:00Z",
            "2026-10-13T12:00:00+00:00",
        )


class TestUpdateMe:
    def test_patch_without_token_returns_401(self, client):
        res = client.patch("/me", json={"nome": "Novo"})
        assert res.status_code == 401

    def test_patch_nome_ok(
        self, client, mock_current_user, mock_profile_service
    ):
        mock_profile_service.update_me.return_value = _me_response(nome="Novo Nome")

        res = client.patch(
            "/me",
            json={"nome": "Novo Nome"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert res.status_code == 200
        assert res.json()["nome"] == "Novo Nome"
        mock_profile_service.update_me.assert_called_once_with(
            "uuid-abc",
            "user@example.com",
            {"nome": "Novo Nome"},
        )

    def test_patch_cpf_cnpj_ok(
        self, client, mock_current_user, mock_profile_service
    ):
        mock_profile_service.update_me.return_value = _me_response(
            cpf_cnpj="11144477735", tipo_pessoa="fisica"
        )

        res = client.patch(
            "/me",
            json={"cpf_cnpj": "111.444.777-35"},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert res.status_code == 200
        body = res.json()
        assert body["cpf_cnpj"] == "11144477735"
        assert body["tipo_pessoa"] == "fisica"
        # CPF chega normalizado (só dígitos) no service.
        mock_profile_service.update_me.assert_called_once_with(
            "uuid-abc",
            "user@example.com",
            {"cpf_cnpj": "11144477735"},
        )

    def test_patch_cpf_invalid_returns_422(self, client, mock_current_user):
        """CPF com DV errado é rejeitado pelo Pydantic ANTES do service."""
        res = client.patch(
            "/me",
            json={"cpf_cnpj": "111.444.777-36"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert res.status_code == 422

    def test_patch_nome_too_short_returns_422(self, client, mock_current_user):
        res = client.patch(
            "/me",
            json={"nome": "A"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert res.status_code == 422

    def test_patch_empty_body_returns_ok(
        self, client, mock_current_user, mock_profile_service
    ):
        """PATCH sem campos é idempotente — devolve o estado atual."""
        mock_profile_service.update_me.return_value = _me_response()

        res = client.patch(
            "/me",
            json={},
            headers={"Authorization": "Bearer fake-token"},
        )

        assert res.status_code == 200
        # exclude_none no model_dump → service recebe dict vazio.
        mock_profile_service.update_me.assert_called_once_with(
            "uuid-abc", "user@example.com", {}
        )

    def test_patch_cpf_already_set_returns_409(
        self, client, mock_current_user, mock_profile_service
    ):
        """Service rejeita troca de CPF já definido → 409."""
        from app.utils.exceptions import ConflictError

        mock_profile_service.update_me.side_effect = ConflictError(
            "CPF/CNPJ já cadastrado. Alteração exige fluxo específico."
        )

        res = client.patch(
            "/me",
            json={"cpf_cnpj": "11144477735"},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert res.status_code == 409