"""Testes das rotas de pagamento (cliente). Foco: auth, ownership, idempotency."""
from unittest.mock import MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def mock_service(client):
    from app.routes import payment_routes
    svc = MagicMock()
    client.app.dependency_overrides[payment_routes.get_payment_service] = lambda: svc
    yield svc
    client.app.dependency_overrides.clear()


@pytest.fixture
def mock_user(client):
    from app.middleware.auth import get_current_user
    fake = {"user_id": "u1", "email": "a@b.com", "role": "user"}
    client.app.dependency_overrides[get_current_user] = lambda: fake
    yield fake
    client.app.dependency_overrides.clear()


def _idem_header():
    return {"Idempotency-Key": str(uuid4())}


# ============================================================
# PIX
# ============================================================


class TestPayWithPix:
    def test_without_token_returns_401(self, client, mock_service):
        res = client.post(
            "/orders/o1/pay/pix",
            headers=_idem_header(),
        )
        assert res.status_code == 401

    def test_without_idempotency_key_returns_422(self, client, mock_service, mock_user):
        res = client.post("/orders/o1/pay/pix")
        assert res.status_code == 422

    def test_with_malformed_idempotency_key_returns_422(
        self, client, mock_service, mock_user
    ):
        res = client.post(
            "/orders/o1/pay/pix",
            headers={"Idempotency-Key": "not-a-uuid"},
        )
        assert res.status_code == 422

    def test_ok_returns_201(self, client, mock_service, mock_user):
        mock_service.create_pix.return_value = {
            "payment_id": "777",
            "status": "pending",
            "qr_code": "00020126...",
            "qr_code_base64": "iVBOR...",
            "ticket_url": "https://mp/qr/777",
            "expires_at": "2026-10-05T00:00:00Z",
        }
        res = client.post(
            "/orders/o1/pay/pix",
            headers=_idem_header(),
        )
        assert res.status_code == 201
        assert res.json()["payment_id"] == "777"
        mock_service.create_pix.assert_called_once()
        kwargs = mock_service.create_pix.call_args.kwargs
        assert kwargs["user_id"] == "u1"
        assert kwargs["user_email"] == "a@b.com"
        assert kwargs["order_id"] == "o1"


# ============================================================
# CARTÃO
# ============================================================


class TestPayWithCard:
    def test_without_token_returns_401(self, client, mock_service):
        res = client.post(
            "/orders/o1/pay/card",
            headers=_idem_header(),
        )
        assert res.status_code == 401

    def test_ok_returns_201(self, client, mock_service, mock_user):
        mock_service.create_card_preference.return_value = {
            "preference_id": "pref-1",
            "init_point": "https://mp/checkout/pref-1",
            "sandbox_init_point": "https://sandbox.mp/pref-1",
        }
        res = client.post(
            "/orders/o1/pay/card",
            headers=_idem_header(),
        )
        assert res.status_code == 201
        assert res.json()["preference_id"] == "pref-1"