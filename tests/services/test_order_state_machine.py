"""
Testes da máquina de estados.
Referência: PAYMENT-10, PAYMENT-11.

Sem mock — função pura.
"""
import pytest

from app.services.order_state_machine import (
    ORDER_TRANSITIONS,
    PAYMENT_TRANSITIONS,
    validate_order_transition,
    validate_payment_transition,
)
from app.utils.exceptions import ValidationError


# ============================================================
# ORDER — transições VÁLIDAS (PAYMENT-10)
# ============================================================


class TestValidOrderTransitions:
    def test_created_to_paid(self):
        validate_order_transition("created", "paid")

    def test_created_to_cancelled(self):
        validate_order_transition("created", "cancelled")

    def test_paid_to_production(self):
        validate_order_transition("paid", "production")

    def test_paid_to_cancelled(self):
        validate_order_transition("paid", "cancelled")

    def test_production_to_shipped(self):
        validate_order_transition("production", "shipped")

    def test_production_to_cancelled(self):
        validate_order_transition("production", "cancelled")

    def test_shipped_to_delivered(self):
        validate_order_transition("shipped", "delivered")

    def test_shipped_to_cancelled(self):
        validate_order_transition("shipped", "cancelled")


# ============================================================
# ORDER — transições PROIBIDAS
# ============================================================


class TestInvalidOrderTransitions:
    def test_delivered_is_final(self):
        """Nenhuma transição sai de delivered."""
        for new in ORDER_TRANSITIONS["delivered"]:
            pytest.fail(f"delivered deveria ser final, mas permite {new}")
        with pytest.raises(ValidationError):
            validate_order_transition("delivered", "paid")

    def test_cancelled_is_final(self):
        with pytest.raises(ValidationError):
            validate_order_transition("cancelled", "paid")

    def test_cannot_skip_steps(self):
        """created → shipped direto é proibido."""
        with pytest.raises(ValidationError):
            validate_order_transition("created", "shipped")

    def test_cannot_go_backwards(self):
        """shipped → paid é proibido."""
        with pytest.raises(ValidationError):
            validate_order_transition("shipped", "paid")

    def test_cancelled_to_production_forbidden(self):
        with pytest.raises(ValidationError):
            validate_order_transition("cancelled", "production")

    def test_unknown_state_fails_closed(self):
        with pytest.raises(ValidationError, match="desconhecido"):
            validate_order_transition("foobar", "paid")


# ============================================================
# PAYMENT — transições VÁLIDAS (PAYMENT-11)
# ============================================================


class TestValidPaymentTransitions:
    def test_pending_to_paid(self):
        validate_payment_transition("pending", "paid")

    def test_pending_to_failed(self):
        validate_payment_transition("pending", "failed")

    def test_paid_to_refunded(self):
        validate_payment_transition("paid", "refunded")


# ============================================================
# PAYMENT — regra de não-regressão (PAYMENT-11)
# ============================================================


class TestPaymentNonRegression:
    def test_paid_cannot_go_to_pending(self):
        """Webhook atrasado NÃO pode rebaixar."""
        with pytest.raises(ValidationError):
            validate_payment_transition("paid", "pending")

    def test_paid_cannot_go_to_failed(self):
        with pytest.raises(ValidationError):
            validate_payment_transition("paid", "failed")

    def test_failed_is_final(self):
        with pytest.raises(ValidationError):
            validate_payment_transition("failed", "paid")

    def test_refunded_is_final(self):
        with pytest.raises(ValidationError):
            validate_payment_transition("refunded", "paid")

    def test_unknown_state_fails_closed(self):
        with pytest.raises(ValidationError, match="desconhecido"):
            validate_payment_transition("whatever", "paid")