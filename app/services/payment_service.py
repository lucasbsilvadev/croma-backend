"""
Regras de negócio do pagamento.
Referência: PAYMENT-14 a PAYMENT-22, PAYMENT-30.
"""
from decimal import Decimal

from app.infra.mp_client import MPClient
from app.repositories.address_repository import AddressRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.order_state_machine import (
    validate_order_transition,
    validate_payment_transition,
)
from app.utils.exceptions import (
    ConflictError,
    NotFoundError,
    PaymentError,
    ValidationError,
)
from app.utils.logging import get_logger
from app.utils.validators import (
    is_valid_cpf_cnpj,
    normalize_cpf_cnpj,
)

logger = get_logger(__name__)


class PaymentService:
    def __init__(
        self,
        mp_client: MPClient | None = None,
        payment_repo: PaymentRepository | None = None,
        order_repo: OrderRepository | None = None,
        address_repo: AddressRepository | None = None,
        product_repo: ProductRepository | None = None,
        profile_repo: ProfileRepository | None = None,
    ):
        self.mp = mp_client or MPClient()
        self.payment_repo = payment_repo or PaymentRepository()
        self.order_repo = order_repo or OrderRepository()
        self.address_repo = address_repo or AddressRepository()
        self.product_repo = product_repo or ProductRepository()
        self.profile_repo = profile_repo or ProfileRepository()

    # ============================================================
    # Validação comum (PAYMENT-14)
    # ============================================================

    def _validate_order_for_payment(
        self, user_id: str, order_id: str, expected_method: str
    ) -> dict:
        """
        Valida que o pedido pode ser pago. Retorna o order.
        Regras compartilhadas entre PIX e cartão.
        """
        order = self.order_repo.get_by_id_and_user(order_id, user_id)
        if not order:
            raise NotFoundError("Pedido não encontrado")

        # payment_status ainda permite?
        if order["payment_status"] not in ("pending",):
            raise ConflictError(
                f"Pedido não permite pagamento "
                f"(payment_status={order['payment_status']})"
            )

        # Já tem cobrança de outro método?
        existing_method = order.get("payment_method")
        if existing_method and existing_method != expected_method:
            raise ConflictError(
                f"Pedido já tem cobrança em {existing_method}. "
                f"Não é possível pagar com {expected_method}."
            )

        # Consistência do valor (PAYMENT-17): deriva do banco, não do front.
        if Decimal(order["total"]) <= 0:
            raise ValidationError("Valor do pedido inválido")

        return order

    def _get_user_cpf_cnpj(self, user_id: str) -> str:
        """CPF/CNPJ vem do perfil autenticado (PAYMENT-02)."""
        profile = self.profile_repo.get_by_user_id(user_id)
        if not profile or not profile.get("cpf_cnpj"):
            raise ValidationError(
                "CPF/CNPJ não cadastrado. Complete seu perfil antes de pagar."
            )
        cpf_cnpj = normalize_cpf_cnpj(profile["cpf_cnpj"])
        if not is_valid_cpf_cnpj(cpf_cnpj):
            raise ValidationError("CPF/CNPJ cadastrado é inválido")
        return cpf_cnpj

    def _get_payer_email(self, user_id: str) -> str:
        """Email do payer para o MP. Vem do profile autenticado."""
        profile = self.profile_repo.get_by_user_id(user_id)
        # O profile não tem email; usamos o email do metadata do auth.
        # Fallback: campo `email` passado pelo middleware (não temos aqui).
        # Por ora, usamos um placeholder derivado do user_id — o ideal é
        # injetar o email no service. Ajuste no _get_user_context abaixo.
        return profile.get("email") if profile else None

    # ============================================================
    # PIX (PAYMENT-02, PAYMENT-15)
    # ============================================================

    def create_pix(
        self,
        user_id: str,
        user_email: str,
        order_id: str,
    ) -> dict:
        """
        Cria cobrança PIX. Se já existe, retorna a referência existente.
        """
        order = self._validate_order_for_payment(user_id, order_id, "pix")

        # Já tem PIX criado? Retorna o mesmo (idempotência PAYMENT-15)
        if order.get("payment_method") == "pix" and order.get("payment_external_id"):
            payment = self.mp.get_payment(order["payment_external_id"])
            return self._pix_response(payment)

        cpf_cnpj = self._get_user_cpf_cnpj(user_id)
        tipo = "CPF" if len(cpf_cnpj) == 11 else "CNPJ"

        idem_key = self.mp.new_idempotency_key()

        payload = {
            "transaction_amount": float(Decimal(order["total"])),
            "description": f"Pedido Croma Drip #{order['id'][:8]}",
            "payment_method_id": "pix",
            "external_reference": order["id"],
            "payer": {
                "email": user_email,
                "identification": {"type": tipo, "number": cpf_cnpj},
            },
        }

        payment = self.mp.create_pix_payment(payload, idempotency_key=idem_key)

        payment_id = str(payment["id"])

        # Persiste referência
        self.payment_repo.update_payment_reference(
            order_id=order["id"],
            payment_method="pix",
            payment_external_id=payment_id,
        )

        logger.info(
            "PIX criado",
            extra={"event": "PAYMENT_CREATED", "user_id": user_id},
        )

        return self._pix_response(payment)

    @staticmethod
    def _pix_response(payment: dict) -> dict:
        """Extrai os campos de PIX da resposta do MP."""
        poi = (payment.get("point_of_interaction") or {}).get("transaction_data") or {}
        return {
            "payment_id": str(payment["id"]),
            "status": payment.get("status", "pending"),
            "qr_code": poi.get("qr_code"),
            "qr_code_base64": poi.get("qr_code_base64"),
            "ticket_url": poi.get("ticket_url"),
            "expires_at": payment.get("date_of_expiration"),
        }

    # ============================================================
    # Cartão (Checkout Pro) — PAYMENT-03, PAYMENT-16
    # ============================================================

    def create_card_preference(
        self,
        user_id: str,
        user_email: str,
        order_id: str,
        *,
        back_urls: dict | None = None,
    ) -> dict:
        """
        Cria preferência do Checkout Pro. Retorna init_point.

        `back_urls` é opcional: o frontend ainda não existe, então o
        backend não deve inventar URLs. Quando `back_urls.success`
        estiver presente, `auto_return` é habilitado — o MP exige o
        par para aceitar `auto_return=approved`.
        """
        order = self._validate_order_for_payment(user_id, order_id, "credit_card")

        # Já tem preferência criada? Retorna a mesma.
        if order.get("payment_method") == "credit_card" and order.get("payment_external_id"):
            pref_id = order["payment_external_id"]
            pref = self.mp._request("GET", f"/checkout/preferences/{pref_id}")
            return {
                "preference_id": pref_id,
                "init_point": pref.get("init_point"),
                "sandbox_init_point": pref.get("sandbox_init_point"),
            }

        items = self.order_repo.list_items_by_order(order["id"])

        preference_items = [
            {
                "title": item["product_nome"],
                "quantity": item["quantidade"],
                "unit_price": float(Decimal(item["preco_unitario"])),
                "currency_id": "BRL",
            }
            for item in items
        ]

        # Frete como item separado (opcional, mas ajuda o cliente)
        if Decimal(order["frete"]) > 0:
            preference_items.append({
                "title": "Frete",
                "quantity": 1,
                "unit_price": float(Decimal(order["frete"])),
                "currency_id": "BRL",
            })

        # ---- Payload do Checkout Pro ----
        # Só inclui back_urls/auto_return quando temos URLs reais.
        # Sem frontend, o front não passa back_urls → enviamos somente
        # itens + external_reference + payer. MP aceita sem problema.
        # Com back_urls.success, habilitamos auto_return=approved.
        payload: dict = {
            "items": preference_items,
            "external_reference": order["id"],
            "payer": {"email": user_email},
        }

        if back_urls:
            payload["back_urls"] = back_urls
            if back_urls.get("success"):
                payload["auto_return"] = "approved"

        pref = self.mp.create_card_preference(
            payload, idempotency_key=self.mp.new_idempotency_key()
        )

        pref_id = str(pref["id"])

        self.payment_repo.update_payment_reference(
            order_id=order["id"],
            payment_method="credit_card",
            payment_external_id=pref_id,
        )

        logger.info(
            "Checkout Pro criado",
            extra={"event": "PAYMENT_CREATED", "user_id": user_id},
        )

        return {
            "preference_id": pref_id,
            "init_point": pref.get("init_point"),
            "sandbox_init_point": pref.get("sandbox_init_point"),
        }

    # ============================================================
    # Webhook (PAYMENT-04, PAYMENT-07, PAYMENT-08)
    # ============================================================

    def process_webhook(
        self,
        *,
        event_type: str,
        external_event_id: str,
        external_resource_id: str | None,
        payload: dict,
    ) -> dict:
        """
        Processa um webhook já validado criptograficamente.
        Idempotente: se o evento já existe, retorna sem reprocessar.
        """
        # 1. Persiste (idempotência via unique constraint)
        event = self.payment_repo.create_event(
            external_event_id=external_event_id,
            external_resource_id=external_resource_id,
            event_type=event_type,
            payload=payload,
        )

        if event is None:
            # Duplicado
            logger.info(
                "Webhook duplicado",
                extra={"event": "PAYMENT_WEBHOOK_DUPLICATE"},
            )
            return {"received": True, "duplicate": True}

        # 2. Processa conforme tipo
        try:
            if event_type == "payment":
                self._handle_payment_event(external_resource_id)
            elif event_type == "merchant_order":
                self._handle_merchant_order_event(external_resource_id)
            else:
                logger.info(
                    "Webhook tipo ignorado",
                    extra={"event": "PAYMENT_WEBHOOK_RECEIVED"},
                )
        except Exception:
            # PAYMENT-08: persistido mas não processado → processed_at = NULL
            logger.warning(
                "Falha ao processar webhook (persistido pra reconciliação)",
                extra={"event": "PAYMENT_WEBHOOK_PROCESS_FAILED"},
            )
            raise

        # 3. Marca como processado
        self.payment_repo.mark_event_processed(event["id"])

        return {"received": True, "duplicate": False}

    def _handle_payment_event(self, payment_id: str) -> None:
        """Consulta o pagamento no MP e atualiza o pedido."""
        if not payment_id:
            return

        payment = self.mp.get_payment(str(payment_id))
        external_ref = payment.get("external_reference")

        if not external_ref:
            logger.info(
                "Pagamento sem external_reference",
                extra={"event": "PAYMENT_STATUS_UPDATED"},
            )
            return

        order = self.payment_repo.get_order_by_external_id(str(payment["id"])) \
            or self.order_repo.get_by_id(external_ref)

        if not order:
            return

        self._sync_order_with_payment(order, payment)

    def _handle_merchant_order_event(self, merchant_order_id: str) -> None:
        """
        Consulta a merchant_order, identifica pagamentos e sincroniza.
        """
        if not merchant_order_id:
            return

        mo = self.mp.get_merchant_order(str(merchant_order_id))
        external_ref = mo.get("external_reference")
        payments = mo.get("payments") or []

        for p in payments:
            payment_id = p.get("id")
            if not payment_id:
                continue
            payment = self.mp.get_payment(str(payment_id))
            order = self.order_repo.get_by_id(external_ref) if external_ref else None
            if order:
                self._sync_order_with_payment(order, payment)

    def _sync_order_with_payment(self, order: dict, payment: dict) -> None:
        """
        Aplica a transição correta conforme o estado do MP.
        Nunca regride payment_status (PAYMENT-11).
        """
        mp_status = payment.get("status")

        if mp_status == "approved":
            if order["payment_status"] == "paid":
                return  # já pago, não regride
            validate_payment_transition(order["payment_status"], "paid")
            self.payment_repo.confirm_payment(order["id"])
            logger.info(
                "Pagamento confirmado",
                extra={"event": "PAYMENT_STATUS_UPDATED"},
            )
        elif mp_status in ("rejected", "cancelled"):
            if order["payment_status"] != "pending":
                return
            validate_payment_transition(order["payment_status"], "failed")
            self.payment_repo.update_payment_status(order["id"], "failed")
            logger.info(
                "Pagamento rejeitado",
                extra={"event": "PAYMENT_STATUS_UPDATED"},
            )
        # outros (pending, in_process) → não altera

    # ============================================================
    # Reconciliação admin (PAYMENT-18, PAYMENT-19)
    # ============================================================

    def reconcile(self, order_id: str) -> dict:
        """Consulta o MP e sincroniza payment_status do pedido."""
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundError("Pedido não encontrado")

        method = order.get("payment_method")
        external_id = order.get("payment_external_id")

        if not external_id:
            raise ValidationError("Pedido não tem cobrança externa para reconciliar")

        if method == "pix":
            payment = self.mp.get_payment(external_id)
            self._sync_order_with_payment(order, payment)
        elif method == "credit_card":
            # external_id é preference_id; consulta merchant_orders
            # pelo external_reference = order.id
            # Solução robusta: listar pagamentos por external_reference.
            # Aqui simplificamos: consulta direta se possível.
            # TODO: usar /v1/payments/search?external_reference=...
            raise ValidationError(
                "Reconciliação de Checkout Pro requer busca por external_reference. "
                "Implementar em bloco separado."
            )
        else:
            raise ValidationError("Método de pagamento desconhecido")

        logger.info(
            "Reconciliação executada",
            extra={"event": "PAYMENT_RECONCILED"},
        )
        return self.order_repo.get_by_id(order_id)

    # ============================================================
    # Admin: mudar status operacional (PAYMENT-10, PAYMENT-12)
    # ============================================================

    def admin_update_status(self, order_id: str, new_status: str) -> dict:
        """
        Altera status operacional validando a máquina de estados.
        Cancelar pedido pago NÃO altera payment_status (PAYMENT-12).
        """
        order = self.order_repo.get_by_id(order_id)
        if not order:
            raise NotFoundError("Pedido não encontrado")

        validate_order_transition(order["status"], new_status)

        updated = self.order_repo.update_status(order_id, new_status)

        logger.info(
            "Status do pedido atualizado",
            extra={"event": "PAYMENT_STATUS_UPDATED"},
        )
        return updated