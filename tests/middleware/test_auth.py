"""
Testes unitários do middleware de autenticação.
Mocka httpx e ProfileRepository — não bate no Supabase real.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.middleware.auth import (
    _extract_nome_from_metadata,
    get_current_admin_user,
    get_current_user,
)
from app.utils.exceptions import AuthError, PermissionDeniedError


# ============================================================
# Helpers
# ============================================================


def _fake_request(request_id: str | None = "req-abc"):
    """Mock de Request com state.request_id."""
    request = MagicMock()
    request.state.request_id = request_id
    return request


def _fake_credentials(token: str = "fake-token"):
    creds = MagicMock()
    creds.credentials = token
    return creds


def _fake_httpx_response(status_code: int, json_data: dict):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    if status_code >= 400:
        # raise_for_status levanta HTTPStatusError
        import httpx

        def raise_status():
            raise httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=MagicMock(status_code=status_code),
            )

        response.raise_for_status.side_effect = raise_status
    else:
        response.raise_for_status.return_value = None
    return response


# ============================================================
# _extract_nome_from_metadata
# ============================================================


class TestExtractNomeFromMetadata:
    def test_prefers_nome_key(self):
        """Nosso metadata (signup email/senha) usa 'nome'."""
        data = {"user_metadata": {"nome": "Fulano", "full_name": "Ignorado"}}
        assert _extract_nome_from_metadata(data, "a@b.com") == "Fulano"

    def test_falls_back_to_full_name(self):
        """Google preenche 'full_name'."""
        data = {"user_metadata": {"full_name": "João Silva"}}
        assert _extract_nome_from_metadata(data, "a@b.com") == "João Silva"

    def test_falls_back_to_name(self):
        """Alguns providers usam só 'name'."""
        data = {"user_metadata": {"name": "Maria"}}
        assert _extract_nome_from_metadata(data, "a@b.com") == "Maria"

    def test_strips_whitespace(self):
        """Nome com espaços é limpo."""
        data = {"user_metadata": {"nome": "  Fulano  "}}
        assert _extract_nome_from_metadata(data, "a@b.com") == "Fulano"

    def test_ignores_empty_strings(self):
        """String vazia não conta — cai pro próximo candidato."""
        data = {"user_metadata": {"nome": "   ", "full_name": "João"}}
        assert _extract_nome_from_metadata(data, "a@b.com") == "João"

    def test_falls_back_to_email_prefix(self):
        """Sem metadata utilizável, usa prefixo do email."""
        data = {"user_metadata": {}}
        assert _extract_nome_from_metadata(data, "joao.silva@example.com") == "joao.silva"

    def test_falls_back_to_default_when_no_email_and_no_metadata(self):
        """Sem nada, retorna 'Usuário' — nunca quebra."""
        data = {}
        assert _extract_nome_from_metadata(data, None) == "Usuário"

    def test_handles_missing_user_metadata_key(self):
        """data sem user_metadata não deve dar KeyError."""
        data = {"id": "uuid-1", "email": "a@b.com"}
        assert _extract_nome_from_metadata(data, "a@b.com") == "a"


# ============================================================
# get_current_user
# ============================================================


class TestGetCurrentUser:
    async def test_raises_when_no_credentials(self):
        """Sem header Authorization → AuthError."""
        repo = MagicMock()
        with pytest.raises(AuthError, match="ausente"):
            await get_current_user(_fake_request(), None, repo)

    async def test_raises_when_empty_token(self):
        """Header presente mas sem valor → AuthError."""
        repo = MagicMock()
        creds = _fake_credentials("")
        with pytest.raises(AuthError, match="vazio"):
            await get_current_user(_fake_request(), creds, repo)

    async def test_raises_on_invalid_token_and_logs_event(self, caplog):
        """Supabase devolve 401 → AuthError + log AUTH_TOKEN_INVALID."""
        caplog.set_level(logging.WARNING, logger="app.middleware.auth")
        repo = MagicMock()

        with patch("app.middleware.auth.httpx.get") as mock_get:
            mock_get.return_value = _fake_httpx_response(401, {})

            with pytest.raises(AuthError, match="inválido"):
                await get_current_user(_fake_request(), _fake_credentials(), repo)

        events = [getattr(r, "event", None) for r in caplog.records]
        assert "AUTH_TOKEN_INVALID" in events

    async def test_raises_on_httpx_network_error(self, caplog):
        """Falha de rede → AuthError + log."""
        caplog.set_level(logging.WARNING, logger="app.middleware.auth")
        repo = MagicMock()

        with patch("app.middleware.auth.httpx.get") as mock_get:
            import httpx

            mock_get.side_effect = httpx.ConnectError("network down")

            with pytest.raises(AuthError, match="Falha ao validar"):
                await get_current_user(_fake_request(), _fake_credentials(), repo)

        events = [getattr(r, "event", None) for r in caplog.records]
        assert "AUTH_TOKEN_INVALID" in events

    async def test_raises_when_response_has_no_user_id(self, caplog):
        """Resposta sem 'id' → AuthError + log."""
        caplog.set_level(logging.WARNING, logger="app.middleware.auth")
        repo = MagicMock()

        with patch("app.middleware.auth.httpx.get") as mock_get:
            mock_get.return_value = _fake_httpx_response(200, {"email": "a@b.com"})

            with pytest.raises(AuthError, match="inválido"):
                await get_current_user(_fake_request(), _fake_credentials(), repo)

        events = [getattr(r, "event", None) for r in caplog.records]
        assert "AUTH_TOKEN_INVALID" in events

    async def test_returns_user_when_profile_exists(self):
        """Happy path: token válido, profile existe."""
        repo = MagicMock()
        repo.get_by_user_id.return_value = {
            "user_id": "u1",
            "nome": "Fulano",
            "role": "user",
        }

        with patch("app.middleware.auth.httpx.get") as mock_get:
            mock_get.return_value = _fake_httpx_response(
                200, {"id": "u1", "email": "a@b.com"}
            )

            user = await get_current_user(_fake_request(), _fake_credentials(), repo)

        assert user == {"user_id": "u1", "email": "a@b.com", "role": "user"}
        repo.ensure_profile.assert_not_called()

    async def test_creates_profile_when_missing_and_logs_oauth_event(self, caplog):
        """
        Usuário OAuth primeira vez: profile não existe → cria + log.
        """
        caplog.set_level(logging.INFO, logger="app.middleware.auth")

        repo = MagicMock()
        repo.get_by_user_id.return_value = None
        repo.ensure_profile.return_value = {
            "user_id": "u-oauth",
            "nome": "João Silva",
            "role": "user",
        }

        with patch("app.middleware.auth.httpx.get") as mock_get:
            mock_get.return_value = _fake_httpx_response(
                200,
                {
                    "id": "u-oauth",
                    "email": "joao@gmail.com",
                    "user_metadata": {"full_name": "João Silva"},
                },
            )

            user = await get_current_user(_fake_request(), _fake_credentials(), repo)

        assert user == {"user_id": "u-oauth", "email": "joao@gmail.com", "role": "user"}
        repo.ensure_profile.assert_called_once_with(
            user_id="u-oauth", nome="João Silva"
        )

        events = [getattr(r, "event", None) for r in caplog.records]
        assert "AUTH_OAUTH_PROFILE_CREATED" in events

    async def test_raises_when_ensure_profile_returns_none(self):
        """ensure_profile devolvendo None é bug — não passar silencioso."""
        repo = MagicMock()
        repo.get_by_user_id.return_value = None
        repo.ensure_profile.return_value = None

        with patch("app.middleware.auth.httpx.get") as mock_get:
            mock_get.return_value = _fake_httpx_response(
                200, {"id": "u-x", "email": "a@b.com"}
            )

            with pytest.raises(AuthError, match="Falha ao criar perfil"):
                await get_current_user(_fake_request(), _fake_credentials(), repo)

    async def test_never_logs_token_in_any_event(self, caplog):
        """
        Segurança: o token nunca pode aparecer em log,
        nem no caminho feliz nem no de erro.
        """
        caplog.set_level(logging.DEBUG, logger="app.middleware.auth")

        repo = MagicMock()
        repo.get_by_user_id.return_value = {"user_id": "u1", "nome": "X", "role": "user"}

        with patch("app.middleware.auth.httpx.get") as mock_get:
            mock_get.return_value = _fake_httpx_response(
                200, {"id": "u1", "email": "a@b.com"}
            )
            await get_current_user(
                _fake_request(), _fake_credentials("TOKEN-SUPER-SECRETO"), repo
            )

        for record in caplog.records:
            payload = " ".join(str(v) for v in record.__dict__.values())
            assert "TOKEN-SUPER-SECRETO" not in payload


# ============================================================
# get_current_admin_user
# ============================================================


class TestGetCurrentAdminUser:
    async def test_returns_user_when_admin(self):
        """role=admin passa."""
        user = {"user_id": "u1", "email": "a@b.com", "role": "admin"}
        result = await get_current_admin_user(current_user=user)
        assert result == user

    async def test_raises_when_role_is_user(self):
        """role=user é rejeitado com 403."""
        user = {"user_id": "u1", "email": "a@b.com", "role": "user"}
        with pytest.raises(PermissionDeniedError):
            await get_current_admin_user(current_user=user)

    async def test_raises_when_role_is_missing(self):
        """Sem role → 403 (fail-closed, não assume admin)."""
        user = {"user_id": "u1", "email": "a@b.com"}
        with pytest.raises(PermissionDeniedError):
            await get_current_admin_user(current_user=user)

    async def test_raises_when_role_is_unknown_value(self):
        """role com valor inesperado (ex: 'superadmin') → 403, não passa."""
        user = {"user_id": "u1", "email": "a@b.com", "role": "superadmin"}
        with pytest.raises(PermissionDeniedError):
            await get_current_admin_user(current_user=user)