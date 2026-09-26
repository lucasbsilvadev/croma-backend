from unittest.mock import MagicMock, patch

import pytest

from app.services.auth_service import AuthService
from app.utils.exceptions import AuthError, ValidationError


def test_login_raises_on_invalid():
    with patch("app.services.auth_service.supabase_public") as mock_sb:
        mock_sb.auth.sign_in_with_password.side_effect = Exception("invalid")
        service = AuthService(profile_repo=MagicMock())
        with pytest.raises(AuthError):
            service.login("a@b.com", "senha")


def test_register_creates_profile():
    with patch("app.services.auth_service.supabase_admin") as mock_admin:
        mock_admin.auth.sign_up.return_value = MagicMock(
            user=MagicMock(id="uuid-1"),
            session=MagicMock(access_token="tok", refresh_token="ref"),
        )
        repo = MagicMock()
        service = AuthService(profile_repo=repo)
        service.register("Fulano", "a@b.com", "senha12345")
        repo.create.assert_called_once_with(user_id="uuid-1", nome="Fulano")


def test_forgot_password_silent_on_error():
    with patch("app.services.auth_service.supabase_public") as mock_sb:
        mock_sb.auth.reset_password_email.side_effect = Exception("not found")
        service = AuthService(profile_repo=MagicMock())
        # Não deve lançar
        service.forgot_password("naoexiste@b.com")