"""
Testes unitários do AuthService.
Mocka httpx.post — não bate no Supabase real.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.auth_service import AuthService
from app.utils.exceptions import AuthError, ValidationError


def _fake_httpx_response(status_code: int, json_data: dict):
    """Helper: cria um mock de httpx.Response."""
    response = MagicMock()
    response.status_code = status_code
    response.content = b"x" if json_data else b""
    response.json.return_value = json_data
    return response


class TestRegister:
    def test_register_creates_profile_on_success(self):
        """Signup OK no Supabase → cria profile local."""
        repo = MagicMock()
        service = AuthService(profile_repo=repo)

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200,
                {
                    "user": {"id": "uuid-1"},
                    "access_token": "tok",
                    "refresh_token": "ref",
                },
            )

            result = service.register("Fulano", "a@b.com", "senhaSegura123")

        assert result["user_id"] == "uuid-1"
        assert result["access_token"] == "tok"
        repo.create.assert_called_once_with(user_id="uuid-1", nome="Fulano")

    def test_register_raises_validation_on_duplicate_email(self):
        """Supabase retorna erro de 'already registered' → ValidationError."""
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                422,
                {"msg": "User already registered"},
            )

            with pytest.raises(ValidationError, match="já cadastrado"):
                service.register("Fulano", "a@b.com", "senhaSegura123")

    def test_register_raises_validation_on_unknown_error(self):
        """Supabase retorna erro genérico → ValidationError genérico."""
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                500,
                {"msg": "Internal error"},
            )

            with pytest.raises(ValidationError):
                service.register("Fulano", "a@b.com", "senhaSegura123")

    def test_register_ignores_conflict_on_profile_creation(self):
        """Se profile já existe (trigger rodou), não falha o signup."""
        from app.utils.exceptions import ConflictError

        repo = MagicMock()
        repo.create.side_effect = ConflictError()
        service = AuthService(profile_repo=repo)

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200,
                {"user": {"id": "uuid-1"}, "access_token": "tok", "refresh_token": "ref"},
            )

            result = service.register("Fulano", "a@b.com", "senhaSegura123")

        assert result["user_id"] == "uuid-1"


class TestLogin:
    def test_login_returns_tokens_on_success(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200,
                {
                    "user": {"id": "uuid-1"},
                    "access_token": "tok",
                    "refresh_token": "ref",
                },
            )

            result = service.login("a@b.com", "senhaSegura123")

        assert result["access_token"] == "tok"
        assert result["user_id"] == "uuid-1"

    def test_login_raises_auth_error_on_invalid_credentials(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                400,
                {"error": "invalid_grant", "error_description": "Invalid login credentials"},
            )

            with pytest.raises(AuthError):
                service.login("a@b.com", "errada")

    def test_login_raises_auth_error_when_no_access_token(self):
        """Caso raro: 200 mas sem access_token (email não confirmado)."""
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200,
                {"user": {"id": "uuid-1"}, "access_token": None},
            )

            with pytest.raises(AuthError, match="não confirmado"):
                service.login("a@b.com", "senhaSegura123")


class TestForgotPassword:
    def test_never_raises_even_on_error(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.side_effect = Exception("network down")

            # Não deve lançar
            service.forgot_password("naoexiste@b.com")

    def test_calls_supabase_with_email(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(200, {})

            service.forgot_password("a@b.com")

        # Confirma que foi chamado com o email no payload
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["email"] == "a@b.com"
