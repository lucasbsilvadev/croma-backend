"""
Testes da rota pública do webhook MP.
Valida assinatura HMAC de verdade com o MPClient real.
"""
import hashlib
import hmac
import json
from unittest.mock import MagicMock

import pytest


MP_SECRET = "test-secret"


def _sign(data_id: str, request_id: str, ts: str, secret: str = MP_SECRET) -> str:
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


@pytest.fixture
def mock_service(client):
    from app.routes import webhook_routes
    svc = MagicMock()
    client.app.dependency_overrides[webhook_routes.get_payment_service] = lambda: svc
    yield svc
    client.app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def patch_secret(monkeypatch):
    """Força o secret de teste no módulo do MPClient."""
    from app.config import settings as settings_module
    monkeypatch.setattr(settings_module.settings, "mp_webhook_secret", MP_SECRET)


def _post(client, body: dict, *, data_id: str, ts: str = "1234567890",
          request_id: str = "req-abc", secret: str = MP_SECRET):
    raw = json.dumps(body).encode()
    sig = _sign(data_id, request_id, ts, secret=secret)
    return client.post(
        f"/webhooks/mercadopago?data.id={data_id}",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "x-signature": sig,
            "x-request-id": request_id,
        },
    )


# ============================================================
# Assinatura HMAC
# ============================================================


class TestWebhookSignature:
    def test_valid_signature_returns_200(self, client, mock_service):
        mock_service.process_webhook.return_value = {"received": True, "duplicate": False}
        res = _post(
            client,
            {"type": "payment", "data": {"id": "777"}},
            data_id="777",
        )
        assert res.status_code == 200
        assert res.json() == {"received": True}

    def test_missing_signature_returns_401(self, client, mock_service):
        res = client.post(
            "/webhooks/mercadopago?data.id=777",
            json={"type": "payment", "data": {"id": "777"}},
        )
        assert res.status_code == 401

    def test_malformed_signature_returns_401(self, client, mock_service):
        res = client.post(
            "/webhooks/mercadopago?data.id=777",
            json={},
            headers={"x-signature": "garbage"},
        )
        assert res.status_code == 401

    def test_wrong_secret_returns_401(self, client, mock_service):
        res = _post(
            client,
            {"type": "payment", "data": {"id": "777"}},
            data_id="777",
            secret="wrong-secret",
        )
        assert res.status_code == 401
        mock_service.process_webhook.assert_not_called()

    def test_wrong_data_id_returns_401(self, client, mock_service):
        """Assina com data_id A, envia data_id B no query → falha."""
        raw = json.dumps({"type": "payment", "data": {"id": "999"}}).encode()
        sig = _sign("777", "req-abc", "1234567890")  # assina 777
        res = client.post(
            "/webhooks/mercadopago?data.id=999",  # envia 999
            content=raw,
            headers={
                "Content-Type": "application/json",
                "x-signature": sig,
                "x-request-id": "req-abc",
            },
        )
        assert res.status_code == 401


# ============================================================
# Delegação ao service
# ============================================================


class TestWebhookDelegation:
    def test_calls_service_with_parsed_event(self, client, mock_service):
        mock_service.process_webhook.return_value = {"received": True, "duplicate": False}
        _post(
            client,
            {"type": "payment", "data": {"id": "777"}},
            data_id="777",
        )
        kwargs = mock_service.process_webhook.call_args.kwargs
        assert kwargs["event_type"] == "payment"
        assert kwargs["external_resource_id"] == "777"
        assert kwargs["external_event_id"]  # não vazio

    def test_duplicate_still_returns_200(self, client, mock_service):
        mock_service.process_webhook.return_value = {"received": True, "duplicate": True}
        res = _post(
            client,
            {"type": "payment", "data": {"id": "777"}},
            data_id="777",
        )
        assert res.status_code == 200