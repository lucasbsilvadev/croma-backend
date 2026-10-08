"""
Máquina de estados do pedido.
Referência: PAYMENT-10, PAYMENT-11.
"""
from app.utils.exceptions import ValidationError

# ============================================================
# Status operacional (orders.status)
# ============================================================

ORDER_TRANSITIONS: dict[str, set[str]] = {
    "created":    {"paid", "cancelled"},
    "paid":       {"production", "cancelled"},
    "production": {"shipped", "cancelled"},
    "shipped":    {"delivered", "cancelled"},
    "delivered":  set(),   # final
    "cancelled":  set(),   # final
}


def validate_order_transition(current: str, new: str) -> None:
    """
    Levanta ValidationError se a transição é inválida.
    Fail-closed: estado desconhecido → erro.
    """
    allowed = ORDER_TRANSITIONS.get(current)
    if allowed is None:
        raise ValidationError(f"Status atual desconhecido: {current}")
    if new not in allowed:
        raise ValidationError(
            f"Transição inválida: {current} → {new}"
        )


# ============================================================
# Status financeiro (orders.payment_status)
# ============================================================

PAYMENT_TRANSITIONS: dict[str, set[str]] = {
    "pending":  {"paid", "failed"},
    "paid":     {"refunded"},
    "failed":   set(),     # final
    "refunded": set(),     # final
}


def validate_payment_transition(current: str, new: str) -> None:
    """
    Levanta ValidationError se transição financeira inválida.
    REGRA DE NÃO-REGRESSÃO (PAYMENT-11): paid → pending/failed é proibido.
    """
    allowed = PAYMENT_TRANSITIONS.get(current)
    if allowed is None:
        raise ValidationError(f"payment_status atual desconhecido: {current}")
    if new not in allowed:
        raise ValidationError(
            f"Transição de pagamento inválida: {current} → {new}"
        )