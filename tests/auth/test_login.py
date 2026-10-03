from unittest.mock import MagicMock

from app.utils.exceptions import AuthError


def test_login_success(client):
    mock_service = MagicMock()
    mock_service.login.return_value = {
        "user_id": "uuid-123",
        "access_token": "tok",
        "refresh_token": "ref",
    }

    from app.routes import auth_routes

    client.app.dependency_overrides[auth_routes.get_auth_service] = lambda: mock_service
    try:
        res = client.post("/auth/login", json={"email": "a@b.com", "password": "senha12345"})
        assert res.status_code == 200
    finally:
        client.app.dependency_overrides.clear()


def test_login_invalid_credentials(client):
    mock_service = MagicMock()
    mock_service.login.side_effect = AuthError()

    from app.routes import auth_routes

    client.app.dependency_overrides[auth_routes.get_auth_service] = lambda: mock_service
    try:
        res = client.post("/auth/login", json={"email": "a@b.com", "password": "senha12345"})
        assert res.status_code == 401
    finally:
        client.app.dependency_overrides.clear()
