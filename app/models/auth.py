from pydantic import BaseModel, EmailStr, Field, field_validator
from app.utils.validators import PASSWORD_RULES_MESSAGE, is_strong_password


class RegisterRequest(BaseModel):
    """Payload de cadastro."""

    nome: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def validate_strong_password(cls, v: str) -> str:
        if not is_strong_password(v):
            raise ValueError(PASSWORD_RULES_MESSAGE)
        return v


class LoginRequest(BaseModel):
    """Payload de login. NÃO valida força — só o cadastro exige."""

    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    """Payload de recuperação de senha."""

    email: EmailStr


class AuthResponse(BaseModel):
    """Resposta de signup/login bem-sucedido."""

    user_id: str
    access_token: str
    refresh_token: str


class MessageResponse(BaseModel):
    """Resposta genérica de mensagem."""

    message: str
