"""
Testes unitários do PaymentService.
Mocka MPClient e todos os repositórios — não bate em MP nem Supabase.
"""
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.payment_service import PaymentService
from app.utils.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mp():
    return MagicMock()


@pytest.fixture
def payment_repo():
    return MagicMock()


@pytest.fixture
def order_repo():
    return MagicMock()


@pytest.fixture
def profile_repo():
    return MagicMock()


@pytest.fixture
def service(mp, payment_repo, order_repo, profile_repo):
    return PaymentService(
        mp_client=mp,
        payment_repo=payment_repo,
        order_repo=order_repo,
        profile_repo=profile_repo,
    )


CPF = "11144477735"


def _order(
    *,
    id="o1",
    user_id="u1",
    status="created",
    payment_status="pending",
    payment_method=None,
    payment_external_id=None,
    total="115.00",
    frete="15.00",
):
    return {
        "id": id,
        "user_id": user_id,
        "address_id": "a1",
        "status": status,
        "subtotal": "100.00",
        "frete": frete,
        "total": total,
        "notes": None,
        "payment_status": payment_status,
        "payment_method": payment_method,
        "payment_external_id": payment_external_id,
        "created_at": "2026-10-04T00:00:00Z",
        "updated_at": "2026-10-04T00:00:00Z",
    }


def _profile(cpf=CPF):
    return {"user_id": "u1", "nome": "Fulano", "cpf_cnpj": cpf, "role": "user"}


def _mp_pix_response(payment_id="777", status="pending"):
    return {
        "id": payment_id,
        "status": status,
        "point_of_interaction": {
            "transaction_data": {
                "qr_code": "00020126...",
                "qr_code_base64": "iVBORw0...",
                "ticket_url": "https://mp/qr/777",
            }
        },
        "date_of_expiration": "2026-10-05T00:00:00Z",
    }


# ============================================================
# Validação comum (PAYMENT-14)
# ============================================================


class TestValidateOrderForPayment:
    def test_raises_404_when_order_not_owned(self, service, order_repo):
        order_repo.get_by_id_and_user.return_value = None
        with pytest.raises(NotFoundError, match="Pedido"):
            service._validate_order_for_payment("u1", "o-x", "pix")

    def test_raises_conflict_when_already_paid(self, service, order_repo):
        order_repo.get_by_id_and_user.return_value = _order(payment_status="paid")
        with pytest.raises(ConflictError, match="não permite pagamento"):
            service._validate_order_for_payment("u1", "o1", "pix")

    def test_raises_conflict_when_other_method(self, service, order_repo):
        order_repo.get_by_id_and_user.return_value = _order(payment_method="pix")
        with pytest.raises(ConflictError, match="já tem cobrança"):
            service._validate_order_for_payment("u1", "o1", "credit_card")

    def test_raises_validation_when_total_zero(self, service, order_repo):
        order_repo.get_by_id_and_user.return_value = _order(total="0.00")
        with pytest.raises(ValidationError, match="Valor"):
            service._validate_order_for_payment("u1", "o1", "pix")

    def test_ok_returns_order(self, service, order_repo):
        order = _order()
        order_repo.get_by_id_and_user.return_value = order
        result = service._validate_order_for_payment("u1", "o1", "pix")
        assert result == order


# ============================================================
# CPF/CNPJ do pagador (PAYMENT-02)
# ============================================================


class TestGetUserCpfCnpj:
    def test_raises_when_profile_missing(self, service, profile_repo):
        profile_repo.get_by_user_id.return_value = None
        with pytest.raises(ValidationError, match="CPF/CNPJ não cadastrado"):
            service._get_user_cpf_cnpj("u1")

    def test_raises_when_cpf_invalid(self, service, profile_repo):
        profile_repo.get_by_user_id.return_value = _profile(cpf="11111111111")
        with pytest.raises(ValidationError, match="inválido"):
            service._get_user_cpf_cnpj("u1")

    def test_returns_normalized(self, service, profile_repo):
        profile_repo.get_by_user_id.return_value = _profile(cpf="111.444.777-35")
        assert service._get_user_cpf_cnpj("u1") == CPF


# ============================================================
# PIX (PAYMENT-15)
# ============================================================


class TestCreatePix:
    def test_creates_pix_and_persists_reference(
        self, service, mp, payment_repo, order_repo, profile_repo
    ):
        order_repo.get_by_id_and_user.return_value = _order()
        profile_repo.get_by_user_id.return_value = _profile()
        mp.new_idempotency_key.return_value = "idem-key"
        mp.create_pix_payment.return_value = _mp_pix_response()

        result = service.create_pix("u1", "a@b.com", "o1")

        assert result["payment_id"] == "777"
        assert result["qr_code"] == "00020126..."
        assert result["status"] == "pending"

        # Payload enviado ao MP (PAYMENT-02)
        call_kwargs = mp.create_pix_payment.call_args
        payload = call_kwargs[0][0]
        assert payload["payment_method_id"] == "pix"
        assert payload["external_reference"] == "o1"
        assert payload["transaction_amount"] == 115.00
        assert payload["payer"]["email"] == "a@b.com"
        assert payload["payer"]["identification"]["type"] == "CPF"
        assert payload["payer"]["identification"]["number"] == CPF

        # Persistiu referência no order
        payment_repo.update_payment_reference.assert_called_once_with(
            order_id="o1", payment_method="pix", payment_external_id="777",
        )

    def test_returns_existing_pix_when_already_created(self, service, mp, order_repo):
        """Idempotência PAYMENT-15: 2ª chamada não cria outra cobrança."""
        order_repo.get_by_id_and_user.return_value = _order(
            payment_method="pix", payment_external_id="777",
        )
        mp.get_payment.return_value = _mp_pix_response()

        service.create_pix("u1", "a@b.com", "o1")

        mp.get_payment.assert_called_once_with("777")
        mp.create_pix_payment.assert_not_called()

    def test_uses_cnpj_for_14_digits(self, service, mp, order_repo, profile_repo):
        """CNPJ válido → identification.type=CNPJ."""
        order_repo.get_by_id_and_user.return_value = _order()
        profile_repo.get_by_user_id.return_value = _profile(cpf="11222333000181")
        mp.create_pix_payment.return_value = _mp_pix_response()

        service.create_pix("u1", "a@b.com", "o1")

        payload = mp.create_pix_payment.call_args[0][0]
        assert payload["payer"]["identification"]["type"] == "CNPJ"
        assert payload["payer"]["identification"]["number"] == "11222333000181"


# ============================================================
# Cartão / Checkout Pro (PAYMENT-16)
# ============================================================


class TestCreateCardPreference:
    def test_creates_preference(self, service, mp, payment_repo, order_repo):
        order_repo.get_by_id_and_user.return_value = _order()
        order_repo.list_items_by_order.return_value = [
            {
                "product_nome": "Calça",
                "quantidade": 1,
                "preco_unitario": Decimal("100.00"),
            }
        ]
        mp.create_card_preference.return_value = {
            "id": "pref-1",
            "init_point": "https://mp/checkout/pref-1",
            "sandbox_init_point": "https://sandbox.mp/pref-1",
        }

        result = service.create_card_preference("u1", "a@b.com", "o1")

        assert result["preference_id"] == "pref-1"
        assert result["init_point"].startswith("https://mp/")

        payload = mp.create_card_preference.call_args[0][0]
        assert payload["external_reference"] == "o1"
        assert payload["payer"]["email"] == "a@b.com"
        # items = produto + frete
        titles = [i["title"] for i in payload["items"]]
        assert "Calça" in titles
        assert "Frete" in titles

        payment_repo.update_payment_reference.assert_called_once_with(
            order_id="o1",
            payment_method="credit_card",
            payment_external_id="pref-1",
        )

    def test_returns_existing_preference(self, service, mp, order_repo):
        order_repo.get_by_id_and_user.return_value = _order(
            payment_method="credit_card", payment_external_id="pref-1",
        )
        mp._request.return_value = {
            "id": "pref-1",
            "init_point": "https://mp/x",
            "sandbox_init_point": "https://sandbox.mp/x",
        }

        service.create_card_preference("u1", "a@b.com", "o1")

        mp.create_card_preference.assert_not_called()
        mp._request.assert_called_once_with("GET", "/checkout/preferences/pref-1")


# ============================================================
# Webhook (PAYMENT-04, 07, 08)
# ============================================================


class TestProcessWebhook:
    def test_persists_new_event_and_marks_processed(
        self, service, payment_repo, mp
    ):
        payment_repo.create_event.return_value = {"id": "evt-1"}
        payment_repo.get_order_by_external_id.return_value = None
        mp.get_payment.return_value = {
            "id": "777",
            "status": "approved",
            "external_reference": "o1",
        }
        service.order_repo.get_by_id = MagicMock(return_value=_order())

        result = service.process_webhook(
            event_type="payment",
            external_event_id="evt-1",
            external_resource_id="777",
            payload={"type": "payment", "data": {"id": "777"}},
        )

        assert result["duplicate"] is False
        payment_repo.create_event.assert_called_once()
        payment_repo.mark_event_processed.assert_called_once_with("evt-1")

    def test_duplicate_event_is_skipped(self, service, payment_repo):
        payment_repo.create_event.return_value = None  # unique violation

        result = service.process_webhook(
            event_type="payment",
            external_event_id="evt-1",
            external_resource_id="777",
            payload={},
        )

        assert result["duplicate"] is True
        payment_repo.mark_event_processed.assert_not_called()

    def test_event_persisted_but_processing_fails_does_not_mark(
        self, service, payment_repo, mp
    ):
        """PAYMENT-08: processed_at fica NULL pra reconciliação."""
        payment_repo.create_event.return_value = {"id": "evt-1"}
        mp.get_payment.side_effect = RuntimeError("MP caiu")

        with pytest.raises(RuntimeError):
            service.process_webhook(
                event_type="payment",
                external_event_id="evt-1",
                external_resource_id="777",
                payload={},
            )

        payment_repo.mark_event_processed.assert_not_called()


# ============================================================
# Sync order ↔ payment status
# ============================================================


class TestSyncOrderWithPayment:
    def test_approved_confirms_order(self, service, payment_repo):
        order = _order(payment_status="pending")
        service._sync_order_with_payment(order, {"id": "777", "status": "approved"})
        payment_repo.confirm_payment.assert_called_once_with("o1")

    def test_approved_does_not_downgrade_paid(self, service, payment_repo):
        """Regra de não-regressão."""
        order = _order(payment_status="paid")
        service._sync_order_with_payment(order, {"id": "777", "status": "approved"})
        payment_repo.confirm_payment.assert_not_called()

    def test_rejected_marks_failed(self, service, payment_repo):
        order = _order(payment_status="pending")
        service._sync_order_with_payment(order, {"id": "777", "status": "rejected"})
        payment_repo.update_payment_status.assert_called_once_with("o1", "failed")

    def test_rejected_does_not_touch_paid(self, service, payment_repo):
        order = _order(payment_status="paid")
        service._sync_order_with_payment(order, {"id": "777", "status": "rejected"})
        payment_repo.update_payment_status.assert_not_called()

    def test_pending_does_not_change(self, service, payment_repo):
        order = _order(payment_status="pending")
        service._sync_order_with_payment(order, {"id": "777", "status": "in_process"})
        payment_repo.confirm_payment.assert_not_called()
        payment_repo.update_payment_status.assert_not_called()


# ============================================================
# Admin update status (PAYMENT-10, PAYMENT-12)
# ============================================================


class TestAdminUpdateStatus:
    def test_valid_transition(self, service, order_repo):
        order_repo.get_by_id.return_value = _order(status="created")
        order_repo.update_status.return_value = _order(status="paid")
        service.admin_update_status("o1", "paid")
        order_repo.update_status.assert_called_once_with("o1", "paid")

    def test_invalid_transition_raises(self, service, order_repo):
        order_repo.get_by_id.return_value = _order(status="delivered")
        with pytest.raises(ValidationError):
            service.admin_update_status("o1", "paid")

    def test_cancel_paid_keeps_payment_status_paid(
        self, service, order_repo, payment_repo
    ):
        """
        PAYMENT-12: cancelar pedido pago NÃO altera payment_status.
        """
        order = _order(status="paid", payment_status="paid")
        order_repo.get_by_id.return_value = order
        order_repo.update_status.return_value = {**order, "status": "cancelled"}

        service.admin_update_status("o1", "cancelled")

        order_repo.update_status.assert_called_once_with("o1", "cancelled")
        # payment_repo NÃO é chamado
        payment_repo.update_payment_status.assert_not_called()

    def test_404_when_order_not_found(self, service, order_repo):
        order_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.admin_update_status("o-x", "paid")


# ============================================================
# Reconcile (PAYMENT-18, PAYMENT-19)
# ============================================================


class TestReconcile:
    def test_pix_calls_mp_and_syncs(self, service, mp, order_repo, payment_repo):
        order_repo.get_by_id.side_effect = [
            _order(payment_method="pix", payment_external_id="777"),  # 1ª: busca
            _order(payment_method="pix", payment_status="paid"),      # 2ª: retorno final
        ]
        mp.get_payment.return_value = {"id": "777", "status": "approved"}

        service.reconcile("o1")

        mp.get_payment.assert_called_once_with("777")
        payment_repo.confirm_payment.assert_called_once_with("o1")

    def test_card_reconcile_not_implemented(self, service, order_repo):
        order_repo.get_by_id.return_value = _order(
            payment_method="credit_card", payment_external_id="pref-1",
        )
        with pytest.raises(ValidationError, match="Checkout Pro"):
            service.reconcile("o1")

    def test_no_external_id_raises(self, service, order_repo):
        order_repo.get_by_id.return_value = _order()
        with pytest.raises(ValidationError, match="não tem cobrança"):
            service.reconcile("o1")

    def test_404_when_order_not_found(self, service, order_repo):
        order_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            service.reconcile("o-x")