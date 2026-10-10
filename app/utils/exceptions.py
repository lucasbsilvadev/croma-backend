from fastapi import HTTPException, status


class AuthError(HTTPException):
    """Credenciais inválidas, token inválido, email não confirmado."""

    def __init__(self, detail: str = "Credenciais inválidas"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class PermissionDeniedError(HTTPException):
    """Usuário autenticado, mas sem permissão para a ação."""

    def __init__(self, detail: str = "Permissão negada"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundError(HTTPException):
    """Recurso não encontrado."""

    def __init__(self, detail: str = "Recurso não encontrado"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(HTTPException):
    """Recurso já existe (ex: profile duplicado, slug duplicado)."""

    def __init__(self, detail: str = "Recurso já existe"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class ValidationError(HTTPException):
    """Dados inválidos segundo regra de negócio."""

    def __init__(self, detail: str = "Dados inválidos"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
        )

class PaymentError(HTTPException):
    """Erro genérico do módulo de pagamento."""

    def __init__(self, detail: str = "Erro no pagamento",
                 status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class InvalidSignatureError(HTTPException):
    """
    Assinatura HMAC inválida no webhook do Mercado Pago.
    Nunca deve retornar detalhes — só 401 seco.
    """

    def __init__(self, detail: str = "Assinatura inválida"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
