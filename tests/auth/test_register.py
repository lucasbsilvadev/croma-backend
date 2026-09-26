from unittest.mock import MagicMock


def test_register_success(client, fake_user, monkeypatch):
    mock_service = MagicMock()
    mock_service.register.return_value = {
        "user_id": "uuid-123",
        "access_token": "tok",
        "refresh_token": "ref",
    }

    from app.routes import auth_routes

    client.app.dependency_overrides[auth_routes.get_auth_service] = lambda: mock_service

    res = client.post("/auth/register", json=fake_user)

    assert res.status_code == 201
    assert res.json()["user_id"] == "uuid-123"
    mock_service.register.assert_called_once()


def test_register_invalid_email(client, fake_user):
    fake_user["email"] = "nao-e-email"
    res = client.post("/auth/register", json=fake_user)
    assert res.status_code == 422


def test_register_short_password(client, fake_user):
    fake_user["password"] = "123"
    res = client.post("/auth/register", json=fake_user)
    assert res.status_code == 422