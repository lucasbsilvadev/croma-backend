"""
Testes unitários do AuthService.
Mocka httpx.post + TermsService + TermsRepository — não bate no Supabase real.

Desde LGPD-01, o register:
  - valida terms_version via TermsService.validate_version (fail-closed)
  - grava aceite com version + document_hash.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.services import auth_service as auth_service_module
from app.services.auth_service import AuthService
from app.utils.exceptions import AuthError, ValidationError

_CPF = "11144477735"
_TERMS_VERSION = "2026-10-13"
_FAKE_DOCUMENT_HASH = "sha256-fake-hash"


def _fake_httpx_response(status_code: int, json_data: dict | None = None):
    """Helper: cria um mock de httpx.Response."""
    response = MagicMock()
    response.status_code = status_code
    response.content = b"x" if json_data else b""
    response.json.return_value = json_data if json_data is not None else {}
    return response


@pytest.fixture(autouse=True)
def _mock_terms_service_class(monkeypatch):
    """Substitui TermsService no módulo auth_service por um MagicMock.

    validate_version devolve uma linha fake com document_hash — assim o
    register tem o que gravar no aceite sem tocar em terms_versions.
    """
    fake_instance = MagicMock()
    fake_instance.validate_version.return_value = {
        "version": _TERMS_VERSION,
        "document_hash": _FAKE_DOCUMENT_HASH,
        "ativo": True,
    }
    fake_cls = MagicMock(return_value=fake_instance)
    monkeypatch.setattr(auth_service_module, "TermsService", fake_cls)
    return fake_instance


@pytest.fixture(autouse=True)
def _mock_terms_repo_class(monkeypatch):
    """Substitui TermsRepository no módulo auth_service por um MagicMock."""
    fake_instance = MagicMock()
    fake_cls = MagicMock(return_value=fake_instance)
    monkeypatch.setattr(auth_service_module, "TermsRepository", fake_cls)
    return fake_instance


# ============================================================
# REGISTER
# ============================================================


class TestRegister:
    def test_register_creates_profile_on_success(self):
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

            result = service.register(
                "Fulano", "a@b.com", "SenhaSegura123!", _CPF, _TERMS_VERSION
            )

        assert result["user_id"] == "uuid-1"
        assert result["access_token"] == "tok"
        repo.ensure_profile.assert_called_once_with(
            user_id="uuid-1", nome="Fulano", cpf_cnpj=_CPF
        )

    def test_register_validates_terms_version_before_supabase(
        self, _mock_terms_service_class
    ):
        """Fail-closed: validate_version roda ANTES do httpx.post."""
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200,
                {"user": {"id": "uuid-1"}, "access_token": "tok", "refresh_token": "ref"},
            )
            service.register(
                "Fulano", "a@b.com", "SenhaSegura123!", _CPF, _TERMS_VERSION
            )

        _mock_terms_service_class.validate_version.assert_called_once_with(
            _TERMS_VERSION
        )

    def test_register_aborts_when_terms_version_invalid(
        self, _mock_terms_service_class
    ):
        """Versão inválida → ValidationError e httpx.post nem é chamado."""
        _mock_terms_service_class.validate_version.side_effect = ValidationError(
            "Versão dos termos inválida ou expirada"
        )

        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            with pytest.raises(ValidationError, match="inválida"):
                service.register(
                    "Fulano", "a@b.com", "SenhaSegura123!", _CPF, "banana"
                )
            mock_post.assert_not_called()

    def test_register_creates_terms_acceptance_with_document_hash(
        self, _mock_terms_repo_class
    ):
        """Register OK grava aceite com version + document_hash."""
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200,
                {"user": {"id": "uuid-1"}, "access_token": "tok", "refresh_token": "ref"},
            )
            service.register(
                "Fulano", "a@b.com", "SenhaSegura123!", _CPF, _TERMS_VERSION
            )

        _mock_terms_repo_class.create_acceptance.assert_called_once_with(
            user_id="uuid-1",
            terms_version=_TERMS_VERSION,
            document_hash=_FAKE_DOCUMENT_HASH,
        )

    def test_register_logs_success_event(self, caplog):
        caplog.set_level(logging.INFO, logger="app.services.auth_service")
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200,
                {"user": {"id": "uuid-1"}, "access_token": "tok", "refresh_token": "ref"},
            )
            service.register(
                "Fulano", "a@b.com", "SenhaSegura123!", _CPF, _TERMS_VERSION
            )

        success = [
            r for r in caplog.records
            if getattr(r, "event", None) == "AUTH_REGISTER_SUCCESS"
        ]
        assert len(success) == 1
        assert success[0].user_id == "uuid-1"

    def test_register_raises_validation_on_duplicate_email(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                422, {"msg": "User already registered"}
            )

            with pytest.raises(ValidationError, match="já cadastrado"):
                service.register(
                    "Fulano", "a@b.com", "SenhaSegura123!", _CPF, _TERMS_VERSION
                )

    def test_register_raises_validation_on_unknown_error(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(500, {"msg": "Internal error"})

            with pytest.raises(ValidationError):
                service.register(
                    "Fulano", "a@b.com", "SenhaSegura123!", _CPF, _TERMS_VERSION
                )

    def test_register_returns_empty_tokens_when_confirm_email_on(self):
        repo = MagicMock()
        service = AuthService(profile_repo=repo)

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200,
                {
                    "id": "uuid-confirm",
                    "email": "a@b.com",
                    "confirmation_sent_at": "2026-10-03T20:00:00Z",
                },
            )

            result = service.register(
                "Fulano", "a@b.com", "SenhaSegura123!", _CPF, _TERMS_VERSION
            )

        assert result["user_id"] == "uuid-confirm"
        assert result["access_token"] == ""
        assert result["refresh_token"] == ""
        repo.ensure_profile.assert_called_once_with(
            user_id="uuid-confirm", nome="Fulano", cpf_cnpj=_CPF
        )

    def test_register_raises_when_response_has_no_user_id(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(200, {"foo": "bar"})

            with pytest.raises(ValidationError):
                service.register(
                    "Fulano", "a@b.com", "SenhaSegura123!", _CPF, _TERMS_VERSION
                )

    def test_register_never_logs_password_or_tokens(self, caplog):
        caplog.set_level(logging.DEBUG, logger="app.services.auth_service")
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200,
                {
                    "user": {"id": "uuid-1"},
                    "access_token": "super-secret",
                    "refresh_token": "refresh-secret",
                },
            )
            service.register(
                "Fulano", "a@b.com", "SenhaUltraSecreta123!", _CPF, _TERMS_VERSION
            )

        for record in caplog.records:
            payload = " ".join(str(v) for v in record.__dict__.values())
            assert "SenhaUltraSecreta123!" not in payload
            assert "super-secret" not in payload
            assert "refresh-secret" not in payload


# ============================================================
# LOGIN
# ============================================================


class TestLogin:
    def test_login_returns_tokens_on_success(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200,
                {"user": {"id": "uuid-1"}, "access_token": "tok", "refresh_token": "ref"},
            )
            result = service.login("a@b.com", "SenhaSegura123!")

        assert result["access_token"] == "tok"
        assert result["user_id"] == "uuid-1"

    def test_login_logs_success_event(self, caplog):
        caplog.set_level(logging.INFO, logger="app.services.auth_service")
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200,
                {"user": {"id": "uuid-1"}, "access_token": "tok", "refresh_token": "ref"},
            )
            service.login("a@b.com", "SenhaSegura123!")

        events = [getattr(r, "event", None) for r in caplog.records]
        assert "AUTH_LOGIN_SUCCESS" in events

    def test_login_raises_auth_error_on_invalid_credentials(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                400,
                {"error": "invalid_grant", "error_description": "Invalid login credentials"},
            )
            with pytest.raises(AuthError):
                service.login("a@b.com", "SenhaErrada123!")

    def test_login_logs_failure_without_email(self, caplog):
        caplog.set_level(logging.DEBUG, logger="app.services.auth_service")
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(400, {"error": "invalid_grant"})
            with pytest.raises(AuthError):
                service.login("usuario-alvo@exemplo.com", "SenhaErrada123!")

        for record in caplog.records:
            payload = " ".join(str(v) for v in record.__dict__.values())
            assert "usuario-alvo@exemplo.com" not in payload

    def test_login_raises_auth_error_when_no_access_token(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200, {"user": {"id": "uuid-1"}, "access_token": None}
            )
            with pytest.raises(AuthError, match="não confirmado"):
                service.login("a@b.com", "SenhaSegura123!")

    def test_login_handles_missing_user_field_gracefully(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(
                200, {"access_token": "tok", "refresh_token": "ref"}
            )
            with pytest.raises((AuthError, KeyError, TypeError)):
                service.login("a@b.com", "SenhaSegura123!")


# ============================================================
# FORGOT PASSWORD
# ============================================================


class TestForgotPassword:
    def test_never_raises_even_on_error(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.side_effect = Exception("network down")
            service.forgot_password("naoexiste@b.com")

    def test_logs_failure_event_silently(self, caplog):
        caplog.set_level(logging.INFO, logger="app.services.auth_service")
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.side_effect = Exception("network down")
            service.forgot_password("naoexiste@b.com")

        events = [getattr(r, "event", None) for r in caplog.records]
        assert "AUTH_FORGOT_PASSWORD_FAILED" in events

    def test_calls_supabase_with_email(self):
        service = AuthService(profile_repo=MagicMock())

        with patch("app.services.auth_service.httpx.post") as mock_post:
            mock_post.return_value = _fake_httpx_response(200, {})
            service.forgot_password("a@b.com")

        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["email"] == "a@b.com"