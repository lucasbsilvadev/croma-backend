from fastapi import HTTPException, status


class AuthError(HTTPException):
    """Credenciais inválidas, token inválido, email não confirmado."""

    def __init__(self, detail: str = "Credenciais inválidas"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ConflictError(HTTPException):
    """Recurso já existe (ex: profile duplicado)."""

    def __init__(self, detail: str = "Recurso já existe"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class ValidationError(HTTPException):
    """Dados inválidos segundo regra de negócio."""

    def __init__(self, detail: str = "Dados inválidos"):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)