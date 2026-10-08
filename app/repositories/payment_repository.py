"""
Acesso a `payment_events` e operações de pagamento em `orders`.
Referência: PAYMENT-07, PAYMENT-29.
"""
from app.config.supabase import supabase_admin
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PaymentRepository:
    """Único ponto de acesso a payment_events e campos de pagamento de orders."""

    # ============================================================
    # payment_events
    # ============================================================

    def create_event(
        self,
        *,
        external_event_id: str,
        external_resource_id: str | None,
        event_type: str,
        payload: dict,
        provider: str = "mercadopago",
    ) -> dict | None:
        """
        Persiste um evento. Retorna None se já existia (duplicado),
        ou a linha criada.

        Idempotência garantida pela constraint
        payment_events_provider_event_uniq (provider, external_event_id).
        """
        try:
            res = (
                supabase_admin.table("payment_events")
                .insert({
                    "provider": provider,
                    "external_event_id": external_event_id,
                    "external_resource_id": external_resource_id,
                    "event_type": event_type,
                    "payload": payload,
                })
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as e:
            # 23505 = unique violation → evento duplicado
            code = getattr(e, "code", None)
            if code == "23505":
                return None
            raise

    def mark_event_processed(self, event_id: str) -> None:
        """Marca processed_at = now()."""
        (
            supabase_admin.table("payment_events")
            .update({"processed_at": "now()"})
            .eq("id", event_id)
            .execute()
        )

    def find_event_by_external_id(
        self, external_event_id: str, provider: str = "mercadopago"
    ) -> dict | None:
        res = (
            supabase_admin.table("payment_events")
            .select("*")
            .eq("provider", provider)
            .eq("external_event_id", external_event_id)
            .execute()
        )
        return res.data[0] if res.data else None

    # ============================================================
    # orders (campos de pagamento)
    # ============================================================

    def update_payment_reference(
        self,
        order_id: str,
        *,
        payment_method: str,
        payment_external_id: str,
    ) -> dict:
        """Associa método + referência externa ao pedido."""
        res = (
            supabase_admin.table("orders")
            .update({
                "payment_method": payment_method,
                "payment_external_id": payment_external_id,
            })
            .eq("id", order_id)
            .execute()
        )
        return res.data[0]

    def confirm_payment(self, order_id: str) -> dict:
        """
        Marca pagamento como aprovado:
          - payment_status = paid
          - status = paid
          - paid_at = now()
        Referência: PAYMENT-12.
        """
        res = (
            supabase_admin.table("orders")
            .update({
                "payment_status": "paid",
                "status": "paid",
                "paid_at": "now()",
            })
            .eq("id", order_id)
            .execute()
        )
        return res.data[0]

    def update_payment_status(self, order_id: str, payment_status: str) -> dict:
        """Atualiza só payment_status (ex: failed)."""
        res = (
            supabase_admin.table("orders")
            .update({"payment_status": payment_status})
            .eq("id", order_id)
            .execute()
        )
        return res.data[0]

    def update_order_status(self, order_id: str, status: str) -> dict:
        """Atualiza só status operacional."""
        res = (
            supabase_admin.table("orders")
            .update({"status": status})
            .eq("id", order_id)
            .execute()
        )
        return res.data[0]

    def get_order_by_external_id(self, external_id: str) -> dict | None:
        """Busca pedido por payment_external_id. Usado no webhook."""
        res = (
            supabase_admin.table("orders")
            .select("*")
            .eq("payment_external_id", external_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None